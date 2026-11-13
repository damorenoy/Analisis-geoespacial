"""
Paso 7 — Generación REAL de los parques del Magdalena, reportada a XM (datos tipo PUNTO).
1. Descarga el listado de recursos de generación de XM y guarda los SOLARES.
2. Busca cada parque de parques_magdalena.csv por su palabra clave (columna clave_xm)
   en el nombre del recurso. Revisa en pantalla que la coincidencia sea correcta.
3. Descarga la generación horaria real (métrica Gene / Recurso) y la pasa a formato
   largo: una fila por parque y hora, con la hora en UTC (para cruzar con GOES).
Salida: datos/procesados/xm_generacion_horaria.csv  (parque, time [UTC], energia_mwh)
Nota: XM entrega kWh por hora local (Values_Hour01 = 00:00–01:00, hora de Colombia).
"""
import datetime as dt
import pandas as pd
from pydataxm.pydataxm import ReadDB
import config as C


def columna(df, *claves):
    for c in df.columns:
        if any(k in c.lower() for k in claves):
            return c
    raise KeyError(f"No encontré columna con {claves} en {list(df.columns)}")


def main():
    api = ReadDB()
    rec = api.request_data("ListadoRecursos", "Sistema", dt.date(2025, 1, 1), dt.date(2025, 1, 2))
    rec.to_csv(C.RAW / "xm_listado_recursos.csv", index=False)
    texto = rec.astype(str).apply(lambda f: " ".join(f).upper(), axis=1)
    solares = rec[texto.str.contains("SOLAR")]
    solares.to_csv(C.PROC / "xm_recursos_solares.csv", index=False)
    print(f"Recursos solares en XM: {len(solares)} (lista en xm_recursos_solares.csv)")

    c_cod = columna(rec, "code", "codigo")
    c_nom = columna(rec, "name", "nombre")
    parques = pd.read_csv(C.ARCHIVO_PARQUES)
    mapa = {}
    for _, p in parques.iterrows():
        m = solares[solares[c_nom].astype(str).str.upper().str.contains(str(p.clave_xm).upper())]
        if m.empty:
            print(f"  ✗ {p.nombre}: sin coincidencia para '{p.clave_xm}' (puede no reportar a XM)")
            continue
        print(f"  ✓ {p.nombre} → {m[[c_cod, c_nom]].values.tolist()}  ← verifica que sea correcto")
        mapa[str(m.iloc[0][c_cod])] = p.nombre
    if not mapa:
        return

    gen = api.request_data("Gene", "Recurso", C.FECHA_INICIO.date(), C.FECHA_FIN.date())
    g_cod = columna(gen, "code")
    gen = gen[gen[g_cod].astype(str).isin(mapa)]
    horas = [c for c in gen.columns if "hour" in c.lower()]
    largo = gen.melt(id_vars=[g_cod, "Date"], value_vars=horas, var_name="h", value_name="kwh")
    largo["h"] = largo["h"].str.extract(r"(\d+)").astype(int)
    local = pd.to_datetime(largo["Date"]) + pd.to_timedelta(largo["h"] - 1, unit="h")
    # la energía de la hora local [h-1, h) se asigna al inicio del intervalo, en UTC
    largo["time"] = local + pd.Timedelta(hours=5)
    largo["parque"] = largo[g_cod].astype(str).map(mapa)
    largo["energia_mwh"] = pd.to_numeric(largo["kwh"], errors="coerce") / 1000
    out = largo[["parque", "time", "energia_mwh"]].sort_values(["parque", "time"])
    out.to_csv(C.PROC / "xm_generacion_horaria.csv", index=False)
    print("generación guardada:", len(out), "filas")


if __name__ == "__main__":
    main()
