@echo off
REM build_with_logo_windows.bat - Build Face Search with Ownize logo for Windows

echo 🚀 Building Ownize Face Search for Windows
echo ==========================================
echo.

REM Check if Python and required packages are available
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Python not found! Please install Python first.
    pause
    exit /b 1
)

pip show pyinstaller >nul 2>&1
if errorlevel 1 (
    echo 📦 Installing PyInstaller...
    pip install pyinstaller
)

REM Check for Ownize logo
if not exist "assets\ownize_logo.png" (
    echo ❌ Ownize logo not found: assets\ownize_logo.png
    echo 💡 Please put your logo in assets\ownize_logo.png
    pause
    exit /b 1
)

echo ✅ Found Ownize logo: assets\ownize_logo.png

REM Create icon from Ownize logo
echo 🎨 Converting logo to Windows icon format...

REM Check if Pillow is available for icon conversion
python -c "from PIL import Image" >nul 2>&1
if errorlevel 1 (
    echo 📦 Installing Pillow for icon conversion...
    pip install Pillow
)

REM Convert PNG to ICO using Python
python -c "
from PIL import Image
import sys
import os

try:
    # Open the logo
    img = Image.open('assets/ownize_logo.png')
    
    # Convert to RGBA if needed
    if img.mode != 'RGBA':
        img = img.convert('RGBA')
    
    # Create multiple sizes for Windows ICO
    sizes = [(16,16), (32,32), (48,48), (64,64), (128,128), (256,256)]
    
    # Resize and save as ICO
    img.save('ownize_icon.ico', format='ICO', sizes=sizes)
    print('✅ Icon created: ownize_icon.ico')
    
except Exception as e:
    print(f'❌ Icon conversion failed: {e}')
    # Fallback: copy PNG as ICO (sometimes works)
    import shutil
    shutil.copy('assets/ownize_logo.png', 'ownize_icon.ico')
    print('⚠️ Using PNG as fallback icon')
"

if not exist "ownize_icon.ico" (
    echo ❌ Icon creation failed
    pause
    exit /b 1
)

REM Clean previous builds
echo 🧹 Cleaning previous builds...
if exist "build" rmdir /s /q "build"
if exist "dist" rmdir /s /q "dist"
if exist "*.spec" del "*.spec"

REM Build with PyInstaller including icon
echo 🔨 Building with PyInstaller (this may take a few minutes)...
echo.

pyinstaller ^
  --onedir ^
  --console ^
  --name "OwnizeFaceSearch" ^
  --icon "ownize_icon.ico" ^
  --exclude-module matplotlib ^
  --exclude-module pandas ^
  --exclude-module scipy ^
  --exclude-module jupyter ^
  --exclude-module notebook ^
  --exclude-module IPython ^
  --exclude-module plotly ^
  --exclude-module seaborn ^
  --exclude-module sklearn ^
  --add-data ".env;." ^
  --hidden-import "PyQt5.QtCore" ^
  --hidden-import "PyQt5.QtGui" ^
  --hidden-import "PyQt5.QtWidgets" ^
  --hidden-import "cv2" ^
  --hidden-import "torch" ^
  --hidden-import "facenet_pytorch" ^
  main.py

if not exist "dist\OwnizeFaceSearch" (
    echo ❌ Build failed! Check the error messages above.
    pause
    exit /b 1
)

echo ✅ Build successful!

REM Copy icon to dist folder for easy access
copy "ownize_icon.ico" "dist\OwnizeFaceSearch\" >nul

REM Create Ownize-branded Windows launchers
echo 🚀 Creating Ownize launchers...

REM Main Ownize launcher
(
echo @echo off
echo title Ownize Face Search
echo color 0B
echo cls
echo echo.
echo echo   ╔══════════════════════════════════════════════════════════════════════════════╗
echo echo   ║                                                                              ║
echo echo   ║                            🔍 OWNIZE FACE SEARCH                            ║
echo echo   ║                         Advanced AI Photo Recognition                       ║
echo echo   ║                                                                              ║
echo echo   ╚══════════════════════════════════════════════════════════════════════════════╝
echo echo.
echo echo   🚀 Starting Ownize Face Search...
echo echo   📱 Custom Ownize branding applied
echo echo   🎨 Windows icon with Ownize logo
echo echo.
echo echo   💡 Features:
echo echo      🤖 AI-powered face recognition
echo echo      📸 Real-time camera detection
echo echo      🔍 Instant photo search
echo echo      🔒 Privacy-first processing
echo echo.
echo echo   📋 Instructions:
echo echo      1. Click 'Search by Face' in the main window
echo echo      2. Allow camera access when prompted
echo echo      3. Position your face clearly in camera
echo echo      4. Search and find your photos instantly!
echo echo.
echo echo   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
echo echo.
echo cd /d "%%~dp0dist\OwnizeFaceSearch"
echo OwnizeFaceSearch.exe
echo echo.
echo echo   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
echo echo   ✅ Ownize Face Search closed successfully
echo echo   🙏 Thank you for using Ownize products!
echo echo.
echo pause
) > "🔍 Ownize Face Search.bat"

