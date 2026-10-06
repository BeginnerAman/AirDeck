"""
AirDeck Pro — Modern Windows Desktop Control Panel & Settings Dashboard (v2.0)
Provides a native, sleek dark-mode management interface for PC status,
device pairing, driver health, Stream Deck macros, live telemetry, and autostart settings.
"""

import os
import socket
import subprocess
import sys
import threading
import time
import tkinter as tk
from tkinter import ttk, messagebox
import webbrowser
from pathlib import Path

# Add project root to sys.path if run directly
BASE_DIR = Path(__file__).parent.parent.resolve()
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from core.config import config
from core.network import get_primary_lan_ip
from core.security import security_engine
from core.media_driver import media_driver
from core.macro_manager import macro_manager
from core.telemetry import get_system_telemetry
from core.autostart import is_autostart_enabled, set_autostart
from core.firewall import check_firewall_rule, add_firewall_rule_elevated, generate_firewall_script

# ── Color Palette (Modern Dark Slate & Indigo) ──────────────────────────
BG_MAIN = "#0f111a"
BG_CARD = "#1a1d2e"
BG_CARD_LIGHT = "#24283f"
BORDER_COLOR = "#2e3450"
ACCENT_COLOR = "#6c63ff"
ACCENT_HOVER = "#584fe3"
TEXT_PRIMARY = "#ffffff"
TEXT_MUTED = "#94a3b8"
SUCCESS_GREEN = "#10b981"
WARNING_AMBER = "#f59e0b"
DANGER_RED = "#ef4444"

def _add_hover(widget, hover_bg, normal_bg):
    """Add hover color effect to a widget."""
    widget.bind("<Enter>", lambda e: widget.config(bg=hover_bg))
    widget.bind("<Leave>", lambda e: widget.config(bg=normal_bg))


