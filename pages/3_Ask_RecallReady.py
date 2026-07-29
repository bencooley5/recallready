"""Streamlit experience for the bounded Ask RecallReady analyst."""

from __future__ import annotations

from time import monotonic

import streamlit as st

from recallready.chat.agent import RecallReadyAgent
from recallready.chat.schemas import FinalAnswer
from recallready.chat.tools import ToolDispatcher
from recallready.config import get_settings
from recallready.ui.chat import ChatTurn, answer_has_valid_evidence, append_turn, can_submit
from recallready.ui.components import (
    chrome,
    metadata,
    missing_data,
    official_source_url,
    repository,
)
from recallready.ui.formatting import freshness_label

SUGGESTIONS = [
    "What were the most common hazard categories among Class I records since 2021?",
    "Compare undeclared-allergen records in bakery and dairy products.",
    "How did Listeria-related records change between 2019–2022 and 2023–2026?",
    "Explain the difference between a recall event and a product record.",
    "Create evidence for a seafood recall tabletop exercise.",
]


def _turns() -> list[ChatTurn]:
    """Retrieve the session-only bounded transcript."""
    return st.session_state.setdefault("recallready_chat_turns", [])


def _evidence(repo: object, references: list[str]) -> list[dict[str, object]]:
    """Resolve cited IDs through trusted detail methods, never user SQL."""
    rows: list[dict[str, object]] = []
    for reference in references:
        detail = repo.recall_detail(reference)
        if detail is None:
            candidates = repo.search_records(limit=200)
            detail = next((row for row in candidates if row.get("recall_number") == reference), None)
        if detail is not None:
            rows.append(detail)
    return rows


def _render_answer(answer: FinalAnswer, evidence: list[dict[str, object]]) -> None:
    """Render only prevalidated content with scope, freshness, and cited evidence."""
    st.markdown(answer.answer_markdown)
    if answer.metric_definitions:
        st.caption(" · ".join(answer.metric_definitions))
    if answer.limitations:
        st.caption("Limitations: " + " ".join(answer.limitations))
    st.caption(f"Data scope: {answer.data_scope} · {freshness_label(metadata())}")
    with st.expander("Evidence and data scope"):
        if evidence:
            fields = ["recall_number", "event_id", "report_date", "recalling_firm", "product_description"]
            st.dataframe([{field: row.get(field) for field in fields} for row in evidence], use_container_width=True)
            for row in evidence:
                url = official_source_url(row.get("recall_number"))
                if url:
                    st.link_button(f"Official openFDA record: {row.get('recall_number')}", url)
        else:
            st.write("No record-level evidence was returned for this answer.")


st.set_page_config(page_title="Ask RecallReady", layout="wide")
st.title("Ask RecallReady")
chrome()
st.caption("Ask concise questions about historical records and methodology; it cannot determine current safety, recall lifecycle, legal obligations, or future outcomes.")
repo = repository()
if repo is None:
    missing_data()
    st.stop()
settings = get_settings()
turns = _turns()
if st.button("Clear chat"):
    st.session_state["recallready_chat_turns"] = []
    st.session_state.pop("recallready_chat_last_request", None)
    st.rerun()

for turn in turns:
    with st.chat_message("user"):
        st.write(turn.question)
    with st.chat_message("assistant"):
        evidence = _evidence(repo, turn.answer.evidence_refs)
        if answer_has_valid_evidence(turn.answer, {str(row.get("recall_number") or row.get("source_record_id")) for row in evidence}):
            _render_answer(turn.answer, evidence)
        else:
            st.warning("This answer was withheld because its evidence could not be validated.")

if not settings.chat_available:
    st.subheader("Guided historical query builder")
    st.info("Chat is disabled. Use this deterministic summary while no OpenAI credentials are configured.")
    classifications = st.multiselect("Classification", ["Class I", "Class II", "Class III"])
    if st.button("Run historical summary"):
        from recallready.db.repository import RecordFilters
        result = repo.summary_metrics(RecordFilters(classifications=tuple(classifications)))
        st.metric("Historical product records", result["product_record_count"])
        st.metric("Known unique events", result["unique_event_count"])
        st.caption(f"{freshness_label(metadata())}. Known events exclude records without event IDs.")
    st.stop()

st.caption("Suggested questions")
for suggestion in SUGGESTIONS:
    st.write(f"- {suggestion}")
question = st.chat_input("Ask about historical enforcement records", max_chars=settings.max_chat_input_chars)
if question:
    reason = can_submit(turns, question, max_turns=settings.max_chat_turns_per_session, last_request=st.session_state.get("recallready_chat_last_request"))
    if reason:
        st.info(reason)
    else:
        st.session_state["recallready_chat_last_request"] = monotonic()
        with st.chat_message("user"):
            st.write(question)
        with st.chat_message("assistant"):
            try:
                from openai import OpenAI
                agent = RecallReadyAgent(OpenAI(api_key=settings.openai_api_key).responses, settings, ToolDispatcher(repo, metadata(), settings.max_tool_result_rows), str((metadata() or {}).get("sha256", "unknown")))
                answer = agent.answer(question)
                evidence = _evidence(repo, answer.evidence_refs)
                known = {str(row.get("recall_number") or row.get("source_record_id")) for row in evidence}
                if not answer_has_valid_evidence(answer, known):
                    st.warning("This answer was withheld because its evidence could not be validated.")
                else:
                    _render_answer(answer, evidence)
                    st.session_state["recallready_chat_turns"] = append_turn(turns, question, answer)
            except Exception:
                st.warning("Ask RecallReady is temporarily unavailable. No answer was saved.")
