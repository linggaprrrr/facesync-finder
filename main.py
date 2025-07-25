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


if __name__ == '__main__':
    app = MainApplication()
    sys.exit(app.run())