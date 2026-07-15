param(
    [Parameter(Mandatory = $true)]
    [string]$InstallerPath,
    [string]$ExpectedVersion = "0.1.0",
    [switch]$AllowUnsignedDevelopmentBuild
)

$ErrorActionPreference = "Stop"
$AppName = "本機 PDF 工具箱"
$AppExeName = "本機PDF工具箱.exe"
$InstallDir = Join-Path $env:LOCALAPPDATA "Programs\LocalPDFToolbox"
$AppExe = Join-Path $InstallDir $AppExeName
$DataDir = Join-Path $env:LOCALAPPDATA "LocalPDFToolbox"
$RuntimePath = Join-Path $DataDir "runtime.json"
$StartMenuDir = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\本機 PDF 工具箱"
$DesktopShortcut = Join-Path ([Environment]::GetFolderPath("Desktop")) "本機 PDF 工具箱.lnk"
$InstalledByScript = $false
$LauncherProcess = $null

function Wait-Until([scriptblock]$Condition, [int]$TimeoutSeconds, [string]$FailureMessage) {
    $deadline = [DateTime]::UtcNow.AddSeconds($TimeoutSeconds)
    do {
        if (& $Condition) {
            return
        }
        Start-Sleep -Milliseconds 250
    } while ([DateTime]::UtcNow -lt $deadline)
    throw $FailureMessage
}

function Stop-VerifiedLauncher {
    if (-not (Test-Path -LiteralPath $RuntimePath)) {
        return
    }
    $runtime = Get-Content -Raw -Encoding UTF8 -LiteralPath $RuntimePath | ConvertFrom-Json
    $server = Get-CimInstance Win32_Process -Filter "ProcessId=$($runtime.pid)" -ErrorAction SilentlyContinue
    if (-not $server) {
        return
    }
    $parent = Get-CimInstance Win32_Process -Filter "ProcessId=$($server.ParentProcessId)" -ErrorAction SilentlyContinue
    if (-not $parent -or [IO.Path]::GetFullPath($parent.ExecutablePath) -ne [IO.Path]::GetFullPath($AppExe)) {
        throw "拒絕關閉未通過路徑驗證的程序。"
    }
    $process = Get-Process -Id $parent.ProcessId -ErrorAction Stop
    if (-not $process.CloseMainWindow()) {
        throw "無法要求啟動器正常關閉。"
    }
    Wait-Until {
        -not (Get-Process -Id $parent.ProcessId -ErrorAction SilentlyContinue) -and
        -not (Get-Process -Id $server.ProcessId -ErrorAction SilentlyContinue)
    } 15 "啟動器關閉後仍有背景程序。"
}

$installer = (Resolve-Path -LiteralPath $InstallerPath).Path
if ([IO.Path]::GetExtension($installer) -ne ".exe") {
    throw "InstallerPath 必須是 .exe 安裝程式。"
}
if (Test-Path -LiteralPath $InstallDir) {
    throw "驗收前已存在安裝目錄，為避免覆蓋既有安裝而中止：$InstallDir"
}

$signature = Get-AuthenticodeSignature -LiteralPath $installer
if (-not $AllowUnsignedDevelopmentBuild -and $signature.Status -ne "Valid") {
    throw "正式驗收要求有效的 Authenticode 簽章，目前狀態：$($signature.Status)"
}

