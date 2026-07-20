param(
    [string]$PreviousInstallerPath = "",
    [string]$NewInstallerPath = "",
    [string]$ExpectedPreviousVersion = "0.1.0",
    [string]$ExpectedNewVersion = "0.2.0",
    [switch]$AllowUnsignedDevelopmentBuild
)

$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$AppName = "本機 PDF 工具箱"
$AppExeName = "本機PDF工具箱.exe"
$InstallDir = Join-Path $env:LOCALAPPDATA "Programs\LocalPDFToolbox"
$AppExe = Join-Path $InstallDir $AppExeName
$DataDir = Join-Path $env:LOCALAPPDATA "LocalPDFToolbox"
$RuntimePath = Join-Path $DataDir "runtime.json"
$DesktopShortcut = Join-Path ([Environment]::GetFolderPath("Desktop")) "$AppName.lnk"
$StartMenuDir = Join-Path ([Environment]::GetFolderPath("Programs")) $AppName
$UninstallRegistryPath = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\{18D34507-C3D3-4532-9F04-B88CC2D59EC8}_is1"
$TestOwnsInstall = $false
$TestCompleted = $false

function Test-VersionEquals([string]$Actual, [string]$Expected) {
    try {
        $actualVersion = [version]$Actual
        $expectedVersion = [version]$Expected
        return (
            $actualVersion.Major -eq $expectedVersion.Major -and
            $actualVersion.Minor -eq $expectedVersion.Minor -and
            $actualVersion.Build -eq $expectedVersion.Build
        )
    }
    catch {
        return $false
    }
}

function Resolve-Installer([string]$Path, [string]$DefaultFileName) {
    $candidate = if ($Path) {
        $Path
    }
    else {
        Join-Path (Join-Path $Root "release") $DefaultFileName
    }
    if (-not (Test-Path -LiteralPath $candidate -PathType Leaf)) {
        throw "找不到安裝程式：$candidate"
    }
    if ([System.IO.Path]::GetExtension($candidate) -ne ".exe") {
        throw "安裝程式必須是 .exe：$candidate"
    }
    return (Resolve-Path -LiteralPath $candidate).Path
}

