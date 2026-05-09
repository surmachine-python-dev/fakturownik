param(
    [switch]$SkipInstaller,
    [switch]$Clean
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$PythonExe = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$PyInstallerExe = Join-Path $ProjectRoot ".venv\Scripts\pyinstaller.exe"
$SpecFile = Join-Path $ProjectRoot "Fakturownik.spec"
$DistDir = Join-Path $ProjectRoot "dist"
$BuildDir = Join-Path $ProjectRoot "build\pyinstaller"
$InstallerScript = Join-Path $ProjectRoot "installer\Fakturownik.iss"

if (-not (Test-Path $PythonExe)) {
    throw "Nie znaleziono interpretera virtualenv: $PythonExe"
}

if (-not (Test-Path $PyInstallerExe)) {
    throw "Nie znaleziono PyInstaller: $PyInstallerExe"
}

if ($Clean) {
    if (Test-Path $BuildDir) {
        Remove-Item $BuildDir -Recurse -Force
    }
    if (Test-Path (Join-Path $DistDir "Fakturownik")) {
        Remove-Item (Join-Path $DistDir "Fakturownik") -Recurse -Force
    }
    if (Test-Path (Join-Path $DistDir "installer")) {
        Remove-Item (Join-Path $DistDir "installer") -Recurse -Force
    }
}

Write-Host "[1/2] Budowanie aplikacji przez PyInstaller..."
& $PyInstallerExe --noconfirm --clean --distpath $DistDir --workpath $BuildDir $SpecFile

if ($SkipInstaller) {
    Write-Host "Pominieto budowanie instalatora Inno Setup (--SkipInstaller)."
    exit 0
}

$InnoCandidates = @(
    (Join-Path ${env:ProgramFiles(x86)} "Inno Setup 6\ISCC.exe"),
    (Join-Path $env:ProgramFiles "Inno Setup 6\ISCC.exe")
) | Where-Object { $_ }

$IsccExe = $InnoCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1

if (-not $IsccExe) {
    $IsccCommand = Get-Command "ISCC.exe" -ErrorAction SilentlyContinue
    if ($IsccCommand) {
        $IsccExe = $IsccCommand.Source
    }
}

if (-not $IsccExe) {
    throw "Nie znaleziono ISCC.exe. Zainstaluj Inno Setup 6 albo uruchom skrypt z parametrem --SkipInstaller."
}

$Version = & $PythonExe -c "from pathlib import Path; import sys; sys.path.insert(0, str(Path(r'$ProjectRoot') / 'src')); from fakturownik import __version__; print(__version__)"
$SourceDir = Join-Path $DistDir "Fakturownik"

if (-not (Test-Path $SourceDir)) {
    throw "Nie znaleziono katalogu builda aplikacji: $SourceDir"
}

Write-Host "[2/2] Budowanie instalatora przez Inno Setup..."
& $IsccExe "/DSourceDir=$SourceDir" "/DAppVersion=$Version" $InstallerScript

Write-Host "Gotowe. Wyniki znajdziesz w katalogu dist\."