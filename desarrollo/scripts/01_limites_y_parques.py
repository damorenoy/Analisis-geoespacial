"""
Paso 1 — Datos tipo ÁREA y PUNTO base.
- Municipios del departamento de estudio (geoBoundaries, ADM2 de Colombia, filtrado por departamento)
- Capa de puntos de parques solares (parques_magdalena.csv)

Alternativa oficial: Marco Geoestadístico Nacional (MGN) del DANE
(https://geoportal.dane.gov.co) — descárgalo a mano y pon la ruta en MGN_LOCAL.
"""
import json
import urllib.request
import geopandas as gpd
import pandas as pd
import config as C

MGN_LOCAL = None   # p. ej. r"C:\datos\MGN_MPIO_POLITICO.shp"


def descargar_geoboundaries(nivel):
    api = f"https://www.geoboundaries.org/api/current/gbOpen/COL/{nivel}/"
    with urllib.request.urlopen(api) as r:
        meta = json.load(r)
    return gpd.read_file(meta["gjDownloadURL"])


def main():
    if MGN_LOCAL:
        mpios = gpd.read_file(MGN_LOCAL)
        col_dpto = [c for c in mpios.columns if "DPTO" in c.upper() and "CCDGO" in c.upper()]
        mpios = mpios[mpios[col_dpto[0]].astype(str) == C.COD_DANE]
    else:
        dptos = descargar_geoboundaries("ADM1")
        mpios_col = descargar_geoboundaries("ADM2")
        region = dptos[dptos["shapeName"].str.contains(C.REGION, case=False)]
        cent = mpios_col.copy()
        cent["geometry"] = cent.representative_point()
        dentro = gpd.sjoin(cent, region[["geometry"]], predicate="within")
        mpios = mpios_col.loc[dentro.index]
        region.to_crs(4326).to_file(C.PROC / "region.gpkg", driver="GPKG")
    mpios = mpios.to_crs(4326)
    mpios.to_file(C.PROC / "municipios.gpkg", driver="GPKG")
    print(f"{len(mpios)} municipios guardados")   # el Magdalena tiene 30

    p = pd.read_csv(C.ARCHIVO_PARQUES)
    parques = gpd.GeoDataFrame(p, geometry=gpd.points_from_xy(p.lon, p.lat), crs=4326)
    parques.to_file(C.PROC / "parques.gpkg", driver="GPKG")
    print(parques[["nombre", "municipio", "capacidad_mw", "estado"]].to_string())


if __name__ == "__main__":
    main()

