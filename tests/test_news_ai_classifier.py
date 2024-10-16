import os

import pytest
import yaml
from augment_news import NewsAIClassifier  # Import your classifier class

# Get the directory where this test script is located
test_dir = os.path.dirname(os.path.abspath(__file__))

# Construct the path to the test_data.yaml file in the same directory as the test script
test_data_file = os.path.join(test_dir, "test_data.yaml")

# Load the test data from the YAML file
with open(test_data_file, "r") as f:
    test_data = yaml.safe_load(f)


@pytest.mark.parametrize(
    "news_entry, expected_is_ai_related_flag",
    [
        (case["news_entry"], case["expected_is_ai_related_flag"])
        for case in test_data["test_cases"]
    ],
)
def test_classify_and_generate_ai_explanation(news_entry, expected_is_ai_related_flag):
    classifier = NewsAIClassifier()

    # Call the classify_and_generate_ai_explanation method
    is_ai_related, _ = classifier.classify_and_generate_ai_explanation(news_entry)

    # Assert the result matches the expected flag
    assert is_ai_related == expected_is_ai_related_flag
