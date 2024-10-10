import json
import logging
import os
from typing import Dict, Optional, Tuple

import json5
import requests

# Set up logging configuration
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


class NewsAIClassifier:
    def __init__(
        self,
        raw_extractions_dir: str = "raw_extractions",
        augmented_news_dir: str = "augmented_news",
    ):
        self.raw_extractions_dir = raw_extractions_dir
        self.augmented_news_dir = augmented_news_dir

        # Ensure the augmented_news directory exists
        if not os.path.exists(self.augmented_news_dir):
            os.makedirs(self.augmented_news_dir)
            logging.info(f"Created directory: {self.augmented_news_dir}")

    def call_llm(self, prompt: str) -> Optional[Dict]:
        """
        Call the LLM API with the given prompt and return the parsed JSON response.
        """
        headers = {"Content-Type": "application/json"}
        data = {
            "model": "llama3.1",
            "prompt": prompt,
            "stream": False,
            "format": "json",
        }

        try:
            response = requests.post(
                "http://localhost:11434/api/generate",
                headers=headers,
                data=json.dumps(data),
            )
            response.raise_for_status()
            response_data = json5.loads(response.text)
            response_json = json5.loads(response_data["response"])
            return response_json
        except requests.exceptions.RequestException as e:
            logging.error(f"Error calling LLM API. Error: {e}")
            return None
        except ValueError as e:
            logging.error(f"Error parsing JSON response. Error: {e}")
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

        response_json = self.call_llm(prompt)
        return response_json.get("is_ai_related", False) if response_json else False

    def generate_ai_explanation(self, news_entry: Dict[str, str]) -> str:
        """
        Generate an explanation of the relation to AI for a news entry by calling the LLM.
        """
        prompt = f"""
        O artigo de notícias a seguir foi classificado como relacionado à Inteligência Artificial (IA).
        Escreva um texto em português (Brasil), de no máximo 300 caracteres, explicando a relação do artigo com IA.

        Aqui estão os detalhes do artigo:
        Título: {news_entry['title']}
        URL: {news_entry['url']}
        Data: {news_entry['date']}
        Categoria: {news_entry['category']}
        Tags: {', '.join(news_entry.get('tags', []))}
        Conteúdo: {news_entry['content']}

        Responda no seguinte formato JSON:
        {{
            "ai_mention": "Texto explicando a relação com IA"
        }}
        """

        response_json = self.call_llm(prompt)
        return response_json.get("ai_mention", "") if response_json else ""

    def highlight_ai_explanation(self, text: str) -> str:
        """
        Highlight technical AI terms in the explanation text.
        """
        prompt = f"""
        Formate o texto a seguir destacando em negrito termos técnicos ou conceitos relacionados à Inteligência Artificial (IA).
        Utilize a tag <b></b> para destacar. Não utilize nenhuma outra tag HTML.

        Aqui está o texto:
        {text}

        Responda no seguinte formato JSON:
        {{
            "highlighted_text": "Texto com destaques"
        }}
        """

        response_json = self.call_llm(prompt)
        return response_json.get("highlighted_text", "") if response_json else ""

    def is_ai_related(self, news_entry: Dict[str, str]) -> Tuple[bool, str]:
        """
        Classify if the news is related to AI and generate an explanation.
        """
        is_related = self.classify_ai_related(news_entry)
        if is_related:
            ai_mention = self.generate_ai_explanation(news_entry)
            highlighted_text = self.highlight_ai_explanation(ai_mention)
            logging.info(
                f"\n\nArtigo relacionado à IA:\nTítulo: {news_entry['title']}\n\nMenção original: {ai_mention}\n\nMenção destacada: {highlighted_text}\n"
            )
            return True, highlighted_text
        else:
            return False, ""

    def process_files(self):
        """
        Process all JSON files in the raw_extractions directory and save augmented files to the augmented_news directory,
        preserving the directory structure.
        """
        for root, dirs, files in os.walk(self.raw_extractions_dir):
            for filename in files:
                if filename.endswith(".json"):
                    file_path = os.path.join(root, filename)
                    logging.info(f"Processing file: {file_path}")

                    try:
                        with open(file_path, "r", encoding="utf-8") as f:
                            news_data = json.load(f)
                    except (json.JSONDecodeError, OSError) as e:
                        logging.error(
                            f"Error reading JSON file: {file_path}. Error: {e}"
                        )
                        continue

                    for news_entry in news_data:
                        is_ai_related_flag, ai_mention = self.is_ai_related(news_entry)
                        news_entry["is_ai_related_flag"] = is_ai_related_flag
                        if is_ai_related_flag:
                            news_entry["ai_mention"] = ai_mention

                    # Construct the corresponding augmented file path
                    relative_path = os.path.relpath(file_path, self.raw_extractions_dir)
                    augmented_file_path = os.path.join(
                        self.augmented_news_dir, relative_path
                    )

                    # Ensure the output directory exists
                    augmented_dir = os.path.dirname(augmented_file_path)
                    if not os.path.exists(augmented_dir):
                        os.makedirs(augmented_dir)
                        logging.info(f"Created directory: {augmented_dir}")

                    try:
                        with open(augmented_file_path, "w", encoding="utf-8") as f:
                            json.dump(news_data, f, ensure_ascii=False, indent=4)
                        logging.info(f"Saved augmented file: {augmented_file_path}")
                    except OSError as e:
                        logging.error(
                            f"Error saving augmented file: {augmented_file_path}. Error: {e}"
                        )


if __name__ == "__main__":
    classifier = NewsAIClassifier()
    classifier.process_files()
