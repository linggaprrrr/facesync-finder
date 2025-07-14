import os
import sys
import logging
import requests
from datetime import datetime


from PyQt5.QtCore import (
    Qt, QDir, QMimeData, QUrl, QThread, QThreadPool, QRunnable,
    pyqtSignal, QObject, QTimer
)
from PyQt5.QtGui import (
    QPixmap, QIcon, QDrag, QClipboard, QPainter, QColor, QFont
)
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QFileSystemModel, QTreeView, QListView,
    QFileDialog, QTextEdit, QPushButton, QVBoxLayout, QWidget, QHBoxLayout,
    QLabel, QLineEdit, QListWidget, QListWidgetItem, QMenu, QAction,
    QInputDialog, QMessageBox, QAbstractItemView, QDialog, QFormLayout,
    QDialogButtonBox, QTabWidget, QGroupBox, QCheckBox, QProgressBar,
    QProgressDialog
)

from core.watcher import start_watcher, stop_watcher
from ui.admin_login import AdminLoginDialog
from ui.admin_setting import AdminSettingsDialog
from utils.features import DragDropListWidget
from ui.image_preview_dialog import ImagePreviewDialog
from ui.face_search_dialog import FaceSearchDialog
from core.download_worker import DownloadWorker
from utils.image_processing import get_shared_detector
from core.device_setup import resnet, device, API_BASE
logger = logging.getLogger(__name__)



class WatcherThread(QThread):
    """Optimized watcher thread"""
    new_file_signal = pyqtSignal(str)
    deleted_file_signal = pyqtSignal(str)

    def __init__(self, folder_path, recursive=True):
        super().__init__()
        self.folder_path = folder_path
        self.recursive = recursive
        self.observer = None

    def run(self):
        self.observer = start_watcher(
            self.folder_path,
            self.handle_new_file,
            self.handle_deleted_file,
            recursive=self.recursive
        )
        self.exec_()

    def handle_new_file(self, file_path):
        self.new_file_signal.emit(file_path)

    def handle_deleted_file(self, file_path):
        self.deleted_file_signal.emit(file_path)

    def stop(self):
        if self.observer:
            stop_watcher(self.observer)
        self.quit()
        self.wait()

