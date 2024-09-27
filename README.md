# GovBR News Scraper

## Introdução

O **GovBR News Scraper** é uma ferramenta automatizada, em fase beta, desenvolvida pelo **Ministério da Gestão e Inovação em Serviços Públicos (MGI)**. Este projeto experimental visa coletar notícias de vários sites de agências governamentais dentro do domínio gov.br, facilitando o monitoramento e o arquivamento de dados de notícias governamentais. A ferramenta faz a raspagem e extração de artigos de notícias, incluindo metadados como título, data, categoria e conteúdo, e os armazena em um formato JSON estruturado.

A ferramenta é executada de forma programada, raspando as notícias do dia anterior e atualizando o repositório automaticamente. Os dados são armazenados na pasta `raw_extractions`, facilitando o acompanhamento das últimas atualizações relacionadas ao governo. Este projeto é útil para pesquisadores, jornalistas e desenvolvedores interessados em monitorar e analisar notícias governamentais.

Além disso, o projeto gera um arquivo [CSV](#csv-consolidado) consolidado de todas as notícias, permitindo um download e manipulação mais simples do dataset.

## Como Usar

Para utilizar o **GovBR News Scraper**, siga estes passos:

1. **Clone o repositório:**

    ```bash
    git clone https://github.com/seu-usuario/govbr-news-scraper.git
    cd govbr-news-scraper
    ```

2. **Instale as dependências:**

    Certifique-se de ter o Python 3.x instalado. Instale as bibliotecas necessárias executando:

    ```bash
    pip install -r requirements.txt
    ```

3. **Execute o scraper:**

    O scraper permite definir uma data específica até a qual as notícias serão raspadas. Para rodar o scraper, use o seguinte comando:

    ```bash
    python news_scraper.py YYYY-MM-DD
    ```

    Substitua `YYYY-MM-DD` pela data desejada. Essa data define o limite mínimo; o scraper coletará notícias publicadas nessa data ou posteriormente.

## Pasta Raw Extractions

A pasta `raw_extractions` contém todos os dados de notícias raspados, organizados por agência e data. Dentro dessa pasta, você encontrará:

- **Estrutura de Pastas:** Cada agência possui sua própria pasta, e dentro de cada pasta há arquivos JSON nomeados de acordo com a data de publicação das notícias.
- **Intervalo de Datas:** A pasta inclui todos os dados coletados desde **2024-01-01**, com os artigos organizados cronologicamente.

Os dados nesses arquivos JSON incluem:
- Título do artigo
- URL do artigo de notícias
- Data de publicação
- Categoria da notícia (se disponível)
- Tags (se disponíveis)
- Conteúdo completo do artigo

Esses dados são úteis para análise de longo prazo ou arquivamento de notícias de várias agências governamentais.

## CSV Consolidado

Para facilitar o download e a manipulação do dataset, o projeto gera um arquivo CSV consolidado com todas as notícias extraídas até o momento. O arquivo CSV contém os seguintes campos:
- Agência
- Título
- URL
- Data de publicação
- Categoria
- Tags (convertidas para uma string separada por vírgulas)
- Conteúdo completo

O arquivo CSV consolidado é salvo em [`raw_extractions/full_history_since_20240101.csv`](https://github.com/nitaibezerra/govbrnews-scraper/blob/main/raw_extractions/full_history_since_20240101.csv), e uma versão compactada também está disponível em [`raw_extractions/full_history_since_20240101.zip`](https://github.com/nitaibezerra/govbrnews-scraper/blob/main/raw_extractions/full_history_since_20240101.zip).

## Agendamento de Raspagem Automatizada

O repositório está configurado com uma **GitHub Action** que automaticamente raspa as notícias do dia anterior. O scraper é executado diariamente, garantindo que a pasta `raw_extractions` esteja sempre atualizada com as últimas notícias.

Todos os dias, o agendamento realiza as seguintes tarefas:
- Raspa os artigos de notícias publicados **ontem** de todas as agências gov.br listadas.
- Salva as notícias extraídas na pasta `raw_extractions`.
- Consolida todos os dados em um arquivo CSV e compacta em ZIP.
- Faz o commit e envia as atualizações automaticamente para o repositório.

Essa configuração garante que os dados permaneçam atualizados e acessíveis para todos os que utilizam o repositório.

## Contribuições

Contribuições para melhorar o **GovBR News Scraper** são muito bem-vindas! Existem várias formas de contribuir:

1. **Sugestões de Código e Correções:**
   - Caso encontre bugs, tenha sugestões de melhorias ou queira adicionar novas funcionalidades, sinta-se à vontade para abrir uma *issue* ou enviar um *pull request*.

2. **Adição de URLs de Agências:**
   - O arquivo `site_urls.yaml` contém o mapeamento de todos os URLs de sites governamentais que o scraper utiliza para coletar notícias. No entanto, pode haver sites que foram omitidos ou que ainda não estão incluídos.
   - Você pode contribuir encontrando e adicionando novos URLs de sites de agências governamentais ao arquivo `site_urls.yaml`. Isso ajudará a ampliar a cobertura do scraper.

   Para adicionar novos URLs:
   - Edite o arquivo `site_urls.yaml` e adicione a nova agência e seu respectivo URL no formato correto.
   - Envie um *pull request* com suas alterações para que possamos revisar e incorporar as novas agências.

Estamos sempre abertos a contribuições que possam melhorar o projeto!