function Assert-InstallerArtifact(
    [string]$Installer,
    [string]$ExpectedVersion
) {
    $actualVersion = (Get-Item -LiteralPath $Installer).VersionInfo.ProductVersion
    if (-not (Test-VersionEquals $actualVersion $ExpectedVersion)) {
        throw "安裝程式版本不符：$Installer；預期 $ExpectedVersion，實際 $actualVersion"
    }

    $sidecar = "$Installer.sha256"
    if (-not (Test-Path -LiteralPath $sidecar -PathType Leaf)) {
        throw "找不到 SHA-256 清單：$sidecar"
    }
    $hashLine = (Get-Content -LiteralPath $sidecar -Encoding UTF8 |
        Where-Object { $_.Trim() } |
        Select-Object -First 1)
    if (-not $hashLine -or $hashLine -notmatch "^([0-9a-fA-F]{64})\s+(.+)$") {
        throw "SHA-256 清單格式錯誤：$sidecar"
    }
    $listedHash = $Matches[1].ToLowerInvariant()
    $listedFileName = $Matches[2].Trim()
    $actualFileName = Split-Path -Leaf $Installer
    if ($listedFileName -ne $actualFileName) {
        throw "SHA-256 清單中的檔名不符：預期 $actualFileName，實際 $listedFileName"
    }
    $actualHash = (Get-FileHash -LiteralPath $Installer -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($listedHash -ne $actualHash) {
        throw "SHA-256 驗證失敗：$Installer"
    }

    $signature = Get-AuthenticodeSignature -LiteralPath $Installer
    if ($signature.Status -ne "Valid" -and -not $AllowUnsignedDevelopmentBuild) {
        throw "安裝程式沒有有效簽章（$($signature.Status)）。未簽章測試版請明確加入 -AllowUnsignedDevelopmentBuild。"
    }
    Write-Host "通過安裝檔驗證：$actualFileName（$ExpectedVersion）"
}

function Get-AppProcesses {
    $normalizedAppExe = [System.IO.Path]::GetFullPath($AppExe)
    return @(
        Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
            Where-Object {
                $_.ExecutablePath -and
                [System.IO.Path]::GetFullPath($_.ExecutablePath) -eq $normalizedAppExe
            }
    )
}

function Assert-CleanStartingState {
    $existing = @()
    if (Test-Path -LiteralPath $InstallDir) {
        $existing += "安裝目錄：$InstallDir"
    }
    if (Test-Path -LiteralPath $DataDir) {
        $existing += "資料目錄：$DataDir"
    }
    if (Test-Path -LiteralPath $DesktopShortcut) {
        $existing += "桌面捷徑：$DesktopShortcut"
    }
    if (Test-Path -LiteralPath $StartMenuDir) {
        $existing += "開始功能表：$StartMenuDir"
    }
    if (Test-Path -LiteralPath $UninstallRegistryPath) {
        $existing += "解除安裝紀錄：$UninstallRegistryPath"
    }
    $processes = @(Get-AppProcesses)
    if ($processes.Count -gt 0) {
        $existing += "執行中程序 PID：$(($processes.ProcessId) -join ', ')"
    }
    if ($existing.Count -gt 0) {
        throw "升級測試必須從未安裝工具箱的乾淨狀態開始，避免覆蓋或移除使用者現有安裝。`n$($existing -join "`n")"
    }
}

function Invoke-Installer([string]$Installer) {
    $process = Start-Process `
        -FilePath $Installer `
        -ArgumentList @("/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/CLOSEAPPLICATIONS") `
        -Wait `
        -PassThru `
        -WindowStyle Hidden
    if ($process.ExitCode -ne 0) {
        throw "安裝程式結束碼不是 0：$($process.ExitCode)"
    }
}

function Assert-NoAutoStart {
    if (Test-Path -LiteralPath $RuntimePath) {
        throw "安裝完成後不應自動啟動本機服務：$RuntimePath"
    }
    $processes = @(Get-AppProcesses)
    if ($processes.Count -gt 0) {
        throw "安裝完成後不應自動啟動程式：PID $(($processes.ProcessId) -join ', ')"
    }
}

function Assert-InstalledVersion([string]$ExpectedVersion) {
    if (-not (Test-Path -LiteralPath $AppExe -PathType Leaf)) {
        throw "找不到安裝後主程式：$AppExe"
    }
    $actualVersion = (Get-Item -LiteralPath $AppExe).VersionInfo.ProductVersion
    if (-not (Test-VersionEquals $actualVersion $ExpectedVersion)) {
        throw "安裝後版本不符：預期 $ExpectedVersion，實際 $actualVersion"
    }
    if (-not (Test-Path -LiteralPath $DesktopShortcut -PathType Leaf)) {
        throw "找不到桌面捷徑：$DesktopShortcut"
    }
    if (-not (Test-Path -LiteralPath $StartMenuDir)) {
        throw "找不到開始功能表捷徑：$StartMenuDir"
    }
    if (-not (Test-Path -LiteralPath $UninstallRegistryPath)) {
        throw "找不到固定 AppId 的解除安裝紀錄。"
    }
    $uninstallEntry = Get-ItemProperty -LiteralPath $UninstallRegistryPath
    if (-not (Test-VersionEquals $uninstallEntry.DisplayVersion $ExpectedVersion)) {
        throw "解除安裝紀錄版本不符：預期 $ExpectedVersion，實際 $($uninstallEntry.DisplayVersion)"
    }
    if ([System.IO.Path]::GetFullPath($uninstallEntry.InstallLocation.TrimEnd("\")) -ne [System.IO.Path]::GetFullPath($InstallDir)) {
        throw "解除安裝紀錄指向錯誤位置：$($uninstallEntry.InstallLocation)"
    }
    $sameAppEntries = @(
        Get-ItemProperty "HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*" -ErrorAction SilentlyContinue |
            Where-Object {
                $_.PSChildName -eq "{18D34507-C3D3-4532-9F04-B88CC2D59EC8}_is1" -or
                ($_.InstallLocation -and
                    [System.IO.Path]::GetFullPath($_.InstallLocation.TrimEnd("\")) -eq
                    [System.IO.Path]::GetFullPath($InstallDir))
            }
    )
    if ($sameAppEntries.Count -ne 1) {
        throw "升級前後應只有一筆工具箱解除安裝紀錄，實際為 $($sameAppEntries.Count) 筆。"
    }
}

function Invoke-InstalledSelfTest([string]$Label) {
    $process = Start-Process `
        -FilePath $AppExe `
        -ArgumentList "--self-test" `
        -Wait `
        -PassThru `
        -WindowStyle Hidden
    if ($process.ExitCode -ne 0) {
        $selfTestLog = Join-Path $DataDir "self-test.log"
        $detail = if (Test-Path -LiteralPath $selfTestLog) {
            Get-Content -Raw -Encoding UTF8 -LiteralPath $selfTestLog
        }
        else {
            "未產生 self-test.log。"
        }
        throw "$Label 安裝版自我檢查失敗：`n$detail"
    }
    if (Test-Path -LiteralPath $RuntimePath) {
        throw "$Label 自我檢查不應啟動本機服務。"
    }
    Write-Host "$Label 安裝版自我檢查通過。"
}

function Invoke-InstalledUninstaller {
    $uninstaller = Join-Path $InstallDir "unins000.exe"
    if (-not (Test-Path -LiteralPath $uninstaller -PathType Leaf)) {
        throw "找不到解除安裝程式：$uninstaller"
    }
    $process = Start-Process `
        -FilePath $uninstaller `
        -ArgumentList @("/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART") `
        -Wait `
        -PassThru `
        -WindowStyle Hidden
    if ($process.ExitCode -ne 0) {
        throw "解除安裝程式結束碼不是 0：$($process.ExitCode)"
    }
    for ($attempt = 0; $attempt -lt 40 -and (Test-Path -LiteralPath $InstallDir); $attempt++) {
        Start-Sleep -Milliseconds 250
    }
}

function Assert-Uninstalled {
    $remaining = @(
        $InstallDir,
        $DataDir,
        $DesktopShortcut,
        $StartMenuDir,
        $UninstallRegistryPath
    ) | Where-Object { Test-Path -LiteralPath $_ }
    if ($remaining.Count -gt 0) {
        throw "解除安裝後仍有殘留：`n$($remaining -join "`n")"
    }
    if (@(Get-AppProcesses).Count -gt 0) {
        throw "解除安裝後仍有工具箱背景程序。"
    }
}

$previousInstaller = Resolve-Installer `
    $PreviousInstallerPath `
    "LocalPDFToolbox-Setup-v$ExpectedPreviousVersion.exe"
$newInstaller = Resolve-Installer `
    $NewInstallerPath `
    "LocalPDFToolbox-Setup-v$ExpectedNewVersion.exe"

if ([version]$ExpectedPreviousVersion -ge [version]$ExpectedNewVersion) {
    throw "舊版本必須低於新版本。"
}

Assert-InstallerArtifact $previousInstaller $ExpectedPreviousVersion
Assert-InstallerArtifact $newInstaller $ExpectedNewVersion
Assert-CleanStartingState

try {
    $TestOwnsInstall = $true

    Write-Host "[1/4] 乾淨安裝 $ExpectedPreviousVersion"
    Invoke-Installer $previousInstaller
    Assert-NoAutoStart
    Assert-InstalledVersion $ExpectedPreviousVersion
    $previousPath = (Resolve-Path -LiteralPath $AppExe).Path
    $previousHash = (Get-FileHash -LiteralPath $AppExe -Algorithm SHA256).Hash
    Invoke-InstalledSelfTest "$ExpectedPreviousVersion"

    Write-Host "[2/4] 不解除安裝，直接覆蓋安裝 $ExpectedNewVersion"
    Invoke-Installer $newInstaller
    Assert-NoAutoStart
    Assert-InstalledVersion $ExpectedNewVersion
    $newPath = (Resolve-Path -LiteralPath $AppExe).Path
    $newHash = (Get-FileHash -LiteralPath $AppExe -Algorithm SHA256).Hash
    if ($newPath -ne $previousPath) {
        throw "覆蓋安裝後主程式位置改變：$previousPath → $newPath"
    }
    if ($newHash -eq $previousHash) {
        throw "覆蓋安裝後主程式內容沒有更新。"
    }
    Invoke-InstalledSelfTest "$ExpectedNewVersion"

    Write-Host "[3/4] 驗證同一安裝位置與單一解除安裝紀錄"
    Assert-InstalledVersion $ExpectedNewVersion

    Write-Host "[4/4] 解除安裝並驗證清理"
    Invoke-InstalledUninstaller
    Assert-Uninstalled
    $TestCompleted = $true
    Write-Host "升級自動測試通過：$ExpectedPreviousVersion → $ExpectedNewVersion"
}
finally {
    if ($TestOwnsInstall -and -not $TestCompleted) {
        $uninstaller = Join-Path $InstallDir "unins000.exe"
        if (Test-Path -LiteralPath $uninstaller -PathType Leaf) {
            Write-Warning "測試失敗，正在解除安裝由本腳本建立的測試版本。"
            try {
                Invoke-InstalledUninstaller
            }
            catch {
                Write-Warning "自動清理失敗，請手動檢查：$InstallDir"
            }
        }
    }
}
