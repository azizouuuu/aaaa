"""Core dataclasses shared across pipelines, signals and API layers."""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class TradeRecord:
    source: str  # "comtrade" | "sample" | later: "comexstat" | "comext" | ...
    reporter: str  # ISO3
    partner: str  # ISO3 or "WLD"
    flow: str  # "X" | "M"
    code: str  # HS code as reported ("1518", "382319", ...)
    code_system: str  # "HS6" | "CN8" | "NCM8" | "HTS10"
    year: int
    value_usd: float
    net_wgt_kg: float | None
    estimated: bool = False

    @property
    def unit_value(self) -> float | None:
        """USD per tonne; None when weight is missing or zero."""
        if not self.net_wgt_kg:
            return None
        return self.value_usd / (self.net_wgt_kg / 1000.0)


@dataclass(frozen=True)
class FlowQuery:
    codes: tuple[str, ...]
    flow: str  # "X" | "M"
    years: tuple[int, ...]
    reporters: tuple[str, ...] | None = None  # None = all reporters
    partners: tuple[str, ...] | None = None  # None = all partners; ("WLD",) = world


@dataclass
class SignalResult:
    reporter: str
    partner: str
    code: str
    year: int
    flow: str
    candidates: list[tuple[str, float]] = field(default_factory=list)  # (feedstock, prob)
    explanations: list[str] = field(default_factory=list)
    confidence: str = "low"  # low | medium | high
    basis: str = "heuristic"  # heuristic | national_tariff_line
    unit_value: float | None = None
