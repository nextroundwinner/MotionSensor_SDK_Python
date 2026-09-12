"""Conversion of raw measurement data to physical units.

See chapter "Conversion of measurement data (packages: RawDataXX)".
"""

import struct
from dataclasses import dataclass
from typing import List, Tuple

Vector3 = Tuple[float, float, float]


@dataclass
class CalibrationData:
    channel: int
    mode: int
    bias: Vector3
    rotation_matrix: Tuple[Vector3, Vector3, Vector3]
    cg1: Vector3
    cg2: Vector3


@dataclass
class ImuSample:
    acc: Vector3
    gyro: Vector3


@dataclass
class RawDataPackage:
    package_number: int
    samples: List[ImuSample]


def parse_calibration_data(data: bytes) -> CalibrationData:
    """Unpacks the 80-byte structure used by GetCalibrationData/SetCalibrationData.

    All values are scaled integers (factor 1,000,000); this returns them as floats.
    """
    values = struct.unpack("<20i", data[0:80])
    scale = 1_000_000.0
    channel, mode = values[0], values[1]
    bias = tuple(v / scale for v in values[2:5])
    matrix_flat = tuple(v / scale for v in values[5:14])
    rotation_matrix = (matrix_flat[0:3], matrix_flat[3:6], matrix_flat[6:9])
    cg1 = tuple(v / scale for v in values[14:17])
    cg2 = tuple(v / scale for v in values[17:20])
    return CalibrationData(channel, mode, bias, rotation_matrix, cg1, cg2)


def lsb_to_physical(raw: int, scale_factor: float) -> float:
    """scale_LSB = LSB / scale_factor, see chapter "Conversion of LSB values"."""
    return raw / scale_factor


def apply_calibration(scaled_xyz: Vector3, calib: CalibrationData) -> Vector3:
    """Applies bias, rotation matrix and Cg1/Cg2 as described in "Apply calibration data"."""
    centered = tuple(scaled_xyz[i] - calib.bias[i] for i in range(3))
    rotated = tuple(
        sum(centered[j] * calib.rotation_matrix[j][i] for j in range(3)) for i in range(3)
    )
    return tuple(
        rotated[i] * calib.cg1[i] + rotated[i] ** 2 * calib.cg2[i] for i in range(3)
    )


def parse_raw_imu6(data: bytes) -> RawDataPackage:
    """Parses RawData14/RawData15 packages: package number + N * (AccXYZ, GyroXYZ) as int16."""
    package_number = struct.unpack("<I", data[0:4])[0]
    sample_data = data[4:]
    num_samples = len(sample_data) // 12
    samples = []
    for i in range(num_samples):
        chunk = sample_data[i * 12 : (i + 1) * 12]
        acc_x, acc_y, acc_z, gyro_x, gyro_y, gyro_z = struct.unpack("<6h", chunk)
        samples.append(ImuSample(acc=(acc_x, acc_y, acc_z), gyro=(gyro_x, gyro_y, gyro_z)))
    return RawDataPackage(package_number=package_number, samples=samples)
