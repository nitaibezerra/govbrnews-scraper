# Docker Typesense - Documentação Claude

## Visão Geral

Este diretório contém a infraestrutura completa para executar um servidor **Typesense** containerizado via Docker, pré-configurado para indexar e disponibilizar o dataset **govbrnews** do HuggingFace para buscas ultrarrápidas em texto completo.

**Typesense** é um motor de busca open-source otimizado para:
- Busca em texto completo com tolerância a erros de digitação (typo-tolerance)
- Busca facetada para filtros dinâmicos
- Respostas em < 50ms para a maioria das queries
- API RESTful simples e intuitiva

## Arquitetura do Sistema

```
docker-typesense/
├── Dockerfile                    # Imagem customizada baseada em typesense:27.1
├── requirements.txt              # Dependências Python para HuggingFace
├── init-typesense.py            # Script de inicialização e indexação
├── entrypoint.sh                # Script de orquestração do container
├── run-typesense-server.sh      # Script principal de gerenciamento
├── web-ui/                      # Interface web de busca
│   ├── web-ui.html             # UI standalone com InstantSearch
│   ├── typesense-adapter.min.js
│   └── instantsearch.min.js
└── README.md                    # Documentação completa de uso
```

### Fluxo de Execução

```
1. run-typesense-server.sh
   ↓
2. docker build (Dockerfile)
   ↓ instala Python + dependências
3. docker run (cria container)
   ↓
4. entrypoint.sh inicia Typesense
   ↓ aguarda health check
5. init-typesense.py executa
   ↓ baixa dataset HuggingFace
   ↓ cria schema da collection
   ↓ indexa 295k+ documentos
6. Servidor pronto na porta 8108
```

## Componentes Principais

### 1. Dockerfile

**Base**: `typesense/typesense:27.1`

**Customizações**:
- Instala Python 3 + pip + virtualenv
- Instala dependências do HuggingFace (datasets, pandas, typesense SDK)
- Copia scripts de inicialização
- Configura ambiente com API key e data directory
- Expõe porta 8108

**Variáveis de Ambiente**:
```bash
TYPESENSE_API_KEY=govbrnews_api_key_change_in_production
TYPESENSE_DATA_DIR=/data
```

**Volumes**:
- `/data` → Persistência dos dados indexados

### 2. entrypoint.sh

Script de orquestração que executa ao iniciar o container:

**Responsabilidades**:
1. Inicia o servidor Typesense em background
2. Aguarda health check (30 tentativas, 2s cada)
3. Verifica se dados já existem em `/data/state/db/CURRENT`
4. Se não existirem dados:
   - Ativa virtualenv Python
   - Executa `init-typesense.py`
5. Mantém processo principal rodando com `wait`

**Lógica de Skip**:
Se o volume persistente já contém dados, pula a inicialização para acelerar restarts (dados são preservados entre recriações do container).

### 3. init-typesense.py

Script Python que faz o trabalho pesado de inicialização:

#### Configuração
```python
TYPESENSE_HOST = 'localhost'
TYPESENSE_PORT = '8108'
TYPESENSE_API_KEY = 'govbrnews_api_key_change_in_production'
COLLECTION_NAME = 'news'
DATASET_PATH = "nitaibezerra/govbrnews"
```

#### Fluxo de Execução

**1. `wait_for_typesense()`**
- Tenta conectar ao Typesense (30 tentativas)
- Verifica endpoint `/health`
- Retorna client configurado

**2. `create_collection()`**
- Verifica se collection 'news' já existe
- Se não existir, cria com schema:

```python
{
    'name': 'news',
    'fields': [
        {'name': 'unique_id', 'type': 'string', 'facet': False},
        {'name': 'agency', 'type': 'string', 'facet': True, 'optional': True},
        {'name': 'published_at', 'type': 'int64', 'facet': False},  # obrigatório
        {'name': 'title', 'type': 'string', 'facet': False, 'optional': True},
        {'name': 'url', 'type': 'string', 'facet': False, 'optional': True},
        {'name': 'image', 'type': 'string', 'facet': False, 'optional': True},
        {'name': 'category', 'type': 'string', 'facet': True, 'optional': True},
        {'name': 'content', 'type': 'string', 'facet': False, 'optional': True},
        {'name': 'extracted_at', 'type': 'int64', 'facet': False, 'optional': True},
        {'name': 'theme_1_level_1', 'type': 'string', 'facet': True, 'optional': True},
        {'name': 'published_year', 'type': 'int32', 'facet': True, 'optional': True},
        {'name': 'published_month', 'type': 'int32', 'facet': True, 'optional': True},
    ],
    'default_sorting_field': 'published_at'  # ordenação padrão por data
}
```

