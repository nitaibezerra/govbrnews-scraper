# Análise: Servidor MCP para GovBRNews

## Pergunta
**Faz sentido ter um servidor MCP sobre uma API como a do Typesense?**

## O que é MCP (Model Context Protocol)?

MCP é um protocolo criado pela Anthropic para permitir que LLMs (como Claude) acessem dados externos de forma estruturada e segura através de "servidores MCP" que expõem ferramentas (tools) e recursos (resources).

## Comparação: MCP vs API REST Direta

| Aspecto | Typesense API Direta | Servidor MCP sobre Typesense |
|---------|---------------------|------------------------------|
| **Acesso por LLMs** | Requer código client em cada contexto | Integração nativa via MCP |
| **Complexidade de queries** | Usuário precisa conhecer sintaxe | MCP pode abstrair complexidade |
| **Descoberta de dados** | Manual (documentação) | Resources listam dados disponíveis |
| **Contexto semântico** | API retorna JSON bruto | MCP pode enriquecer com metadados |
| **Segurança** | API key exposta em requests | MCP pode intermediar autenticação |
| **Rate limiting** | Por API key | Controlado pelo servidor MCP |

## Quando FAZ SENTIDO usar MCP sobre Typesense

### ✅ **1. Uso por LLMs/Agentes de IA**
```
Cenário: Claude precisa buscar notícias para responder perguntas
Sem MCP: Usuário precisa fazer curl e colar resultados
Com MCP: Claude chama tool search_news("educação") automaticamente
```

### ✅ **2. Abstração de Complexidade**
```python
# Typesense requer conhecimento de sintaxe
filter_by=published_year:>=2023 AND agency:Ministério da Educação

# MCP pode simplificar
search_news(
    query="educação",
    year_from=2023,
    agency="Ministério da Educação"
)
```

### ✅ **3. Descoberta de Recursos**
```
MCP Resources podem expor:
- govbrnews://agencies → Lista de agências disponíveis
- govbrnews://themes → Temas classificados
- govbrnews://stats → Estatísticas do dataset
```

### ✅ **4. Enriquecimento de Contexto**
```
Tool pode retornar não só resultados, mas:
- Resumo dos resultados
- Estatísticas de relevância
- Sugestões de refinamento
- Links relacionados
```

### ✅ **5. Casos de Uso Específicos**
- Assistentes conversacionais que precisam buscar notícias
- Sistemas de RAG (Retrieval-Augmented Generation)
- Análise exploratória guiada por IA
- Dashboards inteligentes

## Quando NÃO FAZ SENTIDO

### ❌ **1. Aplicações Web Tradicionais**
- React/Vue frontend → Melhor usar Typesense JS client diretamente
- Performance crítica → MCP adiciona camada extra

### ❌ **2. Integrações Programáticas Simples**
- Scripts batch → curl ou SDK Typesense é mais direto
- ETL pipelines → Typesense API é suficiente

### ❌ **3. Alta Volumetria**
- Milhares de queries/segundo → MCP adiciona overhead
- Streaming de resultados → API REST é mais eficiente

## Arquitetura Proposta: Servidor MCP GovBRNews

### Tools (Ferramentas)

```json
{
  "tools": [
    {
      "name": "search_news",
      "description": "Busca notícias governamentais brasileiras",
      "inputSchema": {
        "type": "object",
        "properties": {
          "query": {"type": "string", "description": "Termos de busca"},
          "agencies": {"type": "array", "items": {"type": "string"}},
          "year_from": {"type": "integer"},
          "year_to": {"type": "integer"},
          "themes": {"type": "array", "items": {"type": "string"}},
          "limit": {"type": "integer", "default": 10},
          "sort": {"type": "string", "enum": ["newest", "oldest", "relevant"]}
        }
      }
    },
    {
      "name": "get_news_by_id",
      "description": "Obtém notícia completa por ID",
      "inputSchema": {
        "type": "object",
        "properties": {
          "unique_id": {"type": "string", "required": true}
        }
      }
    },
    {
      "name": "get_facets",
      "description": "Obtém agregações/estatísticas",
      "inputSchema": {
        "type": "object",
        "properties": {
          "facet_fields": {
            "type": "array",
            "items": {"type": "string", "enum": ["agency", "category", "theme_1_level_1", "published_year"]}
          },
          "filter_query": {"type": "string"}
        }
      }
    },
    {
      "name": "similar_news",
      "description": "Encontra notícias similares",
      "inputSchema": {
        "type": "object",
        "properties": {
          "reference_id": {"type": "string"},
          "limit": {"type": "integer", "default": 5}
        }
      }
    }
  ]
}
```

