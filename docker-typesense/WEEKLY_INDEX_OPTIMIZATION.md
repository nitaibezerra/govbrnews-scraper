# Otimização de Indexação para Análise Semanal

**Data:** 23 de Outubro de 2025
**Status:** 📋 **PLANEJAMENTO**
**Prioridade:** 🟡 **MÉDIA** (Otimização, não bloqueante)

## Contexto

O servidor MCP GovBRNews implementou análise temporal com três granularidades:
- **Anual (yearly):** Performance excelente usando facet `published_year`
- **Mensal (monthly):** Performance muito boa usando facets `published_year` + `published_month`
- **Semanal (weekly):** Performance boa, mas usa range queries em `published_at` (timestamp)

**Situação atual da granularidade semanal:**
- ✅ **FUNCIONAL:** Implementação está completa e testada
- ✅ **PERFORMÁTICA:** ~1-2s para 8-26 semanas
- ⚠️ **OTIMIZÁVEL:** Requer N queries (uma por semana)

## Problema

### Implementação Atual (Semanal)

**Estratégia:** Range queries no campo `published_at` (timestamp Unix int64)

```python
# Para cada semana, uma query separada
week_filter = f"published_at:>={week_start_ts} && published_at:<{week_end_ts}"

results = client.search({
    "q": query,
    "query_by": "title,content",
    "filter_by": week_filter,
    "per_page": 0
})
```

**Complexidade:**
- **8 semanas:** 8 queries
- **26 semanas (6 meses):** 26 queries
- **52 semanas (1 ano):** 52 queries

**Performance atual:**
- 8 semanas: ~1s
- 26 semanas: ~2s
- 52 semanas: ~3-4s (limite máximo permitido)

**Limitações:**
- Latência cresce linearmente com número de semanas
- Não pode usar facets (Typesense não faz facet em ranges)
- Cada query retorna apenas count, sem agregação automática

### Solução Proposta

**Adicionar campo calculado `published_week` no schema**

```json
{
  "name": "published_week",
  "type": "int32",
  "facet": true,
  "index": true
}
```

**Cálculo:** Semana ISO 8601 (1-53) combinada com ano
- Formato: `YYYYWW` (ex: 202543 = semana 43 de 2025)
- Padrão ISO 8601: semana começa na segunda-feira
- Semana 1 = primeira semana com quinta-feira do ano

**Vantagens:**
1. **Performance:** 1 query vs N queries
2. **Facets nativos:** Agregação automática pelo Typesense
3. **Consistência:** Mesma estratégia de yearly/monthly
4. **Escalabilidade:** Suporta qualquer range de semanas

## Análise de Impacto

### Performance Esperada

| Cenário | Atual (Range) | Com `published_week` | Melhoria |
|---------|---------------|---------------------|----------|
| 8 semanas | ~1s (8 queries) | ~100ms (1 query) | **10x** |
| 26 semanas | ~2s (26 queries) | ~150ms (1 query) | **13x** |
| 52 semanas | ~4s (52 queries) | ~200ms (1 query) | **20x** |
| 104 semanas (2 anos) | ~8s (limite) | ~300ms (1 query) | **27x** |

### Armazenamento

**Dados:**
- **Total de documentos:** 295,511 notícias
- **Campo adicional:** int32 (4 bytes)
- **Overhead:** 295,511 × 4 = ~1.18 MB

**Impacto:** NEGLIGÍVEL (< 0.1% do tamanho total)

### Complexidade de Implementação

**BAIXA** - Mudanças necessárias:

1. **Schema Typesense** (5 min)
   - Adicionar campo `published_week`

2. **Script de ingestão** (15 min)
   - Calcular `published_week` a partir de `published_at`
   - Adicionar ao documento antes da indexação

3. **Código MCP** (30 min)
   - Modificar `_get_weekly_distribution()` para usar facets
   - Remover lógica de múltiplas queries
   - Manter backward compatibility

