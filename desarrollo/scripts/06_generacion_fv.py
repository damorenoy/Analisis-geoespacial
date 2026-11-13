"""
Paso 6 — Generación fotovoltaica estimada en cada parque (datos tipo PUNTO).
Con la GHI satelital del píxel del parque:
  GHI → (Erbs) DNI y DHI → irradiancia en el plano del panel → PVWatts (DC) → AC.
También marca, para cada hora, si el parque está bajo un SCM, la distancia al
SCM más cercano y su etapa del ciclo de vida.
Salida: datos/procesados/fv_parques_horario.csv
"""
import numpy as np
import pandas as pd
import xarray as xr
import geopandas as gpd
import pvlib
from scipy import ndimage
import config as C


def main():
    irr = xr.open_mfdataset(sorted(C.PROC.glob("irradiancia_*.nc")))
    mask = xr.open_dataset(C.PROC / "scm_mascara.nc")["scm_id"]
    tray = pd.read_csv(C.PROC / "scm_trayectorias.csv", parse_dates=["time"])
    etapa = tray.set_index(["scm_id", "time"])["etapa"]
    parques = gpd.read_file(C.PROC / "parques.gpkg")
    km_por_pix = C.RES_MALLA * 111.0

    # distancia (km) de cada píxel al SCM más cercano, por hora
    t_comun = np.intersect1d(irr.time.values, mask.time.values)
    m = mask.sel(time=t_comun).values
    dist = np.stack([ndimage.distance_transform_edt(mi == 0) * km_por_pix if mi.any()
                     else np.full(mi.shape, np.inf) for mi in m])

    salidas = []
    for _, p in parques.iterrows():
        sel = dict(lat=p.lat, lon=p.lon, method="nearest")
        s = irr.sel(**sel).sel(time=t_comun).to_dataframe()[["kc", "ghi", "ghi_despejado"]]
        s.index = pd.DatetimeIndex(s.index).tz_localize("UTC")
        sol = pvlib.solarposition.get_solarposition(s.index, p.lat, p.lon)
        dec = pvlib.irradiance.erbs(s.ghi.fillna(0), sol.zenith, s.index)
        poa = pvlib.irradiance.get_total_irradiance(C.INCLINACION, C.AZIMUT, sol.apparent_zenith,
                                                    sol.azimuth, dec["dni"], s.ghi.fillna(0), dec["dhi"])
        tcel = pvlib.temperature.faiman(poa["poa_global"], C.T_AIRE_C, C.VIENTO_MS)
        pdc = pvlib.pvsystem.pvwatts_dc(poa["poa_global"], tcel, p.capacidad_mw, C.GAMMA_PDC)
        s["p_ac_mw"] = np.clip(pdc * C.EFIC_INVERSOR, 0, p.capacidad_mw).where(s.ghi.notna())
        iy = int(np.abs(irr.lat.values - p.lat).argmin()); ix = int(np.abs(irr.lon.values - p.lon).argmin())
        s["scm_id"] = m[:, iy, ix]
        s["bajo_scm"] = s["scm_id"] > 0
        s["dist_scm_km"] = dist[:, iy, ix]
        s["etapa"] = [etapa.get((int(i), t.tz_localize(None)), "") if i > 0 else ""
                      for i, t in zip(s.scm_id, s.index)]
        s["parque"] = p.nombre
        salidas.append(s.reset_index())
    out = pd.concat(salidas)
    out.to_csv(C.PROC / "fv_parques_horario.csv", index=False)
    print(out.groupby(["parque", "bajo_scm"])["kc"].mean().unstack())


if __name__ == "__main__":
    main()
