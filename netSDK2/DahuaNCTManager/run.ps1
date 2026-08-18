param(
    [switch]$NoBuild,
    [switch]$NoDeploy,
    [switch]$KeepExisting,
    [switch]$NoLaunch
)

$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$cmakeExe = "C:\Qt\Tools\CMake_64\bin\cmake.exe"
$qtDeployExe = "C:\Qt\6.11.1\msvc2022_64\bin\windeployqt.exe"
$configurePreset = "msvc2022-debug"
$buildPreset = "build-msvc2022-debug"
$buildDir = Join-Path $projectRoot "build\codex-msvc"
$exePath = Join-Path $buildDir "DahuaManager.exe"
$vsDevCmd = "C:\Program Files\Microsoft Visual Studio\2022\Community\Common7\Tools\VsDevCmd.bat"

$env:PATH = "C:\Qt\6.11.1\msvc2022_64\bin;C:\Qt\Tools\CMake_64\bin;C:\Users\Administrator\AppData\Local\Programs\Python\Python312\Scripts;$env:PATH"

if (-not (Test-Path $buildDir)) {
    New-Item -ItemType Directory -Path $buildDir | Out-Null
}

if (-not $KeepExisting) {
    try {
        Get-Process -Name "DahuaManager" -ErrorAction SilentlyContinue | Stop-Process -Force
    } catch {
        throw "Unable to stop DahuaManager.exe. Close the app manually or rerun with enough permission, then try again."
    }
}

if (-not $NoBuild) {
    if (-not (Test-Path $vsDevCmd)) {
        throw "VsDevCmd.bat was not found at $vsDevCmd"
    }

    $configureCommand = "`"$vsDevCmd`" -arch=x64 -host_arch=x64 && `"$cmakeExe`" --preset $configurePreset"
    $buildCommand = "`"$vsDevCmd`" -arch=x64 -host_arch=x64 && `"$cmakeExe`" --build --preset $buildPreset"

    cmd /c $configureCommand
    if ($LASTEXITCODE -ne 0) {
        throw "CMake configure failed with exit code $LASTEXITCODE"
    }

    cmd /c $buildCommand
    if ($LASTEXITCODE -ne 0) {
        throw "CMake build failed with exit code $LASTEXITCODE"
    }
}

if ((-not $NoDeploy) -and (Test-Path $qtDeployExe)) {
    & $qtDeployExe --dir $buildDir $exePath | Out-Null
}

if (-not $NoLaunch) {
    Start-Process -FilePath $exePath
}
