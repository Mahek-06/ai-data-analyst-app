import io

import pytest

from analyst.config import Settings
from analyst.data_store import DataStore
from analyst.engine import Analyst
from analyst.errors import AnalystError, UnsafeSQLError


class FakeLLM:
    """Returns queued JSON replies so the engine is tested without network access."""

    def __init__(self, *replies):
        self.replies, self.prompts = list(replies), []

    def complete_json(self, system, user):
        self.prompts.append(user)
        return self.replies.pop(0)


NARRATION = {"answer": "West leads.", "insights": ["a"], "reasoning": "grouped by region"}


@pytest.fixture
def store():
    s = DataStore()
    s.add_csv(io.StringIO("region,revenue\nWest,10\nEast,5\nWest,7\n"), "sales.csv")
    return s


def analyst(store, *replies):
    llm = FakeLLM(*replies)
    return Analyst(store, llm, Settings()), llm


def test_query_flow(store):
    sql = "SELECT region, SUM(revenue) AS total FROM sales GROUP BY region ORDER BY total DESC"
    a, _ = analyst(store, {"intent": "query", "sql": sql, "chart": {"type": "bar"}}, NARRATION)
    ans = a.ask("Which region has the highest revenue?")
    assert ans.df.iloc[0]["region"] == "West" and ans.text == "West leads."


def test_failing_sql_is_repaired_once(store):
    a, _ = analyst(store, {"intent": "query", "sql": "SELECT bad FROM sales"},
                   {"sql": "SELECT COUNT(*) AS n FROM sales"}, NARRATION)
    assert a.ask("count rows").df.iloc[0]["n"] == 3


def test_unsafe_sql_is_refused(store):
    bad = {"intent": "query", "sql": "DROP TABLE sales"}
    a, _ = analyst(store, bad, {"sql": "DROP TABLE sales"})
    with pytest.raises(UnsafeSQLError):
        a.ask("delete everything")


def test_history_is_sent_for_follow_ups(store):
    q = {"intent": "query", "sql": "SELECT COUNT(*) AS n FROM sales"}
    a, llm = analyst(store, q, NARRATION, q, NARRATION)
    a.ask("how many rows?")
    a.ask("and now?")
    assert "how many rows?" in llm.prompts[2]


def test_dashboard_skips_broken_panels(store):
    panels = [{"title": "Total", "sql": "SELECT SUM(revenue) AS t FROM sales", "chart": {"type": "kpi"}},
              {"title": "Broken", "sql": "SELECT x FROM nowhere", "chart": {"type": "bar"}}]
    a, _ = analyst(store, {"intent": "dashboard", "panels": panels}, {"sql": "SELECT x FROM nowhere"}, NARRATION)
    assert [p.title for p in a.ask("dashboard").panels] == ["Total"]


def test_requires_data():
    a, _ = analyst(DataStore())
    with pytest.raises(AnalystError):
        a.ask("hello")
