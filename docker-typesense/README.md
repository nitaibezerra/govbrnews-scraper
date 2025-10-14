# GovBR News Typesense Server

Este diretório contém os arquivos necessários para criar um servidor Typesense que automaticamente baixa e disponibiliza o dataset de notícias governamentais brasileiras do HuggingFace para busca rápida e eficiente.

## 🚀 Início Rápido

```bash
# 1. A partir do diretório raiz do projeto govbrnews
./docker-typesense/run-typesense-server.sh

# 2. Aguarde ~3-5 minutos para setup completo e indexação
# 3. Use a API Key: govbrnews_api_key_change_in_production na porta 8108
```

**Pronto!** O servidor Typesense estará rodando com **295.511 notícias** indexadas e pronto para buscas ultrarrápidas com tolerância a erros de digitação.

### 🌐 Acessando a Interface Web

Para usar a interface web de busca:

```bash
# Abra o arquivo web-ui.html no seu navegador
open docker-typesense/web-ui/web-ui.html

# Ou no Linux/Windows, abra manualmente:
# - Navegue até: docker-typesense/web-ui/web-ui.html
# - Clique duas vezes para abrir no navegador
```

A interface web oferece:
- ✅ Busca instantânea com destaque de termos encontrados
- ✅ Filtros por ano, órgão, categoria e temas
- ✅ Ordenação por data (mais recentes ou mais antigos)
- ✅ Visualização de imagens das notícias
- ✅ Links diretos para as notícias originais
- ✅ Paginação e estatísticas de resultados

## Visão Geral

O servidor Typesense criado por este container:

1. **Baixa automaticamente** o dataset `nitaibezerra/govbrnews` do HuggingFace
2. **Cria uma coleção otimizada** para buscas rápidas e facetadas
3. **Indexa todos os documentos** com campos pesquisáveis e facetáveis
4. **Expõe a API Typesense** na porta 8108 para acesso externo
5. **Mantém os dados persistentes** através de volumes Docker
6. **Oferece busca com tolerância a erros** de digitação (typo-tolerance)

## Arquivos Incluídos

- `Dockerfile` - Imagem Typesense customizada com Python e dependências HuggingFace
- `requirements.txt` - Dependências Python necessárias
- `init-typesense.py` - Script Python que baixa o dataset e indexa no Typesense
- `entrypoint.sh` - Script shell que inicia o Typesense e orquestra a inicialização
- `run-typesense-server.sh` - **Script principal** para gerenciar o servidor (build, run, cleanup, refresh)
- `README.md` - Este arquivo de documentação

## Estrutura da Coleção

### Coleção: `news`

| Campo | Tipo | Facetável | Descrição |
|-------|------|-----------|-----------|
| `unique_id` | string | Não | Identificador único da notícia |
| `agency` | string | Sim | Agência governamental que publicou |
| `published_at` | int64 | Não | Timestamp Unix da publicação |
| `title` | string | Não | Título da notícia (pesquisável) |
| `url` | string | Não | URL original da notícia |
| `image` | string | Não | URL da imagem principal |
| `category` | string | Sim | Categoria da notícia |
| `tags` | string[] | Sim | Array de tags associadas |
| `content` | string | Não | Conteúdo completo em Markdown (pesquisável) |
| `extracted_at` | int64 | Não | Timestamp Unix da extração |
| `theme_1_level_1` | string | Sim | Tema principal da notícia |
| `published_year` | int32 | Sim | Ano de publicação |
| `published_month` | int32 | Sim | Mês de publicação |

**Campo de ordenação padrão:** `published_at` (descendente)

## Como Usar

### 🚀 Opção Recomendada: Script Automatizado

A maneira mais fácil de usar este servidor Typesense é através do script automatizado que gerencia todo o processo:

```bash
# Opção 1: A partir do diretório raiz do projeto govbrnews (recomendado)
./docker-typesense/run-typesense-server.sh

# Opção 2: A partir do diretório docker-typesense/
cd docker-typesense
./run-typesense-server.sh

# Ver todas as opções disponíveis
./docker-typesense/run-typesense-server.sh help
```

