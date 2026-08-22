"""
serial_esp32.py — Sends result packets to the ESP32 over USB serial.

Protocol:
  - One JSON object per line, terminated with '\\n'
  - Baud rate and port configured in config.py
  - Reconnects automatically if the serial link drops

Example packet sent:
    {"lane":"MIDDLE","pothole":0.0,"alert":"NONE","ts":1724256000}\\n
"""

import json
import time
import threading
from typing import Optional

import config

try:
    import serial
    import serial.tools.list_ports
    SERIAL_AVAILABLE = True
except ImportError:
    SERIAL_AVAILABLE = False


class SerialESP32:
    """
    Non-blocking serial bridge to the ESP32.

    Usage:
        bridge = SerialESP32()
        bridge.send(result_packet)   # fire-and-forget
        bridge.close()
    """

    def __init__(self):
        self._port   = config.SERIAL_PORT
        self._baud   = config.SERIAL_BAUDRATE
        self._ser: Optional["serial.Serial"] = None
        self._lock   = threading.Lock()
        self._enabled = config.SERIAL_ENABLED and SERIAL_AVAILABLE

        if not SERIAL_AVAILABLE and config.SERIAL_ENABLED:
            print(
                "[SerialESP32] WARNING: 'pyserial' not installed. "
                "Run: pip install pyserial\n"
                "  Serial communication disabled."
            )
            return

        if self._enabled:
            self._connect()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def send(self, packet: dict) -> bool:
        """
        Serialise *packet* as JSON and write it to the serial port.

        Returns True on success, False on failure (will attempt reconnect
        on the next call automatically).
        """
        if not self._enabled:
            return False

        line = json.dumps(packet, separators=(",", ":")) + "\n"
        encoded = line.encode("utf-8")

        with self._lock:
            if self._ser is None or not self._ser.is_open:
                self._connect()
            if self._ser is None:
                return False
            try:
                self._ser.write(encoded)
                return True
            except serial.SerialException as e:
                print(f"[SerialESP32] Write error: {e} — reconnecting next send")
                self._ser = None
                return False

    def close(self):
        with self._lock:
            if self._ser and self._ser.is_open:
                self._ser.close()
            self._ser = None

    @property
    def connected(self) -> bool:
        return self._ser is not None and self._ser.is_open

    @staticmethod
    def list_ports() -> list[str]:
        """Helper: print available serial ports."""
        if not SERIAL_AVAILABLE:
            return []
        return [p.device for p in serial.tools.list_ports.comports()]

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _connect(self):
        try:
            self._ser = serial.Serial(
                port     = self._port,
                baudrate = self._baud,
                timeout  = config.SERIAL_TIMEOUT,
            )
            time.sleep(0.5)   # let the ESP32 boot after DTR toggle
            print(f"[SerialESP32] Connected: {self._port} @ {self._baud} baud")
        except Exception as e:
            print(f"[SerialESP32] Could not open {self._port}: {e}")
            print(f"  Available ports: {self.list_ports()}")
            print(f"  Update SERIAL_PORT in config.py")
            self._ser = None
