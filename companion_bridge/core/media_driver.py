"""
AirDeck Core Media Driver Subsystem (v3.0 Enterprise)
Decoupled management for pyvirtualcam and PyAudio/WASAPI hardware bridges.
Supports:
  1. Virtual Camera (pyvirtualcam)
  2. Phone-to-PC Mic (Dual-Mode: VB-Cable or Direct PC Speakers with auto Mono-to-Stereo upsampling)
  3. PC-to-Phone Wireless Extended Speaker (Windows WASAPI Loopback real-time PC audio capture)
"""

import io
import queue
import threading
from typing import Any, Callable, Dict, Optional, Tuple

import numpy as np
from PIL import Image

from core.config import config

# Check pyvirtualcam availability
try:
    import pyvirtualcam
    HAS_VCAM = True
except ImportError:
    HAS_VCAM = False

# Check PyAudio / PyAudioWPatch availability
try:
    import pyaudiowpatch as pyaudio
    HAS_PYAUDIO = True
    HAS_WASAPI_LOOPBACK = True
except ImportError:
    try:
        import pyaudio
        HAS_PYAUDIO = True
        HAS_WASAPI_LOOPBACK = hasattr(pyaudio.PyAudio, "get_default_wasapi_loopback")
    except ImportError:
        HAS_PYAUDIO = False
        HAS_WASAPI_LOOPBACK = False