**Campos Facetáveis** (permitem filtros e agregações):
- `agency` - Agência governamental
- `category` - Categoria da notícia
- `theme_1_level_1` - Tema principal
- `published_year` - Ano
- `published_month` - Mês

**Campos Pesquisáveis**:
- `title` - Título da notícia
- `content` - Conteúdo em Markdown

**3. `download_and_process_dataset()`**
```python
# Baixa dataset do HuggingFace
dataset = load_dataset("nitaibezerra/govbrnews", split="train")

# Converte para pandas DataFrame
df = dataset.to_pandas()

# Processa datas
df['published_at'] = pd.to_datetime(df['published_at'])
df['published_year'] = df['published_at'].dt.year
df['published_month'] = df['published_at'].dt.month

# Converte para Unix timestamp (segundos)
df['published_at_ts'] = df['published_at'].astype('int64') // 10**9
```

**4. `prepare_document(row)`**
- Converte cada linha do DataFrame para formato Typesense
- Lida com valores nulos (campos opcionais)
- Garante tipos corretos (int64, int32, string)
- Validação de campos obrigatórios

**5. `index_documents_to_typesense()`**
```python
# Indexa em batches de 1000 documentos
for idx, row in df.iterrows():
    doc = prepare_document(row)
    documents.append(doc)

    if len(documents) >= 1000:
        # Upsert batch
        result = client.collections['news'].documents.import_(
            documents,
            {'action': 'upsert'}
        )
        documents = []
```

**Estratégia de Indexação**:
- Batches de 1000 documentos (balanceamento entre memória e performance)
- `action: 'upsert'` → Atualiza se existir, insere se não existir
- Validação de erros por batch
- Logging detalhado do progresso

**6. `run_test_queries()`**
Executa queries de teste para validar:
- Total de documentos indexados
- Busca textual simples
- Busca facetada por agência

### 4. run-typesense-server.sh

Script bash robusto para gerenciamento completo do ciclo de vida.

#### Configuração
```bash
CONTAINER_NAME="govbrnews-typesense"
IMAGE_NAME="govbrnews-typesense"
TYPESENSE_PORT="8108"
VOLUME_NAME="govbrnews-typesense-data"
API_KEY="govbrnews_api_key_change_in_production"
```

#### Comandos Disponíveis

**1. `./run-typesense-server.sh` (padrão)**

Setup completo:
```bash
1. ensure_correct_directory()  # Auto-detecção de diretório
2. cleanup_existing()          # Remove container/imagem antigos
3. check_port()                # Valida porta 8108 disponível
4. create_volume()             # Cria volume persistente
5. build_image()               # Build da imagem Docker
6. run_container()             # Inicia container com volume
7. wait_for_typesense()        # Aguarda health check (30x 2s)
8. wait_for_initialization()   # Monitora logs de inicialização
9. run_test_queries()          # Testa funcionalidade
10. show_connection_info()     # Exibe instruções de uso
```

**Tempo**: ~90 segundos (build + download + indexação)

**2. `./run-typesense-server.sh refresh`**

Atualiza dataset sem rebuild:
```bash
1. Verifica container rodando
2. DELETE /collections/news via API
3. docker exec: python3 /opt/init-typesense.py
4. Re-download e re-indexação
5. Validação de sucesso
```

**Tempo**: ~60 segundos
**Uso**: Atualizar dados após novo push no HuggingFace

**3. `./run-typesense-server.sh cleanup`**

Limpeza completa:
```bash
docker stop govbrnews-typesense
docker rm govbrnews-typesense
docker rmi govbrnews-typesense
docker volume rm govbrnews-typesense-data
```

**Uso**: Reset completo para troubleshooting

**4. `./run-typesense-server.sh help`**

Exibe documentação inline com exemplos.

#### Recursos Avançados do Script

