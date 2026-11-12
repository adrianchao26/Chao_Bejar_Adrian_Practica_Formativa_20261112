from pathlib import Path
import pandas as pd

#======================== COMPROBACION LIMPIEZA, COHERENCIA Y DETECCIÓN DE OUTLIERS ========================

VERIFIED = Path("staging/verified")
QUARANTINE = Path("quarantine")
PROCESSED = Path("processed")
QUARANTINE.mkdir(exist_ok=True)
PROCESSED.mkdir(exist_ok=True)

OBLIGATORIAS = ["id_transaccion", "timestamp", "importe_eur", "unidades"]
rechazados = [] 

def rechazar(df, mascara, motivo):
    """Separa las filas que cumplen 'mascara', las guarda con su motivo y devuelve el resto."""
    malos = df[mascara].copy()
    if not malos.empty:
        malos["motivo_rechazo"] = motivo
        rechazados.append(malos)
    print(f"  [{motivo}] -> {len(malos)} registros a cuarentena")
    return df[~mascara].copy()


# 1) Cargar y concatenar los ficheros verificados
print("=== 1. CARGA ===")
ficheros = sorted(VERIFIED.glob("*.csv"))
for f in ficheros:
    print(f"  {f.name}")
df = pd.concat([pd.read_csv(f) for f in ficheros], ignore_index=True)
total_inicial = len(df)
print(f"Registros cargados: {total_inicial}")
print("\nNulos por columna:")
print(df.isna().sum().to_string())

# 2) Nulos en columnas obligatorias -> cuarentena
print("\n=== 2. NULOS EN COLUMNAS OBLIGATORIAS ===")
df = rechazar(df, df[OBLIGATORIAS].isna().any(axis=1), "nulo_en_columna_obligatoria")

# 3) Coherencia temporal (ISO 8601: YYYY-MM-DD HH:MM:SS)
print("\n=== 3. COHERENCIA TEMPORAL ===")
ahora = pd.Timestamp.now()
ts = pd.to_datetime(df["timestamp"], format="%Y-%m-%d %H:%M:%S", errors="coerce")
df = rechazar(df, ts.isna(), "timestamp_invalido")
ts = ts.dropna()
df["timestamp"] = ts.dt.strftime("%Y-%m-%d %H:%M:%S")
df = rechazar(df, ts > ahora, "fecha_futura")
ts = ts[df.index]
df = rechazar(df, ts.dt.year != ahora.year, "fecha_fuera_del_anio_en_curso")

# 4) Reglas de dominio
print("\n=== 4. REGLAS DE DOMINIO ===")
df = rechazar(df, df["importe_eur"] <= 0, "importe_no_positivo")
df = rechazar(df, df["unidades"] < 1, "unidades_menores_a_1")

# 5) Outliers en importe_eur (regla del rango intercuartilico, IQR)
print("\n=== 5. OUTLIERS (IQR) ===")
q1, q3 = df["importe_eur"].quantile([0.25, 0.75])
iqr = q3 - q1
lim_inf, lim_sup = q1 - 1.5 * iqr, q3 + 1.5 * iqr
print(f"  Q1={q1:.2f}  Q3={q3:.2f}  IQR={iqr:.2f}  limites=[{lim_inf:.2f}, {lim_sup:.2f}]")
df = rechazar(df, (df["importe_eur"] < lim_inf) | (df["importe_eur"] > lim_sup), "outlier_importe")

# 6) Imputacion de nulos en variables secundarias
print("\n=== 6. IMPUTACION DE SECUNDARIAS ===")
for col in ["categoria", "metodo_pago"]:
    n = df[col].isna().sum()
    df[col] = df[col].fillna("Desconocido")
    print(f"  {col}: {n} nulos imputados con 'Desconocido'")

# 7) Exportar resultados
print("\n=== 7. EXPORTACION ===")
bad = pd.concat(rechazados, ignore_index=True)
bad.to_csv(QUARANTINE / "bad_records.csv", index=False)
df.to_csv(PROCESSED / "dataset_kdd_listo.csv", index=False)
print(f"  quarantine/bad_records.csv      : {len(bad)} registros")
print(f"  processed/dataset_kdd_listo.csv : {len(df)} registros")

#======================== PERFILADO KDD Y VALIDACION PARA BI ========================

TAMPERED = Path("quarantine/tampered")
BAD = Path("quarantine/bad_records.csv")
LIMPIO = Path("processed/dataset_kdd_listo.csv")
 
