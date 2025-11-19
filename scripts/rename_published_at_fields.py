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
