import os
import hashlib
import requests
from PyQt5.QtCore import QThread, pyqtSignal, QMutex, QTimer
from PyQt5.QtGui import QPixmap, QPainter, QColor, QFont, QIcon
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QMainWindow, QListWidget, QListWidgetItem
)



import tempfile

class ThumbnailCache:
    """Thread-safe thumbnail cache dengan disk storage"""
    
    def __init__(self, cache_dir=None):
        self.cache_dir = cache_dir or os.path.join(tempfile.gettempdir(), "face_search_cache")
        os.makedirs(self.cache_dir, exist_ok=True)
        self.memory_cache = {}
        self.mutex = QMutex()
        
    def get_cache_key(self, url):
        """Generate cache key from URL"""
        return hashlib.md5(url.encode()).hexdigest()
    
    def get_cache_path(self, cache_key):
        """Get file path for cache key"""
        return os.path.join(self.cache_dir, f"{cache_key}.jpg")
    
    def get_from_memory(self, url):
        """Get pixmap from memory cache"""
        self.mutex.lock()
        try:
            return self.memory_cache.get(url)
        finally:
            self.mutex.unlock()
    
    def store_in_memory(self, url, pixmap):
        """Store pixmap in memory cache"""
        self.mutex.lock()
        try:
            # Limit memory cache size
            if len(self.memory_cache) > 100:
                # Remove oldest items
                keys_to_remove = list(self.memory_cache.keys())[:50]
                for key in keys_to_remove:
                    del self.memory_cache[key]
            
            self.memory_cache[url] = pixmap
        finally:
            self.mutex.unlock()
    
    def get_from_disk(self, url):
        """Get pixmap from disk cache"""
        cache_key = self.get_cache_key(url)
        cache_path = self.get_cache_path(cache_key)
        
        if os.path.exists(cache_path):
            pixmap = QPixmap(cache_path)
            if not pixmap.isNull():
                return pixmap
        return None
    
    def store_to_disk(self, url, pixmap):
        """Store pixmap to disk cache"""
        cache_key = self.get_cache_key(url)
        cache_path = self.get_cache_path(cache_key)
        pixmap.save(cache_path, "JPG", 85)  # 85% quality untuk menghemat space