**💡 Vantagem**: O script pode ser executado de qualquer lugar - ele automaticamente detecta sua localização e muda para o diretório correto (`docker-typesense/`) antes de executar.

### 📋 Comandos do Script

| Comando | Descrição | Tempo | Uso |
|---------|-----------|-------|-----|
| `./docker-typesense/run-typesense-server.sh` | Setup completo (build + run + test) | ~90s | Primeira execução |
| `./docker-typesense/run-typesense-server.sh refresh` | Atualizar dataset (recria coleção) | ~60s | Atualizações de dados |
| `./docker-typesense/run-typesense-server.sh cleanup` | Limpeza completa (container + imagem + volume) | ~5s | Reinício do zero |
| `./docker-typesense/run-typesense-server.sh help` | Mostrar ajuda e exemplos | <1s | Consultar comandos |

### 🔧 Opção Manual: Docker Direto

Se preferir controlar manualmente cada etapa:

#### 1. Construir a Imagem Docker

```bash
# A partir do diretório raiz do projeto govbrnews
cd docker-typesense
docker build -t govbrnews-typesense .
```

#### 2. Executar o Container

```bash
# Criar um volume para persistir os dados
docker volume create govbrnews-typesense-data

# Executar o container com volume persistente
docker run -d \
  --name govbrnews-typesense \
  -p 8108:8108 \
  -e TYPESENSE_API_KEY=govbrnews_api_key_change_in_production \
  -v govbrnews-typesense-data:/data \
  govbrnews-typesense
```

### 3. Conectar à API Typesense

#### Usando curl (linha de comando)

```bash
# Health check
curl http://localhost:8108/health

# Informações da coleção
curl "http://localhost:8108/collections/news" \
  -H "X-TYPESENSE-API-KEY: govbrnews_api_key_change_in_production"

# Busca simples
curl "http://localhost:8108/collections/news/documents/search?q=saúde&query_by=title,content" \
  -H "X-TYPESENSE-API-KEY: govbrnews_api_key_change_in_production"
```

#### Usando Python

```python
import typesense

# Configuração do cliente
client = typesense.Client({
    'nodes': [{
        'host': 'localhost',
        'port': '8108',
        'protocol': 'http'
    }],
    'api_key': 'govbrnews_api_key_change_in_production',
    'connection_timeout_seconds': 2
})

# Exemplo de busca simples
search_params = {
    'q': 'educação',
    'query_by': 'title,content',
    'limit': 10
}

results = client.collections['news'].documents.search(search_params)
print(f"Found {results['found']} results")

for hit in results['hits']:
    doc = hit['document']
    print(f"- {doc['title']} ({doc.get('agency', 'N/A')})")
```

#### Usando JavaScript/Node.js

```javascript
const Typesense = require('typesense');

// Configuração do cliente
let client = new Typesense.Client({
  'nodes': [{
    'host': 'localhost',
    'port': '8108',
    'protocol': 'http'
  }],
  'apiKey': 'govbrnews_api_key_change_in_production',
  'connectionTimeoutSeconds': 2
});

// Exemplo de busca
client.collections('news').documents().search({
  'q': 'tecnologia',
  'query_by': 'title,content',
  'limit': 10
}).then((results) => {
  console.log(`Found ${results.found} results`);
  results.hits.forEach((hit) => {
    console.log(`- ${hit.document.title}`);
  });
});
```

**Credenciais padrão:**
- Host: `localhost`
- Port: `8108`
- API Key: `govbrnews_api_key_change_in_production`
- Collection: `news`

## Exemplos de Buscas

### 1. Busca simples por texto

```bash
curl "http://localhost:8108/collections/news/documents/search?q=saúde&query_by=title,content&limit=5" \
  -H "X-TYPESENSE-API-KEY: govbrnews_api_key_change_in_production"
```

