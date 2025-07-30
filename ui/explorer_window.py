import os
import sys
import logging
import requests
from datetime import datetime

from PyQt5.QtCore import (
    Qt, QThreadPool, QMutex, QMutexLocker, QThread, pyqtSignal, QTimer  # ✅ ADD QTimer
)
from PyQt5.QtGui import (
    QPixmap, QIcon, QDrag, QClipboard, QPainter, QColor, QFont
)
from PyQt5.QtWidgets import (
    QMainWindow, QListView, QFileDialog, QTextEdit, QPushButton, QVBoxLayout, QWidget, QHBoxLayout,
    QLabel, QLineEdit, QListWidget, QListWidgetItem, QMessageBox, QAbstractItemView, QTabWidget, QProgressBar,
    QProgressDialog
)

from utils.features import DragDropListWidget
from ui.face_search_dialog import FaceSearchDialog
from ui.navigation_preview import NavigationPreviewDialog
from utils.image_processing import get_shared_detector
from core.device_setup import FaceEncoder


logger = logging.getLogger(__name__)


class DownloadWorker(QThread):
    """Worker thread for downloading files"""
    
    # Define required signals
    progress_updated = pyqtSignal(int, int)  # completed, total
    file_completed = pyqtSignal(str, str)   # filename, file_path
    download_completed = pyqtSignal(str, int)  # download_dir, total_files
    error_occurred = pyqtSignal(str)        # error_message
    
    def __init__(self, download_tasks, download_dir):
        super().__init__()
        self.download_tasks = download_tasks
        self.download_dir = download_dir
        self.cancelled = False
        
    def cancel(self):
        """Cancel the download"""
        self.cancelled = True
        
    def run(self):
        """Main download loop"""
        try:
            os.makedirs(self.download_dir, exist_ok=True)
            completed = 0
            
            for i, task in enumerate(self.download_tasks):
                if self.cancelled:
                    break
                    
                try:
                    url = task['url']
                    filename = task['filename']
                    outlet_name = task['outlet_name']
                    
                    # Generate unique filename - NO OUTLET SUBFOLDER
                    file_extension = os.path.splitext(filename)[1] or '.jpg'
                    base_name = os.path.splitext(filename)[0]
                    
                    # Include outlet name in filename for identification
                    safe_outlet_name = "".join(c for c in outlet_name if c.isalnum() or c in (' ', '-', '_')).strip()
                    final_filename = f"{safe_outlet_name}_{base_name}{file_extension}"
                    file_path = os.path.join(self.download_dir, final_filename)
                    
                    # Handle duplicate filenames
                    counter = 1
                    while os.path.exists(file_path):
                        final_filename = f"{safe_outlet_name}_{base_name}_{counter}{file_extension}"
                        file_path = os.path.join(self.download_dir, final_filename)
                        counter += 1
                    
                    # Download file
                    response = requests.get(url, stream=True, timeout=30)
                    response.raise_for_status()
                    
                    with open(file_path, 'wb') as f:
                        for chunk in response.iter_content(chunk_size=8192):
                            if self.cancelled:
                                break
                            if chunk:
                                f.write(chunk)
                    
                    if not self.cancelled:
                        completed += 1
                        self.file_completed.emit(filename, file_path)
                        self.progress_updated.emit(completed, len(self.download_tasks))
                        
                except Exception as e:
                    self.error_occurred.emit(f"Failed to download {task['filename']}: {str(e)}")
                    continue
            
            if not self.cancelled:
                self.download_completed.emit(self.download_dir, completed)
                
        except Exception as e:
            self.error_occurred.emit(f"Download error: {str(e)}")


