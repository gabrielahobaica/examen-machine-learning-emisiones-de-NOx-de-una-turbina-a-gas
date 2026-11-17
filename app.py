"""Panel de control de emisiones de NOx de una turbina a gas.

Pestañas:
  1. Simulador de operación: probabilidades de TabPFN (mejor modelo) para una grilla de escenarios.
  2. Plan de intervención: ranking de horas por P(Crítico), curva de ganancia y ROI.
  3. Acciones y seguimiento: acciones por clase, indicadores, riesgos y reentrenamiento.

Archivos (misma carpeta que app.py):
  simulador_grilla.csv  -> Parte F del notebook
  plan_ranking.csv      -> Parte D del notebook
Ejecutar con:  streamlit run app.py
"""
from pathlib import Path

import altair as alt
import numpy as np
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Control de emisiones NOx", layout="wide")

# ---------------------------------------------------------------- estilo (ISA-101: gris normal, color = anormal)
GRIS_TINTA, GRIS_MEDIO, GRIS_CLARO, PANEL = "#232B31", "#7C868D", "#C5CBD0", "#F1F3F4"
ROJO, AMBAR, CIAN = "#C4262E", "#D98A17", "#2A7F9E"
CLASES = ["Muy bajo", "Bajo", "Normal", "Alto", "Crítico"]
COLOR_CLASE = {"Muy bajo": "#9AA3A9", "Bajo": "#9AA3A9", "Normal": "#9AA3A9", "Alto": AMBAR, "Crítico": ROJO}