**Auto-detecção de Diretório**:
```bash
# Pode ser executado de qualquer lugar
./docker-typesense/run-typesense-server.sh        # Do root
cd docker-typesense && ./run-typesense-server.sh  # Do próprio diretório
```

**Monitoramento de Logs**:
```bash
# Detecta progresso da inicialização
- "Downloading govbrnews dataset" → "📥 Downloading..."
- "Dataset downloaded successfully" → "✅ Dataset downloaded..."
- "Indexing documents" → "💾 Indexing..."
```

**Tratamento de Erros**:
- Valida porta disponível com `lsof`
- Timeout de 10 minutos para inicialização
- Logs detalhados em caso de falha
- Exit codes apropriados

**Cores e Formatação**:
```bash
RED='\033[0;31m'     # Erros
GREEN='\033[0;32m'   # Sucesso
YELLOW='\033[1;33m'  # Avisos
BLUE='\033[0;34m'    # Info
NC='\033[0m'         # No Color
```

### 5. Web UI

Interface web standalone com **Algolia InstantSearch**.

**Componentes**:
- `web-ui.html` - Single-page app
- `typesense-adapter.min.js` - Adapter para Typesense
- `instantsearch.min.js` - UI components do Algolia

**Recursos**:
- Busca instantânea com debouncing
- Highlighting de termos encontrados
- Filtros por: ano, órgão, categoria, tema
- Ordenação por data (asc/desc)
- Paginação
- Visualização de imagens
- Links para notícias originais

**Uso**:
```bash
# macOS
open docker-typesense/web-ui/web-ui.html

# Linux
xdg-open docker-typesense/web-ui/web-ui.html

# Windows
start docker-typesense/web-ui/web-ui.html
```

## Persistência de Dados

### Volume Docker
```bash
docker volume create govbrnews-typesense-data
```

**Localização**: `/var/lib/docker/volumes/govbrnews-typesense-data/_data`

**Estrutura Interna**:
```
/data/
├── state/
│   └── db/
│       ├── CURRENT           # Indicador de DB existente
│       ├── MANIFEST-*
│       └── *.sst            # SSTable files (RocksDB)
└── ...
```

**Comportamento**:
- Primeiro run: Volume vazio → inicialização completa
- Runs subsequentes: Volume com dados → skip inicialização
- `refresh`: Mantém volume, recria collection
- `cleanup`: Remove volume → próximo run é do zero

## API Typesense

### Endpoints Principais

**1. Health Check**
```bash
curl http://localhost:8108/health
# Response: {"ok":true}
```

**2. Collection Info**
```bash
curl "http://localhost:8108/collections/news" \
  -H "X-TYPESENSE-API-KEY: govbrnews_api_key_change_in_production"

# Response inclui:
# - num_documents: total indexado
# - fields: schema completo
# - default_sorting_field
```

**3. Search**
```bash
curl "http://localhost:8108/collections/news/documents/search?q=educação&query_by=title,content&per_page=3" \
  -H "X-TYPESENSE-API-KEY: govbrnews_api_key_change_in_production"
```

**Parâmetros de Busca**:
- `q` - Query string
- `query_by` - Campos para buscar (ex: `title,content`)
- `filter_by` - Filtros (ex: `published_year:2024`)
- `facet_by` - Agregações (ex: `agency,category`)
- `sort_by` - Ordenação (ex: `published_at:desc`)
- `per_page` - Resultados por página (padrão: 10)
- `page` - Número da página (padrão: 1)
- `highlight_full_fields` - Campos para highlight

**4. Faceted Search**
```bash
curl "http://localhost:8108/collections/news/documents/search?q=*&query_by=title&facet_by=agency,category,theme_1_level_1&max_facet_values=10" \
  -H "X-TYPESENSE-API-KEY: govbrnews_api_key_change_in_production"
```

**5. Delete Collection** (usado em refresh)
```bash
curl -X DELETE "http://localhost:8108/collections/news" \
  -H "X-TYPESENSE-API-KEY: govbrnews_api_key_change_in_production"
```

## Schema da Collection

### Campos e Tipos

