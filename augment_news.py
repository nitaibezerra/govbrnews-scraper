import argparse
import json
import logging
import os
from datetime import datetime
from typing import Dict, Optional, Tuple

import openai
from dotenv import load_dotenv
from langchain import OpenAI
from langchain.output_parsers import ResponseSchema, StructuredOutputParser
from langchain.prompts import PromptTemplate

# from openai import OpenAI

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
                # model="gpt-3.5-turbo",
                model="gpt-4o-mini",
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

    def classify_and_generate_ai_explanation(
        self, news_entry: Dict[str, str]
    ) -> Tuple[bool, str]:
        """
        Classify if the news is related to AI and generate a highlighted explanation in a single API call.
        Uses Langchain for better output structuring.
        """
        # Define the expected response schema
        response_schemas = [
            ResponseSchema(
                name="is_ai_related",
                description="A boolean indicating if the article is related to AI.",
            ),
            ResponseSchema(
                name="ai_mention",
                description="A brief explanation of the relationship with AI, highlighting technical terms in Markdown.",
            ),
        ]

        # Create the output parser
        output_parser = StructuredOutputParser.from_response_schemas(response_schemas)

        # Create the prompt template
        prompt_template = """
        Analise o seguinte artigo de notícias e determine se ele está diretamente relacionado ao campo de Inteligência Artificial (IA).
        Para ser considerado relacionado à IA, o artigo deve discutir explicitamente tecnologias de IA, como Aprendizado de Máquina (Machine Learning),
        Processamento de Imagem, Modelos de Linguagem de Grande Escala (LLM), IA Generativa, Redes Neurais, Processamento de Linguagem Natural (NLP),
        Visão Computacional, Deep Learning, ou outros temas específicos de IA.

        Se o artigo estiver relacionado à IA, escreva um texto em português (Brasil), de no máximo 300 caracteres, explicando a relação do artigo com IA.
        Além disso, destaque em Markdown os termos técnicos ou conceitos relacionados à Inteligência Artificial (IA) usando ** para destacar.

        Aqui estão os detalhes do artigo:
        Título: {title}
        URL: {url}
        Data: {date}
        Categoria: {category}
        Tags: {tags}
        Conteúdo: {content}

        Responda no seguinte formato JSON:
        {format_instructions}
        """

        # Use Langchain's prompt template with the news entry data
        prompt = PromptTemplate(
            input_variables=[
                "title",
                "url",
                "date",
                "category",
                "tags",
                "content",
                "format_instructions",
            ],
            template=prompt_template,
        ).format(
            title=news_entry["title"],
            url=news_entry["url"],
            date=news_entry["date"],
            category=news_entry["category"],
            tags=", ".join(news_entry.get("tags", [])),
            content=news_entry["content"],
            format_instructions=output_parser.get_format_instructions(),
        )

        # Call the OpenAI API using Langchain with structured output parsing
        try:
            # Make the API call through Langchain's OpenAI integration
            llm = OpenAI(api_key=self.openai_api_key)
            response = llm(prompt)

            # Parse the response
            parsed_response = output_parser.parse(response)

            is_ai_related = bool(parsed_response.get("is_ai_related", False))
            ai_mention = parsed_response.get("ai_mention", "")

            return is_ai_related, ai_mention

        except Exception as e:
            logging.error(f"Error processing LLM response: {e}")
            return False, ""

    def is_ai_related(self, news_entry: Dict[str, str]) -> Tuple[bool, str]:
        """
        Classify if the news is related to AI and generate a highlighted explanation.
        """
        is_related, ai_mention = self.classify_and_generate_ai_explanation(news_entry)
        if is_related:
            logging.info(
                f"\n\nArtigo relacionado à IA:\nTítulo: {news_entry['title']}\n\nMenção destacada: {ai_mention}\n"
            )
        return is_related, ai_mention

    def process_files(
        self, min_date: Optional[str] = None, agency: Optional[str] = None
    ):
        """
        Main method to process all JSON files in the raw_extractions directory and save augmented files to the augmented_news directory.
        Only processes files from a specified agency (if provided) and files with a date greater than or equal to min_date (if provided).

        :param min_date: Minimum date to process (format: 'YYYY-MM-DD').
        :param agency: Agency to filter by (only process files from this agency).
        """
        for root, dirs, files in os.walk(self.raw_extractions_dir):
            # Filter by agency if provided
            if agency and agency not in root:
                continue

            for filename in files:
                # Skip non-JSON files
                if not filename.endswith(".json"):
                    continue

                # Extract the date from the filename (assuming filename has format like 'agency_YYYY-MM-DD.json')
                file_date = filename.split("_")[-1].replace(".json", "")

                # Filter by date if provided
                if min_date and file_date < min_date:
                    continue

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
    parser.add_argument(
        "--min_date",
        type=str,
        default=None,
        help="Minimum date to process files from (format: 'YYYY-MM-DD').",
    )
    parser.add_argument(
        "--agency",
        type=str,
        default=None,
        help="Agency to filter the files by.",
    )
    args = parser.parse_args()

    classifier = NewsAIClassifier(
        openai_api_key=args.openai_api_key,
    )

    # Pass the min_date and agency to the process_files method
    classifier.process_files(min_date=args.min_date, agency=args.agency)