### Resources (Recursos)

```json
{
  "resources": [
    {
      "uri": "govbrnews://agencies",
      "name": "Lista de Agências Governamentais",
      "description": "Todas as agências com contagem de notícias",
      "mimeType": "application/json"
    },
    {
      "uri": "govbrnews://themes",
      "name": "Taxonomia de Temas",
      "description": "Hierarquia de temas classificados",
      "mimeType": "application/json"
    },
    {
      "uri": "govbrnews://stats",
      "name": "Estatísticas do Dataset",
      "description": "Métricas gerais, distribuição temporal, etc",
      "mimeType": "application/json"
    },
    {
      "uri": "govbrnews://news/{id}",
      "name": "Notícia Individual",
      "description": "Conteúdo completo de uma notícia específica",
      "mimeType": "text/markdown"
    }
  ]
}
```

### Prompts (Templates)

```json
{
  "prompts": [
    {
      "name": "analyze_theme",
      "description": "Analisa cobertura de um tema ao longo do tempo",
      "arguments": [
        {"name": "theme", "description": "Tema a analisar", "required": true}
      ]
    },
    {
      "name": "compare_agencies",
      "description": "Compara a cobertura de diferentes agências",
      "arguments": [
        {"name": "agencies", "description": "Lista de agências", "required": true}
      ]
    },
    {
      "name": "summarize_period",
      "description": "Resume notícias de um período",
      "arguments": [
        {"name": "start_date", "required": true},
        {"name": "end_date", "required": true},
        {"name": "agency", "required": false}
      ]
    }
  ]
}
```

## Valor Agregado do MCP

### 1. **Inteligência na Busca**
```python
# MCP pode implementar lógica inteligente
def search_news(query, **filters):
    # Expandir sinônimos
    if "saúde" in query:
        query += " OR medicina OR hospital OR sus"

    # Corrigir agências
    if filters.get("agencies") == ["MEC"]:
        filters["agencies"] = ["Ministério da Educação"]

    # Otimizar query Typesense
    typesense_query = build_optimized_query(query, filters)

    # Enriquecer resultados
    results = typesense_client.search(typesense_query)
    return enrich_with_context(results)
```

### 2. **Cache Inteligente**
```python
# Cachear queries comuns e facets
@cache(ttl=300)
def get_facets(facet_fields):
    return typesense_client.facet_search(facet_fields)
```

### 3. **Controle de Acesso**
```python
# MCP pode implementar lógica de autorização
def search_news(query, user_context):
    if user_context.get("role") == "public":
        # Limitar a notícias públicas
        filters["visibility"] = "public"

    return typesense_client.search(query, filters)
```

### 4. **Análise Semântica**
```python
# MCP pode pré-processar queries
def search_news(query):
    # Detectar intenção
    if is_temporal_query(query):
        # "notícias recentes" → sort by date
        sort = "published_at:desc"

    # Detectar entidades
    entities = extract_entities(query)
    if entities.get("agency"):
        filters["agency"] = entities["agency"]
```

## Arquitetura do Sistema Completo

```
┌─────────────┐
│   Claude    │
│   (Client)  │
└──────┬──────┘
       │ MCP Protocol (stdio/SSE)
       │
┌──────▼──────────────┐
│  MCP Server         │
│  govbrnews-mcp      │
│                     │
│  - Tools            │
│  - Resources        │
│  - Prompts          │
│  - Cache Layer      │
│  - Business Logic   │
└──────┬──────────────┘
       │ Typesense Python SDK
       │ HTTP + JSON
┌──────▼──────────────┐
│  Typesense Server   │
│  localhost:8108     │
│                     │
│  - Full-text search │
│  - Facets           │
│  - 295k+ documents  │
└─────────────────────┘
```

## Casos de Uso Ideais

### 1. **Assistente de Pesquisa**
```
Usuário: "Me mostre notícias sobre educação do MEC em 2024"
Claude → MCP → search_news(query="educação", agencies=["Ministério da Educação"], year_from=2024)
Claude: "Encontrei 1.234 notícias sobre educação do MEC em 2024. As principais são..."
```

