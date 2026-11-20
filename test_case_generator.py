from __future__ import annotations

import json
import re
from typing import Any

from agent import invoke_local_model

SCENARIO_TYPES = {"Positive", "Negative", "Edge"}
PRIORITIES = {"High", "Medium", "Low"}
REQUIRED_CASE_FIELDS = (
    "id",
    "scenario_type",
    "title",
    "preconditions",
    "steps",
    "test_data",
    "expected_result",
    "priority",
    "assumptions",
)


class TestCaseGenerationError(ValueError):
    """Raised when input or generated test case data is invalid."""


def _required_text(value: Any, field: str, case_id: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise TestCaseGenerationError(
            f"{case_id}: '{field}' must be a non-empty string."
        )
    return value.strip()


def _format_steps(value: Any, case_id: str) -> str:
    if isinstance(value, list):
        if not value or any(not isinstance(step, str) or not step.strip() for step in value):
            raise TestCaseGenerationError(
                f"{case_id}: 'steps' must contain at least one non-empty step."
            )
        return "\n".join(
            f"{index}. {step.strip()}" for index, step in enumerate(value, start=1)
        )
    if isinstance(value, str) and value.strip():
        return value.strip()
    raise TestCaseGenerationError(
        f"{case_id}: 'steps' must contain at least one non-empty step."
    )


def validate_test_cases(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, list):
        raise TestCaseGenerationError("'test_cases' must be a list.")
    if not value:
        return []

    validated: list[dict[str, str]] = []
    seen_ids: set[str] = set()
    seen_titles: set[str] = set()

    for index, case in enumerate(value, start=1):
        if not isinstance(case, dict):
            raise TestCaseGenerationError(f"Test case {index} must be a JSON object.")

        missing_fields = [field for field in REQUIRED_CASE_FIELDS if field not in case]
        if missing_fields:
            raise TestCaseGenerationError(
                f"Test case {index} is missing required fields: "
                f"{', '.join(missing_fields)}."
            )

        case_id = _required_text(case["id"], "id", f"Test case {index}")
        if not re.fullmatch(r"TC-\d{2,}", case_id):
            raise TestCaseGenerationError(
                f"Test case ID '{case_id}' must use the format TC-01."
            )
        if case_id in seen_ids:
            raise TestCaseGenerationError(f"Duplicate test case ID '{case_id}'.")
        expected_id = f"TC-{index:02d}"
        if case_id != expected_id:
            raise TestCaseGenerationError(
                f"Test case IDs must be sequential; expected '{expected_id}' "
                f"but received '{case_id}'."
            )
        seen_ids.add(case_id)

        scenario_type = _required_text(
            case["scenario_type"], "scenario_type", case_id
        ).title()
        if scenario_type not in SCENARIO_TYPES:
            raise TestCaseGenerationError(
                f"{case_id}: scenario_type must be Positive, Negative, or Edge."
            )

        priority = _required_text(case["priority"], "priority", case_id).title()
        if priority not in PRIORITIES:
            raise TestCaseGenerationError(
                f"{case_id}: priority must be High, Medium, or Low."
            )

        title = _required_text(case["title"], "title", case_id)
        normalized_title = " ".join(title.casefold().split())
        if normalized_title in seen_titles:
            raise TestCaseGenerationError(f"Duplicate test case title '{title}'.")
        seen_titles.add(normalized_title)

        assumptions = case["assumptions"]
        if isinstance(assumptions, list):
            if any(not isinstance(item, str) or not item.strip() for item in assumptions):
                raise TestCaseGenerationError(
                    f"{case_id}: 'assumptions' must contain non-empty strings."
                )
            assumptions_text = "; ".join(item.strip() for item in assumptions)
        elif isinstance(assumptions, str):
            assumptions_text = assumptions.strip()
        else:
            raise TestCaseGenerationError(
                f"{case_id}: 'assumptions' must be a string or list of strings."
            )

        validated.append(
            {
                "id": case_id,
                "scenario_type": scenario_type,
                "title": title,
                "preconditions": _required_text(
                    case["preconditions"], "preconditions", case_id
                ),
                "steps": _format_steps(case["steps"], case_id),
                "test_data": _required_text(case["test_data"], "test_data", case_id),
                "expected_result": _required_text(
                    case["expected_result"], "expected_result", case_id
                ),
                "priority": priority,
                "assumptions": assumptions_text,
            }
        )

    return validated


def parse_model_response(raw_response: str) -> dict[str, Any]:
    if not isinstance(raw_response, str) or not raw_response.strip():
        raise TestCaseGenerationError("The model returned an empty response.")

    response_text = raw_response.strip()
    if response_text.startswith("```"):
        response_text = re.sub(r"^```(?:json)?\s*|\s*```$", "", response_text)

    try:
        payload = json.loads(response_text)
    except json.JSONDecodeError as exc:
        raise TestCaseGenerationError(
            f"The model response was not valid JSON (line {exc.lineno}, "
            f"column {exc.colno}). Try generating again."
        ) from exc

    if not isinstance(payload, dict):
        raise TestCaseGenerationError("The model response must be a JSON object.")

    analysis = payload.get("analysis")
    if not isinstance(analysis, dict):
        raise TestCaseGenerationError("The model response is missing its analysis.")

    summary = analysis.get("feature_summary")
    if not isinstance(summary, str) or not summary.strip():
        raise TestCaseGenerationError("The model response is missing a feature summary.")

    clarification = analysis.get("clarification_needed", "")
    if not isinstance(clarification, str):
        raise TestCaseGenerationError(
            "The model's clarification_needed field must be a string."
        )

    cases = validate_test_cases(payload.get("test_cases"))
    if not cases and not clarification.strip():
        raise TestCaseGenerationError(
            "The model returned no test cases or clarification. Try again."
        )

    categories = analysis.get("scenario_categories", [])
    if not isinstance(categories, list) or any(
        not isinstance(category, str) for category in categories
    ):
        raise TestCaseGenerationError(
            "The model's scenario_categories field must be a list of strings."
        )

    return {
        "analysis": {
            "feature_summary": summary.strip(),
            "scenario_categories": categories,
            "clarification_needed": clarification.strip(),
        },
        "test_cases": cases,
    }


def generate_test_cases(
    requirement: str,
    model_name: str,
    base_url: str | None = None,
) -> dict[str, Any]:
    if not isinstance(requirement, str) or not requirement.strip():
        raise TestCaseGenerationError("Enter a software requirement first.")
    if len(requirement) > 8000:
        raise TestCaseGenerationError(
            "The requirement is too long. Please keep it under 8,000 characters."
        )
    if not isinstance(model_name, str) or not model_name.strip():
        raise TestCaseGenerationError("Enter an Ollama model name.")

    raw_response = invoke_local_model(
        requirement=requirement.strip(),
        model_name=model_name.strip(),
        base_url=base_url.strip() if base_url else None,
    )
    return parse_model_response(raw_response)