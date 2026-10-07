from typing import Annotated, Any, Literal, Self, TypeIs

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    model_validator,
)

# ---------------------------------------------------------------------------
# isinstance(dict) tpying helper function
# ---------------------------------------------------------------------------


def is_dict(x: object) -> TypeIs[dict[object, object]]:
    return isinstance(x, dict)


# ---------------------------------------------------------------------------
# base model
# ---------------------------------------------------------------------------


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


DSPath = Annotated[str, StringConstraints(pattern=r"^DS:\S+$")]
NTPath = Annotated[str, StringConstraints(pattern=r"^NT:/")]
SignalPath = Annotated[str, StringConstraints(pattern=r"^/")]

# ---------------------------------------------------------------------------
# signal models
# ---------------------------------------------------------------------------


class MatchInfo(StrictModel):
    enabled: DSPath | SignalPath
    autonomous: DSPath | SignalPath
    fms_control: NTPath | SignalPath


class PowerSignals(StrictModel):
    voltage_signal: SignalPath = Field(alias="voltage")
    brownout_signal: SignalPath = Field(alias="brownout")


class CommsSignals(StrictModel):
    radio_status_json: SignalPath = Field(alias="radio_status")


class CanSignals(StrictModel):
    util: SignalPath


class CameraSignals(StrictModel):
    health_signal: SignalPath = Field(alias="health")
    accepted_ts_us: SignalPath = Field(alias="accepted_ts")


# ---------------------------------------------------------------------------
# generic signal source wrapper
# ---------------------------------------------------------------------------


class Source[S: StrictModel](StrictModel):
    instances: dict[str, S] = Field(min_length=1)
    singleton: bool = False


class Sources(StrictModel):
    match_info: Source[MatchInfo]
    power: Source[PowerSignals]
    comms: Source[CommsSignals]
    can: Source[CanSignals]
    cameras: Source[CameraSignals]

    @model_validator(mode="before")
    @classmethod
    def normalize_singletons(cls, data: object) -> object:
        if not is_dict(data):
            return data

        out: dict[object, object] = {}
        for name, value in data.items():
            if is_dict(value) and "instances" not in value:
                value = {"instances": {name: value}, "singleton": True}
            out[name] = value
        return out


# ---------------------------------------------------------------------------
# threshold models
# ---------------------------------------------------------------------------


class IntervalSettings(StrictModel):
    merge_intervals_gap_s: float = Field(ge=0)
    min_interval_duration_s: float = Field(ge=0)


class BrownoutThresholds(IntervalSettings):
    warn_voltage: float = Field(default=7.5, ge=5.5, le=7.5)
    brownout_voltage: float = Field(default=6.8, ge=5.0, le=6.8)

    merge_intervals_gap_s: float = Field(default=0.1, ge=0.05, le=0.5)
    min_interval_duration_s: float = Field(default=0, ge=0, le=0.25)

    @model_validator(mode="after")
    def check_order(self) -> Self:
        if self.brownout_voltage >= self.warn_voltage:
            raise ValueError("brownout_voltage must be below warn_voltage")
        return self


class RadioThresholds(IntervalSettings):
    err_dbm: int = Field(default=-70)  # likely dropouts
    warn_dbm: int = Field(default=-60)  # warn
    # info_dbm: int = Field(default=-50)  # acceptable but not ideal
    err_snr: int = Field(default=20)  # severe, expect packet loss
    warn_snr: int = Field(default=30)  # marginal
    # info_snr: int = Field(default=40)  # ok but could be better

    merge_intervals_gap_s: float = Field(default=0.1, ge=0.05, le=0.5)
    min_interval_duration_s: float = Field(default=0, ge=0, le=0.25)

    @model_validator(mode="after")
    def check_order(self) -> Self:
        if self.err_dbm >= self.warn_dbm:
            raise ValueError("err_dbm must be below warn_dbm")
        if self.err_snr >= self.warn_snr:
            raise ValueError("err_snr must be below warn_snr")
        return self


class CanUtilThresholds(StrictModel):
    warn_sustained_level: float = Field(default=0.8, ge=0.6, le=0.9)
    warn_sustained_s: float = Field(default=0.5, ge=0.2, le=3)
    warn_peak: float = Field(default=0.95, ge=0.75, le=0.99)


class CameraHealthThresholds(StrictModel):
    warn_sustained_s: float = Field(default=0.5, ge=0.1, le=5)


class AprilTagThresholds(StrictModel):
    warn_pct: float = Field(default=50, ge=10, le=100)


# ---------------------------------------------------------------------------
# generic check config
# ---------------------------------------------------------------------------


class CheckConfig[T: StrictModel](StrictModel):
    defaults: T
    overrides: dict[str, dict[str, Any]] = Field(default_factory=dict)

    def resolve(self, instance: str) -> T:
        """set thresholds based on defaults supplied and overrides for this instance"""
        override = self.overrides.get(instance)
        if not override:
            return self.defaults

        # unpacks each dictioanry using ** and recombines into a new dictionary
        # where duplicated keys from second input dict overwite values from first
        merged = {**self.defaults.model_dump(), **override}

        # returns a typed validated model
        return type(self.defaults).model_validate(merged)


class Thresholds(StrictModel):
    brownout: CheckConfig[BrownoutThresholds] | None = None
    radio_signal: CheckConfig[RadioThresholds] | None = None
    can_util: CheckConfig[CanUtilThresholds] | None = None
    camera_health: CheckConfig[CameraHealthThresholds] | None = None
    april_tag: CheckConfig[CameraHealthThresholds] | None = Field(alias="april_tag_seen")


# ---------------------------------------------------------------------------
# root
# ---------------------------------------------------------------------------


class Config(StrictModel):
    version: Literal[1]
    sources: Sources
    thresholds: Thresholds