class ExplorerWindow(QMainWindow):
    """Optimized main window dengan performance improvements"""
    
    def __init__(self, config_manager):
        super().__init__()
        self.threadpool = QThreadPool()
        self.threadpool.setMaxThreadCount(4)  # Limit concurrent processing
        self.config_manager = config_manager
        self.setWindowTitle("Find My Photo - Funclick Explorer")
        self.setGeometry(100, 100, 1200, 700)
        self.watcher_thread = None

        # Initialize UI
        self._init_ui()
        self.init_ui_additions()  # Add the new UI elements
        self.apply_modern_theme()  # Apply the modern theme
        self._setup_connections()
        
        # Status tracking
        self.embedding_in_progress = 0
        self.processing_files = {}  # Track files being processed
        
        # Navigation
        self.path_history = []
        self.current_path = ""
        self.allowed_paths = self.config_manager.config.get("allowed_paths", [])
        
        # Search mode
        self.is_search_mode = False
        self.search_results = None
        
        # Download worker
        self.download_worker = None
        
        # Auto-load initial path
        self._load_initial_path()

    def _init_ui(self):
        """Initialize UI components"""
        # Top controls
        self.path_display = QLabel()
        self.path_display.setStyleSheet("font-weight: bold; font-size: 14px; padding: 5px;")
        self.path_input = QLineEdit()
        self.path_input.setVisible(False)
        
        self.admin_button = QPushButton("Admin Settings")
        self.back_button = QPushButton("← Back")
        self.back_button.setEnabled(False)

        top_layout = QHBoxLayout()
        top_layout.addWidget(self.back_button)
        top_layout.addWidget(QLabel("📁"))
        top_layout.addWidget(self.path_display)
        top_layout.addStretch()
        
        top_layout.addWidget(self.admin_button)

        # Search input
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍 Search files...")

        # File list dengan improved settings
        self.file_list = DragDropListWidget(self)
        self.file_list.setViewMode(QListView.IconMode)
        self.file_list.setIconSize(QPixmap(100, 100).size())
        self.file_list.setResizeMode(QListView.Adjust)
        self.file_list.setSpacing(10)
        self.file_list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.file_list.setWordWrap(True)
        self.file_list.setGridSize(QPixmap(140, 140).size())

        # Progress bar for processing
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_label = QLabel()

        # Log area
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(150)

        # Layout - store as instance variable for additions
        self.main_layout = QVBoxLayout()
        self.main_layout.addLayout(top_layout)
        self.main_layout.addWidget(self.search_input)
        # Toolbar will be added here by init_ui_additions
        self.main_layout.addWidget(self.progress_bar)
        self.main_layout.addWidget(self.progress_label)
        self.main_layout.addWidget(self.file_list)
        self.main_layout.addWidget(QLabel("Logs:"))
        self.main_layout.addWidget(self.log_text)

        container = QWidget()
        container.setLayout(self.main_layout)
        self.setCentralWidget(container)

        # Status bar
        self.status_bar = self.statusBar()
        self.status_bar.showMessage("Ready")
        self.embedding_label = QLabel()
        self.status_bar.addPermanentWidget(self.embedding_label)

    def init_ui_additions(self):
        """Add new UI elements to existing init_ui method"""
        # Create toolbar for additional features
        toolbar_widget = QWidget()
        toolbar_layout = QHBoxLayout(toolbar_widget)
        toolbar_layout.setContentsMargins(5, 5, 5, 5)
        toolbar_layout.setSpacing(10)
        
        # Face search button with beautiful styling (no box-shadow)
        self.face_search_btn = QPushButton("👤 Search by Face")
        self.face_search_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                                          stop: 0 #5e72e4, stop: 1 #4c63d2);
                color: white;
                border: none;
                border-radius: 8px;
                padding: 12px 24px;
                font-size: 14px;
                font-weight: 600;
                text-align: center;
            }
            QPushButton:hover {
                background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                                          stop: 0 #6b7fe6, stop: 1 #5970d4);
                border: 1px solid #5970d4;
            }
            QPushButton:pressed {
                background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                                          stop: 0 #4c63d2, stop: 1 #3a51c0);
            }
        """)
        self.face_search_btn.setCursor(Qt.PointingHandCursor)
        self.face_search_btn.clicked.connect(self.open_face_search)
        
        # Download button (initially hidden)
        self.download_btn = QPushButton("⬇️ Download Selected")
        self.download_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                                          stop: 0 #28a745, stop: 1 #1e7e34);
                color: white;
                border: none;
                border-radius: 8px;
                padding: 12px 24px;
                font-size: 14px;
                font-weight: 600;
                text-align: center;
            }
            QPushButton:hover {
                background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                                          stop: 0 #34ce57, stop: 1 #28a745);
                border: 1px solid #28a745;
            }
            QPushButton:pressed {
                background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                                          stop: 0 #1e7e34, stop: 1 #155724);
            }
            QPushButton:disabled {
                background-color: #6c757d;
                color: #ffffff;
            }
        """)
        self.download_btn.setCursor(Qt.PointingHandCursor)
        self.download_btn.clicked.connect(self.download_selected_files)
        self.download_btn.setEnabled(False)
        self.download_btn.setVisible(False)  # Hidden by default
        
        toolbar_layout.addWidget(self.face_search_btn)
        toolbar_layout.addWidget(self.download_btn)
        toolbar_layout.addStretch()
        
        # Insert toolbar after search input (at index 2)
        self.main_layout.insertWidget(2, toolbar_widget)

    def _setup_connections(self):
        """Setup signal connections"""
        
        self.admin_button.clicked.connect(self.show_admin_settings)
        self.back_button.clicked.connect(self.go_back)
        self.file_list.itemDoubleClicked.connect(self.open_file)
        self.search_input.textChanged.connect(self.filter_file_list)
        self.path_input.textChanged.connect(self.on_path_changed)

    def _load_initial_path(self):
        """Load initial path if available"""
        if self.allowed_paths:
            initial_path = self.allowed_paths[0]
            self.set_current_path(initial_path)
            self.load_files(initial_path)
            self.start_monitoring(initial_path)

    def update_embedding_status(self):
        """Update embedding status display"""
        if self.embedding_in_progress > 0:
            self.embedding_label.setText(f"🧠 Processing: {self.embedding_in_progress} files")
            self.progress_bar.setVisible(True)
            self.progress_bar.setRange(0, 0)  # Indeterminate progress
        else:
            self.embedding_label.setText("")
            self.progress_bar.setVisible(False)
            # Clear progress label juga ketika semua selesai
            if self.embedding_in_progress == 0:
                self.progress_label.setText("")

    def _clear_progress_if_done(self):
        """Clear progress label jika tidak ada yang sedang diproses"""
        if self.embedding_in_progress == 0:
            self.progress_label.setText("")

    def update_progress_label(self, file_path, status):
        """Update progress label"""
        filename = os.path.basename(file_path)
        self.progress_label.setText(f"{status} {filename}")
        
        # Auto-clear setelah delay untuk status upload
        if "📤" in status:  # Upload status
            QTimer.singleShot(2000, self._clear_progress_if_done)  # Clear setelah 2 detik

    def filter_file_list(self, text):
        """Filter file list based on search text"""
        text = text.lower()
        for i in range(self.file_list.count()):
            item = self.file_list.item(i)
            filename = item.data(Qt.UserRole).lower()
            item.setHidden(text not in filename)

    def set_current_path(self, path):
        """Set current path and update display"""
        self.current_path = path
        self.path_input.setText(path)
        display_name = os.path.basename(path) if path else ""
        if not display_name:
            display_name = path
        self.path_display.setText(display_name)

    def smart_truncate_filename(self, filename, max_chars=16):
        """Smart truncate filename preserving extension"""
        if len(filename) <= max_chars:
            return filename
        
        if '.' in filename:
            name_part, ext = os.path.splitext(filename)
            available_chars = max_chars - len(ext) - 3
            if available_chars > 3:
                return name_part[:available_chars] + "..." + ext
            else:
                return filename[:max_chars-3] + "..."
        else:
            return filename[:max_chars-3] + "..."

    def log_with_timestamp(self, message):
        """Add timestamped message to log"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.append(f"[{timestamp}] {message}")
        
        # Auto-scroll to bottom
        scrollbar = self.log_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def browse_folder(self):
        """Browse and select folder"""
        folder = QFileDialog.getExistingDirectory(self, "Select Folder")
        if folder:
            if not self.config_manager.is_path_allowed(folder):
                QMessageBox.warning(self, "Access Denied", 
                                  "Path ini tidak diizinkan!\nSilakan hubungi admin.")
                return
            
            if self.current_path and self.current_path != folder:
                self.path_history.append(self.current_path)
                self.back_button.setEnabled(True)
            
            self.set_current_path(folder)
            self.load_files(folder)

    def go_back(self):
        """Navigate back to previous folder"""
        if self.path_history:
            previous_path = self.path_history.pop()
            self.set_current_path(previous_path)
            self.load_files(previous_path)
            self.back_button.setEnabled(len(self.path_history) > 0)
            self.log_with_timestamp(f"⬅️ Back to: {os.path.basename(previous_path)}")
            self.on_path_changed(previous_path)

    def load_files(self, folder_path):
        """Load files from folder with optimization"""
        if not self.config_manager.is_path_allowed(folder_path):
            self.log_with_timestamp(f"❌ Access denied: {folder_path}")
            return
        
        self.file_list.clear()
        if not os.path.exists(folder_path):
            return
            
        try:
            image_exts = ['.png', '.jpg', '.jpeg']
            items = os.listdir(folder_path)
            
            # Separate and sort items
            folders = sorted([item for item in items 
                            if os.path.isdir(os.path.join(folder_path, item))])
            image_files = sorted([item for item in items 
                                if os.path.splitext(item)[1].lower() in image_exts])
            
            # Add folders first
            for folder_name in folders:
                self._add_folder_item(folder_name, folder_path)
            
            # Add image files
            for filename in image_files:
                self._add_image_item(filename, folder_path)
                
        except Exception as e:
            self.log_with_timestamp(f"❌ Error loading folder: {str(e)}")

    def _add_folder_item(self, folder_name, folder_path):
        """Add folder item to list"""
        item = QListWidgetItem()
        display_name = self.smart_truncate_filename(folder_name, max_chars=16)
        item.setText(display_name)
        item.setData(Qt.UserRole, folder_name)
        item.setData(Qt.UserRole + 1, "folder")
        item.setIcon(self.style().standardIcon(self.style().SP_DirIcon))
        
        full_path = os.path.join(folder_path, folder_name)
        item.setToolTip(f"Folder: {folder_name}\nPath: {full_path}")
        item.setTextAlignment(Qt.AlignHCenter | Qt.AlignBottom)
        
        self.file_list.addItem(item)

    def _add_image_item(self, filename, folder_path):
        """Add image item to list"""
        item = QListWidgetItem()
        display_name = self.smart_truncate_filename(filename, max_chars=16)
        item.setText(display_name)
        item.setData(Qt.UserRole, filename)
        item.setData(Qt.UserRole + 1, "image")
        
        full_path = os.path.join(folder_path, filename)
        
        # Load thumbnail asynchronously in production
        pixmap = QPixmap(full_path)
        if not pixmap.isNull():
            scaled_pixmap = pixmap.scaled(100, 100, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            item.setIcon(QIcon(scaled_pixmap))
        else:
            item.setIcon(self.style().standardIcon(self.style().SP_FileIcon))
        
        # File info tooltip
        try:
            file_info = os.stat(full_path)
            size_mb = file_info.st_size / (1024 * 1024)
            item.setToolTip(f"Image: {filename}\nSize: {size_mb:.2f} MB")
        except:
            item.setToolTip(f"Image: {filename}")
        
        item.setTextAlignment(Qt.AlignHCenter | Qt.AlignBottom)
        self.file_list.addItem(item)

    def open_file(self, item):
        """Open file or navigate to folder with preview functionality"""
        if self.is_search_mode:
            # Handle search result items
            file_path = item.data(Qt.UserRole + 2)  # Full path stored in search mode
            if file_path and os.path.exists(file_path):
                self.show_image_preview(file_path)
            return
            
        # Normal mode handling
        item_name = self.file_list.get_actual_filename(item)
        item_path = os.path.join(self.current_path, item_name)
        item_type = item.data(Qt.UserRole + 1)
        
        if item_type == "folder":
            if self.config_manager.is_path_allowed(item_path):
                if self.current_path != item_path and os.path.exists(self.current_path):
                    self.path_history.append(self.current_path)
                    self.back_button.setEnabled(True)
                
                self.set_current_path(item_path)
                self.load_files(item_path)
                self.on_path_changed(item_path)
            else:
                QMessageBox.warning(self, "Access Denied", 
                                  f"Folder '{item_name}' tidak dapat diakses!")
        else:
            # Show image preview instead of opening with system
            self.show_image_preview(item_path)

    def show_image_preview(self, image_path):
        """Show image in preview dialog"""
        try:
            preview_dialog = ImagePreviewDialog(image_path, self)
            preview_dialog.exec_()
            self.log_with_timestamp(f"👁️ Previewed: {os.path.basename(image_path)}")
        except Exception as e:
            self.log_with_timestamp(f"❌ Error previewing image: {str(e)}")
            # Fallback to system viewer
            try:
                if sys.platform == "win32":
                    os.startfile(image_path)
                elif sys.platform == "darwin":
                    os.system(f"open '{image_path}'")
                else:
                    os.system(f"xdg-open '{image_path}'")
            except:
                pass

    def on_path_changed(self, new_path):
        """Handle path change"""
        if new_path and os.path.isdir(new_path) and self.config_manager.is_path_allowed(new_path):
            if self.watcher_thread:
                self.stop_monitoring()
            self.start_monitoring(new_path)

    def start_monitoring(self, folder=None):
        """Start folder monitoring"""
        if folder is None:
            folder = self.current_path
            
        if not os.path.isdir(folder) or not self.config_manager.is_path_allowed(folder):
            return
        
        if (self.watcher_thread and 
            hasattr(self.watcher_thread, 'folder_path') and 
            self.watcher_thread.folder_path == folder):
            return
        
        self.watcher_thread = WatcherThread(folder, recursive=True)
        self.watcher_thread.new_file_signal.connect(self.on_new_file_detected)
        self.watcher_thread.deleted_file_signal.connect(self.on_file_deleted)
        self.watcher_thread.start()
        
        self.status_bar.showMessage(f"🔄 Monitoring: {os.path.basename(folder)}")

    def stop_monitoring(self):
        """Stop monitoring"""
        if self.watcher_thread:
            self.watcher_thread.stop()
            self.watcher_thread = None
            self.status_bar.showMessage("Ready")

    def on_new_file_detected(self, file_path):
        """Handle new file detection"""
        filename = os.path.basename(file_path)
        
        image_exts = ['.png', '.jpg', '.jpeg']
        if os.path.splitext(filename)[1].lower() not in image_exts:
            return
            
        self.log_with_timestamp(f"🆕 New image: {filename}")
        
        # Add to file list if in current folder
        file_dir = os.path.dirname(file_path)
        if file_dir == self.current_path:
            self._add_image_item(filename, file_dir)

    def on_file_deleted(self, file_path):
        """Handle file deletion"""
        filename = os.path.basename(file_path)
        relative_path = os.path.relpath(file_path, self.current_path)
        self.log_with_timestamp(f"🗑️ Deleted: {relative_path}")
        
        # Remove from current view if applicable
        file_dir = os.path.dirname(file_path)
        if file_dir == self.current_path:
            for i in range(self.file_list.count()):
                item = self.file_list.item(i)
                if item.data(Qt.UserRole) == filename:
                    self.file_list.takeItem(i)
                    break

    def show_admin_settings(self):
        """Show admin settings"""
        login_dialog = AdminLoginDialog(self.config_manager, self)
        if login_dialog.exec_() == QDialog.Accepted:
            settings_dialog = AdminSettingsDialog(self.config_manager, self)
            settings_dialog.exec_()
        else:
            QMessageBox.information(self, "Info", "Login diperlukan untuk admin settings.")

    def open_face_search(self):
        """Open face search dialog"""
        try:
            # Use the shared detector
            face_detector = get_shared_detector()
            
            # Create and show face search dialog
            search_dialog = FaceSearchDialog(
                face_detector=face_detector,
                resnet=resnet,
                device=device,
                api_base=API_BASE,
                parent=self
            )
            
            # Connect to handle search results
            search_dialog.search_completed.connect(self.handle_face_search_results)
            
            self.log_with_timestamp("👤 Opening face search...")
            search_dialog.show()  # Use show() instead of exec_() for non-modal
            
        except Exception as e:
            self.log_with_timestamp(f"❌ Error opening face search: {str(e)}")
            QMessageBox.warning(self, "Error", f"Failed to open face search:\n{str(e)}")

    def get_selected_search_results(self):
        """Get all selected items from search results"""
        selected_items = []
        
        if hasattr(self, 'search_tab_widget') and self.search_tab_widget.isVisible():
            # Multiple outlets - check all tabs
            for i in range(self.search_tab_widget.count()):
                tab_list = self.search_tab_widget.widget(i)
                if tab_list:
                    selected_items.extend(tab_list.selectedItems())
        else:
            # Single outlet - check main file list
            selected_items = self.file_list.selectedItems()
        
        return selected_items

    def get_selected_search_results_count(self):
        """Get count of selected search result items"""
        return len(self.get_selected_search_results())

    def update_download_button_state(self):
        """Update download button state based on selection"""
        if not self.is_search_mode:
            return
            
        selected_count = self.get_selected_search_results_count()
        if hasattr(self, 'download_btn'):
            self.download_btn.setEnabled(selected_count > 0)
            if selected_count > 0:
                self.download_btn.setText(f"⬇️ Download Selected ({selected_count})")
            else:
                self.download_btn.setText("⬇️ Download Selected")

    def connect_selection_handlers(self, list_widget):
        """Connect selection change events for list widgets"""
        list_widget.itemSelectionChanged.connect(self.update_download_button_state)

    def download_selected_files(self):
        """Download selected search result files"""
        selected_items = self.get_selected_search_results()
        
        if not selected_items:
            QMessageBox.information(self, "Download", "No files selected.")
            return
        
        # Choose download location
        if len(selected_items) == 1:
            # Single file - let user choose filename
            filename = selected_items[0].data(Qt.UserRole)  # Original filename
            save_path, _ = QFileDialog.getSaveFileName(
                self, "Save File", filename, 
                "All Files (*)"
            )
        else:
            # Multiple files - choose folder (no ZIP)
            save_path = QFileDialog.getExistingDirectory(
                self, "Select Download Folder", 
                os.path.expanduser("~/Downloads")
            )
        
        if not save_path:
            return
        
        # Start download in separate thread to avoid UI freeze
        self.start_download_thread(selected_items, save_path)

    def start_download_thread(self, selected_items, save_path):
        """Start download in background thread with progress dialog"""
        self.download_worker = DownloadWorker(selected_items, save_path)
        
        # Create progress dialog
        self.progress_dialog = QProgressDialog("Preparing download...", "Cancel", 0, 100, self)
        self.progress_dialog.setWindowModality(Qt.WindowModal)
        self.progress_dialog.setMinimumDuration(0)
        self.progress_dialog.setAutoClose(False)
        self.progress_dialog.setAutoReset(False)
        
        # Connect signals
        self.download_worker.progress.connect(self.update_download_progress)
        self.download_worker.finished.connect(self.download_finished)
        self.progress_dialog.canceled.connect(self.cancel_download)
        
        self.download_worker.start()
        self.log_with_timestamp(f"📥 Starting download of {len(selected_items)} file(s)...")

    def update_download_progress(self, value, status):
        """Update download progress"""
        self.progress_dialog.setValue(value)
        self.progress_dialog.setLabelText(status)

    def cancel_download(self):
        """Cancel ongoing download"""
        if self.download_worker:
            self.download_worker.cancel()
            self.download_worker.terminate()
            self.download_worker.wait(3000)  # Wait max 3 seconds
            

    def download_finished(self, success, message):
        """Handle download completion"""
        self.progress_dialog.close()
        
        if success:
            QMessageBox.information(self, "Download Complete", message)
            self.log_with_timestamp(f"✅ {message}")
        else:
            QMessageBox.warning(self, "Download Failed", message)
            self.log_with_timestamp(f"❌ {message}")
        
        # Clean up
        self.download_worker = None

    def handle_face_search_results(self, results):
        """Handle results from face search with outlet grouping"""
        print(f"Explorer received {len(results)} results")  # Debug
        
        if not results:
            self.log_with_timestamp("❌ Face search: No results found")
            QMessageBox.information(self, "Face Search", "No matching faces found.")
            self.file_list.clear()
            return
        
        self.log_with_timestamp(f"✅ Face search completed: {len(results)} results found")
        
        # Group results by outlet FIRST
        outlet_groups = {}
        for result in results:
            outlet_name = result.get('outlet_name', 'Unknown')
            print(f"Result outlet_name: {outlet_name}")  # Debug
            if outlet_name not in outlet_groups:
                outlet_groups[outlet_name] = []
            outlet_groups[outlet_name].append(result)
        
        print(f"Outlet groups: {list(outlet_groups.keys())}")  # Debug
        print(f"Number of outlets: {len(outlet_groups)}")  # Debug
        
        # Clear current file list
        self.file_list.clear()
        
        # Update path display to show search mode with outlet info
        if len(outlet_groups) == 1:
            outlet_name = list(outlet_groups.keys())[0]
            result_count = len(list(outlet_groups.values())[0])
            self.path_display.setText(f"🔍 Face Search Results - {outlet_name} ({result_count})")
        else:
            total_results = sum(len(group) for group in outlet_groups.values())
            self.path_display.setText(f"🔍 Face Search Results ({total_results} from {len(outlet_groups)} outlets)")
        self.path_display.setStyleSheet("font-weight: bold; font-size: 14px; padding: 5px; color: #5e72e4;")
        
        # Add "Back to Browse" button if not already visible
        if not hasattr(self, 'back_to_browse_btn'):
            self.back_to_browse_btn = QPushButton("← Back to Browse")
            self.back_to_browse_btn.setStyleSheet("""
                QPushButton {
                    background-color: #5e72e4;
                    color: white;
                    border: none;
                    border-radius: 6px;
                    padding: 8px 16px;
                    font-size: 14px;
                    font-weight: 500;
                }
                QPushButton:hover {
                    background-color: #4c63d2;
                }
            """)
            self.back_to_browse_btn.clicked.connect(self.exit_search_mode)
            # Get the top layout properly
            main_layout = self.centralWidget().layout()
            if main_layout and main_layout.count() > 0:
                top_item = main_layout.itemAt(0)
                if top_item and top_item.layout():
                    top_layout = top_item.layout()
                    top_layout.insertWidget(1, self.back_to_browse_btn)
        
        self.back_to_browse_btn.setVisible(True)
        self.back_button.setEnabled(False)  # Disable regular back button in search mode
        
        # Show download button in search mode
        self.download_btn.setVisible(True)
        self.download_btn.setEnabled(False)  # Will be enabled when items are selected
        
        # Store search mode state
        self.is_search_mode = True
        self.search_results = results
        
        # Replace file_list with tab widget if more than one outlet
        if len(outlet_groups) > 1:
            # Hide normal file list
            self.file_list.setVisible(False)
            
            # Create tab widget if not exists
            if not hasattr(self, 'search_tab_widget'):
                self.search_tab_widget = QTabWidget()
                self.search_tab_widget.setStyleSheet("""
                    QTabWidget::pane {
                        background-color: white;
                        border: 1px solid #e0e0e0;
                        border-radius: 8px;
                    }
                    QTabBar::tab {
                        background-color: #f8f9fa;
                        color: #333;
                        padding: 8px 16px;
                        margin-right: 2px;
                        border-top-left-radius: 6px;
                        border-top-right-radius: 6px;
                    }
                    QTabBar::tab:selected {
                        background-color: #5e72e4;
                        color: white;
                    }
                    QTabBar::tab:hover {
                        background-color: #e9ecef;
                    }
                """)
                # Insert where file_list was
                self.main_layout.insertWidget(5, self.search_tab_widget)
            
            self.search_tab_widget.clear()
            self.search_tab_widget.setVisible(True)
            
            # Create tabs for each outlet
            for outlet_name, outlet_results in sorted(outlet_groups.items()):
                # Create list widget for this outlet
                outlet_list = QListWidget()
                outlet_list.setViewMode(QListView.IconMode)
                outlet_list.setIconSize(QPixmap(100, 100).size())
                outlet_list.setResizeMode(QListView.Adjust)
                outlet_list.setSpacing(10)
                outlet_list.setSelectionMode(QAbstractItemView.ExtendedSelection)
                outlet_list.setWordWrap(True)
                outlet_list.setGridSize(QPixmap(140, 140).size())
                
                
                # Copy style from main file list
                outlet_list.setStyleSheet(self.file_list.styleSheet())
                
                # Add items to this outlet's list
                self._populate_search_results(outlet_list, outlet_results)
                
                # Connect double-click and selection change
                outlet_list.itemDoubleClicked.connect(self._open_search_result)
                self.connect_selection_handlers(outlet_list)
                
                # Add tab with count
                tab_label = f"{outlet_name} ({len(outlet_results)})"
                self.search_tab_widget.addTab(outlet_list, tab_label)
            
            # Update status
            total_results = sum(len(group) for group in outlet_groups.values())
            self.status_bar.showMessage(f"Showing {total_results} results from {len(outlet_groups)} outlets")
            
        else:
            # Single outlet or no outlet info - use normal file list
            if hasattr(self, 'search_tab_widget'):
                self.search_tab_widget.setVisible(False)
            
            self.file_list.setVisible(True)
            self._populate_search_results(self.file_list, results)
            # double click to preview image
            self.file_list.itemDoubleClicked.connect(self._open_search_result)
            # Connect selection handler for download button
            self.connect_selection_handlers(self.file_list)

            # Update status
            outlet_name = list(outlet_groups.keys())[0] if outlet_groups else "Unknown"
            self.status_bar.showMessage(f"Showing {len(results)} results from {outlet_name}")

    def _populate_search_results(self, list_widget, results):
        """Populate a list widget with search results"""
        added_count = 0
        not_found_count = 0
        
        for i, result in enumerate(results):
            file_path = result.get('file_path', '')
            original_path = result.get('original_path', '')  # URL for original
            thumbnail_path = result.get('thumbnail_path', '')  # URL for thumbnail
            similarity = result.get('similarity', 0)
            outlet_name = result.get('outlet_name', 'Unknown')
            filename = result.get('filename', os.path.basename(file_path) if file_path else 'Unknown')
            
            # Skip if no useful data
            if not (file_path or original_path or thumbnail_path):
                continue
            
            # Create list item
            item = QListWidgetItem()
            
            # Format display with similarity score and outlet
            display_name = self.smart_truncate_filename(filename, max_chars=14)
            similarity_percent = similarity * 100
            item.setText(f"{display_name}\n{similarity_percent:.0f}% match")
            
            # Store full data including URLs
            item.setData(Qt.UserRole, filename)
            item.setData(Qt.UserRole + 1, "search_result")
            item.setData(Qt.UserRole + 2, original_path or file_path)  # Store URL or path for preview
            item.setData(Qt.UserRole + 3, similarity)  # Store similarity score
            item.setData(Qt.UserRole + 4, outlet_name)  # Store outlet name
            
            # Load thumbnail from URL
            thumbnail_loaded = False
            
            if thumbnail_path:
                try:
                    # Download thumbnail from URL
                    response = requests.get(thumbnail_path, timeout=5)                    

                    if response.status_code == 200:
                        # Convert bytes to QPixmap
                        pixmap = QPixmap()
                        pixmap.loadFromData(response.content)
                        if not pixmap.isNull():
                            scaled_pixmap = pixmap.scaled(100, 100, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                            
                            # Add similarity indicator as overlay
                            painter = QPainter(scaled_pixmap)
                            painter.setRenderHint(QPainter.Antialiasing)
                            
                            # Draw similarity badge
                            badge_color = QColor(94, 114, 228, 200)  # Semi-transparent blue
                            painter.setBrush(badge_color)
                            painter.setPen(Qt.NoPen)
                            painter.drawEllipse(scaled_pixmap.width() - 30, 5, 25, 25)
                            
                            # Draw percentage text
                            painter.setPen(Qt.white)
                            font = QFont()
                            font.setPointSize(9)
                            font.setBold(True)
                            painter.setFont(font)
                            painter.drawText(scaled_pixmap.width() - 30, 5, 25, 25, 
                                           Qt.AlignCenter, f"{similarity_percent:.0f}")
                            painter.end()
                            
                            item.setIcon(QIcon(scaled_pixmap))
                            thumbnail_loaded = True
                except Exception as e:
                    print(f"Error loading thumbnail from URL {thumbnail_path}: {e}")
            else:
                print(f"No thumbnail URL provided for {filename}, using default icon")
            
            # If still no thumbnail, use default icon
            if not thumbnail_loaded:
                item.setIcon(self.style().standardIcon(self.style().SP_FileIcon))
            
            # Tooltip with full info including outlet
            item.setToolTip(f"File: {filename}\nOutlet: {outlet_name}\nSimilarity: {similarity_percent:.1f}%")
            item.setTextAlignment(Qt.AlignHCenter | Qt.AlignBottom)
            
            list_widget.addItem(item)
            added_count += 1
        
        return added_count, not_found_count

    def _open_search_result(self, item):
        """Open search result item"""
        # Get URL or path from item data
        url_or_path = item.data(Qt.UserRole + 2)
        print(f"Opening search result: {url_or_path}")  # Debug
        
        if url_or_path:
            # Check if it's a URL
            if url_or_path.startswith(('http://', 'https://')):
                # For URLs, we need to download and show in preview
                self.show_url_image_preview(url_or_path)
            elif os.path.exists(url_or_path):
                # For local files, use existing preview
                self.show_image_preview(url_or_path)
    
    def show_url_image_preview(self, image_url):
        """Download and show image from URL in preview dialog"""
        try:
            self.log_with_timestamp(f"📥 Downloading image for preview...")
            
            # Download image
            response = requests.get(image_url, timeout=10)
            if response.status_code == 200:
                # Save to temporary file
                import tempfile
                with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as tmp_file:
                    tmp_file.write(response.content)
                    temp_path = tmp_file.name
                
                # Show in preview dialog
                preview_dialog = ImagePreviewDialog(temp_path, self)
                preview_dialog.exec_()
                
                # Clean up temp file
                try:
                    os.unlink(temp_path)
                except:
                    pass
                
                self.log_with_timestamp(f"👁️ Previewed image from URL")
            else:
                self.log_with_timestamp(f"❌ Failed to download image: {response.status_code}")
                QMessageBox.warning(self, "Error", f"Failed to download image for preview")
                
        except Exception as e:
            self.log_with_timestamp(f"❌ Error previewing image from URL: {str(e)}")
            QMessageBox.warning(self, "Error", f"Failed to preview image:\n{str(e)}")
    
    def exit_search_mode(self):
        """Exit search mode and return to normal browsing"""
        self.is_search_mode = False
        self.search_results = None
        
        # Hide search-specific UI
        if hasattr(self, 'back_to_browse_btn'):
            self.back_to_browse_btn.setVisible(False)
        
        if hasattr(self, 'search_tab_widget'):
            self.search_tab_widget.setVisible(False)
        
        # Hide download button
        self.download_btn.setVisible(False)
        
        # Show normal file list
        self.file_list.setVisible(True)
        
        # Re-enable normal back button
        self.back_button.setEnabled(len(self.path_history) > 0)
        
        # Restore normal path display style
        self.path_display.setStyleSheet("font-weight: bold; font-size: 14px; padding: 5px;")
        
        # Return to last browsed folder
        if self.current_path:
            self.set_current_path(self.current_path)
            self.load_files(self.current_path)
        else:
            # Or go to first allowed path
            if self.allowed_paths:
                initial_path = self.allowed_paths[0]
                self.set_current_path(initial_path)
                self.load_files(initial_path)
        
        self.log_with_timestamp("🔙 Exited face search mode")

    def apply_modern_theme(self):
        """Apply modern light theme to the application"""
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f5f5f5;
            }
            
            QLabel {
                color: #333333;
            }
            
            QLineEdit {
                background-color: white;
                border: 1px solid #ddd;
                border-radius: 6px;
                padding: 8px;
                color: #333333;
                font-size: 14px;
            }
            
            QLineEdit:focus {
                border-color: #5e72e4;
                outline: none;
            }
            
            QPushButton {
                background-color: white;
                color: #333333;
                border: 1px solid #ddd;
                border-radius: 6px;
                padding: 8px 16px;
                font-size: 14px;
            }
            
            QPushButton:hover {
                background-color: #f8f9fa;
                border-color: #5e72e4;
            }
            
            QPushButton:pressed {
                background-color: #e9ecef;
            }
            
            QListWidget {
                background-color: white;
                border: 1px solid #e0e0e0;
                border-radius: 8px;
                padding: 10px;
                outline: none;
            }
            
            QListWidget::item {
                background-color: #f8f9fa;
                border-radius: 6px;
                padding: 5px;
                margin: 2px;
                color: #333333;
            }
            
            QListWidget::item:hover {
                background-color: #e9ecef;
                border: 1px solid #5e72e4;
            }
            
            QListWidget::item:selected {
                background-color: #5e72e4;
                color: white;
            }
            
            QTextEdit {
                background-color: white;
                border: 1px solid #ddd;
                border-radius: 6px;
                padding: 8px;
                color: #333333;
                font-family: 'Consolas', 'Monaco', monospace;
                font-size: 12px;
            }
            
            QProgressBar {
                border: 1px solid #ddd;
                border-radius: 5px;
                text-align: center;
                background-color: #f0f0f0;
                color: #333333;
                height: 20px;
            }
            
            QProgressBar::chunk {
                background-color: #5e72e4;
                border-radius: 4px;
            }
            
            QStatusBar {
                background-color: #f5f5f5;
                color: #666666;
                border-top: 1px solid #e0e0e0;
            }
        """)

    def resolve_file_path(self, path):
        """Resolve database path to actual file system path"""
        # Check if path exists as-is
        if os.path.exists(path):
            return path
        
        # Common path replacements (sesuaikan dengan setup Anda)
        replacements = [
            ("/server/photos/", "D:/Foto/"),
            ("/mnt/storage/", "D:/Foto/"),
            ("\\server\\photos\\", "D:\\Foto\\"),
            ("/var/www/uploads/", "D:/Foto/"),
        ]
        
        for old, new in replacements:
            test_path = path.replace(old, new)
            if os.path.exists(test_path):
                return test_path
        
        # Try in allowed paths
        filename = os.path.basename(path)
        for allowed_path in self.allowed_paths:
            # Direct join
            test_path = os.path.join(allowed_path, filename)
            if os.path.exists(test_path):
                return test_path
            
            # Search subdirectories (limited depth for performance)
            for root, dirs, files in os.walk(allowed_path):
                if filename in files:
                    return os.path.join(root, filename)
                # Limit depth
                depth = root[len(allowed_path):].count(os.sep)
                if depth > 3:  # Max 3 levels deep
                    dirs[:] = []  # Don't recurse deeper
        
        return None
    
    def closeEvent(self, event):
        """Handle application close"""
        if self.watcher_thread:
            self.stop_monitoring()
        
        # Cancel any ongoing download
        if self.download_worker:
            self.download_worker.cancel()
            self.download_worker.terminate()
            self.download_worker.wait(3000)
        
        # Wait for running workers to complete
        self.threadpool.waitForDone(3000)  # 3 second timeout
        event.accept()