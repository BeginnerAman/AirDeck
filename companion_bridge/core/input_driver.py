"""
AirDeck Core Input Subsystem
Provides decoupled, non-blocking hardware input injection (mouse, keyboard, media, power actions).
Worker thread architecture ensures the FastAPI asyncio event loop is never choked by Win32 API calls.
"""

import collections
import math
import platform
import queue
import subprocess
import threading
import time
from typing import Any, Dict, List, Optional

import pyautogui
import pyperclip
from pynput.keyboard import Controller as KbdController, Key

from core.config import config

IS_MAC = platform.system() == "Darwin"
IS_WIN = platform.system() == "Windows"
MOD_KEY = "command" if IS_MAC else "ctrl"

# Enable Windows Per-Monitor High-DPI Awareness and Win32 SendInput
HAS_WIN32_INPUT = False
if IS_WIN:
    try:
        import ctypes
        from ctypes import wintypes
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass

    try:
        # Request 1ms high-resolution timer from Windows multimedia subsystem for zero-latency scheduling
        ctypes.windll.winmm.timeBeginPeriod(1)
    except Exception:
        pass

    try:
        PUL = ctypes.POINTER(ctypes.c_ulong)

        class MOUSEINPUT(ctypes.Structure):
            _fields_ = [
                ("dx", ctypes.c_long),
                ("dy", ctypes.c_long),
                ("mouseData", ctypes.c_ulong),
                ("dwFlags", ctypes.c_ulong),
                ("time", ctypes.c_ulong),
                ("dwExtraInfo", PUL),
            ]

        class INPUT_UNION(ctypes.Union):
            _fields_ = [("mi", MOUSEINPUT)]

        class INPUT(ctypes.Structure):
            _fields_ = [
                ("type", ctypes.c_ulong),
                ("u", INPUT_UNION),
            ]

        INPUT_MOUSE = 0
        MOUSEEVENTF_MOVE = 0x0001
        MOUSEEVENTF_LEFTDOWN = 0x0002
        MOUSEEVENTF_LEFTUP = 0x0004
        MOUSEEVENTF_RIGHTDOWN = 0x0008
        MOUSEEVENTF_RIGHTUP = 0x0010
        MOUSEEVENTF_MIDDLEDOWN = 0x0020
        MOUSEEVENTF_MIDDLEUP = 0x0040
        MOUSEEVENTF_WHEEL = 0x0800
        MOUSEEVENTF_HWHEEL = 0x1000

        def win32_send_mouse(flags: int, dx: int = 0, dy: int = 0, data: int = 0):
            inp = INPUT()
            inp.type = INPUT_MOUSE
            inp.u.mi.dx = int(dx)
            inp.u.mi.dy = int(dy)
            inp.u.mi.mouseData = int(data)
            inp.u.mi.dwFlags = int(flags)
            inp.u.mi.time = 0
            inp.u.mi.dwExtraInfo = None
            ctypes.windll.user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))

        HAS_WIN32_INPUT = True
    except Exception:
        HAS_WIN32_INPUT = False

# Zero-Latency PyAutoGUI tuning (used as fallback or for higher-level macros)
pyautogui.FAILSAFE = False
pyautogui.PAUSE = 0

MEDIA_KEYS = {
    "play": Key.media_play_pause,
    "next": Key.media_next,
    "prev": Key.media_previous,
    "volup": Key.media_volume_up,
    "voldn": Key.media_volume_down,
    "mute": Key.media_volume_mute,
}

SPECIAL_KEYS = {
    "Backspace": Key.backspace,
    "Enter": Key.enter,
    "Tab": Key.tab,
    "Escape": Key.esc,
    "ArrowUp": Key.up,
    "ArrowDown": Key.down,
    "ArrowLeft": Key.left,
    "ArrowRight": Key.right,
    "Delete": Key.delete,
    "Home": Key.home,
    "End": Key.end,
    "PageUp": Key.page_up,
    "PageDown": Key.page_down,
    "Insert": Key.insert,
    "F1": Key.f1,
    "F2": Key.f2,
    "F3": Key.f3,
    "F4": Key.f4,
    "F5": Key.f5,
    "F6": Key.f6,
    "F7": Key.f7,
    "F8": Key.f8,
    "F9": Key.f9,
    "F10": Key.f10,
    "F11": Key.f11,
    "F12": Key.f12,
    " ": Key.space,
}


