"""
Funciones compartidas. Las de las secciones 1–3 solo usan numpy/scipy,
así que se pueden probar sin descargar datos (ver test_utils.py).
"""
import numpy as np
from scipy import ndimage

R_TIERRA_KM = 6371.0


# ============================================================================
# 1. Posición solar (algoritmo de la NOAA, vectorizado; error < 0,5°)
# ============================================================================
def cos_zenit(tiempos_utc, lat, lon):
    """
    tiempos_utc: array de numpy datetime64 (n_t,)
    lat, lon: arrays 2D (ny, nx) en grados
    Devuelve cos(ángulo cenital) con forma (n_t, ny, nx).
    """
    t = np.asarray(tiempos_utc, dtype="datetime64[s]")
    doy = (t.astype("datetime64[D]") - t.astype("datetime64[Y]")).astype(int) + 1
    hora = (t - t.astype("datetime64[D]")).astype(float) / 3600.0
    g = 2 * np.pi / 365.0 * (doy - 1 + (hora - 12) / 24.0)
    ecuacion_tiempo = 229.18 * (0.000075 + 0.001868 * np.cos(g) - 0.032077 * np.sin(g)
                                - 0.014615 * np.cos(2 * g) - 0.040849 * np.sin(2 * g))
    decl = (0.006918 - 0.399912 * np.cos(g) + 0.070257 * np.sin(g)
            - 0.006758 * np.cos(2 * g) + 0.000907 * np.sin(2 * g)
            - 0.002697 * np.cos(3 * g) + 0.00148 * np.sin(3 * g))
    lat_r = np.deg2rad(lat)[None]
    # tiempo solar verdadero (min)
    tst = hora[:, None, None] * 60 + ecuacion_tiempo[:, None, None] + 4 * lon[None]
    ang_horario = np.deg2rad(tst / 4.0 - 180.0)
    d = decl[:, None, None]
    cz = np.sin(lat_r) * np.sin(d) + np.cos(lat_r) * np.cos(d) * np.cos(ang_horario)
    return np.clip(cz, -1, 1)


# ============================================================================
# 2. Índice de nubosidad e índice de cielo despejado (Heliosat-2, Rigollier 2004)
# ============================================================================
def indice_nubosidad(rho, rho_despejado, rho_nube):
    return (rho - rho_despejado) / np.maximum(rho_nube - rho_despejado, 1e-3)


def indice_cielo_despejado(n):
    """Relación empírica Kc(n) de Heliosat-2."""
    n = np.asarray(n, dtype=float)
    kc = np.where(n < -0.2, 1.2,
         np.where(n < 0.8, 1.0 - n,
         np.where(n < 1.1, 2.0667 - 3.6667 * n + 1.6667 * n ** 2, 0.05)))
    return np.where(np.isfinite(n), kc, np.nan)


# ============================================================================
# 3. Identificación y seguimiento de SCM sobre campos de temperatura de brillo
# ============================================================================
def area_pixel_km2(lat, lon):
    """Área aproximada de cada píxel de una malla 2D (lat, lon en grados)."""
    dlat = np.abs(np.gradient(lat, axis=0))
    dlon = np.abs(np.gradient(lon, axis=1))
    dy = np.deg2rad(dlat) * R_TIERRA_KM
    dx = np.deg2rad(dlon) * R_TIERRA_KM * np.cos(np.deg2rad(lat))
    return dx * dy


def objetos_frios(tb, area_pix, tb_escudo, tb_nucleo, area_min):
    """
    Etiqueta escudos nubosos fríos en un instante.
    Devuelve (etiquetas, lista de dicts con propiedades) solo para objetos que
    cumplen área mínima y tienen núcleo convectivo.
    """
    mascara = np.isfinite(tb) & (tb <= tb_escudo)
    etiquetas, n = ndimage.label(mascara, structure=np.ones((3, 3)))
    props = []
    salida = np.zeros_like(etiquetas)
    k = 0
    for i, sl in enumerate(ndimage.find_objects(etiquetas), start=1):
        if sl is None:
            continue
        m = etiquetas[sl] == i
        area = float(area_pix[sl][m].sum())
        tb_min = float(np.nanmin(tb[sl][m]))
        if area < area_min or tb_min > tb_nucleo:
            continue
        k += 1
        salida[sl][m] = k
        props.append({"obj": k, "area_km2": area, "tb_min_k": tb_min,
                      "tb_media_k": float(np.nanmean(tb[sl][m]))})
    return salida, props


class Seguidor:
    """
    Une objetos entre instantes consecutivos por solape espacial, hora a hora
    (guarda solo el instante previo, para no agotar la memoria).
    Regla: un objeto continúa la trayectoria del objeto previo más grande con el
    que se solapa (fracción respecto al menor de los dos >= solape_min). En una
    división, el trozo más grande conserva el id; en una fusión sobrevive el id
    del sistema previo más grande.
    """
    def __init__(self, solape_min):
        self.solape_min = solape_min
        self.siguiente_id = 1
        self.previo = None

    def paso(self, et):
        if et is None:
            self.previo = None
            return None
        previo = self.previo
        tr = np.zeros(et.shape, dtype="int32")
        usados = set()
        for obj in np.unique(et[et > 0]):
            m = et == obj
            asignado = None
            if previo is not None:
                ids_prev, cuentas = np.unique(previo[m & (previo > 0)], return_counts=True)
                mejor, mejor_tam = None, 0
                for idp, c in zip(ids_prev, cuentas):
                    tam_prev = int((previo == idp).sum())
                    if c / min(tam_prev, int(m.sum())) >= self.solape_min and tam_prev > mejor_tam:
                        mejor, mejor_tam = int(idp), tam_prev
                if mejor is not None and mejor not in usados:
                    asignado = mejor
                elif mejor is not None and m.sum() > (tr == mejor).sum():
                    tr[tr == mejor] = self.siguiente_id   # el trozo menor recibe id nuevo
                    usados.add(self.siguiente_id)
                    self.siguiente_id += 1
                    asignado = mejor
            if asignado is None:
                asignado = self.siguiente_id
                self.siguiente_id += 1
            usados.add(asignado)
            tr[m] = asignado
        self.previo = tr
        return tr


