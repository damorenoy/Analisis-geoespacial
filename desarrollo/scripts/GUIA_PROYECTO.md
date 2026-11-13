# SCM y generación solar fotovoltaica en el Magdalena — guía del proyecto

Análisis Geoespacial · UNAL Medellín · 2026-02

## 1. La idea en una frase

Medir **cuánta energía solar se pierde en el departamento del Magdalena cuando pasan Sistemas Convectivos de Mesoescala (SCM)**. Se hace con la **generación real** del parque solar Fundación (100 MWac, reporta a XM) y con la irradiancia estimada desde satélite en todo el departamento, para mapear **dónde** es mayor esa pérdida.

**Pregunta de investigación.** ¿Cuánto reduce el paso de SCM la generación fotovoltaica en el Magdalena, y cómo varía esa reducción con la distancia al sistema, su etapa del ciclo de vida, la hora del día y el relieve (Sierra Nevada de Santa Marta, planicie del río Magdalena)?

**Hipótesis.**
- La pérdida es mayor cuando el parque queda bajo el escudo frío de sistemas maduros.
- Muchos SCM del Caribe maduran de noche (Rev. Acad. Colomb. Cienc., 2026). Por eso los **restos del escudo nuboso en la mañana** pueden explicar una parte importante de la pérdida diaria.
- Las zonas bajas del sur y centro del departamento están más expuestas que la franja costera.

## 2. ¿Por qué el Magdalena funciona mejor que Antioquia?

| Parque | Municipio | Capacidad | Estado | Datos de generación |
|---|---|---|---|---|
| Fundación (Enel) | Fundación / Pivijay | 100 MWac | Opera desde 2024, despacho centralizado | **Sí, horaria en XM** |
| Caimán Cienaguero | Ciénaga | 14,3 MWp | Opera desde ene-2024 | Por verificar en XM |

Con datos reales de generación puedes **medir** la pérdida, no solo estimarla. Además puedes **validar** la estimación satelital y luego usarla para todo el departamento.

## 3. Datos (los tres tipos que pide el curso)

| Tipo | Dato | Fuente | Resolución | Para qué |
|---|---|---|---|---|
| Punto | Generación real por parque | XM, API Sinergox (`pydataxm`) | Horaria | Pérdida real y validación |
| Punto | Ubicación y capacidad de los parques | Enel, prensa, Global Energy Monitor → `parques_magdalena.csv` | — | Extraer series y distancias |
| Punto | Estaciones con radiación solar (opcional) | IDEAM-DHIME | Horaria | Validación adicional de la irradiancia |
| Área | Municipios del Magdalena (30) | DANE MGN o geoBoundaries | — | Estadística zonal, Moran, Gi* |
| Área | Polígonos de SCM (escudo nuboso por hora) | Derivados de GOES (script 05) | ~2 km, horario | Exposición, distancia, ciclo de vida |
| Superficie | Temperatura de brillo, canal 13 (10,3 µm) | GOES-16/19 ABI, AWS (libre) | 2 km, 10 min | Identificar y seguir SCM |
| Superficie | Reflectancia visible, canal 2 (0,64 µm) | GOES-16/19 ABI, AWS (libre) | 0,5 km, 10 min | Estimar irradiancia (GHI) |
| Superficie | **Modelo Digital de Elevación** | Copernicus GLO-30 (AWS, libre) o SRTM 30 m | 30 m | Ver sección 4 |

## 4. ¿Necesito un Modelo Digital de Elevación? **Sí**, y aquí aún más.

1. **Irradiancia de cielo despejado.** El Magdalena va de 0 m a ~5.700 m en la Sierra Nevada de Santa Marta. El modelo Ineichen usa la altitud.
2. **Relieve y convección.** La Sierra Nevada y la serranía del Perijá canalizan vientos y fuerzan convección. Cruzar la frecuencia de SCM con la altitud y la distancia a la Sierra es parte del análisis (`deficit_vs_altitud.png`).
3. **Pendiente y orientación.** Sirven para discutir dónde caben nuevos parques (terreno plano) y si esas zonas están más o menos expuestas a SCM.

## 5. Metodología paso a paso

```
GOES canal 13 ──► (5) SCM: umbral 241 K + área + seguimiento ──► polígonos y máscara
GOES canal 2 ──► (4) índice de nubosidad ──► Kc ──► GHI = Kc × GHI_despejado(DEM)
                                                     │
              (6) PVWatts en cada parque ◄───────────┤
              (7) generación REAL de XM ─────────────┤
                                                     ▼
   (8) validación (real vs. estimada) · pérdida real con/sin SCM · por distancia y etapa
       superficies de pérdida ─► estadística zonal por municipio ─► Moran / Gi* · altitud
```

