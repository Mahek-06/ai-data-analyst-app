"""Plain data containers passed between the analyst engine and the UI."""
from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd


@dataclass
class Panel:
    title: str
    sql: str
    chart: dict
    df: pd.DataFrame


@dataclass
class Answer:
    intent: str
    text: str
    insights: list[str] = field(default_factory=list)
    reasoning: str = ""
    sql: str = ""
    pandas_code: str = ""
    chart: dict | None = None
    df: pd.DataFrame | None = None
    panels: list[Panel] = field(default_factory=list)