# --- Datos de partida ---
bruto = pd.concat([pd.read_csv(f) for f in sorted(VERIFIED.glob("*.csv"))], ignore_index=True)
limpio = pd.read_csv(LIMPIO)
bad = pd.read_csv(BAD)
 
# --- Metricas ---
# Completitud: registros sin nulos / registros totales * 100
comp_bruto = bruto.notna().all(axis=1).mean() * 100
comp_limpio = limpio.notna().all(axis=1).mean() * 100
 
# Integridad criptografica: archivos validados vs rechazados en la fase 1
n_ok = len(list(VERIFIED.glob("*.csv")))
n_ko = len(list(TAMPERED.glob("*.csv")))
integridad = n_ok / (n_ok + n_ko) * 100
 
# Unicidad: % de id_transaccion no duplicados en el dataset limpio
unicidad = (~limpio["id_transaccion"].duplicated()).mean() * 100
 
# Validez: registros que superan las reglas / registros del lote verificado
validez = len(limpio) / len(bruto) * 100
 
# Distribucion de importe_eur (dataset limpio)
imp = limpio["importe_eur"]
dist = {
    "media": imp.mean(), "mediana": imp.median(), "desv_std": imp.std(),
    "p25": imp.quantile(0.25), "p75": imp.quantile(0.75),
}
 
motivos = bad["motivo_rechazo"].value_counts()
 
# --- Salida por terminal ---
print("=== DATA PROFILING (ISO/IEC 25012) ===")
print(f"Completitud (bruto verificado) : {comp_bruto:.2f}%")
print(f"Completitud (dataset limpio)   : {comp_limpio:.2f}%")
print(f"Integridad criptografica       : {integridad:.2f}% ({n_ok} validados, {n_ko} rechazados)")
print(f"Unicidad (id_transaccion)      : {unicidad:.2f}%")
print(f"Validez (limpios / verificados): {validez:.2f}% ({len(limpio)} de {len(bruto)})")
print("\nDistribucion de importe_eur (limpio):")
for k, v in dist.items():
    print(f"  {k:8s}: {v:.2f}")
print("\nRegistros en cuarentena por motivo:")
print(motivos.to_string())
 
# --- Informe Markdown ---
informe = f"""# Informe de Calidad KDD - Lote 202611
 
## 1. Metricas de calidad (ISO/IEC 25012)
 
| Metrica | Valor |
|---|---|
| Completitud (lote verificado, antes de limpiar) | {comp_bruto:.2f}% |
| Completitud (dataset limpio) | {comp_limpio:.2f}% |
| Integridad criptografica | {integridad:.2f}% ({n_ok} archivos validados, {n_ko} rechazados) |
| Unicidad de id_transaccion | {unicidad:.2f}% |
| Validez (registros limpios / verificados) | {validez:.2f}% ({len(limpio)} de {len(bruto)}) |
 
## 2. Distribucion de importe_eur (tras la limpieza)
 
| Estadistico | Valor (EUR) |
|---|---|
| Media | {dist['media']:.2f} |
| Mediana | {dist['mediana']:.2f} |
| Desviacion estandar | {dist['desv_std']:.2f} |
| Percentil 25 | {dist['p25']:.2f} |
| Percentil 75 | {dist['p75']:.2f} |
 
## 3. Registros en cuarentena
 
| Motivo | Registros |
|---|---|
""" + "\n".join(f"| {m} | {n} |" for m, n in motivos.items()) + f"""
 
Total en `quarantine/bad_records.csv`: {len(bad)}.
 
## 4. Conclusiones tecnicas
 
- Integridad: el fichero 'transacciones_tienda_sur.csv' se ha aislado en `quarantine/tampered/` por tener un valor hash invalido.
- Descartes: se descartaron los registros sin `id_transaccion` o sin `importe_eur`, porque son variables obligatorias que no se pueden tratar sin ellas.
- Coherencia: se rechazaron timestamps invalidos, fechas futuras o de otro año, importes <= 0 y unidades < 1, por no tener sentido de negocio.
- Outliers: se detectaron con la regla del IQR (1,5 x IQR) y se enviaron a cuarentena en lugar de borrarse, para poder gestionarlos.
- Imputacion: los nulos en `categoria` y `metodo_pago` se imputaron con "Desconocido", ya que son categoricas y la mediana no se aplica; de esa forma no se pierde el registro.
- Resultado: el dataset limpio tiene {comp_limpio:.0f}% de completitud y una distribucion sin valores extremos, lo que garantiza la consistencia de los datos.
"""
Path("reports/INFORME_CALIDAD_KDD.md").write_text(informe, encoding="utf-8")
print("\nInforme generado: INFORME_CALIDAD_KDD.md")
