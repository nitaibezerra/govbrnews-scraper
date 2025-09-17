# GovBR News PostgreSQL Server

Este diretório contém os arquivos necessários para criar um servidor PostgreSQL que automaticamente baixa e disponibiliza o dataset de notícias governamentais brasileiras do HuggingFace.

## 🚀 Início Rápido

```bash
# 1. Navegue para o diretório
cd docker-postgres

# 2. Execute o script automatizado
./run-postgres-server.sh

# 3. Aguarde ~90 segundos para setup completo
# 4. Use as credenciais: postgres/postgres na porta 5433
```

**Pronto!** O servidor PostgreSQL estará rodando com 289k+ notícias carregadas e pronto para consultas.

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
- `run-postgres-server.sh` - **Script principal** para gerenciar o servidor (build, run, cleanup, refresh)
- `README.md` - Este arquivo de documentação

## Estrutura do Banco de Dados

### Tabela: `news`

| Coluna | Tipo | Descrição |
|--------|------|-----------|
| `id` | SERIAL PRIMARY KEY | ID sequencial auto-incrementado |
| `unique_id` | TEXT UNIQUE | Identificador único da notícia |
| `agency` | TEXT | Agência governamental que publicou |
| `published_at` | TIMESTAMP | Data de publicação da notícia |
| `title` | TEXT | Título da notícia |
| `url` | TEXT | URL original da notícia |
| `image` | TEXT | URL da imagem principal |
| `category` | TEXT | Categoria da notícia |
| `tags` | TEXT[] | Array de tags associadas |
| `content` | TEXT | Conteúdo completo em Markdown |
| `extracted_at` | TIMESTAMP | Data de extração dos dados |
| `theme_1_level_1` | TEXT | Tema principal da notícia (nível 1) |
| `created_at` | TIMESTAMP | Data de inserção no banco |

### Índices Criados

- `idx_news_agency` - Índice na coluna `agency`
- `idx_news_published_at` - Índice na coluna `published_at`
- `idx_news_unique_id` - Índice na coluna `unique_id`
- `idx_news_category` - Índice na coluna `category`
- `idx_news_theme_1_level_1` - Índice na coluna `theme_1_level_1`

## Como Usar

### 🚀 Opção Recomendada: Script Automatizado

A maneira mais fácil de usar este servidor PostgreSQL é através do script automatizado que gerencia todo o processo:

```bash
# A partir do diretório raiz do projeto govbrnews
cd docker-postgres

# Iniciar o servidor PostgreSQL (automático: build + run + test)
./run-postgres-server.sh

# Ver todas as opções disponíveis
./run-postgres-server.sh help
```

### 📋 Comandos do Script

| Comando | Descrição | Tempo | Uso |
|---------|-----------|-------|-----|
| `./run-postgres-server.sh` | Setup completo (build + run + test) | ~90s | Primeira execução |
| `./run-postgres-server.sh refresh` | Atualizar dataset (sem rebuild) | ~60s | Atualizações de dados |
| `./run-postgres-server.sh cleanup` | Limpeza completa (container + imagem + volume) | ~5s | Reinício do zero |
| `./run-postgres-server.sh help` | Mostrar ajuda e exemplos | <1s | Consultar comandos |

### 🔧 Opção Manual: Docker Direto

Se preferir controlar manualmente cada etapa:

#### 1. Construir a Imagem Docker

```bash
# A partir do diretório raiz do projeto govbrnews
cd docker-postgres
docker build -t govbrnews-postgres .
```

#### 2. Executar o Container

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

## 🔄 Gerenciamento com Script Automatizado

O script `run-postgres-server.sh` oferece comandos avançados para gerenciar o servidor:

### 🧹 Limpeza Completa
```bash
./run-postgres-server.sh cleanup
```
- **Remove**: Container + Imagem + Volume persistente
- **Quando usar**: Problemas no container, corrupção de dados, ou restart completo
- **Resultado**: Estado limpo para iniciar do zero

