import json
import tempfile
import unittest
from pathlib import Path

from database import get_generation, initialize_database, list_generations, save_generation
from export_utils import test_cases_to_csv
from test_case_generator import (
    TestCaseGenerationError,
    parse_model_response,
    validate_test_cases,
)


def sample_case(case_id="TC-01"):
    return {
        "id": case_id,
        "scenario_type": "Positive",
        "title": "Register with valid details",
        "preconditions": "Registration page is available",
        "steps": ["Enter valid details", "Submit the form"],
        "test_data": "Name: Ana; email: ana@example.com; password: Example123",
        "expected_result": "The account is created successfully",
        "priority": "High",
        "assumptions": [],
    }


class ValidateTestCasesTests(unittest.TestCase):
    def test_normalizes_case_for_display(self):
        result = validate_test_cases([sample_case()])
        self.assertEqual(result[0]["steps"], "1. Enter valid details\n2. Submit the form")
        self.assertEqual(result[0]["assumptions"], "")

    def test_rejects_non_sequential_ids(self):
        with self.assertRaisesRegex(TestCaseGenerationError, "sequential"):
            validate_test_cases([sample_case("TC-02")])

    def test_rejects_unsupported_priority(self):
        case = sample_case()
        case["priority"] = "Urgent"
        with self.assertRaisesRegex(TestCaseGenerationError, "priority"):
            validate_test_cases([case])

    def test_rejects_duplicate_titles(self):
        second = sample_case("TC-02")
        second["title"] = "  REGISTER WITH VALID DETAILS "
        with self.assertRaisesRegex(TestCaseGenerationError, "Duplicate"):
            validate_test_cases([sample_case(), second])

    def test_accepts_clarification_without_cases(self):
        payload = {
            "analysis": {
                "feature_summary": "The feature is not described clearly.",
                "scenario_categories": [],
                "clarification_needed": "Please describe the expected behavior.",
            },
            "test_cases": [],
        }
        parsed = parse_model_response(json.dumps(payload))
        self.assertEqual(parsed["test_cases"], [])
        self.assertIn("Please describe", parsed["analysis"]["clarification_needed"])

    def test_rejects_invalid_json(self):
        with self.assertRaisesRegex(TestCaseGenerationError, "valid JSON"):
            parse_model_response("{not json}")

    def test_sqlite_history_survives_reopening(self):
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "history.sqlite"
            initialize_database(database_path)
            generation_id = save_generation(
                "A user can register.", validate_test_cases([sample_case()]), database_path
            )

            self.assertEqual(list_generations(database_path)[0]["id"], generation_id)
            saved = get_generation(generation_id, database_path)

            self.assertEqual(saved["requirement"], "A user can register.")
            self.assertEqual(saved["test_cases"][0]["id"], "TC-01")

    def test_csv_contains_cases_and_headers(self):
        csv_text = test_cases_to_csv(validate_test_cases([sample_case()]))
        self.assertIn("scenario_type", csv_text.splitlines()[0])
        self.assertIn("Register with valid details", csv_text)


if __name__ == "__main__":
    unittest.main()