### 2. **Análise Exploratória**
```
Usuário: "Compare a cobertura de tecnologia entre 2023 e 2024"
Claude → MCP → get_facets(facet_fields=["published_year"], filter_query="tecnologia")
Claude: "Em 2023 houve 450 notícias sobre tecnologia, enquanto em 2024 foram 678 (+50.6%)..."
```

### 3. **RAG para Chatbots**
```
Usuário: "O que o governo está fazendo sobre mudanças climáticas?"
Claude → MCP → search_news(query="mudanças climáticas", sort="newest", limit=5)
Claude: "Segundo notícias recentes: [resumo baseado nos 5 resultados]"
```

### 4. **Dashboard Inteligente**
```
Usuário: "Me dê um relatório sobre saúde no último trimestre"
Claude → MCP → search_news(query="saúde", year_from=2024, month_from=7) + get_facets(...)
Claude: [Gera relatório estruturado com estatísticas e insights]
```

## Implementação Sugerida

### Stack Tecnológico

```python
# pyproject.toml
[tool.poetry.dependencies]
python = "^3.11"
mcp = "^1.0.0"                    # MCP SDK oficial
typesense = "^0.21.0"             # Cliente Typesense
pydantic = "^2.0"                 # Validação de schemas
cachetools = "^5.3"               # Cache em memória
python-dotenv = "^1.0"            # Configuração

[tool.poetry.group.dev.dependencies]
pytest = "^8.0"
pytest-asyncio = "^0.23"
black = "^24.0"
ruff = "^0.3"
```

### Estrutura do Projeto

```
govbrnews-mcp/
├── pyproject.toml
├── README.md
├── .env.example
├── src/
│   └── govbrnews_mcp/
│       ├── __init__.py
│       ├── server.py           # Servidor MCP principal
│       ├── tools/
│       │   ├── __init__.py
│       │   ├── search.py       # Tool: search_news
│       │   ├── facets.py       # Tool: get_facets
│       │   └── similar.py      # Tool: similar_news
│       ├── resources/
│       │   ├── __init__.py
│       │   ├── agencies.py     # Resource: agencies
│       │   ├── themes.py       # Resource: themes
│       │   └── stats.py        # Resource: stats
│       ├── prompts/
│       │   ├── __init__.py
│       │   └── templates.py    # Prompt templates
│       ├── typesense_client.py # Wrapper do cliente
│       ├── cache.py            # Cache layer
│       └── utils.py            # Utilidades
├── tests/
│   ├── test_tools.py
│   ├── test_resources.py
│   └── test_integration.py
└── docs/
    └── USAGE.md
```

### Exemplo de Implementação

```python
# src/govbrnews_mcp/server.py
from mcp.server import Server
from mcp.types import Tool, Resource, TextContent
from .tools import search, facets, similar
from .resources import agencies, themes, stats
from .typesense_client import TypesenseClient

class GovBRNewsServer:
    def __init__(self):
        self.app = Server("govbrnews-mcp")
        self.typesense = TypesenseClient()
        self._register_handlers()

    def _register_handlers(self):
        # Tools
        @self.app.list_tools()
        async def list_tools():
            return [
                Tool(
                    name="search_news",
                    description="Busca notícias governamentais brasileiras",
                    inputSchema=search.SCHEMA
                ),
                Tool(
                    name="get_facets",
                    description="Obtém agregações e estatísticas",
                    inputSchema=facets.SCHEMA
                ),
                Tool(
                    name="similar_news",
                    description="Encontra notícias similares",
                    inputSchema=similar.SCHEMA
                )
            ]

        @self.app.call_tool()
        async def call_tool(name: str, arguments: dict):
            if name == "search_news":
                return await search.execute(self.typesense, arguments)
            elif name == "get_facets":
                return await facets.execute(self.typesense, arguments)
            elif name == "similar_news":
                return await similar.execute(self.typesense, arguments)

        # Resources
        @self.app.list_resources()
        async def list_resources():
            return [
                Resource(
                    uri="govbrnews://agencies",
                    name="Lista de Agências",
                    mimeType="application/json"
                ),
                Resource(
                    uri="govbrnews://themes",
                    name="Taxonomia de Temas",
                    mimeType="application/json"
                ),
                Resource(
                    uri="govbrnews://stats",
                    name="Estatísticas do Dataset",
                    mimeType="application/json"
                )
            ]

        @self.app.read_resource()
        async def read_resource(uri: str):
            if uri == "govbrnews://agencies":
                return await agencies.get_agencies(self.typesense)
            elif uri == "govbrnews://themes":
                return await themes.get_themes(self.typesense)
            elif uri == "govbrnews://stats":
                return await stats.get_stats(self.typesense)

    def run(self):
        self.app.run()

if __name__ == "__main__":
    server = GovBRNewsServer()
    server.run()
```

