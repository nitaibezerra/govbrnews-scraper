import logging
import os
from typing import Dict, List, Optional, Tuple

from langchain.chains import LLMChain
from langchain.output_parsers import PydanticOutputParser
from langchain.prompts import PromptTemplate
from langchain_community.chat_models import ChatOpenAI
from pydantic import BaseModel, Field, conint


class ClassifiedTheme(BaseModel):
    theme: str = Field(..., description="The third-level theme identified")
    score: conint(ge=1, le=10) = Field(..., description="Relevance score from 1 to 10")


class NewsClassificationResult(BaseModel):
    classified_themes: List[ClassifiedTheme] = Field(
        ..., description="List of up to 3 classified themes with scores"
    )
    news_summary: str = Field(
        ...,
        description="A summary of the news up to 300 characters, focusing on the first theme",
    )


class NewsAnalyzer:
    def __init__(self, openai_api_key: str):
        """
        Initialize the NewsAnalyzer with the OpenAI API key.
        """
        self.openai_api_key = openai_api_key
        if not self.openai_api_key:
            raise ValueError("OpenAI API key must be provided.")

        self.themes_tree_content = self.load_themes_tree()

        # Define the output parser using Pydantic
        self.output_parser = PydanticOutputParser(
            pydantic_object=NewsClassificationResult
        )

    def load_themes_tree(self) -> str:
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

    def classify_and_generate_summary(
        self, news_entry: Dict[str, str]
    ) -> Tuple[Optional[NewsClassificationResult], str]:
        """
        Classify the news entry and generate a summary.

        :param news_entry: A dictionary containing news entry data.
        :return: A tuple containing the parsed response and the raw response.
        """
        # Get the format instructions from the output parser
        format_instructions = self.output_parser.get_format_instructions()

        # Build the prompt
        prompt_template_str = """
Você é um assistente especializado em classificar notícias com base em uma árvore temática de três níveis. Sua tarefa é analisar o **título** e o **texto** de uma notícia fornecida e:

1. **Identificar os 3 temas mais relevantes do terceiro nível** da árvore que se relacionam com a notícia, listando-os em ordem de prioridade (do mais relevante ao menos relevante).

2. Para cada tema identificado, **atribuir uma pontuação de 1 a 10** que represente o grau de correlação entre o tema e a notícia.

3. Elaborar um **resumo da notícia com até 300 caracteres**, destacando e correlacionando principalmente com o **primeiro tema escolhido**.

**Árvore Temática:**

```yaml
{themes_tree}
```

**Formato da Resposta:**

{format_instructions}

**Instruções Adicionais:**

- Certifique-se de que os temas selecionados são os mais relevantes para o conteúdo da notícia.

- A pontuação deve refletir a relevância e a importância de cada tema em relação à notícia.

- O resumo deve ser claro e conciso, enfatizando as partes da notícia que se relacionam principalmente com o **primeiro tema classificado**.

Aqui estão os detalhes da notícia:

Título: {title}
URL: {url}
Data: {date}
Categoria: {category}
Tags: {tags}
Conteúdo: {content}
"""

        # Create the prompt template with partial variables
        prompt = PromptTemplate(
            template=prompt_template_str,
            input_variables=[
                "themes_tree",
                "title",
                "url",
                "date",
                "category",
                "tags",
                "content",
            ],
            partial_variables={"format_instructions": format_instructions},
        )

        # Prepare the input variables
        input_variables = {
            "themes_tree": self.themes_tree_content,
            "title": news_entry["title"],
            "url": news_entry["url"],
            "date": news_entry["date"],
            "category": news_entry["category"],
            "tags": ", ".join(news_entry.get("tags", [])),
            "content": news_entry["content"],
        }

        # Create the LLM instance using ChatOpenAI
        llm = ChatOpenAI(
            openai_api_key=self.openai_api_key,
            temperature=0.5,
            model_name="gpt-3.5-turbo",
        )

        # Create the LLMChain with the output parser
        chain = LLMChain(llm=llm, prompt=prompt, output_parser=self.output_parser)

        # Call the chain
        try:
            parsed_response = chain.predict_and_parse(**input_variables)
            return (
                parsed_response,
                "",
            )  # Return the parsed response and an empty raw response
        except Exception as e:
            logging.error(f"Error processing LLM response: {e}")
            return None, ""
