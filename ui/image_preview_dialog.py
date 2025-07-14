from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QPushButton, QHBoxLayout, 
    QSizePolicy, QGraphicsDropShadowEffect, QWidget
)
from PyQt5.QtCore import Qt, QPropertyAnimation, QEasingCurve
from PyQt5.QtGui import QPixmap, QColor

class ImagePreviewDialog(QDialog):
    """Beautiful image preview dialog with smooth animations"""
    
    def __init__(self, image_path, parent=None):
        super().__init__(parent)
        self.image_path = image_path
        self.setWindowTitle("Image Preview")
        self.setModal(True)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        
        self.init_ui()
        self.load_image()
        self.setup_animations()
        
    def init_ui(self):
        """Initialize UI with beautiful styling"""
        # Main container with rounded corners
        self.container = QWidget(self)
        self.container.setObjectName("container")
        self.container.setStyleSheet("""
            QWidget#container {
                background-color: #ffffff;
                border-radius: 20px;
                border: 1px solid #e0e0e0;
            }
        """)
        
        # Shadow effect
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(30)
        shadow.setXOffset(0)
        shadow.setYOffset(0)
        shadow.setColor(QColor(0, 0, 0, 180))
        self.container.setGraphicsEffect(shadow)
        
        # Layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(self.container)
        
        container_layout = QVBoxLayout(self.container)
        container_layout.setContentsMargins(20, 20, 20, 20)
        container_layout.setSpacing(15)
        
        # Image label
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setStyleSheet("""
            QLabel {
                background-color: #f8f9fa;
                border-radius: 15px;
                padding: 10px;
            }
        """)
        self.image_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        container_layout.addWidget(self.image_label)
        
        # Info label
        self.info_label = QLabel()
        self.info_label.setStyleSheet("""
            QLabel {
                color: #ccc;
                font-size: 12px;
                padding: 5px;
            }
        """)
        self.info_label.setAlignment(Qt.AlignCenter)
        container_layout.addWidget(self.info_label)
        
        # Button container
        button_container = QWidget()
        button_layout = QHBoxLayout(button_container)
        button_layout.setContentsMargins(0, 0, 0, 0)
        button_layout.setSpacing(10)
        
        # Close button
        self.close_button = QPushButton("Close")
        self.close_button.setStyleSheet("""
            QPushButton {
                background-color: #3a3a3a;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 10px 30px;
                font-size: 14px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #4a4a4a;
            }
            QPushButton:pressed {
                background-color: #2a2a2a;
            }
        """)
        self.close_button.clicked.connect(self.close)
        
        button_layout.addStretch()
        button_layout.addWidget(self.close_button)
        button_layout.addStretch()
        
        container_layout.addWidget(button_container)
        
    def load_image(self):
        """Load and display image with scaling"""
        pixmap = QPixmap(self.image_path)
        if not pixmap.isNull():
            # Get screen size for scaling
            screen = self.screen()
            screen_rect = screen.availableGeometry()
            max_width = int(screen_rect.width() * 0.8)
            max_height = int(screen_rect.height() * 0.8)
            
            # Scale image if needed
            if pixmap.width() > max_width or pixmap.height() > max_height:
                pixmap = pixmap.scaled(max_width, max_height, 
                                     Qt.KeepAspectRatio, 
                                     Qt.SmoothTransformation)
            
            self.image_label.setPixmap(pixmap)
            
            # Update info
            import os
            filename = os.path.basename(self.image_path)
            info_text = f"{filename} • {pixmap.width()} × {pixmap.height()} px"
            self.info_label.setText(info_text)
            
            # Resize dialog to fit content
            self.resize(pixmap.width() + 60, pixmap.height() + 120)
            
    def setup_animations(self):
        """Setup smooth fade-in animation"""
        self.setWindowOpacity(0)
        self.animation = QPropertyAnimation(self, b"windowOpacity")
        self.animation.setDuration(200)
        self.animation.setStartValue(0)
        self.animation.setEndValue(1)
        self.animation.setEasingCurve(QEasingCurve.OutCubic)
        self.animation.start()
        
    def mousePressEvent(self, event):
        """Enable window dragging"""
        if event.button() == Qt.LeftButton:
            self.drag_position = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()
            
    def mouseMoveEvent(self, event):
        """Handle window dragging"""
        if event.buttons() == Qt.LeftButton and hasattr(self, 'drag_position'):
            self.move(event.globalPos() - self.drag_position)
            event.accept()
            
    def keyPressEvent(self, event):
        """Close on Escape key"""
        if event.key() == Qt.Key_Escape:
            self.close()