4. **Testes** (30 min)
   - Atualizar mocks nos testes
   - Validar nova implementação
   - Testar com dados reais

**TOTAL:** ~1h 20min de trabalho

### Reindexação

**Opções:**

**Opção A: Reindexação completa (RECOMENDADO)**
- Criar nova collection com schema atualizado
- Re-ingerir todos os documentos com `published_week`
- Trocar collection atomicamente
- **Tempo:** ~10-15 minutos (para 295k docs)
- **Downtime:** Zero (troca atômica)

**Opção B: Update in-place**
- Atualizar schema da collection existente
- Adicionar campo via update de cada documento
- **Tempo:** ~30-45 minutos
- **Complexidade:** Maior
- **Não recomendado:** Mais lento e propenso a erros

## Implementação Detalhada

### 1. Schema Atualizado

```json
{
  "name": "news",
  "fields": [
    // ... campos existentes ...
    {
      "name": "published_year",
      "type": "int32",
      "facet": true,
      "index": true
    },
    {
      "name": "published_month",
      "type": "int32",
      "facet": true,
      "index": true
    },
    {
      "name": "published_week",
      "type": "int32",
      "facet": true,
      "index": true
    },
    {
      "name": "published_at",
      "type": "int64",
      "index": true
    }
    // ... outros campos ...
  ]
}
```

### 2. Cálculo do Campo (Python)

```python
from datetime import datetime

def calculate_published_week(timestamp: int) -> int:
    """
    Calcula semana ISO 8601 no formato YYYYWW.

    Args:
        timestamp: Unix timestamp em segundos

    Returns:
        int no formato YYYYWW (ex: 202543)

    Examples:
        >>> calculate_published_week(1704110400)  # 01/01/2024
        202401  # Semana 1 de 2024

        >>> calculate_published_week(1729641600)  # 23/10/2025
        202543  # Semana 43 de 2025
    """
    dt = datetime.fromtimestamp(timestamp)

    # ISO 8601: ano e semana
    iso_year, iso_week, _ = dt.isocalendar()

    # Combinar: YYYYWW
    return iso_year * 100 + iso_week
```

**Testes do cálculo:**

```python
import pytest
from datetime import datetime

def test_calculate_published_week():
    """Test ISO week calculation."""

    # 01/01/2024 (segunda-feira) = Semana 1
    ts1 = int(datetime(2024, 1, 1).timestamp())
    assert calculate_published_week(ts1) == 202401

    # 23/10/2025 (quinta-feira) = Semana 43
    ts2 = int(datetime(2025, 10, 23).timestamp())
    assert calculate_published_week(ts2) == 202543

    # 31/12/2024 (terça-feira) = Semana 1 de 2025 (ISO 8601)
    ts3 = int(datetime(2024, 12, 31).timestamp())
    assert calculate_published_week(ts3) == 202501

    # 30/12/2024 (segunda-feira) = Semana 1 de 2025 (ISO 8601)
    ts4 = int(datetime(2024, 12, 30).timestamp())
    assert calculate_published_week(ts4) == 202501
```

### 3. Modificação do Script de Ingestão

**Arquivo:** `init-typesense.py`

```python
def prepare_document(row: dict) -> dict:
    """Prepare document for Typesense indexing."""

    # ... código existente ...

    # Campos temporais
    published_at = int(row['published_at'])
    published_dt = datetime.fromtimestamp(published_at)

    doc = {
        # ... outros campos ...
        'published_at': published_at,
        'published_year': published_dt.year,
        'published_month': published_dt.month,
        'published_week': calculate_published_week(published_at),  # NOVO
        # ... outros campos ...
    }

    return doc
```

### 4. Código MCP Otimizado

**Arquivo:** `src/govbrnews_mcp/utils/temporal.py`

