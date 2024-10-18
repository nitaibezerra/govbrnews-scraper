import logging
from typing import Dict, Tuple

from langchain.chains import LLMChain
from langchain.output_parsers import ResponseSchema, StructuredOutputParser
from langchain.prompts import PromptTemplate
from langchain_community.chat_models import ChatOpenAI


class NewsAnalyzer:
    def __init__(self, openai_api_key: str):
        """
        Initialize the NewsAnalyzer with the OpenAI API key.

        :param openai_api_key: OpenAI API key for making API calls.
        """
        self.openai_api_key = openai_api_key
        if not self.openai_api_key:
            raise ValueError("OpenAI API key must be provided.")

    def classify_and_generate_ai_explanation(
        self, news_entry: Dict[str, str]
    ) -> Tuple[bool, str]:
        """
        Classify if the news is related to AI and generate a highlighted explanation in a single API call.
        Uses Langchain for better output structuring.

        :param news_entry: A dictionary containing news entry data.
        :return: A tuple containing a boolean indicating if the article is AI-related and the AI mention text.
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

        # Get the format instructions for the output parser
        format_instructions = output_parser.get_format_instructions()

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

        # Create the prompt with partial variables
        prompt = PromptTemplate(
            template=prompt_template,
            input_variables=["title", "url", "date", "category", "tags", "content"],
            partial_variables={"format_instructions": format_instructions},
        )

        # Create the LLM instance using ChatOpenAI
        llm = ChatOpenAI(openai_api_key=self.openai_api_key, temperature=0.5)

        # Create the LLMChain with the prompt and output parser
        chain = LLMChain(llm=llm, prompt=prompt, output_parser=output_parser)

        # Prepare the input variables
        input_variables = {
            "title": news_entry["title"],
            "url": news_entry["url"],
            "date": news_entry["date"],
            "category": news_entry["category"],
            "tags": ", ".join(news_entry.get("tags", [])),
            "content": news_entry["content"],
        }

        # Call the chain using predict_and_parse
        try:
            parsed_response = chain.predict_and_parse(**input_variables)

            is_ai_related = bool(parsed_response.get("is_ai_related", False))
            ai_mention = parsed_response.get("ai_mention", "")

            return is_ai_related, ai_mention

        except Exception as e:
            logging.error(f"Error processing LLM response: {e}")
            return False, ""
