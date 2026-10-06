"""
AirDeck Dedicated QR Pairing Window (Isolated GUI Process)
Runs safely in its own process without threading conflicts with Pystray or Uvicorn.
Supports display of both Direct LAN IP URL and ZeroConf mDNS Hostname.
"""

import sys
import tkinter as tk
from pathlib import Path

from PIL import ImageTk
import pyperclip
import qrcode


def show_pairing_window(url: str, pin: str, mdns_url: str = ""):
    try:
        root = tk.Tk()
        root.title("AirDeck Pro v3.0 — Pairing")
        root.geometry("380x620")
        root.configure(bg="#0c0c10")
        root.resizable(False, False)

        # Windows 10/11 Native Immersive Dark Titlebar
        if sys.platform == "win32":
            try:
                import ctypes
                root.update_idletasks()
                hwnd = ctypes.windll.user32.GetParent(root.winfo_id()) or root.winfo_id()
                val = ctypes.c_int(1)
                res = ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(val), ctypes.sizeof(val))
                if res != 0:
                    ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 19, ctypes.byref(val), ctypes.sizeof(val))
            except Exception:
                pass

        # Header Title
        lbl_title = tk.Label(
            root, text="AirDeck Pro v3.0", font=("Segoe UI", 16, "bold"),
            fg="#ffffff", bg="#0c0c10"
        )
        lbl_title.pack(pady=(16, 2))

        lbl_sub = tk.Label(
            root, text="Scan with Phone Camera to Connect", font=("Segoe UI", 9),
            fg="#8e8ea0", bg="#0c0c10"
        )
        lbl_sub.pack(pady=(0, 10))

        # QR Code Image
        qr = qrcode.QRCode(border=1, box_size=6)
        qr.add_data(url)
        qr.make(fit=True)
        qr_img = qr.make_image(fill_color="#000000", back_color="#ffffff")
        photo = ImageTk.PhotoImage(qr_img)

        qr_label = tk.Label(root, image=photo, bg="#0c0c10")
        qr_label.image = photo
        qr_label.pack(pady=4)

        # Security PIN Banner
        pin_frame = tk.Frame(root, bg="#161620", bd=1, relief="solid")
        pin_frame.pack(fill="x", padx=30, pady=8)

        tk.Label(
            pin_frame, text="SECURITY PAIRING PIN", font=("Segoe UI", 8, "bold"),
            fg="#6c63ff", bg="#161620"
        ).pack(pady=(6, 2))

        tk.Label(
            pin_frame, text=f"[  {pin}  ]", font=("Consolas", 18, "bold"),
            fg="#22c55e", bg="#161620"
        ).pack(pady=(0, 6))

        # mDNS Hostname indicator (if provided)
        if mdns_url:
            mdns_lbl = tk.Label(
                root, text=f"Local URL: {mdns_url}", font=("Segoe UI", 8),
                fg="#6c63ff", bg="#0c0c10", cursor="hand2"
            )
            mdns_lbl.pack(pady=(2, 6))
            mdns_lbl.bind("<Button-1>", lambda e: pyperclip.copy(mdns_url))

        # Action Buttons
        btn_frame = tk.Frame(root, bg="#0c0c10")
        btn_frame.pack(fill="x", padx=30, pady=(4, 12))

        def copy_url():
            pyperclip.copy(url)
            btn_copy_url.config(text="Copied!")
            root.after(1500, lambda: btn_copy_url.config(text="Copy Link"))

        def copy_pin():
            pyperclip.copy(pin)
            btn_copy_pin.config(text="Copied!")
            root.after(1500, lambda: btn_copy_pin.config(text="Copy PIN"))

        btn_copy_url = tk.Button(
            btn_frame, text="Copy Link", command=copy_url,
            bg="#6c63ff", fg="#ffffff", font=("Segoe UI", 9, "bold"),
            relief="flat", padx=12, pady=6, cursor="hand2"
        )
        btn_copy_url.pack(side="left", expand=True, fill="x", padx=3)

        btn_copy_pin = tk.Button(
            btn_frame, text="Copy PIN", command=copy_pin,
            bg="#1f1f2e", fg="#ffffff", font=("Segoe UI", 9),
            relief="flat", padx=12, pady=6, cursor="hand2"
        )
        btn_copy_pin.pack(side="left", expand=True, fill="x", padx=3)

        def quit_entire_app():
            import os
            import time
            try:
                import urllib.request
                import ssl
                import re
                port_match = re.search(r":(\d+)", url)
                port = port_match.group(1) if port_match else "8765"
                ctx = ssl._create_unverified_context()
                req = urllib.request.Request(f"https://127.0.0.1:{port}/api/system/shutdown", data=b"{}", method="POST")
                urllib.request.urlopen(req, context=ctx, timeout=1.0)
            except Exception:
                pass
            root.destroy()
            time.sleep(0.1)
            os._exit(0)

        bottom_btn_frame = tk.Frame(root, bg="#0c0c10")
        bottom_btn_frame.pack(fill="x", padx=24, pady=(4, 12))

        tk.Button(
            bottom_btn_frame, text="Minimize to Tray", command=root.destroy,
            bg="#181822", fg="#8e8ea0", font=("Segoe UI", 8),
            relief="flat", padx=10, pady=4, cursor="hand2"
        ).pack(side="left", expand=True, fill="x", padx=(0, 4))

        tk.Button(
            bottom_btn_frame, text="Quit AirDeck", command=quit_entire_app,
            bg="#2a1215", fg="#ef4444", font=("Segoe UI", 8, "bold"),
            activebackground="#dc2626", activeforeground="#ffffff",
            relief="flat", padx=10, pady=4, cursor="hand2"
        ).pack(side="left", expand=True, fill="x", padx=(4, 0))

        root.mainloop()
    except Exception as e:
        print(f"[GUI ERROR] Failed to display QR window: {e}")


# Alias for compatibility across entrypoints
show_qr_window = show_pairing_window


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    target_url = args[0] if len(args) > 0 else ""
    target_pin = args[1] if len(args) > 1 else ""
    target_mdns = args[2] if len(args) > 2 else ""
    if target_url and target_pin:
        show_pairing_window(target_url, target_pin, target_mdns)
