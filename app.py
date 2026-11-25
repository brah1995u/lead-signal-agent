"""Streamlit UI: describe your customer, run the agent, review and export scored leads.
Run with: uv run --extra ui streamlit run app.py"""

from __future__ import annotations

import os

import pandas as pd
import streamlit as st

from lead_agent.export import COLUMNS, rows
from lead_agent.llm import LLMError, select_llm
from lead_agent.models import ICP
from lead_agent.pipeline import run
from lead_agent.sources import FirecrawlSource, HackerNewsSource
from lead_agent.store import Store

st.set_page_config(page_title="Lead Signal Agent", page_icon="🎯", layout="wide")
st.title("🎯 Lead Signal Agent")
st.caption(
    "Finds public conversations where people look for a product like yours and scores them against your ideal "
    "customer profile. Fork of AI-Lead-Generation-Agent by Gurpreet Kaur (MIT)."
)

with st.sidebar:
    st.header("Model")
    provider = st.selectbox(
        "Provider",
        ["auto", "anthropic", "openai-compatible"],
        help="Auto: Claude if ANTHROPIC_API_KEY is set, else Ollama",
    )
    st.header("Sources")
    use_hn = st.checkbox("Hacker News (no key)", value=True)
    use_web = st.checkbox("Web search via Firecrawl", value=bool(os.getenv("FIRECRAWL_API_KEY")))
    sites = st.text_input("Sites for web search", "reddit.com, quora.com, indiehackers.com")
    per_query = st.slider("Results per query", 5, 50, 20)

with st.form("icp"):
    product = st.text_area(
        "What do you sell?",
        "An AI support agent that answers customers from your help center and hands over to humans.",
    )
    customers = st.text_input(
        "Who buys it?", "SaaS and e-commerce companies with 5-200 employees and a support team"
    )
    signals = st.text_input(
        "Buying signals (comma separated)",
        "drowning in support tickets, looking for helpdesk, Zendesk too expensive",
    )
    exclude = st.text_input("Not a fit (comma separated)", "people selling their own chatbot, job seekers")
    col1, col2 = st.columns(2)
    min_score = col1.slider("Lead threshold (fit score)", 0, 100, 60)
    days = col2.slider("Look back (days)", 1, 90, 30)
    submitted = st.form_submit_button("Find leads", type="primary")

store = Store(".data/leads.db")

if submitted:
    icp = ICP(
        product=product,
        customers=customers,
        buying_signals=[s.strip() for s in signals.split(",") if s.strip()],
        exclude=[s.strip() for s in exclude.split(",") if s.strip()],
        min_score=min_score,
        days=days,
    )
    sources = []
    if use_hn:
        sources.append(HackerNewsSource())
    if use_web:
        key = os.getenv("FIRECRAWL_API_KEY")
        if key:
            sources.append(FirecrawlSource(key, sites=[s.strip() for s in sites.split(",") if s.strip()]))
        else:
            st.warning("Set FIRECRAWL_API_KEY to use web search.")
    try:
        llm = select_llm(None if provider == "auto" else provider)
        with st.status(f"Running with {llm.model}…", expanded=True) as status:
            report = run(icp, sources, llm, store, per_query=per_query, progress=st.write)
            status.update(label=f"Done: {report.new} new signals, {report.judged} scored", state="complete")
        for error in report.errors:
            st.warning(error)
    except LLMError as error:
        st.error(f"Model error: {error}")

leads = store.leads(min_score=0, limit=500)
counts = store.counts()
c1, c2, c3 = st.columns(3)
c1.metric("Signals collected", counts["signals"])
c2.metric("Scored", counts["qualified"])
c3.metric("Leads ≥ 60", sum(1 for lead in leads if lead.score >= 60))

if leads:
    df = pd.DataFrame(rows(leads), columns=COLUMNS)
    df["score"] = df["score"].astype(int)
    threshold = st.slider("Show leads with score ≥", 0, 100, 60, key="filter")
    view = df[df["score"] >= threshold]
    st.dataframe(
        view,
        hide_index=True,
        use_container_width=True,
        column_config={
            "score": st.column_config.ProgressColumn("Score", min_value=0, max_value=100, format="%d"),
            "url": st.column_config.LinkColumn("Link"),
        },
    )
    st.download_button("Download CSV", view.to_csv(index=False), "leads.csv", "text/csv")
else:
    st.info("No leads yet. Describe your customer and press **Find leads**.")