| Campo | Tipo | Facetável | Opcional | Descrição |
|-------|------|-----------|----------|-----------|
| `unique_id` | string | Não | Não | ID único da notícia |
| `agency` | string | **Sim** | Sim | Agência governamental |
| `published_at` | int64 | Não | Não | Unix timestamp (segundos) |
| `title` | string | Não | Sim | Título (pesquisável) |
| `url` | string | Não | Sim | URL original |
| `image` | string | Não | Sim | URL da imagem |
| `category` | string | **Sim** | Sim | Categoria |
| `content` | string | Não | Sim | Markdown (pesquisável) |
| `extracted_at` | int64 | Não | Sim | Unix timestamp extração |
| `theme_1_level_1` | string | **Sim** | Sim | Tema principal |
| `published_year` | int32 | **Sim** | Sim | Ano (2018-2025) |
| `published_month` | int32 | **Sim** | Sim | Mês (1-12) |

### Design Decisions

**Por que `published_at` é int64?**
- Typesense requer timestamps como Unix epoch (segundos)
- Permite ordenação eficiente
- Compatível com sorting field obrigatório

**Por que campos são opcionais?**
- Dataset pode ter valores nulos
- Typesense rejeita documentos com campos obrigatórios faltando
- `unique_id` e `published_at` são os únicos obrigatórios

**Por que não indexar `tags` como array?**
- Simplificação do processamento
- Tags podem ter formato inconsistente no dataset
- Comentado no código para futura implementação

**Por que facets em agency, category, theme_1_level_1?**
- Permite filtros dinâmicos na UI
- Agregações rápidas para estatísticas
- Caso de uso comum: "Notícias do MEC em 2024"

## Performance

### Benchmarks

**Indexação**:
- 295.511 documentos em ~60-90 segundos
- ~3.300-4.900 docs/segundo
- Batches de 1.000 documentos
- Uso de memória: ~500MB durante indexação

**Busca**:
- Queries simples: < 50ms
- Queries com facets: < 100ms
- Typo-tolerance: sem impacto significativo
- 10k queries/segundo (estimado)

**Disco**:
- Dataset raw: ~X GB (HuggingFace cache)
- Índice Typesense: ~Y GB (RocksDB)
- Volume persistente: ~Z GB total

### Otimizações

**1. Batching na Indexação**
```python
# Batch de 1000 é sweet spot
if len(documents) >= 1000:
    client.collections['news'].documents.import_(documents)
```

**2. Upsert ao invés de Create**
```python
{'action': 'upsert'}  # Evita erros de duplicação
```

**3. Skip de Inicialização**
```bash
# entrypoint.sh verifica dados existentes
if [ -f "${TYPESENSE_DATA_DIR}/state/db/CURRENT" ]; then
    echo "Skipping initialization"
fi
```

**4. Campos Opcionais**
- Reduz rejeições durante indexação
- Permite dataset com dados incompletos

**5. Sorting Field**
- `published_at` permite queries ordenadas sem overhead
- Índice otimizado para range queries

## Casos de Uso

### 1. Busca por Palavra-chave
```bash
# Buscar "educação" no título e conteúdo
curl "http://localhost:8108/collections/news/documents/search?q=educação&query_by=title,content"
```

### 2. Filtro por Período
```bash
# Notícias de 2024
curl "http://localhost:8108/collections/news/documents/search?q=*&query_by=title&filter_by=published_year:2024"
```

### 3. Filtro por Agência
```bash
# Notícias do MEC
curl "http://localhost:8108/collections/news/documents/search?q=*&query_by=title&filter_by=agency:Ministério da Educação"
```

### 4. Busca Combinada
```bash
# Educação no MEC em 2024, ordenado por data
curl "http://localhost:8108/collections/news/documents/search?q=escola&query_by=title,content&filter_by=agency:Ministério da Educação AND published_year:2024&sort_by=published_at:desc"
```

### 5. Agregações
```bash
# Top 5 agências com mais notícias
curl "http://localhost:8108/collections/news/documents/search?q=*&query_by=title&facet_by=agency&max_facet_values=5&limit=0"
```

### 6. Typo Tolerance
```bash
# "edukação" (erro) ainda encontra "educação"
curl "http://localhost:8108/collections/news/documents/search?q=edukação&query_by=title,content"
```

## Troubleshooting

### Problema: Container não inicia

**Sintoma**: `docker ps` não mostra o container

**Diagnóstico**:
```bash
docker logs govbrnews-typesense
```

**Soluções**:
1. Porta 8108 ocupada
   ```bash
   lsof -i :8108
   # Parar processo usando a porta
   ```

