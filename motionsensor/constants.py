"""Protocol constants for the HASOMED MotionSensor 2.0.

Taken from "Documentation HASOMED MotionSensor 2.0", Rev. 11 (2020-02-11).
"""

from enum import IntEnum

# Serial connection parameters (chapter "Serial connection")
BAUDRATE = 460800
BYTESIZE = 8
STOPBITS = 1
PARITY = "N"

# Special bytes (chapter "Structure of packages")
START_BYTE = 0xF0
STOP_BYTE = 0x0F
STUFF_BYTE = 0x81
STUFF_KEY = 0x55


class Command(IntEnum):
    """Command numbers implemented by this library (chapter "Commands")."""

    Init = 0x00
    InitAck = 0x01
    KeepAlive = 0x02
    KeepAliveAck = 0x03

    Error = 0x2C

    GetSerial = 0x42
    GetSerialAck = 0x43

    GetSensorPosition = 0x46
    GetSensorPositionAck = 0x47

    GetCalibrationData = 0x4E
    GetCalibrationDataAck = 0x4F

    GetScaleFactor = 0x54
    GetScaleFactorAck = 0x55

    GetAvailableMeasurementModes = 0x56
    GetAvailableMeasurementModesAck = 0x57

    PrepareMeasurement = 0x58
    PrepareMeasurementAck = 0x59
    UnPrepareMeasurement = 0x5A
    UnPrepareMeasurementAck = 0x5B

    StartMeasurement = 0x5C
    StartMeasurementAck = 0x5D
    StopMeasurement = 0x5E
    StopMeasurementAck = 0x5F

    SetMeasurementMode = 0x60
    SetMeasurementModeAck = 0x61
    GetMeasurementMode = 0x62
    GetMeasurementModeAck = 0x63

    MeasurementActive = 0x68
    MeasurementActiveAck = 0x69

    SensorStatsExt = 0x76
    SensorStatsExtAck = 0x77

    RawData14 = 0x90
    RawData15 = 0x91


# Command numbers that carry asynchronous measurement data (chapter
# "Measurement data") rather than being a synchronous command/Ack pair.
MEASUREMENT_DATA_COMMANDS = {
    125: "RawData3",
    127: "DebugData",
    128: "CalibData",
    129: "OrientationData",
    130: "RawData4",
    131: "RawData5",
    132: "RawData6",
    133: "AccComparisonData",
    134: "RawData7",
    135: "RawData8",
    136: "SyncData5",
    137: "RtData1",
    138: "RawData9",
    139: "RawData10",
    140: "RawData11",
    141: "RawData12",
    142: "GaitPhaseData",
    143: "RawData13",
    144: "RawData14",
    145: "RawData15",
    146: "RawData16",
    147: "RawData17",
}


class SensorPosition(IntEnum):
    """Chapter "Sensor positions"."""

    FootLeft = 0
    FootRight = 1
    ShankLeft = 2
    ShankRight = 3
    ThighLeft = 4
    ThighRight = 5
    Pelvis = 6
    Sternum = 7
    WristLeft = 8
    WristRight = 9
    PelvisDay = 10
    PelvisNight = 11


class Channel(IntEnum):
    """Chapter "Measurement mode of sensors"."""

    Acc = 0
    Gyro = 1
    Mag = 2
    Pressure = 3


class AccMode(IntEnum):
    G1 = 0
    G2 = 1
    G4 = 2
    G8 = 3  # default
    G16 = 4


class GyroMode(IntEnum):
    DPS250 = 0
    DPS500 = 1
    DPS1000 = 2  # default
    DPS2000 = 3


class MagMode(IntEnum):
    GS0_88 = 0
    GS1_3 = 1  # default
    GS1_9 = 2
    GS2_5 = 3
    GS4_0 = 4
    GS4_7 = 5
    GS5_6 = 6
    GS8_1 = 7


class SendStorageMode(IntEnum):
    SendAndNotStore = 0  # default
    SendAndStore = 1
    NotSendAndStore = 2


# Chapter "Error constants"
ERROR_CODES = {
    0x01: "ErrorBadPackage",
    0x02: "ErrorWrongChecksum",
    0x03: "ErrorBadData",
    0x04: "ErrorUnknownPackage",
    0xA0: "ErrorIwrapNoAnswer",
    0xB0: "ErrorInputBufferFull",
    0xB1: "ErrorInputBufferUnderrun",
    0xB2: "ErrorInputBufferOverrun",
    0xB3: "ErrorInputBufferSplit",
    0xC0: "ErrorMuxRead",
    0xD0: "ErrorCalibrationWrite",
    0xD1: "ErrorCalibrationRead",
    0xE0: "ErrorStoreWrite",
    0xE1: "ErrorStoreRead",
    0xE4: "ErrorSdCardUnavailable",
    0xE5: "ErrorSdCardSessionNotValid",
    0xE6: "ErrorSdCardCreateSessionFailed",
    0xF0: "ErrorMeasModePrepared",
    0xF1: "ErrorMeasModeNotPrepared",
    0xF2: "ErrorTimerRunning",
    0xF3: "ErrorTimerNotRunning",
    0xF4: "ErrorMeasCacheOverrun",
    0xF5: "ErrorSync",
    0x0E00: "ErrorInitBma180",
    0x0E01: "ErrorInitImu3000",
    0x0E02: "ErrorInitHmc5883",
    0x0E03: "ErrorInitMpu6050",
    0x0E04: "ErrorInitMpu9150",
    0x0E05: "ErrorInitLis331hh",
    0x0E06: "ErrorInitSdCard",
}


def error_name(code: int) -> str:
    return ERROR_CODES.get(code, f"UnknownError(0x{code:X})")
