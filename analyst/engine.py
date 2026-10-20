"""Orchestrates: plan (LLM) -> validate + execute (DuckDB / pandas) -> narrate (LLM)."""
from __future__ import annotations

import json
import logging

import pandas as pd

from .anomaly import detect_anomalies
from .config import Settings
from .data_store import DataStore
from .errors import AnalystError, LLMError, QueryExecutionError, UnsafeSQLError
from .llm import LLMClient
from .models import Answer, Panel
from .prompts import NARRATE_SYSTEM, PLAN_SYSTEM, REPAIR_SYSTEM
from .sql_guard import validate_select

log = logging.getLogger(__name__)


class Analyst:
    """One instance per user session; keeps conversation history for follow-up questions."""

    def __init__(self, store: DataStore, llm: LLMClient, settings: Settings) -> None:
        self.store, self.llm, self.settings = store, llm, settings
        self.history: list[dict] = []

    # ---- public API --------------------------------------------------------
    def ask(self, question: str) -> Answer:
        if not self.store.tables:
            raise AnalystError("Upload at least one CSV file first.")
        plan = self.llm.complete_json(PLAN_SYSTEM, self._plan_prompt(question))
        intent = plan.get("intent", "query")

        if intent == "dashboard":
            answer = self._dashboard(question, plan)
        elif intent == "anomaly":
            answer = self._anomaly(plan)
        elif intent == "summary":
            answer = self._summary(plan)
        else:
            answer = self._query(question, plan)

        self._narrate(question, answer)
        self.history.append({"q": question, "intent": intent, "sql": answer.sql, "a": answer.text})
        return answer

    def reset(self) -> None:
        self.history.clear()

    # ---- intents -----------------------------------------------------------
    def _query(self, question: str, plan: dict) -> Answer:
        df, sql = self._run_sql(question, plan.get("sql") or "")
        return Answer("query", "", sql=sql, pandas_code=plan.get("pandas") or "",
                      chart=plan.get("chart"), df=df)

    def _dashboard(self, question: str, plan: dict) -> Answer:
        panels = []
        for p in (plan.get("panels") or [])[:6]:
            try:
                df, sql = self._run_sql(question, p.get("sql", ""))
                panels.append(Panel(p.get("title", "Panel"), sql, p.get("chart") or {}, df))
            except AnalystError as exc:  # one bad panel must not break the dashboard
                log.warning("Dashboard panel %r skipped: %s", p.get("title"), exc)
        if not panels:
            raise AnalystError("Could not build any dashboard panels. Try a more specific request.")
        sql = "\n\n".join(f"-- {p.title}\n{p.sql};" for p in panels)
        return Answer("dashboard", "", sql=sql, panels=panels)

    def _anomaly(self, plan: dict) -> Answer:
        name = plan.get("table") if plan.get("table") in self.store.tables else next(iter(self.store.tables))
        found = detect_anomalies(self.store.tables[name])
        return Answer("anomaly", "", df=found,
                      pandas_code=f"# z-score > 3 AND outside 1.5*IQR, table: {name}\n"
                                  "from analyst.anomaly import detect_anomalies\ndetect_anomalies(df)")

    def _summary(self, plan: dict) -> Answer:
        name = plan.get("table") if plan.get("table") in self.store.tables else next(iter(self.store.tables))
        desc = self.store.tables[name].describe(include="all").T.reset_index().astype(str)
        return Answer("summary", "", df=desc, pandas_code=f'df = tables["{name}"]\ndf.describe(include="all")')

    # ---- SQL execution with self-repair -----------------------------------
    def _run_sql(self, question: str, sql: str) -> tuple[pd.DataFrame, str]:
        for attempt in range(self.settings.max_sql_retries + 1):
            try:
                clean = validate_select(sql)
                return self.store.query(clean, self.settings.max_result_rows), clean
            except (QueryExecutionError, UnsafeSQLError) as exc:
                if attempt == self.settings.max_sql_retries:
                    raise
                log.info("Repairing SQL after error: %s", exc)
                sql = self.llm.complete_json(
                    REPAIR_SYSTEM,
                    f"{self.store.schema_text()}\nQuestion: {question}\nFailing SQL:\n{sql}\nError: {exc}",
                ).get("sql", "")
        raise QueryExecutionError("unreachable")  # pragma: no cover

    # ---- prompts / narration ----------------------------------------------
    def _plan_prompt(self, question: str) -> str:
        hist = "\n".join(
            f"Q: {h['q']}\nSQL: {h['sql']}\nA: {h['a']}" for h in self.history[-self.settings.history_turns:]
        )
        return f"{self.store.schema_text()}\n\nConversation so far:\n{hist or '(none)'}\n\nUser message: {question}"

    def _narrate(self, question: str, ans: Answer) -> None:
        n = self.settings.preview_rows
        if ans.panels:
            data = [{"title": p.title, "rows": p.df.head(12).to_dict("records")} for p in ans.panels]
        else:
            data = ans.df.head(n).to_dict("records") if ans.df is not None else []
        payload = json.dumps({"question": question, "intent": ans.intent, "sql": ans.sql, "result": data},
                             default=str)
        try:
            out = self.llm.complete_json(NARRATE_SYSTEM, payload)
            ans.text = out.get("answer", "")
            ans.insights = list(out.get("insights", []))[:3]
            ans.reasoning = out.get("reasoning", "")
        except LLMError as exc:  # results are still valid even if narration fails
            log.warning("Narration failed: %s", exc)
            ans.text = "Here are the results (the written explanation is temporarily unavailable)."
