
# GovBR News Scraper

## Introdução

O **GovBR News Scraper** é uma ferramenta automatizada, em fase beta, desenvolvida pelo **Ministério da Gestão e Inovação em Serviços Públicos (MGI)**. Este projeto experimental visa coletar notícias de vários sites de agências governamentais dentro do domínio gov.br ([sites incluídos](https://github.com/nitaibezerra/govbrnews-scraper/blob/main/site_urls.yaml)), facilitando o monitoramento e o arquivamento de dados de notícias governamentais. A ferramenta faz a raspagem e extração de artigos de notícias, incluindo metadados como título, data, categoria e conteúdo, e os armazena em um formato estruturado.

A ferramenta é executada de forma programada, raspando as notícias do dia anterior e atualizando o repositório automaticamente. Este projeto é útil para pesquisadores, jornalistas e desenvolvedores interessados em monitorar e analisar notícias governamentais.

## Dados Disponíveis no Hugging Face

Os dados resultantes da raspagem estão disponíveis no [Hugging Face Hub](https://huggingface.co/datasets/nitaibezerra/govbrnews), permitindo acesso fácil e centralizado ao dataset atualizado.

**Como utilizar o dataset:**

1. **Acesse o Dataset no Hugging Face:**

   Visite [nitaibezerra/govbrnews](https://huggingface.co/datasets/nitaibezerra/govbrnews) para visualizar informações sobre o dataset, incluindo exemplos e detalhes sobre os campos disponíveis.

2. **Instale a Biblioteca `datasets`:**

   Certifique-se de ter a biblioteca `datasets` instalada:

   ```bash
   pip install datasets
   ```

3. **Carregue o Dataset em Seu Código Python:**

   ```python
   from datasets import load_dataset

   dataset = load_dataset("nitaibezerra/govbrnews")
   ```

   Isso permite que você trabalhe com os dados de forma eficiente, aproveitando as funcionalidades oferecidas pela biblioteca `datasets`.

4. **Explore o Dataset:**

   O dataset inclui os seguintes campos:

   - `unique_id`: Identificador único de cada notícia.
   - `agency`: Agência governamental que publicou a notícia.
   - `published_at`: Data de publicação da notícia.
   - `title`: Título da notícia.
   - `url`: URL da notícia original.
   - `category`: Categoria da notícia (se disponível).
   - `tags`: Lista de tags associadas à notícia (se disponíveis).
   - `content`: Conteúdo completo da notícia.
   - `extracted_at`: Data e hora em que a notícia foi extraída.

   Você pode explorar e manipular esses campos conforme necessário para suas análises e projetos.

## Agendamento de Raspagem Automatizada

O repositório está configurado com uma **GitHub Action** que automaticamente raspa as notícias do dia anterior. O scraper é executado diariamente, garantindo que o dataset publicado no Hugging Face esteja sempre atualizado com as últimas notícias.

Todos os dias, o agendamento realiza as seguintes tarefas:

- Raspa os artigos de notícias publicados **ontem** de todas as agências gov.br listadas.
- Atualiza o dataset no Hugging Face com as novas notícias.

Essa configuração assegura que os dados permaneçam atualizados e acessíveis para todos os que utilizam o dataset.

## Contribuições

Contribuições para melhorar o **GovBR News Scraper** são muito bem-vindas! Caso encontre bugs, tenha sugestões de melhorias ou queira adicionar novas funcionalidades, sinta-se à vontade para abrir uma *issue* ou enviar um *pull request*.

Estamos sempre abertos a contribuições que possam melhorar o projeto!
