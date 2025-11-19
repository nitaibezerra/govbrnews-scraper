# Plano de Migração: Campo `published_at` (Date → Datetime)

**Status**: 🟡 Em Planejamento
**Criado em**: 2025-11-19
**Última atualização**: 2025-11-19
**Responsável**: Nitai Bezerra

---

## 📋 Índice

1. [Contexto e Motivação](#contexto-e-motivação)
2. [Estado Atual](#estado-atual)
3. [Objetivos da Migração](#objetivos-da-migração)
4. [Arquitetura Atual](#arquitetura-atual)
5. [Estratégia de Migração](#estratégia-de-migração)
6. [Plano de Implementação](#plano-de-implementação)
7. [Scripts e Código](#scripts-e-código)
8. [Checklists de Validação](#checklists-de-validação)
9. [Rollback Plan](#rollback-plan)
10. [Timeline](#timeline)
11. [Riscos e Mitigações](#riscos-e-mitigações)

---

## Contexto e Motivação

### O que foi feito no PR #45

O [PR #45](https://github.com/nitaibezerra/govbrnews-scraper/pull/45) introduziu campos de datetime completos no scraper, mantendo retrocompatibilidade:

**Campos adicionados:**
- `published_datetime`: Timestamp completo com hora e timezone (ISO 8601, e.g., "2025-11-17T19:24:43-03:00")
- `updated_datetime`: Timestamp de atualização quando disponível

**Métodos de extração:**
1. **JSON-LD schema** (mais confiável) - extrai de metadados estruturados
2. **Padrões de texto** - detecta formatos como "DD/MM/YYYY HH:MMh"
3. **Timezone padrão**: Brasília (UTC-3)

**Campo mantido:**
- `published_at`: Date-only (sem hora) para retrocompatibilidade

**Bug corrigido:**
- Valores null não são mais convertidos para epoch Unix (1970-01-01)

### Por que migrar agora?

Com os dados de timestamp disponíveis, podemos:
- ✅ **Ordenação precisa**: Notícias do mesmo dia ordenadas por hora de publicação
- ✅ **UX melhorado**: Exibir "19h24" no portal ao invés de só a data
- ✅ **Simplificação**: Remover campo duplicado (`published_at` date-only)
- ✅ **Arquitetura limpa**: Um único campo datetime como fonte de verdade

---

## Estado Atual

### Estrutura de Dados

**Dataset (HuggingFace: nitaibezerra/govbrnews):**
```python
{
    "published_at": "2024-01-15",              # datetime.date (string no dataset)
    "published_datetime": "2024-01-15T19:24:43-03:00",  # datetime com timezone
    "updated_datetime": "2024-01-16T10:30:00-03:00"     # opcional
}
```

**Typesense Schema:**
```python
{'name': 'published_at', 'type': 'int64', 'facet': False}  # Unix timestamp
```

**Portal (TypeScript):**
```typescript
published_at: number | null  // Unix timestamp
```

### Fluxo de Dados Atual

```
┌─────────────────────────────────────────────────────────────┐
│ 1. SCRAPER                                                  │
│    Extrai: published_at (date) + published_datetime (dt)   │
│    ↓ Salva no Dataset HuggingFace                          │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│ 2. TYPESENSE LOADING                                        │
│    Lê: published_at do dataset                             │
│    Converte: datetime.date → Unix timestamp (int64)        │
│    Armazena: published_at como int64 no Typesense          │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│ 3. PORTAL                                                   │
│    Consulta: published_at como number (timestamp)          │
│    Usa para: Ordenação e filtros                           │
│    Exibe: Somente data (sem hora)                          │
└─────────────────────────────────────────────────────────────┘
```

**Insight chave**: A conversão para Unix timestamp acontece no **loading do Typesense**, não no scraper. Isso significa que:
- ✅ Typesense aceita qualquer formato datetime
- ✅ Não precisamos mudar o schema do Typesense
- ✅ Portal não precisa mudanças de tipo

---

## Objetivos da Migração

### Objetivos Primários

1. ✅ **Ordenação precisa por timestamp** - artigos do mesmo dia ordenados por hora
2. ✅ **Exibir hora no Portal** - mostrar "17/11/2025 às 19h24" quando disponível
3. ✅ **Deprecar campo `published_at` (date)** - manter apenas datetime

### Objetivos Secundários

4. ✅ **Simplificar código do scraper** - remover lógica duplicada
5. ✅ **Zero breaking changes** - nenhum downtime ou mudança de schema
6. ✅ **Migração gradual** - implementação por fases com rollback seguro

### Não-Objetivos

❌ Mudar schema do Typesense (continua int64)
❌ Mudar tipo do Portal (continua number)
❌ Rescrape completo de dados históricos
❌ Mudanças em consumidores externos (não existem)

---

## Arquitetura Atual

### Componentes Envolvidos

1. **govbrnews-scraper-main**: Extração de dados e push para HuggingFace
2. **destaquesgovbr-typesense** (Docker): Loading inicial de dados
3. **destaquesgovbr-infra**: Scripts de loading incremental para produção
4. **destaquesgovbr-portal**: Interface web Next.js

### Dependências entre Componentes

```
Scraper (dados) → HuggingFace (storage) → Typesense (indexação) → Portal (UI)
```

**Importante**: Cada componente é independente, permitindo deploy incremental.

---

## Estratégia de Migração

### Abordagem: Renomeação no Dataset

**Conceito**: Trocar os campos no dataset do HuggingFace sem modificar schemas downstream.

```
ANTES:
published_at (date) ───→ Typesense ───→ Portal
published_datetime (datetime) (não usado)

DEPOIS:
published_at (datetime) ───→ Typesense ───→ Portal
published_at_old (date) (temporário, depois removido)
```

### Por que essa abordagem funciona?

1. **Typesense não se importa**: Converte date OU datetime → int64
2. **Portal não se importa**: Espera number (timestamp), funciona com ambos
3. **Nome mantido**: Campo continua se chamando `published_at` para consumidores
4. **Zero downtime**: Mudança transparente

### Tratamento de Dados Históricos

Artigos antigos (pre-PR #45) não têm hora real. Estratégia:

**Opção escolhida: Timestamp sintético 00:00:00**
- Artigo de 2024-01-15 → `2024-01-15T00:00:00-03:00`
- **Rationale**: Hora 00:00 indica "sem informação de hora precisa"
- **Benefício**: Zero nulls, sorting funciona perfeitamente
- **Transparência**: Documentado que hora 00:00 = data aproximada

---

## Plano de Implementação

### Visão Geral das Fases

| Fase | Descrição | Duração | Risco |
|------|-----------|---------|-------|
| 1 | Backfill de dados históricos | 1 semana | 🟢 Baixo |
| 2 | Renomeação no dataset HuggingFace | 1 dia | 🟢 Baixo |
| 3 | Atualização do scraper | 1 semana | 🟢 Baixo |
| 4 | Reindexação e atualização do portal | 1-2 semanas | 🟡 Médio |
| 5 | Limpeza final | 1 dia | 🟢 Baixo |

---

### Fase 1: Backfill de Dados Históricos

**Objetivo**: Garantir que todos os artigos tenham `published_datetime` preenchido.

#### Tarefas

1. **Criar script de backfill** (`scripts/backfill_published_datetime.py`)
2. **Processar dataset completo**:
   - Se `published_datetime` existe → manter valor
   - Se não existe → criar a partir de `published_at` com hora 00:00:00 (timezone Brasília)
3. **Validar resultado**: 0 nulls em `published_datetime`
4. **Push para HuggingFace**

#### Script (ver seção Scripts e Código)

#### Checklist de Validação

- [ ] Script criado e testado localmente
- [ ] Dataset baixado do HuggingFace
- [ ] Backfill executado com sucesso
- [ ] Validação: `df['published_datetime'].isna().sum() == 0`
- [ ] Comparação antes/depois documentada
- [ ] Push para HuggingFace realizado
- [ ] Download de teste confirma dados corretos

#### Riscos e Mitigações

| Risco | Probabilidade | Impacto | Mitigação |
|-------|---------------|---------|-----------|
| Dataset corrompido durante processo | Baixa | Alto | Backup do dataset antes de modificar |
| Timestamps inválidos | Baixa | Médio | Validação com `pd.to_datetime()` antes de salvar |
| Push para HuggingFace falha | Baixa | Baixo | Retry automático, verificação após push |

---

### Fase 2: Renomeação no Dataset

**Objetivo**: Trocar os campos `published_at` e `published_datetime`.

#### Tarefas

1. **Baixar dataset atualizado** (pós-backfill)
2. **Renomear colunas**:
   ```python
   df = df.rename(columns={
       'published_at': 'published_at_old',
       'published_datetime': 'published_at'
   })
   ```
3. **Validar estrutura**:
   - `published_at` agora é datetime
   - `published_at_old` preservado temporariamente
4. **Push para HuggingFace**

#### Script (ver seção Scripts e Código)

#### Checklist de Validação

- [ ] Backup do dataset criado
- [ ] Renomeação executada localmente
- [ ] Validação de tipos: `df['published_at'].dtype == 'datetime64[ns]'`
- [ ] Validação de valores: comparar `published_at` com `published_at_old`
- [ ] Push para HuggingFace
- [ ] Download de teste confirma estrutura nova

#### Riscos e Mitigações

| Risco | Probabilidade | Impacto | Mitigação |
|-------|---------------|---------|-----------|
| Consumidores quebram | Nenhuma* | N/A | *Não há consumidores externos confirmados |
| Typesense loading quebra | Baixa | Médio | Testar loading local antes de produção |

---

### Fase 3: Atualização do Scraper

**Objetivo**: Modificar scraper para salvar datetime diretamente como `published_at`.

#### Tarefas

1. **Criar branch**: `feature/published-at-datetime-migration`
2. **Modificar código**:
   - **webscraper.py (linha ~218)**: Renomear `published_datetime` → `published_at`
   - **webscraper.py**: Remover extração de `published_at` (date-only)
   - **scrape_manager.py**: Atualizar referências
   - **dataset_manager.py**: Atualizar merge/update logic
3. **Atualizar testes**:
   - `test_datetime_scraping.py`: Atualizar assertions
   - `test_new_fields.py`: Remover testes do campo antigo
4. **Testar localmente**:
   - Scrape de teste
   - Validação de tipos
5. **Criar PR e solicitar review**
6. **Merge após aprovação**

#### Arquivos a Modificar

```
src/scraper/webscraper.py (linhas 218-220, 470-656)
src/scraper/scrape_manager.py (linhas 162-165)
src/dataset_manager.py (linhas 159-165, 224-228)
test_datetime_scraping.py
test_new_fields.py
```

#### Checklist de Validação

- [ ] Branch criada e atualizada com main
- [ ] Código modificado
- [ ] Testes atualizados
- [ ] Testes locais passando: `pytest tests/`
- [ ] Scrape de teste realizado
- [ ] Dataset de teste criado e validado
- [ ] PR criado com descrição detalhada
- [ ] Review aprovado
- [ ] Merge realizado
- [ ] CI/CD passa após merge

#### Riscos e Mitigações

| Risco | Probabilidade | Impacto | Mitigação |
|-------|---------------|---------|-----------|
| Quebrar scraping ativo | Baixa | Alto | Testes extensivos antes de merge |
| Regressão em extração de datetime | Média | Médio | Manter testes do PR #45 intactos |
| Merge conflicts | Baixa | Baixo | Atualizar branch regularmente |

---

### Fase 4: Reindexação e Atualização do Portal

**Objetivo**: Reindexar Typesense com novos dados e atualizar Portal para exibir hora.

#### Parte 4A: Reindexação do Typesense

##### Tarefas

1. **Atualizar Typesense Docker** (se necessário)
   - Verificar se loading script já suporta datetime
   - Testar localmente: `./run-typesense-server.sh cleanup && ./run-typesense-server.sh`
2. **Atualizar scripts de infra**
   - Mesmo código de loading
   - Testar em staging se disponível
3. **Reindexação em produção**:
   - Opção A: Full reindex (deleta + recria collection)
   - Opção B: Incremental load de todo o dataset
4. **Validação**: Queries de teste no Typesense

##### Checklist de Validação

- [ ] Loading script do Docker testado localmente
- [ ] Dados carregados corretamente (timestamps válidos)
- [ ] Scripts de infra atualizados
- [ ] Decisão tomada: full vs incremental reindex
- [ ] Backup de produção realizado
- [ ] Reindex executado
- [ ] Validação: contagem de documentos
- [ ] Validação: sorting por `published_at` funciona
- [ ] Validação: filtros por data funcionam

#### Parte 4B: Atualização do Portal

##### Tarefas

1. **Criar branch**: `feature/show-publication-time`
2. **Atualizar componentes de exibição**:
   - Identificar componentes que mostram `published_at`
   - Implementar formatação condicional:
     - Se hora != 00:00 → "17/11/2025 às 19h24"
     - Se hora == 00:00 → "17/11/2025" (sem hora)
3. **Atualizar tipos TypeScript** (se necessário)
4. **Testes**:
   - Testes unitários de componentes
   - Testes de integração
   - Testes visuais/screenshots
5. **Criar PR e review**
6. **Deploy**

##### Arquivos a Modificar (aproximados)

```
src/lib/article-row.ts (tipos)
src/app/actions.ts (queries - nenhuma mudança necessária)
src/components/<ArticleCard|ArticleList>.tsx (formatação de data)
```

##### Checklist de Validação

- [ ] Branch criada
- [ ] Componentes identificados
- [ ] Código de formatação implementado
- [ ] Testes unitários passando
- [ ] Testes de integração passando
- [ ] Preview visual validado
- [ ] PR criado e revisado
- [ ] Deploy em staging (se disponível)
- [ ] Validação em staging
- [ ] Deploy em produção
- [ ] Smoke tests em produção

#### Riscos e Mitigações

| Risco | Probabilidade | Impacto | Mitigação |
|-------|---------------|---------|-----------|
| Downtime durante reindex | Baixa | Médio | Reindex incremental em vez de drop + recreate |
| Portal mostra timestamps incorretos | Média | Alto | Testes extensivos de formatação, considerar timezone |
| Performance de queries degradada | Baixa | Médio | Monitorar métricas após deploy |

---

### Fase 5: Limpeza Final

**Objetivo**: Remover campo temporário `published_at_old`.

#### Tarefas

1. **Validar tudo funcionando**:
   - Scraper salvando novos dados
   - Typesense indexando corretamente
   - Portal exibindo hora
2. **Remover coluna do dataset**:
   ```python
   df = df.drop(columns=['published_at_old'])
   ```
3. **Push para HuggingFace**
4. **Documentar migração**:
   - Atualizar README se necessário
   - Adicionar entry no CHANGELOG
   - Marcar este documento como concluído

#### Checklist de Validação

- [ ] Sistema rodando estável por 1-2 semanas
- [ ] Nenhum erro relacionado a `published_at` nos logs
- [ ] Confirmação: nenhum código referencia `published_at_old`
- [ ] Coluna removida do dataset
- [ ] Push para HuggingFace
- [ ] Documentação atualizada
- [ ] Migração marcada como ✅ Concluída

---

## Scripts e Código

### Script 1: Backfill `published_datetime`

**Arquivo**: `scripts/backfill_published_datetime.py`

```python
"""
Script para backfill do campo published_datetime.

Para artigos que não possuem published_datetime, cria um timestamp
a partir de published_at com hora 00:00:00 (timezone Brasília).

Uso:
    python scripts/backfill_published_datetime.py
"""

import pandas as pd
from datetime import datetime
from datasets import load_dataset, Dataset
from zoneinfo import ZoneInfo

# Configurações
DATASET_NAME = "nitaibezerra/govbrnews"
BRASILIA_TZ = ZoneInfo("America/Sao_Paulo")  # UTC-3


def backfill_published_datetime(df: pd.DataFrame) -> pd.DataFrame:
    """
    Preenche published_datetime quando ausente.

    Args:
        df: DataFrame com colunas published_at e published_datetime

    Returns:
        DataFrame com published_datetime preenchido
    """
    print(f"Total de artigos: {len(df)}")

    # Contar quantos já têm published_datetime
    has_datetime = df['published_datetime'].notna().sum()
    print(f"Artigos com published_datetime: {has_datetime}")
    print(f"Artigos sem published_datetime: {len(df) - has_datetime}")

    # Para cada artigo sem published_datetime
    def fill_datetime(row):
        if pd.notna(row['published_datetime']):
            # Já tem datetime, manter valor
            return row['published_datetime']

        if pd.isna(row['published_at']):
            # Sem nenhuma data, manter None
            return None

        # Criar datetime a partir de published_at com hora 00:00:00
        date = pd.to_datetime(row['published_at']).date()
        dt = datetime.combine(date, datetime.min.time())
        dt = dt.replace(tzinfo=BRASILIA_TZ)

        return dt.isoformat()

    df['published_datetime'] = df.apply(fill_datetime, axis=1)

    # Validação
    nulls_after = df['published_datetime'].isna().sum()
    print(f"\nApós backfill:")
    print(f"  Nulls em published_datetime: {nulls_after}")
    print(f"  Artigos preenchidos: {len(df) - nulls_after}")

    return df


def main():
    """Executa o backfill completo."""
    print("=" * 60)
    print("BACKFILL DE PUBLISHED_DATETIME")
    print("=" * 60)

    # 1. Carregar dataset
    print("\n1. Carregando dataset do HuggingFace...")
    dataset = load_dataset(DATASET_NAME, split='train')
    df = dataset.to_pandas()

    # 2. Fazer backup
    print("\n2. Criando backup local...")
    backup_file = f"backup_dataset_{datetime.now().strftime('%Y%m%d_%H%M%S')}.parquet"
    df.to_parquet(backup_file)
    print(f"   Backup salvo em: {backup_file}")

    # 3. Executar backfill
    print("\n3. Executando backfill...")
    df_updated = backfill_published_datetime(df)

    # 4. Validar resultado
    print("\n4. Validando resultado...")
    assert df_updated['published_datetime'].isna().sum() == 0, \
        "ERRO: Ainda existem nulls em published_datetime!"

    # Verificar formato de datetime
    sample_datetime = df_updated[df_updated['published_datetime'].notna()]['published_datetime'].iloc[0]
    print(f"   Exemplo de datetime: {sample_datetime}")

    # 5. Salvar localmente
    print("\n5. Salvando dataset atualizado...")
    output_file = "dataset_with_backfilled_datetime.parquet"
    df_updated.to_parquet(output_file)
    print(f"   Salvo em: {output_file}")

    # 6. Fazer push para HuggingFace
    print("\n6. Fazendo push para HuggingFace...")
    response = input("   Deseja fazer push? (sim/não): ")

    if response.lower() in ['sim', 's', 'yes', 'y']:
        updated_dataset = Dataset.from_pandas(df_updated)
        updated_dataset.push_to_hub(DATASET_NAME, private=False)
        print("   ✅ Push realizado com sucesso!")
    else:
        print("   ⏭️  Push cancelado. Execute manualmente quando pronto.")

    print("\n" + "=" * 60)
    print("BACKFILL CONCLUÍDO COM SUCESSO!")
    print("=" * 60)


if __name__ == "__main__":
    main()
```

---

### Script 2: Renomear Campos no Dataset

**Arquivo**: `scripts/rename_published_at_fields.py`

```python
"""
Script para renomear campos published_at no dataset.

Renomeia:
- published_at → published_at_old (backup)
- published_datetime → published_at (campo principal)

Uso:
    python scripts/rename_published_at_fields.py
"""

import pandas as pd
from datetime import datetime
from datasets import load_dataset, Dataset

# Configurações
DATASET_NAME = "nitaibezerra/govbrnews"


def rename_fields(df: pd.DataFrame) -> pd.DataFrame:
    """
    Renomeia campos do dataset.

    Args:
        df: DataFrame original

    Returns:
        DataFrame com campos renomeados
    """
    print(f"Colunas antes: {list(df.columns)}")

    # Validar que campos existem
    required_cols = ['published_at', 'published_datetime']
    missing = [col for col in required_cols if col not in df.columns]
    if missing:
        raise ValueError(f"Colunas faltando no dataset: {missing}")

    # Renomear
    df_renamed = df.rename(columns={
        'published_at': 'published_at_old',
        'published_datetime': 'published_at'
    })

    print(f"Colunas depois: {list(df_renamed.columns)}")

    # Validar tipos
    print(f"\nTipo de 'published_at' (novo): {df_renamed['published_at'].dtype}")
    print(f"Tipo de 'published_at_old': {df_renamed['published_at_old'].dtype}")

    # Comparar valores (sanity check)
    print("\nExemplos de dados:")
    print(df_renamed[['published_at', 'published_at_old']].head())

    return df_renamed


def main():
    """Executa a renomeação."""
    print("=" * 60)
    print("RENOMEAÇÃO DE CAMPOS PUBLISHED_AT")
    print("=" * 60)

    # 1. Carregar dataset
    print("\n1. Carregando dataset do HuggingFace...")
    dataset = load_dataset(DATASET_NAME, split='train')
    df = dataset.to_pandas()

    # 2. Fazer backup
    print("\n2. Criando backup local...")
    backup_file = f"backup_before_rename_{datetime.now().strftime('%Y%m%d_%H%M%S')}.parquet"
    df.to_parquet(backup_file)
    print(f"   Backup salvo em: {backup_file}")

    # 3. Renomear campos
    print("\n3. Renomeando campos...")
    df_renamed = rename_fields(df)

    # 4. Validar resultado
    print("\n4. Validando resultado...")
    assert 'published_at' in df_renamed.columns, "Campo 'published_at' não existe!"
    assert 'published_at_old' in df_renamed.columns, "Campo 'published_at_old' não existe!"
    assert 'published_datetime' not in df_renamed.columns, "Campo 'published_datetime' ainda existe!"

    # Verificar nulls
    nulls = df_renamed['published_at'].isna().sum()
    print(f"   Nulls em published_at (novo): {nulls}")

    # 5. Salvar localmente
    print("\n5. Salvando dataset renomeado...")
    output_file = "dataset_renamed.parquet"
    df_renamed.to_parquet(output_file)
    print(f"   Salvo em: {output_file}")

    # 6. Fazer push para HuggingFace
    print("\n6. Fazendo push para HuggingFace...")
    response = input("   Deseja fazer push? (sim/não): ")

    if response.lower() in ['sim', 's', 'yes', 'y']:
        renamed_dataset = Dataset.from_pandas(df_renamed)
        renamed_dataset.push_to_hub(DATASET_NAME, private=False)
        print("   ✅ Push realizado com sucesso!")
    else:
        print("   ⏭️  Push cancelado. Execute manualmente quando pronto.")

    print("\n" + "=" * 60)
    print("RENOMEAÇÃO CONCLUÍDA COM SUCESSO!")
    print("=" * 60)


if __name__ == "__main__":
    main()
```

---

### Script 3: Remover Campo Temporário

**Arquivo**: `scripts/remove_published_at_old.py`

```python
"""
Script para remover campo temporário published_at_old.

Uso:
    python scripts/remove_published_at_old.py
"""

import pandas as pd
from datetime import datetime
from datasets import load_dataset, Dataset

# Configurações
DATASET_NAME = "nitaibezerra/govbrnews"


def main():
    """Remove coluna published_at_old."""
    print("=" * 60)
    print("REMOÇÃO DE CAMPO PUBLISHED_AT_OLD")
    print("=" * 60)

    # 1. Carregar dataset
    print("\n1. Carregando dataset do HuggingFace...")
    dataset = load_dataset(DATASET_NAME, split='train')
    df = dataset.to_pandas()

    # 2. Verificar se coluna existe
    if 'published_at_old' not in df.columns:
        print("   ⚠️  Coluna 'published_at_old' não encontrada. Nada a fazer.")
        return

    print(f"   Colunas atuais: {list(df.columns)}")

    # 3. Fazer backup
    print("\n2. Criando backup local...")
    backup_file = f"backup_before_cleanup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.parquet"
    df.to_parquet(backup_file)
    print(f"   Backup salvo em: {backup_file}")

    # 4. Remover coluna
    print("\n3. Removendo coluna 'published_at_old'...")
    df_cleaned = df.drop(columns=['published_at_old'])
    print(f"   Colunas após remoção: {list(df_cleaned.columns)}")

    # 5. Salvar localmente
    print("\n4. Salvando dataset limpo...")
    output_file = "dataset_cleaned.parquet"
    df_cleaned.to_parquet(output_file)
    print(f"   Salvo em: {output_file}")

    # 6. Fazer push para HuggingFace
    print("\n5. Fazendo push para HuggingFace...")
    response = input("   Deseja fazer push? (sim/não): ")

    if response.lower() in ['sim', 's', 'yes', 'y']:
        cleaned_dataset = Dataset.from_pandas(df_cleaned)
        cleaned_dataset.push_to_hub(DATASET_NAME, private=False)
        print("   ✅ Push realizado com sucesso!")
    else:
        print("   ⏭️  Push cancelado. Execute manualmente quando pronto.")

    print("\n" + "=" * 60)
    print("LIMPEZA CONCLUÍDA COM SUCESSO!")
    print("=" * 60)


if __name__ == "__main__":
    main()
```

---

## Checklists de Validação

### Checklist Geral da Migração

#### Pré-Migração
- [ ] Documento de migração revisado e aprovado
- [ ] Backups de todos os componentes criados:
  - [ ] Dataset HuggingFace
  - [ ] Collection Typesense (se aplicável)
  - [ ] Código dos repositórios (tags Git)
- [ ] Comunicação com stakeholders realizada
- [ ] Janela de manutenção agendada (se necessário)

#### Durante Migração
- [ ] Fase 1 (Backfill) concluída e validada
- [ ] Fase 2 (Renomeação) concluída e validada
- [ ] Fase 3 (Scraper) concluída e validada
- [ ] Fase 4 (Typesense + Portal) concluída e validada
- [ ] Fase 5 (Limpeza) concluída e validada

#### Pós-Migração
- [ ] Sistema em produção estável por 1+ semana
- [ ] Nenhum erro relacionado à migração nos logs
- [ ] Métricas de performance normais
- [ ] Testes end-to-end passando
- [ ] Documentação atualizada
- [ ] Post-mortem realizado (se houve incidentes)

---

### Checklist de Testes

#### Testes de Scraper
- [ ] Scraping de URLs de teste
- [ ] Validação de extração de `published_at` (datetime)
- [ ] Validação de timezone (Brasília)
- [ ] Testes unitários passando
- [ ] Testes de integração passando

#### Testes de Typesense
- [ ] Loading local de dataset de teste
- [ ] Validação de conversão datetime → timestamp
- [ ] Queries de ordenação por `published_at`
- [ ] Queries de filtro por data
- [ ] Performance de queries

#### Testes de Portal
- [ ] Exibição correta de data + hora
- [ ] Exibição correta de apenas data (para hora 00:00)
- [ ] Ordenação de artigos
- [ ] Filtros por data
- [ ] Testes de responsividade
- [ ] Testes de acessibilidade

---

## Rollback Plan

### Cenários de Rollback

#### Fase 1 - Rollback do Backfill

**Quando**: Backfill gerou dados incorretos.

**Ações**:
1. Restaurar dataset do backup: `backup_dataset_<timestamp>.parquet`
2. Fazer push do backup para HuggingFace
3. Validar restauração

**Tempo estimado**: 30 minutos

---

#### Fase 2 - Rollback da Renomeação

**Quando**: Renomeação quebrou consumidores ou gerou dados incorretos.

**Ações**:
1. Restaurar dataset do backup: `backup_before_rename_<timestamp>.parquet`
2. Fazer push do backup para HuggingFace
3. Validar restauração

**Tempo estimado**: 30 minutos

---

#### Fase 3 - Rollback do Scraper

**Quando**: Scraper não está funcionando corretamente após mudanças.

**Ações**:
1. Reverter commit: `git revert <commit-hash>`
2. Fazer push da reversão
3. CI/CD deploy automático
4. Validar scraping funcionando

**Tempo estimado**: 15 minutos

---

#### Fase 4 - Rollback de Typesense

**Quando**: Reindex causou problemas ou Portal não funciona.

**Ações**:

**Opção A - Reindexar com dados antigos**:
1. Restaurar dataset do backup
2. Reindexar Typesense
3. Validar

**Opção B - Restaurar backup de collection** (se disponível):
1. Deletar collection atual
2. Restaurar snapshot
3. Validar

**Tempo estimado**: 30-60 minutos (dependendo do tamanho do dataset)

---

#### Fase 4 - Rollback do Portal

**Quando**: Portal apresenta bugs ou exibição incorreta.

**Ações**:
1. Reverter deploy para versão anterior
2. Validar funcionamento
3. Investigar causa raiz

**Tempo estimado**: 10 minutos (deploy automático)

---

#### Fase 5 - Rollback da Limpeza

**Quando**: Descoberta de dependência em `published_at_old`.

**Ações**:
1. Restaurar dataset do backup: `backup_before_cleanup_<timestamp>.parquet`
2. Fazer push do backup para HuggingFace
3. Validar

**Tempo estimado**: 30 minutos

---

### Plano de Comunicação em Caso de Rollback

1. **Notificar stakeholders**: Email/Slack com motivo do rollback
2. **Atualizar status da migração**: Marcar fase como "falhou"
3. **Investigação**: Post-mortem para entender causa raiz
4. **Decisão**: Corrigir e tentar novamente, ou abortar migração

---

## Timeline

### Timeline Otimista (Sem Problemas)

| Semana | Atividades | Status |
|--------|-----------|--------|
| **Semana 1** | Planejamento e aprovação | 🟡 Em andamento |
| **Semana 2** | Fase 1: Backfill de dados históricos | 🔵 Planejado |
| **Semana 3** | Fase 2: Renomeação no dataset | 🔵 Planejado |
| **Semana 4-5** | Fase 3: Atualização do scraper | 🔵 Planejado |
| **Semana 6-7** | Fase 4: Typesense + Portal | 🔵 Planejado |
| **Semana 8** | Fase 5: Limpeza e documentação | 🔵 Planejado |
| **Semana 9-10** | Monitoramento pós-migração | 🔵 Planejado |

**Total**: ~10 semanas (2,5 meses)

---

### Timeline Realista (Com Contingências)

| Semana | Atividades | Buffer |
|--------|-----------|--------|
| **Semana 1-2** | Planejamento e aprovação | +1 semana para discussões |
| **Semana 3-4** | Fase 1: Backfill | +1 semana para problemas de dados |
| **Semana 5** | Fase 2: Renomeação | +1 semana para validação extra |
| **Semana 6-8** | Fase 3: Scraper | +1 semana para bugs/testes |
| **Semana 9-12** | Fase 4: Typesense + Portal | +2 semanas para ajustes de UI |
| **Semana 13** | Fase 5: Limpeza | - |
| **Semana 14-16** | Monitoramento pós-migração | +2 semanas para estabilização |

**Total**: ~16 semanas (4 meses)

---

### Milestones Críticos

| Milestone | Data Alvo | Critério de Sucesso |
|-----------|-----------|---------------------|
| **M1**: Plano aprovado | Semana 2 | Documento assinado por stakeholders |
| **M2**: Backfill concluído | Semana 4 | Dataset sem nulls em `published_datetime` |
| **M3**: Scraper atualizado | Semana 8 | PR merged e CI verde |
| **M4**: Portal mostrando hora | Semana 12 | Deploy em produção funcionando |
| **M5**: Migração concluída | Semana 16 | Sistema estável, documentação finalizada |

---

## Riscos e Mitigações

### Matriz de Riscos

| ID | Risco | Prob. | Impacto | Severidade | Mitigação |
|----|-------|-------|---------|------------|-----------|
| R1 | Dados históricos corrompidos durante backfill | Baixa | Alto | 🟡 Médio | Backup antes de modificar, validação extensiva |
| R2 | Typesense loading quebra com novo formato | Baixa | Médio | 🟢 Baixo | Testar localmente antes de produção |
| R3 | Portal mostra timestamps incorretos | Média | Alto | 🔴 Alto | Testes extensivos de timezone, validação visual |
| R4 | Performance de queries degradada | Baixa | Médio | 🟡 Médio | Monitoramento, índices otimizados |
| R5 | Scraper para de funcionar após mudanças | Baixa | Alto | 🟡 Médio | Testes automatizados, rollback rápido |
| R6 | Downtime prolongado durante reindex | Baixa | Médio | 🟢 Baixo | Usar incremental load em vez de full reindex |
| R7 | Descoberta de consumidores externos não documentados | Muito Baixa | Médio | 🟢 Baixo | Manter campo temporário `published_at_old` |
| R8 | Problemas com timezone (UTC vs Brasília) | Média | Alto | 🔴 Alto | Validação rigorosa, testes com diferentes timezones |

---

### Detalhamento de Riscos Críticos

#### R3: Portal mostra timestamps incorretos

**Cenário**: Portal exibe hora errada devido a conversões de timezone.

**Sinais de alerta**:
- Usuários reportam horários errados
- Artigos ordenados incorretamente
- Timestamps com diferença de 3h (UTC vs Brasília)

**Mitigação**:
1. **Antes do deploy**: Testes manuais extensivos com diferentes horários
2. **Durante o deploy**: Deploy em staging primeiro
3. **Após o deploy**: Monitoramento de logs, feedback de usuários

**Rollback**: Reverter deploy do portal (rápido, ~10 min)

---

#### R8: Problemas com timezone

**Cenário**: Inconsistência entre timezone do scraper (Brasília) e exibição no portal.

**Exemplo problemático**:
- Artigo publicado 17/11/2025 19:24 (Brasília)
- Armazenado como Unix timestamp: 1731878640
- Portal exibe: 17/11/2025 22:24 (se interpretar como UTC)

**Mitigação**:
1. **Scraper**: Sempre usar `ZoneInfo("America/Sao_Paulo")` ao criar datetime
2. **Typesense**: Armazenar Unix timestamp (UTC universal)
3. **Portal**: Converter de UTC para Brasília na exibição:
   ```typescript
   const date = new Date(timestamp * 1000);
   const brasiliaTime = date.toLocaleString('pt-BR', {
     timeZone: 'America/Sao_Paulo'
   });
   ```

**Validação**:
- Testar com artigos de diferentes horários
- Verificar que exibição corresponde ao esperado
- Comparar com timestamp Unix calculado manualmente

---

## Recursos Adicionais

### Documentação de Referência

- [PR #45 - Datetime Fields](https://github.com/nitaibezerra/govbrnews-scraper/pull/45)
- [Typesense Timestamps](https://typesense.org/docs/latest/api/documents.html#indexing-dates)
- [Pandas Datetime](https://pandas.pydata.org/docs/user_guide/timeseries.html)
- [Python ZoneInfo](https://docs.python.org/3/library/zoneinfo.html)
- [HuggingFace Datasets](https://huggingface.co/docs/datasets/)

### Comandos Úteis

```bash
# Scraper
cd /Users/nitai/Dropbox/dev-mgi/govbrnews-scraper-main
python scripts/backfill_published_datetime.py
python scripts/rename_published_at_fields.py
pytest tests/

# Typesense Docker
cd /Users/nitai/Dropbox/dev-mgi/destaquesgovbr-typesense
./run-typesense-server.sh cleanup
./run-typesense-server.sh

# Infra
cd /Users/nitai/Dropbox/dev-mgi/destaquesgovbr-infra/scripts/typesense/python
python scripts/load_data.py --mode full --force
python scripts/load_data.py --mode incremental --days 30

# Portal
cd /Users/nitai/Dropbox/dev-mgi/destaquesgovbr-portal
npm run dev
npm run build
npm run test
```

### Contatos

- **Responsável pela migração**: Nitai Bezerra
- **Repositórios**:
  - Scraper: https://github.com/nitaibezerra/govbrnews-scraper
  - Portal: (URL se disponível)
  - Infra: (URL se disponível)

---

## Controle de Versão

| Versão | Data | Autor | Mudanças |
|--------|------|-------|----------|
| 1.0 | 2025-11-19 | Claude Code | Versão inicial do plano |

---

## Status Atual da Migração

**Status**: 🟡 Em Planejamento

### Progresso por Fase

- [ ] **Fase 1**: Backfill de dados históricos
- [ ] **Fase 2**: Renomeação no dataset
- [ ] **Fase 3**: Atualização do scraper
- [ ] **Fase 4**: Reindexação e atualização do portal
- [ ] **Fase 5**: Limpeza final

**Última atualização**: 2025-11-19
**Próximo passo**: Criar scripts de backfill e testar localmente

---

## Aprovações

| Stakeholder | Papel | Status | Data |
|-------------|-------|--------|------|
| Nitai Bezerra | Tech Lead | 🟡 Pendente | - |

---

## Notas Finais

Este plano foi elaborado para garantir uma migração segura, gradual e sem downtime do campo `published_at` de date para datetime. A abordagem de renomeação no dataset foi escolhida por:

✅ **Simplicidade**: Menos mudanças de código
✅ **Segurança**: Rollback fácil em cada fase
✅ **Zero downtime**: Mudanças transparentes para usuários
✅ **Backward compatible**: Nenhum breaking change

O sucesso da migração depende de:
1. Execução cuidadosa de cada fase
2. Validação rigorosa após cada etapa
3. Monitoramento contínuo
4. Comunicação clara com stakeholders

**Boa sorte com a migração! 🚀**
