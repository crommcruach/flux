"""
MIDI Clock Manager
Server-side clock input/output for tempo synchronisation (mido + python-rtmidi).
"""
import mido
import time
import threading
import logging
from collections import deque

logger = logging.getLogger(__name__)


class MIDIClockManager:
    CLOCK    = 0xF8
    START    = 0xFA
    CONTINUE = 0xFB
    STOP     = 0xFC
    PPQN     = 24

    def __init__(self):
        self.input_port          = None
        self.input_device_name   = None
        self.input_thread        = None
        self.is_receiving        = False

        self.output_port         = None
        self.output_device_name  = None
        self.output_thread       = None
        self.is_sending          = False

        self.bpm             = 0.0
        self.is_playing      = False
        self.beat_position   = 0.0      # 0.0–4.0 (quarter notes within a bar)
        self.clock_times     = deque(maxlen=24)
        self.last_clock_time = 0.0
        self.clock_count     = 0

        self.output_bpm     = 120.0
        self.output_running = False

        self.on_start_callback = None
        self.on_stop_callback  = None
        self.on_beat_callback  = None

    # ── Device discovery ──────────────────────────────────────────────────────

    def get_input_devices(self):
        try:
            return mido.get_input_names()
        except Exception as e:
            logger.error("MIDI input devices error: %s", e)
            return []

    def get_output_devices(self):
        try:
            return mido.get_output_names()
        except Exception as e:
            logger.error("MIDI output devices error: %s", e)
            return []

    # ── Input (clock receive) ─────────────────────────────────────────────────

    def connect_input(self, device_name=None):
        try:
            if self.is_receiving:
                self.disconnect_input()
            if device_name is None:
                devices = self.get_input_devices()
                if not devices:
                    raise RuntimeError("No MIDI input devices found")
                device_name = devices[0]
            self.input_port        = mido.open_input(device_name)
            self.input_device_name = device_name
            self.is_receiving      = True
            self.input_thread      = threading.Thread(target=self._input_loop, daemon=True, name="midi-clock-in")
            self.input_thread.start()
            logger.info("MIDI input connected: %s", device_name)
            return True
        except Exception as e:
            logger.error("MIDI connect input: %s", e)
            return False

    def disconnect_input(self):
        self.is_receiving = False
        if self.input_thread:
            self.input_thread.join(timeout=2)
            self.input_thread = None
        if self.input_port:
            self.input_port.close()
            self.input_port = None
        self.input_device_name = None

    def _input_loop(self):
        try:
            for msg in self.input_port:
                if not self.is_receiving:
                    break
                if   msg.type == 'clock':    self._handle_clock()
                elif msg.type == 'start':    self._handle_start()
                elif msg.type == 'continue': self._handle_continue()
                elif msg.type == 'stop':     self._handle_stop()
        except Exception as e:
            logger.error("MIDI input loop: %s", e)

    def _handle_clock(self):
        now = time.monotonic()
        if self.last_clock_time > 0:
            self.clock_times.append(now - self.last_clock_time)
        self.last_clock_time = now
        self.clock_count += 1
        if len(self.clock_times) >= 8:
            avg = sum(self.clock_times) / len(self.clock_times)
            if avg > 0:
                self.bpm = 60.0 / (avg * self.PPQN)
        self.beat_position = (self.clock_count % 96) / 24.0
        if self.clock_count % self.PPQN == 0 and self.on_beat_callback:
            try:
                self.on_beat_callback(int(self.beat_position) % 4)
            except Exception:
                pass

    def _handle_start(self):
        self.is_playing    = True
        self.clock_count   = 0
        self.beat_position = 0.0
        if self.on_start_callback:
            try:
                self.on_start_callback()
            except Exception:
                pass

    def _handle_continue(self):
        self.is_playing = True
        if self.on_start_callback:
            try:
                self.on_start_callback()
            except Exception:
                pass

    def _handle_stop(self):
        self.is_playing = False
        if self.on_stop_callback:
            try:
                self.on_stop_callback()
            except Exception:
                pass

    # ── Output (clock send) ───────────────────────────────────────────────────

    def connect_output(self, device_name=None, bpm=120.0):
        try:
            if self.is_sending:
                self.disconnect_output()
            if device_name is None:
                devices = self.get_output_devices()
                if not devices:
                    raise RuntimeError("No MIDI output devices found")
                device_name = devices[0]
            self.output_port        = mido.open_output(device_name)
            self.output_device_name = device_name
            self.output_bpm         = max(20.0, min(300.0, float(bpm)))
            self.is_sending         = True
            self.output_thread      = threading.Thread(target=self._output_loop, daemon=True, name="midi-clock-out")
            self.output_thread.start()
            logger.info("MIDI output connected: %s @ %.1f BPM", device_name, bpm)
            return True
        except Exception as e:
            logger.error("MIDI connect output: %s", e)
            return False

    def disconnect_output(self):
        self.is_sending     = False
        self.output_running = False
        if self.output_thread:
            self.output_thread.join(timeout=2)
            self.output_thread = None
        if self.output_port:
            try:
                self.output_port.send(mido.Message.from_bytes([self.STOP]))
            except Exception:
                pass
            self.output_port.close()
            self.output_port = None
        self.output_device_name = None

    def _output_loop(self):
        while self.is_sending:
            if self.output_running:
                interval = 60.0 / (self.output_bpm * self.PPQN)
                try:
                    self.output_port.send(mido.Message.from_bytes([self.CLOCK]))
                except Exception as e:
                    logger.error("MIDI clock send error: %s", e)
                    break
                time.sleep(interval)
            else:
                time.sleep(0.01)

    def send_start(self):
        if self.output_port and self.is_sending:
            self.output_port.send(mido.Message.from_bytes([self.START]))
            self.output_running = True

    def send_continue(self):
        if self.output_port and self.is_sending:
            self.output_port.send(mido.Message.from_bytes([self.CONTINUE]))
            self.output_running = True

    def send_stop(self):
        if self.output_port and self.is_sending:
            self.output_port.send(mido.Message.from_bytes([self.STOP]))
            self.output_running = False

    def set_output_bpm(self, bpm):
        self.output_bpm = max(20.0, min(300.0, float(bpm)))

    # ── Status ────────────────────────────────────────────────────────────────

    def get_status(self):
        return {
            'input': {
                'connected':     self.is_receiving,
                'device':        self.input_device_name,
                'bpm':           round(self.bpm, 1),
                'playing':       self.is_playing,
                'beat_position': round(self.beat_position, 2),
            },
            'output': {
                'connected': self.is_sending,
                'device':    self.output_device_name,
                'bpm':       self.output_bpm,
                'running':   self.output_running,
            },
        }


# ── Singleton ─────────────────────────────────────────────────────────────────

_instance: MIDIClockManager | None = None


def get_midi_clock_manager() -> MIDIClockManager:
    global _instance
    if _instance is None:
        _instance = MIDIClockManager()
    return _instance
