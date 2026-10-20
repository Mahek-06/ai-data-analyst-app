"""Streamlit UI for the AI Data Analyst."""
from pathlib import Path

import streamlit as st

from analyst.charts import build_chart
from analyst.config import get_settings
from analyst.data_store import DataStore
from analyst.engine import Analyst
from analyst.errors import AnalystError
from analyst.llm import make_llm
from analyst.models import Answer

SAMPLE_DIR = Path(__file__).parent / "sample_data"
EXAMPLES = [
    "Which region generated the highest revenue?",
    "Show monthly sales trends.",
    "Which products are underperforming?",
    "What are the top five customers?",
    "Which customer segment generated the most revenue?",
    "Detect anomalies in the dataset.",
    "Build a dashboard of this data.",
]

st.set_page_config(page_title="AI Data Analyst", page_icon="📊", layout="wide")


def _session() -> None:
    if "store" not in st.session_state:
        st.session_state.store = DataStore()
        st.session_state.loaded = set()
        st.session_state.messages = []
        st.session_state.analyst = None


def _analyst() -> Analyst | None:
    if st.session_state.analyst is None:
        try:
            prov, model, key = st.session_state.cfg_id
            cfg = get_settings(api_key=key, provider=prov, model=model)
            st.session_state.analyst = Analyst(st.session_state.store, make_llm(cfg), cfg)
        except AnalystError as exc:
            st.error(str(exc))
            return None
    return st.session_state.analyst


def _sidebar() -> None:
    st.sidebar.title("📊 AI Data Analyst")
    prov = st.sidebar.selectbox("AI provider", ["gemini", "anthropic"],
                                format_func=lambda p: "Google Gemini" if p == "gemini" else "Anthropic Claude")
    d = get_settings(provider=prov)
    model = st.sidebar.text_input("Model", value=d.gemini_model if prov == "gemini" else d.model,
                                  key=f"model_{prov}")
    key = st.sidebar.text_input(f"{prov.capitalize()} API key", type="password", key=f"key_{prov}",
                                help="Optional if the key is set in a .env file next to app.py")
    if (prov, model, key) != st.session_state.get("cfg_id"):
        st.session_state.cfg_id = (prov, model, key)
        st.session_state.analyst = None
    files = st.sidebar.file_uploader("Upload CSV file(s)", type="csv", accept_multiple_files=True)
    for f in files or []:
        key = (f.name, f.size)
        if key in st.session_state.loaded:
            continue
        try:
            st.session_state.store.add_csv(f, f.name)
            st.session_state.loaded.add(key)
        except AnalystError as exc:
            st.sidebar.error(str(exc))
    if st.sidebar.button("Load sample datasets"):
        for p in sorted(SAMPLE_DIR.glob("*.csv")):
            st.session_state.store.add_csv(str(p), p.name)
    for name, df in st.session_state.store.tables.items():
        with st.sidebar.expander(f"{name} · {len(df)} rows"):
            st.write(", ".join(f"`{c}`" for c in df.columns))
    if st.sidebar.button("Clear conversation"):
        st.session_state.messages = []
        if st.session_state.analyst:
            st.session_state.analyst.reset()
    st.sidebar.markdown("**Try asking**")
    for q in EXAMPLES:
        if st.sidebar.button(q, key=q):
            st.session_state.pending = q


def _render(ans: Answer) -> None:
    st.write(ans.text)
    for tip in ans.insights:
        st.markdown(f"- {tip}")
    if ans.panels:
        kpis = [p for p in ans.panels if p.chart.get("type") == "kpi" and not p.df.empty]
        for col, p in zip(st.columns(max(len(kpis), 1)), kpis):
            col.metric(p.title, f"{p.df.iloc[0, -1]:,.2f}")
        charts = [p for p in ans.panels if p not in kpis]
        for i in range(0, len(charts), 2):
            for col, p in zip(st.columns(2), charts[i : i + 2]):
                fig = build_chart(p.df, {**p.chart, "title": p.title})
                col.plotly_chart(fig, use_container_width=True) if fig else col.dataframe(p.df)
    else:
        fig = build_chart(ans.df, ans.chart)
        if fig:
            st.plotly_chart(fig, use_container_width=True)
        if ans.df is not None:
            st.dataframe(ans.df, use_container_width=True, hide_index=True)
    with st.expander("Reasoning"):
        st.write(ans.reasoning or "n/a")
    if ans.sql:
        with st.expander("SQL"):
            st.code(ans.sql, language="sql")
    if ans.pandas_code:
        with st.expander("Pandas (equivalent, for reference)"):
            st.code(ans.pandas_code, language="python")


def main() -> None:
    _session()
    _sidebar()
    st.title("Ask your data anything")
    for role, content in st.session_state.messages:
        with st.chat_message(role):
            _render(content) if isinstance(content, Answer) else st.write(content)

    question = st.chat_input("e.g. Which region generated the highest revenue?")
    question = st.session_state.pop("pending", None) or question
    if not question:
        return
    st.session_state.messages.append(("user", question))
    with st.chat_message("user"):
        st.write(question)
    analyst = _analyst()
    with st.chat_message("assistant"):
        if analyst is None:
            return
        try:
            with st.spinner("Analysing…"):
                ans = analyst.ask(question)
            st.session_state.messages.append(("assistant", ans))
            _render(ans)
        except AnalystError as exc:
            st.error(str(exc))
            st.session_state.messages.append(("assistant", f"⚠️ {exc}"))


main()