1. **Límites y parques** (`01`): municipios del Magdalena y capa de puntos de parques.
2. **DEM** (`02`): mosaico Copernicus 30 m, recorte, pendiente, orientación y DEM promedio a ~2 km.
3. **Descarga GOES** (`03`): una imagen por hora. El canal 13 se descarga las 24 h en un dominio amplio (4–15 °N, 80–68 °O), para seguir los sistemas desde que nacen. El canal 2 se descarga de 6 a 18 h local solo sobre el Magdalena, promediado a 2 km.
4. **Irradiancia satelital** (`04`): índice de nubosidad tipo Heliosat-2 → Kc → GHI con el modelo Ineichen y la altitud del DEM.
5. **SCM** (`05`): escudo Tb ≤ 241 K con núcleo ≤ 221 K y área ≥ 5.000 km². Seguimiento por solape. Se conservan los sistemas que duran ≥ 3 h y alcanzan ≥ 10.000 km². Etapas: iniciación, madurez, disipación. *Umbrales ajustables en `config.py`.*
6. **Generación estimada** (`06`): PVWatts en cada parque con la GHI satelital. Se marca si el parque está bajo un SCM, la distancia al más cercano y su etapa.
7. **Generación real** (`07`): descarga de XM y emparejamiento con cada parque (revisa en pantalla que el recurso encontrado sea el correcto).
8. **Análisis** (`08`):
   - **Validación**: sesgo, RMSE y correlación entre generación estimada y real.
   - **Pérdida real**: factor de planta bajo SCM vs. sin SCM a la *misma hora del día*, por distancia y por etapa del ciclo de vida.
   - **Superficies**: frecuencia diurna de SCM, pérdida relativa y déficit energético (%).
   - **Áreas**: estadística zonal por municipio, I de Moran, LISA y Getis-Ord Gi*.
   - **Relieve**: déficit por bandas de altitud.

## 6. Cómo correrlo

```bash
python -m venv venv && source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt                        # Windows, si falla: conda install -c conda-forge geopandas rasterio
python test_utils.py                                   # prueba sin internet
python 01_limites_y_parques.py
python 02_dem.py
python 03_descarga_goes.py                             # el paso más largo; se puede reanudar
python 04_irradiancia_satelital.py
python 05_seguimiento_scm.py
python 06_generacion_fv.py
python 07_datos_xm.py
python 08_analisis_espacial.py
```

**Empieza con UN mes**: en `config.py` viene octubre de 2024, temporada lluviosa con el parque ya operando. Revisa los resultados y luego amplía a **2025 completo** para el trabajo final. El cambio de GOES-16 a GOES-19 (abril de 2025) lo maneja el script.

Para cada entrega del curso:
- **Avances (módulo de áreas):** pasos 1–7 con uno a tres meses, más el mapa de frecuencia de SCM por municipio y la primera comparación de factor de planta con y sin SCM.
- **Final:** año completo, validación, mapas de déficit y discusión.

## 7. Limitaciones que conviene mencionar

- La generación real también cae por mantenimiento o restricciones de red (curtailment). Revisa los días anómalos.
- La configuración real del parque (seguidores de un eje o estructura fija, inclinación) no se conoce con certeza. PVWatts con inclinación fija es una aproximación.
- El umbral de 241 K también captura cirros; el núcleo ≤ 221 K y el área mínima lo reducen.
- A resolución horaria se pierden las rampas de minutos.
- Las coordenadas de los parques son aproximadas: verifícalas en una imagen satelital (Google Earth) antes de correr el paso 6.

## 8. Referencias base

- Feng, Z., et al. (2021). A global high-resolution mesoscale convective system database using satellite-derived cloud tops, surface precipitation, and tracking. *JGR: Atmospheres*, 126, e2020JD034202.
- Zuluaga, M. D., y Poveda, G. (2004). Diagnóstico de sistemas convectivos de mesoescala sobre Colombia y el océano Pacífico oriental durante 1998-2002. *Avances en Recursos Hidráulicos*, 11, 145–160.
- Elementos precursores asociados con sistemas convectivos de mesoescala: casos de estudio en el noroeste de Suramérica (2026). *Rev. Acad. Colomb. Cienc. Ex. Fis. Nat.*, 50(195), 540–561.
- Rigollier, C., Lefèvre, M., y Wald, L. (2004). The method Heliosat-2 for deriving shortwave solar radiation from satellite images. *Solar Energy*, 77(2), 159–169.
- Ineichen, P., y Perez, R. (2002). A new airmass independent formulation for the Linke turbidity coefficient. *Solar Energy*, 73(3), 151–157.
- Holmgren, W. F., Hansen, C. W., y Mikofski, M. A. (2018). pvlib python. *JOSS*, 3(29), 884.
- Lanzilao, L., y Meyer, A. (2026). Characterization and forecasting of national-scale solar power ramp events. arXiv:2603.26596.
