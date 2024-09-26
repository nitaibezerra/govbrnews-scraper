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

# Directory paths
raw_extractions_dir = "raw_extractions"
augmented_news_dir = "augmented_news"

# Ensure the augmented_news directory exists
if not os.path.exists(augmented_news_dir):
    os.makedirs(augmented_news_dir)
    logging.info(f"Created directory: {augmented_news_dir}")


def call_llm(prompt: str) -> Optional[Dict]:
    """
    Call the LLM API with the given prompt and return the parsed JSON response.

    :param prompt: The prompt to send to the LLM.
    :return: The parsed JSON response, or None in case of an error.
    """
    headers = {"Content-Type": "application/json"}
    data = {
        "model": "llama3.1",
        "prompt": prompt,
        "stream": False,
        "format": "json",
    }

    try:
        # Make the request to the LLM
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


def classify_ai_related(news_entry: Dict[str, str]) -> bool:
    """
    Determine if the news is related to AI by calling the LLM.

    :param news_entry: Dictionary containing the news attributes.
    :return: A boolean indicating if the news is related to AI.
    """
    prompt = f"""
    Analyze the following news article and determine if it is directly related to any field of Artificial Intelligence (AI). To be considered AI-related, the article must explicitly discuss AI technologies, such as machine learning, data science, data engineering, neural networks, natural language processing, computer vision, or other AI-specific techniques and applications.

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
    Tags: {', '.join(news_entry['tags'])}
    Content: {news_entry['content']}

    Please respond in the following JSON format:
    {{
        "is_ai_related": true
    }}

    In the response field, only include the object with the key is_ai_related. Do not include any other formatting such as markdown (```json), HTML, etc.
    """

    response_json = call_llm(prompt)
    if response_json:
        return response_json.get("is_ai_related", False)
    else:
        return False


def generate_ai_explanation(news_entry: Dict[str, str]) -> str:
    """
    Generate an explanation of the relation to AI for a news entry by calling the LLM.

    :param news_entry: Dictionary containing the news attributes.
    :return: A string containing the explanation of the relation to AI.
    """
    prompt = f"""
O artigo de notícias a seguir foi classificado como relacionado à Inteligência Artificial (IA). Escreva um texto em português (Brasil), de no máximo 300 caracteres, explicando a relação do artigo com IA.

Aqui estão os detalhes do artigo:
-------------------------------
    Título: {news_entry['title']}
    URL: {news_entry['url']}
    Data: {news_entry['date']}
    Categoria: {news_entry['category']}
    Tags: {', '.join(news_entry['tags'])}
    Conteúdo: {news_entry['content']}
-------------------------------

Responda no seguinte formato JSON:
{{
    "ai_mention": "Texto explicando a relação com IA"
}}


Dentro do campo response do JSON inclua apenas o objeto com a chave ai_mention. Não inclua qualquer outra formatação como markdown (```json), HTML, etc.
    """

    response_json = call_llm(prompt)
    if response_json:
        return response_json.get("ai_mention", "")
    else:
        return ""


def highlight_ai_explanation(text: str) -> str:
    prompt = f"""
Formate o texto a seguir destacando em negrito termos técnicos ou conceitos relacionados à Inteligência Artificial (IA).
Utilize a tag <b></b> para destacar. Não utilize nenhuma outra tag HTML.

Exemplos de termos técnicos:
- Inteligência Artificial
- Aprendizado de Máquina
- Visão Computacional
- Ciência de Dados
- Processamento de Linguagem Natural
- Redes Neurais
- Deep Learning
- Algoritmos Genéticos

Aqui está o texto:
-------------------------------
{text}
-------------------------------


Responda no seguinte formato JSON:
{{
    "highlighted_text": "Texto com destaques"
}}


Dentro do campo response do JSON inclua apenas o objeto com a chave highlighted_text.
    """

    response_json = call_llm(prompt)
    if response_json:
        return response_json.get("highlighted_text", "")
    else:
        return ""


def is_ai_related(news_entry: Dict[str, str]) -> Tuple[bool, str]:
    """
    First classify if the news is related to AI, then if true, generate an explanation.

    :param news_entry: Dictionary containing the news attributes.
    :return: A tuple (is_ai_related: bool, ai_mention: str) indicating if the news is related to AI and the ai_mention.
    """
    # First step: classify if the news is related to AI
    is_related = classify_ai_related(news_entry)

    if is_related:
        # Second step: generate the explanation if related to AI
        ai_mention = generate_ai_explanation(news_entry)
        highlighted_text = highlight_ai_explanation(ai_mention)
        logging.info(
            "\n\nArtigo relacionado à IA:\n"
            f"Título: {news_entry['title']}\n\n"
            f"Menção original:{ai_mention}\n\n"
            f"Menção destacada:{highlighted_text}\n"
        )

        return True, highlighted_text
    else:
        return False, ""


def process_files():
    """
    Process all JSON files in the raw_extractions directory, call Ollama, and save augmented files to augmented_news directory.
    """
    for filename in os.listdir(raw_extractions_dir):
        if filename.endswith(".json"):
            file_path = os.path.join(raw_extractions_dir, filename)
            logging.info(f"Processing file: {file_path}")

            # Read the JSON file
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    news_data = json.load(f)
            except (json.JSONDecodeError, OSError) as e:
                logging.error(f"Error reading JSON file: {file_path}. Error: {e}")
                continue

            # Analyze each news entry
            for news_entry in news_data:
                is_ai_related_flag, ai_mention = is_ai_related(news_entry)
                news_entry["is_ai_related_flag"] = is_ai_related_flag
                if is_ai_related_flag:
                    news_entry["ai_mention"] = ai_mention

            # Save the updated JSON to the augmented_news directory
            augmented_file_path = os.path.join(augmented_news_dir, filename)
            try:
                with open(augmented_file_path, "w", encoding="utf-8") as f:
                    json.dump(news_data, f, ensure_ascii=False, indent=4)
                logging.info(f"Saved augmented file: {augmented_file_path}")
            except OSError as e:
                logging.error(
                    f"Error saving augmented file: {augmented_file_path}. Error: {e}"
                )


if __name__ == "__main__":
    process_files()