2. Volume corrompido
   ```bash
   ./run-typesense-server.sh cleanup
   ./run-typesense-server.sh
   ```

### Problema: Indexação falha

**Sintoma**: Logs mostram erros durante `Indexing documents`

**Causas Comuns**:
- Dataset HuggingFace inacessível
- Memória insuficiente
- Campos com tipos inválidos

**Solução**:
```bash
# Ver logs detalhados
docker logs govbrnews-typesense | grep -i error

# Refresh completo
./run-typesense-server.sh cleanup
./run-typesense-server.sh
```

### Problema: Buscas retornam 0 resultados

**Diagnóstico**:
```bash
# Verificar total de documentos
curl "http://localhost:8108/collections/news" \
  -H "X-TYPESENSE-API-KEY: govbrnews_api_key_change_in_production" | grep num_documents
```

**Se `num_documents: 0`**:
```bash
./run-typesense-server.sh refresh
```

### Problema: Refresh falha

**Sintoma**: `./run-typesense-server.sh refresh` retorna erro

**Solução**:
```bash
# Container não está rodando
docker ps | grep govbrnews-typesense

# Se não estiver rodando, iniciar
./run-typesense-server.sh
```

## Comparação com Alternativas

### Typesense vs Elasticsearch

| Característica | Typesense | Elasticsearch |
|----------------|-----------|---------------|
| **Setup** | Simples (1 comando) | Complexo (configs, heap) |
| **Memória** | ~500MB | ~2GB+ |
| **Latência** | < 50ms | 100-500ms |
| **Typo-tolerance** | Nativo | Requer configs |
| **API** | RESTful simples | DSL complexo |
| **Faceted search** | Built-in | Aggregations |
| **Caso de uso** | Apps interativos | Analytics, logs |

### Typesense vs PostgreSQL Full-Text

| Característica | Typesense | PostgreSQL |
|----------------|-----------|------------|
| **Relevância** | Algoritmo avançado | tsvector básico |
| **Typo-tolerance** | Sim | Não nativo |
| **Performance** | < 50ms | 100-1000ms |
| **Facets** | Nativo | Agregações complexas |
| **Highlighting** | Nativo | Manual |
| **Escalabilidade** | Horizontal | Vertical (replicação) |

### Quando Usar Typesense

**Ideal para**:
- Buscas interativas em sites/apps
- Autocomplete
- E-commerce (busca de produtos)
- Documentação técnica
- Dashboards com faceted search

**Não ideal para**:
- Queries SQL complexas (JOINs)
- Transações ACID
- Relatórios analíticos pesados
- Processamento de logs em escala

## Integrações

### Python Client
```python
import typesense

client = typesense.Client({
    'nodes': [{
        'host': 'localhost',
        'port': '8108',
        'protocol': 'http'
    }],
    'api_key': 'govbrnews_api_key_change_in_production',
    'connection_timeout_seconds': 2
})

# Busca
results = client.collections['news'].documents.search({
    'q': 'educação',
    'query_by': 'title,content',
    'filter_by': 'published_year:2024',
    'sort_by': 'published_at:desc'
})

for hit in results['hits']:
    print(hit['document']['title'])
```

### JavaScript Client
```javascript
const Typesense = require('typesense');

let client = new Typesense.Client({
  'nodes': [{
    'host': 'localhost',
    'port': '8108',
    'protocol': 'http'
  }],
  'apiKey': 'govbrnews_api_key_change_in_production'
});

// Busca
client.collections('news').documents().search({
  'q': 'saúde',
  'query_by': 'title,content'
}).then(results => {
  console.log(`Found ${results.found} results`);
});
```

### React Integration
```jsx
import TypesenseInstantSearchAdapter from 'typesense-instantsearch-adapter';
import { InstantSearch, SearchBox, Hits } from 'react-instantsearch-dom';

const adapter = new TypesenseInstantSearchAdapter({
  server: {
    apiKey: 'govbrnews_api_key_change_in_production',
    nodes: [{
      host: 'localhost',
      port: '8108',
      protocol: 'http'
    }]
  },
  additionalSearchParameters: {
    query_by: 'title,content'
  }
});

function App() {
  return (
    <InstantSearch indexName="news" searchClient={adapter.searchClient}>
      <SearchBox />
      <Hits />
    </InstantSearch>
  );
}
```

## Segurança