try {
    Write-Host "[1/8] 安裝 $AppName"
    $setup = Start-Process -FilePath $installer -ArgumentList @(
        "/VERYSILENT",
        "/SUPPRESSMSGBOXES",
        "/NORESTART",
        "/CLOSEAPPLICATIONS"
    ) -Wait -PassThru
    if ($setup.ExitCode -ne 0) {
        throw "安裝程式結束代碼：$($setup.ExitCode)"
    }
    $InstalledByScript = $true

    Write-Host "[2/8] 驗證安裝完成後未自動啟動"
    if (Test-Path -LiteralPath $RuntimePath) {
        throw "安裝完成後不應自行建立 runtime.json。"
    }
    $unexpectedProcesses = @(
        Get-CimInstance Win32_Process -ErrorAction Stop |
            Where-Object {
                $_.ExecutablePath -and
                [IO.Path]::GetFullPath($_.ExecutablePath) -eq [IO.Path]::GetFullPath($AppExe)
            }
    )
    if ($unexpectedProcesses.Count -gt 0) {
        throw "安裝完成後主程式被自動啟動。"
    }

    Write-Host "[3/8] 驗證完整離線安裝內容與版本"
    if (-not (Test-Path -LiteralPath $AppExe)) {
        throw "安裝後找不到主程式：$AppExe"
    }
    $version = (Get-Item -LiteralPath $AppExe).VersionInfo.ProductVersion.Trim()
    if ($version -ne $ExpectedVersion) {
        throw "版本不符，預期 $ExpectedVersion，實際 $version。"
    }
    if (-not (Test-Path -LiteralPath $DesktopShortcut)) {
        throw "未建立桌面捷徑。"
    }
    if (-not (Test-Path -LiteralPath $StartMenuDir)) {
        throw "未建立開始功能表捷徑。"
    }
    $pdfiumDll = Get-ChildItem -LiteralPath $InstallDir -Recurse -File -Filter "pdfium.dll" | Select-Object -First 1
    $pdfiumLicenses = @(
        Get-ChildItem -LiteralPath $InstallDir -Recurse -File |
            Where-Object { $_.FullName -match "pypdfium2-.+\.dist-info.+licenses" }
    )
    $dndLicenses = @(
        Get-ChildItem -LiteralPath $InstallDir -Recurse -File |
            Where-Object { $_.FullName -match "streamlit_dnd-.+\.dist-info.+licenses" }
    )
    if (-not $pdfiumDll -or $pdfiumLicenses.Count -eq 0 -or $dndLicenses.Count -eq 0) {
        throw "安裝內容缺少 PDFium 或第三方授權文件。"
    }

    Write-Host "[4/8] 執行安裝版自我檢查"
    $selfTest = Start-Process -FilePath $AppExe -ArgumentList "--self-test" -Wait -PassThru -WindowStyle Hidden
    if ($selfTest.ExitCode -ne 0) {
        $selfTestLog = Join-Path $DataDir "self-test.log"
        $detail = if (Test-Path -LiteralPath $selfTestLog) {
            Get-Content -Raw -Encoding UTF8 -LiteralPath $selfTestLog
        }
        else {
            "未產生 self-test.log。"
        }
        throw "安裝版自我檢查失敗，結束代碼 $($selfTest.ExitCode)：`n$detail"
    }
    if (Test-Path -LiteralPath $RuntimePath) {
        throw "自我檢查不應啟動本機服務。"
    }

    Write-Host "[5/8] 以安裝後捷徑等效方式啟動"
    $LauncherProcess = Start-Process -FilePath $AppExe -PassThru -WindowStyle Hidden
    Wait-Until { Test-Path -LiteralPath $RuntimePath } 30 "啟動器未建立執行狀態。"
    $runtime = Get-Content -Raw -Encoding UTF8 -LiteralPath $RuntimePath | ConvertFrom-Json
    if (-not ([string]$runtime.url).StartsWith("http://127.0.0.1:")) {
        throw "本機服務網址不符合 loopback 限制：$($runtime.url)"
    }
    Wait-Until {
        try {
            $response = Invoke-WebRequest -UseBasicParsing "$($runtime.url)/_stcore/health" -TimeoutSec 1
            $response.StatusCode -eq 200 -and $response.Content -eq "ok"
        }
        catch {
            $false
        }
    } 30 "本機服務健康檢查逾時。"

    Write-Host "[6/8] 驗證服務只監聽 127.0.0.1"
    $port = ([Uri]$runtime.url).Port
    $listeners = @(Get-NetTCPConnection -State Listen -LocalPort $port -ErrorAction Stop)
    if ($listeners.Count -eq 0 -or ($listeners | Where-Object { $_.LocalAddress -ne "127.0.0.1" })) {
        throw "本機服務監聽範圍不符合要求。"
    }

    Write-Host "[7/8] 正常關閉並檢查背景程序"
    Stop-VerifiedLauncher
    Wait-Until { -not (Test-Path -LiteralPath $RuntimePath) } 5 "關閉後未清除 runtime.json。"

    Write-Host "[8/8] 解除安裝並檢查清理結果"
    $uninstaller = Join-Path $InstallDir "unins000.exe"
    if (-not (Test-Path -LiteralPath $uninstaller)) {
        throw "找不到解除安裝程式。"
    }
    $uninstall = Start-Process -FilePath $uninstaller -ArgumentList @(
        "/VERYSILENT",
        "/SUPPRESSMSGBOXES",
        "/NORESTART"
    ) -Wait -PassThru
    if ($uninstall.ExitCode -ne 0) {
        throw "解除安裝程式結束代碼：$($uninstall.ExitCode)"
    }
    $InstalledByScript = $false
    Wait-Until { -not (Test-Path -LiteralPath $InstallDir) } 15 "解除安裝後仍有安裝目錄。"
    if (Test-Path -LiteralPath $DesktopShortcut) {
        throw "解除安裝後仍有桌面捷徑。"
    }
    if (Test-Path -LiteralPath $StartMenuDir) {
        throw "解除安裝後仍有開始功能表捷徑。"
    }
    if (Test-Path -LiteralPath $DataDir) {
        throw "解除安裝後仍有應用程式資料目錄。"
    }

    Write-Host "0.1.0 發布驗收通過。"
}
finally {
    if ($LauncherProcess -and -not $LauncherProcess.HasExited) {
        try {
            Stop-VerifiedLauncher
        }
        catch {
            Write-Warning $_.Exception.Message
        }
    }
    if ($InstalledByScript) {
        $uninstaller = Join-Path $InstallDir "unins000.exe"
        if (Test-Path -LiteralPath $uninstaller) {
            Start-Process -FilePath $uninstaller -ArgumentList @(
                "/VERYSILENT",
                "/SUPPRESSMSGBOXES",
                "/NORESTART"
            ) -Wait | Out-Null
        }
    }
}
