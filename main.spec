# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all
import tensorflow as tf
import retinaface
import os

# Collect semua packages
tf_datas, tf_binaries, tf_hiddenimports = collect_all('tensorflow')
rf_datas, rf_binaries, rf_hiddenimports = collect_all('retinaface')
tf_keras_datas, tf_keras_binaries, tf_keras_hiddenimports = collect_all('tf_keras')

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=tf_binaries + rf_binaries + tf_keras_binaries,
    datas=[
        ('assets/', 'assets/'),
        ('ui/', 'ui/'),
        ('utils/', 'utils/'),
    ] + tf_datas + rf_datas + tf_keras_datas,
    hiddenimports=[
        # tf_keras modules (IMPORTANT!)
        'tf_keras',
        'tf_keras.models',
        'tf_keras.layers', 
        'tf_keras.utils',
        'tf_keras.backend',
        'tf_keras.applications',
        
        # UI modules
        'ui',
        'ui.admin_setup_dialogs',
        'ui.admin_login', 
        'ui.config_manager',
        'ui.explorer_window',
        'utils',
        'utils.face_detector',
        
        # PyQt5
        'PyQt5.sip',
        'PyQt5.QtCore',
        'PyQt5.QtGui', 
        'PyQt5.QtWidgets',
        
        # AI/ML
        'torch',
        'torchvision',
        'cv2',
        'numpy',
        'PIL',
        'PIL.Image',
        'retinaface',
        
        # TensorFlow
        'tensorflow',
        'tensorflow.keras',
        'tensorflow.keras.models',
        'tensorflow.keras.layers',
        
    ] + tf_hiddenimports + rf_hiddenimports + tf_keras_hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'matplotlib',
        'pandas',
        'jupyter',
        'notebook',
        'IPython',
        'scipy',
        'sklearn',
        'tensorboard',
    ],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='FaceSync - Finder',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='assets/ownize_logo.png'
)