"""Plotly chart builder driven by the LLM's chart spec."""
import pandas as pd
import plotly.express as px

SUPPORTED = {"bar", "line", "pie", "scatter", "histogram"}


def build_chart(df: pd.DataFrame, spec: dict | None):
    """Return a Plotly figure, or None when no sensible chart exists."""
    if df is None or df.empty or not spec:
        return None
    kind = spec.get("type", "none")
    if kind not in SUPPORTED:
        return None
    cols = list(df.columns)
    numeric = list(df.select_dtypes("number").columns)
    x = spec.get("x") if spec.get("x") in cols else cols[0]
    y = spec.get("y") if spec.get("y") in cols else (numeric[-1] if numeric else None)
    title = spec.get("title", "")
    try:
        if kind == "histogram":
            return px.histogram(df, x=x, title=title)
        if y is None:
            return None
        if kind == "line":
            return px.line(df, x=x, y=y, markers=True, title=title)
        if kind == "pie":
            return px.pie(df.head(12), names=x, values=y, title=title)
        if kind == "scatter":
            return px.scatter(df, x=x, y=y, title=title)
        return px.bar(df, x=x, y=y, title=title)
    except (ValueError, TypeError):
        return None
