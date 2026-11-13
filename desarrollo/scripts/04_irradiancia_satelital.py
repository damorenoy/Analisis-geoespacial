"""
Paso 4 — Irradiancia global horizontal (GHI) desde el canal visible de GOES.
Método de índice de nubosidad (tipo Heliosat-2):
  1. ρ* = reflectancia / cos(z)         (normaliza por la altura del sol)
  2. ρ_despejado: percentil bajo de ρ* por píxel, hora y mes (superficie sin nubes)
     ρ_nube: percentil alto de ρ* en todo el dominio (nube densa)
  3. n  = (ρ* − ρ_despejado) / (ρ_nube − ρ_despejado)   índice de nubosidad
  4. Kc = f(n)                                          índice de cielo despejado
  5. GHI = Kc × GHI_despejado (modelo Ineichen; usa la ALTITUD del DEM)
Salida: datos/procesados/irradiancia_YYYYMM.nc en la malla regular (~2 km)
con kc, ghi y ghi_despejado.
Requiere: 02_dem.py y 03_descarga_goes.py (vis).
"""
import numpy as np
import pandas as pd
import xarray as xr
import rasterio
import pvlib
import config as C
from utils import cos_zenit, indice_nubosidad, indice_cielo_despejado, a_malla_regular, malla_regular


def ghi_despejado(tiempos, lat2d, lon2d, altitud):
    """Ineichen–Perez, vectorizado sobre la malla."""
    cz = cos_zenit(tiempos, lat2d, lon2d)
    zen = np.degrees(np.arccos(np.clip(cz, -1, 1)))
    am_rel = pvlib.atmosphere.get_relative_airmass(zen)
    presion = pvlib.atmosphere.alt2pres(np.nan_to_num(altitud, nan=0.0))[None]
    am_abs = pvlib.atmosphere.get_absolute_airmass(am_rel, presion)
    # turbidez de Linke climatológica en el centro del dominio, por mes
    la0, la1, lo0, lo1 = C.DOM_ANALISIS
    idx = pd.DatetimeIndex(tiempos)
    tl = pvlib.clearsky.lookup_linke_turbidity(idx, (la0 + la1) / 2, (lo0 + lo1) / 2).values
    dni_extra = pvlib.irradiance.get_extra_radiation(idx).values
    cs = pvlib.clearsky.ineichen(zen, am_abs, tl[:, None, None],
                                 altitude=np.nan_to_num(altitud, nan=0.0)[None],
                                 dni_extra=dni_extra[:, None, None])
    ghi = np.where(zen < 90, cs["ghi"], 0.0)
    return ghi, zen


def procesar_mes(archivos, altitud, lat_r, lon_r):
    ds = xr.open_mfdataset(archivos, combine="nested", concat_dim="time",
                           coords="minimal", compat="override")
    lat, lon = ds["lat"].values, ds["lon"].values
    if lat.ndim == 3:
        lat, lon = lat[0], lon[0]
    t = ds["time"].values
    rho = ds["reflectancia"].values
    cz = cos_zenit(t, lat, lon)
    zen = np.degrees(np.arccos(cz))
    rho_n = np.where(zen < C.ZENIT_MAX, rho / np.maximum(cz, 0.05), np.nan)

    horas = pd.DatetimeIndex(t).hour
    rho_desp = np.full_like(rho_n, np.nan)
    for h in np.unique(horas):
        sel = horas == h
        rho_desp[sel] = np.nanpercentile(rho_n[sel], C.PERCENTIL_CIELO_DESPEJADO, axis=0)
    rho_nube = np.nanpercentile(rho_n, C.PERCENTIL_NUBE)
    kc_goes = indice_cielo_despejado(indice_nubosidad(rho_n, rho_desp, rho_nube))

    LO, LA = np.meshgrid(lon_r, lat_r)
    kc = np.stack([a_malla_regular(k, lat, lon, C.DOM_ANALISIS, C.RES_MALLA)[0] for k in kc_goes])
    gcs, zen_r = ghi_despejado(t, LA, LO, altitud)
    kc = np.where(zen_r < C.ZENIT_MAX, kc, np.nan)
    ghi = kc * gcs
    return xr.Dataset(
        {"kc": (("time", "lat", "lon"), kc.astype("float32")),
         "ghi": (("time", "lat", "lon"), ghi.astype("float32")),
         "ghi_despejado": (("time", "lat", "lon"), gcs.astype("float32"))},
        coords={"time": t, "lat": lat_r, "lon": lon_r},
        attrs={"metodo": "Heliosat-2 simplificado + Ineichen con altitud del DEM"})


def main():
    with rasterio.open(C.PROC / "dem_2km.tif") as src:
        altitud = src.read(1)
    lat_r, lon_r = malla_regular(C.DOM_ANALISIS, C.RES_MALLA)
    archivos = sorted((C.RAW / "vis").glob("vis_*.nc"))
    meses = sorted({a.stem[4:10] for a in archivos})
    for m in meses:
        destino = C.PROC / f"irradiancia_{m}.nc"
        if destino.exists():
            continue
        ds = procesar_mes([a for a in archivos if a.stem[4:10] == m], altitud, lat_r, lon_r)
        ds.to_netcdf(destino, encoding={v: {"zlib": True} for v in ds.data_vars})
        print("listo", destino.name)


if __name__ == "__main__":
    main()
