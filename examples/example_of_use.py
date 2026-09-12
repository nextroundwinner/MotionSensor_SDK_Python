#!/usr/bin/env python3
"""Example use of the MotionSensor library, following chapter "Example of use"
of the MotionSensor 2.0 documentation:

    Init -> GetSerial, GetPosition, GetAvailableMeasurementModes, GetScaleFactor,
    GetCalibrationData, SetMeasurementMode (place settings, once per connection)
    -> PrepareMeasurement -> StartMeasurement -> (MeasPackage ...) -> StopMeasurement

Connects to a sensor on /dev/ttyACM0, streams RawData15 (1 sample/package) for a
few seconds, converts samples to physical units and prints a short summary.
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from motionsensor import (
    AccMode,
    Channel,
    GyroMode,
    MagMode,
    MotionSensor,
    SendStorageMode,
    apply_calibration,
    lsb_to_physical,
)
from motionsensor.constants import Command, MEASUREMENT_DATA_COMMANDS

PORT = "/dev/ttyACM0"
SAMPLE_RATE_HZ = 100
MEASUREMENT_DURATION_S = 3.0

# Default flash-calibrated channel/mode combinations, see chapter "SetCalibrationData".
ACC_MODE = AccMode.G8
GYRO_MODE = GyroMode.DPS1000
MAG_MODE = MagMode.GS1_3


def main() -> int:
    with MotionSensor(PORT) as sensor:
        info = sensor.init()
        print(f"Connected: protocol version {info.version}, welcome text: {info.welcome_text!r}")

        serial_number = sensor.get_serial()
        print(f"Serial number: {serial_number}")

        position = sensor.get_sensor_position()
        print(f"Sensor position: {position.name}")

        modes = sensor.get_available_measurement_modes()
        mode_names = [MEASUREMENT_DATA_COMMANDS.get(m, str(m)) for m in modes]
        print(f"Available measurement modes: {mode_names}")

        acc_scale = sensor.get_scale_factor(Channel.Acc, ACC_MODE)
        gyro_scale = sensor.get_scale_factor(Channel.Gyro, GYRO_MODE)
        mag_scale = sensor.get_scale_factor(Channel.Mag, MAG_MODE)
        print(f"Scale factors: acc={acc_scale}, gyro={gyro_scale}, mag={mag_scale}")

        acc_calib = sensor.get_calibration_data(Channel.Acc, ACC_MODE)
        gyro_calib = sensor.get_calibration_data(Channel.Gyro, GYRO_MODE)
        print(f"Acc calibration: bias={acc_calib.bias}")
        print(f"Gyro calibration: bias={gyro_calib.bias}")

        stats = sensor.sensor_stats_ext()
        print(f"Battery: {stats.rsoc}% ({stats.volt} mV)")

        sensor.set_measurement_mode(
            sample_rate=SAMPLE_RATE_HZ,
            measurement_mode=Command.RawData15,
            acc_mode=ACC_MODE,
            gyro_mode=GYRO_MODE,
            mag_mode=MAG_MODE,
            send_storage_mode=SendStorageMode.SendAndNotStore,
        )

        received = {"packages": 0, "samples": 0}

        def on_data(command, package):
            received["packages"] += 1
            for sample in package.samples:
                received["samples"] += 1
                acc_phys = tuple(lsb_to_physical(v, acc_scale) for v in sample.acc)
                gyro_phys = tuple(lsb_to_physical(v, gyro_scale) for v in sample.gyro)
                acc_calibrated = apply_calibration(acc_phys, acc_calib)
                gyro_calibrated = apply_calibration(gyro_phys, gyro_calib)
                if received["samples"] % SAMPLE_RATE_HZ == 0:
                    print(
                        f"  sample {received['samples']}: "
                        f"acc={tuple(round(v, 3) for v in acc_calibrated)} m/s^2, "
                        f"gyro={tuple(round(v, 3) for v in gyro_calibrated)} deg/s"
                    )

        sensor.set_data_callback(on_data)

        session_id = sensor.prepare_measurement()
        print(f"Prepared measurement, session id {session_id}")

        start_time = sensor.start_measurement()
        print(f"Measurement started at t={start_time} ms")

        deadline = time.monotonic() + MEASUREMENT_DURATION_S
        while time.monotonic() < deadline:
            time.sleep(0.5)
            print(f"  active={sensor.measurement_active()}, packages so far={received['packages']}")

        stop_time, package_count = sensor.stop_measurement()
        print(f"Measurement stopped at t={stop_time} ms, sensor reports {package_count} packages")
        print(f"Received {received['packages']} packages / {received['samples']} samples")

        sensor.keep_alive()
    return 0


if __name__ == "__main__":
    sys.exit(main())