class ModernControlPanel:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("AirDeck Pro v3.0 — Control Panel & Dashboard")
        self.root.geometry("820x640")
        self.root.minsize(760, 580)
        self.root.configure(bg=BG_MAIN)

        # Application state — prefer env vars from parent tray process (subprocess has its own SecurityEngine)
        self.ip = get_primary_lan_ip()
        self.port = int(os.environ.get("AIRDECK_PORT", config.get("server.port", 8765)))
        self.hostname = socket.gethostname()
        self.mdns_host = f"airdeck-{self.hostname.lower()}.local"
        _token = os.environ.get("AIRDECK_TOKEN", security_engine.master_token)
        self.pin = os.environ.get("AIRDECK_PIN", security_engine.pairing_pin)
        self.auto_pair_url = f"https://{self.ip}:{self.port}/?token={_token}"

        self._telemetry_running = True

        self._apply_dark_titlebar()
        self._setup_styles()
        self._build_header()
        self._build_tabs()
        self._start_telemetry_loop()

        # Handle window close
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def _apply_dark_titlebar(self):
        """Enable Windows 10/11 native immersive dark titlebar and rounded styling."""
        if sys.platform == "win32":
            try:
                import ctypes
                self.root.update_idletasks()
                hwnd = ctypes.windll.user32.GetParent(self.root.winfo_id()) or self.root.winfo_id()
                val = ctypes.c_int(1)
                res = ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(val), ctypes.sizeof(val))
                if res != 0:
                    ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 19, ctypes.byref(val), ctypes.sizeof(val))
            except Exception:
                pass

    def _setup_styles(self):
        style = ttk.Style()
        style.theme_use("clam")

        # Notebook tabs
        style.configure(
            "TNotebook",
            background=BG_MAIN,
            borderwidth=0,
            tabmargins=[10, 5, 10, 0],
        )
        style.configure(
            "TNotebook.Tab",
            background=BG_CARD,
            foreground=TEXT_MUTED,
            padding=[16, 8],
            font=("Segoe UI", 10, "bold"),
            borderwidth=0,
        )
        style.map(
            "TNotebook.Tab",
            background=[("selected", ACCENT_COLOR)],
            foreground=[("selected", "#ffffff")],
        )

        # Progressbar
        style.configure(
            "Telemetry.Horizontal.TProgressbar",
            troughcolor=BG_CARD_LIGHT,
            background=ACCENT_COLOR,
            thickness=12,
            borderwidth=0,
        )

        # Treeview (Macro table)
        style.configure(
            "Treeview",
            background=BG_CARD,
            foreground=TEXT_PRIMARY,
            fieldbackground=BG_CARD,
            rowheight=32,
            font=("Segoe UI", 9),
            borderwidth=0,
        )
        style.configure(
            "Treeview.Heading",
            background=BG_CARD_LIGHT,
            foreground=TEXT_PRIMARY,
            font=("Segoe UI", 9, "bold"),
            borderwidth=0,
        )
        style.map("Treeview", background=[("selected", ACCENT_COLOR)])

    def _build_header(self):
        header = tk.Frame(self.root, bg=BG_CARD, height=70, padx=20, pady=12)
        header.pack(fill="x", side="top")

        # Brand / Title
        brand_frame = tk.Frame(header, bg=BG_CARD)
        brand_frame.pack(side="left")

        title_lbl = tk.Label(
            brand_frame,
            text="AIRDECK PRO",
            font=("Segoe UI", 16, "bold"),
            fg=TEXT_PRIMARY,
            bg=BG_CARD,
        )
        title_lbl.pack(side="left")

        ver_lbl = tk.Label(
            brand_frame,
            text=" v3.0 Enterprise",
            font=("Segoe UI", 9),
            fg=ACCENT_COLOR,
            bg=BG_CARD,
        )
        ver_lbl.pack(side="left", padx=(4, 0), pady=(4, 0))

        # Right side status pill & Shutdown button
        status_frame = tk.Frame(header, bg=BG_CARD)
        status_frame.pack(side="right")

        dot = tk.Label(status_frame, text="●", font=("Segoe UI", 12), fg=SUCCESS_GREEN, bg=BG_CARD)
        dot.pack(side="left", padx=(0, 4))

        status_text = tk.Label(
            status_frame,
            text=f"Online — {self.ip}:{self.port}",
            font=("Segoe UI", 10, "bold"),
            fg=TEXT_PRIMARY,
            bg=BG_CARD,
        )
        status_text.pack(side="left", padx=(0, 10))

        btn_exit = tk.Button(
            status_frame,
            text="Exit AirDeck",
            font=("Segoe UI", 9, "bold"),
            bg="#dc2626",
            fg="#ffffff",
            activebackground="#b91c1c",
            activeforeground="#ffffff",
            relief="flat",
            padx=10,
            pady=3,
            cursor="hand2",
            command=self._on_exit_entire_app,
        )
        btn_exit.pack(side="left")
        _add_hover(btn_exit, "#b91c1c", "#dc2626")

        # Subtle bottom separator
        separator = tk.Frame(self.root, bg=ACCENT_COLOR, height=2)
        separator.pack(fill="x")

    def _on_exit_entire_app(self):
        ans = messagebox.askyesno(
            "Exit AirDeck Pro v3.0",
            "Are you sure you want to shut down AirDeck and stop all background services completely?",
            parent=self.root
        )
        if ans:
            self._telemetry_running = False
            try:
                import urllib.request
                import ssl
                ctx = ssl._create_unverified_context()
                req = urllib.request.Request(f"https://127.0.0.1:{self.port}/api/system/shutdown", data=b"{}", method="POST")
                urllib.request.urlopen(req, context=ctx, timeout=1.0)
            except Exception:
                pass
            self.root.destroy()
            time.sleep(0.1)
            os._exit(0)

    def _build_tabs(self):
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True, padx=16, pady=12)

        # Tab Frames
        self.tab_overview = tk.Frame(self.notebook, bg=BG_MAIN, padx=16, pady=16)
        self.tab_macros = tk.Frame(self.notebook, bg=BG_MAIN, padx=16, pady=16)
        self.tab_telemetry = tk.Frame(self.notebook, bg=BG_MAIN, padx=16, pady=16)
        self.tab_settings = tk.Frame(self.notebook, bg=BG_MAIN, padx=16, pady=16)

        self.notebook.add(self.tab_overview, text=" Connectivity & Pairing ")
        self.notebook.add(self.tab_macros, text=" Stream Deck Studio ")
        self.notebook.add(self.tab_telemetry, text=" PC Diagnostics ")
        self.notebook.add(self.tab_settings, text=" Settings & Startup ")

        self._render_overview_tab()
        self._render_macros_tab()
        self._render_telemetry_tab()
        self._render_settings_tab()

    # ════════════════════════════════════════════════════════════════
    #  TAB 1: CONNECTIVITY & PAIRING
    # ════════════════════════════════════════════════════════════════
    def _render_overview_tab(self):
        p = self.tab_overview

        # Card: Quick Pairing
        card_pair = tk.Frame(p, bg=BG_CARD, highlightbackground=BORDER_COLOR, highlightthickness=1, padx=16, pady=16)
        card_pair.pack(fill="x", pady=(0, 14))

        pair_title = tk.Label(
            card_pair,
            text="Mobile Pairing & Security PIN",
            font=("Segoe UI", 12, "bold"),
            fg=TEXT_PRIMARY,
            bg=BG_CARD,
        )
        pair_title.pack(anchor="w", pady=(0, 8))

        row1 = tk.Frame(card_pair, bg=BG_CARD)
        row1.pack(fill="x", pady=4)

        tk.Label(row1, text="Pairing PIN:", font=("Segoe UI", 10), fg=TEXT_MUTED, bg=BG_CARD).pack(side="left")

        self.pin_label = tk.Label(
            row1,
            text=f"  {self.pin}  ",
            font=("Segoe UI", 14, "bold"),
            fg=ACCENT_COLOR,
            bg=BG_CARD_LIGHT,
            padx=10,
            pady=2,
        )
        self.pin_label.pack(side="left", padx=12)

        btn_regen = tk.Button(
            row1,
            text="Regenerate PIN",
            font=("Segoe UI", 9),
            bg=BG_CARD_LIGHT,
            fg=TEXT_PRIMARY,
            relief="flat",
            padx=10,
            pady=4,
            command=self._on_regenerate_pin,
            cursor="hand2",
        )
        btn_regen.pack(side="left", padx=4)
        _add_hover(btn_regen, "#2e3450", BG_CARD_LIGHT)

        btn_qr = tk.Button(
            row1,
            text="Show Pairing QR Code",
            font=("Segoe UI", 9, "bold"),
            bg=ACCENT_COLOR,
            fg="#ffffff",
            relief="flat",
            padx=14,
            pady=4,
            command=self._on_show_qr,
            cursor="hand2",
        )
        btn_qr.pack(side="right")
        _add_hover(btn_qr, ACCENT_HOVER, ACCENT_COLOR)

        # Direct Link Row
        row2 = tk.Frame(card_pair, bg=BG_CARD)
        row2.pack(fill="x", pady=(10, 4))

        tk.Label(row2, text="Auto-Pair Link:", font=("Segoe UI", 9), fg=TEXT_MUTED, bg=BG_CARD).pack(side="left")
        self.link_entry = tk.Entry(
            row2,
            font=("Segoe UI", 9),
            bg=BG_CARD_LIGHT,
            fg=TEXT_PRIMARY,
            insertbackground="#ffffff",
            relief="flat",
        )
        self.link_entry.insert(0, self.auto_pair_url)
        self.link_entry.configure(state="readonly")
        self.link_entry.pack(side="left", fill="x", expand=True, padx=8)

        btn_copy = tk.Button(
            row2,
            text="Copy Link",
            font=("Segoe UI", 9),
            bg=BG_CARD_LIGHT,
            fg=TEXT_PRIMARY,
            relief="flat",
            padx=10,
            command=self._on_copy_link,
            cursor="hand2",
        )
        btn_copy.pack(side="right", padx=2)
        _add_hover(btn_copy, "#2e3450", BG_CARD_LIGHT)

        btn_open = tk.Button(
            row2,
            text="Open in Browser",
            font=("Segoe UI", 9),
            bg=BG_CARD_LIGHT,
            fg=TEXT_PRIMARY,
            relief="flat",
            padx=10,
            command=lambda: webbrowser.open(self.auto_pair_url),
            cursor="hand2",
        )
        btn_open.pack(side="right", padx=2)
        _add_hover(btn_open, "#2e3450", BG_CARD_LIGHT)

        # SSL Root Certificate Profile Row
        row_cert = tk.Frame(card_pair, bg=BG_CARD)
        row_cert.pack(fill="x", pady=(6, 2))
        tk.Label(row_cert, text="SSL Mobile Profile:", font=("Segoe UI", 9), fg=TEXT_MUTED, bg=BG_CARD).pack(side="left")
        cert_url = f"https://{self.ip}:{self.port}/cert"
        cert_entry = tk.Entry(row_cert, font=("Segoe UI", 9), bg=BG_CARD_LIGHT, fg=TEXT_PRIMARY, relief="flat")
        cert_entry.insert(0, cert_url)
        cert_entry.configure(state="readonly")
        cert_entry.pack(side="left", fill="x", expand=True, padx=8)

        def _copy_cert_link():
            import pyperclip
            pyperclip.copy(cert_url)
            messagebox.showinfo("Copied", "SSL Certificate download link copied to clipboard!\nOpen this link on your phone to install trusted root profile.")

        tk.Button(row_cert, text="Copy Cert URL", font=("Segoe UI", 9), bg=BG_CARD_LIGHT, fg=TEXT_PRIMARY, relief="flat", padx=10, command=_copy_cert_link, cursor="hand2").pack(side="right", padx=2)

        # Card: Hardware Drivers Diagnostic
        card_hw = tk.Frame(p, bg=BG_CARD, highlightbackground=BORDER_COLOR, highlightthickness=1, padx=16, pady=16)
        card_hw.pack(fill="x", pady=(0, 14))

        hw_title = tk.Label(
            card_hw,
            text="Hardware Virtual Drivers Health",
            font=("Segoe UI", 12, "bold"),
            fg=TEXT_PRIMARY,
            bg=BG_CARD,
        )
        hw_title.pack(anchor="w", pady=(0, 8))

        hw_status = media_driver.get_hardware_status()

        # Cam row
        cam_row = tk.Frame(card_hw, bg=BG_CARD)
        cam_row.pack(fill="x", pady=4)
        tk.Label(cam_row, text="Virtual Webcam Sink:", font=("Segoe UI", 10), fg=TEXT_MUTED, bg=BG_CARD).pack(side="left")
        vcam_ok = hw_status["webcam"]["available"]
        vcam_text = f"✓ {hw_status['webcam']['driver']}" if vcam_ok else "✗ Missing (OBS/Unity)"
        vcam_color = SUCCESS_GREEN if vcam_ok else WARNING_AMBER
        tk.Label(cam_row, text=vcam_text, font=("Segoe UI", 10, "bold"), fg=vcam_color, bg=BG_CARD).pack(side="right")

        # Mic row
        mic_row = tk.Frame(card_hw, bg=BG_CARD)
        mic_row.pack(fill="x", pady=4)
        tk.Label(mic_row, text="Virtual Microphone (Zoom/Meet):", font=("Segoe UI", 10), fg=TEXT_MUTED, bg=BG_CARD).pack(side="left")
        mic_ok = hw_status["microphone"]["available"]
        mic_text = f"✓ {hw_status['microphone']['driver']}" if mic_ok else "✗ Missing (VB-Audio Cable)"
        mic_color = SUCCESS_GREEN if mic_ok else WARNING_AMBER
        tk.Label(mic_row, text=mic_text, font=("Segoe UI", 10, "bold"), fg=mic_color, bg=BG_CARD).pack(side="right")

        # Speaker row (Wireless loopback)
        spk_row = tk.Frame(card_hw, bg=BG_CARD)
        spk_row.pack(fill="x", pady=4)
        tk.Label(spk_row, text="Extended Speaker (WASAPI Loopback):", font=("Segoe UI", 10), fg=TEXT_MUTED, bg=BG_CARD).pack(side="left")
        spk_ok = hw_status.get("speaker", {}).get("available", False)
        spk_text = "✓ Ready (Windows System Audio)" if spk_ok else "✗ WASAPI Loopback Unavailable"
        spk_color = SUCCESS_GREEN if spk_ok else WARNING_AMBER
        tk.Label(spk_row, text=spk_text, font=("Segoe UI", 10, "bold"), fg=spk_color, bg=BG_CARD).pack(side="right")

        if not mic_ok:
            btn_install_mic = tk.Button(
                card_hw,
                text="Download Free VB-Audio Virtual Cable Driver (Required for Virtual Mic)",
                font=("Segoe UI", 9, "underline"),
                bg=BG_CARD,
                fg=ACCENT_COLOR,
                bd=0,
                cursor="hand2",
                command=lambda: webbrowser.open("https://vb-audio.com/Cable/"),
            )
            btn_install_mic.pack(anchor="e", pady=(4, 0))

    def _on_regenerate_pin(self):
        new_pin = security_engine.regenerate_pin()
        self.pin = new_pin
        self.pin_label.config(text=f"  {new_pin}  ")
        messagebox.showinfo("PIN Regenerated", f"New Security PIN: {new_pin}\nPrevious PINs have been invalidated.")

    def _on_show_qr(self):
        try:
            if getattr(sys, "frozen", False):
                cmd = [sys.executable, "--qr-window", self.auto_pair_url, self.pin, f"https://{self.mdns_host}:{self.port}"]
            else:
                qr_script = BASE_DIR / "core" / "qr_window.py"
                cmd = [sys.executable, str(qr_script), self.auto_pair_url, self.pin, f"https://{self.mdns_host}:{self.port}"]
            subprocess.Popen(
                cmd,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
            )
        except Exception:
            webbrowser.open(self.auto_pair_url)

    def _on_copy_link(self):
        import pyperclip
        pyperclip.copy(self.auto_pair_url)
        messagebox.showinfo("Copied", "Auto-pair URL copied to clipboard!")

    # ════════════════════════════════════════════════════════════════
    #  TAB 2: STREAM DECK STUDIO
    # ════════════════════════════════════════════════════════════════
    def _render_macros_tab(self):
        p = self.tab_macros

        # Toolbar
        toolbar = tk.Frame(p, bg=BG_MAIN)
        toolbar.pack(fill="x", pady=(0, 10))

        tk.Label(
            toolbar,
            text="Active Macros Grid",
            font=("Segoe UI", 12, "bold"),
            fg=TEXT_PRIMARY,
            bg=BG_MAIN,
        ).pack(side="left")

        btn_reset = tk.Button(
            toolbar,
            text="Reset Defaults",
            font=("Segoe UI", 9),
            bg=BG_CARD_LIGHT,
            fg=TEXT_PRIMARY,
            relief="flat",
            padx=10,
            pady=3,
            command=self._on_macro_reset,
            cursor="hand2",
        )
        btn_reset.pack(side="right", padx=4)
        _add_hover(btn_reset, "#2e3450", BG_CARD_LIGHT)

        btn_del = tk.Button(
            toolbar,
            text="Delete Selected",
            font=("Segoe UI", 9),
            bg=DANGER_RED,
            fg="#ffffff",
            relief="flat",
            padx=10,
            pady=3,
            command=self._on_macro_delete,
            cursor="hand2",
        )
        btn_del.pack(side="right", padx=4)
        _add_hover(btn_del, "#b91c1c", DANGER_RED)

        btn_run = tk.Button(
            toolbar,
            text="▶ Test Run",
            font=("Segoe UI", 9, "bold"),
            bg=ACCENT_COLOR,
            fg="#ffffff",
            relief="flat",
            padx=12,
            pady=3,
            command=self._on_macro_test,
            cursor="hand2",
        )
        btn_run.pack(side="right", padx=4)
        _add_hover(btn_run, ACCENT_HOVER, ACCENT_COLOR)

        # Macro Treeview Table
        cols = ("id", "label", "type", "target", "color")
        self.macro_tree = ttk.Treeview(p, columns=cols, show="headings", height=8)
        self.macro_tree.heading("id", text="ID")
        self.macro_tree.heading("label", text="Button Label")
        self.macro_tree.heading("type", text="Action Type")
        self.macro_tree.heading("target", text="Target Command / Path / URL")
        self.macro_tree.heading("color", text="Color")

        self.macro_tree.column("id", width=90, anchor="center")
        self.macro_tree.column("label", width=140)
        self.macro_tree.column("type", width=90, anchor="center")
        self.macro_tree.column("target", width=300)
        self.macro_tree.column("color", width=80, anchor="center")

        self.macro_tree.pack(fill="both", expand=True, pady=(0, 10))

        # Add New Macro Card
        add_frame = tk.Frame(p, bg=BG_CARD, highlightbackground=BORDER_COLOR, highlightthickness=1, padx=14, pady=12)
        add_frame.pack(fill="x")

        tk.Label(add_frame, text="Add New Button:", font=("Segoe UI", 10, "bold"), fg=TEXT_PRIMARY, bg=BG_CARD).grid(row=0, column=0, sticky="w", pady=4)

        tk.Label(add_frame, text="Label:", font=("Segoe UI", 9), fg=TEXT_MUTED, bg=BG_CARD).grid(row=1, column=0, sticky="w")
        self.entry_m_label = tk.Entry(add_frame, width=15, bg=BG_CARD_LIGHT, fg=TEXT_PRIMARY, relief="flat")
        self.entry_m_label.grid(row=1, column=1, padx=6, pady=4)

        tk.Label(add_frame, text="Type:", font=("Segoe UI", 9), fg=TEXT_MUTED, bg=BG_CARD).grid(row=1, column=2, sticky="w")
        self.combo_m_type = ttk.Combobox(add_frame, values=["action", "hotkey", "launch", "url", "text"], width=10, state="readonly")
        self.combo_m_type.set("hotkey")
        self.combo_m_type.grid(row=1, column=3, padx=6, pady=4)

        tk.Label(add_frame, text="Target:", font=("Segoe UI", 9), fg=TEXT_MUTED, bg=BG_CARD).grid(row=1, column=4, sticky="w")
        self.entry_m_target = tk.Entry(add_frame, width=24, bg=BG_CARD_LIGHT, fg=TEXT_PRIMARY, relief="flat")
        self.entry_m_target.grid(row=1, column=5, padx=6, pady=4)

        btn_add = tk.Button(
            add_frame,
            text="+ Add Button",
            font=("Segoe UI", 9, "bold"),
            bg=ACCENT_COLOR,
            fg="#ffffff",
            relief="flat",
            padx=12,
            pady=2,
            command=self._on_macro_add,
            cursor="hand2",
        )
        btn_add.grid(row=1, column=6, padx=8, pady=4)
        _add_hover(btn_add, ACCENT_HOVER, ACCENT_COLOR)

        self._refresh_macro_tree()

    def _refresh_macro_tree(self):
        for item in self.macro_tree.get_children():
            self.macro_tree.delete(item)

        macros = macro_manager.get_macros()
        for m in macros:
            self.macro_tree.insert(
                "",
                "end",
                iid=m.get("id"),
                values=(
                    m.get("id"),
                    m.get("label"),
                    m.get("type"),
                    m.get("target"),
                    m.get("color", "#6C63FF"),
                ),
            )

    def _on_macro_add(self):
        lbl = self.entry_m_label.get().strip()
        mtype = self.combo_m_type.get().strip()
        target = self.entry_m_target.get().strip()

        if not lbl or not target:
            messagebox.showwarning("Incomplete", "Please provide both Label and Target.")
            return

        macro_manager.add_macro({
            "label": lbl,
            "type": mtype,
            "target": target,
            "icon": "activity",
            "color": "#6366f1",
        })

        self.entry_m_label.delete(0, "end")
        self.entry_m_target.delete(0, "end")
        self._refresh_macro_tree()
        messagebox.showinfo("Success", f"Added Stream Deck macro: {lbl}")

    def _on_macro_delete(self):
        sel = self.macro_tree.selection()
        if not sel:
            messagebox.showinfo("Selection Required", "Please select a macro from the table to delete.")
            return

        macro_id = sel[0]
        if messagebox.askyesno("Confirm Delete", f"Delete macro '{macro_id}'?"):
            macro_manager.delete_macro(macro_id)
            self._refresh_macro_tree()

    def _on_macro_test(self):
        sel = self.macro_tree.selection()
        if not sel:
            messagebox.showinfo("Selection Required", "Please select a macro from the table to test.")
            return

        macro_id = sel[0]
        ok, msg = macro_manager.execute_macro(macro_id)
        if ok:
            messagebox.showinfo("Test Execution", f"Executed successfully:\n{msg}")
        else:
            messagebox.showerror("Execution Failed", msg)

    def _on_macro_reset(self):
        if messagebox.askyesno("Reset Defaults", "Reset all Stream Deck buttons to factory defaults?"):
            macro_manager.reset_defaults()
            self._refresh_macro_tree()

    # ════════════════════════════════════════════════════════════════
    #  TAB 3: PC DIAGNOSTICS & TELEMETRY
    # ════════════════════════════════════════════════════════════════
    def _render_telemetry_tab(self):
        p = self.tab_telemetry

        # Telemetry Gauges Card
        card_gauges = tk.Frame(p, bg=BG_CARD, highlightbackground=BORDER_COLOR, highlightthickness=1, padx=16, pady=16)
        card_gauges.pack(fill="x", pady=(0, 14))

        tk.Label(
            card_gauges,
            text="Live PC Performance Metrics",
            font=("Segoe UI", 12, "bold"),
            fg=TEXT_PRIMARY,
            bg=BG_CARD,
        ).pack(anchor="w", pady=(0, 12))

        # CPU Row
        cpu_header = tk.Frame(card_gauges, bg=BG_CARD)
        cpu_header.pack(fill="x")
        tk.Label(cpu_header, text="CPU Utilization:", font=("Segoe UI", 10), fg=TEXT_MUTED, bg=BG_CARD).pack(side="left")
        self.lbl_cpu_val = tk.Label(cpu_header, text="0%", font=("Segoe UI", 10, "bold"), fg=TEXT_PRIMARY, bg=BG_CARD)
        self.lbl_cpu_val.pack(side="right")

        self.pb_cpu = ttk.Progressbar(card_gauges, style="Telemetry.Horizontal.TProgressbar", maximum=100)
        self.pb_cpu.pack(fill="x", pady=(4, 12))

        # RAM Row
        ram_header = tk.Frame(card_gauges, bg=BG_CARD)
        ram_header.pack(fill="x")
        tk.Label(ram_header, text="Memory (RAM) Usage:", font=("Segoe UI", 10), fg=TEXT_MUTED, bg=BG_CARD).pack(side="left")
        self.lbl_ram_val = tk.Label(ram_header, text="0% (0/0 GB)", font=("Segoe UI", 10, "bold"), fg=TEXT_PRIMARY, bg=BG_CARD)
        self.lbl_ram_val.pack(side="right")

        self.pb_ram = ttk.Progressbar(card_gauges, style="Telemetry.Horizontal.TProgressbar", maximum=100)
        self.pb_ram.pack(fill="x", pady=(4, 12))

        # Battery & Uptime Row
        details_row = tk.Frame(card_gauges, bg=BG_CARD)
        details_row.pack(fill="x", pady=4)

        self.lbl_batt = tk.Label(details_row, text="Battery: Detecting...", font=("Segoe UI", 9), fg=TEXT_MUTED, bg=BG_CARD)
        self.lbl_batt.pack(side="left")

        self.lbl_uptime = tk.Label(details_row, text="Uptime: 0h 0m", font=("Segoe UI", 9), fg=TEXT_MUTED, bg=BG_CARD)
        self.lbl_uptime.pack(side="right")

        # Windows Firewall Card
        card_fw = tk.Frame(p, bg=BG_CARD, highlightbackground=BORDER_COLOR, highlightthickness=1, padx=16, pady=16)
        card_fw.pack(fill="x")

        tk.Label(
            card_fw,
            text="Windows Defender Firewall Integration",
            font=("Segoe UI", 12, "bold"),
            fg=TEXT_PRIMARY,
            bg=BG_CARD,
        ).pack(anchor="w", pady=(0, 6))

        fw_ok = check_firewall_rule()
        fw_status_str = "✓ AirDeck Inbound Rule Active" if fw_ok else "⚠ Inbound Rule Not Detected"
        fw_color = SUCCESS_GREEN if fw_ok else WARNING_AMBER

        fw_row = tk.Frame(card_fw, bg=BG_CARD)
        fw_row.pack(fill="x", pady=4)

        self.lbl_fw = tk.Label(fw_row, text=fw_status_str, font=("Segoe UI", 10, "bold"), fg=fw_color, bg=BG_CARD)
        self.lbl_fw.pack(side="left")

        btn_add_fw = tk.Button(
            fw_row,
            text="Authorize Firewall Rule (1-Click)",
            font=("Segoe UI", 9, "bold"),
            bg=ACCENT_COLOR,
            fg="#ffffff",
            relief="flat",
            padx=12,
            pady=3,
            command=self._on_authorize_firewall,
            cursor="hand2",
        )
        btn_add_fw.pack(side="right")
        _add_hover(btn_add_fw, ACCENT_HOVER, ACCENT_COLOR)

    def _on_authorize_firewall(self):
        script_path = generate_firewall_script()
        ok = add_firewall_rule_elevated()
        if ok:
            messagebox.showinfo(
                "Firewall Updated",
                "Firewall elevation command submitted.\nYour phone can now discover and connect to AirDeck.",
            )
        else:
            messagebox.showinfo(
                "Firewall Script Generated",
                f"Generated helper script at:\n{script_path}\nPlease right-click and run as Administrator.",
            )

    def _start_telemetry_loop(self):
        def _poll():
            while self._telemetry_running:
                try:
                    data = get_system_telemetry()
                    if data.get("available") and hasattr(self, "lbl_cpu_val"):
                        cpu = data.get("cpu_percent", 0.0)
                        ram = data.get("ram_percent", 0.0)
                        used = data.get("ram_used_gb", 0.0)
                        tot = data.get("ram_total_gb", 0.0)
                        uptime_s = data.get("uptime_seconds", 0)
                        hours = uptime_s // 3600
                        mins = (uptime_s % 3600) // 60

                        batt = data.get("battery")
                        batt_str = f"Battery: {batt['percent']}% ({'Plugged In' if batt['power_plugged'] else 'On Battery'})" if batt else "Power: Desktop (AC Source)"

                        # Schedule UI update on main thread
                        self.root.after(0, lambda c=cpu, r=ram, u=used, t=tot, b=batt_str, h=hours, m=mins: self._update_telemetry_ui(c, r, u, t, b, h, m))
                except Exception:
                    pass
                time.sleep(1.5)

        t = threading.Thread(target=_poll, daemon=True, name="ControlPanelTelemetry")
        t.start()

    def _update_telemetry_ui(self, cpu, ram, used, tot, batt_str, hours, mins):
        if not self._telemetry_running:
            return
        try:
            self.lbl_cpu_val.config(text=f"{cpu}%")
            self.pb_cpu["value"] = cpu

            self.lbl_ram_val.config(text=f"{ram}% ({used}/{tot} GB)")
            self.pb_ram["value"] = ram

            self.lbl_batt.config(text=batt_str)
            self.lbl_uptime.config(text=f"PC Uptime: {hours}h {mins}m")
        except Exception:
            pass

    # ════════════════════════════════════════════════════════════════
    #  TAB 4: SETTINGS & AUTOSTART
    # ════════════════════════════════════════════════════════════════
    def _render_settings_tab(self):
        p = self.tab_settings

        card_settings = tk.Frame(p, bg=BG_CARD, highlightbackground=BORDER_COLOR, highlightthickness=1, padx=16, pady=16)
        card_settings.pack(fill="x")

        tk.Label(
            card_settings,
            text="Windows System & Startup Settings",
            font=("Segoe UI", 12, "bold"),
            fg=TEXT_PRIMARY,
            bg=BG_CARD,
        ).pack(anchor="w", pady=(0, 12))

        # Autostart Checkbox
        self.var_autostart = tk.BooleanVar(value=is_autostart_enabled())
        chk_autostart = tk.Checkbutton(
            card_settings,
            text="Start AirDeck automatically when Windows boots",
            variable=self.var_autostart,
            font=("Segoe UI", 10),
            fg=TEXT_PRIMARY,
            bg=BG_CARD,
            activebackground=BG_CARD,
            activeforeground=TEXT_PRIMARY,
            selectcolor=BG_CARD_LIGHT,
            command=self._on_toggle_autostart,
            cursor="hand2",
        )
        chk_autostart.pack(anchor="w", pady=6)

        # Port configuration
        port_row = tk.Frame(card_settings, bg=BG_CARD)
        port_row.pack(fill="x", pady=8)
        tk.Label(port_row, text="Server Network Port:", font=("Segoe UI", 10), fg=TEXT_MUTED, bg=BG_CARD).pack(side="left")

        self.entry_port = tk.Entry(port_row, width=8, font=("Segoe UI", 10), bg=BG_CARD_LIGHT, fg=TEXT_PRIMARY, relief="flat")
        self.entry_port.insert(0, str(self.port))
        self.entry_port.pack(side="left", padx=10)

        # Save Settings Button
        btn_save = tk.Button(
            card_settings,
            text="Save Settings",
            font=("Segoe UI", 9, "bold"),
            bg=ACCENT_COLOR,
            fg="#ffffff",
            relief="flat",
            padx=14,
            pady=4,
            command=self._on_save_settings,
            cursor="hand2",
        )
        btn_save.pack(anchor="w", pady=(12, 0))
        _add_hover(btn_save, ACCENT_HOVER, ACCENT_COLOR)

    def _on_toggle_autostart(self):
        enable = self.var_autostart.get()
        ok = set_autostart(enable)
        if ok:
            status = "enabled" if enable else "disabled"
            messagebox.showinfo("Startup Setting", f"Start-with-Windows has been {status}.")
        else:
            messagebox.showerror("Error", "Failed to update Windows Startup registry.")

    def _on_save_settings(self):
        try:
            new_port = int(self.entry_port.get().strip())
            config.set("server.port", new_port)
            config.save()
            messagebox.showinfo("Settings Saved", "Configuration saved. (Restart AirDeck if port was modified).")
        except ValueError:
            messagebox.showerror("Invalid Input", "Please enter a valid port number (e.g. 8765).")

    def on_close(self):
        self._telemetry_running = False
        self.root.destroy()


def open_control_panel():
    """Launch the Control Panel in a clean root window (enforcing single window)."""
    from core.single_instance import SingleInstance
    cp_mutex = SingleInstance("AirDeck_ControlPanel_Window_Mutex")
    if cp_mutex.is_running():
        if sys.platform == "win32":
            try:
                import ctypes
                hwnd = ctypes.windll.user32.FindWindowW(None, "AirDeck Pro — Control Panel & Dashboard")
                if hwnd:
                    ctypes.windll.user32.ShowWindow(hwnd, 9)  # SW_RESTORE
                    ctypes.windll.user32.SetForegroundWindow(hwnd)
                    return
            except Exception:
                pass
        return

    root = tk.Tk()
    app = ModernControlPanel(root)
    root.mainloop()


if __name__ == "__main__":
    open_control_panel()