class OptimizedSearchResultsWidget:
    """Widget optimizer untuk search results dengan smart thumbnail loading"""
    
    def __init__(self, list_widget, parent_window):
        self.list_widget = list_widget
        self.parent = parent_window
        self.thumbnail_cache = {}
        self.loading_queue = []
        self.currently_loading = set()
        self.max_concurrent = 3  # Max 3 downloads bersamaan
        
        # Start thumbnail loader thread
        self.thumbnail_loader = ThumbnailLoaderThread()
        self.thumbnail_loader.thumbnail_ready.connect(self.on_thumbnail_ready)
        self.thumbnail_loader.start()
    
    def populate_results_optimized(self, results):
        """Populate results dengan optimized thumbnail loading"""
        print(f"🚀 Optimized loading: {len(results)} items")
        
        for i, result in enumerate(results):
            # Extract data
            file_path = result.get('file_path', '')
            original_path = result.get('original_path', '')
            thumbnail_path = result.get('thumbnail_path', '')
            similarity = result.get('similarity', 0)
            outlet_name = result.get('outlet_name', 'Unknown')
            filename = result.get('filename', os.path.basename(file_path) if file_path else 'Unknown')
            
            if not (file_path or original_path or thumbnail_path):
                continue
            
            # Create item dengan placeholder
            item = QListWidgetItem()
            display_name = self.parent.smart_truncate_filename(filename, max_chars=14)
            similarity_percent = similarity * 100
            item.setText(f"{display_name}\n{similarity_percent:.0f}% match")
            
            # Store data
            item.setData(Qt.UserRole, filename)
            item.setData(Qt.UserRole + 1, "search_result")
            item.setData(Qt.UserRole + 2, original_path or file_path)
            item.setData(Qt.UserRole + 3, similarity)
            item.setData(Qt.UserRole + 4, outlet_name)
            
            # Set placeholder icon
            placeholder_icon = self.parent.style().standardIcon(self.parent.style().SP_FileIcon)
            item.setIcon(placeholder_icon)
            
            item.setToolTip(f"File: {filename}\nOutlet: {outlet_name}\nSimilarity: {similarity_percent:.1f}%")
            item.setTextAlignment(Qt.AlignHCenter | Qt.AlignBottom)
            
            self.list_widget.addItem(item)
            
            # Queue thumbnail loading
            if thumbnail_path:
                self.queue_thumbnail_load(thumbnail_path, item, similarity_percent)
        
        print(f"✅ Added {self.list_widget.count()} items to list widget")  # ✅ DEBUG
        
        # Start loading thumbnails
        self.process_thumbnail_queue()
    
    def queue_thumbnail_load(self, thumbnail_url, item, similarity_percent):
        """Queue thumbnail untuk loading"""
        if thumbnail_url not in self.thumbnail_cache and thumbnail_url not in self.currently_loading:
            self.loading_queue.append({
                'url': thumbnail_url,
                'item': item,
                'similarity': similarity_percent
            })
    
    def process_thumbnail_queue(self):
        """Process thumbnail loading queue"""
        while len(self.currently_loading) < self.max_concurrent and self.loading_queue:
            task = self.loading_queue.pop(0)
            url = task['url']
            
            if url in self.thumbnail_cache:
                # Use cached thumbnail
                self.apply_cached_thumbnail(task['item'], url, task['similarity'])
            else:
                # Start download
                self.currently_loading.add(url)
                self.thumbnail_loader.add_task(url, task['item'], task['similarity'])
    
    def apply_cached_thumbnail(self, item, url, similarity_percent):
        """Apply cached thumbnail ke item"""
        if url in self.thumbnail_cache:
            pixmap = self.thumbnail_cache[url]
            self.apply_thumbnail_with_overlay(item, pixmap, similarity_percent)
    
    def on_thumbnail_ready(self, url, pixmap, item, similarity_percent):
        """Handle thumbnail ready"""
        self.currently_loading.discard(url)
        
        if not pixmap.isNull():
            # Cache the result
            self.thumbnail_cache[url] = pixmap
            # Apply to item
            self.apply_thumbnail_with_overlay(item, pixmap, similarity_percent)
            print(f"✅ Thumbnail loaded: {os.path.basename(url)}")
        else:
            print(f"❌ Thumbnail failed: {os.path.basename(url)}")
        
        # Process next in queue
        QTimer.singleShot(100, self.process_thumbnail_queue)
    
    def apply_thumbnail_with_overlay(self, item, pixmap, similarity_percent):
        import sip
        """Apply thumbnail dengan similarity overlay"""
        try:
            # Skip jika item sudah None atau dihapus
            if item is None or sip.isdeleted(item):
                print("⚠️ Item sudah dihapus, skip setIcon()")
                return

            # Scale to standard size
            scaled_pixmap = pixmap.scaled(100, 100, Qt.KeepAspectRatio, Qt.SmoothTransformation)

            # Add overlay
            painter = QPainter(scaled_pixmap)
            painter.setRenderHint(QPainter.Antialiasing)

            # Draw similarity badge
            badge_color = QColor(94, 114, 228, 200)
            painter.setBrush(badge_color)
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(scaled_pixmap.width() - 30, 5, 25, 25)

            # Draw percentage
            painter.setPen(Qt.white)
            font = QFont()
            font.setPointSize(9)
            font.setBold(True)
            painter.setFont(font)
            painter.drawText(scaled_pixmap.width() - 30, 5, 25, 25,
                            Qt.AlignCenter, f"{similarity_percent:.0f}")
            painter.end()

            item.setIcon(QIcon(scaled_pixmap))

        except RuntimeError as e:
            print(f"❌ RuntimeError: {e}")
        except Exception as e:
            print(f"❌ Error applying overlay: {e}")
            try:
                if item and not sip.isdeleted(item):
                    item.setIcon(QIcon(pixmap))
            except:
                pass



class ThumbnailLoaderThread(QThread):
    """Background thread untuk loading thumbnails"""
    
    thumbnail_ready = pyqtSignal(str, QPixmap, object, float)  # url, pixmap, item, similarity
    
    def __init__(self):
        super().__init__()
        self.task_queue = []
        self.running = True
        self.mutex = QMutex()
    
    def add_task(self, url, item, similarity):
        """Add loading task"""
        with QMutexLocker(self.mutex):
            self.task_queue.append({
                'url': url,
                'item': item,
                'similarity': similarity
            })
    
    def run(self):
        """Main thread loop"""
        while self.running:
            task = None
            
            # Get next task
            with QMutexLocker(self.mutex):
                if self.task_queue:
                    task = self.task_queue.pop(0)
            
            if task:
                self.load_thumbnail(task['url'], task['item'], task['similarity'])
            else:
                self.msleep(100)  # Sleep 100ms if no tasks
    
    def load_thumbnail(self, url, item, similarity):
        """Load single thumbnail"""
        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                pixmap = QPixmap()
                if pixmap.loadFromData(response.content):
                    self.thumbnail_ready.emit(url, pixmap, item, similarity)
                    return
        except Exception as e:
            print(f"❌ Thumbnail load error: {e}")
        
        # Emit empty pixmap on failure
        self.thumbnail_ready.emit(url, QPixmap(), item, similarity)
    
    def cancel(self):
        """Cancel all tasks"""
        self.running = False
        with QMutexLocker(self.mutex):
            self.task_queue.clear()


