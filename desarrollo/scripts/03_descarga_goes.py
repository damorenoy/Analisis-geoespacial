"""
Paso 3 — Datos tipo SUPERFICIE: imágenes GOES-Este (ABI), una por hora.
  - Canal 13 (10,3 µm, ~2 km): temperatura de brillo → identificar SCM.
  - Canal 2  (0,64 µm, ~0,5 km): reflectancia visible → irradiancia en superficie.
Fuente: buckets públicos de NOAA en AWS (noaa-goes16 / noaa-goes19), sin registro.
Solo se leen los bloques del archivo que cubren el dominio (no el disco completo).

Salidas (una por día):
  datos/crudos/tb/tb_YYYYMMDD.nc       dominio de seguimiento, 24 h
  datos/crudos/vis/vis_YYYYMMDD.nc     dominio de análisis, 6–18 h local,
                                       promediado a ~2 km (alineado con el canal 13)
Uso:  python 03_descarga_goes.py            (ambos canales)
      python 03_descarga_goes.py tb         (solo canal 13)
Si se interrumpe, vuelve a correrlo: salta los días ya descargados.
"""
import re
import sys
from datetime import timedelta
import numpy as np
import xarray as xr
import s3fs
import config as C
from utils import indices_dominio, latlon_subconjunto

fs = s3fs.S3FileSystem(anon=True)
_cache_idx = {}


def satelite(dt):
    return ("noaa-goes19", "G19") if dt >= C.CAMBIO_GOES19 else ("noaa-goes16", "G16")


def archivo_hora(dt, canal):
    bucket, _ = satelite(dt)
    ruta = f"{bucket}/ABI-L2-CMIPF/{dt:%Y}/{dt:%j}/{dt:%H}/"
    try:
        arch = [a for a in fs.ls(ruta) if re.search(rf"M\dC{canal:02d}_", a)]
    except FileNotFoundError:
        return None
    if not arch:
        return None
    # el escaneo que empieza más cerca de la hora en punto
    minuto = lambda a: int(re.search(r"_s\d{9}(\d{2})", a).group(1))
    return sorted(arch, key=minuto)[0]


def leer(dt, canal, dominio, factor=1):
    a = archivo_hora(dt, canal)
    if a is None:
        return None
    with fs.open(a, "rb") as f, xr.open_dataset(f, engine="h5netcdf") as ds:
        clave = (satelite(dt)[1], canal, dominio)
        if clave not in _cache_idx:
            if factor == 1:
                _cache_idx[clave] = indices_dominio(ds, dominio)
            else:   # canal 2: índices anidados en la malla de 2 km del canal 13
                y0, y1, x0, x1 = _cache_idx[(satelite(dt)[1], 13, dominio)]
                _cache_idx[clave] = (y0 * factor, y1 * factor, x0 * factor, x1 * factor)
        y0, y1, x0, x1 = _cache_idx[clave]
        sub = ds.isel(y=slice(y0, y1), x=slice(x0, x1))
        cmi = sub["CMI"].values.astype("float32")
        if factor > 1:   # promedio en bloques factor×factor → ~2 km
            ny, nx = cmi.shape[0] // factor, cmi.shape[1] // factor
            cmi = np.nanmean(cmi[:ny * factor, :nx * factor]
                             .reshape(ny, factor, nx, factor), axis=(1, 3))
            sub = sub.isel(y=slice(0, None, factor), x=slice(0, None, factor))
            sub = sub.isel(y=slice(0, ny), x=slice(0, nx))
        lat, lon = latlon_subconjunto(sub)
    return cmi, lat, lon


def asegurar_indices_c13(dt, dominio):
    clave = (satelite(dt)[1], 13, dominio)
    if clave not in _cache_idx:
        leer(dt, 13, dominio)


def descargar(tipo):
    dia = C.FECHA_INICIO
    while dia <= C.FECHA_FIN:
        destino = C.RAW / tipo / f"{tipo}_{dia:%Y%m%d}.nc"
        destino.parent.mkdir(parents=True, exist_ok=True)
        if destino.exists():
            dia += timedelta(days=1); continue
        horas = C.HORAS_TB if tipo == "tb" else C.HORAS_VIS
        dominio = C.DOM_SEGUIMIENTO if tipo == "tb" else C.DOM_ANALISIS
        campos, tiempos, lat, lon = [], [], None, None
        for h in horas:
            dt = dia + timedelta(hours=h)
            try:
                if tipo == "tb":
                    r = leer(dt, 13, dominio)
                else:
                    asegurar_indices_c13(dt, dominio)
                    r = leer(dt, 2, dominio, factor=4)
            except Exception as e:
                print("  error", dt, e); r = None
            if r is None:
                print("  falta", dt); continue
            campo, lat, lon = r
            campos.append(campo); tiempos.append(np.datetime64(dt))
        if campos:
            var = "tb" if tipo == "tb" else "reflectancia"
            ds = xr.Dataset({var: (("time", "y", "x"), np.stack(campos))},
                            coords={"time": tiempos, "lat": (("y", "x"), lat),
                                    "lon": (("y", "x"), lon)})
            ds.to_netcdf(destino, encoding={var: {"zlib": True, "complevel": 4}})
            print(f"{destino.name}: {len(campos)} horas")
        dia += timedelta(days=1)


if __name__ == "__main__":
    tipos = sys.argv[1:] or ["tb", "vis"]
    for t in tipos:
        descargar(t)
