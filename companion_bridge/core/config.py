"""
AirDeck Core Configuration Engine
Handles JSON-based configuration persistence, defaults, and runtime settings.
"""

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict

DEFAULT_CONFIG: Dict[str, Any] = {
    "server": {
        "port": 8765,
        "auto_fallback_port": True,
        "max_port_attempts": 10,
        "host": "0.0.0.0",
    },
    "input": {
        "sensitivity": 1.8,
        "accel_power": 1.2,
        "wheel_delta": 120,
    },
    "security": {
        "max_failed_attempts": 5,
        "lockout_seconds": 60,
        "token_lifetime_days": 365,
    },
    "hardware": {
        "cam_fps": 15,
        "cam_quality": 0.70,
        "audio_sample_rate": 16000,
    }
}

class ConfigManager:
    """Thread-safe configuration manager with JSON persistence."""

    def __init__(self, config_path: Path = None):
        if config_path is None:
            # Default to config.json alongside executable or in bridge root
            if getattr(sys, "frozen", False):
                base_dir = Path(sys.executable).parent.resolve()
            else:
                base_dir = Path(__file__).parent.parent.resolve()
            self.config_path = base_dir / "config.json"
        else:
            self.config_path = Path(config_path)

        self._data: Dict[str, Any] = {}
        self.load()

    def load(self) -> Dict[str, Any]:
        """Load configuration from disk, creating default if missing."""
        if not self.config_path.exists():
            self._data = dict(DEFAULT_CONFIG)
            self.save()
            return self._data

        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                loaded = json.load(f)
                # Deep merge defaults so new config keys are never missing
                self._data = self._deep_merge(dict(DEFAULT_CONFIG), loaded)
        except Exception:
            self._data = dict(DEFAULT_CONFIG)
            self.save()

        return self._data

    def save(self) -> bool:
        """Save active configuration to disk."""
        try:
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(self._data, f, indent=2)
            return True
        except Exception as e:
            print(f"[CONFIG ERROR] Failed to save config: {e}")
            return False

    def get(self, key_path: str, default: Any = None) -> Any:
        """
        Get nested value using dot-notation, e.g. get('server.port').
        """
        parts = key_path.split(".")
        current = self._data
        for part in parts:
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return default
        return current

    def set(self, key_path: str, value: Any, auto_save: bool = True) -> None:
        """
        Set nested value using dot-notation, e.g. set('server.port', 8766).
        """
        parts = key_path.split(".")
        current = self._data
        for part in parts[:-1]:
            if part not in current or not isinstance(current[part], dict):
                current[part] = {}
            current = current[part]
        current[parts[-1]] = value
        if auto_save:
            self.save()

    @staticmethod
    def _deep_merge(base: dict, update: dict) -> dict:
        """Recursively merge dictionary update into base."""
        merged = dict(base)
        for k, v in update.items():
            if k in merged and isinstance(merged[k], dict) and isinstance(v, dict):
                merged[k] = ConfigManager._deep_merge(merged[k], v)
            else:
                merged[k] = v
        return merged


# Singleton instance
config = ConfigManager()
