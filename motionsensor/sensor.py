"""High level driver for the HASOMED MotionSensor 2.0.

Implements the subset of the communication protocol described in chapters
"Commands" / "General command structure" of the MotionSensor 2.0 documentation
that is needed to configure the sensor and run a measurement:

Init, GetSerial, GetSensorPosition, GetCalibrationData, GetScaleFactor,
GetAvailableMeasurementModes, PrepareMeasurement, UnPrepareMeasurement,
StartMeasurement, StopMeasurement, SetMeasurementMode, GetMeasurementMode,
MeasurementActive, SensorStatsExt, RawData14, RawData15, Error, KeepAlive.
"""

import queue
import struct
import threading
from dataclasses import dataclass
from typing import Callable, List, Optional

import serial

from .constants import (
    BAUDRATE,
    BYTESIZE,
    MEASUREMENT_DATA_COMMANDS,
    PARITY,
    STOPBITS,
    Command,
    SensorPosition,
)
from .convert import CalibrationData, RawDataPackage, parse_calibration_data, parse_raw_imu6
from .exceptions import MotionSensorError, MotionSensorProtocolError, MotionSensorTimeoutError
from .packet import FrameParser, build_packet

DEFAULT_TIMEOUT = 2.0

# RawData14/RawData15 both use the plain Acc+Gyro sample layout from convert.parse_raw_imu6.
_RAWDATA_PARSERS = {
    Command.RawData14: parse_raw_imu6,
    Command.RawData15: parse_raw_imu6,
}


@dataclass
class InitInfo:
    version: int
    welcome_text: str


@dataclass
class MeasurementModeConfig:
    sample_rate: int
    measurement_mode: int
    acc_mode: int
    gyro_mode: int
    mag_mode: int
    send_storage_mode: int


@dataclass
class SensorStats:
    csoc: int
    ttecp: int
    ai: int
    rsoc: int
    volt: int


DataCallback = Callable[[int, RawDataPackage], None]


