"""Streamlit entry point for RecallReady."""

from __future__ import annotations

import streamlit as st

from recallready.config import get_settings
from recallready.logging_config import configure_logging
from recallready.ui.components import chrome, missing_data, repository


def main() -> None:
    """Render the Phase 1 landing page without loading external data."""
    settings = get_settings()
    configure_logging(settings.log_level)

    st.set_page_config(page_title="RecallReady", page_icon="🧭", layout="wide")
    st.title("RecallReady")
    st.caption("Historical U.S. food enforcement intelligence")
    chrome()
    if repository() is None:
        missing_data()
    else:
        st.success("Validated historical snapshot loaded. Use the pages in the navigation.")

    if not settings.chat_available:
        st.caption("The historical analyst is disabled because no OpenAI API key is configured.")

    st.markdown("See `docs/IMPLEMENTATION_PLAN.md` and `docs/ARCHITECTURE.md` for scope.")


if __name__ == "__main__":
    main()
