from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Literal

import plotly.graph_objects as go
from plotly.subplots import make_subplots

if TYPE_CHECKING:
    from eagleeye.signals import BaseSignal

type Axis = Literal["left", "right"]
MAX_POINTS = 20_000


@dataclass(frozen=True)
class Trace:
    label: str
    signal: BaseSignal[Any]
    axis: Axis = "left"  # "right" for booleans/flags
    visible: bool = True  # start unchecked if noisy


@dataclass(frozen=True)
class HLine:
    y: float
    label: str


@dataclass(frozen=True)
class PlotSpec:
    title: str
    t0_us: int
    traces: list[Trace]
    hlines: list[HLine] = field(default_factory=list[HLine])
    bool_spans: list[tuple[int, int]] = field(default_factory=list[tuple[int, int]])
    y_label: str = ""
    y2_label: str = ""


def _to_seconds(timestamps: list[int], t0_us: int) -> list[float]:
    return [(t - t0_us) * 1e-6 for t in timestamps]


# def _downsample(xs: list[float], ys: list[float]) -> tuple[list[float], list[float]]:
#     n = len(xs)
#     if n <= MAX_POINTS:
#         return xs, ys

#     bucket = n // (MAX_POINTS // 2)
#     out_x: list[float] = []
#     out_y: list[float] = []

#     for start in range(0, n, bucket):
#         end = min(start + bucket, n)
#         lo = hi = start
#         for i in range(start + 1, end):
#             if ys[i] < ys[lo]:
#                 lo = i
#             elif ys[i] > ys[hi]:
#                 hi = i
#         for i in sorted((lo, hi)):
#             out_x.append(xs[i])
#             out_y.append(ys[i])

#     return out_x, out_y


def _build_trace(trace: Trace, t0_us: int) -> tuple[go.Scatter, bool]:
    xs = _to_seconds(trace.signal.timestamps, t0_us)
    ys = [float(v) for v in trace.signal.values]
    # xs, ys = _downsample(xs, ys)

    secondary = trace.axis == "right"

    scatter = go.Scatter(
        x=xs,
        y=ys,
        name=trace.label,
        mode="lines",
        line_shape="hv",  # zero-order hold — the data is a staircase
        visible=True if trace.visible else "legendonly",
        hovertemplate="%{x:.3f}s — %{y:.4g}<extra>" + trace.label + "</extra>",
    )
    return scatter, secondary


def build_figure(spec: PlotSpec) -> go.Figure:
    fig: Any = make_subplots(specs=[[{"secondary_y": True}]])

    for trace in spec.traces:
        scatter, secondary = _build_trace(trace, spec.t0_us)
        fig.add_trace(scatter, secondary_y=secondary)

    for line in spec.hlines:
        fig.add_hline(
            y=line.y,
            line_dash="dash",
            line_width=1,
            annotation_text=line.label,
        )

    for lo_us, hi_us in spec.bool_spans:
        fig.add_vrect(
            x0=(lo_us - spec.t0_us) * 1e-6,
            x1=(hi_us - spec.t0_us) * 1e-6,
            fillcolor="red",
            opacity=0.12,
            line_width=0,
        )

    fig.update_layout(title=spec.title, hovermode="x unified")
    fig.update_xaxes(title_text="Seconds since match start")
    fig.update_yaxes(title_text=spec.y_label, secondary_y=False)
    fig.update_yaxes(title_text=spec.y2_label, secondary_y=True)

    return fig


def render(spec: PlotSpec, *, include_plotlyjs: bool | str = True) -> str:
    fig = build_figure(spec)
    return fig.to_html(include_plotlyjs=include_plotlyjs, full_html=True)