class ThumbnailLoader(QThread):
    """Asynchronous thumbnail loader dengan batch processing"""
    
    thumbnail_loaded = pyqtSignal(int, QPixmap)  # index, pixmap
    batch_completed = pyqtSignal()
    
    def __init__(self, cache_manager):
        super().__init__()
        self.cache_manager = cache_manager
        self.tasks = []
        self.cancelled = False
        
    def add_task(self, index, url, similarity):
        """Add thumbnail loading task"""
        self.tasks.append({
            'index': index,
            'url': url,
            'similarity': similarity
        })
    
    def cancel(self):
        """Cancel all loading tasks"""
        self.cancelled = True
    
    def run(self):
        """Process thumbnail loading tasks"""
        for task in self.tasks:
            if self.cancelled:
                break
                
            index = task['index']
            url = task['url']
            similarity = task['similarity']
            
            try:
                # Check memory cache first
                pixmap = self.cache_manager.get_from_memory(url)
                
                if pixmap is None:
                    # Check disk cache
                    pixmap = self.cache_manager.get_from_disk(url)
                    
                    if pixmap is not None:
                        # Store in memory for next time
                        self.cache_manager.store_in_memory(url, pixmap)
                
                if pixmap is None:
                    # Download from network
                    pixmap = self.download_thumbnail(url, similarity)
                    
                    if pixmap is not None:
                        # Store in both caches
                        self.cache_manager.store_to_disk(url, pixmap)
                        self.cache_manager.store_in_memory(url, pixmap)
                
                if pixmap is not None and not self.cancelled:
                    self.thumbnail_loaded.emit(index, pixmap)
                    
            except Exception as e:
                print(f"Error loading thumbnail {index}: {e}")
                continue
        
        if not self.cancelled:
            self.batch_completed.emit()
    
    def download_thumbnail(self, url, similarity):
        """Download and process thumbnail"""
        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                # Convert to pixmap
                pixmap = QPixmap()
                pixmap.loadFromData(response.content)
                
                if not pixmap.isNull():
                    # Scale and add similarity badge
                    scaled_pixmap = pixmap.scaled(100, 100, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                    return self.add_similarity_badge(scaled_pixmap, similarity)
        except Exception as e:
            print(f"Network error downloading thumbnail: {e}")
        
        return None
    
    def add_similarity_badge(self, pixmap, similarity):
        """Add similarity percentage badge to pixmap"""
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Draw similarity badge
        similarity_percent = similarity * 100
        badge_color = QColor(94, 114, 228, 200)
        painter.setBrush(badge_color)
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(pixmap.width() - 30, 5, 25, 25)
        
        # Draw percentage text
        painter.setPen(Qt.white)
        font = QFont()
        font.setPointSize(9)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(pixmap.width() - 30, 5, 25, 25, 
                        Qt.AlignCenter, f"{similarity_percent:.0f}")
        painter.end()
        
        return pixmap

class OptimizedSearchResultsWidget:
    """Optimized search results dengan lazy loading"""
    
    def __init__(self, list_widget, parent):
        self.list_widget = list_widget
        self.parent = parent
        self.cache_manager = ThumbnailCache()
        self.thumbnail_loader = None
        self.pending_items = {}  # index -> item_data
        
        # Lazy loading timer
        self.lazy_timer = QTimer()
        self.lazy_timer.setSingleShot(True)
        self.lazy_timer.timeout.connect(self.load_visible_thumbnails)
        
        # Connect scroll events for lazy loading
        if hasattr(list_widget, 'verticalScrollBar'):
            list_widget.verticalScrollBar().valueChanged.connect(self.on_scroll)
    
    def populate_results_optimized(self, results):
        """Populate results dengan optimized loading"""
        self.list_widget.clear()
        self.pending_items.clear()
        
        # Cancel any existing loader
        if self.thumbnail_loader:
            self.thumbnail_loader.cancel()
            self.thumbnail_loader.wait(1000)
        
        # Add items dengan placeholder icons
        for i, result in enumerate(results):
            item = self.create_list_item(result, i)
            self.list_widget.addItem(item)
            self.pending_items[i] = result
        
        # Start loading thumbnails untuk visible items
        QTimer.singleShot(100, self.load_visible_thumbnails)
    
    def create_list_item(self, result, index):
        """Create list item dengan placeholder"""
        filename = result.get('filename', 'Unknown')
        similarity = result.get('similarity', 0)
        outlet_name = result.get('outlet_name', 'Unknown')
        
        item = QListWidgetItem()
        
        # Format display text
        display_name = self.smart_truncate_filename(filename, max_chars=14)
        similarity_percent = similarity * 100
        item.setText(f"{display_name}\n{similarity_percent:.0f}% match")
        
        # Store data
        item.setData(Qt.UserRole, filename)
        item.setData(Qt.UserRole + 1, "search_result")
        item.setData(Qt.UserRole + 2, result.get('original_path', ''))
        item.setData(Qt.UserRole + 3, similarity)
        item.setData(Qt.UserRole + 4, outlet_name)
        item.setData(Qt.UserRole + 5, index)  # Store index untuk thumbnail loading
        
        # Set placeholder icon
        placeholder_icon = self.create_placeholder_icon(similarity_percent)
        item.setIcon(placeholder_icon)
        
        # Tooltip
        item.setToolTip(f"File: {filename}\nOutlet: {outlet_name}\nSimilarity: {similarity_percent:.1f}%")
        item.setTextAlignment(Qt.AlignHCenter | Qt.AlignBottom)
        
        return item
    
    def create_placeholder_icon(self, similarity_percent):
        """Create placeholder icon dengan similarity percentage"""
        pixmap = QPixmap(100, 100)
        pixmap.fill(QColor(240, 240, 240))
        
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Draw loading indicator
        painter.setPen(QColor(150, 150, 150))
        painter.drawText(pixmap.rect(), Qt.AlignCenter, "📷\nLoading...")
        
        # Add similarity badge
        badge_color = QColor(94, 114, 228, 200)
        painter.setBrush(badge_color)
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(70, 5, 25, 25)
        
        painter.setPen(Qt.white)
        font = QFont()
        font.setPointSize(9)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(70, 5, 25, 25, Qt.AlignCenter, f"{similarity_percent:.0f}")
        
        painter.end()
        return QIcon(pixmap)
    
    def on_scroll(self):
        """Handle scroll events untuk lazy loading"""
        self.lazy_timer.start(200)  # Load after 200ms of no scrolling
    
    def load_visible_thumbnails(self):
        """Load thumbnails untuk visible items saja"""
        visible_items = self.get_visible_items()
        
        if not visible_items:
            return
        
        # Cancel existing loader
        if self.thumbnail_loader:
            self.thumbnail_loader.cancel()
            self.thumbnail_loader.wait(1000)
        
        # Create new loader
        self.thumbnail_loader = ThumbnailLoader(self.cache_manager)
        self.thumbnail_loader.thumbnail_loaded.connect(self.on_thumbnail_loaded)
        self.thumbnail_loader.batch_completed.connect(self.on_batch_completed)
        
        # Add visible items to loader
        for item_index in visible_items:
            if item_index in self.pending_items:
                result = self.pending_items[item_index]
                thumbnail_url = result.get('thumbnail_path', '')
                similarity = result.get('similarity', 0)
                
                if thumbnail_url:
                    self.thumbnail_loader.add_task(item_index, thumbnail_url, similarity)
        
        # Start loading
        self.thumbnail_loader.start()
    
    def get_visible_items(self):
        """Get indices of currently visible items"""
        visible_items = []
        
        # Get viewport geometry
        viewport = self.list_widget.viewport()
        viewport_rect = viewport.rect()
        
        # Check each item
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            if item:
                item_rect = self.list_widget.visualItemRect(item)
                if viewport_rect.intersects(item_rect):
                    index = item.data(Qt.UserRole + 5)
                    if index is not None:
                        visible_items.append(index)
        
        return visible_items
    
    def on_thumbnail_loaded(self, index, pixmap):
        """Handle thumbnail loaded dari worker thread"""
        # Find item dengan matching index
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            if item and item.data(Qt.UserRole + 5) == index:
                item.setIcon(QIcon(pixmap))
                # Remove from pending
                if index in self.pending_items:
                    del self.pending_items[index]
                break
    
    def on_batch_completed(self):
        """Handle batch loading completion"""
        print(f"Batch loading completed. {len(self.pending_items)} items remaining.")
    
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