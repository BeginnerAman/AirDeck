"""
AirDeck Core Macro Subsystem
Provides persistent, user-customizable Stream Deck macros (actions, hotkeys, executable launching, URL opening).
Stored in JSON format with support for mobile and desktop creation.
"""

import json
import os
import subprocess
import sys
import threading
import uuid
import webbrowser
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from core.input_driver import input_driver

DEFAULT_MACROS: List[Dict[str, Any]] = [
    {"id": "m_taskmgr",   "label": "Task Mgr",    "icon": "activity", "type": "action", "target": "taskmgr",      "color": "#6366f1"},
    {"id": "m_explorer",  "label": "Explorer",    "icon": "folder",   "type": "action", "target": "explorer",     "color": "#3b82f6"},
    {"id": "m_terminal",  "label": "Run / CMD",   "icon": "terminal", "type": "action", "target": "terminal",     "color": "#10b981"},
    {"id": "m_settings",  "label": "Settings",    "icon": "settings", "type": "action", "target": "settings",     "color": "#8b5cf6"},
    {"id": "m_newtab",    "label": "New Tab",     "icon": "globe",    "type": "action", "target": "newtab",       "color": "#06b6d4"},
    {"id": "m_discord",   "label": "Discord Mute","icon": "micoff",   "type": "action", "target": "discord_mute", "color": "#5865F2"},
    {"id": "m_fullscreen","label": "Fullscreen",  "icon": "maximize", "type": "action", "target": "fullscreen",   "color": "#f59e0b"},
    {"id": "m_snip",      "label": "Screenshot",  "icon": "scissors", "type": "action", "target": "snip",         "color": "#ec4899"},
    {"id": "m_appswitch", "label": "Alt + Tab",   "icon": "switch",   "type": "action", "target": "appswitch",    "color": "#6366f1"},
    {"id": "m_desktop",   "label": "Desktop",     "icon": "monitor",  "type": "action", "target": "desktop",      "color": "#14b8a6"},
    {"id": "m_calc",      "label": "Calculator",  "icon": "calculator","type": "launch", "target": "calc.exe",     "color": "#f97316"},
    {"id": "m_notepad",   "label": "Notepad",     "icon": "filetext", "type": "launch", "target": "notepad.exe",  "color": "#64748b"},
    {"id": "m_closeapp",  "label": "Alt + F4",    "icon": "x",        "type": "action", "target": "closeapp",     "color": "#ef4444"},
    {"id": "m_lock",      "label": "Lock PC",     "icon": "lock",     "type": "action", "target": "lock",         "color": "#dc2626", "confirm": True},
]


class MacroManager:
    """Manages custom and default macros with JSON persistence and multi-action execution."""

    def __init__(self, storage_path: Optional[Path] = None):
        if storage_path is None:
            if getattr(sys, "frozen", False):
                base_dir = Path(sys.executable).parent.resolve()
            else:
                base_dir = Path(__file__).parent.parent.resolve()
            self.storage_path = base_dir / "macros.json"
        else:
            self.storage_path = Path(storage_path)

        self._lock = threading.Lock()
        self._macros: List[Dict[str, Any]] = []
        self.load()

    def load(self) -> List[Dict[str, Any]]:
        """Load macros from storage, populating defaults if missing."""
        with self._lock:
            if not self.storage_path.exists():
                self._macros = list(DEFAULT_MACROS)
                self._save_internal()
                return self._macros

            try:
                with open(self.storage_path, "r", encoding="utf-8") as f:
                    self._macros = json.load(f)
            except Exception:
                self._macros = list(DEFAULT_MACROS)
                self._save_internal()

            return self._macros

    def _save_internal(self) -> bool:
        try:
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.storage_path, "w", encoding="utf-8") as f:
                json.dump(self._macros, f, indent=2)
            return True
        except Exception as e:
            print(f"[MACRO ERROR] Failed to save macros: {e}")
            return False

    def save(self) -> bool:
        with self._lock:
            return self._save_internal()

    def get_macros(self) -> List[Dict[str, Any]]:
        with self._lock:
            return list(self._macros)

    def add_macro(self, macro_data: Dict[str, Any]) -> Dict[str, Any]:
        with self._lock:
            new_id = macro_data.get("id") or f"m_{uuid.uuid4().hex[:8]}"
            entry = {
                "id": new_id,
                "label": macro_data.get("label", "Custom"),
                "icon": macro_data.get("icon", "activity"),
                "type": macro_data.get("type", "action"),
                "target": macro_data.get("target", ""),
                "color": macro_data.get("color", "#6C63FF"),
                "confirm": bool(macro_data.get("confirm", False)),
            }
            self._macros.append(entry)
            self._save_internal()
            return entry

    def update_macro(self, macro_id: str, macro_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        with self._lock:
            for i, m in enumerate(self._macros):
                if m.get("id") == macro_id:
                    self._macros[i].update(macro_data)
                    self._save_internal()
                    return self._macros[i]
            return None

    def delete_macro(self, macro_id: str) -> bool:
        with self._lock:
            before_len = len(self._macros)
            self._macros = [m for m in self._macros if m.get("id") != macro_id]
            if len(self._macros) < before_len:
                self._save_internal()
                return True
            return False

    def reset_defaults(self) -> List[Dict[str, Any]]:
        with self._lock:
            self._macros = list(DEFAULT_MACROS)
            self._save_internal()
            return self._macros

    def execute_macro(self, macro_id: str) -> Tuple[bool, str]:
        """Execute a macro by ID based on its configured type."""
        macro = None
        with self._lock:
            for m in self._macros:
                if m.get("id") == macro_id:
                    macro = dict(m)
                    break

        if not macro:
            return False, f"Macro '{macro_id}' not found"

        mtype = macro.get("type", "action")
        target = macro.get("target", "")

        try:
            if mtype == "action":
                input_driver.post_action(target)
                return True, f"Action: {macro.get('label')}"

            elif mtype == "hotkey":
                keys = target if isinstance(target, list) else target.split("+")
                input_driver.post_hotkey([k.strip().lower() for k in keys])
                return True, f"Hotkey: {target}"

            elif mtype == "key" or mtype == "text":
                input_driver.post_key(str(target))
                return True, f"Typed: {macro.get('label')}"

            elif mtype == "launch":
                target_str = str(target).strip()
                if sys.platform == "win32":
                    try:
                        # Native Windows ShellExecute: safe, opens executables without cmd.exe command chaining
                        os.startfile(target_str)
                    except Exception:
                        import shlex
                        subprocess.Popen(shlex.split(target_str, posix=False), shell=False)
                else:
                    import shlex
                    subprocess.Popen(shlex.split(target_str))
                return True, f"Launched: {target_str}"

            elif mtype == "url":
                target_str = str(target).strip()
                if not (target_str.startswith("http://") or target_str.startswith("https://")):
                    target_str = "https://" + target_str
                webbrowser.open(target_str)
                return True, f"Opened URL: {target_str}"

            else:
                return False, f"Unknown macro type: {mtype}"

        except Exception as e:
            return False, f"Execution failed: {e}"


# Singleton instance
macro_manager = MacroManager()
