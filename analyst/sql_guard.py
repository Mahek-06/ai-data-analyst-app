"""Read-only SQL guard: LLM-generated SQL is untrusted input."""
import re

from .errors import UnsafeSQLError

_FORBIDDEN = re.compile(
    r"\b(insert|update|delete|drop|alter|create|attach|detach|copy|pragma|install|"
    r"load|export|call|truncate|glob|read_\w+|write_\w+)\b",
    re.IGNORECASE,
)


def _strip_noise(sql: str) -> str:
    """Remove comments and string literals so keywords inside them are ignored."""
    sql = re.sub(r"/\*.*?\*/", " ", sql, flags=re.S)
    sql = re.sub(r"--[^\n]*", " ", sql)
    return re.sub(r"'(?:[^']|'')*'", "''", sql)


def validate_select(sql: str) -> str:
    """Return the cleaned SQL or raise UnsafeSQLError if it is not a single SELECT."""
    if not sql or not sql.strip():
        raise UnsafeSQLError("Empty SQL statement.")
    scan = _strip_noise(sql).strip().rstrip(";").strip()
    if ";" in scan:
        raise UnsafeSQLError("Multiple SQL statements are not allowed.")
    if not re.match(r"(select|with)\b", scan, re.IGNORECASE):
        raise UnsafeSQLError("Only SELECT queries are allowed.")
    if _FORBIDDEN.search(scan):
        raise UnsafeSQLError("Query contains a forbidden keyword or function.")
    return sql.strip().rstrip(";").strip()
