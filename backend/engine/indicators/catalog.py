from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Literal


@dataclass(frozen=True)
class ParamSpec:
    """Metadata and validation constraints for an indicator parameter."""

    name: str
    label: str
    param_type: Literal["int", "float", "select"]
    default: int | float | str
    min_val: float | None = None
    max_val: float | None = None
    options: tuple[str, ...] | None = None


@dataclass(frozen=True)
class OutputSeriesSpec:
    """Metadata for a computed indicator output series."""

    key: str
    label: str
    color: str
    series_type: Literal["line", "histogram"] = "line"


@dataclass(frozen=True)
class IndicatorSpec:
    """Catalog definition for a built-in indicator."""

    id: str
    name: str
    category: Literal["trend", "momentum", "volatility", "volume"]
    pane: Literal["overlay", "oscillator"]
    description: str
    parameters: tuple[ParamSpec, ...]
    outputs: tuple[OutputSeriesSpec, ...]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


_PRICE_SOURCES = ("close", "open", "high", "low", "hl2", "hlc3", "ohlc4")

INDICATOR_SPECS: dict[str, IndicatorSpec] = {
    "sma": IndicatorSpec(
        id="sma",
        name="Simple Moving Average (SMA)",
        category="trend",
        pane="overlay",
        description="Arithmetic rolling average over the selected price source.",
        parameters=(
            ParamSpec("length", "Length", "int", 20, min_val=1, max_val=500),
            ParamSpec("source", "Source", "select", "close", options=_PRICE_SOURCES),
            ParamSpec("offset", "Offset", "int", 0, min_val=0, max_val=50),
        ),
        outputs=(OutputSeriesSpec("sma", "SMA", "#38BDF8"),),
    ),
    "ema": IndicatorSpec(
        id="ema",
        name="Exponential Moving Average (EMA)",
        category="trend",
        pane="overlay",
        description="Exponentially weighted moving average giving higher weight to recent bars.",
        parameters=(
            ParamSpec("length", "Length", "int", 20, min_val=1, max_val=500),
            ParamSpec("source", "Source", "select", "close", options=_PRICE_SOURCES),
            ParamSpec("offset", "Offset", "int", 0, min_val=0, max_val=50),
        ),
        outputs=(OutputSeriesSpec("ema", "EMA", "#F59E0B"),),
    ),
    "bb": IndicatorSpec(
        id="bb",
        name="Bollinger Bands (BB)",
        category="volatility",
        pane="overlay",
        description="SMA basis with upper and lower population standard deviation bands.",
        parameters=(
            ParamSpec("length", "Length", "int", 20, min_val=2, max_val=200),
            ParamSpec("mult", "StdDev Mult", "float", 2.0, min_val=0.1, max_val=10.0),
            ParamSpec("source", "Source", "select", "close", options=_PRICE_SOURCES),
        ),
        outputs=(
            OutputSeriesSpec("upper", "Upper Band", "#818CF8"),
            OutputSeriesSpec("basis", "Basis", "#94A3B8"),
            OutputSeriesSpec("lower", "Lower Band", "#818CF8"),
        ),
    ),
    "vwap": IndicatorSpec(
        id="vwap",
        name="Volume Weighted Average Price (VWAP)",
        category="volume",
        pane="overlay",
        description="Cumulative volume-weighted average price anchored to UTC session, week, or month.",
        parameters=(
            ParamSpec("anchor", "Anchor", "select", "session", options=("session", "week", "month")),
            ParamSpec("source", "Source", "select", "hlc3", options=_PRICE_SOURCES),
        ),
        outputs=(OutputSeriesSpec("vwap", "VWAP", "#EC4899"),),
    ),
    "supertrend": IndicatorSpec(
        id="supertrend",
        name="Supertrend",
        category="trend",
        pane="overlay",
        description="ATR-based dynamic trailing trend line.",
        parameters=(
            ParamSpec("atr_length", "ATR Length", "int", 10, min_val=1, max_val=200),
            ParamSpec("factor", "Factor", "float", 3.0, min_val=0.5, max_val=20.0),
        ),
        outputs=(OutputSeriesSpec("supertrend", "Supertrend", "#19C995"),),
    ),
    "ichimoku": IndicatorSpec(
        id="ichimoku",
        name="Ichimoku Cloud",
        category="trend",
        pane="overlay",
        description="Tenkan-sen, Kijun-sen, Senkou Span A, and Senkou Span B (strictly causal).",
        parameters=(
            ParamSpec("conversion_periods", "Conversion Periods", "int", 9, min_val=1, max_val=200),
            ParamSpec("base_periods", "Base Periods", "int", 26, min_val=1, max_val=200),
            ParamSpec("lagging_span2_periods", "Span B Periods", "int", 52, min_val=1, max_val=400),
            ParamSpec("displacement", "Displacement", "int", 26, min_val=1, max_val=200),
        ),
        outputs=(
            OutputSeriesSpec("tenkan", "Conversion (Tenkan)", "#38BDF8"),
            OutputSeriesSpec("kijun", "Base (Kijun)", "#F43F5E"),
            OutputSeriesSpec("senkou_a", "Leading Span A", "#19C995"),
            OutputSeriesSpec("senkou_b", "Leading Span B", "#F59E0B"),
        ),
    ),
    "rsi": IndicatorSpec(
        id="rsi",
        name="Relative Strength Index (RSI)",
        category="momentum",
        pane="oscillator",
        description="Wilder-smoothed momentum oscillator bounded between 0 and 100.",
        parameters=(
            ParamSpec("length", "Length", "int", 14, min_val=2, max_val=200),
            ParamSpec("source", "Source", "select", "close", options=_PRICE_SOURCES),
            ParamSpec("overbought", "Overbought", "int", 70, min_val=50, max_val=99),
            ParamSpec("oversold", "Oversold", "int", 30, min_val=1, max_val=50),
        ),
        outputs=(OutputSeriesSpec("rsi", "RSI", "#A78BFA"),),
    ),
    "macd": IndicatorSpec(
        id="macd",
        name="MACD",
        category="momentum",
        pane="oscillator",
        description="Moving Average Convergence Divergence with signal line and histogram.",
        parameters=(
            ParamSpec("fast_length", "Fast Length", "int", 12, min_val=2, max_val=200),
            ParamSpec("slow_length", "Slow Length", "int", 26, min_val=2, max_val=400),
            ParamSpec("signal_length", "Signal Length", "int", 9, min_val=2, max_val=200),
            ParamSpec("source", "Source", "select", "close", options=_PRICE_SOURCES),
        ),
        outputs=(
            OutputSeriesSpec("macd", "MACD", "#38BDF8"),
            OutputSeriesSpec("signal", "Signal", "#F59E0B"),
            OutputSeriesSpec("histogram", "Histogram", "#19C995", series_type="histogram"),
        ),
    ),
    "atr": IndicatorSpec(
        id="atr",
        name="Average True Range (ATR)",
        category="volatility",
        pane="oscillator",
        description="Wilder-smoothed average true range volatility measure.",
        parameters=(
            ParamSpec("length", "Length", "int", 14, min_val=1, max_val=200),
        ),
        outputs=(OutputSeriesSpec("atr", "ATR", "#F97316"),),
    ),
    "adx": IndicatorSpec(
        id="adx",
        name="Average Directional Index (ADX)",
        category="trend",
        pane="oscillator",
        description="Trend strength indicator with +DI and -DI directional lines.",
        parameters=(
            ParamSpec("di_length", "DI Length", "int", 14, min_val=2, max_val=200),
            ParamSpec("adx_smoothing", "ADX Smoothing", "int", 14, min_val=2, max_val=200),
        ),
        outputs=(
            OutputSeriesSpec("adx", "ADX", "#E2E8F0"),
            OutputSeriesSpec("plus_di", "+DI", "#19C995"),
            OutputSeriesSpec("minus_di", "-DI", "#F05B70"),
        ),
    ),
    "stoch": IndicatorSpec(
        id="stoch",
        name="Stochastic Oscillator",
        category="momentum",
        pane="oscillator",
        description="Smoothed %K and %D stochastic momentum oscillator.",
        parameters=(
            ParamSpec("k_length", "%K Length", "int", 14, min_val=1, max_val=200),
            ParamSpec("k_smoothing", "%K Smoothing", "int", 3, min_val=1, max_val=100),
            ParamSpec("d_length", "%D Smoothing", "int", 3, min_val=1, max_val=100),
        ),
        outputs=(
            OutputSeriesSpec("k", "%K", "#38BDF8"),
            OutputSeriesSpec("d", "%D", "#F59E0B"),
        ),
    ),
}


