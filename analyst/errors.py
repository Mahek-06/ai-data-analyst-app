"""Domain-specific exceptions so the UI can show precise, friendly messages."""


class AnalystError(Exception):
    """Base class for all expected, user-facing errors."""


class DataValidationError(AnalystError):
    """The uploaded file is not a usable CSV."""


class UnsafeSQLError(AnalystError):
    """Generated SQL was rejected by the read-only guard."""


class QueryExecutionError(AnalystError):
    """DuckDB failed to execute a (valid, read-only) query."""


class LLMError(AnalystError):
    """The language model is unavailable or returned unusable output."""
