from __future__ import annotations

import struct
from dataclasses import dataclass, field
from typing import Any

import util

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
    timestamp: float
    capture_ts_us: int
    seq_id: int
    targets: list[TargetObservation] = field(default_factory=list)

    @property
    def tag_count(self) -> int:
        return sum(1 for t in self.targets if t.fiducial_id >= 0)

@dataclass(kw_only=True)
class CameraSignal(util.BaseSignal):
    frames: list[PipelineFrame] = field(default_factory=list)

    def append_payload(self, timestamp: int, payload: bytes) -> None:
        self.timestamps.append(timestamp)
        self.frames.append(decode_pipeline_result(payload, timestamp * 1e-6))

# ---------------------------------------------------------------------------
# helper functions
# ---------------------------------------------------------------------------

def _transform3d(buffer: bytes, offset: int) -> tuple[tuple[Any], int]:
    vals = struct.unpack_from("<ddddddd", buffer, offset)
    return vals, offset + 56

def _target(buffer: bytes, offset: int) -> tuple[TargetObservation, int]:

    yaw, offset = util.f64(buffer, offset)
    pitch, offset = util.f64(buffer, offset)
    area, offset = util.f64(buffer, offset)
    skew, offset = util.f64(buffer, offset)
    fid, offset = util.i32(buffer, offset)
    _odid, offset = util.i32(buffer, offset)
    _odconf, offset = util.f32(buffer, offset)
    best, offset = _transform3d(buffer, offset)
    alt, offset = _transform3d(buffer, offset)
    amb, offset = util.f64(buffer, offset)
    mar, offset = util.u8(buffer, offset)
    offset += mar * 16
    dc, offset = util.u8(buffer, offset)
    offset += dc * 16

    return TargetObservation(fid, yaw, pitch, area, skew, amb, best, alt), offset

# ---------------------------------------------------------------------------
# top level photonvision pipeline payload decoder
# ---------------------------------------------------------------------------

def decode_pipeline_result(payload: bytes, log_ts_s: float) -> PipelineFrame:

    offset = 0

    seq, offset   = util.i64(payload, offset) # sequence id
    cap, offset   = util.i64(payload, offset) # img capture timestamp
    _pub, offset  = util.i64(payload, offset) # publish to network tables timestamp
    _pong, offset = util.i64(payload, offset) # time since last rio pong
    count, offset = util.u8(payload, offset)

    targets = []

    for _ in range(count):
        target, offset = _target(payload, offset)
        targets.append(target)

    present, offset = util.u8(payload, offset)

    if present:

        offset += 56 + 56 + 8 + 8 + 8
        n, offset = util.u8(payload, offset)
        offset += n*2

    if offset != len(payload):
        raise ValueError(f"struct decode consumed {offset} of {len(payload)} bytes")

    return PipelineFrame(log_ts_s, cap, seq, targets)
