import logging
import os
from typing import Dict, List, Tuple

from dotenv import load_dotenv
from langchain.output_parsers import PydanticOutputParser
from langchain.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

load_dotenv()


class ClassifiedTheme(BaseModel):
    theme: str = Field(..., description="The third-level theme identified")
    theme_code: str = Field(..., description="The code associated with the theme")


class NewsClassificationResult(BaseModel):
    classified_themes: List[ClassifiedTheme] = Field(
        ..., description="List of up to 3 classified themes with scores"
    )
    news_summary: str = Field(
        ...,
        description="A summary of the news up to 500 characters, referring to the classified themes",
    )


class ClassifierSummarizer:
    def __init__(self):
        """
        Initialize the ClassifierSummarizer with the OpenAI API key.
        """
        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        if not self.openai_api_key:
            raise ValueError("OpenAI API key must be provided.")

        self.themes_tree_content = self._load_themes_tree()

        # Define the output parser using Pydantic
        self.output_parser = PydanticOutputParser(
            pydantic_object=NewsClassificationResult
        )

    def _load_themes_tree(self) -> str:
        """
        Load the themes tree from the 'themes_tree.yaml' file.
        """
        module_dir = os.path.dirname(os.path.abspath(__file__))
        themes_tree_path = os.path.join(module_dir, "themes_tree.yaml")
        try:
            with open(themes_tree_path, "r", encoding="utf-8") as f:
                themes_tree_content = f.read()
            return themes_tree_content
        except Exception as e:
            logging.error(f"Error reading themes_tree.yaml: {e}")
            return ""

    def get_themes_and_summary(
        self, news_entry: Dict[str, str]
    ) -> Tuple[List[Dict[str, str]], str]:
        """
        Classify the news entry and generate a summary.

        :param news_entry: A dictionary containing news entry data.
        :return: The parsed response.
        """
        # Get the format instructions from the output parser
        format_instructions = self.output_parser.get_format_instructions()

        # Build the prompt
        prompt_template_str = """
Você é um assistente especializado em classificar notícias com base em uma árvore temática hierárquica de três níveis. Sua tarefa é analisar uma notícia fornecida e:

1. **Identificar os 3 temas mais relevantes e mais específicos (do terceiro nível) da árvore** que se relacionam com a notícia. Os temas de terceiro nível possuem 3 partes numéricas (ex.: 16.04.01). Tenha certeza de que os temas selecionados são de terceiro nível.

2. Selecione temas que são complementares e não redundantes. Temas em posições distantes na árvore são mais complementares.

3. Elaborar um **resumo da notícia com até 500 caracteres**, destacando e correlacionando com os **temas escolhidos**.

**Árvore Temática:**

```yaml
{themes_tree}
```

**Formato da Resposta:**

{format_instructions}

**Instruções Adicionais:**

- Certifique-se de que os temas selecionados são os mais relevantes para o conteúdo da notícia e que não são redundantes.

- A pontuação deve refletir a relevância e a importância de cada tema em relação à notícia.

- O resumo deve ser claro e conciso, enfatizando as partes da notícia que se relacionam principalmente com o **primeiro tema classificado**.

Aqui estão os detalhes da notícia:

Título: {title}
Data de Publicação: {published_at}
Categoria: {category}
Tags: {tags}
Conteúdo: {content}
"""

        # Convert the above string template into a ChatPromptTemplate
        chat_prompt = ChatPromptTemplate.from_template(prompt_template_str)

        # Prepare the input variables
        input_data = {
            "themes_tree": self.themes_tree_content,
            "title": news_entry["title"],
            "published_at": news_entry["published_at"],
            "category": news_entry["category"],
            "tags": ", ".join(news_entry.get("tags", [])),
            "content": news_entry["content"],
            "format_instructions": format_instructions,
        }

        # Create the LLM
        llm = ChatOpenAI(
            openai_api_key=self.openai_api_key,
            temperature=0.7,
            model_name="gpt-4o",
        )

        # Build a RunnableSequence / pipe that goes: prompt -> llm -> parser
        chain = chat_prompt | llm | self.output_parser

        # Invoke the chain with the input data
        parsed_response: NewsClassificationResult = chain.invoke(input_data)

        # Extract from the parsed response
        themes = [theme.model_dump() for theme in parsed_response.classified_themes]
        summary = parsed_response.news_summary

        return themes, summary
