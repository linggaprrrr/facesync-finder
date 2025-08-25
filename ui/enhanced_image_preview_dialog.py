# ui/enhanced_image_preview_dialog.py

import os
import tempfile
import requests
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QScrollArea, QWidget, QApplication, QProgressBar, QMessageBox, QShortcut
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt5.QtGui import QPixmap, QIcon, QKeySequence, QFont

class ImageDownloadThread(QThread):
    """Thread untuk download image dari URL"""
    image_downloaded = pyqtSignal(str, str)  # temp_path, error_msg
    progress_updated = pyqtSignal(int)  # progress percentage
    
    def __init__(self, url):
        super().__init__()
        self.url = url
        self.temp_path = None
        
    def run(self):
        try:
            response = requests.get(self.url, timeout=15, stream=True)
            response.raise_for_status()
            
            # Get file size for progress
            total_size = int(response.headers.get('content-length', 0))
            downloaded_size = 0
            
            # Determine file extension
            content_type = response.headers.get('content-type', '')
            if 'jpeg' in content_type or 'jpg' in content_type:
                suffix = '.jpg'
            elif 'png' in content_type:
                suffix = '.png'
            elif 'gif' in content_type:
                suffix = '.gif'
            elif 'webp' in content_type:
                suffix = '.webp'
            else:
                suffix = '.jpg'
            
            # Create temp file
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_file:
                self.temp_path = tmp_file.name
                
                # Download in chunks
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        tmp_file.write(chunk)
                        downloaded_size += len(chunk)
                        
                        if total_size > 0:
                            progress = int((downloaded_size / total_size) * 100)
                            self.progress_updated.emit(progress)
            
            self.image_downloaded.emit(self.temp_path, "")
            
        except Exception as e:
            self.image_downloaded.emit("", str(e))

