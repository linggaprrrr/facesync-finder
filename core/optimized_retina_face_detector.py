import time
import logging
import cv2
import numpy as np
from retinaface import RetinaFace

logger = logging.getLogger(__name__)


class OptimizedRetinaFaceDetector:
    """Optimized RetinaFace detector dengan speed improvements"""
    
    def __init__(self, device='cpu', conf_threshold=0.6, nms_threshold=0.4, max_size=640):
        self.device = device
        self.conf_threshold = conf_threshold
        self.nms_threshold = nms_threshold
        self.max_size = max_size
        self.model_warmed = False
        self._warm_up_model()
    
    def _warm_up_model(self):
        """Warm up model dengan dummy detection"""
        try:
            dummy_img = np.ones((224, 224, 3), dtype=np.uint8) * 128
            RetinaFace.detect_faces(dummy_img, threshold=0.9)
            self.model_warmed = True
            logger.info("✅ RetinaFace model warmed up")
        except Exception as e:
            logger.warning(f"⚠️ Model warm up failed: {e}")
    
    def detect_with_resize(self, img):
        """Detect dengan image resizing dan FIXED coordinate scaling"""
        original_h, original_w = img.shape[:2]
        
        # Resize jika terlalu besar
        if max(original_w, original_h) > self.max_size:
            scale = self.max_size / max(original_w, original_h)
            new_w = int(original_w * scale)
            new_h = int(original_h * scale)
            
            logger.info(f"🔄 Resizing: {original_w}x{original_h} -> {new_w}x{new_h} (scale={scale:.3f})")
            
            resized_img = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
            
            faces_dict = RetinaFace.detect_faces(
                resized_img, 
                threshold=self.conf_threshold,
                model=None,
                allow_upscaling=False
            )
            
            # FIXED: Scale coordinates back properly
            if faces_dict:
                for face_key, face_data in faces_dict.items():
                    facial_area = face_data['facial_area']  # [x1, y1, x2, y2]
                    
                    # Scale back ke original size
                    x1, y1, x2, y2 = facial_area
                    original_x1 = int(x1 / scale)
                    original_y1 = int(y1 / scale) 
                    original_x2 = int(x2 / scale)
                    original_y2 = int(y2 / scale)
                    
                    # Update dengan koordinat original
                    face_data['facial_area'] = [original_x1, original_y1, original_x2, original_y2]
                    
                    logger.debug(f"Scaled bbox: ({x1},{y1},{x2},{y2}) -> ({original_x1},{original_y1},{original_x2},{original_y2})")
        else:
            faces_dict = RetinaFace.detect_faces(
                img, 
                threshold=self.conf_threshold,
                model=None,
                allow_upscaling=False
            )
        
        return faces_dict
    
    def detect(self, img):
        """Main detection method dengan FIXED bbox conversion"""
        try:
            start_time = time.time()
            faces_dict = self.detect_with_resize(img)
            detection_time = time.time() - start_time
            
            logger.info(f"🔍 Detection time: {detection_time:.3f}s")
            
            if not faces_dict:
                return False, None
            
            faces_list = []
            img_h, img_w = img.shape[:2]
            
            for face_key, face_data in faces_dict.items():
                facial_area = face_data['facial_area']  # [x1, y1, x2, y2]
                confidence = float(face_data['score'])
                
                # FIXED: Proper conversion dari [x1,y1,x2,y2] ke [x,y,w,h]
                x1, y1, x2, y2 = facial_area
                x = int(x1)
                y = int(y1)
                w = int(x2 - x1)  # ✅ width = x2 - x1
                h = int(y2 - y1)  # ✅ height = y2 - y1
                
                # Validasi bbox
                if w <= 0 or h <= 0:
                    logger.warning(f"⚠️ Invalid bbox: x1={x1}, y1={y1}, x2={x2}, y2={y2}")
                    continue
                
                # Pastikan bbox dalam bounds image
                x = max(0, min(x, img_w - 1))
                y = max(0, min(y, img_h - 1))
                w = max(1, min(w, img_w - x))
                h = max(1, min(h, img_h - y))
                
                face_array = [x, y, w, h, confidence]
                faces_list.append(face_array)
                
                logger.debug(f"Face bbox: x={x}, y={y}, w={w}, h={h}, conf={confidence:.3f}")
            
            return True, faces_list
            
        except Exception as e:
            logger.error(f"❌ Error dalam deteksi: {e}")
            return False, None