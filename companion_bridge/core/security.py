"""
AirDeck Core Security Engine
Provides dynamic PIN generation, persistent token authorization, and brute-force lockout protection.
"""

import json
import os
import secrets
import sys
import threading
import time
from pathlib import Path
from typing import Dict, Optional, Set, Tuple

from core.config import config


def _get_storage_path() -> Path:
    if getattr(sys, "frozen", False):
        base_dir = Path(sys.executable).parent.resolve()
    else:
        base_dir = Path(__file__).parent.parent.resolve()
    return base_dir / "paired_tokens.json"


class SecurityEngine:
    """Manages pairing PIN, token exchange, persistent authorized device tokens, and anti-brute-force rate limiting."""

    def __init__(self, storage_path: Optional[Path] = None):
        self._lock = threading.Lock()
        self.pairing_pin = f"{secrets.randbelow(9000) + 1000}"  # 4-digit PIN (1000-9999)
        self.master_token = secrets.token_urlsafe(32)
        self.storage_path = storage_path or _get_storage_path()

        # {token_str: {"created_at": float, "last_used_at": float, "client_ip": str}}
        self._tokens_db: Dict[str, Dict] = {}
        self.valid_tokens: Set[str] = {self.master_token}

        # Load persisted tokens from disk
        self._load_tokens()

        # IP-based rate limiting: {ip: {"attempts": int, "locked_until": float}}
        self._ip_attempts: Dict[str, Dict] = {}

    def _load_tokens(self):
        """Load paired device tokens from persistent storage."""
        if not self.storage_path.exists():
            return
        try:
            with open(self.storage_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                loaded_tokens = data.get("tokens", {})
                for tok, meta in loaded_tokens.items():
                    if isinstance(tok, str) and tok:
                        self._tokens_db[tok] = meta
                        self.valid_tokens.add(tok)
        except Exception as e:
            print(f"[SECURITY] Warning: Could not load paired tokens: {e}")

    def _save_tokens(self):
        """Persist authorized tokens to disk."""
        try:
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.storage_path, "w", encoding="utf-8") as f:
                json.dump({"tokens": self._tokens_db}, f, indent=2)
        except Exception as e:
            print(f"[SECURITY] Error saving paired tokens: {e}")

    def get_max_attempts(self) -> int:
        return int(config.get("security.max_failed_attempts", 5))

    def get_lockout_seconds(self) -> int:
        return int(config.get("security.lockout_seconds", 60))

    def regenerate_pin(self) -> str:
        """Regenerate pairing PIN on demand."""
        with self._lock:
            self.pairing_pin = f"{secrets.randbelow(9000) + 1000}"
            return self.pairing_pin

    def is_token_valid(self, token: Optional[str]) -> bool:
        """Constant-time token validation helper."""
        if not token:
            return False
        with self._lock:
            # Check against master token or stored valid tokens
            for valid_tok in self.valid_tokens:
                if secrets.compare_digest(token, valid_tok):
                    return True
            return False

    def revoke_token(self, token: str) -> bool:
        """Revoke a specific paired device token."""
        with self._lock:
            if token in self.valid_tokens and token != self.master_token:
                self.valid_tokens.remove(token)
                self._tokens_db.pop(token, None)
                self._save_tokens()
                return True
            return False

    def is_ip_locked(self, ip: str) -> Tuple[bool, int]:
        """Check if an IP address is currently locked out."""
        with self._lock:
            record = self._ip_attempts.get(ip)
            if not record:
                return False, 0

            locked_until = record.get("locked_until", 0)
            now = time.time()
            if locked_until > now:
                remaining = int(locked_until - now)
                return True, remaining
            return False, 0

    def verify_auth(self, ip: str, token: Optional[str] = None, pin: Optional[str] = None) -> Tuple[bool, str, Optional[str]]:
        """
        Authenticate a client using token or PIN.
        Returns: (success: bool, message: str, new_token: Optional[str])
        """
        # 1. Check if IP is currently under lockout
        is_locked, remaining = self.is_ip_locked(ip)
        if is_locked:
            return False, f"Too many failed attempts. Try again in {remaining}s.", None

        now = time.time()

        # 2. Verify token (trusted device auto-pair)
        if token and self.is_token_valid(token):
            with self._lock:
                if ip in self._ip_attempts:
                    del self._ip_attempts[ip]

                # Update timestamp on matched token
                if token in self._tokens_db:
                    self._tokens_db[token]["last_used_at"] = now
                    self._tokens_db[token]["client_ip"] = ip
                    self._save_tokens()

                # Issue refreshed token and persist
                refreshed_token = secrets.token_urlsafe(32)
                self.valid_tokens.add(refreshed_token)
                self._tokens_db[refreshed_token] = {
                    "created_at": now,
                    "last_used_at": now,
                    "client_ip": ip,
                }
                self._save_tokens()
                return True, "Authorized via token", refreshed_token

        # 3. Verify PIN
        clean_pin = str(pin).strip() if pin else ""
        if clean_pin and secrets.compare_digest(clean_pin, self.pairing_pin):
            with self._lock:
                if ip in self._ip_attempts:
                    del self._ip_attempts[ip]

                new_token = secrets.token_urlsafe(32)
                self.valid_tokens.add(new_token)
                self._tokens_db[new_token] = {
                    "created_at": now,
                    "last_used_at": now,
                    "client_ip": ip,
                }
                self._save_tokens()
                return True, "Authorized via PIN", new_token

        # 4. Handle failed verification (Record attempt)
        with self._lock:
            record = self._ip_attempts.setdefault(ip, {"attempts": 0, "locked_until": 0})
            record["attempts"] += 1
            max_attempts = self.get_max_attempts()

            if record["attempts"] >= max_attempts:
                lockout_duration = self.get_lockout_seconds()
                record["locked_until"] = time.time() + lockout_duration
                record["attempts"] = 0
                return False, f"Maximum PIN attempts exceeded. Locked for {lockout_duration}s.", None

            remaining_attempts = max_attempts - record["attempts"]
            return False, f"Invalid PIN or token. ({remaining_attempts} attempts remaining)", None


# Singleton instance
security_engine = SecurityEngine()
