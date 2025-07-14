from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QWidget, QProgressBar, QListWidget,
    QListWidgetItem, QSplitter
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QThread, QPropertyAnimation, QEasingCurve
from PyQt5.QtGui import QPixmap, QImage, QIcon
import cv2
import numpy as np
import torch
import json
import requests
import os

class FaceDetectionThread(QThread):
    """Thread for face detection and embedding"""
    face_detected = pyqtSignal(np.ndarray, list)  # image, embedding
    detection_failed = pyqtSignal(str)
    
    def __init__(self, face_detector, resnet, device):
        super().__init__()
        self.face_detector = face_detector
        self.resnet = resnet
        self.device = device
        self.current_frame = None
        self.detecting = False
        
    def process_frame(self, frame):
        """Process a frame for face detection"""
        self.current_frame = frame.copy()
        if not self.detecting:
            self.start()
            
    def run(self):
        """Run face detection and embedding"""
        if self.current_frame is None:
            return
            
        self.detecting = True
        try:
            # Detect faces
            success, faces = self.face_detector.detect(self.current_frame)
            
            if success and faces and len(faces) > 0:
                # Get the largest face (assuming it's the main subject)
                largest_face = max(faces, key=lambda f: f[2] * f[3])  # w * h
                x, y, w, h = map(int, largest_face[:4])
                
                # Crop face
                face_crop = self.current_frame[y:y+h, x:x+w]
                
                # Generate embedding
                face_rgb = cv2.cvtColor(face_crop, cv2.COLOR_BGR2RGB)
                face_resized = cv2.resize(face_rgb, (160, 160))
                
                # Convert to tensor
                face_tensor = torch.from_numpy(face_resized).permute(2, 0, 1).float()
                face_tensor = (face_tensor / 255.0 - 0.5) / 0.5
                face_tensor = face_tensor.unsqueeze(0).to(self.device)
                
                with torch.no_grad():
                    embedding = self.resnet(face_tensor).squeeze().cpu().numpy().tolist()
                
                # Draw detection box on frame
                frame_with_box = self.current_frame.copy()
                cv2.rectangle(frame_with_box, (x, y), (x+w, y+h), (0, 255, 0), 2)
                cv2.putText(frame_with_box, "Face Detected", (x, y-10), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
                
                self.face_detected.emit(frame_with_box, embedding)
            else:
                self.detection_failed.emit("No face detected")
                
        except Exception as e:
            self.detection_failed.emit(str(e))
        finally:
            self.detecting = False

class CameraWidget(QWidget):
    """Beautiful camera widget with overlay"""
    capture_requested = pyqtSignal(np.ndarray)
    
    def __init__(self):
        super().__init__()
        self.camera = None
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_frame)
        self.current_frame = None
        self.has_detection = False
        self.init_ui()
        
    def init_ui(self):
        """Initialize camera UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Camera view
        self.camera_label = QLabel()
        self.camera_label.setMinimumSize(640, 480)
        self.camera_label.setStyleSheet("""
            QLabel {
                background-color: #ffffff;
                border: 2px solid #e0e0e0;
                border-radius: 10px;
            }
        """)
        self.camera_label.setAlignment(Qt.AlignCenter)
        self.camera_label.setScaledContents(True)
        
        # Overlay for face guide
        self.overlay_label = QLabel(self.camera_label)
        self.overlay_label.setGeometry(0, 0, 640, 480)
        self.overlay_label.setAttribute(Qt.WA_TranslucentBackground)
        
        layout.addWidget(self.camera_label)
        
        # Initial message
        self.camera_label.setText("📷 Camera initializing...")
        self.camera_label.setStyleSheet("""
            QLabel {
                background-color: #ffffff;
                border: 2px solid #e0e0e0;
                border-radius: 10px;
                color: #666;
                font-size: 16px;
            }
        """)
        
    def start_camera(self):
        """Start camera capture"""
        # Try different camera indices if default (0) fails
        for camera_index in [0, 1, 2]:
            self.camera = cv2.VideoCapture(camera_index)
            if self.camera.isOpened():
                self.timer.start(30)  # 30ms = ~33 FPS
                return True
        
        # If all indices fail, show error
        self.camera_label.setText("❌ Camera not available\n\nPlease check camera permissions:\nSystem Preferences → Security & Privacy → Privacy → Camera")
        return False
            
    def stop_camera(self):
        """Stop camera capture"""
        self.timer.stop()
        if self.camera:
            self.camera.release()
            self.camera = None
            
    def update_frame(self):
        """Update camera frame"""
        if self.camera and self.camera.isOpened():
            ret, frame = self.camera.read()
            if ret:
                self.current_frame = frame
                self.display_frame(frame)
                
    def display_frame(self, frame):
        """Display frame with face detection overlay"""
        # Convert to RGB
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        
        # Create QImage
        h, w, ch = rgb_frame.shape
        bytes_per_line = ch * w
        qt_image = QImage(rgb_frame.data, w, h, bytes_per_line, QImage.Format_RGB888)
        
        # Scale to fit label
        pixmap = QPixmap.fromImage(qt_image)
        scaled_pixmap = pixmap.scaled(self.camera_label.size(), 
                                     Qt.KeepAspectRatio, 
                                     Qt.SmoothTransformation)
        self.camera_label.setPixmap(scaled_pixmap)
        
    def set_detection_status(self, has_detection):
        """Update detection status"""
        self.has_detection = has_detection
        
    def capture_current_frame(self):
        """Emit current frame for processing"""
        if self.current_frame is not None:
            self.capture_requested.emit(self.current_frame.copy())

class FaceSearchDialog(QDialog):
    """Beautiful face search dialog"""
    search_completed = pyqtSignal(list)  # List of matching files
    
    def __init__(self, face_detector, resnet, device, api_base, parent=None):
        super().__init__(parent)
        self.face_detector = face_detector
        self.resnet = resnet
        self.device = device
        self.api_base = api_base
        self.current_embedding = None
        
        self.setWindowTitle("Face Search")
        self.setWindowFlags(Qt.Window | Qt.WindowCloseButtonHint | Qt.WindowMinimizeButtonHint)  # Make it a separate window
        self.resize(1000, 700)
        
        # Detection thread
        self.detection_thread = FaceDetectionThread(face_detector, resnet, device)
        self.detection_thread.face_detected.connect(self.on_face_detected)
        self.detection_thread.detection_failed.connect(self.on_detection_failed)
        
        self.init_ui()
        self.setup_animations()
        
    def init_ui(self):
        """Initialize UI with modern design"""
        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(20)
        main_layout.setContentsMargins(20, 20, 20, 20)
        
        # Title
        title_label = QLabel("🔍 Face Search")
        title_label.setStyleSheet("""
            QLabel {
                font-size: 24px;
                font-weight: bold;
                color: #333;                
            }
        """)
        main_layout.addWidget(title_label)
        
        # Content area with splitter
        splitter = QSplitter(Qt.Horizontal)
        
        # Left side - Camera
        camera_container = QWidget()
        camera_layout = QVBoxLayout(camera_container)
        
        self.camera_widget = CameraWidget()
        camera_layout.addWidget(self.camera_widget)
        
        # Camera controls
        controls_widget = QWidget()
        controls_layout = QHBoxLayout(controls_widget)
        controls_layout.setSpacing(10)
        
        # Auto-capture toggle with modern styling - DEFAULT ON
        self.auto_capture_btn = QPushButton("🔄 Auto Capture: ON")
        self.auto_capture_btn.setCheckable(True)
        self.auto_capture_btn.setChecked(True)  # Set default to ON
        self.auto_capture_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: 2px solid #4CAF50;
                border-radius: 8px;
                padding: 10px 20px;
                font-size: 14px;
                font-weight: 500;
            }
            QPushButton:!checked {
                background-color: #2a2a2a;
                color: #ccc;
                border-color: #444;
            }
            QPushButton:hover {
                background-color: #45a049;
                border-color: #45a049;
            }
            QPushButton:!checked:hover {
                background-color: #3a3a3a;
                border-color: #555;
            }
        """)
        self.auto_capture_btn.toggled.connect(self.toggle_auto_capture)
        
        # Search button
        self.search_btn = QPushButton("🔍 Search")
        self.search_btn.setEnabled(False)
        self.search_btn.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 10px 30px;
                font-size: 16px;
                font-weight: bold;
            }
            QPushButton:hover:enabled {
                background-color: #1976D2;
            }
            QPushButton:disabled {
                background-color: #555;
                color: #999;
            }
        """)
        self.search_btn.clicked.connect(self.perform_search)
        
        controls_layout.addWidget(self.auto_capture_btn)
        controls_layout.addStretch()
        controls_layout.addWidget(self.search_btn)
        
        camera_layout.addWidget(controls_widget)
        
        # Status bar
        self.status_label = QLabel("Position your face in the camera")
        self.status_label.setStyleSheet("""
            QLabel {
                background-color: #2a2a2a;
                color: #aaa;
                padding: 10px;
                border-radius: 5px;
                font-size: 14px;
            }
        """)
        camera_layout.addWidget(self.status_label)
        
        splitter.addWidget(camera_container)
        
        # Right side - Results
        results_container = QWidget()
        results_layout = QVBoxLayout(results_container)
        
        results_title = QLabel("📋 Search Results")
        results_title.setStyleSheet("""
            QLabel {
                font-size: 18px;
                font-weight: bold;                
                padding: 5px;
            }
        """)
        results_layout.addWidget(results_title)
        
        # Results list
        self.results_list = QListWidget()
        self.results_list.setStyleSheet("""
            QListWidget {
                background-color: #2a2a2a;
                border: 1px solid #444;
                border-radius: 8px;
                padding: 5px;
                color: #fff;
            }
            QListWidget::item {
                padding: 10px;
                border-bottom: 1px solid #333;
            }
            QListWidget::item:hover {
                background-color: #3a3a3a;
            }
            QListWidget::item:selected {
                background-color: #2196F3;
            }
        """)
        results_layout.addWidget(self.results_list)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #444;
                border-radius: 5px;
                text-align: center;
                background-color: #2a2a2a;
                color: white;
            }
            QProgressBar::chunk {
                background-color: #2196F3;
                border-radius: 4px;
            }
        """)
        results_layout.addWidget(self.progress_bar)
        
        splitter.addWidget(results_container)
        splitter.setSizes([600, 400])
        
        main_layout.addWidget(splitter)
        
        # Dialog buttons
        button_widget = QWidget()
        button_layout = QHBoxLayout(button_widget)
        button_layout.setContentsMargins(0, 10, 0, 0)
        
        self.close_btn = QPushButton("Close")
        self.close_btn.setStyleSheet("""
            QPushButton {
                background-color: #444;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 10px 30px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #555;
            }
        """)
        self.close_btn.clicked.connect(self.close)
        
        button_layout.addStretch()
        button_layout.addWidget(self.close_btn)
        
        main_layout.addWidget(button_widget)
        
        # Auto-capture timer
        self.auto_capture_timer = QTimer()
        self.auto_capture_timer.timeout.connect(self.auto_capture_frame)
        
        # Set light theme
        self.setStyleSheet("""
            QDialog {
                background-color: #f5f5f5;
            }
        """)
        
    def setup_animations(self):
        """Setup animations"""
        self.setWindowOpacity(0)
        self.fade_animation = QPropertyAnimation(self, b"windowOpacity")
        self.fade_animation.setDuration(300)
        self.fade_animation.setStartValue(0)
        self.fade_animation.setEndValue(1)
        self.fade_animation.setEasingCurve(QEasingCurve.OutCubic)
        
    def showEvent(self, event):
        """Start camera when dialog shows"""
        super().showEvent(event)
        if self.camera_widget.start_camera():
            self.fade_animation.start()
            self.status_label.setText("✅ Camera ready - Position your face")
            # Start auto-capture since it's ON by default
            self.auto_capture_timer.start(500)
        else:
            self.status_label.setText("❌ Failed to start camera")
            
    def closeEvent(self, event):
        """Stop camera when dialog closes"""
        self.camera_widget.stop_camera()
        if self.auto_capture_timer.isActive():
            self.auto_capture_timer.stop()
        super().closeEvent(event)
        
    def toggle_auto_capture(self, checked):
        """Toggle auto capture mode"""
        if checked:
            self.auto_capture_btn.setText("🔄 Auto Capture: ON")
            self.auto_capture_timer.start(500)  # Check every 500ms
            self.status_label.setText("🔄 Auto capture enabled - Face will be detected automatically")
        else:
            self.auto_capture_btn.setText("🔄 Auto Capture: OFF")
            self.auto_capture_timer.stop()
            self.status_label.setText("✅ Camera ready - Position your face")
            
    def auto_capture_frame(self):
        """Auto capture when face is detected"""
        if self.camera_widget.current_frame is not None:
            self.detection_thread.process_frame(self.camera_widget.current_frame)
            
    def on_face_detected(self, frame_with_box, embedding):
        """Handle successful face detection"""
        self.current_embedding = embedding
        self.camera_widget.display_frame(frame_with_box)
        self.search_btn.setEnabled(True)
        self.status_label.setText("✅ Face detected! Click Search to find similar faces")
        self.status_label.setStyleSheet("""
            QLabel {
                background-color: #2d5a2d;
                color: #90EE90;
                padding: 10px;
                border-radius: 5px;
                font-size: 14px;
            }
        """)
        
    def on_detection_failed(self, error):
        """Handle detection failure"""
        self.search_btn.setEnabled(False)
        self.status_label.setText(f"⚠️ {error}")
        self.status_label.setStyleSheet("""
            QLabel {
                background-color: #5a2d2d;
                color: #FFA07A;
                padding: 10px;
                border-radius: 5px;
                font-size: 14px;
            }
        """)
        
    def perform_search(self):
        """Perform face search"""
        if not self.current_embedding:
            return
            
        self.search_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)  # Indeterminate
        self.results_list.clear()
        self.status_label.setText("🔍 Searching for similar faces...")
        
        # Perform search in thread
        QTimer.singleShot(100, self._do_search)
        
    def _do_search(self):
        """Actual search implementation"""
        try:
            # Debug: Print embedding info
            print(f"Searching with embedding of length: {len(self.current_embedding)}")
            
            # Choose endpoint based on your backend implementation
            url = f"{self.api_base}/faces/search-by-face"
            request_data = {
                "embedding": self.current_embedding,
                "radius": 0.7,  # Similarity threshold
                "top_k": 50,    # Max results
                "collection_name": "face_embeddings"
            }
            
            print(f"Sending request to: {url}")
            
            response = requests.post(
                url,
                json=request_data,
                headers={"Content-Type": "application/json"},
                timeout=30
            )
            
            print(f"Response status: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                print(f"Response data keys: {data.keys()}")
                
                # Handle different response formats
                results = []
                if "data" in data:
                    results = data.get("data", [])  # Full endpoint response
                elif "results" in data:
                    results = data.get("results", [])  # Simple endpoint response
                else:
                    # Maybe the response is the array directly?
                    if isinstance(data, list):
                        results = data
                
                print(f"Found {len(results)} results")
                if results:
                    print(f"First result: {results[0]}")
                    # Check similarity values from backend
                    for i, r in enumerate(results[:3]):
                        sim = r.get('similarity', 0)
                        print(f"Result {i} similarity from backend: {sim}")
                    
                self.display_results(results)
            else:
                error_msg = "Search failed"
                try:
                    error_detail = response.json()
                    print(f"Error response: {error_detail}")
                    if isinstance(error_detail, dict):
                        error_msg = error_detail.get("detail", error_msg)
                        if isinstance(error_msg, dict):
                            error_msg = error_msg.get("message", "Search failed")
                except:
                    error_msg = f"Search failed: {response.status_code}"
                self.status_label.setText(f"❌ {error_msg}")
                
        except requests.exceptions.Timeout:
            self.status_label.setText("❌ Search timeout - please try again")
        except requests.exceptions.ConnectionError:
            self.status_label.setText("❌ Cannot connect to server")
        except Exception as e:
            self.status_label.setText(f"❌ Error: {str(e)}")
            print(f"Search error details: {e}")  # Debug logging
            import traceback
            traceback.print_exc()
        finally:
            self.progress_bar.setVisible(False)
            self.search_btn.setEnabled(True)
            
    def display_results(self, results):
        """Display search results"""
        if not results:
            self.status_label.setText("❌ No matching faces found")
            return
            
        self.status_label.setText(f"✅ Found {len(results)} matching images")
        
        # Format results for explorer window
        formatted_results = []
        
        for result in results:
            # Create custom list item
            item = QListWidgetItem()
            
            # Extract data - handle different response formats
            file_path = result.get('file_path', '')
            similarity = result.get('similarity', 0)
            photo_id = result.get('photo_id', '')
            outlet_name = result.get('outlet_name', 'Unknown') 
            thumbnail_path = result.get('thumbnail_path', '')
            original_path = result.get('original_path', '')
            
            # Debug: Print raw data
            print(f"Raw result data: file_path={original_path}, similarity={similarity}, outlet={outlet_name}")
            
            # Skip if no file path
            if not file_path:
                continue
            
            # Ensure similarity is between 0 and 1
            similarity = max(0, min(1, similarity))
            
            filename = os.path.basename(file_path)
            similarity_percent = similarity * 100
            item.setText(f"📷 {filename}\n   Similarity: {similarity_percent:.1f}%")
            item.setData(Qt.UserRole, file_path)
            item.setData(Qt.UserRole + 1, photo_id)
            
            # Add icon if possible
            if os.path.exists(file_path):
                pixmap = QPixmap(file_path)
                if not pixmap.isNull():
                    icon = QIcon(pixmap.scaled(64, 64, Qt.KeepAspectRatio, Qt.SmoothTransformation))
                    item.setIcon(icon)
                    
            self.results_list.addItem(item)
            
            # IMPORTANT: Add to formatted results with correct similarity
            formatted_results.append({
                "file_path": file_path,
                "similarity": similarity,  # Make sure this is included!
                "photo_id": photo_id,
                "outlet_name": outlet_name,
                "thumbnail_path": thumbnail_path,
                "original_path": original_path
            })
        
        # Debug: Print what we're sending
        print(f"Sending {len(formatted_results)} results to explorer")
        for r in formatted_results[:3]:  # Print first 3
            print(f"  - {r['file_path']} (similarity: {r.get('similarity', 0):.3f})")
            
        # Emit formatted results
        if formatted_results:
            self.search_completed.emit(formatted_results)