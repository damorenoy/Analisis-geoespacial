"""
Paso 8 — Análisis geoespacial y resultados.
SUPERFICIES (GeoTIFF, malla ~2 km):
  frecuencia_scm_diurna   fracción de horas de sol con un SCM encima
  kc_medio_con_scm / kc_medio_sin_scm
  perdida_relativa        1 − Kc(con SCM)/Kc(sin SCM)
  deficit_energetico      % de la energía solar anual "perdida" por SCM
ÁREAS: estadística zonal por municipio + autocorrelación espacial (I de Moran,
        LISA y Getis-Ord Gi*) → resultados/municipios_resultados.gpkg
PUNTOS: parques → pérdida por distancia al SCM, por etapa del ciclo de vida y
        ciclo diurno → figuras PNG.
RELIEVE: frecuencia de SCM vs. altitud (DEM).
GENERACIÓN REAL (XM): validación de la estimación satelital y pérdida real
        de factor de planta bajo SCM (misma hora del día, con vs. sin SCM).
"""
import numpy as np
import pandas as pd
import xarray as xr
import geopandas as gpd
import rasterio
from rasterio import features
from rasterio.transform import from_origin
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import libpysal
from esda.moran import Moran, Moran_Local
from esda.getisord import G_Local
import config as C

TRANSF = from_origin(C.DOM_ANALISIS[2], C.DOM_ANALISIS[1], C.RES_MALLA, C.RES_MALLA)


def guardar_tif(nombre, arr):
    with rasterio.open(C.OUT / f"{nombre}.tif", "w", driver="GTiff", height=arr.shape[0],
                       width=arr.shape[1], count=1, dtype="float32", crs="EPSG:4326",
                       transform=TRANSF, nodata=np.nan, compress="lzw") as dst:
        dst.write(arr.astype("float32"), 1)


def superficies():
    irr = xr.open_mfdataset(sorted(C.PROC.glob("irradiancia_*.nc")))
    mask = xr.open_dataset(C.PROC / "scm_mascara.nc")["scm_id"]
    t = np.intersect1d(irr.time.values, mask.time.values)
    kc = irr["kc"].sel(time=t).values
    gcs = irr["ghi_despejado"].sel(time=t).values
    con = mask.sel(time=t).values > 0
    dia = np.isfinite(kc)
    with np.errstate(invalid="ignore", divide="ignore"):
        frec = (con & dia).sum(0) / dia.sum(0)
        kc_con = np.nanmean(np.where(con, kc, np.nan), axis=0)
        kc_sin = np.nanmean(np.where(~con, kc, np.nan), axis=0)
        perdida = 1 - kc_con / kc_sin
        # déficit: energía que habría llegado con el Kc típico sin SCM de esa hora
        horas = pd.DatetimeIndex(t).hour
        kc_ref = np.empty_like(kc)
        for h in np.unique(horas):
            s = horas == h
            kc_ref[s] = np.nanmean(np.where(~con[s], kc[s], np.nan), axis=0)
        e_ref = np.nansum(kc_ref * gcs, axis=0)
        e_perdida = np.nansum(np.where(con, kc_ref * gcs - kc * gcs, 0), axis=0)
        deficit = 100 * e_perdida / e_ref
    salida = {"frecuencia_scm_diurna": frec, "kc_medio_con_scm": kc_con,
              "kc_medio_sin_scm": kc_sin, "perdida_relativa": perdida,
              "deficit_energetico": deficit}
    for k, v in salida.items():
        guardar_tif(k, v)
    # ciclo diurno de la frecuencia de SCM sobre la región (24 h, canal 13)
    m_all = mask.values > 0
    hl = (pd.DatetimeIndex(mask.time.values) - pd.Timedelta(hours=5)).hour
    ciclo = pd.Series(m_all.mean(axis=(1, 2)), index=hl).groupby(level=0).mean()
    ax = ciclo.plot(kind="bar", figsize=(9, 4), color="#3D6E8F")
    ax.set_xlabel("Hora local"); ax.set_ylabel("Fracción del dominio bajo SCM")
    plt.tight_layout(); plt.savefig(C.OUT / "ciclo_diurno_scm.png", dpi=150); plt.close()
    return salida


