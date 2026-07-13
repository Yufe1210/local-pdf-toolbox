param(
    [string]$UpdateFeedUrl = "",
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

function Find-SignTool {
    $command = Get-Command signtool.exe -ErrorAction SilentlyContinue
    if ($command) {
        return $command.Source
    }
    $kits = Join-Path ${env:ProgramFiles(x86)} "Windows Kits\10\bin"
    if (Test-Path $kits) {
        return Get-ChildItem -LiteralPath $kits -Recurse -File -Filter signtool.exe |
            Where-Object { $_.FullName -like "*\x64\signtool.exe" } |
            Sort-Object FullName -Descending |
            Select-Object -First 1 -ExpandProperty FullName
    }
    return $null
}

function Sign-Artifact([string]$Path, [string]$Thumbprint) {
    $signTool = Find-SignTool
    if (-not $signTool) {
        throw "找不到 signtool.exe，無法建立正式簽章。"
    }
    & $signTool sign /sha1 $Thumbprint /fd SHA256 /tr http://timestamp.digicert.com /td SHA256 $Path
    if ($LASTEXITCODE -ne 0) {
        throw "簽署失敗：$Path"
    }
}

if ($ReleaseBuild) {
    if ($SkipPackagedSmokeTest) {
        throw "正式建置不得略過打包後 smoke test。"
    }
    if (-not $UpdateFeedUrl.StartsWith("https://")) {
        throw "正式建置必須提供 HTTPS UpdateFeedUrl。"
    }
    if (-not $CertificateThumbprint) {
        throw "正式建置必須提供 CertificateThumbprint。"
    }
}

$version = (& uv run python -c "from pdf_toolbox import __version__; print(__version__)").Trim()
if (-not $version) {
    throw "無法取得應用程式版本。"
}

Write-Host "[1/6] 同步 uv 環境"
& uv sync --all-groups

Write-Host "[2/6] 執行測試"
$env:PYTHONUTF8 = "1"
& uv run pytest
if ($LASTEXITCODE -ne 0) {
    throw "測試失敗。"
}

Write-Host "[3/6] 產生建置設定"
$generatedDir = Join-Path $Root "build\generated"
New-Item -ItemType Directory -Force $generatedDir | Out-Null
$generatedConfig = Join-Path $generatedDir "update-config.json"
$configJson = @{
    update_feed_url = $UpdateFeedUrl
    require_signed_updates = $true
} | ConvertTo-Json
[System.IO.File]::WriteAllText(
    $generatedConfig,
    $configJson,
    [System.Text.UTF8Encoding]::new($false)
)
$env:PDF_TOOLBOX_UPDATE_CONFIG = $generatedConfig

Write-Host "[4/6] 建立 PyInstaller onedir"
& uv run pyinstaller --noconfirm --clean packaging\pdf_toolbox.spec
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller 建置失敗。"
}

$distDir = Join-Path $Root "dist\本機PDF工具箱"
$appExe = Join-Path $distDir "本機PDF工具箱.exe"
if (-not (Test-Path -LiteralPath $appExe)) {
    throw "找不到打包後執行檔：$appExe"
}
if ($CertificateThumbprint) {
    Sign-Artifact $appExe $CertificateThumbprint
}

if ($SkipPackagedSmokeTest) {
    Write-Warning "[5/6] 已略過打包後 smoke test；此產物不得作為正式發布版。"
}
else {
    Write-Host "[5/6] 驗證打包後本機服務"
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
    "本機PDF工具箱-安裝程式"
}
else {
    "本機PDF工具箱-安裝程式-未簽章測試版"
}
& $iscc "/DMyAppVersion=$version" "/DSourceDir=$distDir" "/DOutputDir=$releaseDir" "/DOutputBaseName=$outputBaseName" packaging\installer.iss
if ($LASTEXITCODE -ne 0) {
    throw "Inno Setup 建置失敗。"
}

$installer = Join-Path $releaseDir "$outputBaseName.exe"
if (-not (Test-Path -LiteralPath $installer)) {
    throw "找不到安裝程式：$installer"
}
if ($CertificateThumbprint) {
    Sign-Artifact $installer $CertificateThumbprint
}

$hash = (Get-FileHash -LiteralPath $installer -Algorithm SHA256).Hash.ToLowerInvariant()
[System.IO.File]::WriteAllText(
    "$installer.sha256",
    "$hash  $([System.IO.Path]::GetFileName($installer))`n",
    [System.Text.UTF8Encoding]::new($false)
)
Write-Host "完成：$installer"