### 2. Busca com tolerância a erros (typo-tolerance)

```bash
# Busca por "edukação" (com erro) ainda encontra "educação"
curl "http://localhost:8108/collections/news/documents/search?q=edukação&query_by=title,content" \
  -H "X-TYPESENSE-API-KEY: govbrnews_api_key_change_in_production"
```

### 3. Busca facetada por agência

```bash
curl "http://localhost:8108/collections/news/documents/search?q=*&query_by=title&facet_by=agency&max_facet_values=10" \
  -H "X-TYPESENSE-API-KEY: govbrnews_api_key_change_in_production"
```

### 4. Filtro por agência específica

```bash
curl "http://localhost:8108/collections/news/documents/search?q=*&query_by=title&filter_by=agency:Agência%20Brasil" \
  -H "X-TYPESENSE-API-KEY: govbrnews_api_key_change_in_production"
```

### 5. Busca com filtro por ano

```bash
curl "http://localhost:8108/collections/news/documents/search?q=educação&query_by=title,content&filter_by=published_year:2024" \
  -H "X-TYPESENSE-API-KEY: govbrnews_api_key_change_in_production"
```

### 6. Busca com múltiplos filtros e facetas

```bash
curl "http://localhost:8108/collections/news/documents/search?q=tecnologia&query_by=title,content&filter_by=published_year:>=2023&facet_by=agency,category,theme_1_level_1" \
  -H "X-TYPESENSE-API-KEY: govbrnews_api_key_change_in_production"
```

### 7. Busca ordenada por data (mais recentes primeiro)

```bash
curl "http://localhost:8108/collections/news/documents/search?q=*&query_by=title&sort_by=published_at:desc&limit=10" \
  -H "X-TYPESENSE-API-KEY: govbrnews_api_key_change_in_production"
```

### 8. Busca com destaque (highlighting)

```bash
curl "http://localhost:8108/collections/news/documents/search?q=saúde&query_by=title,content&highlight_full_fields=title,content" \
  -H "X-TYPESENSE-API-KEY: govbrnews_api_key_change_in_production"
```

## Recursos Avançados do Typesense

### Typo Tolerance (Tolerância a Erros)

O Typesense automaticamente corrige erros de digitação:
- "edjcação" → "educação"
- "saude" → "saúde"
- "tecnolgia" → "tecnologia"

### Faceted Search (Busca Facetada)

Campos facetáveis permitem criar filtros dinâmicos:
- `agency` - Filtrar por agência
- `category` - Filtrar por categoria
- `tags` - Filtrar por tags
- `theme_1_level_1` - Filtrar por tema
- `published_year` - Filtrar por ano
- `published_month` - Filtrar por mês

### Geo Search

Embora não implementado neste dataset, o Typesense suporta busca geoespacial.

### Synonyms (Sinônimos)

Você pode configurar sinônimos para melhorar a busca:
```json
{
  "synonyms": [
    ["saúde", "medicina", "hospitais"],
    ["educação", "ensino", "escola"]
  ]
}
```

## Monitoramento e Logs

### Verificar logs do container

```bash
# Ver logs em tempo real
docker logs -f govbrnews-typesense

# Ver logs da inicialização
docker logs govbrnews-typesense | grep -E "(initialization|Download|Indexing)"
```

### Verificar status da coleção

```bash
# Informações da coleção
curl "http://localhost:8108/collections/news" \
  -H "X-TYPESENSE-API-KEY: govbrnews_api_key_change_in_production"

# Health check
curl http://localhost:8108/health

# Estatísticas do servidor
curl "http://localhost:8108/stats.json" \
  -H "X-TYPESENSE-API-KEY: govbrnews_api_key_change_in_production"
```

## 🛠️ Solução de Problemas

### Problemas com o Script Automatizado

#### Comando `refresh` falha
1. **Verifique se o container está rodando:**
   ```bash
   docker ps | grep govbrnews-typesense
   ```

