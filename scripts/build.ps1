param(
    [string]$UpdateFeedUrl = "https://raw.githubusercontent.com/Yufe1210/local-pdf-toolbox/main/updates/update.json",
    [string]$CertificateThumbprint = "",
    [switch]$ReleaseBuild,
    [switch]$SkipPackagedSmokeTest,
    [switch]$SkipInstaller
)

$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $Root

function Get-FreeLoopbackPort {
    $listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, 0)
    $listener.Start()
    try {
        return ([System.Net.IPEndPoint]$listener.LocalEndpoint).Port
    }
    finally {
        $listener.Stop()
    }
}

function Find-CodeSigningCertificate([string]$Thumbprint) {
    $normalized = ($Thumbprint -replace "\s", "").ToUpperInvariant()
    foreach ($store in @("Cert:\CurrentUser\My", "Cert:\LocalMachine\My")) {
        $certificate = Get-ChildItem -LiteralPath $store -ErrorAction SilentlyContinue |
            Where-Object {
                $_.Thumbprint -eq $normalized -and
                $_.HasPrivateKey -and
                $_.NotBefore -le (Get-Date) -and
                $_.NotAfter -gt (Get-Date) -and
                $_.EnhancedKeyUsageList.ObjectId -contains "1.3.6.1.5.5.7.3.3"
            } |
            Select-Object -First 1
        if ($certificate) {
            return $certificate
        }
    }
    throw "找不到可用且含私密金鑰的程式碼簽章憑證：$Thumbprint"
}

function Sign-Artifact(
    [string]$Path,
    [System.Security.Cryptography.X509Certificates.X509Certificate2]$Certificate
) {
    $signature = Set-AuthenticodeSignature `
        -LiteralPath $Path `
        -Certificate $Certificate `
        -HashAlgorithm SHA256 `
        -TimestampServer "http://timestamp.digicert.com"
    if ($signature.Status -ne "Valid") {
        throw "簽署或驗證失敗：$Path`n$($signature.StatusMessage)"
    }
}

function Sign-ApplicationBundle(
    [string]$Directory,
    [System.Security.Cryptography.X509Certificates.X509Certificate2]$Certificate
) {
    $artifacts = @(
        Get-ChildItem -LiteralPath $Directory -Recurse -File |
            Where-Object { $_.Extension -in ".exe", ".dll", ".pyd" }
    )
    $signedCount = 0
    foreach ($artifact in $artifacts) {
        $status = (Get-AuthenticodeSignature -LiteralPath $artifact.FullName).Status
        if ($status -ne "Valid") {
            Sign-Artifact $artifact.FullName $Certificate
            $signedCount += 1
        }
    }
    $invalid = $artifacts | Where-Object {
        (Get-AuthenticodeSignature -LiteralPath $_.FullName).Status -ne "Valid"
    }
    if ($invalid) {
        throw "應用程式目錄仍含未通過簽章驗證的執行檔。"
    }
    Write-Host "已簽署 $signedCount 個執行檔，並驗證全部 $($artifacts.Count) 個 PE 檔案。"
}

if ($ReleaseBuild) {
    if (-not $UpdateFeedUrl.StartsWith("https://")) {
        throw "正式建置必須提供 HTTPS UpdateFeedUrl。"
    }
    if ($CertificateThumbprint -and $SkipPackagedSmokeTest) {
        throw "簽章正式建置不得略過打包後 smoke test。"
    }
    if (-not $CertificateThumbprint) {
        Write-Warning "正在建立未簽章公開測試版；Windows 可能警告或封鎖，發布前必須在乾淨 Windows 驗收。"
    }
}

$version = (& uv run python -c "from pdf_toolbox import __version__; print(__version__)").Trim()
if (-not $version) {
    throw "無法取得應用程式版本。"
}
$signingCertificate = if ($CertificateThumbprint) {
    Find-CodeSigningCertificate $CertificateThumbprint
}
else {
    $null
}

Write-Host "[1/6] 同步 uv 環境"
& uv sync --all-groups

Write-Host "[2/6] 執行測試"
$env:PYTHONUTF8 = "1"
& uv run python -m pytest
if ($LASTEXITCODE -ne 0) {
    throw "測試失敗。"
}

Write-Host "[3/6] 產生建置設定"
$generatedDir = Join-Path $Root "build\generated"
New-Item -ItemType Directory -Force $generatedDir | Out-Null
$generatedConfig = Join-Path $generatedDir "update-config.json"
$configJson = @{
    update_feed_url = $UpdateFeedUrl
} | ConvertTo-Json
[System.IO.File]::WriteAllText(
    $generatedConfig,
    $configJson,
    [System.Text.UTF8Encoding]::new($false)
)
$env:PDF_TOOLBOX_UPDATE_CONFIG = $generatedConfig

Write-Host "[4/6] 建立 PyInstaller onedir"
& uv run python -m PyInstaller --noconfirm --clean packaging\pdf_toolbox.spec
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller 建置失敗。"
}

$requiredModules = @(
    Get-Content -Encoding UTF8 -LiteralPath (Join-Path $Root "packaging\required_toolbox_modules.txt") |
        Where-Object { $_.Trim() }
)
$pyzToc = Join-Path $Root "build\pdf_toolbox\PYZ-00.toc"
if (-not (Test-Path -LiteralPath $pyzToc)) {
    throw "找不到 PyInstaller 模組清單：$pyzToc"
}
$missingModules = @(
    foreach ($module in $requiredModules) {
        if (-not (Select-String -LiteralPath $pyzToc -SimpleMatch "('$module'," -Quiet)) {
            $module
        }
    }
)
if ($missingModules.Count -gt 0) {
    throw "打包後缺少必要模組：$($missingModules -join ', ')"
}
Write-Host "已驗證 $($requiredModules.Count) 個本機 PDF 工具箱模組均已封裝。"

