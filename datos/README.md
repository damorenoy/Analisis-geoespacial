# Datos

Archivos generados por `desarrollo/descarga_datos_v2.ipynb`.

## `crudos/`
- `xm_listado_recursos.csv`, `xm/gene_AAAA-MM.csv` — generación horaria por recurso (XM)
- `osm_plantas_solares.json` — plantas solares de OpenStreetMap (Overpass)
- `chirps_mensual_colombia.nc` — precipitación mensual CHIRPS 2023–2024
- `earthenv_nubes/nubes_MM_colombia.tif`, `nubes_anual_colombia.tif` — frecuencia de nubes (valores × 100)

## `procesados/`
- `departamentos.gpkg`, `municipios.gpkg` — geoBoundaries
- `regimen_pluviometrico_ideam.gpkg`, `zonas_radiacion_ideam.gpkg` — IDEAM
- `xm_recursos_solares.csv`, `xm_generacion_mensual.csv` — plantas solares y energía / factor de planta mensual
- `plantas_solares.gpkg` — ubicación de las plantas con departamento, régimen, zona de radiación y elevación
- `power_mensual_plantas.csv` — variables NASA POWER por planta y mes
- panel planta × mes (sección 5 del notebook)

> GitHub no acepta archivos de más de 100 MB (25 MB si se suben desde la web). Si algún archivo los supera (p. ej. el NetCDF de CHIRPS), se puede regenerar con el notebook o guardar con Git LFS.
