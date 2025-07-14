import os
import shutil
import logging
import requests

from PyQt5.QtCore import (
    Qt, QThread, pyqtSignal
)
logger = logging.getLogger(__name__)


class DownloadWorker(QThread):
    """Worker thread for downloading files"""
    progress = pyqtSignal(int, str)  # progress, status
    finished = pyqtSignal(bool, str)  # success, message
    
    def __init__(self, items, save_path):
        super().__init__()
        self.items = items
        self.save_path = save_path
        self.cancelled = False
    
    def run(self):
        try:
            if len(self.items) == 1:
                self.download_single_file()
            else:
                self.download_multiple_files_direct()  # Changed from ZIP to direct download
            
            if not self.cancelled:
                self.finished.emit(True, f"Downloaded {len(self.items)} file(s) successfully!")
            
        except Exception as e:
            self.finished.emit(False, f"Download failed: {str(e)}")
    
    def cancel(self):
        """Cancel the download operation"""
        self.cancelled = True
    
    def download_single_file(self):
        """Download single file"""
        item = self.items[0]
        url_or_path = item.data(Qt.UserRole + 2)
        
        self.progress.emit(50, "Downloading file...")
        
        if url_or_path.startswith(('http://', 'https://')):
            response = requests.get(url_or_path, stream=True, timeout=30)
            response.raise_for_status()
            
            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0
            
            with open(self.save_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if self.cancelled:
                        return
                    f.write(chunk)
                    downloaded += len(chunk)
                    
                    if total_size > 0:
                        progress = int((downloaded / total_size) * 100)
                        self.progress.emit(progress, f"Downloading... {downloaded}/{total_size} bytes")
        else:
            # Local file
            import shutil
            shutil.copy2(url_or_path, self.save_path)
            self.progress.emit(100, "File copied successfully")
    
    def download_multiple_files_direct(self):
        """Download multiple files directly to folder (no ZIP)"""
        # save_path is the folder path, not a file
        download_folder = self.save_path
        
        # Create download folder if it doesn't exist
        if not os.path.exists(download_folder):
            os.makedirs(download_folder)
        
        for i, item in enumerate(self.items):
            if self.cancelled:
                return
                
            progress_percent = int((i / len(self.items)) * 100)
            filename = item.data(Qt.UserRole)
            self.progress.emit(progress_percent, f"Downloading {filename} ({i+1}/{len(self.items)})")
            
            url_or_path = item.data(Qt.UserRole + 2)
            outlet_name = item.data(Qt.UserRole + 4)
            
            # Create unique filename to avoid conflicts
            # Add outlet prefix and similarity score
            similarity = item.data(Qt.UserRole + 3)
            similarity_percent = int(similarity * 100) if similarity else 0
            
            # Create filename with outlet and similarity info
            name_part, ext = os.path.splitext(filename)
            if outlet_name and outlet_name != 'Unknown':
                new_filename = f"[{outlet_name}]_{name_part}_{similarity_percent}pct{ext}"
            else:
                new_filename = f"{name_part}_{similarity_percent}pct{ext}"
            
            # Handle duplicate filenames
            counter = 1
            original_filename = new_filename
            file_path = os.path.join(download_folder, new_filename)
            while os.path.exists(file_path):
                name_part, ext = os.path.splitext(original_filename)
                new_filename = f"{name_part}_{counter}{ext}"
                file_path = os.path.join(download_folder, new_filename)
                counter += 1
            
            try:
                if url_or_path.startswith(('http://', 'https://')):
                    # Download from URL
                    response = requests.get(url_or_path, timeout=30)
                    response.raise_for_status()
                    
                    with open(file_path, 'wb') as f:
                        f.write(response.content)
                else:
                    # Local file
                    if os.path.exists(url_or_path):
                        shutil.copy2(url_or_path, file_path)
                    else:
                        logger.warning(f"File not found: {url_or_path}")
                        continue
                        
            except Exception as e:
                logger.warning(f"Failed to download {filename}: {e}")
                continue