REM Simple launcher
(
echo @echo off
echo title Ownize Face Search - Quick Launch
echo echo 🔍 Starting Ownize Face Search...
echo echo 📱 App will open in a moment...
echo echo.
echo cd /d "%%~dp0dist\OwnizeFaceSearch"
echo OwnizeFaceSearch.exe
) > "FaceSearch.bat"

REM Silent launcher (no console window)
(
echo @echo off
echo cd /d "%%~dp0dist\OwnizeFaceSearch"
echo start "" "OwnizeFaceSearch.exe"
) > "FaceSearch_Silent.bat"

REM Developer launcher with detailed output
(
echo @echo off
echo title Ownize Face Search - Developer Mode
echo color 0A
echo echo ================================================
echo echo       🔍 OWNIZE FACE SEARCH ^(DEV MODE^)
echo echo ================================================
echo echo.
echo echo 🚀 Starting Ownize Face Search Application...
echo echo 📊 Developer mode - detailed logs enabled
echo echo.
echo echo 💡 Tips:
echo echo • Camera permission may be requested on first use
echo echo • You can minimize this window
echo echo • Do NOT close this window while app is running
echo echo • Watch this window for debug information
echo echo.
echo echo ================================================
echo echo.
echo cd /d "%%~dp0dist\OwnizeFaceSearch"
echo OwnizeFaceSearch.exe
echo echo.
echo echo ✅ Ownize Face Search has closed
echo echo 📊 Check above for any error messages
echo pause
) > "FaceSearch_Dev.bat"

REM Create desktop shortcut script
(
echo @echo off
echo echo 🖥️ Creating desktop shortcut for Ownize Face Search...
echo.
echo set "shortcutPath=%%USERPROFILE%%\Desktop\Ownize Face Search.lnk"
echo set "targetPath=%%CD%%\🔍 Ownize Face Search.bat"
echo set "iconPath=%%CD%%\ownize_icon.ico"
echo.
echo powershell "$WshShell = New-Object -comObject WScript.Shell; $Shortcut = $WshShell.CreateShortcut('%%shortcutPath%%'^); $Shortcut.TargetPath = '%%targetPath%%'; $Shortcut.IconLocation = '%%iconPath%%'; $Shortcut.Save(^)"
echo.
echo if exist "%%shortcutPath%%" (
echo     echo ✅ Desktop shortcut created: Ownize Face Search.lnk
echo     echo 🎯 You can now launch from desktop!
echo ^) else (
echo     echo ❌ Failed to create desktop shortcut
echo ^)
echo.
echo pause
) > "Create_Desktop_Shortcut.bat"

echo.
echo 🎉 Windows Build Complete with Ownize Branding!
echo ===============================================
echo.
echo ✅ Created:
echo    📱 dist\OwnizeFaceSearch\ (main app with icon)
echo    🎨 ownize_icon.ico (Windows icon file)
echo    🚀 🔍 Ownize Face Search.bat (main launcher)
echo    🚀 FaceSearch.bat (simple launcher)
echo    🚀 FaceSearch_Silent.bat (no console launcher)
echo    🛠️ FaceSearch_Dev.bat (developer launcher)
echo    🖥️ Create_Desktop_Shortcut.bat (desktop shortcut creator)
echo.
echo 🎯 To use your Ownize Face Search:
echo    🥇 Double-click: 🔍 Ownize Face Search.bat (RECOMMENDED)
echo    🥈 Double-click: FaceSearch.bat (simple)
echo    🥉 Double-click: FaceSearch_Silent.bat (no console)
echo    🛠️ Double-click: FaceSearch_Dev.bat (debugging)
echo.
echo 🎨 Windows Icon Features:
echo    ✅ Custom Ownize icon in executable
echo    ✅ Ownize branding in launchers
echo    ✅ Professional Windows appearance
echo    ✅ Desktop shortcut support
echo.
echo 🖥️ Optional: Run Create_Desktop_Shortcut.bat to add to desktop
echo.
echo 🔍 Your Ownize Face Search app is ready for Windows!
echo 📱 Click 'Search by Face' to start searching photos
echo.
pause