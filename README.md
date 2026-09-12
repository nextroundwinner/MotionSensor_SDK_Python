# MotionSensor SDK (Python)

A small Python library for talking to a **HASOMED MotionSensor 2.0** IMU over
its serial protocol (USB-CDC, e.g. `/dev/ttyACM0`, or a Bluetooth SPP virtual
COM port). It implements package framing (start/stop byte, byte stuffing,
checksum) and a synchronous command/acknowledge API on top of it, plus
asynchronous streaming of measurement data.

This library implements a deliberate subset of the full protocol described in
*"Documentation HASOMED MotionSensor 2.0"* (Rev. 11): `Init`, `GetSerial`,
`GetSensorPosition`, `GetCalibrationData`, `GetScaleFactor`,
`GetAvailableMeasurementModes`, `PrepareMeasurement`,
`UnPrepareMeasurement`, `StartMeasurement`, `StopMeasurement`,
`SetMeasurementMode`, `GetMeasurementMode`, `MeasurementActive`,
`SensorStatsExt`, `RawData14`, `RawData15`, `Error` and `KeepAlive`.

## Installation

```bash
pip install -r requirements.txt
```

Only dependency is [`pyserial`](https://pypi.org/project/pyserial/).

## Connecting to a sensor

```python
from motionsensor import MotionSensor

with MotionSensor("/dev/ttyACM0") as sensor:
    info = sensor.init()
    print(info.welcome_text)
# connection is closed automatically at the end of the `with` block
```

`MotionSensor(port, baudrate=460800, timeout=2.0)` opens the serial port
immediately (8 data bits, 1 stop bit, no parity, no flow control — the values
required by the protocol) and starts a background thread that continuously
reads and decodes packages. Every command method below sends a package and
blocks until the matching acknowledge package arrives, or raises an exception
(see [Error handling](#error-handling)) after `timeout` seconds.

If you don't use the `with` statement, call `sensor.close()` yourself when
you are done.

## Command reference

Every command is a method on `MotionSensor`. It sends the request, waits for
the `...Ack` package the sensor sends back, and returns its decoded content
(or raises on error — there is no separate "Ack" object to inspect).

### `init()`

Sends `Init`, must be called once at the beginning of the connection.
Returns an `InitInfo(version, welcome_text)`.

```python
info = sensor.init()
print(info.version, info.welcome_text)
```

### `get_serial()`

Sends `GetSerial`. Returns the sensor's serial number as `int`.

```python
serial_number = sensor.get_serial()
```

### `get_sensor_position()`

Sends `GetSensorPosition`. Returns a `SensorPosition` enum value describing
where the sensor is meant to be worn (`FootLeft`, `FootRight`, `ShankLeft`,
`ShankRight`, `ThighLeft`, `ThighRight`, `Pelvis`, `Sternum`, `WristLeft`,
`WristRight`, `PelvisDay`, `PelvisNight`).

```python
from motionsensor import SensorPosition

position = sensor.get_sensor_position()
assert position == SensorPosition.FootRight
```

### `get_calibration_data(channel, mode)`

Sends `GetCalibrationData` for one sensor chip (`channel`) and measurement
range (`mode`) and returns a `CalibrationData(channel, mode, bias,
rotation_matrix, cg1, cg2)`. Only specific `channel`/`mode` combinations have
calibration data stored in flash (see [Enums and constants](#enums-and-constants)); requesting
any other combination raises `MotionSensorError` (`ErrorCalibrationRead`).

```python
from motionsensor import Channel, AccMode

calib = sensor.get_calibration_data(Channel.Acc, AccMode.G8)
print(calib.bias, calib.rotation_matrix, calib.cg1, calib.cg2)
```

Use `apply_calibration()` (see [Converting raw data](#converting-raw-data-to-physical-units))
to apply the result to raw samples.

### `get_scale_factor(channel, mode)`

Sends `GetScaleFactor` for one `channel`/`mode` combination. Returns the
scale factor as a `float` (already divided by the protocol's `1 000 000`
fixed-point scaling).

```python
acc_scale = sensor.get_scale_factor(Channel.Acc, AccMode.G8)
```

### `get_available_measurement_modes()`

Sends `GetAvailableMeasurementModes`. Returns a `list[int]` of measurement
data command numbers the connected sensor supports (which `RawDataXX` /
`OrientationData` / ... commands it can be configured to stream). Not every
sensor supports every mode — always query this instead of hard-coding one.

```python
modes = sensor.get_available_measurement_modes()
```

### `set_measurement_mode(sample_rate, measurement_mode, acc_mode, gyro_mode, mag_mode, send_storage_mode, timeout=2.0)`

Sends `SetMeasurementMode`. Configures the sample rate (Hz, up to 600) and
which measurement data package the sensor will stream once
`start_measurement()` is called, plus the sensitivity range of each chip and
whether data is sent, stored on the internal SD-card, or both. The sensor
must not currently be prepared (see `prepare_measurement()`). The call can
take up to ~250 ms because internal sensors are reinitialized.

```python
from motionsensor import GyroMode, MagMode, SendStorageMode
from motionsensor.constants import Command

sensor.set_measurement_mode(
    sample_rate=100,
    measurement_mode=Command.RawData15,   # or Command.RawData14, an int works too
    acc_mode=AccMode.G8,
    gyro_mode=GyroMode.DPS1000,
    mag_mode=MagMode.GS1_3,
    send_storage_mode=SendStorageMode.SendAndNotStore,
)
```

### `get_measurement_mode()`

Sends `GetMeasurementMode`. Returns the currently configured
`MeasurementModeConfig(sample_rate, measurement_mode, acc_mode, gyro_mode,
mag_mode, send_storage_mode)`.

```python
config = sensor.get_measurement_mode()
```

### `prepare_measurement()`

Sends `PrepareMeasurement`. Must be called before `start_measurement()`; once
called, the measurement mode cannot be changed until
`unprepare_measurement()` or `stop_measurement()`. Returns the session id
(`int`) of the upcoming measurement.

```python
session_id = sensor.prepare_measurement()
```

### `unprepare_measurement()`

Sends `UnPrepareMeasurement`, releasing the prepared state without running a
measurement. Not needed after `stop_measurement()`, which does this
implicitly.

```python
sensor.unprepare_measurement()
```

### `start_measurement()`

Sends `StartMeasurement`. The sensor starts streaming measurement data
packages (`RawData14`/`RawData15`/... depending on `set_measurement_mode()`)
immediately; register a callback with `set_data_callback()` beforehand to
receive them (see [Receiving measurement data](#receiving-measurement-data-rawdata14--rawdata15)).
Returns the sensor's start time in milliseconds.

```python
start_time_ms = sensor.start_measurement()
```

### `stop_measurement()`

Sends `StopMeasurement`. Returns a `(stop_time_ms, package_count)` tuple —
the sensor's stop time and the number of measurement packages it sent.

```python
stop_time_ms, package_count = sensor.stop_measurement()
```

### `measurement_active()`

Sends `MeasurementActive`. Returns `True`/`False` depending on whether a
measurement is currently running — useful for polling from another process
or after reconnecting.

```python
if sensor.measurement_active():
    ...
```

### `sensor_stats_ext()`

Sends `SensorStatsExt`. Returns `SensorStats(csoc, ttecp, ai, rsoc, volt)`:
state of charge in %, time-to-empty in minutes, average current in mA,
relative state of charge in %, and battery voltage in mV.

```python
stats = sensor.sensor_stats_ext()
print(f"{stats.rsoc}% ({stats.volt} mV)")
```

### `keep_alive()`

Sends `KeepAlive`, resetting the sensor's standby timer so it does not turn
itself off. Call this periodically (e.g. every few seconds) during idle
periods between measurements.

```python
sensor.keep_alive()
```

### Receiving measurement data (`RawData14` / `RawData15`)

`RawData14` and `RawData15` are not requested explicitly — they arrive
asynchronously, as soon as they were selected via `set_measurement_mode()`
and a measurement is running. Register a callback with
`set_data_callback(callback)` before calling `start_measurement()`; it is
invoked from the background reader thread as
`callback(command, package)` for every package received, where `command` is
the `Command` value (`Command.RawData14` or `Command.RawData15`) and
`package` is a decoded `RawDataPackage(package_number, samples)` — `samples`
is a list of `ImuSample(acc, gyro)` with raw (LSB) accelerometer and
gyroscope readings (`RawData14` bundles up to 21 samples per package,
`RawData15` exactly 1). `sensor.received_package_count` tracks how many
packages (of any measurement type) have been received in total.

```python
def on_data(command, package):
    for sample in package.samples:
        print(package.package_number, sample.acc, sample.gyro)

sensor.set_data_callback(on_data)
sensor.start_measurement()
```

Convert raw samples to physical units with `lsb_to_physical()` and
`apply_calibration()`, see below.

### Error handling (`Error`)

The sensor answers a failed command with an `Error` package instead of the
expected `...Ack`. This library turns that into a `MotionSensorError`
exception (with `.error_code` and `.name`, e.g. `ErrorCalibrationRead`),
raised directly from the command method that triggered it — there is no
separate method to call for it.

```python
from motionsensor import MotionSensorError

try:
    sensor.get_calibration_data(channel=0, mode=99)
except MotionSensorError as e:
    print(e.name, hex(e.error_code))
```

Other exceptions: `MotionSensorTimeoutError` (no response within `timeout`
seconds) and `MotionSensorProtocolError` (a response arrived but was not the
expected one). All three inherit from `MotionSensorException`.

## Converting raw data to physical units

Raw accelerometer/gyroscope values from `RawData14`/`RawData15` are LSB
counts. Convert them with the scale factor from `get_scale_factor()`, then
optionally apply the calibration from `get_calibration_data()`:

```python
from motionsensor import lsb_to_physical, apply_calibration

acc_scale = sensor.get_scale_factor(Channel.Acc, AccMode.G8)
acc_calib = sensor.get_calibration_data(Channel.Acc, AccMode.G8)

physical = tuple(lsb_to_physical(v, acc_scale) for v in sample.acc)  # m/s^2 (uncalibrated)
calibrated = apply_calibration(physical, acc_calib)                  # m/s^2 (calibrated)
```

The same applies to `sample.gyro` with the gyroscope's scale factor and
calibration data (unit: °/s).

## Enums and constants

Importable from `motionsensor` (or `motionsensor.constants`):

| Name | Values | Used for |
|---|---|---|
| `Channel` | `Acc=0`, `Gyro=1`, `Mag=2`, `Pressure=3` | `get_calibration_data()`, `get_scale_factor()` |
| `AccMode` | `G1..G16` (`G8` is the sensor default) | accelerometer range |
| `GyroMode` | `DPS250..DPS2000` (`DPS1000` default) | gyroscope range |
| `MagMode` | `GS0_88..GS8_1` (`GS1_3` default) | magnetometer range |
| `SendStorageMode` | `SendAndNotStore`, `SendAndStore`, `NotSendAndStore` | `set_measurement_mode()` |
| `SensorPosition` | `FootLeft`, `FootRight`, `ShankLeft`, ... | `get_sensor_position()` |

Calibration data is only stored in flash for these `channel`/`mode`
combinations: `(Channel.Acc, AccMode.G8)`, `(Channel.Acc, AccMode.G16)`,
`(Channel.Gyro, GyroMode.DPS1000)`, `(Channel.Gyro, GyroMode.DPS2000)`,
`(Channel.Mag, MagMode.GS1_3)`.

`measurement_mode` in `set_measurement_mode()` takes a measurement data
command number, e.g. `Command.RawData14` / `Command.RawData15` from
`motionsensor.constants`, or any value returned by
`get_available_measurement_modes()`. `motionsensor.constants.MEASUREMENT_DATA_COMMANDS`
maps these numbers to their names (`{144: "RawData14", 145: "RawData15", ...}`)
for logging/debugging.

## Full example

See [`examples/example_of_use.py`](examples/example_of_use.py) for a
complete, runnable walkthrough against a sensor on `/dev/ttyACM0`, following
the *"Example of use"* chapter of the MotionSensor 2.0 documentation:

```bash
python3 examples/example_of_use.py
```

It connects, reads out identification/scale/calibration data, configures and
runs a short `RawData15` measurement while printing live samples converted to
physical units, then stops the measurement and prints a summary.


## Notes
- This code is fully written and tested by AI