class MotionSensor:
    """Serial connection to one MotionSensor 2.0.

    Use as a context manager, or call :meth:`close` explicitly when done::

        with MotionSensor("/dev/ttyACM0") as sensor:
            sensor.init()
            ...
    """

    def __init__(self, port: str, baudrate: int = BAUDRATE, timeout: float = DEFAULT_TIMEOUT):
        self._timeout = timeout
        self._ser = serial.Serial(
            port,
            baudrate=baudrate,
            bytesize=BYTESIZE,
            parity=PARITY,
            stopbits=STOPBITS,
            timeout=0.1,
        )
        self._parser = FrameParser()
        self._resp_queue: "queue.Queue[tuple]" = queue.Queue()
        self._send_lock = threading.Lock()
        self._data_callback: Optional[DataCallback] = None
        self._package_count = 0
        self._running = True
        self._reader_thread = threading.Thread(target=self._reader_loop, daemon=True)
        self._reader_thread.start()

    def __enter__(self) -> "MotionSensor":
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()

    def close(self):
        self._running = False
        if self._reader_thread.is_alive():
            self._reader_thread.join(timeout=1.0)
        if self._ser.is_open:
            self._ser.close()

    def set_data_callback(self, callback: Optional[DataCallback]):
        """Registers a callback invoked as ``callback(command, RawDataPackage)`` for
        every incoming RawData14/RawData15 package received while a measurement runs."""
        self._data_callback = callback

    @property
    def received_package_count(self) -> int:
        return self._package_count

    # -- low level plumbing --------------------------------------------------

    def _reader_loop(self):
        while self._running:
            try:
                chunk = self._ser.read(4096)
            except serial.SerialException:
                break
            if not chunk:
                continue
            for command, data in self._parser.feed(chunk):
                self._handle_frame(command, data)

    def _handle_frame(self, command: int, data: bytes):
        if command in MEASUREMENT_DATA_COMMANDS:
            self._package_count += 1
            parser = _RAWDATA_PARSERS.get(command)
            if self._data_callback is not None:
                package = parser(data) if parser else data
                self._data_callback(command, package)
            return
        self._resp_queue.put((command, data))

    def _send_command(self, command: Command, data: bytes = b"", timeout: Optional[float] = None) -> bytes:
        with self._send_lock:
            # Drop stale responses from a previous, unrelated command.
            while not self._resp_queue.empty():
                self._resp_queue.get_nowait()

            self._ser.write(build_packet(int(command), data))

            try:
                resp_command, resp_data = self._resp_queue.get(timeout=timeout or self._timeout)
            except queue.Empty:
                raise MotionSensorTimeoutError(f"No response for command {command.name}")

            if resp_command == Command.Error:
                error_code = struct.unpack("<I", resp_data[0:4])[0]
                raise MotionSensorError(error_code)

            expected = int(command) + 1
            if resp_command != expected:
                raise MotionSensorProtocolError(
                    f"Expected response {expected} ({command.name}Ack) for command "
                    f"{command.name}, got {resp_command}"
                )
            return resp_data

    # -- commands -------------------------------------------------------------

    def init(self) -> InitInfo:
        data = self._send_command(Command.Init)
        version, text_length = struct.unpack("<II", data[0:8])
        welcome_text = data[8 : 8 + text_length].decode("ascii", errors="replace")
        return InitInfo(version=version, welcome_text=welcome_text)

    def keep_alive(self):
        self._send_command(Command.KeepAlive)

    def get_serial(self) -> int:
        data = self._send_command(Command.GetSerial)
        return struct.unpack("<I", data[0:4])[0]

    def get_sensor_position(self) -> SensorPosition:
        data = self._send_command(Command.GetSensorPosition)
        return SensorPosition(struct.unpack("<I", data[0:4])[0])

    def get_calibration_data(self, channel: int, mode: int) -> CalibrationData:
        request = struct.pack("<II", channel, mode)
        data = self._send_command(Command.GetCalibrationData, request)
        return parse_calibration_data(data)

    def get_scale_factor(self, channel: int, mode: int) -> float:
        request = struct.pack("<II", channel, mode)
        data = self._send_command(Command.GetScaleFactor, request)
        _channel, _mode, scale_factor = struct.unpack("<IIi", data[0:12])
        return scale_factor / 1_000_000.0

    def get_available_measurement_modes(self) -> List[int]:
        data = self._send_command(Command.GetAvailableMeasurementModes)
        count = struct.unpack("<I", data[0:4])[0]
        return list(struct.unpack(f"<{count}I", data[4 : 4 + count * 4]))

    def prepare_measurement(self) -> int:
        """Returns the session id, required to request lost packages later."""
        data = self._send_command(Command.PrepareMeasurement)
        return struct.unpack("<I", data[0:4])[0]

    def unprepare_measurement(self):
        self._send_command(Command.UnPrepareMeasurement)

    def start_measurement(self) -> int:
        """Returns the sensor's start time in ms."""
        self._package_count = 0
        data = self._send_command(Command.StartMeasurement)
        return struct.unpack("<I", data[0:4])[0]

    def stop_measurement(self) -> "tuple[int, int]":
        """Returns (stop time in ms, number of packages sent)."""
        data = self._send_command(Command.StopMeasurement)
        return struct.unpack("<II", data[0:8])

    def set_measurement_mode(
        self,
        sample_rate: int,
        measurement_mode: int,
        acc_mode: int,
        gyro_mode: int,
        mag_mode: int,
        send_storage_mode: int,
        timeout: float = 2.0,
    ):
        request = struct.pack(
            "<IIIIII",
            sample_rate,
            measurement_mode,
            acc_mode,
            gyro_mode,
            mag_mode,
            send_storage_mode,
        )
        self._send_command(Command.SetMeasurementMode, request, timeout=timeout)

    def get_measurement_mode(self) -> MeasurementModeConfig:
        data = self._send_command(Command.GetMeasurementMode)
        values = struct.unpack("<IIIIII", data[0:24])
        return MeasurementModeConfig(*values)

    def measurement_active(self) -> bool:
        data = self._send_command(Command.MeasurementActive)
        return bool(struct.unpack("<I", data[0:4])[0])

    def sensor_stats_ext(self) -> SensorStats:
        data = self._send_command(Command.SensorStatsExt)
        values = struct.unpack("<5i", data[0:20])
        return SensorStats(*values)
