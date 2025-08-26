# ui/navigation_preview.py - CPU Optimized Version

import os
import logging
import requests
import tempfile
from PyQt5.QtCore import Qt, pyqtSignal, QTimer, QThread
from PyQt5.QtGui import QPixmap, QKeySequence, QImage
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, 
    QCheckBox, QApplication, QMessageBox, QShortcut
)

logger = logging.getLogger(__name__)

class ImageLoaderThread(QThread):
    """Background thread untuk load images tanpa blocking UI"""
    image_loaded = pyqtSignal(QPixmap)
    loading_failed = pyqtSignal(str)
    
    def __init__(self, url_or_path):
        super().__init__()
        self.url_or_path = url_or_path
        self.cancelled = False
    
    def cancel(self):
        """Cancel loading operation"""
        self.cancelled = True
        
    def run(self):
        """Load image in background"""
        if self.cancelled:
            return
            
        try:
            if self.url_or_path.startswith(('http://', 'https://')):
                self.load_from_url()
            elif os.path.exists(self.url_or_path):
                self.load_from_file()
            else:
                self.loading_failed.emit("Image not found")
                
        except Exception as e:
            if not self.cancelled:
                self.loading_failed.emit(str(e))
    
    def load_from_url(self):
        """Load image from URL"""
        try:
            # Set shorter timeout and smaller chunk size
            response = requests.get(self.url_or_path, timeout=5, stream=True)
            
            if self.cancelled:
                return
                
            if response.status_code == 200:
                # Load in chunks to check cancellation
                content = b''
                for chunk in response.iter_content(chunk_size=8192):
                    if self.cancelled:
                        return
                    content += chunk
                
                if not self.cancelled:
                    pixmap = QPixmap()
                    success = pixmap.loadFromData(content)
                    
                    if success and not pixmap.isNull():
                        self.image_loaded.emit(pixmap)
                    else:
                        self.loading_failed.emit("Invalid image format")
            else:
                self.loading_failed.emit(f"HTTP {response.status_code}")
                
        except requests.exceptions.Timeout:
            if not self.cancelled:
                self.loading_failed.emit("Download timeout")
        except Exception as e:
            if not self.cancelled:
                self.loading_failed.emit(str(e))
    
    def load_from_file(self):
        """Load image from local file"""
        try:
            pixmap = QPixmap(self.url_or_path)
            
            if not self.cancelled and not pixmap.isNull():
                self.image_loaded.emit(pixmap)
            elif not self.cancelled:
                self.loading_failed.emit("Invalid image file")
                
        except Exception as e:
            if not self.cancelled:
                self.loading_failed.emit(str(e))

