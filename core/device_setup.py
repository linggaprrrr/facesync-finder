# face_encoder.py

import os
import torch
from dotenv import load_dotenv
from facenet_pytorch import InceptionResnetV1

load_dotenv()
API_BASE = "https://api.ownize.app"

class FaceEncoder:
    _resnet = None
    _device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    def __new__(cls):
        if cls._resnet is None:
            cls._resnet = InceptionResnetV1(pretrained='vggface2').eval().to(cls._device)
        return cls._resnet

    @classmethod
    def get_device(cls):
        return cls._device

    @classmethod
    def get_api_base(cls):
        return API_BASE