class InputDriver:
    """Thread-safe, non-blocking hardware input controller."""

    def __init__(self):
        self.kbd = KbdController()
        self._lock = threading.Lock()
        self._cv = threading.Condition(self._lock)
        self._held_buttons = set()
        self._queue = collections.deque()
        self._running = True

        # High-precision floating sub-pixel accumulators (zero movement loss)
        self._sub_x = 0.0
        self._sub_y = 0.0

        self._worker_thread = threading.Thread(
            target=self._process_queue,
            daemon=True,
            name="AirDeck-InputWorker",
        )
        self._worker_thread.start()

    def stop(self):
        """Signal background worker to exit cleanly."""
        self._running = False
        with self._cv:
            self._cv.notify_all()
        if IS_WIN:
            try:
                ctypes.windll.winmm.timeEndPeriod(1)
            except Exception:
                pass

    def get_sensitivity(self) -> float:
        return float(config.get("input.sensitivity", 1.8))

    def get_accel_power(self) -> float:
        return float(config.get("input.accel_power", 1.2))

    def get_wheel_delta(self) -> int:
        return int(config.get("input.wheel_delta", 120))

    def accelerate_vector(self, dx: float, dy: float) -> tuple[float, float]:
        """
        True 2D vector kinematics with continuous sub-pixel precision:
        1. Calculates Euclidean velocity magnitude (distance).
        2. Applies smooth ergonomic velocity curve based on speed:
           - Slow motion (<1.2px): pure 1:1 precision, zero micro-jitter.
           - Fast swipes: natural dynamic power curve for effortless cross-screen reach.
        3. Preserves exact trajectory angle by scaling (dx, dy) with the same multiplier.
        """
        dist = math.hypot(dx, dy)
        if dist < 1e-6:
            return 0.0, 0.0

        sens = self.get_sensitivity()
        power = self.get_accel_power()

        if dist < 1.2:
            multiplier = sens
        else:
            multiplier = sens * (dist ** (power - 1.0))

        return dx * multiplier, dy * multiplier

    def accelerate(self, delta: float) -> float:
        """Non-linear mouse acceleration: sign(d) * |d|^power * sensitivity (1D fallback)."""
        if delta == 0:
            return 0.0
        sens = self.get_sensitivity()
        power = self.get_accel_power()
        return math.copysign(abs(delta) ** power * sens, delta)

    def reset_sub_pixels(self):
        """Reset sub-pixel accumulator between touch sessions to prevent residual jump."""
        with self._lock:
            self._sub_x = 0.0
            self._sub_y = 0.0

    def release_all_mouse_buttons(self):
        """Fail-safe: Release any mouse button that might be stuck held."""
        with self._lock:
            self._sub_x = 0.0
            self._sub_y = 0.0
            for btn in list(self._held_buttons):
                if HAS_WIN32_INPUT:
                    if btn == "left":
                        win32_send_mouse(MOUSEEVENTF_LEFTUP)
                    elif btn == "right":
                        win32_send_mouse(MOUSEEVENTF_RIGHTUP)
                    elif btn == "middle":
                        win32_send_mouse(MOUSEEVENTF_MIDDLEUP)
                else:
                    try:
                        pyautogui.mouseUp(button=btn, _pause=False)
                    except Exception:
                        pass
            self._held_buttons.clear()

    def _process_queue(self):
        """Dedicated background worker executing Win32 input calls."""
        while self._running:
            cmd = None
            args = None
            with self._cv:
                while not self._queue and self._running:
                    self._cv.wait(timeout=0.5)
                if not self._running:
                    break
                if not self._queue:
                    continue
                cmd, args = self._queue.popleft()

            try:
                self._dispatch(cmd, args)
            except Exception:
                pass

    def _dispatch(self, cmd: str, args: tuple):
        if cmd == "move":
            dx, dy = args
            accum_x, accum_y = dx, dy
            # Safely peek and coalesce subsequent move events without re-ordering other commands
            with self._cv:
                while self._queue and self._queue[0][0] == "move":
                    next_item = self._queue.popleft()
                    accum_x += next_item[1][0]
                    accum_y += next_item[1][1]

            if HAS_WIN32_INPUT:
                win32_send_mouse(MOUSEEVENTF_MOVE, dx=accum_x, dy=accum_y)
            else:
                pyautogui.moveRel(accum_x, accum_y, _pause=False)

        elif cmd == "click":
            btn = args[0]
            if HAS_WIN32_INPUT:
                if btn == "left":
                    win32_send_mouse(MOUSEEVENTF_LEFTDOWN)
                    win32_send_mouse(MOUSEEVENTF_LEFTUP)
                elif btn == "right":
                    win32_send_mouse(MOUSEEVENTF_RIGHTDOWN)
                    win32_send_mouse(MOUSEEVENTF_RIGHTUP)
                elif btn == "middle":
                    win32_send_mouse(MOUSEEVENTF_MIDDLEDOWN)
                    win32_send_mouse(MOUSEEVENTF_MIDDLEUP)
            else:
                pyautogui.click(button=btn, _pause=False)

        elif cmd == "mdown":
            btn = args[0]
            self._held_buttons.add(btn)
            if HAS_WIN32_INPUT:
                if btn == "left":
                    win32_send_mouse(MOUSEEVENTF_LEFTDOWN)
                elif btn == "right":
                    win32_send_mouse(MOUSEEVENTF_RIGHTDOWN)
                elif btn == "middle":
                    win32_send_mouse(MOUSEEVENTF_MIDDLEDOWN)
            else:
                pyautogui.mouseDown(button=btn, _pause=False)

        elif cmd == "mup":
            btn = args[0]
            self._held_buttons.discard(btn)
            if HAS_WIN32_INPUT:
                if btn == "left":
                    win32_send_mouse(MOUSEEVENTF_LEFTUP)
                elif btn == "right":
                    win32_send_mouse(MOUSEEVENTF_RIGHTUP)
                elif btn == "middle":
                    win32_send_mouse(MOUSEEVENTF_MIDDLEUP)
            else:
                pyautogui.mouseUp(button=btn, _pause=False)

        elif cmd == "scroll":
            sx, sy = args
            wheel_delta = self.get_wheel_delta()
            if HAS_WIN32_INPUT:
                if sy:
                    win32_send_mouse(MOUSEEVENTF_WHEEL, data=sy * wheel_delta)
                if sx:
                    win32_send_mouse(MOUSEEVENTF_HWHEEL, data=sx * wheel_delta)
            else:
                if sy:
                    delta_y = sy * wheel_delta if IS_WIN else sy
                    pyautogui.scroll(delta_y, _pause=False)
                if sx:
                    delta_x = sx * wheel_delta if IS_WIN else sx
                    pyautogui.hscroll(delta_x, _pause=False)

        elif cmd == "key":
            text = args[0]
            self._type_text_internal(text)

        elif cmd == "skey":
            k = args[0]
            pkey = SPECIAL_KEYS.get(k)
            if pkey:
                self.kbd.press(pkey)
                self.kbd.release(pkey)

        elif cmd == "hotkey":
            keys = args[0]
            keys = [MOD_KEY if k == "mod" else k for k in keys]
            if keys:
                pyautogui.hotkey(*keys, _pause=False)

        elif cmd == "media":
            action = args[0]
            if action == "seekf":
                self.kbd.press(Key.right)
                self.kbd.release(Key.right)
            elif action == "seekb":
                self.kbd.press(Key.left)
                self.kbd.release(Key.left)
            else:
                mkey = MEDIA_KEYS.get(action)
                if mkey:
                    self.kbd.press(mkey)
                    self.kbd.release(mkey)

        elif cmd == "action":
            act = args[0]
            self._execute_action_internal(act)

    def _type_text_internal(self, text: str):
        if not text:
            return
        if text.isascii():
            pyautogui.write(text, interval=0, _pause=False)
        else:
            old_clip = ""
            try:
                old_clip = pyperclip.paste()
            except Exception:
                pass
            pyperclip.copy(text)
            pyautogui.hotkey(MOD_KEY, "v", _pause=False)
            time.sleep(0.05)
            try:
                pyperclip.copy(old_clip)
            except Exception:
                pass

    def _execute_action_internal(self, act: str):
        if act == "lock":
            if IS_WIN:
                import ctypes
                ctypes.windll.user32.LockWorkStation()
            elif IS_MAC:
                subprocess.run(["pmset", "displaysleepnow"])
        elif act == "desktop":
            pyautogui.hotkey("win" if IS_WIN else "command", "d", _pause=False)
        elif act == "appswitch":
            pyautogui.hotkey("alt", "tab", _pause=False)
        elif act == "snip":
            if IS_WIN:
                pyautogui.hotkey("win", "shift", "s", _pause=False)
            elif IS_MAC:
                pyautogui.hotkey("command", "shift", "4", _pause=False)
        elif act == "closetab":
            pyautogui.hotkey(MOD_KEY, "w", _pause=False)
        elif act == "taskmgr":
            pyautogui.hotkey("ctrl", "shift", "esc", _pause=False)
        elif act == "explorer":
            pyautogui.hotkey("win", "e", _pause=False)
        elif act == "settings":
            pyautogui.hotkey("win", "i", _pause=False)
        elif act == "terminal":
            if IS_WIN:
                pyautogui.hotkey("win", "r", _pause=False)
            else:
                pyautogui.hotkey(MOD_KEY, "space", _pause=False)
        elif act == "newtab":
            pyautogui.hotkey(MOD_KEY, "t", _pause=False)
        elif act == "closeapp":
            pyautogui.hotkey("alt", "f4", _pause=False)
        elif act == "fullscreen":
            pyautogui.press("f11", _pause=False)
        elif act == "slideshow_start":
            pyautogui.press("f5", _pause=False)
        elif act == "slideshow_end":
            self.kbd.press(Key.esc)
            self.kbd.release(Key.esc)
        elif act == "slide_black":
            self._type_text_internal("b")
        elif act == "slide_white":
            self._type_text_internal("w")
        elif act == "slide_next":
            self.kbd.press(Key.right)
            self.kbd.release(Key.right)
        elif act == "slide_prev":
            self.kbd.press(Key.left)
            self.kbd.release(Key.left)
        elif act == "discord_mute":
            pyautogui.hotkey("ctrl", "shift", "m", _pause=False)

    # ── Non-Blocking Public Enqueue APIs ──────────────────────────

    def _enqueue(self, cmd: str, args: tuple):
        with self._cv:
            if len(self._queue) < 300:
                self._queue.append((cmd, args))
                self._cv.notify()

    def post_move(self, raw_dx: float, raw_dy: float):
        """
        Inject mouse motion with vector-based kinematic acceleration and continuous
        sub-pixel residual accumulation. Zero micro-movements are lost.
        """
        if not raw_dx and not raw_dy:
            return
        adx, ady = self.accelerate_vector(raw_dx, raw_dy)
        with self._lock:
            self._sub_x += adx
            self._sub_y += ady

            ix = int(self._sub_x)
            iy = int(self._sub_y)

            self._sub_x -= ix
            self._sub_y -= iy

        if ix != 0 or iy != 0:
            self._enqueue("move", (ix, iy))

    def post_click(self, button: str = "left"):
        self._enqueue("click", (button,))

    def post_mouse_down(self, button: str = "left"):
        self._enqueue("mdown", (button,))

    def post_mouse_up(self, button: str = "left"):
        self._enqueue("mup", (button,))

    def post_scroll(self, sx: int, sy: int):
        self._enqueue("scroll", (sx, sy))

    def post_key(self, text: str):
        self._enqueue("key", (text,))

    def post_special_key(self, key_name: str):
        self._enqueue("skey", (key_name,))

    def post_hotkey(self, keys: List[str]):
        self._enqueue("hotkey", (keys,))

    def post_media(self, action: str):
        self._enqueue("media", (action,))

    def post_action(self, action: str):
        self._enqueue("action", (action,))


# Singleton instance
input_driver = InputDriver()