class NavigationPreviewDialog(QDialog):
    """CPU-optimized preview dialog"""
    
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
        
        # ===== CPU OPTIMIZATION FLAGS =====
        self.is_loading = False
        self.is_closing = False
        self.pending_load_timer = None
        self.current_loader_thread = None
        self.ui_update_timer = None
        
        # Image cache untuk menghindari reload
        self.image_cache = {}
        self.max_cache_size = 10  # Cache maksimal 10 images
        
        # Reset global state when new preview opens successfully
        NavigationPreviewDialog._global_close_requested = False
        
        self.setWindowTitle("Image Preview")
        self.setWindowFlags(Qt.Window | Qt.WindowCloseButtonHint | Qt.WindowMaximizeButtonHint)
        self.resize(800, 600)
        
        self.init_ui()
        self.setup_shortcuts()
        
        # ===== CPU OPTIMIZATION: Delayed load =====
        # Don't load immediately, give UI time to render first
        self.initial_load_timer = QTimer()
        self.initial_load_timer.setSingleShot(True)
        self.initial_load_timer.timeout.connect(self.load_current_image)
        self.initial_load_timer.start(100)  # 100ms delay
    
    @classmethod
    def reset_global_state(cls):
        """Reset global close state"""
        cls._global_close_requested = False
        print("RESET: Global preview state reset")
    
    @classmethod
    def set_global_close_state(cls):
        """Set global close state"""
        cls._global_close_requested = True
        print("BLOCKED: Global preview state set to CLOSED")
    
    def init_ui(self):
        """Initialize UI - OPTIMIZED VERSION"""
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)
       
        # Navigation bar
        nav_layout = QHBoxLayout()
        nav_layout.setSpacing(20)
        
        # Previous button
        self.prev_btn = QPushButton("← Previous")
        self.prev_btn.setStyleSheet(self.get_button_style("#6c757d", "#5a6268"))
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
        self.next_btn = QPushButton("Next →")
        self.next_btn.setStyleSheet(self.get_button_style("#007bff", "#0056b3"))
        self.next_btn.setFixedSize(110, 38)
        self.next_btn.clicked.connect(self.safe_next_image)
        
        nav_layout.addWidget(self.prev_btn)
        nav_layout.addStretch()
        nav_layout.addWidget(self.similarity_label)
        nav_layout.addStretch()
        nav_layout.addWidget(self.next_btn)
        layout.addLayout(nav_layout)
        
        # Image display area - OPTIMIZED
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
        # ===== CPU FIX: Set minimum size to avoid constant resizing =====
        self.image_label.setMinimumSize(400, 300)
        self.image_label.setMaximumSize(1200, 800)  # Prevent excessive scaling
        layout.addWidget(self.image_label)
        
        # Bottom controls
        bottom_layout = QHBoxLayout()
        bottom_layout.setSpacing(15)
        
        self.outlet_label = QLabel()
        self.outlet_label.setStyleSheet("font-size: 12px; color: #666; padding: 5px;")
        
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
        self.select_checkbox = QCheckBox("Select")
        self.select_checkbox.setStyleSheet(self.get_checkbox_style())
        self.select_checkbox.stateChanged.connect(self.safe_selection_changed)
        
        # Download selected button
        self.download_selected_btn = QPushButton("↓ Download Selected")
        self.download_selected_btn.setStyleSheet(self.get_button_style("#28a745", "#218838"))
        self.download_selected_btn.clicked.connect(self.download_selected)
        self.download_selected_btn.setEnabled(False)
        
        # CLOSE BUTTON
        self.close_btn = QPushButton("Close")
        self.close_btn.setStyleSheet(self.get_button_style("#dc3545", "#c82333"))
        self.close_btn.clicked.connect(self.force_close)
        
        bottom_layout.addWidget(self.outlet_label)
        bottom_layout.addWidget(self.selection_summary_label)        
        bottom_layout.addStretch()
        bottom_layout.addWidget(self.select_checkbox)
        bottom_layout.addWidget(self.download_selected_btn)
        bottom_layout.addWidget(self.close_btn)
        layout.addLayout(bottom_layout)
    
    def get_button_style(self, bg_color, hover_color):
        """Get consistent button style"""
        return f"""
            QPushButton {{
                background-color: {bg_color};
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-size: 13px;
                font-weight: 500;
                min-width: 70px;
            }}
            QPushButton:hover:enabled {{
                background-color: {hover_color};
            }}
            QPushButton:disabled {{
                background-color: #cccccc;
                color: #999;
            }}
        """
    
    def get_checkbox_style(self):
        """Get checkbox style"""
        return """
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
        """
    
    def setup_shortcuts(self):
        """Setup keyboard shortcuts - OPTIMIZED"""
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
            
        except Exception as e:
            print(f"Shortcuts disabled: {e}")
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
        """Safe wrapper dengan debouncing"""
        if self.is_loading or self.is_closing or NavigationPreviewDialog._global_close_requested:
            return
        
        # ===== CPU FIX: Debounce rapid navigation =====
        if self.pending_load_timer and self.pending_load_timer.isActive():
            self.pending_load_timer.stop()
        
        if self.current_index > 0:
            self.current_index -= 1
            self.schedule_image_load()
    
    def safe_next_image(self):
        """Safe wrapper dengan debouncing"""
        if self.is_loading or self.is_closing or NavigationPreviewDialog._global_close_requested:
            return
        
        # ===== CPU FIX: Debounce rapid navigation =====
        if self.pending_load_timer and self.pending_load_timer.isActive():
            self.pending_load_timer.stop()
        
        if self.current_index < len(self.items_data) - 1:
            self.current_index += 1
            self.schedule_image_load()
    
    def schedule_image_load(self):
        """Schedule image loading dengan delay untuk debouncing"""
        if not self.pending_load_timer:
            self.pending_load_timer = QTimer()
            self.pending_load_timer.setSingleShot(True)
            self.pending_load_timer.timeout.connect(self.load_current_image)
        
        # ===== CPU FIX: 200ms debounce untuk rapid navigation =====
        self.pending_load_timer.start(200)
        
        # Update UI immediately (without image)
        self.update_ui_info_only()
    
    def safe_selection_changed(self, state):
        """Safe wrapper untuk selection changed"""
        if self.is_loading or self.is_closing or NavigationPreviewDialog._global_close_requested:
            return
        self.on_selection_changed(state)
    
    def force_close(self):
        """OPTIMIZED: Quick close dengan cleanup"""
        print("CLOSE: Forcing close with cleanup")
        
        # SET GLOBAL STATE FIRST
        NavigationPreviewDialog.set_global_close_state()
        
        # Set local state
        self.is_closing = True
        
        # ===== CPU FIX: Cancel all pending operations =====
        self.cancel_all_operations()
        
        # Disable all controls
        self.disable_all_controls()
        
        # Close immediately
        self.reject()
    
    def cancel_all_operations(self):
        """Cancel all ongoing operations"""
        # Cancel timers
        if self.pending_load_timer:
            self.pending_load_timer.stop()
        
        if hasattr(self, 'initial_load_timer'):
            self.initial_load_timer.stop()
        
        if self.ui_update_timer:
            self.ui_update_timer.stop()
        
        # Cancel image loading thread
        if self.current_loader_thread and self.current_loader_thread.isRunning():
            self.current_loader_thread.cancel()
            self.current_loader_thread.quit()
            self.current_loader_thread.wait(1000)  # Wait max 1 second
    
    def disable_all_controls(self):
        """Disable all UI controls"""
        self.prev_btn.setEnabled(False)
        self.next_btn.setEnabled(False)
        self.select_checkbox.setEnabled(False)
        self.download_selected_btn.setEnabled(False)
        self.close_btn.setEnabled(False)
    
    def toggle_current_selection(self):
        """Toggle selection of current image with spacebar"""
        if self.is_loading or self.is_closing or NavigationPreviewDialog._global_close_requested:
            return
        
        current_state = self.select_checkbox.isChecked()
        self.select_checkbox.setChecked(not current_state)
    
    def update_ui_info_only(self):
        """Update only UI info without image - FAST"""
        if self.is_closing or NavigationPreviewDialog._global_close_requested or not self.items_data:
            return
        
        # ===== CPU FIX: Batch UI updates dengan timer =====
        if not self.ui_update_timer:
            self.ui_update_timer = QTimer()
            self.ui_update_timer.setSingleShot(True)
            self.ui_update_timer.timeout.connect(self._do_ui_update)
        
        if not self.ui_update_timer.isActive():
            self.ui_update_timer.start(50)  # Batch updates setiap 50ms
    
    def _do_ui_update(self):
        """Actual UI update implementation"""
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
            self.similarity_label.setText(f"{similarity_percent:.1f}% match")
            
            # Update outlet
            outlet_name = current_item.get('outlet_name', 'Unknown')
            self.outlet_label.setText(f"Outlet: {outlet_name}")
            
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
                self.selection_summary_label.setText(f"{selected_count} selected")
                self.download_selected_btn.setEnabled(True and not self.is_closing)
                self.download_selected_btn.setText(f"↓ Download ({selected_count})")
            else:
                self.selection_summary_label.setText("")
                self.download_selected_btn.setEnabled(False)
                self.download_selected_btn.setText("↓ Download Selected")
            
            # Update window title
            filename = current_item.get('filename', 'Unknown')
            short_filename = filename[:25] + "..." if len(filename) > 25 else filename
            self.setWindowTitle(f"Image Preview - {short_filename} ({self.current_index + 1}/{len(self.items_data)})")
            
        except Exception as e:
            print(f"Error updating UI info: {e}")
    
    def update_ui_info(self):
        """Compatibility method - delegates to optimized version"""
        self.update_ui_info_only()
    
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
            self.update_ui_info_only()
            
        except Exception as e:
            print(f"Error in selection changed: {e}")
    
    def load_current_image(self):
        """Load current image - OPTIMIZED dengan caching dan background loading"""
        if self.is_closing or NavigationPreviewDialog._global_close_requested or not self.items_data:
            return
        
        # Cancel any existing loader
        if self.current_loader_thread and self.current_loader_thread.isRunning():
            self.current_loader_thread.cancel()
            self.current_loader_thread.quit()
            self.current_loader_thread.wait(500)
        
        try:
            current_item = self.items_data[self.current_index]
            
            # Use thumbnail for display
            thumbnail_url = current_item.get('thumbnail', '')
            if not thumbnail_url:
                thumbnail_url = current_item.get('original', '')
            
            if not thumbnail_url:
                self.image_label.setText("❌ No image available")
                self.update_ui_info_only()
                return
            
            # ===== CPU FIX: Check cache first =====
            cache_key = f"{self.current_index}_{thumbnail_url}"
            if cache_key in self.image_cache:
                print(f"✅ Using cached image for index {self.current_index}")
                cached_pixmap = self.image_cache[cache_key]
                self.display_pixmap(cached_pixmap)
                self.update_ui_info_only()
                return
            
            # Show loading state
            self.is_loading = True
            self.image_label.clear()
            self.image_label.setText("Loading...")
            self.update_ui_info_only()
            
            # ===== CPU FIX: Load in background thread =====
            self.current_loader_thread = ImageLoaderThread(thumbnail_url)
            self.current_loader_thread.image_loaded.connect(self.on_image_loaded)
            self.current_loader_thread.loading_failed.connect(self.on_image_failed)
            self.current_loader_thread.finished.connect(self.on_loading_finished)
            self.current_loader_thread.start()
                
        except Exception as e:
            print(f"Error loading current image: {e}")
            if not NavigationPreviewDialog._global_close_requested:
                self.image_label.setText(f"❌ Error: {str(e)}")
            self.is_loading = False
            self.update_ui_info_only()
    
    def on_image_loaded(self, pixmap):
        """Handle successful image loading"""
        if self.is_closing or NavigationPreviewDialog._global_close_requested:
            return
        
        # ===== CPU FIX: Cache the loaded image =====
        current_item = self.items_data[self.current_index]
        thumbnail_url = current_item.get('thumbnail', '') or current_item.get('original', '')
        cache_key = f"{self.current_index}_{thumbnail_url}"
        
        # Manage cache size
        if len(self.image_cache) >= self.max_cache_size:
            # Remove oldest entry
            oldest_key = next(iter(self.image_cache))
            del self.image_cache[oldest_key]
        
        self.image_cache[cache_key] = pixmap
        self.display_pixmap(pixmap)
    
    def on_image_failed(self, error_message):
        """Handle image loading failure"""
        if not NavigationPreviewDialog._global_close_requested and not self.is_closing:
            self.image_label.setText(f"❌ {error_message}")
    
    def on_loading_finished(self):
        """Handle loading completion"""
        self.is_loading = False
        if not NavigationPreviewDialog._global_close_requested and not self.is_closing:
            self.update_ui_info_only()
    
    def display_pixmap(self, pixmap):
        """Display pixmap with OPTIMIZED scaling"""
        if self.is_closing or NavigationPreviewDialog._global_close_requested or pixmap.isNull():
            return
            
        try:
            # ===== CPU FIX: Limit maximum image size untuk performance =====
            max_width = 800   # Reduced from screen-based calculation
            max_height = 600  # Reduced from screen-based calculation
            
            # Scale only if necessary
            if pixmap.width() > max_width or pixmap.height() > max_height:
                # ===== CPU FIX: Use faster scaling =====
                scaled_pixmap = pixmap.scaled(
                    max_width, max_height, 
                    Qt.KeepAspectRatio, 
                    Qt.FastTransformation  # Changed from SmoothTransformation
                )
            else:
                scaled_pixmap = pixmap
            
            # Final check before display
            if not NavigationPreviewDialog._global_close_requested:
                self.image_label.setPixmap(scaled_pixmap)
                
                # ===== CPU FIX: Don't resize dialog frequently =====
                # Only resize if significantly different
                current_size = self.size()
                new_width = min(scaled_pixmap.width() + 80, 1000)
                new_height = min(scaled_pixmap.height() + 200, 800)
                
                if abs(current_size.width() - new_width) > 100 or abs(current_size.height() - new_height) > 100:
                    self.resize(new_width, new_height)
            
        except Exception as e:
            if not NavigationPreviewDialog._global_close_requested:
                self.image_label.setText(f"❌ Display error: {str(e)}")
    
    def previous_image(self):
        """Go to previous image - OPTIMIZED"""
        self.safe_previous_image()
    
    def next_image(self):
        """Go to next image - OPTIMIZED"""
        self.safe_next_image()
    
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
        """OPTIMIZED cleanup"""
        print("CLEANUP: Dialog closing with optimized cleanup")
        
        # Set global close state
        NavigationPreviewDialog.set_global_close_state()
        
        self.is_closing = True
        
        # ===== CPU FIX: Quick cleanup =====
        self.cancel_all_operations()
        self.cleanup_shortcuts()
        
        # Clear image cache
        if hasattr(self, 'image_cache'):
            self.image_cache.clear()
        
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