def seguir_objetos(lista_etiquetas, solape_min):
    """Versión por lotes (para pruebas): lista de etiquetas → lista de trayectorias."""
    s = Seguidor(solape_min)
    return [s.paso(et) for et in lista_etiquetas]


def etapa_ciclo_vida(areas):
    """
    Clasifica cada hora de una trayectoria según su área:
    'iniciación' antes del 80 % del área máxima, 'madurez' mientras el área
    está por encima del 80 % del máximo, 'disipación' después.
    """
    a = np.asarray(areas, dtype=float)
    umbral = 0.8 * a.max()
    sobre = np.where(a >= umbral)[0]
    i0, i1 = sobre.min(), sobre.max()
    etapas = np.array(["madurez"] * len(a), dtype=object)
    etapas[:i0] = "iniciación"
    etapas[i1 + 1:] = "disipación"
    return etapas.tolist()


# ============================================================================
# 4. Proyección de la malla fija de GOES (requiere pyproj)
# ============================================================================
def proyeccion_goes(ds):
    from pyproj import Proj
    p = ds["goes_imager_projection"].attrs
    h = float(p["perspective_point_height"])
    proj = Proj(proj="geos", h=h, lon_0=float(p["longitude_of_projection_origin"]),
                a=float(p["semi_major_axis"]), b=float(p["semi_minor_axis"]),
                sweep=str(p["sweep_angle_axis"]))
    return proj, h


def indices_dominio(ds, dominio, n=60):
    """Índices (y0, y1, x0, x1) de la malla fija que cubren el dominio lat/lon."""
    proj, h = proyeccion_goes(ds)
    la0, la1, lo0, lo1 = dominio
    lats = np.r_[np.linspace(la0, la1, n), np.linspace(la0, la1, n),
                 np.full(n, la0), np.full(n, la1)]
    lons = np.r_[np.full(n, lo0), np.full(n, lo1),
                 np.linspace(lo0, lo1, n), np.linspace(lo0, lo1, n)]
    xm, ym = proj(lons, lats)
    xr_, yr_ = np.asarray(xm) / h, np.asarray(ym) / h
    x = ds["x"].values
    y = ds["y"].values
    xi = np.where((x >= xr_.min()) & (x <= xr_.max()))[0]
    yi = np.where((y >= yr_.min()) & (y <= yr_.max()))[0]
    return int(yi.min()), int(yi.max()) + 1, int(xi.min()), int(xi.max()) + 1


def latlon_subconjunto(ds_sub):
    proj, h = proyeccion_goes(ds_sub)
    X, Y = np.meshgrid(ds_sub["x"].values * h, ds_sub["y"].values * h)
    lon, lat = proj(X, Y, inverse=True)
    lon = np.where(np.abs(lon) > 360, np.nan, lon)
    lat = np.where(np.abs(lat) > 90, np.nan, lat)
    return np.asarray(lat), np.asarray(lon)


def malla_regular(dominio, res):
    """Centros de píxel de la malla regular (norte→sur, oeste→este), igual a dem_2km.tif."""
    la0, la1, lo0, lo1 = dominio
    ny, nx = int(round((la1 - la0) / res)), int(round((lo1 - lo0) / res))
    return la1 - res * (np.arange(ny) + 0.5), lo0 + res * (np.arange(nx) + 0.5)


_cache_remuestreo = {}


def a_malla_regular(campo, lat, lon, dominio, res):
    """Remuestrea (vecino más cercano) un campo 2D de malla GOES a malla lat/lon regular.
    Los índices se calculan una sola vez por malla de origen y se reutilizan (rápido)."""
    from scipy.spatial import cKDTree
    lats_r, lons_r = malla_regular(dominio, res)
    clave = (lat.shape, float(np.nanmean(lat)), float(np.nanmean(lon)), tuple(dominio), res)
    if clave not in _cache_remuestreo:
        LO, LA = np.meshgrid(lons_r, lats_r)
        ok = np.isfinite(lat) & np.isfinite(lon)
        arbol = cKDTree(np.c_[lat[ok], lon[ok]])
        dist, idx = arbol.query(np.c_[LA.ravel(), LO.ravel()])
        _cache_remuestreo[clave] = (ok, idx, (dist > 2 * res).reshape(LA.shape), LA.shape)
    ok, idx, lejos, forma = _cache_remuestreo[clave]
    vals = np.asarray(campo)[ok][idx].reshape(forma).astype("float64")
    vals[lejos] = np.nan
    return vals, lats_r, lons_r
