# GovBR News PostgreSQL Server

Este diretório contém os arquivos necessários para criar um servidor PostgreSQL que automaticamente baixa e disponibiliza o dataset de notícias governamentais brasileiras do HuggingFace.

## Visão Geral

O servidor PostgreSQL criado por este container:

1. **Baixa automaticamente** o dataset `nitaibezerra/govbrnews` do HuggingFace
2. **Cria uma estrutura de tabelas** otimizada para consultas
3. **Popula o banco de dados** com todas as notícias do dataset
4. **Expõe o PostgreSQL** na porta 5432 para acesso externo
5. **Mantém os dados persistentes** através de volumes Docker

## Arquivos Incluídos

- `Dockerfile` - Imagem PostgreSQL customizada com Python e dependências HuggingFace
- `requirements.txt` - Dependências Python necessárias
- `init-db.py` - Script Python que baixa o dataset e popula o banco
- `init-db.sh` - Script shell que orquestra a inicialização
- `README.md` - Este arquivo de documentação

## Estrutura do Banco de Dados

### Tabela: `news`

| Coluna | Tipo | Descrição |
|--------|------|-----------|
| `id` | SERIAL PRIMARY KEY | ID sequencial auto-incrementado |
| `unique_id` | VARCHAR(255) UNIQUE | Identificador único da notícia |
| `agency` | VARCHAR(255) | Agência governamental que publicou |
| `published_at` | TIMESTAMP | Data de publicação da notícia |
| `title` | TEXT | Título da notícia |
| `url` | TEXT | URL original da notícia |
| `image` | TEXT | URL da imagem principal |
| `category` | VARCHAR(255) | Categoria da notícia |
| `tags` | TEXT[] | Array de tags associadas |
| `content` | TEXT | Conteúdo completo em Markdown |
| `extracted_at` | TIMESTAMP | Data de extração dos dados |
| `created_at` | TIMESTAMP | Data de inserção no banco |

### Índices Criados

- `idx_news_agency` - Índice na coluna `agency`
- `idx_news_published_at` - Índice na coluna `published_at`
- `idx_news_unique_id` - Índice na coluna `unique_id`
- `idx_news_category` - Índice na coluna `category`

## Como Usar

### 1. Construir a Imagem Docker

```bash
# A partir do diretório raiz do projeto govbrnews
cd docker
docker build -t govbrnews-postgres .
```

### 2. Executar o Container

#### Opção A: Execução Simples (dados temporários)

```bash
docker run -d \
  --name govbrnews-db \
  -p 5432:5432 \
  -e POSTGRES_PASSWORD=postgres \
  govbrnews-postgres
```

#### Opção B: Execução com Volume Persistente (recomendado)

```bash
# Criar um volume para persistir os dados
docker volume create govbrnews-data

# Executar o container com volume persistente
docker run -d \
  --name govbrnews-db \
  -p 5432:5432 \
  -e POSTGRES_PASSWORD=postgres \
  -v govbrnews-data:/var/lib/postgresql/data \
  govbrnews-postgres

# Se a porta 5432 estiver em uso, use a porta 5433:
docker run -d \
  --name govbrnews-db \
  -p 5433:5432 \
  -e POSTGRES_PASSWORD=postgres \
  -v govbrnews-data:/var/lib/postgresql/data \
  govbrnews-postgres
```

#### Opção C: Usando Docker Compose

Crie um arquivo `docker-compose.yml`:

```yaml
version: '3.8'

services:
  govbrnews-postgres:
    build: .
    container_name: govbrnews-db
    ports:
      - "5432:5432"
    environment:
      - POSTGRES_DB=govbrnews
      - POSTGRES_USER=postgres
      - POSTGRES_PASSWORD=postgres
    volumes:
      - govbrnews_data:/var/lib/postgresql/data
    restart: unless-stopped

volumes:
  govbrnews_data:
```

Execute com:

```bash
docker-compose up -d
```

### 3. Conectar ao Banco de Dados

#### Usando psql (linha de comando)

```bash
# Conectar diretamente no container
docker exec -it govbrnews-db psql -U postgres -d govbrnews

# Ou conectar externamente (se tiver psql instalado)
PGPASSWORD=postgres psql -h localhost -p 5432 -U postgres -d govbrnews

# Se a porta 5432 estiver em uso (ex: Cursor, PostgreSQL local), use a porta 5433:
PGPASSWORD=postgres psql -h localhost -p 5433 -U postgres -d govbrnews
```

#### Usando Python

```python
import psycopg2
import pandas as pd

# Configuração de conexão
conn = psycopg2.connect(
    host="localhost",
    port=5432,
    database="govbrnews",
    user="postgres",
    password="postgres"
)

# Exemplo de consulta
query = """
SELECT agency, COUNT(*) as total_news
FROM news
GROUP BY agency
ORDER BY total_news DESC;
"""

df = pd.read_sql(query, conn)
print(df)

conn.close()
```

#### Usando ferramentas GUI

Você pode conectar usando qualquer cliente PostgreSQL:

- **DBeaver**: Host: localhost, Port: 5432, Database: govbrnews
- **pgAdmin**: mesmo setup
- **Postico** (macOS): mesmo setup

**Credenciais padrão:**
- Host: `localhost`
- Port: `5432` (ou `5433` se houver conflito de porta)
- Database: `govbrnews`
- Username: `postgres`
- Password: `postgres`

## Exemplos de Consultas