class ExplorerWindow(QMainWindow):
    """Optimized main window dengan performance improvements"""
    
    def __init__(self):
        super().__init__()
        self.threadpool = QThreadPool()
        self.threadpool.setMaxThreadCount(4)
        self.setWindowTitle("Find My Photo - FaceSync Finder")
        self.setGeometry(100, 100, 1200, 700)
        self.watcher_thread = None
        
        # Thumbnail management
        self.thumbnail_cache = {}
        self.search_optimizers = []
        self.outlet_data = {}
        self.tab_loaded = {}
        
        # Initialize UI
        self._init_ui()
        self.init_ui_additions()
        self.apply_modern_theme()
        self._setup_connections()
        
        # Status tracking
        self.embedding_in_progress = 0
        self.processing_files = {}
        
        # Navigation
        self.path_history = []
        self.current_path = ""
        
        # Search mode
        self.is_search_mode = False
        self.search_results = None
        
        # Download worker
        self.download_worker = None

    def _init_ui(self):
        """Initialize UI components"""
        # Top controls
        self.path_display = QLabel()
        self.path_display.setStyleSheet("font-weight: bold; font-size: 14px; padding: 5px;")
        
        top_layout = QHBoxLayout()        
        top_layout.addWidget(QLabel("📁"))
        top_layout.addWidget(self.path_display)
        top_layout.addStretch()

        # File list
        self.file_list = DragDropListWidget(self)
        self.file_list.setViewMode(QListView.IconMode)
        self.file_list.setIconSize(QPixmap(100, 100).size())
        self.file_list.setResizeMode(QListView.Adjust)
        self.file_list.setSpacing(10)
        self.file_list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.file_list.setWordWrap(True)
        self.file_list.setGridSize(QPixmap(140, 140).size())

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_label = QLabel()

        # Log area
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(150)

        # Layout
        self.main_layout = QVBoxLayout()
        self.main_layout.addLayout(top_layout)
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
        """Add new UI elements"""
        # Create toolbar
        toolbar_widget = QWidget()
        toolbar_layout = QHBoxLayout(toolbar_widget)
        toolbar_layout.setContentsMargins(5, 5, 5, 5)
        toolbar_layout.setSpacing(10)
        
        # Face search button
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
            }
            QPushButton:hover {
                background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                                          stop: 0 #6b7fe6, stop: 1 #5970d4);
            }
        """)
        self.face_search_btn.clicked.connect(self.open_face_search)
        
        # Download button
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
            }
            QPushButton:disabled {
                background-color: #6c757d;
            }
        """)
        self.download_btn.clicked.connect(self.download_selected_files)
        self.download_btn.setEnabled(False)
        self.download_btn.setVisible(False)
        
        toolbar_layout.addWidget(self.face_search_btn)
        toolbar_layout.addWidget(self.download_btn)
        toolbar_layout.addStretch()
        
        # Insert toolbar
        self.main_layout.insertWidget(2, toolbar_widget)
    
    def _setup_connections(self):
        """Setup signal connections"""
        # Connect file list selection changes to update download button
        self.file_list.itemSelectionChanged.connect(self.update_download_button_state)

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

    
    
    def open_face_search(self):
        """Open face search dialog with comprehensive error handling"""
        self.file_list.clear()
        try:            
            # self.log_with_timestamp("🔄 Starting face search...")
            
            # Debug: Check if running in PyInstaller
            import sys
            if getattr(sys, 'frozen', False):
                self.log_with_timestamp("📦 Running in PyInstaller mode")
                bundle_dir = sys._MEIPASS
                self.log_with_timestamp(f"📁 Bundle directory: {bundle_dir}")
            
            
            # Step 1: Import dengan error handling
            # self.log_with_timestamp("📦 Importing face detector...")
            try:
                from utils.image_processing import get_shared_detector
                face_detector = get_shared_detector()
                # self.log_with_timestamp("✅ Face detector imported successfully")
            except Exception as e:
                self.log_with_timestamp(f"❌ Face detector import failed: {str(e)}")
                self.show_error("Face detector import failed", str(e))
                return
            
            # Step 2: Import FaceEncoder
            # self.log_with_timestamp("📦 Importing face encoder...")
            try:
                from core.device_setup import FaceEncoder
                resnet = FaceEncoder()
                device = FaceEncoder.get_device()
                api_base = FaceEncoder.get_api_base()
                # self.log_with_timestamp("✅ Face encoder loaded successfully")
            except Exception as e:
                self.log_with_timestamp(f"❌ Face encoder import failed: {str(e)}")
                self.show_error("Face encoder import failed", str(e))
                return
            
            # Step 3: Import dialog
            # self.log_with_timestamp("📦 Importing face search dialog...")
            try:
                from ui.face_search_dialog import FaceSearchDialog
                # self.log_with_timestamp("✅ Dialog imported successfully")
            except Exception as e:
                self.log_with_timestamp(f"❌ Dialog import failed: {str(e)}")
                self.show_error("Dialog import failed", str(e))
                return
            
            # Step 4: Create dialog
            # self.log_with_timestamp("🔧 Creating face search dialog...")
            try:
                search_dialog = FaceSearchDialog(
                    face_detector=face_detector,
                    resnet=resnet,
                    device=device,
                    api_base=api_base,
                    parent=self
                )
                # self.log_with_timestamp("✅ Dialog created successfully")
            except Exception as e:
                self.log_with_timestamp(f"❌ Dialog creation failed: {str(e)}")
                self.show_error("Dialog creation failed", str(e))
                return
            
            # Step 5: Connect signals
            try:
                search_dialog.search_completed.connect(self.handle_face_search_results)
                # self.log_with_timestamp("✅ Signals connected")
            except Exception as e:
                self.log_with_timestamp(f"❌ Signal connection failed: {str(e)}")
                self.show_error("Signal connection failed", str(e))
                return
            
            # Step 6: Show dialog
            # self.log_with_timestamp("🎯 Showing face search dialog...")
            try:
                search_dialog.show()
                # self.log_with_timestamp("✅ Face search dialog shown successfully")
            except Exception as e:
                self.log_with_timestamp(f"❌ Dialog show failed: {str(e)}")
                self.show_error("Dialog show failed", str(e))
                return

        except Exception as e:
            self.log_with_timestamp(f"❌ Unexpected error in open_face_search: {str(e)}")
            self.show_error("Unexpected error", str(e))
            
            # Print full traceback untuk debugging
            import traceback
            traceback.print_exc()

    def show_error(self, title, message):
        """Show error dialog dengan fallback"""
        try:
            from PyQt5.QtWidgets import QMessageBox
            QMessageBox.critical(self, title, f"{message}\n\nCheck the logs for more details.")
        except Exception:
            # Fallback jika QMessageBox gagal
            print(f"ERROR: {title} - {message}")
    
    def handle_face_search_results(self, results):
        """Handle results from face search with optimized loading - FIXED"""
        print(f"🔍 Explorer received {len(results)} results")
        
        if not results:
            self.log_with_timestamp("❌ Face search: No results found")
            QMessageBox.information(self, "Face Search", "No matching faces found.")
            return
        
        self.log_with_timestamp(f"✅ Face search completed: {len(results)} results found")
        
        # ✅ DEBUG - Print first result structure
        if results:
            print("🔍 First result structure:")
            for key, value in results[0].items():
                print(f"  {key}: {value}")
        
        # Cleanup previous optimizers
        self.cleanup_search_optimizers()
        
        # Group by outlet
        outlet_groups = {}
        for result in results:
            outlet_name = result.get('outlet_name', 'Unknown')
            if outlet_name not in outlet_groups:
                outlet_groups[outlet_name] = []
            outlet_groups[outlet_name].append(result)
        
        print(f"🏪 Outlet groups: {list(outlet_groups.keys())}")
        
        # Setup UI
        self.file_list.clear()
        self.is_search_mode = True
        self.search_results = results
        self.download_btn.setVisible(True)
        self.download_btn.setEnabled(False)
        
        # Update path display
        if len(outlet_groups) == 1:
            outlet_name = list(outlet_groups.keys())[0]
            result_count = len(list(outlet_groups.values())[0])
            self.path_display.setText(f"🔍 Face Search Results - {outlet_name} ({result_count})")
        else:
            total_results = sum(len(group) for group in outlet_groups.values())
            self.path_display.setText(f"🔍 Face Search Results ({total_results} from {len(outlet_groups)} outlets)")
        
        self.path_display.setStyleSheet("font-weight: bold; font-size: 14px; padding: 5px; color: #5e72e4;")
        
        # Handle multiple outlets with optimization
        if len(outlet_groups) > 1:
            print("📋 Setting up multiple outlet tabs...")
            self.setup_multi_outlet_tabs_optimized(outlet_groups)
        else:
            print("📋 Setting up single outlet view...")
            self.setup_single_outlet_optimized(results)
        
        print(f"✅ UI setup completed. File list count: {self.file_list.count()}")

    def cleanup_search_optimizers(self):
        """Cleanup existing search optimizers"""
        for optimizer in self.search_optimizers:
            if hasattr(optimizer, 'thumbnail_loader'):
                optimizer.thumbnail_loader.cancel()
                optimizer.thumbnail_loader.wait(1000)
        self.search_optimizers.clear()

    
    def setup_single_outlet_optimized(self, results):
        """Setup single outlet with WORKING thumbnail loading"""
        print(f"🏪 Setting up single outlet with {len(results)} results - WITH THUMBNAILS")
        
        if hasattr(self, 'search_tab_widget'):
            self.search_tab_widget.setVisible(False)
        
        self.file_list.setVisible(True)
        self.file_list.clear()
        
        # Use OptimizedSearchResultsWidget for thumbnail loading
        optimizer = OptimizedSearchResultsWidget(self.file_list, self)
        optimizer.populate_results_optimized(results)
        self.search_optimizers.append(optimizer)
        
        print(f"✅ Single outlet populated with thumbnail loading")
        
        # Connect events
        self.file_list.itemDoubleClicked.connect(self._open_search_result)
        self.connect_selection_handlers(self.file_list)

    # ✅ FALLBACK METHOD - BASIC POPULATION
    def populate_results_basic(self, list_widget, results):
        """Basic population without optimization - fallback"""
        print(f"🔄 Using basic population for {len(results)} results")
        
        for i, result in enumerate(results):
            file_path = result.get('file_path', '')
            original_path = result.get('original_path', '')
            similarity = result.get('similarity', 0)
            outlet_name = result.get('outlet_name', 'Unknown')
            filename = result.get('filename', os.path.basename(file_path) if file_path else f'Image_{i+1}')
            
            if not (file_path or original_path):
                continue
            
            # Create item
            item = QListWidgetItem()
            display_name = self.smart_truncate_filename(filename, max_chars=14)
            similarity_percent = similarity * 100
            item.setText(f"{display_name}\n{similarity_percent:.0f}% match")
            
            # Store data
            item.setData(Qt.UserRole, filename)
            item.setData(Qt.UserRole + 1, "search_result")
            item.setData(Qt.UserRole + 2, original_path or file_path)
            item.setData(Qt.UserRole + 3, similarity)
            item.setData(Qt.UserRole + 4, outlet_name)
            
            # Default icon
            item.setIcon(self.style().standardIcon(self.style().SP_FileIcon))
            item.setToolTip(f"File: {filename}\nOutlet: {outlet_name}\nSimilarity: {similarity_percent:.1f}%")
            item.setTextAlignment(Qt.AlignHCenter | Qt.AlignBottom)
            
            list_widget.addItem(item)
        
        print(f"✅ Basic population completed. Items added: {list_widget.count()}")

    def setup_multi_outlet_tabs_optimized(self, outlet_groups):
        """Setup multiple outlet tabs with HIGHEST SIMILARITY FIRST and thumbnail loading"""
        print(f"🏪 Setting up {len(outlet_groups)} outlet tabs - WITH THUMBNAILS")
        
        self.file_list.setVisible(False)
        
        # Create tab widget  
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
            """)
            self.main_layout.insertWidget(3, self.search_tab_widget)
        
        self.search_tab_widget.clear()
        self.search_tab_widget.setVisible(True)
        
        # ✅ NEW: Calculate highest similarity for each outlet and sort
        outlet_with_max_similarity = []
        
        for outlet_name, outlet_results in outlet_groups.items():
            # Find highest similarity in this outlet
            max_similarity = max((result.get('similarity', 0) for result in outlet_results), default=0)
            outlet_with_max_similarity.append({
                'outlet_name': outlet_name,
                'results': outlet_results,
                'max_similarity': max_similarity,
                'count': len(outlet_results)
            })
            print(f"📊 Outlet '{outlet_name}': {len(outlet_results)} results, max similarity: {max_similarity:.3f}")
        
        # ✅ Sort by highest similarity DESCENDING
        outlet_with_max_similarity.sort(key=lambda x: x['max_similarity'], reverse=True)
        
        print("🎯 Tab order by highest similarity:")
        for i, outlet_info in enumerate(outlet_with_max_similarity):
            print(f"  Tab {i+1}: {outlet_info['outlet_name']} (max: {outlet_info['max_similarity']:.1%})")
        
        # CREATE TABS IN SORTED ORDER WITH THUMBNAIL LOADING
        for outlet_info in outlet_with_max_similarity:
            outlet_name = outlet_info['outlet_name']
            outlet_results = outlet_info['results']
            max_similarity = outlet_info['max_similarity']
            
            print(f"📋 Creating tab: {outlet_name} with {len(outlet_results)} items (max: {max_similarity:.1%})")
            
            # Create list widget
            outlet_list = QListWidget()
            outlet_list.setViewMode(QListView.IconMode)
            outlet_list.setIconSize(QPixmap(100, 100).size())
            outlet_list.setResizeMode(QListView.Adjust)
            outlet_list.setSpacing(10)
            outlet_list.setSelectionMode(QAbstractItemView.ExtendedSelection)
            outlet_list.setWordWrap(True)
            outlet_list.setGridSize(QPixmap(140, 140).size())
            outlet_list.setStyleSheet(self.file_list.styleSheet())
            
            # Use OptimizedSearchResultsWidget for thumbnail loading
            tab_optimizer = OptimizedSearchResultsWidget(outlet_list, self)
            tab_optimizer.populate_results_optimized(outlet_results)
            self.search_optimizers.append(tab_optimizer)
            
            print(f"✅ Added thumbnail loading for {outlet_name} tab")
            
            # Connect events
            outlet_list.itemDoubleClicked.connect(self._open_search_result)
            self.connect_selection_handlers(outlet_list)
            
            # Add tab with similarity info
            tab_label = f"{outlet_name} ({len(outlet_results)}) - {max_similarity:.0%}"
            self.search_tab_widget.addTab(outlet_list, tab_label)
        
        print(f"✅ All tabs created with thumbnail loading in similarity order. Tab count: {self.search_tab_widget.count()}")
    # def setup_multi_outlet_tabs_optimized(self, outlet_groups):
    #     """Setup multiple outlet tabs with WORKING thumbnail loading"""
    #     print(f"🏪 Setting up {len(outlet_groups)} outlet tabs - WITH THUMBNAILS")
        
    #     self.file_list.setVisible(False)
        
    #     # Create tab widget  
    #     if not hasattr(self, 'search_tab_widget'):
    #         self.search_tab_widget = QTabWidget()
    #         self.search_tab_widget.setStyleSheet("""
    #             QTabWidget::pane {
    #                 background-color: white;
    #                 border: 1px solid #e0e0e0;
    #                 border-radius: 8px;
    #             }
    #             QTabBar::tab {
    #                 background-color: #f8f9fa;
    #                 color: #333;
    #                 padding: 8px 16px;
    #                 margin-right: 2px;
    #                 border-top-left-radius: 6px;
    #                 border-top-right-radius: 6px;
    #             }
    #             QTabBar::tab:selected {
    #                 background-color: #5e72e4;
    #                 color: white;
    #             }
    #         """)
    #         self.main_layout.insertWidget(3, self.search_tab_widget)
        
    #     self.search_tab_widget.clear()
    #     self.search_tab_widget.setVisible(True)
        
    #     # CREATE TABS WITH THUMBNAIL LOADING
    #     for outlet_name, outlet_results in sorted(outlet_groups.items()):
    #         print(f"📋 Creating tab: {outlet_name} with {len(outlet_results)} items")
            
    #         # Create list widget
    #         outlet_list = QListWidget()
    #         outlet_list.setViewMode(QListView.IconMode)
    #         outlet_list.setIconSize(QPixmap(100, 100).size())
    #         outlet_list.setResizeMode(QListView.Adjust)
    #         outlet_list.setSpacing(10)
    #         outlet_list.setSelectionMode(QAbstractItemView.ExtendedSelection)
    #         outlet_list.setWordWrap(True)
    #         outlet_list.setGridSize(QPixmap(140, 140).size())
    #         outlet_list.setStyleSheet(self.file_list.styleSheet())
            
    #         # Use OptimizedSearchResultsWidget for thumbnail loading
    #         tab_optimizer = OptimizedSearchResultsWidget(outlet_list, self)
    #         tab_optimizer.populate_results_optimized(outlet_results)
    #         self.search_optimizers.append(tab_optimizer)
            
    #         print(f"✅ Added thumbnail loading for {outlet_name} tab")
            
    #         # Connect events
    #         outlet_list.itemDoubleClicked.connect(self._open_search_result)
    #         self.connect_selection_handlers(outlet_list)
            
    #         # Add tab
    #         tab_label = f"{outlet_name} ({len(outlet_results)})"
    #         self.search_tab_widget.addTab(outlet_list, tab_label)
        
    #     print(f"✅ All tabs created with thumbnail loading. Tab count: {self.search_tab_widget.count()}")

    
    def on_tab_changed(self, index):
        """Load tab content when tab is selected (lazy loading) - NEW"""
        if index >= 0 and not self.tab_loaded.get(index, True):
            self.load_tab_content(index)
    
    def load_tab_content(self, tab_index):
        """Load content for specific tab - NEW"""
        if tab_index < 0 or self.tab_loaded.get(tab_index, True):
            return
        
        outlet_list = self.search_tab_widget.widget(tab_index)
        if not outlet_list:
            return
        
        # Get outlet data
        outlet_names = list(self.outlet_data.keys())
        if tab_index >= len(outlet_names):
            return
            
        outlet_name = outlet_names[tab_index]
        outlet_results = self.outlet_data[outlet_name]
        
        print(f"📋 Loading tab content: {outlet_name} ({len(outlet_results)} items)")
        
        # Create optimizer dan populate
        tab_optimizer = OptimizedSearchResultsWidget(outlet_list, self)
        tab_optimizer.populate_results_optimized(outlet_results)
        self.search_optimizers.append(tab_optimizer)
        
        # Mark as loaded
        self.tab_loaded[tab_index] = True
        
        print(f"✅ Tab loaded: {outlet_name}")

    def _open_search_result(self, item):
        """Open search result item with navigation support - WITH DEBUG"""
        current_list = item.listWidget()
        if not current_list:
            return
            
        all_items = []
        current_index = 0
        
        for i in range(current_list.count()):
            list_item = current_list.item(i)
            url_or_path = list_item.data(Qt.UserRole + 2)
            filename = list_item.data(Qt.UserRole)  # Should be preserved now
            similarity = list_item.data(Qt.UserRole + 3)
            outlet_name = list_item.data(Qt.UserRole + 4)
            
            # DEBUG: Print data yang akan dikirim ke preview
            if i < 3:  # Print first 3 items
                print(f"🔍 Preview item {i}:")
                print(f"  - filename from UserRole: '{filename}'")
                print(f"  - url_or_path: {url_or_path}")
                print(f"  - similarity: {similarity}")
                print(f"  - outlet_name: {outlet_name}")
            
            if url_or_path:
                all_items.append({
                    'url_or_path': url_or_path,
                    'filename': filename,  # Should be correct now
                    'similarity': similarity,
                    'outlet_name': outlet_name,
                    'index': i
                })
                
                if list_item == item:
                    current_index = len(all_items) - 1
        
        if not all_items:
            self.log_with_timestamp("❌ No items available for preview")
            return
            
        # DEBUG: Print final data untuk current item
        current_item = all_items[current_index]
        print(f"🎯 Opening preview for:")
        print(f"  - filename: '{current_item['filename']}'")
        print(f"  - url_or_path: {current_item['url_or_path']}")
        
        self.log_with_timestamp(f"👁️ Opening preview: {current_item['filename']} ({current_index + 1} of {len(all_items)})")
        
        # Open preview dengan data yang sudah diperbaiki
        self.open_enhanced_preview(all_items, current_index)

    def open_enhanced_preview(self, items_data, start_index=0):
        """Open navigation preview with selection support"""
        try:
            dialog = NavigationPreviewDialog(items_data, start_index, self)
            # Connect the download signal from preview to main window
            dialog.download_requested.connect(self.handle_preview_download)
            dialog.exec_()
            # self.log_with_timestamp("✅ Image preview completed")
        except Exception as e:
            self.log_with_timestamp(f"❌ Error opening preview: {str(e)}")
    
    def handle_preview_download(self, selected_items_data):
        """Handle download request from preview dialog"""
        try:
            if not selected_items_data:
                QMessageBox.information(self, "Download", "No images selected for download.")
                return
            
            # Choose download directory
            download_dir = QFileDialog.getExistingDirectory(
                self,
                "Choose Download Directory",
                os.path.expanduser("~/Downloads")
            )
            
            if not download_dir:
                return
            
            # Prepare download tasks from preview selection
            download_tasks = []
            for item_info in selected_items_data:
                item_data = item_info['data']
                url_or_path = item_data.get('url_or_path', '')
                filename = item_data.get('filename', f"image_{item_info['index']}")
                outlet_name = item_data.get('outlet_name', 'unknown_outlet')
                
                if url_or_path:
                    download_tasks.append({
                        'url': url_or_path,
                        'filename': filename,
                        'outlet_name': outlet_name
                    })
            
            if not download_tasks:
                QMessageBox.warning(self, "Download", "No valid files to download.")
                return
            
            self.log_with_timestamp(f"📥 Starting preview download of {len(download_tasks)} files to {download_dir}")
            
            # Start download worker
            self.start_download_worker(download_tasks, download_dir)
            
        except Exception as e:
            self.log_with_timestamp(f"❌ Error handling preview download: {str(e)}")
            QMessageBox.critical(self, "Download Error", f"Failed to start download:\n{str(e)}")
            

    def on_preview_selection_changed(self, index, is_selected):
        """Handle selection change from preview dialog"""
        # Opsional: sync selection dengan main list jika diperlukan
        print(f"Preview selection changed: Item {index} {'selected' if is_selected else 'deselected'}")
        
        # Update download button state di main window jika perlu
        if hasattr(self, 'download_btn') and self.is_search_mode:
            # Bisa update state berdasarkan preview selection
            pass

    # ✅ NEW METHODS FOR DOWNLOAD FUNCTIONALITY
    def connect_selection_handlers(self, list_widget):
        """Connect selection change handlers for download button updates"""
        list_widget.itemSelectionChanged.connect(self.update_download_button_state)
    
    def update_download_button_state(self):
        """Update download button enabled state based on selection"""
        if not self.is_search_mode or not hasattr(self, 'download_btn'):
            return
        
        selected_items = self.get_selected_search_items()
        self.download_btn.setEnabled(len(selected_items) > 0)
    
    def get_selected_search_items(self):
        """Get all selected search result items across tabs"""
        selected_items = []
        
        if hasattr(self, 'search_tab_widget') and self.search_tab_widget.isVisible():
            # Multi-outlet mode - check all tabs
            for i in range(self.search_tab_widget.count()):
                tab_list = self.search_tab_widget.widget(i)
                if tab_list:
                    selected_items.extend(tab_list.selectedItems())
        else:
            # Single outlet mode
            selected_items = self.file_list.selectedItems()
        
        # Filter only search result items
        search_items = []
        for item in selected_items:
            if item.data(Qt.UserRole + 1) == "search_result":
                search_items.append(item)
        
        return search_items
    
    def download_selected_files(self):
        """Download selected files from search results"""
        try:
            selected_items = self.get_selected_search_items()
            
            if not selected_items:
                QMessageBox.information(self, "Download", "Please select items to download.")
                return
            
            # Choose download directory
            download_dir = QFileDialog.getExistingDirectory(
                self,
                "Choose Download Directory",
                os.path.expanduser("~/Downloads")
            )
            
            if not download_dir:
                return
            
            # Prepare download tasks
            download_tasks = []
            for item in selected_items:
                url_or_path = item.data(Qt.UserRole + 2)
                filename = item.data(Qt.UserRole) or "unknown_file"
                outlet_name = item.data(Qt.UserRole + 4) or "unknown_outlet"
                
                if url_or_path:
                    download_tasks.append({
                        'url': url_or_path,
                        'filename': filename,
                        'outlet_name': outlet_name
                    })
            
            if not download_tasks:
                QMessageBox.warning(self, "Download", "No valid files to download.")
                return
            
            self.log_with_timestamp(f"📥 Starting download of {len(download_tasks)} files to {download_dir}")
            
            # Start download worker
            self.start_download_worker(download_tasks, download_dir)
            
        except Exception as e:
            self.log_with_timestamp(f"❌ Error starting download: {str(e)}")
            QMessageBox.critical(self, "Download Error", f"Failed to start download:\n{str(e)}")
    
    def start_download_worker(self, download_tasks, download_dir):
        """Start the download worker thread"""
        try:
            # Cancel any existing download
            self.current_download_dir = download_dir 
            if self.download_worker and self.download_worker.isRunning():
                self.download_worker.cancel()
                self.download_worker.wait(3000)
            
            # Create new download worker
            self.download_worker = DownloadWorker(download_tasks, download_dir)
            
            # Connect signals
            self.download_worker.progress_updated.connect(self.on_download_progress)
            self.download_worker.file_completed.connect(self.on_file_downloaded)
            self.download_worker.download_completed.connect(self.on_download_completed)
            self.download_worker.error_occurred.connect(self.on_download_error)
            
            # Show progress bar
            self.progress_bar.setVisible(True)
            self.progress_bar.setValue(0)
            self.progress_bar.setMaximum(len(download_tasks))
            self.progress_label.setText(f"Downloading 0/{len(download_tasks)} files...")
            
            # Disable download button during download
            self.download_btn.setEnabled(False)
            self.download_btn.setText("⏳ Downloading...")
            
            # Start download
            self.download_worker.start()
            
        except Exception as e:
            self.log_with_timestamp(f"❌ Error creating download worker: {str(e)}")
            QMessageBox.critical(self, "Download Error", f"Failed to create download worker:\n{str(e)}")
    
    def on_download_progress(self, completed, total):
        """Handle download progress updates"""
        self.progress_bar.setValue(completed)
        self.progress_label.setText(f"Downloading {completed}/{total} files...")
        
    def on_file_downloaded(self, filename, file_path):
        """Handle individual file download completion"""
        self.log_with_timestamp(f"✅ Downloaded: {filename} -> {file_path}")
        
    def on_download_completed(self, download_dir, total_files):
        """Handle download completion"""
        folder_to_open = self.current_download_dir 
        self.progress_bar.setVisible(False)
        self.progress_label.setText("")
        
        # Re-enable download button
        self.download_btn.setEnabled(True)
        self.download_btn.setText("⬇️ Download Selected")
        
        self.log_with_timestamp(f"🎉 Download completed! {total_files} files saved to {download_dir}")
        
        # Show completion message
        # reply = QMessageBox.question(
        #     self,
        #     "Download Complete",
        #     f"Successfully downloaded {total_files} files to:\n{folder_to_open}\n\nOpen download folder?",
        #     QMessageBox.Yes | QMessageBox.No
        # )
        
        # if reply == QMessageBox.Yes:
        #     try:
        #         import subprocess
        #         import platform
                
        #         if platform.system() == "Windows":
        #             subprocess.run(["explorer", folder_to_open])
        #         elif platform.system() == "Darwin":  # macOS
        #             subprocess.run(["open", folder_to_open])
        #         else:  # Linux
        #             subprocess.run(["xdg-open", folder_to_open])
        #     except Exception as e:
        #         self.log_with_timestamp(f"❌ Could not open folder: {str(e)}")
    
    def on_download_error(self, error_message):
        """Handle download errors"""
        self.progress_bar.setVisible(False)
        self.progress_label.setText("")
        
        # Re-enable download button
        self.download_btn.setEnabled(True)
        self.download_btn.setText("⬇️ Download Selected")
        
        self.log_with_timestamp(f"❌ Download error: {error_message}")
        QMessageBox.critical(self, "Download Error", f"Download failed:\n{error_message}")
    
    def exit_search_mode(self):
        """Exit search mode and return to normal browsing"""
        self.is_search_mode = False
        self.search_results = None
        
        # Cancel any ongoing download
        if self.download_worker and self.download_worker.isRunning():
            self.download_worker.cancel()
            self.download_worker.wait(3000)
        
        if hasattr(self, 'search_tab_widget'):
            self.search_tab_widget.setVisible(False)
        
        # Hide download button
        self.download_btn.setVisible(False)
        
        # Show normal file list
        self.file_list.setVisible(True)
        
        # Restore normal path display style
        self.path_display.setStyleSheet("font-weight: bold; font-size: 14px; padding: 5px;")
        
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

    
    def closeEvent(self, event):
        """Handle application close - UPDATED"""
        # Cleanup search optimizers
        self.cleanup_search_optimizers()
        
        # Cancel any ongoing download
        if self.download_worker:
            self.download_worker.cancel()
            self.download_worker.terminate()
            self.download_worker.wait(3000)
        
        # Wait for running workers to complete
        self.threadpool.waitForDone(3000)  # 3 second timeout
        event.accept()