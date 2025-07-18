
import os
import sys
import logging
import requests
from datetime import datetime


from PyQt5.QtCore import (
    Qt, QThreadPool
)
from PyQt5.QtGui import (
    QPixmap, QIcon, QDrag, QClipboard, QPainter, QColor, QFont
)
from PyQt5.QtWidgets import (
    QMainWindow, QListView, QFileDialog, QTextEdit, QPushButton, QVBoxLayout, QWidget, QHBoxLayout,
    QLabel, QLineEdit, QListWidget, QListWidgetItem, QMessageBox, QAbstractItemView, QTabWidget, QProgressBar,
    QProgressDialog, QProgressDialog
)


from utils.features import DragDropListWidget
from ui.face_search_dialog import FaceSearchDialog
from ui.navigation_preview import NavigationPreviewDialog
from core.download_worker import DownloadWorker
from utils.image_processing import get_shared_detector
from core.device_setup import resnet, device, API_BASE
from config.thumbnail_manager import OptimizedSearchResultsWidget
logger = logging.getLogger(__name__)

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
        """Apply thumbnail dengan similarity overlay"""
        try:
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
            
        except Exception as e:
            print(f"❌ Error applying overlay: {e}")
            item.setIcon(QIcon(pixmap))