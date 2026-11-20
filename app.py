from __future__ import annotations

import os
from typing import Any

import pandas as pd
import streamlit as st

from database import (
    get_generation,
    initialize_database,
    list_generations,
    save_generation,
)
from export_utils import EXPORT_COLUMNS, test_cases_to_csv
from test_case_generator import (
    TestCaseGenerationError,
    generate_test_cases,
    validate_test_cases,
)

st.set_page_config(
    page_title="AI Test Case Generator",
    page_icon="🧪",
    layout="wide",
)

initialize_database()

if "requirement" not in st.session_state:
    st.session_state.requirement = ""
if "case_requirement" not in st.session_state:
    st.session_state.case_requirement = ""
if "test_cases" not in st.session_state:
    st.session_state.test_cases = []
if "analysis" not in st.session_state:
    st.session_state.analysis = None
if "cases_revision" not in st.session_state:
    st.session_state.cases_revision = 0

st.title("🧪 AI Test Case Generator")
st.markdown(
    "Turn plain-language software requirements into structured manual test cases. "
    "Generation runs locally through Ollama."
)

with st.sidebar:
    st.header("Local model")
    model_name = st.text_input(
        "Ollama model",
        value=os.getenv("OLLAMA_MODEL", "llama3.2"),
        help="Use a model already downloaded in Ollama, such as llama3.2.",
    )
    model_url = st.text_input(
        "Ollama URL",
        value=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
    )
    st.caption("Start Ollama and pull your model before generating cases.")

st.subheader("Describe the feature")
requirement = st.text_area(
    "Software requirement",
    value=st.session_state.requirement,
    height=150,
    placeholder=(
        "Example: A user should be able to register using name, email, and password."
    ),
    help="Describe the expected behavior and any rules that are known.",
    label_visibility="collapsed",
)
st.session_state.requirement = requirement

if st.button("Generate test cases", type="primary", use_container_width=False):
    if not requirement.strip():
        st.warning("Enter a software requirement before generating test cases.")
    else:
        with st.spinner("Analyzing the requirement and generating test cases..."):
            try:
                result = generate_test_cases(
                    requirement=requirement,
                    model_name=model_name,
                    base_url=model_url,
                )
            except (TestCaseGenerationError, RuntimeError) as exc:
                st.error(str(exc))
            else:
                st.session_state.analysis = result["analysis"]
                st.session_state.test_cases = result["test_cases"]
                st.session_state.case_requirement = requirement.strip()
                st.session_state.cases_revision += 1

analysis = st.session_state.analysis
if analysis:
    st.subheader("Requirement analysis")
    st.info(analysis["feature_summary"])
    categories = analysis.get("scenario_categories", [])
    if categories:
        st.caption("Scenario categories: " + ", ".join(categories))
    if analysis.get("clarification_needed"):
        st.warning("Clarification needed: " + analysis["clarification_needed"])

test_cases: list[dict[str, Any]] = st.session_state.test_cases
if test_cases:
    st.subheader("Generated test cases")
    st.caption(f"Requirement: {st.session_state.case_requirement}")
    st.caption(
        "Review and edit these AI-generated cases before using them in actual testing."
    )
    editor_key = f"cases_editor_{st.session_state.cases_revision}"
    edited_dataframe = st.data_editor(
        pd.DataFrame(test_cases, columns=EXPORT_COLUMNS),
        key=editor_key,
        hide_index=True,
        num_rows="fixed",
        use_container_width=True,
        disabled=["id"],
        column_config={
            "scenario_type": st.column_config.SelectboxColumn(
                "Scenario", options=["Positive", "Negative", "Edge"], required=True
            ),
            "priority": st.column_config.SelectboxColumn(
                "Priority", options=["High", "Medium", "Low"], required=True
            ),
            "steps": st.column_config.TextColumn("Steps", width="large"),
        },
    )
    st.session_state.test_cases = edited_dataframe.to_dict(orient="records")
    test_cases = st.session_state.test_cases

    selected_ids = st.multiselect(
        "Select test cases to delete",
        options=[case["id"] for case in test_cases],
        key=f"delete_selection_{st.session_state.cases_revision}",
    )
    if st.button("Delete selected test cases"):
        if selected_ids:
            st.session_state.test_cases = [
                case for case in test_cases if case["id"] not in selected_ids
            ]
            st.session_state.cases_revision += 1
            st.rerun()
        else:
            st.warning("Select at least one test case to delete.")

    col_save, col_export = st.columns(2)
    with col_save:
        if st.button("Save to history", use_container_width=True):
            try:
                validated_cases = validate_test_cases(test_cases)
            except TestCaseGenerationError as exc:
                st.error(f"Cannot save these test cases: {exc}")
            else:
                generation_id = save_generation(
                    st.session_state.case_requirement, validated_cases
                )
                st.session_state.test_cases = validated_cases
                st.success(f"Saved to history (record {generation_id}).")
    with col_export:
        try:
            csv_data = test_cases_to_csv(test_cases)
        except (TypeError, ValueError) as exc:
            st.error(f"Could not prepare the CSV export: {exc}")
        else:
            st.download_button(
                "Download CSV",
                data=csv_data,
                file_name="test_cases.csv",
                mime="text/csv",
                use_container_width=True,
                disabled=not test_cases,
            )
elif analysis and analysis.get("clarification_needed"):
    st.info("Add the requested details to the requirement and generate again.")

st.divider()
st.subheader("Saved history")
history = list_generations()
if not history:
    st.caption("Saved requirements and test cases will appear here.")
else:
    selected_generation = st.selectbox(
        "Previously saved requirements",
        options=history,
        format_func=lambda item: (
            f"#{item['id']} · {item['created_at']} · "
            f"{item['requirement'][:80]}"
        ),
    )
    st.caption(
        f"{selected_generation['test_case_count']} saved test cases · "
        f"{selected_generation['created_at']}"
    )
    with st.expander("View saved requirement"):
        st.write(selected_generation["requirement"])
    if st.button("Load selected history"):
        saved = get_generation(selected_generation["id"])
        if saved is None:
            st.error("That history record could not be found.")
        else:
            st.session_state.requirement = saved["requirement"]
            st.session_state.case_requirement = saved["requirement"]
            st.session_state.test_cases = saved["test_cases"]
            st.session_state.analysis = None
            st.session_state.cases_revision += 1
            st.rerun()