2. **Se não estiver rodando, inicie o servidor:**
   ```bash
   ./run-typesense-server.sh
   ```

3. **Se o refresh continuar falhando, faça limpeza completa:**
   ```bash
   ./run-typesense-server.sh cleanup
   ./run-typesense-server.sh
   ```

#### Container não inicia

1. **Verifique se a porta 8108 não está em uso:**
   ```bash
   lsof -i :8108
   ```

2. **Verifique os logs:**
   ```bash
   docker logs govbrnews-typesense
   ```

#### Dataset não foi carregado

1. **Verifique os logs de inicialização:**
   ```bash
   docker logs govbrnews-typesense | grep -i "download\|error\|dataset"
   ```

2. **Para forçar reload do dataset:**
   ```bash
   ./run-typesense-server.sh refresh
   ```

### 🆘 Solução Universal

Em caso de problemas persistentes:

```bash
# Limpeza completa e restart
./run-typesense-server.sh cleanup
./run-typesense-server.sh

# Isso resolve a maioria dos problemas
```

## 🔄 Atualizações do Dataset

### Método Recomendado: Refresh Automático

Para atualizar apenas os dados (recria a coleção):

```bash
./run-typesense-server.sh refresh
```

**Vantagens:**
- ⚡ Rápido (~60s)
- 🔄 Recria coleção com dados mais recentes
- 📊 Mantém configurações do servidor

### Método Alternativo: Rebuild Completo

Para atualizações com mudanças na estrutura:

1. **Limpeza completa:**
   ```bash
   ./run-typesense-server.sh cleanup
   ```

2. **Restart do zero:**
   ```bash
   ./run-typesense-server.sh
   ```

## Performance e Escalabilidade

### Características de Performance

- **Busca ultrarrápida**: < 50ms para a maioria das queries
- **Indexação em tempo real**: Novos documentos são pesquisáveis imediatamente
- **Typo-tolerance**: Sem impacto significativo na performance
- **Faceted search**: Agregações rápidas mesmo em grandes volumes

### Dicas de Otimização

1. **Use filtros antes de busca textual** para reduzir o conjunto de dados
2. **Limite os campos em `query_by`** apenas aos necessários
3. **Use paginação** com `page` e `per_page` para grandes resultados
4. **Cache resultados comuns** no lado do cliente

## Comparação com PostgreSQL

| Característica | Typesense | PostgreSQL |
|----------------|-----------|------------|
| Tipo de busca | Full-text search otimizado | SQL queries |
| Typo-tolerance | Sim, nativo | Não (requer extensões) |
| Performance de busca | < 50ms | Varia (100ms - 1s+) |
| Faceted search | Nativo e rápido | Requer agregações complexas |
| Highlighting | Nativo | Manual |
| Relevância | Algoritmo de ranking avançado | Básico (tsvector) |
| API | RESTful JSON | SQL |
| Ideal para | Buscas interativas, autocomplete | Queries complexas, transações |

## Contribuindo

Para contribuir com melhorias neste setup Typesense:

1. Faça suas modificações nos arquivos do diretório `docker-typesense/`
2. Teste localmente construindo e executando a imagem
3. Documente suas mudanças neste README
4. Submeta um pull request

## Suporte

Para questões relacionadas ao:
- **Dataset**: Consulte o [repositório principal do govbrnews](https://huggingface.co/datasets/nitaibezerra/govbrnews)
- **Configuração Typesense**: Consulte a [documentação oficial do Typesense](https://typesense.org/docs/)
- **Docker**: Consulte a [documentação do Docker](https://docs.docker.com/)

## Recursos Adicionais

- [Typesense Documentation](https://typesense.org/docs/)
- [Typesense API Reference](https://typesense.org/docs/latest/api/)
- [Typesense Cloud](https://cloud.typesense.org/) - Managed hosting
- [Typesense GitHub](https://github.com/typesense/typesense)

## Licença

Este projeto segue a mesma licença do projeto principal govbrnews.
