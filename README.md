# GovBR News Scraper

## Introdução

O **GovBR News Scraper** é uma ferramenta experimental desenvolvida pelo Ministério da Gestão e Inovação em Serviços Públicos (MGI) para coletar e organizar notícias de sites de agências governamentais no domínio gov.br. O objetivo é facilitar o monitoramento e a análise dessas publicações, extraindo metadados relevantes (título, data, categoria, conteúdo, etc.) e disponibilizando-os em formato estruturado. A raspagem é atualizada diariamente, tornando o serviço útil para pesquisadores, jornalistas e desenvolvedores que buscam acompanhar as últimas notícias governamentais.

---

## Dados Disponíveis

Os dados extraídos são publicados diariamente no [Hugging Face Hub](https://huggingface.co/datasets/nitaibezerra/govbrnews), em dois formatos: **dataset estruturado** (compatível com a biblioteca `datasets`) e **arquivos CSV**.

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
   - `published_at`: Data de publicação da notícia (apenas data, mantido por compatibilidade).
   - `published_datetime`: Data e hora completa de publicação da notícia (ISO 8601 com timezone UTC-3).
   - `updated_datetime`: Data e hora de atualização da notícia, quando disponível (ISO 8601 com timezone UTC-3).
   - `title`: Título da notícia.
   - `url`: URL da notícia original.
   - `image`: Link para a imagem principal da notícia.
   - `category`: Categoria da notícia (se disponível).
   - `tags`: Lista de tags associadas à notícia (se disponíveis).
   - `content`: Conteúdo completo da notícia em formato Markdown.
   - `extracted_at`: Data e hora em que a notícia foi extraída.

   **Nota sobre timestamps:** A partir de novembro de 2025, o dataset inclui `published_datetime` e `updated_datetime` com informações completas de data e hora (timezone UTC-3). A coluna `published_at` (apenas data) é mantida para compatibilidade com sistemas existentes. Notícias coletadas antes desta atualização terão `None` nestes novos campos.

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

## Dashboard Interativo

Para facilitar a exploração dos dados, disponibilizamos um **dashboard interativo** que permite a visualização e análise básica das notícias coletadas. Este recurso é útil para obter insights rápidos e compreender tendências nas publicações governamentais. Você pode acessar o dashboard através do seguinte link: [Dashboard Interativo](https://huggingface.co/spaces/nitaibezerra/govbrnews)

![image](https://github.com/user-attachments/assets/723870ec-2c73-4515-9309-b0ed997664ad)

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
