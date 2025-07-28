from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QWidget, QProgressBar, QListWidget, QSlider, QCheckBox,
    QListWidgetItem, QSplitter, QGroupBox, QSpinBox, QDoubleSpinBox
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QThread, QPropertyAnimation, QEasingCurve, QSettings
from PyQt5.QtGui import QPixmap, QImage, QIcon
import cv2
import numpy as np
import torch
import json
import requests
import os

class SearchThread(QThread):
    results_ready = pyqtSignal(list)
    search_failed = pyqtSignal(str)

    def __init__(self, embedding, api_base, radius=0.7):
        super().__init__()
        self.embedding = embedding
        self.api_base = api_base
        self.radius = radius  # Custom radius

    def run(self):
        try:
            url = f"{self.api_base}/faces/search-by-face"
            request_data = {
                "embedding": self.embedding,
                "radius": self.radius,  # Use custom radius
                "top_k": 100,
                "collection_name": "face_embeddings"
            }

            response = requests.post(
                url,
                json=request_data,
                headers={"Content-Type": "application/json"},
                timeout=30
            )

            if response.status_code == 200:
                data = response.json()
                results = []

                if isinstance(data, dict):
                    results = data.get("data", data.get("results", []))
                elif isinstance(data, list):
                    results = data
                else:
                    results = []

                self.results_ready.emit(results)

            else:
                try:
                    error_detail = response.json()
                    message = error_detail.get("detail", "Search failed")
                    if isinstance(message, dict):
                        message = message.get("message", "Search failed")
                    self.search_failed.emit(message)
                except:
                    self.search_failed.emit(f"Search failed: {response.status_code}")

        except requests.exceptions.Timeout:
            self.search_failed.emit("Search timeout - please try again")
        except requests.exceptions.ConnectionError:
            self.search_failed.emit("Cannot connect to server")
        except Exception as e:
            self.search_failed.emit(str(e))


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
    """Enhanced face search dialog with custom radius settings"""
    search_completed = pyqtSignal(list)  # List of matching files
    
    def __init__(self, face_detector, resnet, device, api_base, parent=None):
        super().__init__(parent)
        self.face_detector = face_detector
        self.resnet = resnet
        self.device = device
        self.api_base = api_base
        self.current_embedding = None
        
        # Settings management
        self.settings = QSettings("FaceSync", "FaceSearchApp")
        
        self.setWindowTitle("Face Search - Enhanced")
        self.setWindowFlags(Qt.Window | Qt.WindowCloseButtonHint | Qt.WindowMinimizeButtonHint)
        self.resize(1200, 750)  # Slightly larger for settings panel
        
        # Detection thread
        self.detection_thread = FaceDetectionThread(face_detector, resnet, device)
        self.detection_thread.face_detected.connect(self.on_face_detected)
        self.detection_thread.detection_failed.connect(self.on_detection_failed)
        
        self.init_ui()
        self.setup_animations()
        self.load_settings()  # Load saved settings
        
    def init_ui(self):
        """Initialize UI with modern design and settings panel"""
        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(20)
        main_layout.setContentsMargins(20, 20, 20, 20)
        
        # Title
        title_label = QLabel("🔍 Enhanced Face Search")
        title_label.setStyleSheet("""
            QLabel {
                font-size: 24px;
                font-weight: bold;
                color: #333;                
            }
        """)
        main_layout.addWidget(title_label)
        
        # Settings Panel (NEW)
        self.create_settings_panel()
        main_layout.addWidget(self.settings_group)
        
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
        self.auto_capture_btn.setChecked(True)
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
        splitter.setSizes([700, 500])  # Adjust for settings panel
        
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
    
    def create_settings_panel(self):
        """Create settings panel with similarity radius control"""
        self.settings_group = QGroupBox("🔧 Search Settings")
        self.settings_group.setStyleSheet("""
            QGroupBox {
                font-size: 16px;
                font-weight: bold;
                color: #333;
                border: 2px solid #e0e0e0;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
        """)
        
        settings_layout = QHBoxLayout(self.settings_group)
        settings_layout.setSpacing(20)
        
        # Similarity threshold setting
        similarity_widget = QWidget()
        similarity_layout = QVBoxLayout(similarity_widget)
        similarity_layout.setContentsMargins(0, 0, 0, 0)
        
        # Label
        sim_label = QLabel("🎯 Similarity Threshold:")
        sim_label.setStyleSheet("font-size: 14px; font-weight: 600; color: #333;")
        similarity_layout.addWidget(sim_label)
        
        # Slider and spinbox container
        slider_container = QWidget()
        slider_layout = QHBoxLayout(slider_container)
        slider_layout.setContentsMargins(0, 0, 0, 0)
        slider_layout.setSpacing(10)
        
        # Slider (70% to 90%)
        self.radius_slider = QSlider(Qt.Horizontal)
        self.radius_slider.setMinimum(70)  # 70%
        self.radius_slider.setMaximum(90)  # 90%
        self.radius_slider.setValue(70)    # Default 70%
        self.radius_slider.setTickPosition(QSlider.TicksBelow)
        self.radius_slider.setTickInterval(5)
        self.radius_slider.setStyleSheet("""
            QSlider::groove:horizontal {
                border: 1px solid #999999;
                height: 8px;
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #B1B1B1, stop:1 #c4c4c4);
                margin: 2px 0;
                border-radius: 4px;
            }
            QSlider::handle:horizontal {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #5e72e4, stop:1 #4c63d2);
                border: 1px solid #5c5c5c;
                width: 18px;
                margin: -2px 0;
                border-radius: 9px;
            }
            QSlider::handle:horizontal:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #6b7fe6, stop:1 #5970d4);
            }
        """)
        
        # SpinBox for precise control
        self.radius_spinbox = QSpinBox()
        self.radius_spinbox.setMinimum(70)
        self.radius_spinbox.setMaximum(90)
        self.radius_spinbox.setValue(70)
        self.radius_spinbox.setSuffix("%")
        self.radius_spinbox.setStyleSheet("""
            QSpinBox {
                background-color: white;
                border: 1px solid #ddd;
                border-radius: 4px;
                padding: 5px;
                font-size: 14px;
                min-width: 60px;
            }
            QSpinBox:focus {
                border-color: #5e72e4;
            }
        """)
        
        # Connect slider and spinbox
        self.radius_slider.valueChanged.connect(self.radius_spinbox.setValue)
        self.radius_spinbox.valueChanged.connect(self.radius_slider.setValue)
        self.radius_slider.valueChanged.connect(self.on_radius_changed)
        
        slider_layout.addWidget(self.radius_slider)
        slider_layout.addWidget(self.radius_spinbox)
        
        similarity_layout.addWidget(slider_container)
        
        # Info label
        self.radius_info_label = QLabel("Higher values = More strict matching")
        self.radius_info_label.setStyleSheet("""
            QLabel {
                font-size: 12px;
                color: #666;
                font-style: italic;
            }
        """)
        similarity_layout.addWidget(self.radius_info_label)
        
        settings_layout.addWidget(similarity_widget)
        
        # Add some spacing
        settings_layout.addStretch()
        
        # Auto-save checkbox
        self.auto_save_checkbox = QCheckBox("💾 Auto-save settings")
        self.auto_save_checkbox.setChecked(True)
        self.auto_save_checkbox.setStyleSheet("""
            QCheckBox {
                font-size: 14px;
                color: #333;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
            }
            QCheckBox::indicator:unchecked {
                border: 2px solid #ddd;
                border-radius: 3px;
                background-color: white;
            }
            QCheckBox::indicator:checked {
                border: 2px solid #5e72e4;
                border-radius: 3px;
                background-color: #5e72e4;
                image: url(data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMTQiIGhlaWdodD0iMTAiIHZpZXdCb3g9IjAgMCAxNCAxMCIgZmlsbD0ibm9uZSIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj4KPHBhdGggZD0iTTEgNUw1IDlMMTMgMSIgc3Ryb2tlPSJ3aGl0ZSIgc3Ryb2tlLXdpZHRoPSIyIiBzdHJva2UtbGluZWNhcD0icm91bmQiIHN0cm9rZS1saW5lam9pbj0icm91bmQiLz4KPC9zdmc+);
            }
        """)
        settings_layout.addWidget(self.auto_save_checkbox)
    
    def on_radius_changed(self, value):
        """Handle radius change"""
        radius_decimal = value / 100.0  # Convert percentage to decimal
        self.radius_info_label.setText(f"Current threshold: {value}% ({radius_decimal:.2f}) - {'Very Strict' if value > 85 else 'Strict' if value > 80 else 'Moderate' if value > 75 else 'Relaxed'}")
        
        # Auto-save if enabled
        if self.auto_save_checkbox.isChecked():
            self.save_settings()
    
    def load_settings(self):
        """Load settings from QSettings"""
        try:
            # Load similarity radius (default 70%)
            saved_radius = self.settings.value("similarity_radius", 70, type=int)
            saved_radius = max(70, min(90, saved_radius))  # Clamp to valid range
            
            self.radius_slider.setValue(saved_radius)
            self.radius_spinbox.setValue(saved_radius)
            
            # Load auto-save preference
            auto_save = self.settings.value("auto_save_settings", True, type=bool)
            self.auto_save_checkbox.setChecked(auto_save)
            
            print(f"✅ Settings loaded: radius={saved_radius}%, auto_save={auto_save}")
            
        except Exception as e:
            print(f"⚠️ Error loading settings: {e}")
            # Use defaults
            self.radius_slider.setValue(70)
            self.radius_spinbox.setValue(70)
    
    def save_settings(self):
        """Save settings to QSettings"""
        try:
            self.settings.setValue("similarity_radius", self.radius_spinbox.value())
            self.settings.setValue("auto_save_settings", self.auto_save_checkbox.isChecked())
            self.settings.sync()
            
            print(f"💾 Settings saved: radius={self.radius_spinbox.value()}%")
            
        except Exception as e:
            print(f"❌ Error saving settings: {e}")
    
    def closeEvent(self, event):
        """Save settings on close"""
        self.save_settings()  # Always save on close
        self.camera_widget.stop_camera()
        if self.auto_capture_timer.isActive():
            self.auto_capture_timer.stop()
        super().closeEvent(event)
        
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
        """Perform search with custom radius"""
        if not self.current_embedding:
            return

        # Get custom radius from settings
        radius = self.radius_spinbox.value() / 100.0  # Convert to decimal
        
        self.search_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)
        self.results_list.clear()
        self.status_label.setText(f"🔍 Searching with {self.radius_spinbox.value()}% similarity threshold...")

        # Use custom radius
        self.search_thread = SearchThread(self.current_embedding, self.api_base, radius)
        self.search_thread.results_ready.connect(self.on_search_results)
        self.search_thread.search_failed.connect(self.on_search_failed)
        self.search_thread.finished.connect(self.on_search_finished)
        self.search_thread.start()

    def on_search_results(self, results):
        """Handle search results"""
        self.display_results(results)

    def on_search_failed(self, message):
        """Handle search failure"""
        self.status_label.setText(f"❌ {message}")
        self.status_label.setStyleSheet("""
            QLabel {
                background-color: #5a2d2d;
                color: #FFA07A;
                padding: 10px;
                border-radius: 5px;
                font-size: 14px;
            }
        """)

    def on_search_finished(self):
        """Handle search completion"""
        self.progress_bar.setVisible(False)
        self.search_btn.setEnabled(True)
            
    def display_results(self, results):
        """Display search results - PRESERVE FILENAME"""
        if not results:
            self.status_label.setText("❌ No matching faces found")
            return
            
        self.status_label.setText(f"✅ Found {len(results)} matching images")
        
        # Format results for explorer window - PRESERVE ALL FIELDS
        formatted_results = []
        
        for result in results:
            # Extract all fields
            file_path = result.get('original_path', '') or result.get('file_path', '')
            similarity = result.get('similarity', 0)
            photo_id = result.get('photo_id', '')
            outlet_name = result.get('outlet_name', 'Unknown') 
            thumbnail_path = result.get('thumbnail_path', '')
            original_path = result.get('original_path', '')
            
            # CRITICAL: Preserve filename from backend
            filename = result.get('filename', '')
            
            print(f"🔍 Backend result: filename='{filename}', photo_id={photo_id}")
            
            # Fallback filename extraction if empty
            if not filename:
                if original_path:
                    if original_path.startswith(('http://', 'https://')):
                        filename = original_path.split('/')[-1].split('?')[0]
                    else:
                        filename = os.path.basename(original_path)
                elif file_path:
                    filename = os.path.basename(file_path)
                else:
                    filename = f"{photo_id}.jpg"
            
            # Skip if no useful data
            if not file_path:
                continue
            
            # Create list item for dialog (OPTIONAL - for display in dialog)
            item = QListWidgetItem()
            
            similarity = max(0, min(1, similarity))
            display_filename = os.path.basename(filename) if filename else 'Unknown'
            similarity_percent = similarity * 100
            item.setText(f"📷 {display_filename}\n   Similarity: {similarity_percent:.1f}%")
            item.setData(Qt.UserRole, file_path)
            item.setData(Qt.UserRole + 1, photo_id)
            
            self.results_list.addItem(item)
            
            # IMPORTANT: Preserve ALL fields including filename for ExplorerWindow
            formatted_results.append({
                "file_path": file_path,
                "filename": filename,  # ← CRITICAL: Include filename!
                "similarity": similarity,
                "photo_id": photo_id,
                "outlet_name": outlet_name,
                "thumbnail_path": thumbnail_path,
                "original_path": original_path
            })
        
        # Debug: Print what will be sent to ExplorerWindow
        print(f"📤 Sending to Explorer: {len(formatted_results)} results")
        for i, r in enumerate(formatted_results[:3]):  # Print first 3
            print(f"  Result {i}: filename='{r['filename']}', similarity={r.get('similarity', 0):.3f}")
        
        # Emit to ExplorerWindow with preserved filename
        if formatted_results:
            self.search_completed.emit(formatted_results)