def zonal_y_autocorrelacion(sup):
    mpios = gpd.read_file(C.PROC / "municipios.gpkg").reset_index(drop=True)
    shape = next(iter(sup.values())).shape
    ids = features.rasterize(((g, i + 1) for i, g in enumerate(mpios.geometry)),
                             out_shape=shape, transform=TRANSF, fill=0, all_touched=True)
    for k, v in sup.items():
        df = pd.DataFrame({"id": ids.ravel(), "v": v.ravel()}).query("id > 0")
        medias = df.groupby("id")["v"].mean()
        mpios[k] = mpios.index.map(lambda i: medias.get(i + 1, np.nan))
    var = "deficit_energetico"
    mp = mpios.dropna(subset=[var]).copy()
    w = libpysal.weights.Queen.from_dataframe(mp, use_index=False)
    w.transform = "r"
    mi = Moran(mp[var].values, w)
    print(f"I de Moran ({var}) = {mi.I:.3f}, p = {mi.p_sim:.3f}")
    lisa = Moran_Local(mp[var].values, w)
    cuad = {1: "Alto-Alto", 2: "Bajo-Alto", 3: "Bajo-Bajo", 4: "Alto-Bajo"}
    mp["lisa"] = [cuad[q] if p < 0.05 else "No significativo" for q, p in zip(lisa.q, lisa.p_sim)]
    gi = G_Local(mp[var].values, w, star=True)
    mp["gi_z"] = gi.Zs
    mp["gi_p"] = gi.p_sim
    mp.to_file(C.OUT / "municipios_resultados.gpkg", driver="GPKG")
    fig, axs = plt.subplots(1, 2, figsize=(14, 7))
    mp.plot(var, ax=axs[0], legend=True, cmap="YlOrRd", edgecolor="0.6", linewidth=0.3)
    axs[0].set_title("Déficit de energía solar por SCM (%)")
    mp.plot("gi_z", ax=axs[1], legend=True, cmap="RdBu_r", edgecolor="0.6", linewidth=0.3)
    axs[1].set_title("Puntos calientes (Getis-Ord Gi*, z)")
    parques = gpd.read_file(C.PROC / "parques.gpkg")
    for ax in axs:
        parques.plot(ax=ax, color="black", marker="^", markersize=50)
        ax.set_axis_off()
    plt.tight_layout(); plt.savefig(C.OUT / "mapa_municipios.png", dpi=150); plt.close()
    pd.DataFrame({"I_Moran": [mi.I], "p": [mi.p_sim]}).to_csv(C.OUT / "moran.csv", index=False)


def relieve(sup):
    with rasterio.open(C.PROC / "dem_2km.tif") as src:
        z = src.read(1)
    df = pd.DataFrame({"z": z.ravel(), "f": sup["frecuencia_scm_diurna"].ravel(),
                       "d": sup["deficit_energetico"].ravel()}).dropna()
    df["banda"] = pd.cut(df.z, [-50, 250, 500, 1000, 1500, 2000, 2500, 4000])
    res = df.groupby("banda", observed=True)[["f", "d"]].mean()
    res.to_csv(C.OUT / "scm_vs_altitud.csv")
    ax = res["d"].plot(kind="bar", figsize=(8, 4), color="#E0A526")
    ax.set_xlabel("Altitud (m s.n.m.)"); ax.set_ylabel("Déficit energético por SCM (%)")
    plt.tight_layout(); plt.savefig(C.OUT / "deficit_vs_altitud.png", dpi=150); plt.close()


def parques():
    f = C.PROC / "fv_parques_horario.csv"
    if not f.exists():
        return
    d = pd.read_csv(f).dropna(subset=["kc"])
    d["rango_dist"] = pd.cut(d.dist_scm_km, [-1, 0, 25, 50, 100, 200, np.inf],
                             labels=["bajo SCM", "0–25", "25–50", "50–100", "100–200", ">200 km"])
    tab = d.groupby(["parque", "rango_dist"], observed=True)["kc"].mean().unstack(0)
    tab.to_csv(C.OUT / "kc_por_distancia_scm.csv")
    tab.plot(marker="o", figsize=(9, 4)); plt.ylabel("Kc medio")
    plt.tight_layout(); plt.savefig(C.OUT / "kc_por_distancia.png", dpi=150); plt.close()
    et = d[d.bajo_scm].groupby(["parque", "etapa"])["kc"].mean().unstack(0)
    et.to_csv(C.OUT / "kc_por_etapa_scm.csv")
    d["hora_local"] = (pd.to_datetime(d["time"]) - pd.Timedelta(hours=5)).dt.hour
    cic = d.groupby(["hora_local", "bajo_scm"])["p_ac_mw"].mean().unstack()
    cic.to_csv(C.OUT / "ciclo_diurno_fv.csv")
    print(tab.round(3)); print(et.round(3))


