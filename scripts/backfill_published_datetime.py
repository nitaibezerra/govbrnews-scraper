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

    # Converter coluna para datetime (mantém timezone)
    df['published_datetime'] = pd.to_datetime(df['published_datetime'], utc=False)

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
