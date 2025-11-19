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
