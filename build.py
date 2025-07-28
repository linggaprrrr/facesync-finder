import os
import subprocess
import sys
import shutil
from pathlib import Path

def check_requirements():
    """Check if all required files and packages are available"""
    print("🔍 Checking requirements...")
    
    # Check if main.py exists
    if not os.path.exists("main.py"):
        print("❌ main.py not found!")
        return False
    
    # Check if logo exists
    logo_path = "assets/ownize_logo.png"
    if not os.path.exists(logo_path):
        print(f"⚠️ Logo not found: {logo_path}")
        print("   The build will continue but without an icon.")
    else:
        print(f"✅ Logo found: {logo_path}")
    
    # Check required directories
    required_dirs = ["ui", "utils", "core"]
    for dir_name in required_dirs:
        if not os.path.exists(dir_name):
            print(f"⚠️ Directory not found: {dir_name}")
        else:
            print(f"✅ Directory found: {dir_name}")
    
    # Check if PyInstaller is installed
    try:
        import PyInstaller
        print(f"✅ PyInstaller found: {PyInstaller.__version__}")
    except ImportError:
        print("❌ PyInstaller not installed. Run: pip install pyinstaller")
        return False
    
    return True

def create_icon_file():
    """Convert PNG logo to ICO format for Windows"""
    logo_path = "assets/ownize_logo.png"
    ico_path = "assets/ownize_logo.ico"
    
    if not os.path.exists(logo_path):
        return None
    
    try:
        from PIL import Image
        
        # Open PNG and convert to ICO
        img = Image.open(logo_path)
        
        # Resize to standard icon sizes
        icon_sizes = [(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
        
        # Create ICO file with multiple sizes
        img.save(ico_path, format='ICO', sizes=icon_sizes)
        print(f"✅ ICO file created: {ico_path}")
        return ico_path
        
    except ImportError:
        print("⚠️ Pillow not installed. Using PNG directly.")
        return logo_path
    except Exception as e:
        print(f"⚠️ ICO conversion failed: {e}. Using PNG directly.")
        return logo_path

def clean_build_dirs():
    """Clean previous build directories"""
    print("🧹 Cleaning previous builds...")
    
    dirs_to_clean = ['build', 'dist', '__pycache__']
    files_to_clean = ['*.spec']
    
    for dir_name in dirs_to_clean:
        if os.path.exists(dir_name):
            shutil.rmtree(dir_name)
            print(f"🗑️ Removed {dir_name}")
    
    # Remove .spec files
    for spec_file in Path('.').glob('*.spec'):
        spec_file.unlink()
        print(f"🗑️ Removed {spec_file}")

def create_version_file():
    """Create version_info.txt file"""
    version_content = '''VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=(1, 0, 0, 0),
    prodvers=(1, 0, 0, 0),
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo(
      [
      StringTable(
        u'040904B0',
        [StringStruct(u'CompanyName', u'Ownize'),
        StringStruct(u'FileDescription', u'FaceSync - Finder: Advanced Face Recognition Search Tool'),
        StringStruct(u'FileVersion', u'1.0.0.0'),
        StringStruct(u'InternalName', u'FaceSync-Finder'),
        StringStruct(u'LegalCopyright', u'© 2024 Ownize. All rights reserved.'),
        StringStruct(u'OriginalFilename', u'FaceSync - Finder.exe'),
        StringStruct(u'ProductName', u'FaceSync - Finder'),
        StringStruct(u'ProductVersion', u'1.0.0.0')])
      ]), 
    VarFileInfo([VarStruct(u'Translation', [1033, 1200])])
  ]
)'''
    
    with open('version_info.txt', 'w', encoding='utf-8') as f:
        f.write(version_content)
    
    print("✅ Version info file created")

def build_with_pyinstaller():
    """Build using PyInstaller with the spec file"""
    print("🚀 Building FaceSync - Finder...")
    
    # Create ICO file
    icon_path = create_icon_file()
    
    # Create version file
    create_version_file()
    
    # Build command
    cmd = [
        "pyinstaller",
        "--onefile",                              # Single executable
        "--windowed",                             # No console window
        "--name", "FaceSync - Finder",            # ✅ App name with space
        
        # Add data directories
        "--add-data", "ui;ui",
        "--add-data", "utils;utils", 
        "--add-data", "core;core",
        "--add-data", "assets;assets",            # ✅ Include assets folder
        
        # Hidden imports
        "--hidden-import", "PyQt5.sip",
        "--hidden-import", "PIL._tkinter_finder",
        "--hidden-import", "sip",
        
        # Optimizations
        "--optimize", "2",
        "--strip",                                # Strip debug symbols
        
        # Exclude unnecessary modules
        "--exclude-module", "tkinter",
        "--exclude-module", "matplotlib",
        "--exclude-module", "jupyter",
        "--exclude-module", "IPython",
        
        # Version info
        "--version-file", "version_info.txt",
        
        # Main script
        "main.py"
    ]
    
    # Add icon if available
    if icon_path:
        cmd.extend(["--icon", icon_path])
    
    print("📦 PyInstaller command:")
    print(" ".join(cmd))
    print()
    
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        print("✅ Build completed successfully!")
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"❌ Build failed!")
        print(f"Return code: {e.returncode}")
        print(f"stdout: {e.stdout}")
        print(f"stderr: {e.stderr}")
        return False

def verify_build():
    """Verify the build was successful"""
    exe_path = "dist/FaceSync - Finder.exe"
    
    if os.path.exists(exe_path):
        size_mb = os.path.getsize(exe_path) / (1024 * 1024)
        print(f"✅ Executable created: {exe_path}")
        print(f"📏 Size: {size_mb:.1f} MB")
        
        # Check if it's really portable
        print("🧪 Verifying portability...")
        
        # List what's inside dist folder
        dist_contents = os.listdir("dist")
        print(f"📁 Dist folder contents: {dist_contents}")
        
        if len(dist_contents) == 1 and dist_contents[0].endswith('.exe'):
            print("✅ Truly portable - single executable file!")
        else:
            print("⚠️ Additional files found - may not be fully portable")
        
        return True
    else:
        print(f"❌ Executable not found: {exe_path}")
        return False

def create_distribution_package():
    """Create a complete distribution package"""
    print("📦 Creating distribution package...")
    
    # Create distribution folder
    dist_folder = "FaceSync-Finder-Portable"
    if os.path.exists(dist_folder):
        shutil.rmtree(dist_folder)
    
    os.makedirs(dist_folder)
    
    # Copy executable
    exe_source = "dist/FaceSync - Finder.exe"
    exe_dest = os.path.join(dist_folder, "FaceSync - Finder.exe")
    
    if os.path.exists(exe_source):
        shutil.copy2(exe_source, exe_dest)
        print(f"✅ Copied executable to {dist_folder}")
    
    # Create README
    readme_content = """FaceSync - Finder - Portable Edition
=====================================

DESCRIPTION:
Advanced face recognition search tool with AI-powered similarity matching.

SYSTEM REQUIREMENTS:
- Windows 7 or later (64-bit recommended)
- 4 GB RAM minimum (8 GB recommended)
- Webcam (for face detection)
- Internet connection (for searching)

INSTALLATION:
No installation required! This is a portable application.
Just run "FaceSync - Finder.exe"

FEATURES:
✅ Real-time face detection
✅ Custom similarity threshold (70-90%)
✅ Multi-outlet search results
✅ Image preview with navigation
✅ Bulk download functionality
✅ Settings auto-save

USAGE:
1. Double-click "FaceSync - Finder.exe"
2. Allow camera access when prompted
3. Position your face in front of camera
4. Adjust similarity threshold if needed (70-90%)
5. Click "Search" to find similar faces
6. Browse results by outlet tabs
7. Select and download images as needed

SETTINGS:
- All settings are automatically saved
- Similarity threshold: Adjustable from 70% to 90%
- Camera permissions: Grant when first prompted
- No configuration files to manage

TROUBLESHOOTING:
- If camera doesn't work: Check privacy settings
- If search fails: Check internet connection
- If app is slow to start: Normal for first run (extracting files)

SUPPORT:
For technical support or questions:
Email: [your-support-email]

VERSION: 1.0.0
BUILD: Portable Edition
COPYRIGHT: © 2024 Ownize. All rights reserved.
"""
    
    readme_path = os.path.join(dist_folder, "README.txt")
    with open(readme_path, 'w', encoding='utf-8') as f:
        f.write(readme_content)
    
    print(f"✅ Created README: {readme_path}")
    
    # Create version info
    version_info = f"""FaceSync - Finder v1.0.0
Build Date: {subprocess.check_output(['date'], shell=True).decode().strip()}
Build Type: Portable Executable
Platform: Windows (64-bit)
Size: {os.path.getsize(exe_dest) / (1024*1024):.1f} MB
"""
    
    version_path = os.path.join(dist_folder, "VERSION.txt")
    with open(version_path, 'w', encoding='utf-8') as f:
        f.write(version_info)
    
    print(f"✅ Distribution package ready: {dist_folder}/")
    return dist_folder

def main():
    """Main build process"""
    print("🚀 FaceSync - Finder Build Process")
    print("=" * 50)
    
    # Check requirements
    if not check_requirements():
        print("❌ Requirements check failed!")
        sys.exit(1)
    
    # Clean previous builds
    clean_build_dirs()
    
    # Build with PyInstaller
    if not build_with_pyinstaller():
        print("❌ Build process failed!")
        sys.exit(1)
    
    # Verify build
    if not verify_build():
        print("❌ Build verification failed!")
        sys.exit(1)
    
    # Create distribution package
    dist_folder = create_distribution_package()
    
    print("\n" + "=" * 50)
    print("🎉 BUILD COMPLETED SUCCESSFULLY!")
    print("=" * 50)
    print(f"📁 Executable: dist/FaceSync - Finder.exe")
    print(f"📦 Distribution: {dist_folder}/")
    print(f"🚀 Ready for deployment!")
    print("\nTo test: Double-click the executable")
    print("To distribute: Copy the entire distribution folder")

if __name__ == "__main__":
    main()