import io

import pytest

from analyst.data_store import DataStore
from analyst.errors import DataValidationError, QueryExecutionError


def csv(text):
    return io.StringIO(text)


def test_normalises_names_and_parses_dates():
    s = DataStore()
    name = s.add_csv(csv("Order Date,Total $\n2025-01-01,5\n2025-01-02,6\n"), "My Sales.csv")
    assert name == "my_sales"
    assert list(s.tables[name].columns) == ["order_date", "total"]
    assert str(s.tables[name]["order_date"].dtype).startswith("datetime")


@pytest.mark.parametrize("text", ["", "a,b\n"])
def test_rejects_empty_files(text):
    with pytest.raises(DataValidationError):
        DataStore().add_csv(csv(text), "x.csv")


def test_rejects_duplicate_columns():
    with pytest.raises(DataValidationError):
        DataStore().add_csv(csv("A b,a_b\n1,2\n"), "x.csv")


def test_sql_join_across_files():
    s = DataStore()
    s.add_csv(csv("id,amount\n1,10\n2,20\n"), "orders.csv")
    s.add_csv(csv("id,seg\n1,A\n2,B\n"), "customers.csv")
    df = s.query("SELECT seg, SUM(amount) AS total FROM orders JOIN customers USING (id) GROUP BY seg ORDER BY seg")
    assert df["total"].tolist() == [10, 20]


def test_bad_sql_raises_domain_error():
    s = DataStore()
    s.add_csv(csv("a\n1\n"), "t.csv")
    with pytest.raises(QueryExecutionError):
        s.query("SELECT nope FROM t")