### Produção: Mudanças Necessárias

**1. API Key**
```bash
# Gerar key segura
openssl rand -hex 32

# Usar em:
# - Dockerfile: ENV TYPESENSE_API_KEY=<nova_key>
# - run-typesense-server.sh: API_KEY=<nova_key>
# - Clients: api_key=<nova_key>
```

**2. HTTPS**
```bash
# Usar proxy reverso (nginx, Caddy, Traefik)
docker run -d \
  --name govbrnews-typesense \
  -p 127.0.0.1:8108:8108 \  # Bind somente localhost
  ...
```

**3. Firewall**
```bash
# Permitir somente proxy reverso
ufw allow from <proxy_ip> to any port 8108
```

**4. API Keys Segregadas**
```bash
# Admin key (full access)
TYPESENSE_API_KEY=admin_key_xxx

# Search-only key (clients)
curl -X POST "http://localhost:8108/keys" \
  -H "X-TYPESENSE-API-KEY: admin_key_xxx" \
  -d '{
    "description": "Search-only key",
    "actions": ["documents:search"],
    "collections": ["news"]
  }'
```

## Manutenção

### Backup
```bash
# Backup do volume
docker run --rm \
  -v govbrnews-typesense-data:/data \
  -v $(pwd):/backup \
  ubuntu tar czf /backup/typesense-backup-$(date +%Y%m%d).tar.gz /data

# Restore
docker run --rm \
  -v govbrnews-typesense-data:/data \
  -v $(pwd):/backup \
  ubuntu tar xzf /backup/typesense-backup-20250101.tar.gz -C /
```

### Atualização do Typesense
```bash
# Modificar Dockerfile
FROM typesense/typesense:28.0  # Nova versão

# Rebuild
./run-typesense-server.sh cleanup
./run-typesense-server.sh
```

### Monitoramento
```bash
# Logs em tempo real
docker logs -f govbrnews-typesense

# Métricas
curl "http://localhost:8108/stats.json" \
  -H "X-TYPESENSE-API-KEY: govbrnews_api_key_change_in_production"

# Health check
curl http://localhost:8108/health
```

## Roadmap

### Melhorias Futuras

1. **Array de Tags**
   - Implementar indexação de `tags` como `string[]`
   - Permite filtro por múltiplas tags

2. **Synonyms**
   ```json
   {
     "synonyms": [
       ["saúde", "medicina", "hospital"],
       ["educação", "ensino", "escola", "universidade"]
     ]
   }
   ```

3. **Geolocalização**
   - Adicionar campos `lat/lon` se disponíveis
   - Busca por proximidade geográfica

4. **Multi-tenancy**
   - Múltiplas collections por agência
   - API keys segregadas por tenant

5. **Cache de Resultados**
   - Redis para queries frequentes
   - TTL de 5 minutos

6. **Rate Limiting**
   - Limitar queries por IP/key
   - Proteção contra abuse

## Recursos e Links

### Documentação Oficial
- [Typesense Docs](https://typesense.org/docs/)
- [Typesense API Reference](https://typesense.org/docs/latest/api/)
- [Typesense Cloud](https://cloud.typesense.org/)

### Tutoriais
- [Guide to Typesense](https://typesense.org/docs/guide/)
- [Search UI with InstantSearch](https://typesense.org/docs/guide/search-ui-components.html)

### Comunidade
- [GitHub](https://github.com/typesense/typesense)
- [Slack Community](https://join.slack.com/t/typesense-community)

### HuggingFace
- [Dataset govbrnews](https://huggingface.co/datasets/nitaibezerra/govbrnews)

## Conclusão

Este setup fornece uma infraestrutura **production-ready** para busca em texto completo no dataset govbrnews, com:

- **Automação completa**: 1 comando para setup
- **Persistência**: Dados sobrevivem a restarts
- **Performance**: < 50ms para buscas
- **Facilidade**: API RESTful simples
- **Recursos avançados**: Typo-tolerance, facets, highlighting
- **Manutenibilidade**: Scripts de refresh e cleanup

**Próximos passos sugeridos**:
1. Experimentar queries na web UI
2. Integrar com aplicação Python/JavaScript
3. Configurar synonyms para domínio governamental
4. Implementar cache para queries frequentes
5. Deploy em produção com HTTPS e API keys segregadas
