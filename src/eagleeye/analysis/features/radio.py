from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict, Field

from eagleeye.analysis.util import Context, Feature, FeatureResult
from eagleeye.signals import ByteSignal, TimeSeries


class NetworkStatus6(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)

    radio_dbm: int = Field(alias="signalDbm")
    radio_snr: int = Field(alias="signalNoiseRatio")


class RadioJSON(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)

    network_status6: NetworkStatus6 = Field(alias="networkStatus6")


@dataclass(frozen=True)
class RadioSample:
    radio_dbm: int
    radio_snr: int


@dataclass(frozen=True)
class RadioTelemetry(FeatureResult):
    series: TimeSeries[RadioSample]

    def __rich__(self) -> str: ...


class RadioData(Feature[RadioTelemetry]):
    key = "radio_telemetry"

    def compute(self, ctx: Context) -> RadioTelemetry:

        timestamps_us: list[int] = []
        samples: list[RadioSample] = []

        radio = ctx.require("/Robot/RadioStatus/StatusJson", ByteSignal)

        for ts_us, payload in radio.zip_between_ts():
            data = RadioJSON.model_validate_json(payload)
            ns = data.network_status6
            timestamps_us.append(ts_us)
            samples.append(RadioSample(ns.radio_dbm, ns.radio_snr))

        return RadioTelemetry(
            TimeSeries[RadioSample](
                name="radio_status", timestamps_us=timestamps_us, values=samples
            )
        )