class MediaDriver:
    """Thread-safe virtual hardware manager for camera and two-way audio routing."""

    def __init__(self):
        self._lock = threading.Lock()
        self.vcam_instance: Optional[Any] = None
        self.pa_instance: Optional[Any] = None
        self.audio_stream: Optional[Any] = None
        self.output_channels = 2
        self.output_sample_rate = 16000

        self.cam_active = False
        self.audio_active = False
        self.speaker_active = False

        self.vcam_device_name = "Not Available"
        self.audio_device_name = "Not Available"
        self.is_cable_mode = False
        self.target_output_idx: Optional[int] = None

        # Wireless Speaker Loopback Stream
        self.speaker_stream: Optional[Any] = None
        self.speaker_callback: Optional[Callable[[bytes], None]] = None

        # Worker queues
        self.video_queue: queue.Queue = queue.Queue(maxsize=2)
        self.audio_queue: queue.Queue = queue.Queue(maxsize=10)

        # Detect drivers at startup
        self._detect_drivers()

        # Start worker threads
        self._running = True
        self._video_thread = threading.Thread(
            target=self._video_worker, daemon=True, name="AirDeck-VideoWorker"
        )
        self._audio_thread = threading.Thread(
            target=self._audio_worker, daemon=True, name="AirDeck-AudioWorker"
        )
        self._video_thread.start()
        self._audio_thread.start()

    def _detect_drivers(self):
        """Probe available virtual camera, audio outputs, and loopback sinks."""
        # 1. Probe Virtual Camera
        if HAS_VCAM:
            try:
                cam = pyvirtualcam.Camera(width=320, height=240, fps=15, print_fps=False)
                self.vcam_device_name = str(getattr(cam, "device", "Virtual Camera"))
                cam.close()
            except Exception:
                self.vcam_device_name = "None (Install OBS or Unity Capture)"
        else:
            self.vcam_device_name = "Missing pyvirtualcam"

        # 2. Probe Virtual Audio Cable (for Virtual Mic feature)
        if HAS_PYAUDIO:
            try:
                p = pyaudio.PyAudio()
                cable_idx = None

                # Look for VB-Audio Virtual Cable
                for i in range(p.get_device_count()):
                    try:
                        info = p.get_device_info_by_index(i)
                        name = info.get("name", "").lower()
                        if "cable" in name and info.get("maxOutputChannels", 0) > 0:
                            cable_idx = i
                            self.audio_device_name = f"{info.get('name')} (Virtual Mic Mode)"
                            self.is_cable_mode = True
                            self.output_channels = int(info.get("maxOutputChannels", 2))
                            break
                    except Exception:
                        pass

                self.target_output_idx = cable_idx
                p.terminate()

                if self.target_output_idx is None:
                    self.audio_device_name = "VB-Audio Cable Not Installed"
                    self.is_cable_mode = False
            except Exception as e:
                self.audio_device_name = f"Audio Probe Error: {e}"
        else:
            self.audio_device_name = "Missing PyAudio"

    def has_vcam(self) -> bool:
        return HAS_VCAM and not self.vcam_device_name.startswith("None")

    def has_audio(self) -> bool:
        return HAS_PYAUDIO and self.is_cable_mode and self.target_output_idx is not None

    def has_audio_cable(self) -> bool:
        return self.is_cable_mode

    def get_hardware_status(self) -> Dict[str, Any]:
        """Return diagnostic health info for connected mobile clients."""
        return {
            "webcam": {
                "available": self.has_vcam(),
                "driver": self.vcam_device_name,
                "active": self.cam_active,
            },
            "microphone": {
                "available": self.is_cable_mode,
                "driver": self.audio_device_name,
                "is_cable": self.is_cable_mode,
                "active": self.audio_active,
                "install_url": "https://vb-audio.com/Cable/",
            },
            "speaker": {
                "available": HAS_WASAPI_LOOPBACK,
                "active": self.speaker_active,
            },
        }

    # ════════════════════════════════════════════════════════════════
    #  CAMERA PIPELINE
    # ════════════════════════════════════════════════════════════════

    def start_camera(self) -> Tuple[bool, str]:
        if not HAS_VCAM:
            return False, "Virtual camera module (pyvirtualcam) not installed on PC."
        with self._lock:
            self.cam_active = True
            return True, f"Virtual camera ready ({self.vcam_device_name})"

    def stop_camera(self):
        with self._lock:
            self.cam_active = False
            if self.vcam_instance:
                try:
                    self.vcam_instance.close()
                except Exception:
                    pass
                self.vcam_instance = None
                print("[VCAM] Virtual camera closed & released.")

    def push_video_frame(self, jpeg_payload: bytes):
        if not self.cam_active:
            return
        if self.video_queue.full():
            try:
                self.video_queue.get_nowait()
            except queue.Empty:
                pass
        try:
            self.video_queue.put_nowait(jpeg_payload)
        except queue.Full:
            pass

    def _video_worker(self):
        while self._running:
            try:
                payload = self.video_queue.get(timeout=0.5)
                if not self.cam_active:
                    continue
                img = Image.open(io.BytesIO(payload)).convert("RGB")
                frame_np = np.array(img)
                h, w, _ = frame_np.shape

                with self._lock:
                    if self.vcam_instance is None or (self.vcam_instance.width != w or self.vcam_instance.height != h):
                        if self.vcam_instance:
                            try:
                                self.vcam_instance.close()
                            except Exception:
                                pass
                        fps = int(config.get("hardware.cam_fps", 30))
                        try:
                            self.vcam_instance = pyvirtualcam.Camera(
                                width=w, height=h, fps=fps, fmt=pyvirtualcam.PixelFormat.RGB
                            )
                        except Exception as e:
                            print(f"[VCAM ERROR] Could not initialize virtual camera: {e}")
                            self.cam_active = False
                            continue

                    self.vcam_instance.send(frame_np)
            except queue.Empty:
                continue
            except Exception:
                pass

    # ════════════════════════════════════════════════════════════════
    #  AUDIO PIPELINE 1: PHONE-TO-PC MIC (Wireless Mic / Megaphone)
    # ════════════════════════════════════════════════════════════════

    def start_audio(self) -> Tuple[bool, str]:
        if not HAS_PYAUDIO:
            return False, "PyAudio is not installed on PC."

        with self._lock:
            try:
                if self.pa_instance is None:
                    self.pa_instance = pyaudio.PyAudio()

                if self.target_output_idx is None:
                    self._detect_drivers()

                if self.target_output_idx is None:
                    return False, "VB-Audio Virtual Cable is required for Virtual Mic. Install it from vb-audio.com/Cable"

                if self.audio_stream is None:
                    self.output_sample_rate = int(config.get("hardware.audio_sample_rate", 16000))
                    # Open stream with device-supported channel count
                    channels_to_open = 2 if self.output_channels >= 2 else 1
                    self.audio_stream = self.pa_instance.open(
                        format=pyaudio.paInt16,
                        channels=channels_to_open,
                        rate=self.output_sample_rate,
                        output=True,
                        output_device_index=self.target_output_idx,
                        frames_per_buffer=1024,
                    )

                self.audio_active = True
                return True, f"Virtual Mic Live → {self.audio_device_name}"
            except Exception as e:
                self.audio_active = False
                return False, f"Audio start error: {e}"

    def stop_audio(self):
        with self._lock:
            self.audio_active = False
            if self.audio_stream:
                try:
                    self.audio_stream.stop_stream()
                    self.audio_stream.close()
                except Exception:
                    pass
                self.audio_stream = None
            print("[MIC] Audio stream released.")

    def push_audio_chunk(self, pcm_payload: bytes):
        """Enqueue PCM chunk, performing real-time Mono-to-Stereo upsampling if needed."""
        if not self.audio_active or not self.audio_stream:
            return

        # If destination is Stereo (2 channels) and input is Mono (1 channel, 16-bit):
        # Double the samples so Left & Right channels are filled identically
        if self.output_channels >= 2:
            try:
                mono_arr = np.frombuffer(pcm_payload, dtype=np.int16)
                stereo_bytes = np.repeat(mono_arr, 2).tobytes()
                final_payload = stereo_bytes
            except Exception:
                final_payload = pcm_payload
        else:
            final_payload = pcm_payload

        if not self.audio_queue.full():
            try:
                self.audio_queue.put_nowait(final_payload)
            except queue.Full:
                pass

    def _audio_worker(self):
        while self._running:
            try:
                payload = self.audio_queue.get(timeout=0.5)
                if not self.audio_active or not self.audio_stream:
                    continue
                self.audio_stream.write(payload)
            except queue.Empty:
                continue
            except Exception:
                pass

    # ════════════════════════════════════════════════════════════════
    #  AUDIO PIPELINE 2: PC-TO-PHONE WIRELESS SPEAKER (WASAPI Loopback)
    # ════════════════════════════════════════════════════════════════

    def start_speaker_stream(self, callback: Callable[[bytes], None]) -> Tuple[bool, str]:
        """
        Capture Windows System Audio in real-time via WASAPI Loopback and stream to phone.
        Laptop speakers remain active and unmuted.
        """
        if not HAS_WASAPI_LOOPBACK:
            return False, "WASAPI Loopback requires PyAudioWPatch on Windows."

        with self._lock:
            try:
                if self.pa_instance is None:
                    self.pa_instance = pyaudio.PyAudio()

                loopback = self.pa_instance.get_default_wasapi_loopback()
                if not loopback:
                    return False, "Could not find default WASAPI Loopback device."

                self.speaker_callback = callback
                channels = int(loopback.get("maxInputChannels", 2))
                rate = int(loopback.get("defaultSampleRate", 48000))

                def _loopback_callback(in_data, frame_count, time_info, status):
                    if self.speaker_active and self.speaker_callback and in_data:
                        try:
                            self.speaker_callback(in_data)
                        except Exception:
                            pass
                    return (None, pyaudio.paContinue)

                self.speaker_stream = self.pa_instance.open(
                    format=pyaudio.paInt16,
                    channels=channels,
                    rate=rate,
                    input=True,
                    input_device_index=loopback["index"],
                    stream_callback=_loopback_callback,
                    frames_per_buffer=1024,
                )
                self.speaker_stream.start_stream()
                self.speaker_active = True
                return True, f"Wireless Speaker active ({loopback.get('name')})"
            except Exception as e:
                self.speaker_active = False
                return False, f"Speaker stream error: {e}"

    def stop_speaker_stream(self):
        """Stop WASAPI Loopback audio capture."""
        with self._lock:
            self.speaker_active = False
            self.speaker_callback = None
            if self.speaker_stream:
                try:
                    self.speaker_stream.stop_stream()
                    self.speaker_stream.close()
                except Exception:
                    pass
                self.speaker_stream = None
            print("[SPEAKER] Wireless speaker loopback released.")

    # ════════════════════════════════════════════════════════════════
    #  TEARDOWN & CLEANUP
    # ════════════════════════════════════════════════════════════════

    def cleanup_all(self):
        """Release all hardware instances immediately and terminate background loops."""
        self._running = False
        self.stop_camera()
        self.stop_audio()
        self.stop_speaker_stream()
        if self.pa_instance:
            try:
                self.pa_instance.terminate()
            except Exception:
                pass
            self.pa_instance = None


# Singleton instance
media_driver = MediaDriver()
