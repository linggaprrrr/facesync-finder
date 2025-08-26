import sys
import os
from PyQt5.QtGui import QIcon, QPixmap, QPainter, QFont
from PyQt5.QtWidgets import (
    QApplication, QMessageBox, QSplashScreen
)
from PyQt5.QtCore import Qt, QTimer

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
    
    return getattr(sys, 'frozen', False)

class FastMainApplication:
    """Fast startup dengan safe splash screen - no threading"""
    
    def __init__(self):
        fix_pyinstaller_paths()
        
        # macOS specific setup
        if sys.platform == 'darwin':
            os.environ['QT_MAC_WANTS_LAYER'] = '1'
        
        # Minimal QApplication setup
        QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
        QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
        
        self.app = QApplication(sys.argv)
        self.app.setApplicationName("FaceSync Finder")
        
        # Set application icon
        self.set_app_icon()
    
    def set_app_icon(self):
        """Set application icon from assets"""
        try:
            icon_path = os.path.join(os.path.dirname(__file__), "assets", "ownize_logo.ico")
            if os.path.exists(icon_path):
                self.app.setWindowIcon(QIcon(icon_path))
                return True
            else:
                print(f"Icon not found: {icon_path}")
                return False
        except Exception as e:
            print(f"Failed to set icon: {e}")
            return False
        
        # Set application icon
        self.set_app_icon()
        
        self.main_window = None
        self.splash = None
        self.load_timer = None
    
    def set_app_icon(self):
        """Set application icon from assets"""
        try:
            icon_path = os.path.join(os.path.dirname(__file__), "assets", "ownize_logo.ico")
            if os.path.exists(icon_path):
                self.app.setWindowIcon(QIcon(icon_path))
                return True
            else:
                print(f"Icon not found: {icon_path}")
                return False
        except Exception as e:
            print(f"Failed to set icon: {e}")
            return False
    
    def create_splash_screen(self):
        """Create splash screen dengan background image dan logo"""
        try:
            # Try to load background splash image first
            splash_bg_path = os.path.join(os.path.dirname(__file__), "assets", "ownize.png")
            splash_pixmap = None
            
            if os.path.exists(splash_bg_path):
                try:
                    splash_pixmap = QPixmap(splash_bg_path)
                    if splash_pixmap.isNull():
                        splash_pixmap = None
                except Exception as e:
                    print(f"Failed to load splash background: {e}")
                    splash_pixmap = None
            
            # Fallback: create custom splash if no background image
            if splash_pixmap is None:
                splash_pixmap = QPixmap(400, 250)
                splash_pixmap.fill(Qt.white)
                
                # Draw custom content
                painter = QPainter(splash_pixmap)
                try:
                    # Try to load and draw logo
                    logo_path = os.path.join(os.path.dirname(__file__), "assets", "ownize_logo.ico")
                    if os.path.exists(logo_path):
                        logo = QPixmap(logo_path)
                        if not logo.isNull():
                            # Scale logo to fit nicely
                            scaled_logo = logo.scaled(64, 64, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                            # Draw logo at top center
                            logo_x = (400 - scaled_logo.width()) // 2
                            painter.drawPixmap(logo_x, 20, scaled_logo)
                            title_y = 100
                        else:
                            title_y = 80
                    else:
                        title_y = 80
                    
                    # Title
                    painter.setFont(QFont("Arial", 20, QFont.Bold))
                    painter.setPen(Qt.black)
                    painter.drawText(50, title_y, "FaceSync Finder")
                    
                    # Version/subtitle
                    painter.setFont(QFont("Arial", 12))
                    painter.setPen(Qt.gray)
                    painter.drawText(50, title_y + 30, "Face Recognition Photo Search")
                    
                    # Loading message area
                    painter.setFont(QFont("Arial", 14))
                    painter.setPen(Qt.blue)
                    painter.drawText(50, title_y + 80, "Loading application...")
                    
                    # Progress indicator
                    painter.setPen(Qt.lightGray)
                    painter.drawRect(50, title_y + 100, 300, 20)
                    painter.fillRect(52, title_y + 102, 296, 16, Qt.white)
                    
                finally:
                    painter.end()
            else:
                # Using background image - scale if needed
                if splash_pixmap.width() > 500 or splash_pixmap.height() > 350:
                    splash_pixmap = splash_pixmap.scaled(400, 250, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            
            # Create splash screen
            self.splash = QSplashScreen(splash_pixmap)
            self.splash.setWindowFlags(Qt.SplashScreen | Qt.WindowStaysOnTopHint)
            
            # Show splash
            self.splash.show()
            self.splash.showMessage("Initializing...", Qt.AlignBottom | Qt.AlignCenter, Qt.black)
            
            # Process events untuk ensure splash appears
            self.app.processEvents()
            
            return True
            
        except Exception as e:
            print(f"Splash screen failed: {e}")
            return False
    
    def update_splash_progress(self, message, progress=None):
        """Update splash screen message"""
        if self.splash:
            try:
                self.splash.showMessage(message, Qt.AlignBottom | Qt.AlignCenter, Qt.black)
                self.app.processEvents()
                
                # Optional: Update progress bar
                if progress is not None:
                    # Redraw with progress
                    pixmap = self.splash.pixmap()
                    painter = QPainter(pixmap)
                    try:
                        # Clear progress area
                        painter.fillRect(52, 202, 296, 16, Qt.white)
                        # Draw progress
                        progress_width = int(296 * progress / 100)
                        painter.fillRect(52, 202, progress_width, 16, Qt.blue)
                    finally:
                        painter.end()
                    
                    self.splash.setPixmap(pixmap)
                    self.app.processEvents()
                    
            except Exception as e:
                print(f"Splash update failed: {e}")
    
    def load_main_window_step(self, step=0):
        """Load main window dalam steps untuk show progress"""
        try:
            if step == 0:
                self.update_splash_progress("Loading configuration...", 20)
                # Delay untuk show progress
                QTimer.singleShot(200, lambda: self.load_main_window_step(1))
                
            elif step == 1:
                self.update_splash_progress("Loading core modules...", 40)
                # Import config manager
                try:
                    from config.config_manager import ConfigManager
                    self.config_manager = ConfigManager()
                except Exception as e:
                    raise Exception(f"Config loading failed: {e}")
                
                QTimer.singleShot(100, lambda: self.load_main_window_step(2))
                
            elif step == 2:
                self.update_splash_progress("Initializing user interface...", 70)
                QTimer.singleShot(100, lambda: self.load_main_window_step(3))
                
            elif step == 3:
                self.update_splash_progress("Creating main window...", 90)
                
                # Import and create main window
                from ui.explorer_window import ExplorerWindow
                self.main_window = ExplorerWindow()
                
                QTimer.singleShot(100, lambda: self.load_main_window_step(4))
                
            elif step == 4:
                self.update_splash_progress("Finalizing...", 100)
                QTimer.singleShot(300, self.show_main_window)
                
        except Exception as e:
            self.handle_loading_error(str(e))
    
    def show_main_window(self):
        """Show main window and hide splash"""
        try:
            if self.main_window:
                # Show main window
                self.main_window.show()
                self.main_window.raise_()
                self.main_window.activateWindow()
                
                # Hide splash
                if self.splash:
                    self.splash.finish(self.main_window)
                    self.splash = None
                
                # Final process events
                self.app.processEvents()
                
        except Exception as e:
            self.handle_loading_error(f"Failed to show main window: {e}")
    
    def handle_loading_error(self, error_message):
        """Handle loading errors"""
        # Hide splash
        if self.splash:
            self.splash.hide()
            self.splash = None
        
        # Show error
        try:
            QMessageBox.critical(
                None, 
                "Startup Error", 
                f"Application failed to start:\n\n{error_message}"
            )
        except:
            print(f"FATAL ERROR: {error_message}")
        
        self.app.quit()
    
    def run(self):
        """Run application dengan splash screen"""
        try:
            # Create and show splash
            splash_ok = self.create_splash_screen()
            
            if splash_ok:
                # Start loading process dengan delay
                QTimer.singleShot(500, lambda: self.load_main_window_step(0))
            else:
                # Fallback: direct loading tanpa splash
                self.load_main_window_direct()
            
            # Run event loop
            return self.app.exec_()
            
        except Exception as e:
            print(f"Application failed: {e}")
            try:
                QMessageBox.critical(None, "Error", f"Application failed:\n{str(e)}")
            except:
                pass
            return 1
    
    def load_main_window_direct(self):
        """Fallback: direct loading tanpa splash"""
        try:
            from ui.explorer_window import ExplorerWindow
            self.main_window = ExplorerWindow()
            self.main_window.show()
        except Exception as e:
            self.handle_loading_error(str(e))

# Even simpler version - basic splash
class SimpleWithSplash:
    """Ultra-simple version dengan basic splash"""
    
    def __init__(self):
        fix_pyinstaller_paths()
        
        if sys.platform == 'darwin':
            os.environ['QT_MAC_WANTS_LAYER'] = '1'
            
        QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
        self.app = QApplication(sys.argv)
        self.app.setApplicationName("FaceSync Finder")
        self.set_app_icon()
    
    def set_app_icon(self):
        """Set application icon from assets"""
        try:
            icon_path = os.path.join(os.path.dirname(__file__), "assets", "ownize_logo.ico")
            if os.path.exists(icon_path):
                self.app.setWindowIcon(QIcon(icon_path))
                return True
            else:
                print(f"Icon not found: {icon_path}")
                return False
        except Exception as e:
            print(f"Failed to set icon: {e}")
            return False
    def run(self):
        try:
            # Simple splash with background image
            splash_pixmap = None
            
            # Try to load splash background image
            splash_bg_path = os.path.join(os.path.dirname(__file__), "assets", "ownize.png")
            if os.path.exists(splash_bg_path):
                splash_pixmap = QPixmap(splash_bg_path)
                if splash_pixmap.isNull():
                    splash_pixmap = None
                else:
                    # Scale if too large
                    if splash_pixmap.width() > 400 or splash_pixmap.height() > 300:
                        splash_pixmap = splash_pixmap.scaled(400, 300, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            
            # Fallback to simple text splash
            if splash_pixmap is None:
                splash_pixmap = QPixmap(300, 150)
                splash_pixmap.fill(Qt.white)
                
                painter = QPainter(splash_pixmap)
                painter.setFont(QFont("Arial", 16, QFont.Bold))
                painter.drawText(splash_pixmap.rect(), Qt.AlignCenter, 
                               "FaceSync Finder\n\nLoading...")
                painter.end()
            
            # Create and show splash
            splash = QSplashScreen(splash_pixmap)
            splash.show()
            self.app.processEvents()
            
            # Load main window
            splash.showMessage("Loading...", Qt.AlignBottom | Qt.AlignCenter)
            self.app.processEvents()
            
            from ui.explorer_window import ExplorerWindow
            main_window = ExplorerWindow()
            
            # Show window and hide splash
            main_window.show()
            splash.finish(main_window)
            
            return self.app.exec_()
            
        except Exception as e:
            try:
                QMessageBox.critical(None, "Error", f"Failed: {str(e)}")
            except:
                print(f"FATAL: {e}")
            return 1

if __name__ == '__main__':
    # Pilih version yang mau dipakai
    USE_SIMPLE_SPLASH = True  # Set False untuk detailed progress splash
    
    try:
        if USE_SIMPLE_SPLASH:
            app = SimpleWithSplash()
        else:
            app = FastMainApplication()
        
        sys.exit(app.run())
        
    except Exception as e:
        print(f"FATAL: {e}")
        sys.exit(1)