```python
def _get_weekly_distribution(
    client,
    query: str,
    year_from: int | None,
    year_to: int | None,
    max_periods: int
) -> dict[str, Any]:
    """
    Obtém distribuição semanal usando facets (OTIMIZADO).

    Usa campo published_week para agregação via facets,
    resultando em performance ~20x melhor que range queries.
    """

    # Limitar a 52 semanas (ainda recomendado)
    if max_periods > 52:
        max_periods = 52
        logger.warning(f"max_periods ajustado para 52 semanas")

    # Construir filtro de anos se necessário
    filter_parts = []
    if year_from or year_to:
        # Calcular range de semanas ISO (YYYYWW)
        if year_from:
            week_from = year_from * 100 + 1  # Primeira semana do ano
            filter_parts.append(f"published_week:>={week_from}")
        if year_to:
            week_to = year_to * 100 + 53  # Última semana possível
            filter_parts.append(f"published_week:<={week_to}")

    filter_by = " && ".join(filter_parts) if filter_parts else None

    # Query com facet semanal (1 ÚNICA QUERY!)
    search_params = {
        "q": query,
        "query_by": "title,content",
        "facet_by": "published_week",
        "per_page": 0,
        "max_facet_values": max_periods
    }

    if filter_by:
        search_params["filter_by"] = filter_by

    results = client.client.collections["news"].documents.search(search_params)

    # Processar resultados
    distribution = []

    if "facet_counts" in results:
        for facet in results["facet_counts"]:
            if facet["field_name"] == "published_week":
                for count in facet["counts"]:
                    week_iso = int(count["value"])  # YYYYWW

                    # Decompor em ano e semana
                    year = week_iso // 100
                    week = week_iso % 100

                    # Calcular data da segunda-feira desta semana
                    week_start = datetime.strptime(f"{year}-W{week:02d}-1", "%Y-W%W-%w")

                    distribution.append({
                        "period": f"{year}-W{week:02d}",
                        "label": f"Semana de {week_start.strftime('%d/%m/%Y')}",
                        "week_iso": week_iso,
                        "year": year,
                        "week": week,
                        "count": count["count"]
                    })

    # Ordenar por período
    distribution.sort(key=lambda x: x["week_iso"])

    # Limitar resultados
    distribution = distribution[-max_periods:]

    return {
        "granularity": "weekly",
        "query": query,
        "total_found": results.get("found", 0),
        "distribution": distribution,
        "filters": {
            "year_from": year_from,
            "year_to": year_to
        },
        "note": f"Distribuição semanal (ISO 8601) limitada a {max_periods} períodos"
    }
```

### 5. Testes Atualizados

**Arquivo:** `tests/test_temporal.py`

```python
@patch("govbrnews_mcp.utils.temporal.get_typesense_client")
def test_get_temporal_distribution_weekly_optimized(mock_get_client):
    """Test optimized weekly distribution using published_week facet."""
    mock_client = MagicMock()
    mock_get_client.return_value = mock_client

    # Mock facet results
    mock_client.client.collections.__getitem__.return_value.documents.search.return_value = {
        "found": 500,
        "facet_counts": [
            {
                "field_name": "published_week",
                "counts": [
                    {"value": "202540", "count": 125},  # Semana 40 de 2025
                    {"value": "202541", "count": 143},  # Semana 41 de 2025
                    {"value": "202542", "count": 98},   # Semana 42 de 2025
                    {"value": "202543", "count": 134},  # Semana 43 de 2025
                ]
            }
        ]
    }

    result = get_temporal_distribution("test", "weekly", max_periods=4)

    assert result["granularity"] == "weekly"
    assert len(result["distribution"]) == 4
    assert result["distribution"][0]["week_iso"] == 202540
    assert result["distribution"][0]["count"] == 125

    # Verificar que usou apenas 1 query com facet
    call_args = mock_client.client.collections.__getitem__.return_value.documents.search.call_args
    assert call_args[0][0]["facet_by"] == "published_week"
    assert call_args[0][0]["per_page"] == 0
```

## Plano de Implementação

### Fase 1: Preparação (30 min)