```python
# src/govbrnews_mcp/tools/search.py
from pydantic import BaseModel, Field
from typing import List, Optional, Literal

class SearchNewsArgs(BaseModel):
    query: str = Field(description="Termos de busca")
    agencies: Optional[List[str]] = Field(default=None, description="Filtrar por agências")
    year_from: Optional[int] = Field(default=None, ge=2018, le=2025)
    year_to: Optional[int] = Field(default=None, ge=2018, le=2025)
    themes: Optional[List[str]] = Field(default=None, description="Filtrar por temas")
    limit: int = Field(default=10, ge=1, le=100)
    sort: Literal["newest", "oldest", "relevant"] = Field(default="relevant")

SCHEMA = SearchNewsArgs.model_json_schema()

async def execute(typesense_client, args: dict):
    validated = SearchNewsArgs(**args)

    # Construir query Typesense
    search_params = {
        'q': validated.query,
        'query_by': 'title,content',
        'per_page': validated.limit
    }

    # Adicionar filtros
    filters = []
    if validated.agencies:
        agency_filter = ' OR '.join([f'agency:={a}' for a in validated.agencies])
        filters.append(f'({agency_filter})')

    if validated.year_from:
        filters.append(f'published_year:>={validated.year_from}')

    if validated.year_to:
        filters.append(f'published_year:<={validated.year_to}')

    if validated.themes:
        theme_filter = ' OR '.join([f'theme_1_level_1:={t}' for t in validated.themes])
        filters.append(f'({theme_filter})')

    if filters:
        search_params['filter_by'] = ' && '.join(filters)

    # Sorting
    if validated.sort == "newest":
        search_params['sort_by'] = 'published_at:desc'
    elif validated.sort == "oldest":
        search_params['sort_by'] = 'published_at:asc'
    # 'relevant' usa ranking padrão do Typesense

    # Executar busca
    results = await typesense_client.search('news', search_params)

    # Formatar resposta para o LLM
    formatted = format_results_for_llm(results)

    return [TextContent(type="text", text=formatted)]

def format_results_for_llm(results):
    """Formata resultados de forma legível para o LLM"""
    found = results.get('found', 0)
    hits = results.get('hits', [])

    output = f"Encontrados {found} resultados.\n\n"

    for i, hit in enumerate(hits, 1):
        doc = hit['document']
        output += f"## {i}. {doc.get('title', 'Sem título')}\n"
        output += f"- **Agência:** {doc.get('agency', 'N/A')}\n"
        output += f"- **Data:** {format_timestamp(doc.get('published_at'))}\n"
        output += f"- **URL:** {doc.get('url', 'N/A')}\n"

        # Snippet do conteúdo
        content = doc.get('content', '')[:300]
        if len(content) == 300:
            content += "..."
        output += f"- **Resumo:** {content}\n\n"

    return output
```

## Configuração e Deployment

### Arquivo .env
```bash
# Typesense
TYPESENSE_HOST=localhost
TYPESENSE_PORT=8108
TYPESENSE_API_KEY=govbrnews_api_key_change_in_production
TYPESENSE_PROTOCOL=http

# Cache
CACHE_TTL=300  # 5 minutos

# MCP
MCP_LOG_LEVEL=INFO
```

### Configuração no Claude Desktop

```json
{
  "mcpServers": {
    "govbrnews": {
      "command": "python",
      "args": [
        "-m",
        "govbrnews_mcp"
      ],
      "env": {
        "TYPESENSE_HOST": "localhost",
        "TYPESENSE_PORT": "8108",
        "TYPESENSE_API_KEY": "govbrnews_api_key_change_in_production"
      }
    }
  }
}
```

### Docker Compose (Opcional)