class EnhancedImagePreviewDialog(QDialog):
    """Enhanced Image Preview dengan Navigation"""
    
    def __init__(self, items_data, start_index=0, parent=None):
        super().__init__(parent)
        self.items_data = items_data
        self.current_index = start_index
        self.temp_files = []  # Track temp files for cleanup
        self.download_thread = None
        
        self.setWindowTitle("Image Preview")
        self.setWindowFlags(Qt.Window | Qt.WindowCloseButtonHint | Qt.WindowMaximizeButtonHint)
        self.resize(1000, 700)
        
        self.init_ui()
        self.setup_shortcuts()
        self.load_current_image()
        
    def init_ui(self):
        """Initialize UI components"""
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(15, 15, 15, 15)
        
        # Top info bar
        self.info_bar = self.create_info_bar()
        layout.addWidget(self.info_bar)
        
        # Navigation bar
        nav_bar = self.create_navigation_bar()
        layout.addWidget(nav_bar)
        
        # Progress bar (hidden by default)
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #ddd;
                border-radius: 5px;
                text-align: center;
                background-color: #f0f0f0;
                height: 20px;
            }
            QProgressBar::chunk {
                background-color: #5e72e4;
                border-radius: 4px;
            }
        """)
        layout.addWidget(self.progress_bar)
        
        # Image display area
        self.scroll_area = QScrollArea()
        self.scroll_area.setAlignment(Qt.AlignCenter)
        self.scroll_area.setStyleSheet("""
            QScrollArea {
                background-color: #2a2a2a;
                border: 1px solid #555;
                border-radius: 8px;
            }
        """)
        
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setStyleSheet("background-color: #2a2a2a; color: white; font-size: 16px;")
        self.image_label.setMinimumSize(600, 400)
        
        self.scroll_area.setWidget(self.image_label)
        self.scroll_area.setWidgetResizable(True)
        layout.addWidget(self.scroll_area)
        
        # Bottom controls
        bottom_bar = self.create_bottom_bar()
        layout.addWidget(bottom_bar)
        
    def create_info_bar(self):
        """Create top info bar"""
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(10, 5, 10, 5)
        
        # Current item info
        self.filename_label = QLabel()
        self.filename_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #333;")
        
        # Position info
        self.position_label = QLabel()
        self.position_label.setStyleSheet("font-size: 14px; color: #666;")
        
        layout.addWidget(self.filename_label)
        layout.addStretch()
        layout.addWidget(self.position_label)
        
        return widget
        
    def create_navigation_bar(self):
        """Create navigation controls"""
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(10, 5, 10, 5)
        
        # Previous button
        self.prev_btn = QPushButton("⬅️ Previous")
        self.prev_btn.setStyleSheet("""
            QPushButton {
                background-color: #6c757d;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 10px 20px;
                font-size: 14px;
                font-weight: 500;
            }
            QPushButton:hover:enabled {
                background-color: #5a6268;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #666666;
            }
        """)
        self.prev_btn.clicked.connect(self.previous_image)
        
        # Next button
        self.next_btn = QPushButton("Next ➡️")
        self.next_btn.setStyleSheet("""
            QPushButton {
                background-color: #007bff;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 10px 20px;
                font-size: 14px;
                font-weight: 500;
            }
            QPushButton:hover:enabled {
                background-color: #0056b3;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #666666;
            }
        """)
        self.next_btn.clicked.connect(self.next_image)
        
        # Similarity info
        self.similarity_label = QLabel()
        self.similarity_label.setStyleSheet("""
            QLabel {
                background-color: #28a745;
                color: white;
                border-radius: 15px;
                padding: 5px 15px;
                font-size: 12px;
                font-weight: bold;
            }
        """)
        
        layout.addWidget(self.prev_btn)
        layout.addStretch()
        layout.addWidget(self.similarity_label)
        layout.addStretch()
        layout.addWidget(self.next_btn)
        
        return widget
        
    def create_bottom_bar(self):
        """Create bottom controls"""
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(10, 5, 10, 5)
        
        # Outlet info
        self.outlet_label = QLabel()
        self.outlet_label.setStyleSheet("font-size: 12px; color: #666;")
        
        # Close button
        close_btn = QPushButton("Close")
        close_btn.setStyleSheet("""
            QPushButton {
                background-color: #dc3545;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 20px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #c82333;
            }
        """)
        close_btn.clicked.connect(self.close)
        
        layout.addWidget(self.outlet_label)
        layout.addStretch()
        layout.addWidget(close_btn)
        
        return widget
        
    def setup_shortcuts(self):
        """Setup keyboard shortcuts"""
        # Arrow keys for navigation
        left_shortcut = QShortcut(QKeySequence(Qt.Key_Left), self)
        left_shortcut.activated.connect(self.previous_image)
        
        right_shortcut = QShortcut(QKeySequence(Qt.Key_Right), self)
        right_shortcut.activated.connect(self.next_image)
        
        # A and D keys (alternative navigation)
        a_shortcut = QShortcut(QKeySequence(Qt.Key_A), self)
        a_shortcut.activated.connect(self.previous_image)
        
        d_shortcut = QShortcut(QKeySequence(Qt.Key_D), self)
        d_shortcut.activated.connect(self.next_image)
        
        # Escape to close
        escape_shortcut = QShortcut(QKeySequence(Qt.Key_Escape), self)
        escape_shortcut.activated.connect(self.close)
        
    def update_ui_info(self):
        """Update UI with current item info"""
        if not self.items_data:
            return
            
        current_item = self.items_data[self.current_index]
        
        # Update filename
        filename = current_item.get('filename', 'Unknown')
        self.filename_label.setText(filename)
        
        # Update position
        total_items = len(self.items_data)
        self.position_label.setText(f"{self.current_index + 1} of {total_items}")
        
        # Update similarity
        similarity = current_item.get('similarity', 0)
        similarity_percent = similarity * 100
        self.similarity_label.setText(f"{similarity_percent:.1f}% match")
        
        # Update outlet
        outlet_name = current_item.get('outlet_name', 'Unknown')
        self.outlet_label.setText(f"Outlet: {outlet_name}")
        
        # Update navigation buttons
        self.prev_btn.setEnabled(self.current_index > 0)
        self.next_btn.setEnabled(self.current_index < len(self.items_data) - 1)
        
        # Update window title
        self.setWindowTitle(f"Image Preview - {filename} ({self.current_index + 1}/{total_items})")
        
    def load_current_image(self):
        """Load current image"""
        if not self.items_data:
            return
            
        current_item = self.items_data[self.current_index]
        thumbnail = current_item.get('thumbnail', '')
        
        self.update_ui_info()
        
        if not thumbnail:
            self.image_label.setText("❌ No image path available")
            return
            
        if thumbnail.startswith(('http://', 'https://')):
            self.load_image_from_url(thumbnail)
        elif os.path.exists(thumbnail):
            self.load_image_from_file(thumbnail)
        else:
            self.image_label.setText("❌ Image file not found")
            
    def load_image_from_url(self, url):
        """Load image from URL"""
        self.image_label.setText("📥 Downloading image...")
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        
        # Cancel previous download if any
        if self.download_thread and self.download_thread.isRunning():
            self.download_thread.terminate()
            self.download_thread.wait()
            
        # Start new download
        self.download_thread = ImageDownloadThread(url)
        self.download_thread.image_downloaded.connect(self.on_image_downloaded)
        self.download_thread.progress_updated.connect(self.progress_bar.setValue)
        self.download_thread.start()
        
    def on_image_downloaded(self, temp_path, error_msg):
        """Handle downloaded image"""
        self.progress_bar.setVisible(False)
        
        if error_msg:
            self.image_label.setText(f"❌ Download failed:\n{error_msg}")
            return
            
        if temp_path:
            self.temp_files.append(temp_path)  # Track for cleanup
            self.load_image_from_file(temp_path)
            
    def load_image_from_file(self, file_path):
        """Load image from local file"""
        try:
            pixmap = QPixmap(file_path)
            if pixmap.isNull():
                self.image_label.setText("❌ Failed to load image")
                return
                
            # Scale image to fit while maintaining aspect ratio
            max_width = self.scroll_area.width() - 50
            max_height = self.scroll_area.height() - 50
            
            if pixmap.width() > max_width or pixmap.height() > max_height:
                pixmap = pixmap.scaled(max_width, max_height, 
                                     Qt.KeepAspectRatio, 
                                     Qt.SmoothTransformation)
            
            self.image_label.setPixmap(pixmap)
            self.image_label.adjustSize()
            
        except Exception as e:
            self.image_label.setText(f"❌ Error loading image:\n{str(e)}")
            
    def previous_image(self):
        """Go to previous image"""
        if self.current_index > 0:
            self.current_index -= 1
            self.load_current_image()
        else:
            # Visual feedback when at first image
            self.prev_btn.setStyleSheet("""
                QPushButton {
                    background-color: #dc3545;
                    color: white;
                    border: none;
                    border-radius: 6px;
                    padding: 10px 20px;
                    font-size: 14px;
                    font-weight: 500;
                }
            """)
            QTimer.singleShot(200, lambda: self.prev_btn.setStyleSheet("""
                QPushButton {
                    background-color: #6c757d;
                    color: white;
                    border: none;
                    border-radius: 6px;
                    padding: 10px 20px;
                    font-size: 14px;
                    font-weight: 500;
                }
                QPushButton:hover:enabled {
                    background-color: #5a6268;
                }
                QPushButton:disabled {
                    background-color: #cccccc;
                    color: #666666;
                }
            """))
            
    def next_image(self):
        """Go to next image"""
        if self.current_index < len(self.items_data) - 1:
            self.current_index += 1
            self.load_current_image()
        else:
            # Visual feedback when at last image
            self.next_btn.setStyleSheet("""
                QPushButton {
                    background-color: #dc3545;
                    color: white;
                    border: none;
                    border-radius: 6px;
                    padding: 10px 20px;
                    font-size: 14px;
                    font-weight: 500;
                }
            """)
            QTimer.singleShot(200, lambda: self.next_btn.setStyleSheet("""
                QPushButton {
                    background-color: #007bff;
                    color: white;
                    border: none;
                    border-radius: 6px;
                    padding: 10px 20px;
                    font-size: 14px;
                    font-weight: 500;
                }
                QPushButton:hover:enabled {
                    background-color: #0056b3;
                }
                QPushButton:disabled {
                    background-color: #cccccc;
                    color: #666666;
                }
            """))
            
    def closeEvent(self, event):
        """Clean up when closing"""
        # Cancel download thread
        if self.download_thread and self.download_thread.isRunning():
            self.download_thread.terminate()
            self.download_thread.wait()
            
        # Clean up temp files
        for temp_file in self.temp_files:
            try:
                os.unlink(temp_file)
            except:
                pass
                
        super().closeEvent(event)