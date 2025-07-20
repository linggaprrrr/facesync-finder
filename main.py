import sys
import os
from PyQt5.QtGui import QIcon, QPixmap
from PyQt5.QtWidgets import (
    QApplication, QMessageBox, QDialog, QSplashScreen, QProgressBar, QLabel, QVBoxLayout, QWidget
)
from PyQt5.QtCore import QThread, pyqtSignal, Qt, QTimer

def get_resource_path(relative_path):
    """Get absolute path to resource - works for dev and PyInstaller"""
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)

class ModelLoader(QThread):
    """Background thread untuk load heavy modules"""
    progress = pyqtSignal(int, str)
    finished = pyqtSignal()
    error = pyqtSignal(str)
    
    def run(self):
        try:
            # Step 1: Load config
            self.progress.emit(10, "Loading configuration...")
            from config.config_manager import ConfigManager
            
            # Step 2: Load UI modules
            self.progress.emit(30, "Loading UI components...")
            from ui.admin_setup_dialogs import AdminSetupDialog
            from ui.admin_login import AdminLoginDialog
            
            # Step 3: Load heavy AI modules
            self.progress.emit(50, "Loading AI models (this may take a while)...")
            # Force import heavy modules here in background
            import torch
            import cv2
            import numpy as np
            
            # Step 4: Load face detection
            self.progress.emit(70, "Loading face detection...")
            try:
                from retinaface import RetinaFace
            except ImportError as e:
                print(f"RetinaFace loading error: {e}")
            
            # Step 5: Load main window
            self.progress.emit(90, "Loading main interface...")
            from ui.explorer_window import ExplorerWindow
            
            # Done
            self.progress.emit(100, "Ready!")
            self.finished.emit()
            
        except Exception as e:
            self.error.emit(str(e))

class LoadingWindow(QWidget):
    """Custom loading window with progress"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("FaceSync")
        self.setFixedSize(400, 200)
        self.setWindowFlag(Qt.WindowStaysOnTopHint)
        
        # Center window
        self.setStyleSheet("""
            QWidget {
                background-color: #2b2b2b;
                color: white;
                font-family: Arial;
            }
            QProgressBar {
                border: 2px solid #555;
                border-radius: 5px;
                text-align: center;
            }
            QProgressBar::chunk {
                background-color: #4CAF50;
                border-radius: 3px;
            }
        """)
        
        layout = QVBoxLayout()
        
        # Logo
        logo_path = get_resource_path("assets/ownize_logo.png")
        if os.path.exists(logo_path):
            logo_label = QLabel()
            pixmap = QPixmap(logo_path).scaled(100, 100, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            logo_label.setPixmap(pixmap)
            logo_label.setAlignment(Qt.AlignCenter)
            layout.addWidget(logo_label)
        
        # Title
        title_label = QLabel("FaceSync")
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setStyleSheet("font-size: 24px; font-weight: bold; margin: 10px;")
        layout.addWidget(title_label)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        layout.addWidget(self.progress_bar)
        
        # Status label
        self.status_label = QLabel("Initializing...")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet("margin: 10px;")
        layout.addWidget(self.status_label)
        
        self.setLayout(layout)
        
        # Center on screen
        self.center_on_screen()
    
    def center_on_screen(self):
        """Center window on screen"""
        screen = QApplication.desktop().screenGeometry()
        size = self.geometry()
        self.move(
            (screen.width() - size.width()) // 2,
            (screen.height() - size.height()) // 2
        )
    
    def update_progress(self, value, message):
        """Update progress bar and message"""
        self.progress_bar.setValue(value)
        self.status_label.setText(message)
        QApplication.processEvents()  # Keep UI responsive

class MainApplication:
    """Main application controller with optimized loading"""
    
    def __init__(self):
        self.app = QApplication(sys.argv)
        
        # Set app icon
        logo_path = get_resource_path("assets/ownize_logo.png")
        if os.path.exists(logo_path):
            self.app.setWindowIcon(QIcon(logo_path))
        
        self.main_window = None
        self.loading_window = None
        self.model_loader = None
    
    def show_loading_screen(self):
        """Show loading screen while loading heavy modules"""
        self.loading_window = LoadingWindow()
        self.loading_window.show()
        
        # Start background loading
        self.model_loader = ModelLoader()
        self.model_loader.progress.connect(self.loading_window.update_progress)
        self.model_loader.finished.connect(self.on_loading_finished)
        self.model_loader.error.connect(self.on_loading_error)
        self.model_loader.start()
    
    def on_loading_finished(self):
        """Called when background loading is done"""
        try:
            # Close loading window
            self.loading_window.close()
            
            # Now safely import and create main window
            from ui.explorer_window import ExplorerWindow
            from config.config_manager import ConfigManager
            
            # Create config manager
            config_manager = ConfigManager()
            
            # Create and show main window
            self.main_window = ExplorerWindow()
            self.main_window.show()
            
        except Exception as e:
            self.on_loading_error(str(e))
    
    def on_loading_error(self, error_message):
        """Handle loading errors"""
        if self.loading_window:
            self.loading_window.close()
        
        QMessageBox.critical(
            None, 
            "Loading Error", 
            f"Failed to load application:\n{error_message}\n\nThe application will now exit."
        )
        sys.exit(1)
    
    def run(self):
        """Run the application with optimized loading"""
        try:
            # Show loading screen immediately
            self.show_loading_screen()
            
            # Start Qt event loop
            return self.app.exec_()
            
        except Exception as e:
            QMessageBox.critical(
                None, 
                "Application Error", 
                f"Failed to start application:\n{str(e)}"
            )
            return 1

# Quick check for dependencies before starting
def check_basic_dependencies():
    """Quick check for basic dependencies"""
    try:
        from PyQt5.QtWidgets import QApplication
        return True
    except ImportError as e:
        print(f"Critical dependency missing: {e}")
        print("This application requires PyQt5 to run.")
        return False

if __name__ == '__main__':
    # Quick dependency check
    if not check_basic_dependencies():
        input("Press Enter to exit...")
        sys.exit(1)
    
    # Start application
    app = MainApplication()
    sys.exit(app.run())