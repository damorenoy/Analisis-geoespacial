"""
Pruebas con datos sintéticos (no requieren internet).
Ejecuta:  python test_utils.py
"""
import numpy as np
from utils import (cos_zenit, indice_cielo_despejado, area_pixel_km2,
                   objetos_frios, seguir_objetos, etapa_ciclo_vida)


def test_sol():
    lat = np.array([[6.25]]); lon = np.array([[-75.57]])   # Medellín
    t = np.array(["2024-03-20T17:00", "2024-03-20T12:00", "2024-03-20T05:00"],
                 dtype="datetime64[s]")
    cz = cos_zenit(t, lat, lon)[:, 0, 0]
    # 17 UTC = mediodía local aprox: sol casi en el cenit en equinoccio
    assert cz[0] > 0.98, cz
    assert 0 < cz[1] < 0.35, cz            # amanecer
    assert cz[2] < 0, cz                  # noche
    print("posición solar OK", np.round(cz, 3))


def test_kc():
    kc = indice_cielo_despejado(np.array([-0.5, 0.0, 0.5, 0.9, 1.5, np.nan]))
    assert np.allclose(kc[:5], [1.2, 1.0, 0.5, 2.0667 - 3.6667 * 0.9 + 1.6667 * 0.81, 0.05])
    assert np.isnan(kc[5])
    print("índice de cielo despejado OK", np.round(kc, 3))


def test_seguimiento():
    ny, nx = 200, 300
    lat = np.repeat(np.linspace(10, 4, ny)[:, None], nx, axis=1)
    lon = np.repeat(np.linspace(-80, -70, nx)[None, :], ny, axis=0)
    apix = area_pixel_km2(lat, lon)
    yy, xx = np.mgrid[0:ny, 0:nx]
    radios = [10, 20, 30, 30, 20, 8]       # crece, madura y se disipa
    etiquetas = []
    for k, r in enumerate(radios):
        cx, cy = 60 + 12 * k, 100            # se desplaza hacia el este
        tb = np.full((ny, nx), 290.0)
        d = np.hypot(xx - cx, yy - cy)
        tb[d < r] = 235.0
        tb[d < r / 3] = 210.0
        # nube pequeña aislada que debe descartarse
        tb[10:13, 250:253] = 215.0
        et, props = objetos_frios(tb, apix, 241, 221, 2000)
        etiquetas.append(et)
    tray = seguir_objetos(etiquetas, 0.3)
    ids = {int(v) for t in tray for v in np.unique(t[t > 0])}
    print("ids de trayectorias:", ids)
    areas = [float(apix[t > 0].sum()) for t in tray]
    print("áreas (km²):", np.round(areas))
    assert len(ids) == 1, "el sistema debería ser una sola trayectoria"
    print("etapas:", etapa_ciclo_vida(areas))


if __name__ == "__main__":
    test_sol(); test_kc(); test_seguimiento()
    print("Todas las pruebas pasaron.")
