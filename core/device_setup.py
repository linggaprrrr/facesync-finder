# device_setup.py - SIMPLE FIX
import os
import torch
from dotenv import load_dotenv

load_dotenv()
API_BASE = "https://api.ownize.app"

class FaceEncoder:
    _resnet = None
    _device = "cpu"

    def __new__(cls):
        if cls._resnet is None:
            # ✅ SIMPLE: Load model hanya saat pertama kali dipakai
            print("Loading face recognition model...")  # User feedback
            
            # Set PyTorch untuk lebih cepat
            torch.set_grad_enabled(False)
            torch.set_num_threads(4)
            
            from facenet_pytorch import InceptionResnetV1
            cls._resnet = InceptionResnetV1(pretrained='vggface2').eval().to(cls._device)
            
            print("Model loaded!")
        return cls._resnet

    @classmethod
    def get_device(cls):
        return cls._device

    @classmethod
    def get_api_base(cls):
        return API_BASE