def get_indicator_spec(indicator_id: str) -> IndicatorSpec:
    """Return catalog specification or raise ValueError if unknown."""
    spec = INDICATOR_SPECS.get(indicator_id)
    if spec is None:
        raise ValueError(f"Unknown indicator '{indicator_id}'")
    return spec


def validate_and_coerce_params(indicator_id: str, raw_params: dict[str, Any] | None) -> dict[str, Any]:
    """Validate and coerce raw indicator parameters against the catalog schema."""
    spec = get_indicator_spec(indicator_id)
    raw = raw_params or {}
    coerced: dict[str, Any] = {}

    for p in spec.parameters:
        val = raw.get(p.name, p.default)
        if p.param_type == "int":
            try:
                num = int(val)
            except (TypeError, ValueError) as exc:
                raise ValueError(f"Parameter '{p.name}' must be an integer") from exc
            if p.min_val is not None and num < int(p.min_val):
                raise ValueError(f"Parameter '{p.name}' must be >= {int(p.min_val)}")
            if p.max_val is not None and num > int(p.max_val):
                raise ValueError(f"Parameter '{p.name}' must be <= {int(p.max_val)}")
            coerced[p.name] = num
        elif p.param_type == "float":
            try:
                fnum = float(val)
            except (TypeError, ValueError) as exc:
                raise ValueError(f"Parameter '{p.name}' must be a number") from exc
            if p.min_val is not None and fnum < float(p.min_val):
                raise ValueError(f"Parameter '{p.name}' must be >= {p.min_val}")
            if p.max_val is not None and fnum > float(p.max_val):
                raise ValueError(f"Parameter '{p.name}' must be <= {p.max_val}")
            coerced[p.name] = round(fnum, 6)
        elif p.param_type == "select":
            sval = str(val)
            if p.options and sval not in p.options:
                raise ValueError(f"Parameter '{p.name}' must be one of {p.options}")
            coerced[p.name] = sval

    return coerced
