import os
import pytest
import yaml

from src.augmentation.classifier_summarizer import (
    ClassifierSummarizer,
)


def _load_test_cases():
    """Helper function to load test cases for the class-based approach."""
    current_dir = os.path.dirname(__file__)
    yaml_path = os.path.join(current_dir, "test_cases.yaml")
    with open(yaml_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data["test_cases"]


@pytest.fixture(params=_load_test_cases())
def test_case(request):
    """Fixture that supplies a single test case at a time from the YAML file."""
    return request.param


class TestNewsAnalyzer:
    def test_get_themes_and_summary(self, test_case):
        # Extract inputs and expectations from the test case
        news_entry = test_case["news_entry"]
        expected_theme_macro_code = test_case["expected_theme_macro_code"]

        # Initialize the analyzer (mock out if needed)
        analyzer = ClassifierSummarizer()

        # Get themes (which contain "theme_code" in each dict)
        themes, _ = analyzer.get_themes_and_summary(news_entry)

        # Extract the theme_code from each returned theme
        returned_theme_codes = [theme_dict["theme_code"] for theme_dict in themes]

        # Check if any theme_code starts with the expected macro code
        assert any(
            code.startswith(expected_theme_macro_code) for code in returned_theme_codes
        ), (
            f"None of the returned theme codes ({returned_theme_codes}) starts with "
            f"{expected_theme_macro_code}"
        )
