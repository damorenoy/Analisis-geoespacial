"""
Paso 5 — Identificación y seguimiento de Sistemas Convectivos de Mesoescala.
Sobre la temperatura de brillo del canal 13 (dominio de seguimiento):
  1. Escudo frío: píxeles con Tb ≤ 241 K, conectados (8 vecinos).
  2. Se conservan objetos con área ≥ AREA_MIN_KM2 y núcleo Tb ≤ 221 K.
  3. Seguimiento hora a hora por solape espacial.
  4. Es SCM si dura ≥ DURACION_MIN_H y alcanza AREA_MAX_MIN_KM2.
  5. Etapa del ciclo de vida: iniciación / madurez / disipación.
Salidas:
  datos/procesados/scm_trayectorias.csv  (una fila por SCM y hora: área, Tb mín., centroide, etapa)
  datos/procesados/scm_poligonos.gpkg     (datos tipo ÁREA: escudo de cada SCM sobre la región por hora)
  datos/procesados/scm_mascara.nc         (id de SCM por píxel en la malla de análisis)
"""
import numpy as np
import pandas as pd
import xarray as xr
import geopandas as gpd
from shapely.geometry import shape
from rasterio import features
from rasterio.transform import from_origin
import config as C
from utils import (area_pixel_km2, objetos_frios, Seguidor, etapa_ciclo_vida,
                   a_malla_regular, malla_regular)


def main():
    archivos = sorted((C.RAW / "tb").glob("tb_*.nc"))
    with xr.open_dataset(archivos[0]) as d0:
        lat, lon = d0["lat"].values, d0["lon"].values
    apix = area_pixel_km2(lat, lon)
    seg = Seguidor(C.SOLAPE_MIN)
    filas, mascaras, tiempos = [], [], []
    t_prev = None

    for a in archivos:                                   # día por día
        with xr.open_dataset(a) as ds:
            for k, t in enumerate(pd.DatetimeIndex(ds["time"].values)):
                if t_prev is not None and (t - t_prev) > pd.Timedelta(hours=1.5):
                    seg.paso(None)                       # hueco: se cortan trayectorias
                t_prev = t
                tb = ds["tb"].isel(time=k).values
                et, _ = objetos_frios(tb, apix, C.TB_ESCUDO_K, C.TB_NUCLEO_K, C.AREA_MIN_KM2)
                tr = seg.paso(et)
                for i in np.unique(tr[tr > 0]):
                    m = tr == i
                    w = apix[m]
                    filas.append({"scm_id": int(i), "time": t, "area_km2": float(w.sum()),
                                  "tb_min_k": float(np.nanmin(tb[m])),
                                  "lat_c": float(np.average(lat[m], weights=w)),
                                  "lon_c": float(np.average(lon[m], weights=w))})
                m_r, _, _ = a_malla_regular(tr, lat, lon, C.DOM_ANALISIS, C.RES_MALLA)
                mascaras.append(np.nan_to_num(m_r).astype("int32"))
                tiempos.append(t)
        print("procesado", a.name)

    df = pd.DataFrame(filas)
    g = df.groupby("scm_id")
    dur, amax = g["time"].count(), g["area_km2"].max()
    validos = dur[(dur >= C.DURACION_MIN_H) & (amax >= C.AREA_MAX_MIN_KM2)].index
    df = df[df.scm_id.isin(validos)].sort_values(["scm_id", "time"]).copy()
    df["etapa"] = np.concatenate([etapa_ciclo_vida(s.values) for _, s in df.groupby("scm_id")["area_km2"]])
    df["duracion_h"] = df.groupby("scm_id")["time"].transform("count")
    df["hora_local"] = (df["time"] - pd.Timedelta(hours=5)).dt.hour
    df.to_csv(C.PROC / "scm_trayectorias.csv", index=False)
    print(f"{len(validos)} SCM identificados")

    lat_r, lon_r = malla_regular(C.DOM_ANALISIS, C.RES_MALLA)
    pila = np.stack(mascaras)
    pila[~np.isin(pila, np.asarray(validos))] = 0
    mask = xr.Dataset({"scm_id": (("time", "lat", "lon"), pila)},
                      coords={"time": tiempos, "lat": lat_r, "lon": lon_r})
    mask.to_netcdf(C.PROC / "scm_mascara.nc", encoding={"scm_id": {"zlib": True}})

    transf = from_origin(C.DOM_ANALISIS[2], C.DOM_ANALISIS[1], C.RES_MALLA, C.RES_MALLA)
    etapas = df.set_index(["scm_id", "time"])["etapa"]
    polis = []
    for t, m_r in zip(tiempos, pila):
        if not m_r.any():
            continue
        for geom, val in features.shapes(m_r, mask=m_r > 0, transform=transf):
            polis.append({"scm_id": int(val), "time": str(t),
                          "etapa": etapas.get((int(val), t), ""), "geometry": shape(geom)})
    if polis:
        gdf = gpd.GeoDataFrame(polis, crs=4326).dissolve(by=["scm_id", "time"], as_index=False)
        gdf.to_file(C.PROC / "scm_poligonos.gpkg", driver="GPKG")
    print("máscara y polígonos listos")


if __name__ == "__main__":
    main()
