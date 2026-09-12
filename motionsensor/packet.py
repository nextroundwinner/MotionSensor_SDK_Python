"""Package framing: start/stop byte, byte stuffing and checksum.

See chapters "Structure of packages" and "General command structure".
"""

import struct
from typing import List

from .constants import START_BYTE, STOP_BYTE, STUFF_BYTE, STUFF_KEY

_SPECIAL_BYTES = (START_BYTE, STOP_BYTE, STUFF_BYTE)


def _stuff(data: bytes) -> bytes:
    out = bytearray()
    for b in data:
        if b in _SPECIAL_BYTES:
            out.append(STUFF_BYTE)
            out.append(b ^ STUFF_KEY)
        else:
            out.append(b)
    return bytes(out)


def _unstuff(data: bytes) -> bytes:
    out = bytearray()
    it = iter(data)
    for b in it:
        if b == STUFF_BYTE:
            out.append(next(it) ^ STUFF_KEY)
        else:
            out.append(b)
    return bytes(out)


def build_packet(command: int, data: bytes = b"") -> bytes:
    """Build a complete, stuffed package ready to be written to the serial port."""
    cmd_bytes = struct.pack("<H", command)
    checksum = (sum(cmd_bytes) + sum(data)) & 0xFFFF
    payload = struct.pack("<H", checksum) + cmd_bytes + bytes(data)
    return bytes([START_BYTE]) + _stuff(payload) + bytes([STOP_BYTE])


class FrameParser:
    """Incrementally extracts unstuffed, checksum-verified frames from a byte stream.

    Feed it raw bytes as they arrive from the serial port; it returns a list of
    ``(command, data)`` tuples for every complete, valid frame found so far.
    Frames with a wrong checksum are silently dropped, matching the fact that
    the sensor does not retransmit corrupted packages on its own.
    """

    def __init__(self):
        self._buf = bytearray()
        self._in_frame = False

    def feed(self, chunk: bytes) -> List[tuple]:
        frames = []
        for b in chunk:
            if not self._in_frame:
                if b == START_BYTE:
                    self._in_frame = True
                    self._buf = bytearray()
                continue

            if b == START_BYTE:
                # Unexpected new start byte: discard the incomplete frame.
                self._buf = bytearray()
                continue

            if b == STOP_BYTE:
                frame = self._parse_frame(bytes(self._buf))
                if frame is not None:
                    frames.append(frame)
                self._in_frame = False
                self._buf = bytearray()
                continue

            self._buf.append(b)
        return frames

    @staticmethod
    def _parse_frame(stuffed_payload: bytes):
        payload = _unstuff(stuffed_payload)
        if len(payload) < 4:
            return None
        checksum, command = struct.unpack("<HH", payload[0:4])
        data = payload[4:]
        calc_checksum = (sum(payload[2:4]) + sum(data)) & 0xFFFF
        if calc_checksum != checksum:
            return None
        return command, data