$distDir = Join-Path $Root "dist\本機PDF工具箱"
$appExe = Join-Path $distDir "本機PDF工具箱.exe"
if (-not (Test-Path -LiteralPath $appExe)) {
    throw "找不到打包後執行檔：$appExe"
}
$pdfiumDll = Get-ChildItem -LiteralPath $distDir -Recurse -File -Filter "pdfium.dll" | Select-Object -First 1
if (-not $pdfiumDll) {
    throw "打包後缺少 PDFium 原生程式庫。"
}
$pdfiumLicenses = @(
    Get-ChildItem -LiteralPath $distDir -Recurse -File |
        Where-Object { $_.FullName -match "pypdfium2-.+\.dist-info.+licenses" }
)
if ($pdfiumLicenses.Count -eq 0) {
    throw "打包後缺少 pypdfium2 或 PDFium 授權文件。"
}
$gridFrontend = Join-Path $distDir "_internal\pdf_toolbox\ui\pdf_grid_frontend\index.html"
if (-not (Test-Path -LiteralPath $gridFrontend)) {
    throw "打包後缺少 PDF 響應式拖曳網格前端。"
}
Write-Host "已驗證 PDFium 與第三方授權文件均已封裝。"
if ($signingCertificate) {
    Sign-ApplicationBundle $distDir $signingCertificate
}

if ($SkipPackagedSmokeTest) {
    Write-Warning "[5/6] 已略過打包後 smoke test；必須在其他乾淨 Windows 完整驗收後才能發布。"
}
else {
    Write-Host "[5/6] 驗證打包後自我檢查與本機服務"
    $selfTest = Start-Process -FilePath $appExe -ArgumentList "--self-test" -Wait -PassThru -WindowStyle Hidden
    if ($selfTest.ExitCode -ne 0) {
        $selfTestLog = Join-Path (Join-Path $env:LOCALAPPDATA "LocalPDFToolbox") "self-test.log"
        $detail = if (Test-Path -LiteralPath $selfTestLog) {
            Get-Content -Raw -Encoding UTF8 -LiteralPath $selfTestLog
        }
        else {
            "未產生 self-test.log。"
        }
        throw "打包後自我檢查失敗：`n$detail"
    }
    $port = Get-FreeLoopbackPort
    $process = Start-Process -FilePath $appExe -ArgumentList @("--run-server", "--port", "$port") -PassThru -WindowStyle Hidden
    try {
        $ready = $false
        for ($attempt = 0; $attempt -lt 80; $attempt++) {
            if ($process.HasExited) {
                throw "打包後程式在健康檢查前結束。"
            }
            try {
                $response = Invoke-WebRequest -UseBasicParsing "http://127.0.0.1:$port/_stcore/health" -TimeoutSec 1
                if ($response.StatusCode -eq 200 -and $response.Content -eq "ok") {
                    $ready = $true
                    break
                }
            }
            catch {
                Start-Sleep -Milliseconds 250
            }
        }
        if (-not $ready) {
            throw "打包後程式健康檢查逾時。"
        }
        $listeners = Get-NetTCPConnection -State Listen -LocalPort $port
        if (-not $listeners -or ($listeners | Where-Object { $_.LocalAddress -ne "127.0.0.1" })) {
            throw "打包後程式未限定在 127.0.0.1。"
        }
    }
    finally {
        if (-not $process.HasExited) {
            Stop-Process -Id $process.Id -Force
            $process.WaitForExit()
        }
    }
}

if ($SkipInstaller) {
    Write-Host "[6/6] 已略過 Inno Setup"
    exit 0
}

Write-Host "[6/6] 建立 Inno Setup 安裝程式"
$isccCommand = Get-Command iscc.exe -ErrorAction SilentlyContinue
$isccCandidates = @(
    if ($isccCommand) { $isccCommand.Source }
    (Join-Path ${env:ProgramFiles(x86)} "Inno Setup 6\ISCC.exe")
    (Join-Path $env:LOCALAPPDATA "Programs\Inno Setup 6\ISCC.exe")
)
$iscc = $isccCandidates | Where-Object { $_ -and (Test-Path -LiteralPath $_) } | Select-Object -First 1
if (-not $iscc) {
    throw "找不到 Inno Setup 6 的 ISCC.exe。"
}

$releaseDir = Join-Path $Root "release"
$outputBaseName = if ($ReleaseBuild) {
    "LocalPDFToolbox-Setup-v$version"
}
else {
    "LocalPDFToolbox-Setup-v$version-unsigned-test"
}
& $iscc "/DMyAppVersion=$version" "/DSourceDir=$distDir" "/DOutputDir=$releaseDir" "/DOutputBaseName=$outputBaseName" packaging\installer.iss
if ($LASTEXITCODE -ne 0) {
    throw "Inno Setup 建置失敗。"
}

$installer = Join-Path $releaseDir "$outputBaseName.exe"
if (-not (Test-Path -LiteralPath $installer)) {
    throw "找不到安裝程式：$installer"
}
if ($signingCertificate) {
    Sign-Artifact $installer $signingCertificate
}

$hash = (Get-FileHash -LiteralPath $installer -Algorithm SHA256).Hash.ToLowerInvariant()
[System.IO.File]::WriteAllText(
    "$installer.sha256",
    "$hash  $([System.IO.Path]::GetFileName($installer))`n",
    [System.Text.UTF8Encoding]::new($false)
)
Write-Host "完成：$installer"