```yaml
version: '3.8'

services:
  typesense:
    image: govbrnews-typesense
    ports:
      - "8108:8108"
    volumes:
      - govbrnews-data:/data
    environment:
      - TYPESENSE_API_KEY=govbrnews_api_key_change_in_production

  mcp-server:
    build: ./govbrnews-mcp
    depends_on:
      - typesense
    environment:
      - TYPESENSE_HOST=typesense
      - TYPESENSE_PORT=8108
      - TYPESENSE_API_KEY=govbrnews_api_key_change_in_production
    stdin_open: true
    tty: true

volumes:
  govbrnews-data:
```

## Benefícios do MCP sobre Typesense

### 1. **Abstração de Complexidade**
- Cliente não precisa conhecer sintaxe Typesense
- Parâmetros mais intuitivos
- Validação automática de inputs

### 2. **Descoberta de Dados**
```
Claude: "Quais agências estão disponíveis?"
→ Resource govbrnews://agencies
→ Lista todas as agências com contagens
```

### 3. **Contexto Enriquecido**
- Resultados formatados para consumo por LLM
- Metadados adicionais (estatísticas, sugestões)
- Explicações sobre os resultados

### 4. **Lógica de Negócio Centralizada**
- Expansão de sinônimos
- Correção de entidades
- Validações de domínio
- Cache inteligente

### 5. **Segurança**
- API key do Typesense não exposta ao client
- Rate limiting por usuário/sessão
- Logs de auditoria

### 6. **Evolução Independente**
- Backend Typesense pode mudar sem afetar clients
- Adicionar novos índices transparentemente
- A/B testing de algoritmos de ranking

## Limitações e Trade-offs

### Overhead
- Latência adicional: ~10-50ms
- Uso de memória: ~100MB para o servidor MCP
- Complexidade operacional: mais um serviço para gerenciar

### Não Substitui API REST
- Para apps web tradicionais, API direta é melhor
- Para integrações batch, SDK Typesense é suficiente
- MCP é específico para uso por LLMs/agentes

### Escalabilidade
- MCP server precisa escalar junto com demanda
- Cache pode mitigar, mas não elimina bottleneck
- Considerar load balancer para múltiplas instâncias

## Roadmap de Implementação

### Fase 1: MVP (1-2 semanas)
- [ ] Setup do projeto com Poetry
- [ ] Implementar tool `search_news`
- [ ] Implementar resource `govbrnews://stats`
- [ ] Testes básicos
- [ ] README e documentação

### Fase 2: Features Core (2-3 semanas)
- [ ] Implementar tool `get_facets`
- [ ] Implementar tool `similar_news`
- [ ] Implementar resources `agencies` e `themes`
- [ ] Cache layer com TTL configurável
- [ ] Logging estruturado
- [ ] Testes de integração

### Fase 3: Inteligência (2-3 semanas)
- [ ] Expansão de sinônimos
- [ ] Correção automática de nomes de agências
- [ ] Detecção de intenção em queries
- [ ] Enriquecimento de resultados
- [ ] Prompts templates

### Fase 4: Produção (1-2 semanas)
- [ ] Configuração via environment variables
- [ ] Health checks e monitoramento
- [ ] Rate limiting
- [ ] Documentação completa
- [ ] Docker image
- [ ] CI/CD pipeline

## Conclusão

### ✅ **RECOMENDAÇÃO: SIM, DESENVOLVA O SERVIDOR MCP**

**Justificativa:**
1. **Valor para LLMs**: Claude pode explorar notícias conversacionalmente
2. **Abstração útil**: Simplifica sintaxe complexa do Typesense
3. **Descoberta de dados**: Resources expõem metadados estruturados
4. **Extensibilidade**: Camada para adicionar inteligência e lógica de negócio
5. **Casos de uso claros**: Assistentes, RAG, análise exploratória

**Cenário ideal:**
- Você quer usar Claude para pesquisar e analisar notícias
- Você planeja construir aplicações conversacionais
- Você precisa de uma camada de abstração sobre Typesense
- Você quer centralizar lógica de negócio

**Não use se:**
- Você só precisa de uma API REST tradicional
- Performance é absolutamente crítica (< 10ms)
- Você não tem casos de uso com LLMs/agentes

**Próximo passo sugerido:**
Implemente um MVP com `search_news` tool e `stats` resource para validar a arquitetura e coletar feedback de uso real.
