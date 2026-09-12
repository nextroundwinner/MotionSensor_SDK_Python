from .constants import error_name


class MotionSensorException(Exception):
    """Base class for all exceptions raised by this library."""


class MotionSensorTimeoutError(MotionSensorException):
    """Raised when the sensor did not answer a command in time."""


class MotionSensorProtocolError(MotionSensorException):
    """Raised on malformed packages or unexpected responses."""


class MotionSensorError(MotionSensorException):
    """Raised when the sensor answers a command with an Error package."""

    def __init__(self, error_code: int):
        self.error_code = error_code
        self.name = error_name(error_code)
        super().__init__(f"{self.name} (0x{error_code:X})")
