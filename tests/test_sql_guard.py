import pytest

from analyst.errors import UnsafeSQLError
from analyst.sql_guard import validate_select


@pytest.mark.parametrize("sql", [
    "SELECT * FROM sales",
    "WITH a AS (SELECT 1) SELECT * FROM a;",
    "SELECT 'drop; table' AS note",
])
def test_allows_read_only_queries(sql):
    assert validate_select(sql)


@pytest.mark.parametrize("sql", [
    "DROP TABLE sales",
    "SELECT 1; SELECT 2",
    "INSERT INTO sales VALUES (1)",
    "SELECT * FROM read_csv('/etc/passwd')",
    "-- harmless\nDELETE FROM sales",
    "",
])
def test_blocks_unsafe_queries(sql):
    with pytest.raises(UnsafeSQLError):
        validate_select(sql)
