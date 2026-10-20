import numpy as np
import pandas as pd

from analyst.anomaly import detect_anomalies


def test_detects_planted_outlier_with_explanation():
    df = pd.DataFrame({"revenue": np.random.default_rng(1).normal(100, 10, 200)})
    df.loc[5, "revenue"] = 900
    out = detect_anomalies(df)
    assert out.iloc[0]["row"] == 5 and "standard deviations" in out.iloc[0]["reason"]


def test_no_anomalies_in_uniform_data():
    assert detect_anomalies(pd.DataFrame({"a": range(50)})).empty


def test_small_or_constant_columns_are_skipped():
    assert detect_anomalies(pd.DataFrame({"a": [1, 2, 3], "b": [5] * 3})).empty
