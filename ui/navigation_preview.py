# ui/navigation_preview.py - SIMPLE SOLUTION

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
    """Simple preview dialog with global close state"""
    
    # GLOBAL CLASS VARIABLE - shared across all instances
    _global_close_requested = False
    
    # Signals untuk communicate back ke parent
    selection_changed = pyqtSignal(int, bool)  # index, is_selected
    download_requested = pyqtSignal(list)      # selected_items_data
    
    def __init__(self, items_data, start_index=0, parent=None):
        super().__init__(parent)
        
        # CHECK GLOBAL STATE FIRST
        if NavigationPreviewDialog._global_close_requested:
            print("BLOCKED: Preview blocked by global close state")
            self.reject()  # Close immediately
            return
        
        self.items_data = items_data
        self.current_index = start_index
        self.temp_files = []
        
        # Track selection state untuk setiap item
        self.selection_state = {i: False for i in range(len(items_data))}
        
        # Simple flags
        self.is_loading = False
        self.is_closing = False
        
        # Reset global state when new preview opens successfully
        NavigationPreviewDialog._global_close_requested = False
        
        self.setWindowTitle("Image Preview")
        self.setWindowFlags(Qt.Window | Qt.WindowCloseButtonHint | Qt.WindowMaximizeButtonHint)
        self.resize(800, 600)
        
        self.init_ui()
        self.setup_shortcuts()
        self.load_current_image()
    
    @classmethod
    def reset_global_state(cls):
        """Reset global close state - call this when main window opens new search"""
        cls._global_close_requested = False
        print("RESET: Global preview state reset")
    
    @classmethod
    def set_global_close_state(cls):
        """Set global close state - prevent any new previews"""
        cls._global_close_requested = True
        print("BLOCKED: Global preview state set to CLOSED")
    
    def init_ui(self):
        """Initialize UI - same as before"""
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
        
        # CLOSE BUTTON - SET GLOBAL STATE
        self.close_btn = QPushButton("Close")
        self.close_btn.setStyleSheet("""
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
        self.close_btn.clicked.connect(self.force_close)
        
        bottom_layout.addWidget(self.outlet_label)
        bottom_layout.addWidget(self.selection_summary_label)        
        bottom_layout.addStretch()
        bottom_layout.addWidget(self.select_checkbox)
        bottom_layout.addWidget(self.download_selected_btn)
        bottom_layout.addWidget(self.close_btn)
        layout.addLayout(bottom_layout)
    
    def setup_shortcuts(self):
        """Setup keyboard shortcuts"""
        try:
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
            escape_shortcut.activated.connect(self.force_close)
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
    
    def safe_previous_image(self):
        """Safe wrapper untuk previous_image"""
        if self.is_loading or self.is_closing or NavigationPreviewDialog._global_close_requested:
            return
        self.previous_image()
    
    def safe_next_image(self):
        """Safe wrapper untuk next_image"""
        if self.is_loading or self.is_closing or NavigationPreviewDialog._global_close_requested:
            return
        self.next_image()
    
    def safe_selection_changed(self, state):
        """Safe wrapper untuk selection changed"""
        if self.is_loading or self.is_closing or NavigationPreviewDialog._global_close_requested:
            return
        self.on_selection_changed(state)
    
    def force_close(self):
        """SIMPLE: Set global state and close"""
        print("CLOSE: Setting global close state and closing dialog")
        
        # SET GLOBAL STATE FIRST
        NavigationPreviewDialog.set_global_close_state()
        
        # Set local state
        self.is_closing = True
        
        # Disable all controls
        self.prev_btn.setEnabled(False)
        self.next_btn.setEnabled(False)
        self.select_checkbox.setEnabled(False)
        self.download_selected_btn.setEnabled(False)
        self.close_btn.setEnabled(False)
        
        # Close immediately
        self.reject()
    
    def toggle_current_selection(self):
        """Toggle selection of current image with spacebar"""
        if self.is_loading or self.is_closing or NavigationPreviewDialog._global_close_requested:
            return
        
        current_state = self.select_checkbox.isChecked()
        self.select_checkbox.setChecked(not current_state)
    
    def update_ui_info(self):
        """Update UI info dengan safety checks"""
        if self.is_closing or NavigationPreviewDialog._global_close_requested or not self.items_data:
            return
            
        try:
            current_item = self.items_data[self.current_index]
            
            # Update similarity
            similarity = current_item.get('similarity', 0)
            similarity_percent = similarity * 100
            
            # Color coding
            if similarity_percent >= 80:
                color = "#28a745"
            elif similarity_percent >= 60:
                color = "#ffc107"
            elif similarity_percent >= 40:
                color = "#fd7e14"
            else:
                color = "#dc3545"
                
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
            
            # Update selection checkbox
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
        if self.is_closing or NavigationPreviewDialog._global_close_requested:
            return
            
        try:
            is_selected = state == 2
            self.selection_state[self.current_index] = is_selected
            
            # Emit signal untuk parent
            self.selection_changed.emit(self.current_index, is_selected)
            
            # Update UI
            self.update_ui_info()
            
            print(f"{'✅' if is_selected else '❌'} Image {self.current_index + 1} {'selected' if is_selected else 'deselected'}")
        except Exception as e:
            print(f"❌ Error in selection changed: {e}")
    
    def load_current_image(self):
        """Load current image - SIMPLE VERSION"""
        if self.is_closing or NavigationPreviewDialog._global_close_requested or not self.items_data:
            return
        
        self.is_loading = True
        
        try:
            # Clear previous image
            self.image_label.clear()
            self.image_label.setText("📥 Loading...")
            QApplication.processEvents()
            
            # Check again after UI update
            if NavigationPreviewDialog._global_close_requested:
                return
            
            self.update_ui_info()
            
            current_item = self.items_data[self.current_index]
            
            # Use thumbnail for display
            thumbnail_url = current_item.get('thumbnail', '')
            
            if not thumbnail_url:
                thumbnail_url = current_item.get('original', '')
            
            if not thumbnail_url:
                self.image_label.setText("❌ No image available")
                return
                
            if thumbnail_url.startswith(('http://', 'https://')):
                self.load_image_from_url(thumbnail_url)
            elif os.path.exists(thumbnail_url):
                self.load_image_from_file(thumbnail_url)
            else:
                self.image_label.setText("❌ Image not found")
                
        except Exception as e:
            print(f"❌ Error loading current image: {e}")
            if not NavigationPreviewDialog._global_close_requested:
                self.image_label.setText(f"❌ Error: {str(e)}")
        finally:
            self.is_loading = False
            if not NavigationPreviewDialog._global_close_requested:
                self.update_ui_info()
    
    def load_image_from_url(self, url):
        """Simple URL loading"""
        if self.is_closing or NavigationPreviewDialog._global_close_requested:
            return
            
        try:
            response = requests.get(url, timeout=10)
            
            # Check state after network call
            if NavigationPreviewDialog._global_close_requested:
                return
                
            if response.status_code == 200:
                pixmap = QPixmap()
                pixmap.loadFromData(response.content)
                
                if not pixmap.isNull() and not NavigationPreviewDialog._global_close_requested:
                    self.display_pixmap(pixmap)
            else:
                if not NavigationPreviewDialog._global_close_requested:
                    self.image_label.setText(f"❌ Download failed: {response.status_code}")
                    
        except Exception as e:
            if not NavigationPreviewDialog._global_close_requested:
                self.image_label.setText(f"❌ Download error: {str(e)}")

    def load_image_from_file(self, file_path):
        """Simple file loading"""
        if self.is_closing or NavigationPreviewDialog._global_close_requested:
            return
            
        try:
            pixmap = QPixmap(file_path)
            if not pixmap.isNull() and not NavigationPreviewDialog._global_close_requested:
                self.display_pixmap(pixmap)
            else:
                if not NavigationPreviewDialog._global_close_requested:
                    self.image_label.setText("❌ Invalid image")
        except Exception as e:
            if not NavigationPreviewDialog._global_close_requested:
                self.image_label.setText(f"❌ Error: {str(e)}")
    
    def display_pixmap(self, pixmap):
        """Display pixmap with scaling"""
        if self.is_closing or NavigationPreviewDialog._global_close_requested or pixmap.isNull():
            return
            
        try:
            # Get screen size
            screen = QApplication.primaryScreen()
            screen_rect = screen.availableGeometry()
            max_width = int(screen_rect.width() * 0.7)
            max_height = int(screen_rect.height() * 0.6)
            
            # Scale if needed
            if pixmap.width() > max_width or pixmap.height() > max_height:
                scaled_pixmap = pixmap.scaled(max_width, max_height, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            else:
                scaled_pixmap = pixmap
            
            # Final check before display
            if not NavigationPreviewDialog._global_close_requested:
                self.image_label.setPixmap(scaled_pixmap)
                
                # Resize dialog
                dialog_width = min(scaled_pixmap.width() + 80, screen_rect.width() - 100)
                dialog_height = min(scaled_pixmap.height() + 200, screen_rect.height() - 100)
                
                self.resize(dialog_width, dialog_height)
                
                # Center dialog
                x = (screen_rect.width() - dialog_width) // 2
                y = (screen_rect.height() - dialog_height) // 2
                self.move(x, y)
            
        except Exception as e:
            if not NavigationPreviewDialog._global_close_requested:
                self.image_label.setText(f"❌ Display error: {str(e)}")
    
    def previous_image(self):
        """Go to previous image"""
        if self.is_loading or self.is_closing or NavigationPreviewDialog._global_close_requested:
            return
            
        if self.current_index > 0:
            self.current_index -= 1
            self.load_current_image()
    
    def next_image(self):
        """Go to next image"""
        if self.is_loading or self.is_closing or NavigationPreviewDialog._global_close_requested:
            return
            
        if self.current_index < len(self.items_data) - 1:
            self.current_index += 1
            self.load_current_image()
    
    def get_selected_items(self):
        """Get selected items for download"""
        selected_items = []
        for index, is_selected in self.selection_state.items():
            if is_selected and index < len(self.items_data):
                item_data = self.items_data[index].copy()
                
                # Use original URL for download
                original_url = item_data.get('original', '')
                if original_url:
                    item_data['url_or_path'] = original_url
                else:
                    thumbnail_url = item_data.get('thumbnail', '')
                    item_data['url_or_path'] = thumbnail_url
                
                selected_items.append({
                    'index': index,
                    'data': item_data
                })
        return selected_items
    
    def download_selected(self):
        """Download selected images"""
        if self.is_closing or NavigationPreviewDialog._global_close_requested:
            return
            
        try:
            selected_items = self.get_selected_items()
            
            if not selected_items:
                QMessageBox.information(self, "Download", "No images selected.")
                return
            
            # Emit signal to parent
            self.download_requested.emit(selected_items)
            
        except Exception as e:
            QMessageBox.critical(self, "Download Error", f"Failed: {str(e)}")
    
    def closeEvent(self, event):
        """Simple cleanup"""
        print("CLEANUP: Dialog closing")
        
        # Set global close state
        NavigationPreviewDialog.set_global_close_state()
        
        self.is_closing = True
        
        # Cleanup shortcuts
        self.cleanup_shortcuts()
        
        # Clean temp files
        if hasattr(self, 'temp_files'):
            for temp_file in self.temp_files:
                try:
                    if os.path.exists(temp_file):
                        os.unlink(temp_file)
                except:
                    pass
        
        # Accept event
        event.accept()