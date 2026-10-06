# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['D:\\Other\\AirDeck\\companion_bridge\\tray_app.py'],
    pathex=[],
    binaries=[],
    datas=[('D:\\Other\\AirDeck\\companion_bridge\\static', 'static'), ('D:\\Other\\AirDeck\\companion_bridge\\core', 'core')],
    hiddenimports=['core', 'core.config', 'core.crypto', 'core.network', 'core.input_driver', 'core.security', 'core.qr_window', 'core.discovery', 'core.media_driver', 'core.telemetry', 'core.macro_manager', 'core.autostart', 'core.firewall', 'core.control_panel', 'core.logger', 'core.single_instance', 'psutil', 'winreg', 'zeroconf', 'uvicorn.logging', 'uvicorn.loops', 'uvicorn.loops.auto', 'uvicorn.protocols', 'uvicorn.protocols.http', 'uvicorn.protocols.http.auto', 'uvicorn.protocols.websockets', 'uvicorn.protocols.websockets.auto', 'uvicorn.lifespan', 'uvicorn.lifespan.on', 'pystray', 'pynput.keyboard._win32', 'pynput.mouse._win32', 'cryptography', 'pyperclip', 'pyaudio', 'pyaudiowpatch'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['cv2'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='AirDeck',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['D:\\Other\\AirDeck\\companion_bridge\\airdeck.ico'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='AirDeck',
)
