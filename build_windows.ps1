# build_windows.ps1

# 1. Setup Virtual Environment
if (-not (Test-Path "venv_win")) {
    Write-Host "Creating Windows Virtual Environment..." -ForegroundColor Cyan
    python -m venv venv_win
}

Write-Host "Activating Environment..." -ForegroundColor Cyan
.\venv_win\Scripts\Activate.ps1

# 2. Install Dependencies
Write-Host "Installing requirements..." -ForegroundColor Cyan
pip install --upgrade pip
pip install pyinstaller
pip install -e .  # Installs your workforce package and its dependencies

# 3. Run PyInstaller
Write-Host "Building Windows Executable..." -ForegroundColor Cyan
pyinstaller --onefile --windowed `
    --icon="docs/images/icon.ico" `
    --hidden-import engineio.async_drivers.threading `
    --hidden-import dns.resolver `
    --distpath "dist/windows" `
    --workpath "build/windows" `
    --name "workforce" `
    "workforce/__main__.py"

# 4. Run Inno Setup
$ISCC = "C:\Users\tpor598\AppData\Local\Programs\Inno Setup 6\ISCC.exe"
if (Test-Path $ISCC) {
    Write-Host "Running Inno Setup..." -ForegroundColor Cyan
    & $ISCC installer.iss
} else {
    Write-Error "Inno Setup Compiler (ISCC.exe) not found at $ISCC"
}

Write-Host "Build Complete! Check the dist/ folder." -ForegroundColor Green
