import hashlib
import shutil
import logging
from pathlib import Path

# --- CONFIGURACIÓN DE RUTAS Y CARPETAS ---
ruta_manifest = "manifest_checksums.sha256"
archivos_a_comprobar = [
    "transacciones_tienda_norte.csv",
    "transacciones_tienda_sur.csv",
    "transacciones_tienda_este.csv"
]

# Definir carpetas de destino
dir_staging = Path("staging/verified")
dir_quarantine = Path("quarantine/tampered")
dir_logs = Path("logs")

# Crear las carpetas si no existen 
dir_staging.mkdir(parents=True, exist_ok=True)
dir_quarantine.mkdir(parents=True, exist_ok=True)
dir_logs.mkdir(parents=True, exist_ok=True)

# --- CONFIGURACIÓN DEL LOG ---
archivo_log = dir_logs / "ejecucion_pipeline.log"
logging.basicConfig(
    filename=archivo_log,
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# --- FUNCIONES BASE ---
def calcular_sha256(ruta_fichero):
    hasher = hashlib.sha256()
    with open(ruta_fichero, 'rb') as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()

def cargar_manifest(ruta_manifest):
    hashes_esperados = {}
    with open(ruta_manifest, 'r', encoding='utf-8') as f:
        for linea in f:
            linea = linea.strip()
            if not linea:
                continue
            partes = linea.split()
            if len(partes) >= 2:
                hash_esperado = partes[0].lower()
                nombre_archivo = Path(partes[-1].replace("*", "")).name 
                hashes_esperados[nombre_archivo] = hash_esperado
    return hashes_esperados

# --- LÓGICA DE COMPROBACIÓN Y MOVIMIENTO ---
try:
    hashes_manifest = cargar_manifest(ruta_manifest)
    print("Iniciando validación y enrutamiento de archivos...\n" + "-"*50)
    logging.info("--- NUEVA EJECUCIÓN DEL PIPELINE DE VALIDACIÓN ---")
    
    for archivo_str in archivos_a_comprobar:
        ruta_origen = Path(archivo_str)
        nombre_base = ruta_origen.name
        
        # Comprobar si el archivo físico existe antes de hacer nada
        if not ruta_origen.exists():
            print(f"Archivo no encontrado en disco: {nombre_base}")
            continue
 
        # Cálculo y comparación
        hash_calculado = calcular_sha256(ruta_origen)
        hash_esperado = hashes_manifest[nombre_base]
        
        if hash_calculado == hash_esperado:
            # ARCHIVO CORRECTO
            ruta_destino = dir_staging / nombre_base
            shutil.move(str(ruta_origen), str(ruta_destino))
            
            print(f"✅ CORRECTO -> Movido a staging: {nombre_base}")
            
        else:
            ruta_destino = dir_quarantine / nombre_base
            shutil.move(str(ruta_origen), str(ruta_destino))
            
            mensaje_alerta = (
                f"ALERTA DE INTEGRIDAD: '{nombre_base}' ha sido modificado o esta corrupto. "
                f"Movido a cuarentena ({dir_quarantine}). "
                f"Hash esperado: {hash_esperado} | Hash calculado: {hash_calculado}"
            )
            print(f"❌ CORRUPTO -> Movido a cuarentena: {nombre_base}")
            logging.error(mensaje_alerta)  

except FileNotFoundError:
    error_msg = f"Error fatal: No se ha encontrado el archivo manifest '{ruta_manifest}'"
    print(f"{error_msg}")
    logging.critical(error_msg)
except Exception as e:
    error_msg = f"Error inesperado durante la ejecución: {e}"
    print(f"{error_msg}")
    logging.critical(error_msg)