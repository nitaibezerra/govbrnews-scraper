import argparse
import json
import logging
import os
from typing import Dict, Optional, Tuple

import openai
from dotenv import load_dotenv
from openai import OpenAI

# Load environment variables from the .env file
load_dotenv()

# Set up logging configuration
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


class NewsAIClassifier:
    def __init__(
        self,
        raw_extractions_dir: str = "raw_extractions",
        augmented_news_dir: str = "augmented_news",
        openai_api_key: Optional[str] = None,
    ):
        self.raw_extractions_dir = raw_extractions_dir
        self.augmented_news_dir = augmented_news_dir
        self.openai_api_key = openai_api_key or os.getenv("OPENAI_API_KEY")

        if not self.openai_api_key:
            raise ValueError("OpenAI API key must be provided.")
        openai.api_key = self.openai_api_key

        # Ensure the augmented_news directory exists
        if not os.path.exists(self.augmented_news_dir):
            os.makedirs(self.augmented_news_dir)
            logging.info(f"Created directory: {self.augmented_news_dir}")

    def call_openai_api(self, prompt: str) -> Optional[Dict]:
        """
        Call the OpenAI API with the given prompt and return the parsed JSON response.
        """
        try:
            # Create an OpenAI client instance with the API key
            client = OpenAI(api_key=self.openai_api_key)

            # Make the API call using the updated method
            response = client.chat.completions.create(
                model="gpt-3.5-turbo",  # Specify the model you want to use
                messages=[
                    {"role": "system", "content": "You are an AI expert."},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=250,
                n=1,
                stop=None,
                temperature=0.5,
            )

            # Extract and parse the response
            response_text = response.choices[0].message.content.strip()
            response_json = json.loads(response_text)
            return response_json
        except Exception as e:
            logging.error(f"OpenAI API error: {e}")
            return None

    def classify_ai_related(self, news_entry: Dict[str, str]) -> bool:
        """
        Determine if the news is related to AI by calling the LLM.
        """
        prompt = f"""
        Analyze the following news article and determine if it is directly related to any field of Artificial Intelligence (AI).
        To be considered AI-related, the article must explicitly discuss AI technologies, such as machine learning, data science,
        data engineering, neural networks, natural language processing, computer vision, or other AI-specific techniques and applications.

        Disregard articles that:
        - Mention general technological advancements or digital transformation without explicit reference to AI technologies.
        - Focus on information technology (IT) infrastructure, cybersecurity, data privacy, digital governance, or public management, unless AI is a central theme.
        - Discuss technology or innovation in a generic way without specifically addressing AI-related concepts or applications.

        To classify the article as AI-related, there must be a clear and direct reference to AI technologies. Please avoid making inferences based on vague mentions of technology.

        Here is the information:
        Title: {news_entry['title']}
        URL: {news_entry['url']}
        Date: {news_entry['date']}
        Category: {news_entry['category']}
        Tags: {', '.join(news_entry.get('tags', []))}
        Content: {news_entry['content']}

        Please respond in the following JSON format:
        {{
            "is_ai_related": true
        }}
        """

        response_json = self.call_openai_api(prompt)
        return response_json.get("is_ai_related", False) if response_json else False

    def generate_and_highlight_ai_explanation(self, news_entry: Dict[str, str]) -> str:
        """
        Generate an explanation of the relation to AI for a news entry and highlight AI terms
        in a single API call.
        """
        prompt = f"""
        O artigo de notícias a seguir foi classificado como relacionado à Inteligência Artificial (IA).
        Escreva um texto em português (Brasil), de no máximo 300 caracteres, explicando a relação do artigo com IA.
        Além disso, destaque em negrito termos técnicos ou conceitos relacionados à Inteligência Artificial (IA) usando a tag <b></b>.

        Aqui estão os detalhes do artigo:
        Título: {news_entry['title']}
        URL: {news_entry['url']}
        Data: {news_entry['date']}
        Categoria: {news_entry['category']}
        Tags: {', '.join(news_entry.get('tags', []))}
        Conteúdo: {news_entry['content']}

        Responda no seguinte formato JSON:
        {{
            "ai_mention": "Texto explicando a relação com IA com os termos técnicos destacados em negrito"
        }}
        """

        response_json = self.call_openai_api(prompt)
        return response_json.get("ai_mention", "") if response_json else ""

    def is_ai_related(self, news_entry: Dict[str, str]) -> Tuple[bool, str]:
        """
        Classify if the news is related to AI and generate a highlighted explanation.
        """
        is_related = self.classify_ai_related(news_entry)
        if is_related:
            ai_mention = self.generate_and_highlight_ai_explanation(news_entry)
            logging.info(
                f"\n\nArtigo relacionado à IA:\nTítulo: {news_entry['title']}\n\nMenção destacada: {ai_mention}\n"
            )
            return True, ai_mention
        else:
            return False, ""

    def process_files(self):
        """
        Main method to process all JSON files in the raw_extractions directory
        and save augmented files to the augmented_news directory.
        """
        for root, dirs, files in os.walk(self.raw_extractions_dir):
            for filename in files:
                if filename.endswith(".json"):
                    file_path = os.path.join(root, filename)
                    augmented_file_path = self.get_augmented_file_path(file_path)

                    if self.should_skip_file(augmented_file_path):
                        continue

                    news_data = self.load_json_file(file_path)
                    if news_data is None:
                        continue

                    augmented_data = self.process_news_entries(news_data)
                    self.save_augmented_file(augmented_file_path, augmented_data)

    def get_augmented_file_path(self, file_path: str) -> str:
        """
        Construct the augmented file path based on the raw file path, preserving the directory structure.
        """
        relative_path = os.path.relpath(file_path, self.raw_extractions_dir)
        return os.path.join(self.augmented_news_dir, relative_path)

    def should_skip_file(self, augmented_file_path: str) -> bool:
        """
        Check if the augmented file already exists to decide if the processing can be skipped.
        """
        if os.path.exists(augmented_file_path):
            logging.info(f"Skipping already processed file: {augmented_file_path}")
            return True
        return False

    def load_json_file(self, file_path: str) -> Optional[Dict]:
        """
        Load the JSON file and return its content. Log an error if the file cannot be read.
        """
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            logging.error(f"Error reading JSON file: {file_path}. Error: {e}")
            return None

    def process_news_entries(self, news_data: Dict) -> Dict:
        """
        Process each news entry in the JSON data to determine if it is AI-related and generate explanations.
        """
        for news_entry in news_data:
            is_ai_related_flag, ai_mention = self.is_ai_related(news_entry)
            news_entry["is_ai_related_flag"] = is_ai_related_flag
            if is_ai_related_flag:
                news_entry["ai_mention"] = ai_mention
        return news_data

    def save_augmented_file(self, augmented_file_path: str, augmented_data: Dict):
        """
        Save the augmented data to the specified file path, creating directories if necessary.
        """
        augmented_dir = os.path.dirname(augmented_file_path)
        if not os.path.exists(augmented_dir):
            os.makedirs(augmented_dir)
            logging.info(f"Created directory: {augmented_dir}")

        try:
            with open(augmented_file_path, "w", encoding="utf-8") as f:
                json.dump(augmented_data, f, ensure_ascii=False, indent=4)
            logging.info(f"Saved augmented file: {augmented_file_path}")
        except OSError as e:
            logging.error(
                f"Error saving augmented file: {augmented_file_path}. Error: {e}"
            )


if __name__ == "__main__":
    # Parse command-line arguments
    parser = argparse.ArgumentParser(
        description="Process news files and classify AI-related articles."
    )
    parser.add_argument(
        "--openai_api_key",
        type=str,
        default=None,
        help="OpenAI API key (if not provided, will use OPENAI_API_KEY environment variable).",
    )
    args = parser.parse_args()

    classifier = NewsAIClassifier(
        openai_api_key=args.openai_api_key,
    )
    classifier.process_files()
