import sys
import os
import logging
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import (
    QApplication, QMessageBox, QDialog
)
from PyQt5.QtCore import Qt, QTimer

from config.config_manager import ConfigManager
from ui.explorer_window import ExplorerWindow

# import requests
# from PIL import Image
# try:
#     from PIL.ExifTags import ORIENTATION
# except ImportError:
#     ORIENTATION = 274  # Standard EXIF orientation tag number

# from io import BytesIO


def fix_pyinstaller_paths():
    """Fix import paths for PyInstaller"""
    if getattr(sys, 'frozen', False):
        bundle_dir = sys._MEIPASS
        if bundle_dir not in sys.path:
            sys.path.insert(0, bundle_dir)
        
        subdirs = ['ui', 'core', 'utils']
        for subdir in subdirs:
            subdir_path = os.path.join(bundle_dir, subdir)
            if os.path.exists(subdir_path) and subdir_path not in sys.path:
                sys.path.insert(0, subdir_path)
        
        print(f"🔧 PyInstaller paths fixed: {bundle_dir}")
    else:
        print("🐍 Running in development mode")

# CALL THIS FIRST!
fix_pyinstaller_paths()

class MainApplication:
    """Main application controller dengan windowed mode fixes"""
    
    def __init__(self):
        # Setup windowed mode logging
        self.setup_windowed_logging()
        
        # Setup QApplication dengan proper attributes untuk windowed mode
        self.setup_qapplication()
        
        # Original initialization
        self.config_manager = ConfigManager()
        self.main_window = None
        
        self.logger.info("✅ MainApplication initialized")
    
    def setup_windowed_logging(self):
        """Setup logging untuk windowed mode"""
        try:
            # Create log file di Desktop untuk easy access
            log_file = os.path.expanduser('~/Desktop/FaceSearchApp_Debug.log')
            
            logging.basicConfig(
                level=logging.INFO,
                format='%(asctime)s - %(levelname)s - %(message)s',
                handlers=[
                    logging.FileHandler(log_file),
                    logging.StreamHandler(sys.stdout)
                ]
            )
            
            self.logger = logging.getLogger(__name__)
            self.logger.info("🚀 Windowed mode logging started")
            self.logger.info(f"📝 Log file: {log_file}")
            
        except Exception as e:
            print(f"❌ Logging setup error: {e}")
            self.logger = logging.getLogger(__name__)
    
    def setup_qapplication(self):
        """Setup QApplication dengan windowed mode fixes"""
        try:
            # WINDOWED MODE FIX: Set Qt attributes BEFORE creating QApplication
            QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
            QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
            QApplication.setAttribute(Qt.AA_DontShowIconsInMenus, False)
            
            # Create QApplication
            self.app = QApplication(sys.argv)
            
            # Set app properties (your existing code)
            logo_path = os.path.join(os.path.dirname(__file__), "assets", "ownize_logo.png")
            if os.path.exists(logo_path):
                self.app.setWindowIcon(QIcon(logo_path))
            
            # Additional windowed mode properties
            self.app.setApplicationName("FaceSearchApp")
            self.app.setApplicationDisplayName("Face Search Application")
            self.app.setOrganizationName("YourCompany")
            
            # CRITICAL: Process events untuk proper initialization
            self.app.processEvents()
            
        except Exception as e:
            print(f"❌ QApplication setup error: {e}")
            raise e
    
    def create_main_window_delayed(self):
        """Create main window dengan delay untuk windowed mode"""
        try:
            self.logger.info("📱 Creating main window...")
            
            # Import dan create main window
            from ui.explorer_window import ExplorerWindow
            
            self.main_window = ExplorerWindow()
            
            # WINDOWED MODE FIX: Set proper window attributes
            self.main_window.setAttribute(Qt.WA_DeleteOnClose, True)
            
            # Show window dengan proper sequence
            self.main_window.show()
            self.main_window.raise_()
            self.main_window.activateWindow()
            
            # Process events lagi
            self.app.processEvents()
            
            self.logger.info("✅ Main window created and shown successfully")
            
        except Exception as e:
            self.logger.error(f"❌ Main window creation error: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            
            # Show error dialog jika memungkinkan
            try:
                QMessageBox.critical(
                    None, 
                    "Application Error", 
                    f"Failed to create main window:\n{str(e)}\n\nCheck log file for details."
                )
            except:
                print(f"FATAL ERROR: {e}")
            
            self.app.quit()
    
    def run(self):
        """Run the application dengan windowed mode fixes"""
        try:
            self.logger.info("🚀 Starting application...")
            
            # WINDOWED MODE FIX: Delayed window creation
            # Ini critical untuk windowed mode di macOS
            QTimer.singleShot(100, self.create_main_window_delayed)
            
            self.logger.info("🎯 Starting event loop...")
            
            # Run event loop
            result = self.app.exec_()
            
            self.logger.info(f"🏁 Application ended with code: {result}")
            return result
            
        except Exception as e:
            self.logger.error(f"❌ Fatal application error: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            return 1


# def test_image_orientation(url):
#     """Test function untuk check EXIF orientation"""
#     try:
#         print(f"🧪 Testing URL orientation...")
#         print(f"🌐 URL: {url[:100]}...")
        
#         # Download image
#         response = requests.get(url, timeout=15)
#         if response.status_code != 200:
#             print(f"❌ Download failed: {response.status_code}")
#             return
            
#         print(f"✅ Downloaded {len(response.content)} bytes")
        
#         # Open with Pillow
#         pil_image = Image.open(BytesIO(response.content))
#         print(f"🖼️ Image size: {pil_image.size}")
#         print(f"🖼️ Image mode: {pil_image.mode}")
        
#         # Check EXIF data with multiple methods
#         exif_dict = None
#         orientation = None
        
#         # Method 1: Try _getexif() (older method)
#         try:
#             exif_dict = pil_image._getexif()
#             if exif_dict:
#                 orientation = exif_dict.get(ORIENTATION) or exif_dict.get(274)
#                 print(f"📋 EXIF data found via _getexif(): {len(exif_dict)} entries")
#         except AttributeError:
#             print("⚠️ _getexif() not available")
        
#         # Method 2: Try getexif() (newer method) if first failed
#         if not orientation:
#             try:
#                 exif_dict = pil_image.getexif()
#                 if exif_dict:
#                     orientation = exif_dict.get(ORIENTATION) or exif_dict.get(274)
#                     print(f"📋 EXIF data found via getexif(): {len(exif_dict)} entries")
#             except AttributeError:
#                 print("⚠️ getexif() not available")
        
#         print(f"🧭 EXIF orientation: {orientation}")
            
#         if orientation:
#             orientation_meanings = {
#                 1: "Normal (no rotation needed)",
#                 2: "Horizontal flip", 
#                 3: "180° rotation needed",
#                 4: "Vertical flip",
#                 5: "Horizontal flip + 270° rotation",
#                 6: "270° rotation needed (90° CW)",
#                 7: "Horizontal flip + 90° rotation", 
#                 8: "90° rotation needed (270° CW)"
#             }
#             meaning = orientation_meanings.get(orientation, "Unknown orientation")
#             print(f"📖 Meaning: {meaning}")
            
#             # Check if this image needs rotation
#             needs_rotation = orientation in [3, 6, 8]
#             if needs_rotation:
#                 print(f"🔄 ⚠️ THIS IMAGE NEEDS ROTATION!")
#                 print(f"   Original size: {pil_image.size}")
                
#                 # Apply the rotation
#                 if orientation == 3:
#                     rotated = pil_image.rotate(180, expand=True)
#                     print(f"   Applied 180° → New size: {rotated.size}")
#                 elif orientation == 6:
#                     rotated = pil_image.rotate(270, expand=True)
#                     print(f"   Applied 270° → New size: {rotated.size}")
#                 elif orientation == 8:
#                     rotated = pil_image.rotate(90, expand=True)
#                     print(f"   Applied 90° → New size: {rotated.size}")
#                 else:
#                     print(f"✅ No rotation needed")
#             else:
#                 print("✅ No orientation tag found - image should display normally")
#         else:
#             print("✅ No EXIF data found - image should display normally")
        
#         return pil_image
        
#     except Exception as e:
#         print(f"❌ Test error: {e}")
#         import traceback
#         traceback.print_exc()
#         return None
    

if __name__ == '__main__':
    app = MainApplication()
    sys.exit(app.run())
    # test_url = "https://s3.ap-southeast-1.wasabisys.com/rca-photos/originals/c10ee611-f5b8-4ab1-b575-aec0fa491466.jpg" 
    
    # print("🧪 STARTING ORIENTATION TEST")
    # print("=" * 50)
    
    # result = test_image_orientation(test_url)
    
    # print("=" * 50)
    # print("🏁 TEST COMPLETED")