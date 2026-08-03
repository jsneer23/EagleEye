from __future__ import annotations

import struct
from dataclasses import dataclass, field
from typing import Any

from eagleeye.parsers import byte_decoders
from eagleeye.parsers.signals import BaseSignal

# ---------------------------------------------------------------------------
# photonvision pipeline result dataclasses
# ---------------------------------------------------------------------------

@dataclass
class TargetObservation:
    fiducial_id: int
    yaw: float
    pitch: float
    area: float
    skew: float
    pose_ambiguity: float
    best_cam_to_target: tuple[float,...]
    alt_cam_to_target: tuple[float,...]

@dataclass
class PipelineFrame:
    timestamp: int
    capture_ts_us: int
    seq_id: int
    targets: list[TargetObservation] = field(default_factory=list[TargetObservation])

    @property
    def tag_count(self) -> int:
        return sum(1 for t in self.targets if t.fiducial_id >= 0)

@dataclass(kw_only=True)
class CameraSignal(BaseSignal):
    frames: list[PipelineFrame] = field(default_factory=list)

    def append_payload(self, timestamp: int, payload: bytes) -> None:
        self.timestamps.append(timestamp)
        self.frames.append(decode_pipeline_result(payload, timestamp))

# ---------------------------------------------------------------------------
# helper functions
# ---------------------------------------------------------------------------

def _transform3d(buffer: bytes, offset: int) -> tuple[tuple[Any], int]:
    vals = struct.unpack_from("<ddddddd", buffer, offset)
    return vals, offset + 56

def _target(buffer: bytes, offset: int) -> tuple[TargetObservation, int]:

    yaw, offset = byte_decoders.f64(buffer, offset)
    pitch, offset = byte_decoders.f64(buffer, offset)
    area, offset = byte_decoders.f64(buffer, offset)
    skew, offset = byte_decoders.f64(buffer, offset)
    fid, offset = byte_decoders.i32(buffer, offset)
    _odid, offset = byte_decoders.i32(buffer, offset)
    _odconf, offset = byte_decoders.f32(buffer, offset)
    best, offset = _transform3d(buffer, offset)
    alt, offset = _transform3d(buffer, offset)
    amb, offset = byte_decoders.f64(buffer, offset)
    mar, offset = byte_decoders.u8(buffer, offset)
    offset += mar * 16
    dc, offset = byte_decoders.u8(buffer, offset)
    offset += dc * 16

    return TargetObservation(fid, yaw, pitch, area, skew, amb, best, alt), offset

# ---------------------------------------------------------------------------
# top level photonvision pipeline payload decoder
# ---------------------------------------------------------------------------

def decode_pipeline_result(payload: bytes, log_ts_s: int) -> PipelineFrame:

    offset = 0

    seq, offset   = byte_decoders.i64(payload, offset) # sequence id
    cap, offset   = byte_decoders.i64(payload, offset) # img capture timestamp
    _pub, offset  = byte_decoders.i64(payload, offset) # publish to network tables timestamp
    _pong, offset = byte_decoders.i64(payload, offset) # time since last rio pong
    count, offset = byte_decoders.u8(payload, offset)

    targets: list[TargetObservation] = []

    for _ in range(count):
        target, offset = _target(payload, offset)
        targets.append(target)

    present, offset = byte_decoders.u8(payload, offset)

    if present:

        offset += 56 + 56 + 8 + 8 + 8
        n, offset = byte_decoders.u8(payload, offset)
        offset += n*2

    if offset != len(payload):
        raise ValueError(f"struct decode consumed {offset} of {len(payload)} bytes")

    return PipelineFrame(log_ts_s, cap, seq, targets)