def validacion_y_perdida_real():
    """
    Con la generación REAL de XM:
      1. Valida la generación estimada desde satélite (sesgo, RMSE, correlación).
      2. Mide la pérdida real: factor de planta con y sin SCM encima, y por distancia.
    """
    fx, ff = C.PROC / "xm_generacion_horaria.csv", C.PROC / "fv_parques_horario.csv"
    if not (fx.exists() and ff.exists()):
        print("sin datos de XM: se omite la validación"); return
    xm = pd.read_csv(fx, parse_dates=["time"])
    fv = pd.read_csv(ff)
    fv["time"] = pd.to_datetime(fv["time"], utc=True).dt.tz_convert(None)
    cap = pd.read_csv(C.ARCHIVO_PARQUES).set_index("nombre")["capacidad_mw"]
    filas, unidos = [], []
    for parque, f in fv.groupby("parque"):
        f = f.set_index("time").sort_index()
        # XM da energía del intervalo [t, t+1h); GOES es instantáneo → promedio de t y t+1h
        est = (f["p_ac_mw"] + f["p_ac_mw"].shift(-1, freq="h").reindex(f.index)) / 2
        d = xm[xm.parque == parque].set_index("time").join(
            pd.DataFrame({"estimado_mwh": est, "bajo_scm": f["bajo_scm"],
                          "dist_scm_km": f["dist_scm_km"], "etapa": f["etapa"]}), how="inner")
        d = d.dropna(subset=["energia_mwh", "estimado_mwh"])
        if d.empty:
            continue
        d["parque"] = parque
        d["factor_planta"] = d["energia_mwh"] / cap[parque]
        err = d["estimado_mwh"] - d["energia_mwh"]
        # pérdida real comparando la MISMA hora del día con y sin SCM
        d["hora_local"] = (d.index - pd.Timedelta(hours=5)).hour
        por_hora = d.groupby(["hora_local", d.bajo_scm.astype(bool)])["factor_planta"].mean().unstack()
        n_con = d[d.bajo_scm.astype(bool)].groupby("hora_local").size()
        perdida = np.nan
        if True in por_hora and False in por_hora:
            r = (1 - por_hora[True] / por_hora[False]).dropna()
            w = n_con.reindex(r.index).fillna(0)
            perdida = 100 * float((r * w).sum() / w.sum()) if w.sum() > 0 else np.nan
        filas.append({"parque": parque, "n_horas": len(d), "n_horas_bajo_scm": int(n_con.sum()),
                      "sesgo_mwh": err.mean(), "rmse_mwh": np.sqrt((err ** 2).mean()),
                      "r": d["estimado_mwh"].corr(d["energia_mwh"]),
                      "perdida_real_%": perdida})
        unidos.append(d)
        plt.figure(figsize=(5, 5))
        plt.scatter(d["energia_mwh"], d["estimado_mwh"], s=6, alpha=0.4,
                    c=np.where(d.bajo_scm.astype(bool), "#B5810F", "#3D6E8F"))
        lim = [0, max(d["energia_mwh"].max(), d["estimado_mwh"].max())]
        plt.plot(lim, lim, "k--", lw=1)
        plt.xlabel("Generación real XM (MWh)"); plt.ylabel("Estimada desde GOES (MWh)")
        plt.title(f"{parque}\n(naranja = bajo SCM)")
        plt.tight_layout(); plt.savefig(C.OUT / f"validacion_{parque[:20].replace(' ', '_')}.png", dpi=150)
        plt.close()
    if not filas:
        return
    res = pd.DataFrame(filas)
    res.to_csv(C.OUT / "validacion_y_perdida_real.csv", index=False)
    print(res.round(3).to_string())
    todo = pd.concat(unidos)
    todo["rango_dist"] = pd.cut(todo.dist_scm_km, [-1, 0, 25, 50, 100, 200, np.inf],
                                labels=["bajo SCM", "0–25", "25–50", "50–100", "100–200", ">200 km"])
    todo.groupby(["parque", "rango_dist"], observed=True)["factor_planta"].mean() \
        .unstack(0).to_csv(C.OUT / "factor_planta_por_distancia_scm.csv")
    todo[todo.bajo_scm.astype(bool)].groupby(["parque", "etapa"])["factor_planta"].mean() \
        .unstack(0).to_csv(C.OUT / "factor_planta_por_etapa_scm.csv")


if __name__ == "__main__":
    s = superficies()
    zonal_y_autocorrelacion(s)
    relieve(s)
    parques()
    validacion_y_perdida_real()
    print("Resultados en", C.OUT)