1. **Backup da collection atual**
   ```bash
   # Typesense Cloud ou export local
   curl -H "X-TYPESENSE-API-KEY: ${API_KEY}" \
        "http://localhost:8108/collections/news/documents/export" \
        > backup_news.jsonl
   ```

2. **Atualizar schema**
   - Modificar `init-typesense.py` com novo campo
   - Adicionar função `calculate_published_week()`

3. **Testar cálculo**
   - Executar testes unitários do cálculo
   - Validar com casos edge (virada de ano, etc)

### Fase 2: Reindexação (15 min)

1. **Criar nova collection** com schema atualizado
   ```python
   client.collections.create(schema_with_published_week)
   ```

2. **Re-ingerir documentos** com campo calculado
   ```python
   for doc in documents:
       doc['published_week'] = calculate_published_week(doc['published_at'])
       client.collections['news_v2'].documents.create(doc)
   ```

3. **Validar nova collection**
   - Confirmar contagem de documentos
   - Testar facet `published_week`
   - Verificar distribuição de valores

### Fase 3: Atualização do Código MCP (30 min)

1. **Modificar** `_get_weekly_distribution()`
   - Implementar versão otimizada com facets
   - Manter backward compatibility (feature flag?)

2. **Atualizar testes**
   - Modificar mocks para usar facets
   - Adicionar teste de performance (assert < 500ms)

3. **Testar com dados reais**
   - 8 semanas, 26 semanas, 52 semanas
   - Medir latência real
   - Confirmar resultados corretos

### Fase 4: Deploy (10 min)

1. **Trocar collection** atomicamente
   ```python
   # Apontar alias 'news' para 'news_v2'
   client.aliases.upsert('news', {'collection_name': 'news_v2'})
   ```

2. **Restart MCP server**
   - Aplicar novo código
   - Verificar logs

3. **Testes de validação**
   - Executar queries via Claude Code
   - Confirmar latência melhorada
   - Verificar resultados corretos

### Fase 5: Limpeza (5 min)

1. **Remover collection antiga** (após confirmação)
   ```python
   client.collections['news_old'].delete()
   ```

2. **Atualizar documentação**
   - Marcar otimização como implementada
   - Atualizar métricas de performance

**TEMPO TOTAL:** ~1h 30min

## Riscos e Mitigações

### Risco 1: Semanas ISO diferentes de semanas calendário
- **Impacto:** BAIXO - Usuários podem estranhar semanas ISO
- **Mitigação:** Labels mostram data exata da segunda-feira
- **Exemplo:** "Semana de 23/10/2025" é mais claro que "Semana 43"

### Risco 2: Virada de ano ISO
- **Impacto:** BAIXO - Últimos dias de dezembro podem ser semana 1 do ano seguinte
- **Exemplo:** 31/12/2024 = Semana 1 de 2025 (ISO 8601)
- **Mitigação:** Documentação clara + testes para casos edge

### Risco 3: Reindexação falhar
- **Impacto:** MÉDIO - Downtime temporário
- **Mitigação:**
  - Backup completo antes
  - Criar collection nova (não modificar existente)
  - Troca atômica via alias
  - Rollback imediato se necessário

### Risco 4: Performance não melhorar como esperado
- **Impacto:** BAIXO - Implementação atual já funciona
- **Probabilidade:** MUITO BAIXA - Facets são otimização nativa do Typesense
- **Mitigação:** Testar em staging primeiro, rollback fácil

## Decisão: Implementar ou Não?

### Argumentos CONTRA implementação agora:

1. ✅ **Implementação atual funciona bem** (~1-2s é aceitável)
2. ✅ **Não é bloqueante** para nenhuma funcionalidade
3. ⚠️ **Requer reindexação** (mesmo que rápida e segura)
4. ⚠️ **Adiciona complexidade** ao processo de ingestão

### Argumentos A FAVOR da implementação:

1. 🚀 **Ganho de 10-20x em performance** é significativo
2. 🚀 **Permite expandir limite** de 52 para 104+ semanas
3. 🚀 **Consistência** com yearly/monthly (todos usam facets)
4. 🚀 **Baixo risco** (collection nova + troca atômica)
5. 🚀 **Rápido de implementar** (~1h30)
6. 🚀 **Custo negligível** de armazenamento (<1MB)

## Recomendação Final

### ✅ **IMPLEMENTAR** - Mas não urgente

**Quando implementar:**
- ✅ **AGORA:** Se planejando usar análise semanal intensivamente
- ✅ **AGORA:** Se quiser melhor experiência de usuário (< 500ms)
- 🟡 **DEPOIS:** Se funcionalidade atual atende (pode esperar Fase 6)
- 🟡 **DEPOIS:** Se quiser focar em Fase 5 (Prompts) primeiro

**Prioridade sugerida:**
1. **Fase 5:** Prompts Templates (essencial, maior valor)
2. **Fase 6:** Dashboard e Visualizações (se aplicável)
3. **Otimização Semanal:** Implementar quando houver janela de manutenção

### Implementação Sugerida: Fase 5.5 (Entre Prompts e próxima fase)

**Benefícios de esperar:**
- Fase 5 completa primeiro (maior prioridade)
- Acumular feedback sobre uso de análise semanal
- Identificar se limite de 52 semanas é realmente necessário aumentar
- Implementar em janela de manutenção planejada

**Próximos passos imediatos:**
1. ✅ **Documentar** (este arquivo - FEITO)
2. ✅ **Seguir para Fase 5** (Prompts Templates)
3. 🔜 **Revisitar** após Fase 5 completa
4. 🔜 **Implementar** se houver demanda real

---

## Apêndice A: Comparação de Implementações

### Implementação Atual (Range Queries)

```python
# Múltiplas queries
for week in weeks:
    query = {
        "filter_by": f"published_at:>={week.start} && published_at:<{week.end}"
    }
    count = search(query)["found"]
```

**Pros:**
- ✅ Funciona com schema atual
- ✅ Sem necessidade de reindexação
- ✅ Flexível (qualquer range arbitrário)

**Cons:**
- ❌ N queries (latência linear)
- ❌ Limite prático de ~52 semanas
- ❌ Mais complexo (calcular ranges)

### Implementação Otimizada (Facets)

```python
# 1 única query
query = {
    "facet_by": "published_week",
    "max_facet_values": 52
}
counts = search(query)["facet_counts"]
```

**Pros:**
- ✅ 1 query (latência constante)
- ✅ Consistente com yearly/monthly
- ✅ Escalável (100+ semanas possível)
- ✅ Código mais simples

**Cons:**
- ❌ Requer campo no schema
- ❌ Requer reindexação
- ❌ Campo calculado na ingestão

## Apêndice B: Formato ISO 8601

**Padrão ISO 8601 para semanas:**
- Semana começa na segunda-feira
- Semana 1 = primeira semana com quinta-feira do ano
- Algumas semanas do final de dezembro pertencem ao ano seguinte
- Algumas semanas do início de janeiro pertencem ao ano anterior

**Exemplos:**
```
31/12/2024 (terça) = 2025-W01 (Semana 1 de 2025)
01/01/2025 (quarta) = 2025-W01
06/01/2025 (segunda) = 2025-W02

29/12/2025 (segunda) = 2025-W53
31/12/2025 (quarta) = 2025-W53
01/01/2026 (quinta) = 2026-W01
```

**Por que ISO 8601:**
- Padrão internacional reconhecido
- Suportado nativamente por Python (`datetime.isocalendar()`)
- Consistente e previsível
- Usado por sistemas de BI e analytics

---

**Documento criado:** 23 de Outubro de 2025
**Autor:** Claude + Nitai Bezerra
**Versão:** 1.0
**Status:** 📋 Planejamento completo - Pronto para implementação futura
