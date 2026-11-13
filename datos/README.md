# Datos

Archivos generados por `desarrollo/descarga_datos_v2.ipynb`.

## `crudos/`
- `xm_listado_recursos.csv`, `xm/gene_AAAA-MM.csv` — generación horaria por recurso (XM)
- `osm_plantas_solares.json` — plantas solares de OpenStreetMap (Overpass)
- `chirps_mensual_colombia.nc` — precipitación mensual CHIRPS 2023–2024
- `chirps_diario_plantas.csv` — precipitación diaria CHIRPS en el píxel de cada planta
- `ideam_catalogo_estaciones.csv` — Catálogo Nacional de Estaciones del IDEAM
- `ideam_precipitacion_diaria.csv`, `ideam_temperatura_diaria.csv`, `ideam_humedad_diaria.csv` — series diarias de las estaciones cercanas a las plantas
- `earthenv_nubes/nubes_MM_colombia.tif`, `nubes_anual_colombia.tif` — frecuencia de nubes (valores × 100)

## `procesados/`
- `departamentos.gpkg`, `municipios.gpkg` — geoBoundaries
- `regimen_pluviometrico_ideam.gpkg`, `zonas_radiacion_ideam.gpkg` — IDEAM
- `xm_recursos_solares.csv`, `xm_generacion_mensual.csv` — plantas solares y energía / factor de planta mensual
- `plantas_solares.gpkg` — ubicación de las plantas con departamento, régimen, zona de radiación y elevación
- `power_mensual_plantas.csv` — variables NASA POWER por planta y mes
- `ideam_estaciones_por_planta.csv` — estaciones del IDEAM a ≤ 30 km de cada planta y su distancia
- `ideam_estaciones_mensual.csv`, `ideam_estaciones.gpkg` — lluvia, días de lluvia, temperatura y humedad mensual por estación
- `chirps_diario_mensual_plantas.csv` — lluvia mensual, días de lluvia y día más lluvioso (CHIRPS diario) por planta
- panel planta × mes (sección 5 del notebook)

> GitHub no acepta archivos de más de 100 MB (25 MB si se suben desde la web). Si algún archivo los supera (p. ej. el NetCDF de CHIRPS), se puede regenerar con el notebook o guardar con Git LFS.
