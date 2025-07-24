import logging
import cv2
import numpy as np
import torch
from core.optimized_retina_face_detector import OptimizedRetinaFaceDetector
from core.device_setup import FaceEncoder

logger = logging.getLogger(__name__)

# Shared detector instance untuk reuse
_detector_instance = None

def convert_to_json_serializable(obj):
    """Convert numpy types to Python native types for JSON serialization"""
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, (np.float32, np.float64)):
        return float(obj)
    elif isinstance(obj, (np.int32, np.int64)):
        return int(obj)
    elif isinstance(obj, dict):
        return {key: convert_to_json_serializable(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [convert_to_json_serializable(item) for item in obj]
    else:
        return obj


def get_shared_detector():
    """Get shared detector instance dengan GPU optimization"""
    global _detector_instance
    if _detector_instance is None:
        device = 'cpu' 
        _detector_instance = OptimizedRetinaFaceDetector(
            device=device,
            conf_threshold=0.6,
            nms_threshold=0.4,
            max_size=640  # Bisa naik ke 1024 jika pakai GPU untuk akurasi lebih tinggi
        )
        
        # Log GPU usage
        
            
    return _detector_instance

def create_face_detector():
    """Factory function dengan shared instance"""
    return get_shared_detector()

def process_faces_in_image(file_path, original_shape=None, pad=None, scale=None):
    """Optimized face processing dengan lazy-loaded model dan error handling yang rapi"""
    try:
        img = cv2.imread(file_path)
        if img is None or img.size == 0:
            logger.warning(f"❌ Gagal membaca gambar: {file_path}")
            return []

        h, w = img.shape[:2]
        logger.info(f"📸 Processing image: {file_path} ({w}x{h})")

        face_detector = get_shared_detector()
        success, faces = face_detector.detect(img)

        if not success or faces is None or len(faces) == 0:
            logger.warning("❌ Tidak ada wajah terdeteksi.")
            return []

        logger.info(f"✅ {len(faces)} wajah terdeteksi dengan RetinaFace.")

        # Load resnet secara lazy
        resnet = FaceEncoder()
        device = FaceEncoder.get_device()

        embeddings = []

        for i, face in enumerate(faces):
            try:
                x, y, w_box, h_box = map(int, face[:4])
                confidence = float(face[4])

                # Validasi koordinat agar tidak keluar batas
                x1, y1 = max(x, 0), max(y, 0)
                x2, y2 = min(x + w_box, w), min(y + h_box, h)

                if x2 <= x1 or y2 <= y1:
                    logger.warning(f"⚠️ Invalid bbox untuk wajah {i}")
                    continue

                face_crop = img[y1:y2, x1:x2]
                if face_crop.size == 0:
                    logger.warning(f"⚠️ Wajah crop kosong (i={i})")
                    continue

                # Resize + konversi ke RGB
                face_crop_resized = cv2.resize(face_crop, (160, 160), interpolation=cv2.INTER_LINEAR)
                face_rgb = cv2.cvtColor(face_crop_resized, cv2.COLOR_BGR2RGB)

                # Convert ke tensor & normalisasi
                face_tensor = torch.from_numpy(face_rgb).permute(2, 0, 1).float()
                face_tensor = (face_tensor / 255.0 - 0.5) / 0.5
                face_tensor = face_tensor.unsqueeze(0).to(device)

                with torch.no_grad():
                    embedding_tensor = resnet(face_tensor).squeeze()
                    embedding = embedding_tensor.cpu().numpy().tolist()

                # Kalkulasi original bbox jika ada scale/pad
                if original_shape and pad and scale:
                    bbox_dict = {"x": int(x), "y": int(y), "w": int(w_box), "h": int(h_box)}
                    original_bbox = reverse_letterbox(
                        bbox=bbox_dict,
                        original_shape=original_shape,
                        resized_shape=img.shape[:2],
                        pad=pad,
                        scale=scale
                    )
                    original_bbox = convert_to_json_serializable(original_bbox)
                else:
                    original_bbox = {"x": int(x), "y": int(y), "w": int(w_box), "h": int(h_box)}

                embeddings.append({
                    "embedding": embedding,
                    "bbox": original_bbox,
                    "confidence": confidence
                })

            except Exception as e:
                logger.warning(f"⚠️ Error processing face {i}: {e}")
                continue

        return embeddings

    except Exception as e:
        logger.error(f"❌ Error processing image {file_path}: {e}")
        return []