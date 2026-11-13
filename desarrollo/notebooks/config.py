"""
Configuración central del proyecto:
Influencia de los Sistemas Convectivos de Mesoescala (SCM) en la generación
solar fotovoltaica del departamento del Magdalena.

Edita SOLO este archivo para cambiar período, dominio o umbrales.
"""
from datetime import datetime
from pathlib import Path

# ----------------------------------------------------------------------------
# Rutas
# ----------------------------------------------------------------------------
BASE = Path(__file__).resolve().parent
DATA = BASE / "datos"
RAW = DATA / "crudos"          # descargas sin procesar
PROC = DATA / "procesados"     # productos intermedios
OUT = BASE / "resultados"      # mapas, tablas y figuras finales
for p in (DATA, RAW, PROC, OUT):
    p.mkdir(parents=True, exist_ok=True)

# ----------------------------------------------------------------------------
# Período de estudio
# Recomendación: probar primero con UN mes y luego ampliar. Octubre de 2024 es
# temporada lluviosa en el Caribe y el parque Fundación ya estaba en operación.
# Para el trabajo final: 2025 completo.
# GOES-16 fue GOES-Este hasta el 2025-04-07; desde entonces es GOES-19
# (el script cambia de satélite automáticamente).
# ----------------------------------------------------------------------------
FECHA_INICIO = datetime(2024, 10, 1)
FECHA_FIN = datetime(2024, 10, 31)   # inclusive

# Horas UTC que se descargan
HORAS_TB = list(range(24))           # canal 13 (infrarrojo): 24 h, para seguir el ciclo de vida
HORAS_VIS = list(range(11, 24))      # canal 2 (visible): 11–23 UTC = 6–18 hora local

# ----------------------------------------------------------------------------
# Dominios (lat_min, lat_max, lon_min, lon_max)
# ----------------------------------------------------------------------------
# Dominio de seguimiento de SCM: más grande que el Magdalena para capturar
# sistemas que nacen en los piedemontes andinos, el valle del Magdalena,
# la Sierra Nevada o sobre el mar Caribe.
DOM_SEGUIMIENTO = (4.0, 15.0, -80.0, -68.0)
# Dominio de análisis: departamento del Magdalena con un pequeño margen.
DOM_ANALISIS = (8.6, 11.6, -75.2, -73.4)

# Región de estudio
REGION = "Magdalena"
COD_DANE = "47"              # código DANE del departamento

# ----------------------------------------------------------------------------
# Criterios de identificación de SCM (ajustables; ver README)
# Basados en la literatura de seguimiento con temperatura de brillo
# (p. ej. Feng et al., 2021; Zuluaga y Poveda, 2004).
# ----------------------------------------------------------------------------
TB_ESCUDO_K = 241.0        # escudo nuboso frío
TB_NUCLEO_K = 221.0        # núcleo convectivo profundo
AREA_MIN_KM2 = 5000.0      # área mínima del escudo en cada hora
AREA_MAX_MIN_KM2 = 10000.0 # el sistema debe alcanzar al menos esta área en su vida
DURACION_MIN_H = 3         # duración mínima (horas)
SOLAPE_MIN = 0.3           # fracción de solape para unir objetos entre horas

# ----------------------------------------------------------------------------
# Irradiancia satelital (método de índice de nubosidad tipo Heliosat)
# ----------------------------------------------------------------------------
PERCENTIL_CIELO_DESPEJADO = 5    # albedo de cielo despejado por píxel/hora/mes
PERCENTIL_NUBE = 99              # albedo de nube densa (todo el dominio, por mes)
ZENIT_MAX = 80.0                 # se descartan ángulos cenitales mayores

# ----------------------------------------------------------------------------
# Modelo fotovoltaico genérico (PVWatts) para los parques
# ----------------------------------------------------------------------------
INCLINACION = 10.0         # grados (latitud ~10 °N); cambia si conoces el diseño real del parque
AZIMUT = 180.0             # orientado al sur
GAMMA_PDC = -0.004         # coeficiente de temperatura (1/°C)
T_AIRE_C = 27.0            # temperatura del aire supuesta (mejorable con ERA5)
VIENTO_MS = 1.0
EFIC_INVERSOR = 0.96

# Resolución de la malla regular de salida (grados) ~2,2 km
RES_MALLA = 0.02

# Parques solares (editar/ampliar en parques_magdalena.csv)
ARCHIVO_PARQUES = BASE / "parques_magdalena.csv"

# Satélite GOES-Este según la fecha
CAMBIO_GOES19 = datetime(2025, 4, 7)
