"""
Paso 2 — Datos tipo SUPERFICIE: Modelo Digital de Elevación (DEM).
Copernicus GLO-30 (30 m), bucket público de AWS, sin registro.
Produce:
  dem_region_30m.tif        (para mapas y pendiente/orientación)
  pendiente_grados.tif, orientacion_grados.tif
  dem_2km.tif               (remuestreado a la malla de análisis)

¿Para qué sirve el DEM en este trabajo?
  1. La altitud entra al modelo de irradiancia de cielo despejado (Ineichen):
     en el Magdalena hay de 0 m (planicie y ciénagas) a ~5.700 m (Sierra Nevada
     de Santa Marta), y eso cambia la irradiancia máxima.
  2. Relacionar dónde nacen/se intensifican los SCM con el relieve
     (Sierra Nevada, serranía del Perijá, valle del río Magdalena).
  3. Pendiente y orientación: aptitud de terreno para nuevos parques.
Alternativa: SRTM 1 arc-sec (USGS EarthExplorer), como en otros trabajos del curso.
"""
import numpy as np
import rasterio
from rasterio.merge import merge
from rasterio.mask import mask
from rasterio.warp import reproject, Resampling, calculate_default_transform
from rasterio.transform import from_origin
import geopandas as gpd
import config as C

URL = ("https://copernicus-dem-30m.s3.amazonaws.com/"
       "Copernicus_DSM_COG_10_{ns}{lat:02d}_00_{ew}{lon:03d}_00_DEM/"
       "Copernicus_DSM_COG_10_{ns}{lat:02d}_00_{ew}{lon:03d}_00_DEM.tif")


def teselas(dominio):
    la0, la1, lo0, lo1 = dominio
    for lat in range(int(np.floor(la0)), int(np.ceil(la1))):
        for lon in range(int(np.floor(lo0)), int(np.ceil(lo1))):
            yield URL.format(ns="N" if lat >= 0 else "S", lat=abs(lat),
                             ew="W" if lon < 0 else "E", lon=abs(lon))


def main():
    fuentes = []
    for u in teselas(C.DOM_ANALISIS):
        try:
            fuentes.append(rasterio.open(u))
            print("ok", u.split("/")[-1])
        except Exception:
            print("sin tesela (mar):", u.split("/")[-1])
    mosaico, transf = merge(fuentes)
    perfil = fuentes[0].profile | {"height": mosaico.shape[1], "width": mosaico.shape[2],
                                   "transform": transf, "driver": "GTiff", "compress": "lzw",
                                   "tiled": True, "nodata": -9999}
    tmp = C.RAW / "dem_mosaico.tif"
    with rasterio.open(tmp, "w", **perfil) as dst:
        dst.write(mosaico)

    region = gpd.read_file(C.PROC / "region.gpkg").to_crs(4326)
    with rasterio.open(tmp) as src:
        rec, t2 = mask(src, region.geometry.buffer(0.05), crop=True, nodata=-9999)
        perfil.update(height=rec.shape[1], width=rec.shape[2], transform=t2)
    with rasterio.open(C.PROC / "dem_region_30m.tif", "w", **perfil) as dst:
        dst.write(rec)

    # Pendiente y orientación en un sistema métrico (MAGNA-SIRGAS Origen Nacional)
    with rasterio.open(C.PROC / "dem_region_30m.tif") as src:
        dst_crs = "EPSG:9377"
        t, w, h = calculate_default_transform(src.crs, dst_crs, src.width, src.height,
                                              *src.bounds, resolution=30)
        z = np.full((h, w), np.nan, dtype="float32")
        reproject(rasterio.band(src, 1), z, dst_transform=t, dst_crs=dst_crs,
                  resampling=Resampling.bilinear, dst_nodata=np.nan)
    gy, gx = np.gradient(z, 30.0)
    pendiente = np.degrees(np.arctan(np.hypot(gx, gy)))
    orientacion = (np.degrees(np.arctan2(-gx, gy)) + 360) % 360
    pm = {"driver": "GTiff", "height": h, "width": w, "count": 1, "dtype": "float32",
          "crs": dst_crs, "transform": t, "nodata": np.nan, "compress": "lzw"}
    for nombre, arr in (("pendiente_grados", pendiente), ("orientacion_grados", orientacion)):
        with rasterio.open(C.PROC / f"{nombre}.tif", "w", **pm) as dst:
            dst.write(arr.astype("float32"), 1)

    # DEM promedio a la malla regular de análisis (~2 km)
    la0, la1, lo0, lo1 = C.DOM_ANALISIS
    res = C.RES_MALLA
    ny, nx = int(round((la1 - la0) / res)), int(round((lo1 - lo0) / res))
    t2km = from_origin(lo0, la1, res, res)
    z2 = np.full((ny, nx), np.nan, dtype="float32")
    with rasterio.open(tmp) as src:
        reproject(rasterio.band(src, 1), z2, dst_transform=t2km, dst_crs="EPSG:4326",
                  resampling=Resampling.average, src_nodata=-9999, dst_nodata=np.nan)
    with rasterio.open(C.PROC / "dem_2km.tif", "w", driver="GTiff", height=ny, width=nx,
                       count=1, dtype="float32", crs="EPSG:4326", transform=t2km,
                       nodata=np.nan) as dst:
        dst.write(z2, 1)
    print("DEM listo en", C.PROC)


if __name__ == "__main__":
    main()