### 🔄 Atualização do Dataset
```bash
./run-postgres-server.sh refresh
```
- **Atualiza**: Apenas os dados (baixa dataset mais recente do HuggingFace)
- **Preserva**: Container, configurações, e estrutura do banco
- **Quando usar**: Obter notícias mais recentes sem perder configurações
- **Requisito**: Container deve estar rodando

### 📖 Ajuda e Exemplos
```bash
./run-postgres-server.sh help
```
- Mostra todos os comandos disponíveis
- Inclui exemplos de uso
- Documenta casos de uso para cada comando

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

### 6. Consultar por tema

```sql
SELECT theme_1_level_1, COUNT(*) as total_news
FROM news
WHERE theme_1_level_1 IS NOT NULL
GROUP BY theme_1_level_1
ORDER BY total_news DESC;
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

## 🛠️ Solução de Problemas

### Problemas com o Script Automatizado

#### Comando `refresh` falha
1. **Verifique se o container está rodando:**
   ```bash
   docker ps | grep govbrnews-db
   ```

2. **Se não estiver rodando, inicie o servidor:**
   ```bash
   ./run-postgres-server.sh
   ```

3. **Se o refresh continuar falhando, faça limpeza completa:**
   ```bash
   ./run-postgres-server.sh cleanup
   ./run-postgres-server.sh
   ```

#### Erro "Dockerfile not found"
- Certifique-se de estar no diretório `docker-postgres/`:
  ```bash
  cd docker-postgres
  ./run-postgres-server.sh
  ```

#### Container não inicia após cleanup
1. **Verifique se o Docker está rodando:**
   ```bash
   docker info
   ```

2. **Verifique logs do script:**
   ```bash
   ./run-postgres-server.sh help  # Para ver comandos disponíveis
   ```

### Problemas Gerais do Container

#### Container não inicia

1. Verifique se a porta 5432 não está em uso:
   ```bash
   lsof -i :5432
   ```

2. Se a porta 5432 estiver em uso (comum com Cursor ou PostgreSQL local), use a porta 5433:
   ```bash
   docker run -d --name govbrnews-db -p 5433:5432 -e POSTGRES_PASSWORD=postgres govbrnews-postgres
   ```
   
   **Ou use o script que detecta automaticamente:**
   ```bash
   ./run-postgres-server.sh  # Detecta conflito e usa porta 5433
   ```

3. Verifique os logs:
   ```bash
   docker logs govbrnews-db
   ```

#### Dataset não foi carregado

1. Verifique se há conectividade com a internet no container
2. Verifique os logs de inicialização:
   ```bash
   docker logs govbrnews-db | grep -i "download\|error\|dataset"
   ```

3. **Para forçar reload do dataset:**
   ```bash
   ./run-postgres-server.sh refresh
   ```

#### Performance lenta

1. Considere aumentar a memória disponível para o container:
   ```bash
   docker run -d --name govbrnews-db -p 5432:5432 -m 2g govbrnews-postgres
   ```

2. Verifique se os índices foram criados:
   ```sql
   SELECT indexname, tablename FROM pg_indexes WHERE tablename = 'news';
   ```

### 🆘 Solução Universal
Em caso de problemas persistentes:

```bash
# Limpeza completa e restart
./run-postgres-server.sh cleanup
./run-postgres-server.sh

# Isso resolve a maioria dos problemas
```

## 🔄 Atualizações do Dataset

### Método Recomendado: Refresh Automático
Para atualizar apenas os dados (mais rápido):

```bash
./run-postgres-server.sh refresh
```

**Vantagens:**
- ⚡ 33% mais rápido (~60s vs ~90s)
- 🔒 Preserva configurações e conexões
- 📊 Mantém estrutura do banco
- ✅ Verifica pré-requisitos automaticamente

### Método Alternativo: Rebuild Completo
Para atualizações com mudanças na estrutura:

1. **Limpeza completa:**
   ```bash
   ./run-postgres-server.sh cleanup
   ```

2. **Restart do zero:**
   ```bash
   ./run-postgres-server.sh
   ```

### Método Manual (Docker)
Se estiver usando Docker manualmente:

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

1. Faça suas modificações nos arquivos do diretório `docker-postgres/`
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
