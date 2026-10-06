"""
AirDeck Core Single-Instance Mutex Subsystem
Ensures only one instance of AirDeck runs at any time, preventing duplicate tray icons and port conflicts.
"""

import os
import sys
from typing import Optional


class SingleInstance:
    """Windows Named Mutex to enforce a single running application instance."""

    def __init__(self, app_id: str = "AirDeck_Pro_Instance_Mutex"):
        self.app_id = app_id
        self.mutex_handle = None
        self.already_running = False
        self._acquire()

    def _acquire(self):
        if sys.platform == "win32":
            import ctypes
            from ctypes import wintypes

            kernel32 = ctypes.windll.kernel32
            ERROR_ALREADY_EXISTS = 183

            # Create or open named mutex
            self.mutex_handle = kernel32.CreateMutexW(
                None,
                False,
                self.app_id,
            )
            last_error = kernel32.GetLastError()
            if last_error == ERROR_ALREADY_EXISTS:
                self.already_running = True
            else:
                self.already_running = False
        else:
            # Fallback for POSIX platforms using file lock
            import fcntl
            from pathlib import Path
            self.lock_file_path = Path.home() / f".{self.app_id}.lock"
            try:
                self.lock_file = open(self.lock_file_path, "w")
                fcntl.lockf(self.lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
                self.already_running = False
            except (IOError, BlockingIOError):
                self.already_running = True

    def is_running(self) -> bool:
        """Return True if another instance is already running."""
        return self.already_running

    def release(self):
        """Release the mutex lock upon process exit."""
        if sys.platform == "win32" and self.mutex_handle:
            import ctypes
            ctypes.windll.kernel32.CloseHandle(self.mutex_handle)
            self.mutex_handle = None
        elif hasattr(self, "lock_file") and self.lock_file:
            try:
                import fcntl
                fcntl.lockf(self.lock_file, fcntl.LOCK_UN)
                self.lock_file.close()
                if hasattr(self, "lock_file_path") and self.lock_file_path.exists():
                    self.lock_file_path.unlink()
            except Exception:
                pass


# Helper function
def check_single_instance(app_id: str = "AirDeck_Pro_Instance_Mutex") -> SingleInstance:
    return SingleInstance(app_id)