st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Barlow:wght@400;500;600&family=Barlow+Condensed:wght@500;600&display=swap');
html, body, [class*="st-"], .stMarkdown, .stDataFrame, button, input {{ font-family: 'Barlow', sans-serif; }}
h1, h2, h3 {{ font-family: 'Barlow Condensed', sans-serif !important; font-weight: 600 !important; letter-spacing: .01em; color: {GRIS_TINTA}; }}
h1 {{ font-size: 2.3rem !important; margin-bottom: 0 !important; }}
h3 {{ font-size: 1.35rem !important; }}
.block-container {{ padding-top: 2.2rem; max-width: 1280px; }}
.sub {{ color: {GRIS_MEDIO}; font-size: .98rem; margin: .2rem 0 1.1rem 0; max-width: 78ch; }}
[data-testid="stMetricValue"] {{ font-family: 'Barlow Condensed', sans-serif; font-variant-numeric: tabular-nums; }}
.stTabs [data-baseweb="tab-list"] {{ gap: .4rem; border-bottom: 2px solid {GRIS_CLARO}; }}
.stTabs [data-baseweb="tab"] {{ font-family: 'Barlow Condensed', sans-serif; font-size: 1.15rem; padding: .4rem 1rem; }}
/* panel anunciador */
.anunciador {{ display: grid; grid-template-columns: repeat(5, 1fr); gap: 6px; background: #3A4249; padding: 6px; border-radius: 4px; }}
.ventana {{ background: #59626A; color: #AEB5BA; padding: .7rem .5rem .55rem; border-radius: 2px; text-align: center; min-height: 92px; }}
.ventana .nom {{ font-family: 'Barlow Condensed', sans-serif; font-size: 1.05rem; font-weight: 600; }}
.ventana .val {{ font-family: 'Barlow Condensed', sans-serif; font-size: 1.9rem; font-variant-numeric: tabular-nums; line-height: 1.15; }}
.ventana.encendida {{ background: #E9ECEE; color: {GRIS_TINTA}; box-shadow: inset 0 0 0 2px #FFFFFF; }}
.ventana.alto {{ background: {AMBAR}; color: #2B1A00; }}
.ventana.critico {{ background: {ROJO}; color: #FFFFFF; }}
/* indicador de barra */
.barra {{ position: relative; height: 18px; background: {PANEL}; border: 1px solid {GRIS_CLARO}; border-radius: 2px; margin: .35rem 0 .2rem; }}
.barra .relleno {{ position: absolute; left: 0; top: 0; bottom: 0; }}
.barra .limite {{ position: absolute; top: -5px; bottom: -5px; width: 2px; background: {GRIS_TINTA}; }}
.leyenda {{ display: flex; justify-content: space-between; color: {GRIS_MEDIO}; font-size: .85rem; font-variant-numeric: tabular-nums; }}
.estado {{ font-size: 1.02rem; margin: .7rem 0 0; }}
.estado b {{ font-weight: 600; }}
.nota {{ color: {GRIS_MEDIO}; font-size: .88rem; }}
.cifra {{ background: {PANEL}; border: 1px solid {GRIS_CLARO}; border-radius: 3px; padding: .75rem .9rem; margin-bottom: .6rem; }}
table.hmi {{ width: 100%; border-collapse: collapse; font-size: .95rem; background: {PANEL}; }}
table.hmi th {{ text-align: left; font-weight: 500; color: {GRIS_MEDIO}; border-bottom: 2px solid {GRIS_CLARO}; padding: .5rem .6rem; }}
table.hmi td {{ vertical-align: top; border-bottom: 1px solid #DDE1E4; padding: .55rem .6rem; line-height: 1.4; }}
.chip {{ display: inline-block; padding: .05rem .5rem; border-radius: 2px; background: #C9CFD3; color: {GRIS_TINTA}; font-weight: 500; white-space: nowrap; }}
.chip.critico {{ background: {ROJO}; color: #fff; }} .chip.alto {{ background: {AMBAR}; color: #2B1A00; }}
.cifra .n {{ font-family: 'Barlow Condensed', sans-serif; font-size: 2rem; font-variant-numeric: tabular-nums; color: {GRIS_TINTA}; line-height: 1.1; }}
.cifra .t {{ color: {GRIS_MEDIO}; font-size: .9rem; }}
.cifra.accion .n {{ color: {CIAN}; }}
</style>
""", unsafe_allow_html=True)

TEMA = {"config": {
    "background": "transparent", "font": "Barlow, sans-serif",
    "axis": {"labelColor": GRIS_TINTA, "titleColor": GRIS_MEDIO, "gridColor": "#D7DCDF", "domainColor": GRIS_CLARO,
             "tickColor": GRIS_CLARO, "labelFontSize": 12, "titleFontSize": 12, "titleFontWeight": 500},
    "legend": {"labelColor": GRIS_TINTA, "titleColor": GRIS_MEDIO}, "view": {"stroke": None}}}
try:  # Altair 5.5+
    alt.theme.register("hmi", enable=True)(lambda: alt.theme.ThemeConfig(TEMA))
except AttributeError:  # versiones anteriores
    alt.themes.register("hmi", lambda: TEMA)
    alt.themes.enable("hmi")

AQUI = Path(__file__).parent


@st.cache_data
def leer(origen):
    return pd.read_csv(origen)


def cargar(nombre, parte):
    ruta = AQUI / nombre
    if ruta.exists():
        return leer(ruta)
    subido = st.file_uploader(f"Falta {nombre}: súbelo aquí (se genera en la {parte} del notebook)", type="csv", key=nombre)
    return leer(subido) if subido is not None else None


def cifra(numero, texto, accion=False):
    return f'<div class="cifra{" accion" if accion else ""}"><div class="n">{numero}</div><div class="t">{texto}</div></div>'


def dec(x, d=1):
    return f"{x:.{d}f}".replace(".", ",")


def pesos(x):
    return f"${x:,.0f}".replace(",", ".")


# ---------------------------------------------------------------- encabezado
st.title("Control de emisiones de NOx en la turbina a gas")
st.markdown('<p class="sub">Herramienta de apoyo a la sala de control: anticipa las horas con emisión crítica de NOx '
            '(≥ 80 mg/m³) a partir de las variables de operación, usando TabPFN (F1 macro 0,853 en test). '
            'Gris significa operación normal; el color aparece solo cuando hay que actuar.</p>', unsafe_allow_html=True)

tab_sim, tab_plan, tab_acc = st.tabs(["Simulador de operación", "Plan de intervención", "Acciones y seguimiento"])

# ================================================================ 1. SIMULADOR
with tab_sim:
    grilla = cargar("simulador_grilla.csv", "Parte F")
    if grilla is None:
        st.info("Sin la grilla de escenarios no se puede simular. Ejecuta la Parte F del notebook y sube el CSV.")
    else:
        niveles = {v: sorted(grilla[v].unique()) for v in ["AT", "TEY", "TIT"]}
        frec = grilla[~grilla["Poco frecuente"]]
        inicio = frec.iloc[((frec["AT"] - grilla["AT"].median()).abs()
                            + (frec["TEY"] - grilla["TEY"].median()).abs() / 10).argmin()]

        ctrl, vista = st.columns([1, 2.6], gap="large")
        with ctrl:
            st.subheader("Condiciones")
            at = st.select_slider("Temperatura ambiente, AT (°C)", options=niveles["AT"], value=inicio["AT"],
                                  format_func=lambda v: f"{v:.1f}", help="No la controla la central: define el día.")
            st.subheader("Punto de operación")
            tey = st.select_slider("Carga, TEY (MWh)", options=niveles["TEY"], value=inicio["TEY"],
                                   format_func=lambda v: f"{v:.0f}")
            tit = st.select_slider("Temperatura de entrada a la turbina, TIT (°C)", options=niveles["TIT"],
                                   value=inicio["TIT"], format_func=lambda v: f"{v:.0f}")
            st.subheader("Criterio de ventana segura")
            umbral = st.slider("P(Crítico) máxima aceptada", 0.02, 0.50, 0.10, 0.01, format="%.2f",
                               help="10% es la proporción normal de horas críticas en los datos.")
            solo_frec = st.checkbox("Excluir combinaciones poco frecuentes", value=True)

        fila = grilla[(grilla["AT"] == at) & (grilla["TEY"] == tey) & (grilla["TIT"] == tit)].iloc[0]
        probs = {c: fila[f"P({c})"] for c in CLASES}
        p_crit = probs["Crítico"]
        mas_probable = max(probs, key=probs.get)

        with vista:
            # panel anunciador: se enciende la clase mas probable; Critico en rojo si supera el umbral
            html = '<div class="anunciador">'
            for c in CLASES:
                clase_css = ""
                if c == "Crítico" and p_crit > umbral:
                    clase_css = "critico"
                elif c == "Alto" and mas_probable == "Alto":
                    clase_css = "alto"
                elif c == mas_probable:
                    clase_css = "encendida"
                html += f'<div class="ventana {clase_css}"><div class="nom">{c}</div><div class="val">{probs[c]:.0%}</div></div>'
            html += "</div>"
            color_barra = ROJO if p_crit > umbral else (AMBAR if p_crit > umbral / 2 else GRIS_MEDIO)
            html += (f'<div class="estado">Probabilidad de emisión crítica: <b>{dec(p_crit * 100)}%</b></div>'
                     f'<div class="barra"><div class="relleno" style="width:{p_crit:.1%};background:{color_barra}"></div>'
                     f'<div class="limite" style="left:{umbral:.1%}"></div></div>'
                     f'<div class="leyenda"><span>0%</span><span>límite aceptado {umbral:.0%}</span><span>100%</span></div>')
            st.markdown(html, unsafe_allow_html=True)

            if p_crit > umbral:
                st.markdown(f'<p class="estado">Fuera de la ventana segura. Con {at:.1f} °C, este punto de operación '
                            f'tiene alto riesgo de superar 80 mg/m³: priorizar esta hora para intervención.</p>',
                            unsafe_allow_html=True)
            else:
                st.markdown('<p class="estado">Dentro de la ventana segura: operación normal.</p>', unsafe_allow_html=True)
            if fila["Poco frecuente"]:
                tipicas = frec[(frec["AT"] == at) & (frec["TEY"] == tey)]["TIT"]
                extra = (f" Con esta temperatura y carga, la TIT habitual es {tipicas.min():.0f}–{tipicas.max():.0f} °C."
                         if not tipicas.empty else " No hay horas reales parecidas con esta temperatura y carga.")
                st.warning("Combinación poco frecuente en los datos reales: la probabilidad es menos confiable." + extra)

            st.subheader(f"Mapa de riesgo con AT = {at:.1f} °C")
            sub = grilla[grilla["AT"] == at].copy()
            sub["Segura"] = (sub["P(Crítico)"] <= umbral) & ~(solo_frec & sub["Poco frecuente"])
            sub["TEY_e"] = sub["TEY"].map("{:.0f}".format)
            sub["TIT_e"] = sub["TIT"].map("{:.0f}".format)
            orden_tey = [f"{v:.0f}" for v in niveles["TEY"]]
            orden_tit = [f"{v:.0f}" for v in sorted(niveles["TIT"], reverse=True)]
            base = alt.Chart(sub).encode(
                x=alt.X("TEY_e:O", title="Carga TEY (MWh)", sort=orden_tey, axis=alt.Axis(labelAngle=0)),
                y=alt.Y("TIT_e:O", title="TIT (°C)", sort=orden_tit))
            mapa = base.mark_rect(stroke="#E3E6E8", strokeWidth=1).encode(
                color=alt.Color("P(Crítico):Q", title="P(Crítico)",
                                scale=alt.Scale(domain=[0, umbral, 0.5, 1], range=["#DDE1E4", "#C2C9CE", "#DE7A7E", ROJO],
                                                interpolate="rgb"),
                                legend=alt.Legend(format=".0%", gradientLength=180)),
                opacity=alt.condition("datum['Poco frecuente']", alt.value(0.3), alt.value(1.0)),
                tooltip=[alt.Tooltip("TEY_e:N", title="Carga (MWh)"), alt.Tooltip("TIT_e:N", title="TIT (°C)"),
                         alt.Tooltip("P(Crítico):Q", format=".1%"), "Poco frecuente"])
            seguras = base.transform_filter("datum.Segura").mark_point(shape="circle", size=28, filled=True, color=GRIS_TINTA)
            actual = alt.Chart(pd.DataFrame({"TEY_e": [f"{tey:.0f}"], "TIT_e": [f"{tit:.0f}"]})).mark_square(
                size=420, filled=False, color=CIAN, strokeWidth=3).encode(
                x=alt.X("TEY_e:O", sort=orden_tey), y=alt.Y("TIT_e:O", sort=orden_tit))
            st.altair_chart((mapa + seguras + actual).properties(height=360), width="stretch")
            st.markdown('<p class="nota">Punto = combinación dentro de la ventana segura. Cuadro celeste = punto de operación '
                        'actual. Celdas tenues = combinaciones poco frecuentes: en la turbina real la TIT sube junto con la carga.</p>',
                        unsafe_allow_html=True)

            segura = sub[sub["Segura"]]
            st.subheader("Ventana de operación recomendada")
            if segura.empty:
                st.error(f"Con {at:.1f} °C ninguna combinación de carga y TIT queda bajo {umbral:.0%} de riesgo. "
                         "Estas horas deben ir primero en el plan de intervención.")
            else:
                st.markdown(f'<p class="estado">Con {at:.1f} °C: carga entre <b>{segura["TEY"].min():.0f} y '
                            f'{segura["TEY"].max():.0f} MWh</b> y TIT entre <b>{segura["TIT"].min():.0f} y '
                            f'{segura["TIT"].max():.0f} °C</b> ({len(segura)} de {len(sub)} combinaciones). '
                            'Es el contorno de las combinaciones seguras: dentro del rango, usar el mapa.</p>',
                            unsafe_allow_html=True)
            st.markdown('<p class="nota">La ventana refleja asociaciones aprendidas por el modelo, no un efecto causal '
                        'comprobado; debe validarse con el área de operación antes de aplicarse.</p>', unsafe_allow_html=True)

# ================================================================ 2. PLAN DE INTERVENCION
# supuestos del ROI (fuentes en el notebook, Parte D.4)
TEY_MEDIO, USD_CLP, UTA = 133.51, 903.38, 865_812
SUELDO_DS, GPU_USD_HORA = 1_423_554, 0.42
C_MODELO = 2 * SUELDO_DS + 0.25 * SUELDO_DS * 12 + 365 * GPU_USD_HORA * USD_CLP

with tab_plan:
    ranking = cargar("plan_ranking.csv", "Parte D")
    if ranking is None:
        st.info("Sin el ranking de test no se puede calcular el plan. Ejecuta la celda de exportación de la Parte D.")
    else:
        es_crit = (ranking.sort_values("P(Crítico)", ascending=False)["Clase real"] == "Crítico").to_numpy()
        n, total_crit = len(es_crit), es_crit.sum()
        dias = n / 24
        acum = np.cumsum(es_crit)

        c1, c2 = st.columns([1, 2.6], gap="large")
        with c1:
            st.subheader("Capacidad de intervención")
            horas = st.slider("Horas que operación puede intervenir por día", 1, 8, 3,
                              help="Supuesto base: 3 horas de cada 24 (12,5% de las horas).")
            k = int(round(horas / 24 * n))
            cap_m = int(acum[k - 1])
            cap_a = k * total_crit / n
            st.markdown(cifra(f"{cap_m / total_crit:.0%}", f"de las horas críticas detectadas con el modelo "
                              f"({cap_m} de {total_crit} en test)", accion=True), unsafe_allow_html=True)
            st.markdown(cifra(f"{cap_a / total_crit:.0%}", f"al intervenir {k} horas al azar "
                              f"(~{cap_a:.0f} críticas)"), unsafe_allow_html=True)
            st.markdown(cifra(f"{dec(cap_m / cap_a)} veces", "más horas críticas que al azar, con los mismos recursos"),
                        unsafe_allow_html=True)
            st.markdown(f'<p class="nota">Test: {n:,} horas (~{dias:.0f} días). '.replace(",", ".")
                        + f'Precisión de las intervenciones: {cap_m / k:.0%}; falsas alarmas: {dec((k - cap_m) / dias)} por día.</p>',
                        unsafe_allow_html=True)

        with c2:
            st.subheader("Curva de ganancia")
            paso = max(1, n // 400)
            idx = np.arange(paso, n + 1, paso)
            curva = pd.concat([
                pd.DataFrame({"Revisado": idx / n, "Capturado": acum[idx - 1] / total_crit, "Estrategia": "Modelo (TabPFN)"}),
                pd.DataFrame({"Revisado": [0, 1], "Capturado": [0, 1], "Estrategia": "Al azar"}),
                pd.DataFrame({"Revisado": [0, total_crit / n, 1], "Capturado": [0, 1, 1], "Estrategia": "Modelo perfecto"})])
            lineas = alt.Chart(curva).mark_line(strokeWidth=2.5).encode(
                x=alt.X("Revisado:Q", title="Horas intervenidas (ordenadas por P(Crítico))", axis=alt.Axis(format="%")),
                y=alt.Y("Capturado:Q", title="Horas críticas detectadas", axis=alt.Axis(format="%")),
                color=alt.Color("Estrategia:N", scale=alt.Scale(domain=["Modelo (TabPFN)", "Al azar", "Modelo perfecto"],
                                                                 range=[GRIS_TINTA, GRIS_MEDIO, GRIS_CLARO]),
                                legend=alt.Legend(orient="bottom-right", title=None)),
                strokeDash=alt.StrokeDash("Estrategia:N", scale=alt.Scale(
                    domain=["Modelo (TabPFN)", "Al azar", "Modelo perfecto"], range=[[1, 0], [6, 4], [2, 3]]), legend=None))
            cap = pd.DataFrame({"x": [k / n], "y": [cap_m / total_crit],
                                "t": [f"{horas} h/día: {cap_m / total_crit:.0%} detectadas"]})
            regla = alt.Chart(cap).mark_rule(color=CIAN, strokeWidth=2).encode(x="x:Q")
            punto = alt.Chart(cap).mark_point(color=CIAN, filled=True, size=110).encode(x="x:Q", y="y:Q")
            texto = alt.Chart(cap).mark_text(align="left", dx=8, dy=14, color=CIAN, fontSize=13, fontWeight=600).encode(
                x="x:Q", y="y:Q", text="t:N")
            st.altair_chart((lineas + regla + punto + texto).properties(height=330), width="stretch")

        st.subheader("Ranking de horas a intervenir")
        tabla = ranking.sort_values("P(Crítico)", ascending=False).reset_index(drop=True).copy()
        tabla["Prioridad"] = tabla.index + 1
        tabla["Acción"] = np.where(tabla["Prioridad"] <= k, "Intervenir: bajar carga 5%", "Operación normal")
        ver_real = st.checkbox("Mostrar la clase real (solo para evaluar; en operación no se conoce)", value=False)
        cols = ["Prioridad", "ID hora", "P(Crítico)", "Clase predicha"] + (["Clase real"] if ver_real else []) + ["Acción"]
        st.dataframe(tabla[cols].head(max(k + 5, 25)), hide_index=True, width="stretch", height=320,
                     column_config={"P(Crítico)": st.column_config.ProgressColumn(format="percent", min_value=0, max_value=1)})
        st.markdown(f'<p class="nota">Se muestran las {k} horas que entran en la capacidad y las 5 siguientes.</p>',
                    unsafe_allow_html=True)

        st.subheader("Retorno de la inversión anual")
        r1, r2 = st.columns([1, 2.6], gap="large")
        with r1:
            c_crit_uta = st.slider("Costo evitado por hora crítica corregida (UTA)", 0.1, 10.0, 1.0, 0.1,
                                   help="No hay un valor publicado: la norma evalúa % de horas, no multa por hora. "
                                        "Mover para ver la sensibilidad.")
            reduccion = st.slider("Reducción de carga al intervenir (%)", 1, 15, 5) / 100
            precio = st.slider("Precio de la energía (USD/MWh)", 40.0, 200.0, 96.1, 0.1,
                               help="Base: costo marginal promedio de julio 2026, barra Quillota (CNE).")
        c_int = TEY_MEDIO * reduccion * precio * USD_CLP
        h_anio = horas * 365
        tp_m, tp_a = h_anio * cap_m / k, h_anio * total_crit / n
        costo_m, costo_a = h_anio * c_int + C_MODELO, h_anio * c_int
        benef_m, benef_a = tp_m * c_crit_uta * UTA, tp_a * c_crit_uta * UTA
        roi_m, roi_a = (benef_m - costo_m) / costo_m, (benef_a - costo_a) / costo_a
        eq_m, eq_a = costo_m / tp_m / UTA, costo_a / tp_a / UTA
        with r2:
            g1, g2, g3 = st.columns(3)
            g1.markdown(cifra(f"{roi_m:+.0%}", "ROI anual con el modelo", accion=True), unsafe_allow_html=True)
            g2.markdown(cifra(f"{roi_a:+.0%}", "ROI anual interviniendo al azar"), unsafe_allow_html=True)
            g3.markdown(cifra(f"{dec(eq_m, 2)} UTA", f"por hora crítica: desde aquí el plan se paga (al azar: {dec(eq_a, 2)})"),
                        unsafe_allow_html=True)
            uta_grid = np.logspace(np.log10(0.1), np.log10(10), 120)
            sens = pd.concat([
                pd.DataFrame({"UTA": uta_grid, "ROI": (tp_m * uta_grid * UTA - costo_m) / costo_m, "Estrategia": "Con modelo"}),
                pd.DataFrame({"UTA": uta_grid, "ROI": (tp_a * uta_grid * UTA - costo_a) / costo_a, "Estrategia": "Al azar"})])
            curvas = alt.Chart(sens).mark_line(strokeWidth=2.5).encode(
                x=alt.X("UTA:Q", scale=alt.Scale(type="log"), title="Costo evitado por hora crítica (UTA, escala log)"),
                y=alt.Y("ROI:Q", axis=alt.Axis(format="%"), title="ROI anual"),
                color=alt.Color("Estrategia:N", scale=alt.Scale(domain=["Con modelo", "Al azar"], range=[GRIS_TINTA, GRIS_MEDIO]),
                                legend=alt.Legend(orient="top-left", title=None)),
                strokeDash=alt.StrokeDash("Estrategia:N", scale=alt.Scale(domain=["Con modelo", "Al azar"],
                                                                          range=[[1, 0], [6, 4]]), legend=None))
            cero = alt.Chart(pd.DataFrame({"y": [0]})).mark_rule(color=GRIS_TINTA, strokeWidth=1).encode(y="y:Q")
            elegido = alt.Chart(pd.DataFrame({"x": [c_crit_uta]})).mark_rule(color=CIAN, strokeWidth=2).encode(x="x:Q")
            st.altair_chart((curvas + cero + elegido).properties(height=260), width="stretch")
        st.markdown(
            f'<p class="nota">Con {horas} h/día se intervienen {h_anio:,} horas al año. Costo por hora intervenida: '
            f'{pesos(c_int)} (energía no vendida); costo del modelo el año 1: {pesos(C_MODELO)}. Beneficio anual con el '
            f'modelo: {pesos(benef_m)} vs. costo {pesos(costo_m)}. Supone que intervenir corrige siempre la hora crítica '
            'y extrapola a un año la precisión medida en test.</p>'.replace("1,095", "1.095"), unsafe_allow_html=True)

# ================================================================ 3. ACCIONES Y SEGUIMIENTO
with tab_acc:
    st.subheader("Qué hacer según la clase predicha")
    acciones = pd.DataFrame([
        ["Crítico", "Si está dentro de la capacidad del día: bajar la carga 5% y llevar TEY/TIT a la ventana segura del simulador. Registrar la intervención.",
         "Jefe de turno de operación", "Antes de 15 min desde la alerta", "Operador de sala de control, sistema de control (DCS), simulador"],
        ["Alto", "Vigilancia reforzada: revisar la tendencia del analizador de NOx cada 15 min y dejar preparada la intervención.",
         "Operador de sala de control", "Durante la hora", "Analizador continuo (CEMS), simulador"],
        ["Normal", "Operación estándar con monitoreo rutinario.", "Operador de sala de control", "Continuo", "CEMS"],
        ["Bajo / Muy bajo", "Operación estándar. Hay margen ambiental si el despacho pide más carga.",
         "Operación y despacho", "Continuo", "Sin recursos adicionales"],
        ["Todas (revisión semanal)", "Revisar el % de horas sobre el límite de NOx y las intervenciones de la semana.",
         "Área de medio ambiente", "Semanal", "Reporte del CEMS y registro de intervenciones"],
        ["Todas (revisión mensual)", "Medir el desempeño del modelo con las horas nuevas y actualizar su contexto.",
         "Analista de datos (25% de jornada)", "Mensual", "Notebook, GPU (1 h/día), datos del mes"]],
        columns=["Clase predicha", "Qué se hace", "Quién", "Plazo", "Recursos"])
    def chip(c):
        css = "critico" if c == "Crítico" else ("alto" if c == "Alto" else "")
        return f'<span class="chip {css}">{c}</span>'
    filas = "".join(f"<tr><td>{chip(r[0])}</td><td>{r[1]}</td><td>{r[2]}</td><td>{r[3]}</td><td>{r[4]}</td></tr>"
                    for r in acciones.itertuples(index=False))
    st.markdown('<table class="hmi"><tr><th>Clase predicha</th><th style="width:38%">Qué se hace</th><th>Quién</th>'
                f'<th>Plazo</th><th>Recursos</th></tr>{filas}</table>', unsafe_allow_html=True)

    st.subheader("Indicadores de seguimiento")
    kpi = pd.DataFrame([
        ["Horas críticas detectadas a tiempo", "Críticas reales dentro del ranking diario / críticas reales", "≥ 90%", "94,5%"],
        ["Precisión de las intervenciones", "Intervenciones en horas que eran críticas / intervenciones", "≥ 70%", "76,3%"],
        ["Falsas alarmas", "Intervenciones en horas no críticas, por día", "≤ 1 por día", "0,7 por día"],
        ["Tiempo de respuesta", "Minutos entre la alerta y el ajuste de carga", "≤ 15 min", "Se mide en operación"],
        ["Horas sobre 80 mg/m³", "% de horas de operación con NOx crítico (CEMS)", "Bajo 10% y bajando", "10,1% sin plan"],
        ["Desempeño del modelo", "F1 macro mensual con las horas nuevas", "≥ 0,80 (alerta si cae 5 puntos)", "0,853"],
        ["Costo de intervenir", "Energía no vendida por intervenciones, mensual", "Dentro del presupuesto", "~$53 millones al mes"]],
        columns=["Indicador", "Cómo se mide", "Meta", "Valor en test / base"])
    filas = "".join(f"<tr><td><b>{r[0]}</b></td><td>{r[1]}</td><td>{r[2]}</td><td>{r[3]}</td></tr>"
                    for r in kpi.itertuples(index=False))
    st.markdown('<table class="hmi"><tr><th>Indicador</th><th>Cómo se mide</th><th>Meta</th><th>Valor en test o base</th></tr>'
                f'{filas}</table>', unsafe_allow_html=True)
    st.markdown('<p class="nota">Valores en test con capacidad de 3 h/día. El costo mensual es 1.095 horas × $579.515 / 12.</p>',
                unsafe_allow_html=True)

    st.subheader("Riesgos y reentrenamiento")
    a, b = st.columns(2, gap="large")
    with a:
        st.markdown("""
**Horas críticas no detectadas.** 41 de 741 en test (5,5%), unas 49 al año. Quedan cubiertas por el analizador continuo (CEMS), que sigue operando como respaldo: el modelo prioriza, no reemplaza la medición.

**Falsas alarmas.** Cerca de 1 de cada 4 intervenciones ocurre en una hora que no era crítica: ~260 horas al año, unos $151 millones en energía no vendida. Es el principal costo del plan.

**Supuestos del beneficio.** El ROI supone que bajar la carga corrige siempre la hora crítica y que el costo evitado por hora supera 0,89 UTA. Ambos deben validarse en planta.

**Origen de los datos.** El modelo se entrenó con una turbina en Turquía (2011–2015). Para una central chilena hay que reentrenarlo con sus propios datos del CEMS antes de usarlo.
""")
    with b:
        st.markdown("""
**Cada cuánto reentrenar.** TabPFN no ajusta pesos: aprende del contexto. "Reentrenar" es actualizar ese contexto con las horas recientes.
- **Mensual:** agregar las horas del último mes y quitar las más antiguas (ventana móvil de 12 meses), para seguir el desgaste y la estacionalidad. Por eso el año de operación se incluyó como variable: la turbina puede cambiar con el desgaste.
- **Extraordinario:** después de una mantención mayor de la turbina, un cambio de combustible o si el F1 macro mensual cae más de 5 puntos.

**Operación del modelo.** Cada predicción toma ~75 s en GPU T4: alcanza para un ranking por hora, pero requiere GPU disponible.

**Licencia.** Las versiones recientes de TabPFN tienen licencia no comercial: el uso real en la central requiere licencia comercial (costo no incluido en el ROI).
""")
