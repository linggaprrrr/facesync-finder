import os
import logging
import requests
import tempfile
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QPixmap, QKeySequence, QImage
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, 
    QCheckBox, QApplication, QMessageBox, QShortcut
)

logger = logging.getLogger(__name__)


class NavigationPreviewDialog(QDialog):
    """Fixed preview dialog with proper cleanup, working download, and image rotation fix"""
    
    # Signals untuk communicate back ke parent
    selection_changed = pyqtSignal(int, bool)  # index, is_selected
    download_requested = pyqtSignal(list)      # selected_items_data
    
    def __init__(self, items_data, start_index=0, parent=None):
        super().__init__(parent)
        self.items_data = items_data
        self.current_index = start_index
        self.temp_files = []
        
        # Track selection state untuk setiap item
        self.selection_state = {i: False for i in range(len(items_data))}
        
        # TAMBAH: Flag untuk prevent multiple operations
        self.is_loading = False
        self.is_closing = False
        
        self.setWindowTitle("Image Preview")
        self.setWindowFlags(Qt.Window | Qt.WindowCloseButtonHint | Qt.WindowMaximizeButtonHint)
        self.resize(800, 600)
        
        self.init_ui()
        self.setup_shortcuts()
        self.load_current_image()
    
    def init_ui(self):
        """Initialize UI"""
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)
       
        # Navigation bar
        nav_layout = QHBoxLayout()
        nav_layout.setSpacing(20)
        
        # Previous button
        self.prev_btn = QPushButton("⬅️ Previous")
        self.prev_btn.setStyleSheet("""
            QPushButton {
                background-color: #6c757d;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 8px 16px;
                font-size: 14px;
                font-weight: 500;
            }
            QPushButton:hover:enabled {
                background-color: #5a6268;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #999;
            }
        """)
        self.prev_btn.setFixedSize(110, 38)
        self.prev_btn.clicked.connect(self.safe_previous_image)
        
        # Similarity badge
        self.similarity_label = QLabel()
        self.similarity_label.setStyleSheet("""
            QLabel {
                background-color: #28a745;
                color: white;
                border-radius: 18px;
                padding: 8px 16px;
                font-size: 13px;
                font-weight: 600;
            }
        """)
        self.similarity_label.setFixedSize(130, 36)
        self.similarity_label.setAlignment(Qt.AlignCenter)
        
        # Next button
        self.next_btn = QPushButton("Next ➡️")
        self.next_btn.setStyleSheet("""
            QPushButton {
                background-color: #007bff;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 8px 16px;
                font-size: 14px;
                font-weight: 500;
            }
            QPushButton:hover:enabled {
                background-color: #0056b3;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #999;
            }
        """)
        self.next_btn.setFixedSize(110, 38)
        self.next_btn.clicked.connect(self.safe_next_image)
        
        nav_layout.addWidget(self.prev_btn)
        nav_layout.addStretch()
        nav_layout.addWidget(self.similarity_label)
        nav_layout.addStretch()
        nav_layout.addWidget(self.next_btn)
        layout.addLayout(nav_layout)
        
        # Image display area
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setStyleSheet("""
            QLabel {
                background-color: #2a2a2a;
                color: white;
                font-size: 16px;
                border: 2px solid #444;
                border-radius: 10px;
                padding: 20px;
            }
        """)
        layout.addWidget(self.image_label)
        
        # Bottom controls
        bottom_layout = QHBoxLayout()
        bottom_layout.setSpacing(15)
        
        self.outlet_label = QLabel()
        self.outlet_label.setStyleSheet("""
            QLabel {
                font-size: 12px; 
                color: #666;
                padding: 5px;
            }
        """)
        
        self.selection_summary_label = QLabel()
        self.selection_summary_label.setStyleSheet("""
            QLabel {
                font-size: 12px; 
                color: #007bff;
                font-weight: 500;
                padding: 5px;
            }
        """)
        
        # Selection checkbox
        self.select_checkbox = QCheckBox("📂 Select")
        self.select_checkbox.setStyleSheet("""
            QCheckBox {
                font-size: 13px;
                font-weight: 500;
                color: #333;
                padding: 8px;
                background-color: #f8f9fa;
                border-radius: 4px;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
                border-radius: 3px;
                border: 2px solid #ddd;
                background-color: white;
            }
            QCheckBox::indicator:checked {
                background-color: #007bff;
                border-color: #007bff;
            }
            QCheckBox::indicator:hover {
                border-color: #007bff;
                background-color: #f0f8ff;
            }
        """)
        self.select_checkbox.stateChanged.connect(self.safe_selection_changed)
        
        # Download selected button
        self.download_selected_btn = QPushButton("⬇️ Download Selected")
        self.download_selected_btn.setStyleSheet("""
            QPushButton {
                background-color: #28a745;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-size: 13px;
                font-weight: 500;
                min-width: 130px;
            }
            QPushButton:hover:enabled {
                background-color: #218838;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #999;
            }
        """)
        self.download_selected_btn.clicked.connect(self.download_selected)
        self.download_selected_btn.setEnabled(False)
        
        close_btn = QPushButton("Close")
        close_btn.setStyleSheet("""
            QPushButton {
                background-color: #dc3545;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-size: 13px;
                font-weight: 500;
                min-width: 70px;
            }
            QPushButton:hover {
                background-color: #c82333;
            }
        """)
        close_btn.clicked.connect(self.safe_close)
        
        bottom_layout.addWidget(self.outlet_label)
        bottom_layout.addWidget(self.selection_summary_label)        
        bottom_layout.addStretch()
        bottom_layout.addWidget(self.select_checkbox)
        bottom_layout.addWidget(self.download_selected_btn)
        bottom_layout.addWidget(close_btn)
        layout.addLayout(bottom_layout)
    
    def setup_shortcuts(self):
        """Setup keyboard shortcuts dengan proper cleanup"""
        try:
            # Store shortcuts untuk cleanup nanti
            self.shortcuts = []
            
            # Arrow keys
            left_shortcut = QShortcut(QKeySequence(Qt.Key_Left), self)
            left_shortcut.activated.connect(self.safe_previous_image)
            self.shortcuts.append(left_shortcut)
            
            right_shortcut = QShortcut(QKeySequence(Qt.Key_Right), self)
            right_shortcut.activated.connect(self.safe_next_image)
            self.shortcuts.append(right_shortcut)
            
            # Escape to close
            escape_shortcut = QShortcut(QKeySequence(Qt.Key_Escape), self)
            escape_shortcut.activated.connect(self.safe_close)
            self.shortcuts.append(escape_shortcut)
            
            # Space for select/deselect
            space_shortcut = QShortcut(QKeySequence(Qt.Key_Space), self)
            space_shortcut.activated.connect(self.toggle_current_selection)
            self.shortcuts.append(space_shortcut)
            
            print("✅ Keyboard shortcuts enabled")
            
        except Exception as e:
            print(f"⚠️ Shortcuts disabled: {e}")
            self.shortcuts = []
    
    def cleanup_shortcuts(self):
        """Cleanup keyboard shortcuts"""
        if hasattr(self, 'shortcuts'):
            for shortcut in self.shortcuts:
                try:
                    shortcut.setEnabled(False)
                    shortcut.deleteLater()
                except:
                    pass
            self.shortcuts.clear()
    
    # SAFE WRAPPER METHODS - Prevent operations during loading/closing
    def safe_previous_image(self):
        """Safe wrapper untuk previous_image"""
        if self.is_loading or self.is_closing:
            print("⚠️ Operation blocked - loading or closing in progress")
            return
        self.previous_image()
    
    def safe_next_image(self):
        """Safe wrapper untuk next_image"""
        if self.is_loading or self.is_closing:
            print("⚠️ Operation blocked - loading or closing in progress")
            return
        self.next_image()
    
    def safe_selection_changed(self, state):
        """Safe wrapper untuk selection changed"""
        if self.is_loading or self.is_closing:
            print("⚠️ Selection change blocked - loading or closing in progress")
            return
        self.on_selection_changed(state)
    
    def safe_close(self):
        """Safe wrapper untuk close"""
        if self.is_closing:
            print("⚠️ Close already in progress")
            return
        self.close()
    
    def toggle_current_selection(self):
        """Toggle selection of current image with spacebar"""
        if self.is_loading or self.is_closing:
            return
        
        current_state = self.select_checkbox.isChecked()
        self.select_checkbox.setChecked(not current_state)
    
    def update_ui_info(self):
        """Update UI info dengan safety checks"""
        if self.is_closing or not self.items_data:
            return
            
        try:
            current_item = self.items_data[self.current_index]
            
            # Update similarity
            similarity = current_item.get('similarity', 0)
            similarity_percent = similarity * 100
            
            # Color coding
            if similarity_percent >= 80:
                color = "#28a745"  # Green
            elif similarity_percent >= 60:
                color = "#ffc107"  # Yellow
            elif similarity_percent >= 40:
                color = "#fd7e14"  # Orange
            else:
                color = "#dc3545"  # Red
                
            self.similarity_label.setStyleSheet(f"""
                QLabel {{
                    background-color: {color};
                    color: white;
                    border-radius: 18px;
                    padding: 8px 16px;
                    font-size: 13px;
                    font-weight: 600;
                    min-width: 130px;
                }}
            """)
            self.similarity_label.setText(f"🎯 {similarity_percent:.1f}% match")
            
            # Update outlet
            outlet_name = current_item.get('outlet_name', 'Unknown')
            self.outlet_label.setText(f"🏪 {outlet_name}")
            
            # Update navigation buttons
            self.prev_btn.setEnabled(self.current_index > 0 and not self.is_closing)
            self.next_btn.setEnabled(self.current_index < len(self.items_data) - 1 and not self.is_closing)
            
            # Update selection checkbox - BLOCK SIGNALS saat update
            self.select_checkbox.blockSignals(True)
            self.select_checkbox.setChecked(self.selection_state.get(self.current_index, False))
            self.select_checkbox.blockSignals(False)
            self.select_checkbox.setEnabled(not self.is_closing)
            
            # Update selection summary
            selected_count = sum(self.selection_state.values())
            if selected_count > 0:
                self.selection_summary_label.setText(f"📋 {selected_count} selected")
                self.download_selected_btn.setEnabled(True and not self.is_closing)
                self.download_selected_btn.setText(f"⬇️ Download ({selected_count})")
            else:
                self.selection_summary_label.setText("")
                self.download_selected_btn.setEnabled(False)
                self.download_selected_btn.setText("⬇️ Download Selected")
            
            # Update window title
            filename = current_item.get('filename', 'Unknown')
            short_filename = filename[:25] + "..." if len(filename) > 25 else filename
            self.setWindowTitle(f"Image Preview - {short_filename} ({self.current_index + 1}/{len(self.items_data)})")
            
        except Exception as e:
            print(f"❌ Error updating UI info: {e}")
    
    def on_selection_changed(self, state):
        """Handle checkbox selection change"""
        if self.is_closing:
            return
            
        try:
            is_selected = state == 2  # Qt.Checked = 2
            self.selection_state[self.current_index] = is_selected
            
            # Emit signal untuk parent
            self.selection_changed.emit(self.current_index, is_selected)
            
            # Update UI
            self.update_ui_info()
            
            print(f"{'✅' if is_selected else '❌'} Image {self.current_index + 1} {'selected' if is_selected else 'deselected'}")
        except Exception as e:
            print(f"❌ Error in selection changed: {e}")
    
    def load_current_image(self):
        """Load current image dengan safety checks"""
        if self.is_closing or not self.items_data:
            return
        
        # Set loading flag
        self.is_loading = True
        
        try:
            # Clear previous image IMMEDIATELY
            self.image_label.clear()
            self.image_label.setText("📥 Loading image...\n\nPlease wait...")
            
            # Force UI update
            QApplication.processEvents()
            
            # Update UI info
            self.update_ui_info()
            
            current_item = self.items_data[self.current_index]
            url_or_path = current_item.get('url_or_path', '')
            
            if not url_or_path:
                self.image_label.setText("❌ No image available")
                return
                
            if url_or_path.startswith(('http://', 'https://')):
                self.load_image_from_url(url_or_path)
            elif os.path.exists(url_or_path):
                self.load_image_from_file(url_or_path)
            else:
                self.image_label.setText("❌ Image not found")
                
        except Exception as e:
            print(f"❌ Error loading current image: {e}")
            self.image_label.setText(f"❌ Error loading image\n\n{str(e)}")
        finally:
            # Always clear loading flag dan update UI
            self.is_loading = False
            self.update_ui_info()  # Update button states
    
    def fix_image_orientation(self, image_path_or_data, is_url=False):
        """
        ✅ WORKING: Fix EXIF orientation - tested and confirmed working
        Returns QPixmap with correct orientation or None if failed
        """
        try:
            from PIL import Image
            import numpy as np
            from io import BytesIO
            
            print(f"🔧 Starting orientation fix (is_url: {is_url})")
            
            # Load image based on type
            if is_url:
                pil_image = Image.open(BytesIO(image_path_or_data))
                print(f"🌐 Loaded image from URL data: {len(image_path_or_data)} bytes")
            else:
                pil_image = Image.open(image_path_or_data)
                print(f"📁 Loaded image from file: {image_path_or_data}")
            
            print(f"🖼️ Original image size: {pil_image.size}, mode: {pil_image.mode}")
            
            # Get EXIF orientation
            orientation = None
            try:
                # Try newer method first
                exif_data = pil_image.getexif()
                orientation = exif_data.get(274)  # 274 = orientation tag
                if orientation:
                    print(f"🧭 EXIF orientation found via getexif(): {orientation}")
            except:
                pass
            
            # Try older method if newer failed
            if not orientation:
                try:
                    exif_data = pil_image._getexif()
                    if exif_data:
                        orientation = exif_data.get(274)
                        if orientation:
                            print(f"🧭 EXIF orientation found via _getexif(): {orientation}")
                except:
                    pass
            
            # Apply rotation based on EXIF orientation
            rotation_applied = False
            if orientation:
                if orientation == 1:
                    print("✅ No rotation needed (orientation = 1)")
                elif orientation == 2:
                    pil_image = pil_image.transpose(Image.FLIP_LEFT_RIGHT)
                    rotation_applied = True
                    print("🔄 Applied horizontal flip (orientation = 2)")
                elif orientation == 3:
                    pil_image = pil_image.rotate(180, expand=True)
                    rotation_applied = True
                    print("🔄 Applied 180° rotation (orientation = 3)")
                elif orientation == 4:
                    pil_image = pil_image.transpose(Image.FLIP_TOP_BOTTOM)
                    rotation_applied = True
                    print("🔄 Applied vertical flip (orientation = 4)")
                elif orientation == 5:
                    pil_image = pil_image.transpose(Image.FLIP_LEFT_RIGHT)
                    pil_image = pil_image.rotate(270, expand=True)
                    rotation_applied = True
                    print("🔄 Applied horizontal flip + 270° rotation (orientation = 5)")
                elif orientation == 6:
                    pil_image = pil_image.rotate(270, expand=True)
                    rotation_applied = True
                    print("🔄 Applied 270° rotation (orientation = 6)")
                elif orientation == 7:
                    pil_image = pil_image.transpose(Image.FLIP_LEFT_RIGHT)
                    pil_image = pil_image.rotate(90, expand=True)
                    rotation_applied = True
                    print("🔄 Applied horizontal flip + 90° rotation (orientation = 7)")
                elif orientation == 8:
                    # ✅ THIS IS YOUR CASE!
                    pil_image = pil_image.rotate(90, expand=True)
                    rotation_applied = True
                    print("🔄 ✨ Applied 90° rotation (orientation = 8) - FIXED!")
                else:
                    print(f"❓ Unknown orientation: {orientation}")
            else:
                print("✅ No EXIF orientation found")
            
            # Convert PIL to QPixmap
            if pil_image.mode != 'RGB':
                pil_image = pil_image.convert('RGB')
                print("🔄 Converted to RGB")
            
            # Convert to numpy array
            np_array = np.array(pil_image)
            height, width, channels = np_array.shape
            bytes_per_line = channels * width
            
            # Create QImage
            q_image = QImage(np_array.data, width, height, bytes_per_line, QImage.Format_RGB888)
            
            # Convert to QPixmap
            pixmap = QPixmap.fromImage(q_image)
            
            if rotation_applied:
                print(f"✅ ✨ ORIENTATION FIXED! New size: {pixmap.width()}x{pixmap.height()}")
            else:
                print(f"✅ Image loaded: {pixmap.width()}x{pixmap.height()}")
            
            return pixmap if not pixmap.isNull() else None
            
        except ImportError:
            print("❌ Missing Pillow or numpy. Install with: pip install Pillow numpy")
            return None
        except Exception as e:
            print(f"❌ Error fixing orientation: {e}")
            import traceback
            traceback.print_exc()
            return None

    def load_image_from_url(self, url):
        """✅ Updated load from URL with working orientation fix"""
        if self.is_closing:
            return
            
        try:
            print(f"🌐 Downloading image from URL...")
            response = requests.get(url, timeout=15)
            if response.status_code == 200:
                print(f"✅ Downloaded {len(response.content)} bytes")
                
                # ✅ ALWAYS fix orientation first
                pixmap = self.fix_image_orientation(response.content, is_url=True)
                
                if pixmap and not pixmap.isNull():
                    print("✅ ✨ Using orientation-fixed image")
                    self.display_pixmap(pixmap)
                else:
                    print("⚠️ Orientation fix failed, using fallback")
                    # Fallback to temp file
                    with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as tmp_file:
                        tmp_file.write(response.content)
                        temp_path = tmp_file.name
                    
                    self.temp_files.append(temp_path)
                    
                    # Try orientation fix on file
                    pixmap = self.fix_image_orientation(temp_path, is_url=False)
                    if pixmap and not pixmap.isNull():
                        self.display_pixmap(pixmap)
                    else:
                        # Last resort - basic loader
                        self.load_image_from_file_fallback(temp_path)
            else:
                self.image_label.setText(f"❌ Download failed\n\nStatus: {response.status_code}")
        except Exception as e:
            if not self.is_closing:
                self.image_label.setText(f"❌ Download error\n\n{str(e)}")
                print(f"❌ URL download error: {e}")
        finally:
            self.is_loading = False
            if not self.is_closing:
                self.update_ui_info()

    def load_image_from_file(self, file_path):
        """✅ Updated load from file with working orientation fix"""
        if self.is_closing:
            return
            
        try:
            print(f"📁 Loading image from file: {os.path.basename(file_path)}")
            
            # ✅ ALWAYS fix orientation first  
            pixmap = self.fix_image_orientation(file_path, is_url=False)
            
            if pixmap and not pixmap.isNull():
                print("✅ ✨ Using orientation-fixed image")
                self.display_pixmap(pixmap)
            else:
                print("⚠️ Orientation fix failed, using fallback")
                self.load_image_from_file_fallback(file_path)
                
        except Exception as e:
            if not self.is_closing:
                self.image_label.setText(f"❌ Error loading image\n\n{str(e)}")
                print(f"❌ File load error: {e}")
        finally:
            self.is_loading = False
            if not self.is_closing:
                self.update_ui_info()
    
    def load_image_from_file_fallback(self, file_path):
        """Fallback method without orientation fix"""
        try:
            pixmap = QPixmap(file_path)
            if pixmap.isNull():
                self.image_label.setText("❌ Invalid image file")
                return
            
            print("⚠️ Using fallback loading without orientation fix")
            self.display_pixmap(pixmap)
            
        except Exception as e:
            if not self.is_closing:
                self.image_label.setText(f"❌ Error loading image\n\n{str(e)}")
    
    def display_pixmap(self, pixmap):
        """Display pixmap with proper scaling and dialog resizing"""
        if self.is_closing or pixmap.isNull():
            return
            
        try:
            # Get screen size for scaling
            screen = QApplication.primaryScreen()
            screen_rect = screen.availableGeometry()
            max_width = int(screen_rect.width() * 0.7)
            max_height = int(screen_rect.height() * 0.6)
            
            # Scale image if needed
            if pixmap.width() > max_width or pixmap.height() > max_height:
                scaled_pixmap = pixmap.scaled(max_width, max_height, 
                                            Qt.KeepAspectRatio, 
                                            Qt.SmoothTransformation)
                print(f"🔄 Scaled image: {pixmap.width()}x{pixmap.height()} → {scaled_pixmap.width()}x{scaled_pixmap.height()}")
            else:
                scaled_pixmap = pixmap
                print(f"✅ Image fits screen: {pixmap.width()}x{pixmap.height()}")
            
            # IMPORTANT: Check if still not closing before setting pixmap
            if not self.is_closing:
                self.image_label.setPixmap(scaled_pixmap)
                
                # Adjust dialog size
                dialog_width = scaled_pixmap.width() + 80
                dialog_height = scaled_pixmap.height() + 200
                
                dialog_width = min(dialog_width, screen_rect.width() - 100)
                dialog_height = min(dialog_height, screen_rect.height() - 100)
                
                self.resize(dialog_width, dialog_height)
                
                # Center dialog
                x = (screen_rect.width() - dialog_width) // 2
                y = (screen_rect.height() - dialog_height) // 2
                self.move(x, y)
                
                print(f"✅ Image displayed and dialog resized to {dialog_width}x{dialog_height}")
            
        except Exception as e:
            if not self.is_closing:
                self.image_label.setText(f"❌ Error displaying image\n\n{str(e)}")
                print(f"❌ Display error: {e}")
    
    def previous_image(self):
        """Go to previous image"""
        if self.is_loading or self.is_closing:
            return
            
        print(f"⬅️ Previous clicked - current: {self.current_index}")
        if self.current_index > 0:
            self.current_index -= 1
            self.load_current_image()
            print(f"✅ Moved to index: {self.current_index}")
        else:
            print("⚠️ Already at first image")
    
    def next_image(self):
        """Go to next image"""
        if self.is_loading or self.is_closing:
            return
            
        print(f"➡️ Next clicked - current: {self.current_index}")
        if self.current_index < len(self.items_data) - 1:
            self.current_index += 1
            self.load_current_image()
            print(f"✅ Moved to index: {self.current_index}")
        else:
            print("⚠️ Already at last image")
    
    def get_selected_items(self):
        """Get list of selected items with their data"""
        selected_items = []
        for index, is_selected in self.selection_state.items():
            if is_selected and index < len(self.items_data):
                selected_items.append({
                    'index': index,
                    'data': self.items_data[index]
                })
        return selected_items
    
    def download_selected(self):
        """Download selected images - WORKING IMPLEMENTATION"""
        if self.is_closing:
            return
            
        try:
            selected_items = self.get_selected_items()
            
            if not selected_items:
                QMessageBox.information(self, "Download", "No images selected for download.")
                return
            
            print(f"📥 Preview download requested: {len(selected_items)} items")
            
            # Debug: Print selected items
            for i, item in enumerate(selected_items):
                data = item['data']
                print(f"  {i+1}. {data.get('filename', 'unknown')} from {data.get('outlet_name', 'unknown')}")
            
            # Emit signal to parent dengan selected items data
            self.download_requested.emit(selected_items)
            
        except Exception as e:
            print(f"❌ Error in download_selected: {e}")
            QMessageBox.critical(self, "Download Error", f"Failed to start download:\n{str(e)}")
    
    def closeEvent(self, event):
        """Clean up dengan proper order"""
        print("🔄 Starting cleanup process...")
        
        # Set closing flag to prevent new operations
        self.is_closing = True
        
        # Disable all controls immediately
        self.prev_btn.setEnabled(False)
        self.next_btn.setEnabled(False)
        self.select_checkbox.setEnabled(False)
        self.download_selected_btn.setEnabled(False)
        
        # Clear image immediately to prevent display issues
        self.image_label.clear()
        self.image_label.setText("Closing...")
        
        # Force process events to ensure UI updates
        QApplication.processEvents()
        
        # Cleanup shortcuts
        self.cleanup_shortcuts()
        
        # Clean up temp files
        print(f"🧹 Cleaning up {len(self.temp_files)} temp files")
        for temp_file in self.temp_files:
            try:
                if os.path.exists(temp_file):
                    os.unlink(temp_file)
                    print(f"🗑️ Deleted: {temp_file}")
            except Exception as e:
                print(f"❌ Failed to delete {temp_file}: {e}")
        
        # Clear all references
        self.temp_files.clear()
        self.items_data.clear()
        self.selection_state.clear()
        
        print("✅ Cleanup completed")
        super().closeEvent(event)