"""
agregar_vle.py — paso 1 del pipeline (OULAD).

Agrega studentVle.csv (clics por recurso, ~450 MB) a clics por estudiante, módulo,
presentación y día. Ejecutar desde la raíz del repositorio:
    py pipeline/agregar_vle.py
Genera: vle_features_agregadas.csv
"""
import pandas as pd

print("Cargando studentVle.csv (puede tardar un poco si es grande)...")
df_vle = pd.read_csv('datasets/studentVle.csv')
# columnas esperadas: id_student, code_module, code_presentation, id_site, date, sum_click

print("Agregando clics por estudiante/módulo/presentación/día...")
agg_diaria = (
    df_vle.groupby(['id_student', 'code_module', 'code_presentation', 'date'])['sum_click']
    .sum()
    .reset_index()
)

agg_diaria.to_csv('vle_features_agregadas.csv', index=False)
print(f"Listo. Filas: {len(agg_diaria):,}")
