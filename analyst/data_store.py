"""CSV loading, validation and querying (DuckDB in-memory)."""
from __future__ import annotations

import re
import warnings
from typing import IO

import duckdb
import pandas as pd

from .errors import DataValidationError, QueryExecutionError

_DATE_HINT = re.compile(r"^\d{4}-\d{1,2}-\d{1,2}|^\d{1,2}[/-]\d{1,2}[/-]\d{2,4}")


def _snake(name: str) -> str:
    return re.sub(r"\W+", "_", str(name).strip()).strip("_").lower() or "col"


class DataStore:
    """Holds every uploaded table; DuckDB gives real SQL (incl. joins) across files."""

    def __init__(self) -> None:
        self.con = duckdb.connect(":memory:")
        self.tables: dict[str, pd.DataFrame] = {}

    # ---- loading -----------------------------------------------------------
    @staticmethod
    def table_name(filename: str) -> str:
        name = _snake(re.sub(r"\.csv$", "", filename, flags=re.IGNORECASE))
        return f"t_{name}" if name[0].isdigit() else name

    def add_csv(self, source: str | IO, filename: str) -> str:
        """Validate and register a CSV; returns the table name."""
        try:
            df = pd.read_csv(source)
        except pd.errors.EmptyDataError as exc:
            raise DataValidationError(f"{filename}: the file is empty.") from exc
        except (pd.errors.ParserError, UnicodeDecodeError) as exc:
            raise DataValidationError(f"{filename}: not a valid CSV ({exc}).") from exc
        if df.empty:
            raise DataValidationError(f"{filename}: no data rows found.")

        cols = [_snake(c) for c in df.columns]
        if len(set(cols)) != len(cols):
            raise DataValidationError(f"{filename}: duplicate column names after cleaning.")
        df.columns = cols

        for col in df.select_dtypes(include="object"):
            sample = df[col].dropna().astype(str)
            if len(sample) and sample.str.match(_DATE_HINT).mean() > 0.8:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    parsed = pd.to_datetime(df[col], errors="coerce")
                if parsed.notna().mean() > 0.8:
                    df[col] = parsed

        name = self.table_name(filename)
        self.con.register(name, df)
        self.tables[name] = df
        return name

    def remove(self, name: str) -> None:
        if name in self.tables:
            self.con.unregister(name)
            del self.tables[name]

    # ---- introspection -----------------------------------------------------
    def schema_text(self, sample_rows: int = 3) -> str:
        """Compact schema + sample rows for the LLM prompt (no full data leaves the app)."""
        parts = []
        for name, df in self.tables.items():
            cols = ", ".join(f"{c} ({t})" for c, t in df.dtypes.astype(str).items())
            sample = df.head(sample_rows).to_csv(index=False)
            parts.append(f"TABLE {name} ({len(df)} rows)\nColumns: {cols}\nSample:\n{sample}")
        return "\n".join(parts)

    # ---- querying ----------------------------------------------------------
    def query(self, sql: str, max_rows: int = 5000) -> pd.DataFrame:
        try:
            return self.con.execute(sql).fetch_df().head(max_rows)
        except duckdb.Error as exc:
            raise QueryExecutionError(str(exc)) from exc
