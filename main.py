import sys
import os
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import (
    QApplication, QMessageBox, QDialog
)
from ui.admin_setup_dialogs import AdminSetupDialog
from ui.admin_login import AdminLoginDialog
from config.config_manager import ConfigManager
from ui.explorer_window import ExplorerWindow

class MainApplication:
    """Main application controller"""
    
    def __init__(self):
        self.app = QApplication(sys.argv)
         # Set logo aplikasi
        logo_path = os.path.join(os.path.dirname(__file__), "assets", "ownize_logo.png")
        self.app.setWindowIcon(QIcon(logo_path))
        self.config_manager = ConfigManager()
        self.main_window = None
    
    def run(self):
        """Run the application with authentication flow"""
        
        # Launch main application
        self.main_window = ExplorerWindow()
        self.main_window.show()
        
        return self.app.exec_()


if __name__ == '__main__':
    app = MainApplication()
    sys.exit(app.run())