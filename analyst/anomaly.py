"""Explainable anomaly detection: flag a value only if BOTH z-score and IQR rules agree."""
import pandas as pd

COLUMNS = ["row", "column", "value", "z_score", "normal_low", "normal_high", "reason"]


def detect_anomalies(
    df: pd.DataFrame, z_threshold: float = 3.0, iqr_k: float = 1.5, top: int = 10
) -> pd.DataFrame:
    rows = []
    for col in df.select_dtypes("number").columns:
        s = df[col].dropna()
        if len(s) < 8 or s.std(ddof=0) == 0:
            continue
        mean, std = s.mean(), s.std(ddof=0)
        q1, q3 = s.quantile(0.25), s.quantile(0.75)
        low, high = q1 - iqr_k * (q3 - q1), q3 + iqr_k * (q3 - q1)
        z = (df[col] - mean) / std
        mask = (z.abs() > z_threshold) & ((df[col] < low) | (df[col] > high))
        for idx in df.index[mask]:
            val = float(df.at[idx, col])
            rows.append(
                {
                    "row": int(idx),
                    "column": col,
                    "value": val,
                    "z_score": round(float(z[idx]), 2),
                    "normal_low": round(float(low), 2),
                    "normal_high": round(float(high), 2),
                    "reason": (
                        f"{col}={val:,.2f} is {z[idx]:+.1f} standard deviations from the mean "
                        f"({mean:,.2f}) and outside the IQR range [{low:,.2f}, {high:,.2f}]"
                    ),
                }
            )
    out = pd.DataFrame(rows, columns=COLUMNS)
    if out.empty:
        return out
    return out.reindex(out["z_score"].abs().sort_values(ascending=False).index).head(top).reset_index(drop=True)
