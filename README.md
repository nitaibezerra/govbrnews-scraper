# GovBR News Scraper

## Introdução

O **GovBR News Scraper** é uma ferramenta automatizada, em fase beta, desenvolvida pelo **Ministério da Gestão e Inovação em Serviços Públicos (MGI)**. Este projeto experimental visa coletar notícias de vários sites de agências governamentais dentro do domínio gov.br ([sites incluídos](https://github.com/nitaibezerra/govbrnews-scraper/blob/main/src/scraper/site_urls.yaml)), facilitando o monitoramento e o arquivamento de dados de notícias governamentais. A ferramenta faz a raspagem e extração de artigos de notícias, incluindo metadados como título, data, categoria e conteúdo, e os armazena em um formato estruturado.

A ferramenta é executada de forma programada, raspando as notícias do dia anterior e atualizando o repositório automaticamente. Este projeto é útil para pesquisadores, jornalistas e desenvolvedores interessados em monitorar e analisar notícias governamentais.

---

## Dados Disponíveis

Os dados extraídos estão disponíveis de forma centralizada no [Hugging Face Hub](https://huggingface.co/datasets/nitaibezerra/govbrnews), em dois formatos: **dataset estruturado** (compatível com a biblioteca `datasets`) e **arquivos CSV**.

### Dataset Estruturado no Hugging Face

Para carregar o dataset diretamente no Python utilizando a biblioteca `datasets`:

1. **Instale a Biblioteca `datasets`:**

   ```bash
   pip install datasets
   ```

2. **Carregue o Dataset em Seu Código Python:**

   ```python
   from datasets import load_dataset

   dataset = load_dataset("nitaibezerra/govbrnews")
   ```

3. **Explore o Dataset:**

   O dataset inclui os seguintes campos:
   - `unique_id`: Identificador único de cada notícia.
   - `agency`: Agência governamental que publicou a notícia.
   - `published_at`: Data de publicação da notícia.
   - `title`: Título da notícia.
   - `url`: URL da notícia original.
   - `image`: Link para a imagem principal da notícia.
   - `category`: Categoria da notícia (se disponível).
   - `tags`: Lista de tags associadas à notícia (se disponíveis).
   - `content`: Conteúdo completo da notícia em formato Markdown.
   - `extracted_at`: Data e hora em que a notícia foi extraída.

---

### Dados Disponíveis em CSV

Além do dataset estruturado, os dados estão disponíveis em arquivos CSV para facilitar o uso em ferramentas como Excel, Google Sheets, ou scripts personalizados:

1. **Arquivo Global CSV:**
   - Um único arquivo contendo todas as notícias disponíveis.
   - Acesse aqui: [govbr_news_dataset.csv](https://huggingface.co/datasets/nitaibezerra/govbrnews/blob/main/govbr_news_dataset.csv)

2. **Arquivos CSV por Agência (Órgão):**
   - Dados separados por agência governamental.
   - Acesse os arquivos por agência nesta pasta: [Agências](https://huggingface.co/datasets/nitaibezerra/govbrnews/tree/main/agencies)

3. **Arquivos CSV por Ano:**
   - Dados separados por ano de publicação.
   - Acesse os arquivos por ano nesta pasta: [Anos](https://huggingface.co/datasets/nitaibezerra/govbrnews/tree/main/years)

---

## Agendamento de Raspagem Automatizada

O repositório está configurado com uma **GitHub Action** que automaticamente raspa as notícias do dia anterior. O scraper é executado diariamente, garantindo que o dataset publicado no Hugging Face esteja sempre atualizado com as últimas notícias.

Todos os dias, o agendamento realiza as seguintes tarefas:

- Raspa os artigos de notícias publicados **ontem** de todas as agências gov.br listadas.
- Atualiza o dataset no Hugging Face com as novas notícias.

Essa configuração assegura que os dados permaneçam atualizados e acessíveis para todos os que utilizam o dataset.

---

## Contribuições

Contribuições para melhorar o **GovBR News Scraper** são muito bem-vindas! Caso encontre bugs, tenha sugestões de melhorias ou queira adicionar novas funcionalidades, sinta-se à vontade para abrir uma *issue* ou enviar um *pull request*.

Estamos sempre abertos a contribuições que possam melhorar o projeto!
