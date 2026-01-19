# Building the Windows Installer

## Prerequisites

1. **PyInstaller** (already installed):
   ```powershell
   pip install pyinstaller
   ```

2. **Inno Setup 6** (needs to be installed):
   - Download from: https://jrsoftware.org/isdl.php
   - Run the installer to install Inno Setup 6
   - Default installation path: `C:\Program Files\Inno Setup 6\`

## Building Steps

### Step 1: Build the Executable

From the workspace root (`c:\Users\tpor598\workforce`), run:


```powershell
python -m PyInstaller --onefile --windowed --name workforce --icon=docs/images/icon.ico --hidden-import=threading --distpath dist/windows --workpath build/windows workforce/__main__.py
```

This creates `dist\windows\workforce.exe`.

### Step 2: Compile the Installer

Once Inno Setup 6 is installed, run:

```powershell
& "C:\Program Files\Inno Setup 6\ISCC.exe" installer.iss
```

Or use the Inno Setup GUI:
1. Open `installer.iss` in Inno Setup
2. Click `Build` → `Compile`

The installer will be created as `dist\workforce_setup.exe`.

### Step 3: Deploy

The Windows installer is ready for distribution as `dist\workforce_setup.exe`.

## Troubleshooting

**Problem**: `ISCC.exe is not recognized`
- **Solution**: Ensure Inno Setup 6 is installed. You can download it from https://jrsoftware.org/isdl.php

**Problem**: Missing executable in installer
- **Solution**: Make sure you ran Step 1 to build the executable first. The executable must exist at `dist\windows\workforce.exe`.

**Problem**: Icon not found
- **Solution**: The icon file `docs/images/icon.ico` must exist. If missing, rebuild from Windows or create a .ico file from `docs/images/icon.xbm`.

## Installer Features

- **One-file executable**: Bundled with all dependencies
- **Windows-only**: 64-bit only (x64 architecture)
- **Desktop shortcut**: Automatically creates shortcut on desktop
- **Start Menu**: Adds app to Start Menu
- **Uninstall**: Full uninstall support with cleanup
- **License**: Shows LICENSE file before installation
- **Admin privileges**: Requires administrator access for installation

## Makefile Integration

The `Makefile` contains a `windows` target that does both steps automatically (requires Inno Setup installed):

```bash
make windows
```

## Notes

- The installer requires admin privileges for installation (standard for Program Files)
- All dependencies are bundled in the single executable
- No Python runtime or additional files needed on target machine
- The server automatically starts in-process when running from the frozen executable