### 1. Contar notícias por agência

```sql
SELECT agency, COUNT(*) as total_news
FROM news
WHERE agency IS NOT NULL
GROUP BY agency
ORDER BY total_news DESC;
```

### 2. Notícias mais recentes

```sql
SELECT title, agency, published_at, url
FROM news
WHERE published_at IS NOT NULL
ORDER BY published_at DESC
LIMIT 10;
```

### 3. Buscar notícias por palavra-chave

```sql
SELECT title, agency, published_at, url
FROM news
WHERE title ILIKE '%saúde%'
   OR content ILIKE '%saúde%'
ORDER BY published_at DESC;
```

### 4. Notícias por período

```sql
SELECT COUNT(*) as total_news, agency
FROM news
WHERE published_at BETWEEN '2024-01-01' AND '2024-12-31'
GROUP BY agency
ORDER BY total_news DESC;
```

### 5. Estatísticas gerais

```sql
SELECT
    COUNT(*) as total_news,
    COUNT(DISTINCT agency) as total_agencies,
    MIN(published_at) as oldest_news,
    MAX(published_at) as newest_news
FROM news;
```

## Monitoramento e Logs

### Verificar logs do container

```bash
# Ver logs em tempo real
docker logs -f govbrnews-db

# Ver logs da inicialização
docker logs govbrnews-db | grep -E "(initialization|Download|Database)"
```

### Verificar status da inicialização

```bash
# Conectar e verificar se os dados foram carregados (dentro do container)
docker exec -it govbrnews-db psql -U postgres -d govbrnews -c "SELECT COUNT(*) FROM news;"

# Ou conectar externamente (lembre-se de usar PGPASSWORD e a porta correta)
PGPASSWORD=postgres psql -h localhost -p 5432 -U postgres -d govbrnews -c "SELECT COUNT(*) FROM news;"

# Se usando porta 5433:
PGPASSWORD=postgres psql -h localhost -p 5433 -U postgres -d govbrnews -c "SELECT COUNT(*) FROM news;"
```

## Configurações Avançadas

### Variáveis de Ambiente

Você pode customizar o comportamento através de variáveis de ambiente:

```bash
docker run -d \
  --name govbrnews-db \
  -p 5432:5432 \
  -e POSTGRES_DB=meu_banco \
  -e POSTGRES_USER=meu_usuario \
  -e POSTGRES_PASSWORD=minha_senha \
  govbrnews-postgres
```

### Backup e Restore

#### Fazer backup

```bash
docker exec govbrnews-db pg_dump -U postgres govbrnews > backup_govbrnews.sql
```

#### Restaurar backup

```bash
# Primeiro, pare o container existente
docker stop govbrnews-db
docker rm govbrnews-db

# Inicie um novo container
docker run -d --name govbrnews-db -p 5432:5432 -e POSTGRES_PASSWORD=postgres govbrnews-postgres

# Aguarde a inicialização e restaure
sleep 30
cat backup_govbrnews.sql | docker exec -i govbrnews-db psql -U postgres -d govbrnews
```

## Solução de Problemas

### Container não inicia

1. Verifique se a porta 5432 não está em uso:
   ```bash
   lsof -i :5432
   ```

2. Se a porta 5432 estiver em uso (comum com Cursor ou PostgreSQL local), use a porta 5433:
   ```bash
   docker run -d --name govbrnews-db -p 5433:5432 -e POSTGRES_PASSWORD=postgres govbrnews-postgres
   ```

3. Verifique os logs:
   ```bash
   docker logs govbrnews-db
   ```

### Dataset não foi carregado

1. Verifique se há conectividade com a internet no container
2. Verifique os logs de inicialização:
   ```bash
   docker logs govbrnews-db | grep -i "download\|error\|dataset"
   ```

### Performance lenta

1. Considere aumentar a memória disponível para o container:
   ```bash
   docker run -d --name govbrnews-db -p 5432:5432 -m 2g govbrnews-postgres
   ```

2. Verifique se os índices foram criados:
   ```sql
   SELECT indexname, tablename FROM pg_indexes WHERE tablename = 'news';
   ```

## Atualizações do Dataset

O dataset é baixado apenas durante a inicialização do container. Para obter dados atualizados:

1. **Pare e remova o container atual:**
   ```bash
   docker stop govbrnews-db
   docker rm govbrnews-db
   ```

2. **Construa uma nova imagem (opcional, se houve mudanças):**
   ```bash
   docker build -t govbrnews-postgres .
   ```

3. **Execute um novo container:**
   ```bash
   docker run -d --name govbrnews-db -p 5432:5432 -v govbrnews-data:/var/lib/postgresql/data govbrnews-postgres
   ```

## Contribuindo

Para contribuir com melhorias neste setup PostgreSQL:

1. Faça suas modificações nos arquivos do diretório `docker/`
2. Teste localmente construindo e executando a imagem
3. Documente suas mudanças neste README
4. Submeta um pull request

## Suporte

Para questões relacionadas ao:
- **Dataset**: Consulte o [repositório principal do govbrnews](https://huggingface.co/datasets/nitaibezerra/govbrnews)
- **Configuração PostgreSQL**: Consulte a [documentação oficial do PostgreSQL](https://www.postgresql.org/docs/)
- **Docker**: Consulte a [documentação do Docker](https://docs.docker.com/)

## Licença

Este projeto segue a mesma licença do projeto principal govbrnews.
