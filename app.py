"""Simulador what-if del nivel de NOx de una turbina a gas.

Lee las probabilidades que TabPFN (el mejor modelo) calculó para una grilla de escenarios
(archivo simulador_grilla.csv, generado en la Parte F del notebook).
Ejecutar con:  streamlit run app.py
"""
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Simulador NOx · Turbina a gas", layout="wide")

CLASES = ["Muy bajo", "Bajo", "Normal", "Alto", "Crítico"]
COLORES = ["#1a9850", "#91cf60", "#bdbdbd", "#fc8d59", "#d73027"]
ARCHIVO = Path(__file__).with_name("simulador_grilla.csv")


@st.cache_data
def cargar(origen):
    return pd.read_csv(origen)


# --- Datos: CSV junto a app.py, o subido a mano ---
if ARCHIVO.exists():
    grilla = cargar(ARCHIVO)
else:
    subido = st.file_uploader("Sube simulador_grilla.csv (generado en la Parte F del notebook)", type="csv")
    if subido is None:
        st.stop()
    grilla = cargar(subido)

niveles = {v: sorted(grilla[v].unique()) for v in ["AT", "TEY", "TIT"]}

# Escenario inicial: uno frecuente (realista), cerca del centro de la grilla
frec = grilla[~grilla["Poco frecuente"]]
inicio = frec.iloc[((frec["AT"] - grilla["AT"].median()).abs() + (frec["TEY"] - grilla["TEY"].median()).abs() / 10).argmin()]

# --- Sliders ---
st.sidebar.header("Escenario de operación")
st.sidebar.caption("Condición (no controlable)")
at = st.sidebar.select_slider("Temperatura ambiente, AT (°C)", options=niveles["AT"],
                              value=inicio["AT"], format_func=lambda v: f"{v:.1f}")
st.sidebar.caption("Variables operables")
tey = st.sidebar.select_slider("Carga, TEY (MWh)", options=niveles["TEY"],
                               value=inicio["TEY"], format_func=lambda v: f"{v:.0f}")
tit = st.sidebar.select_slider("Temperatura de entrada a la turbina, TIT (°C)", options=niveles["TIT"],
                               value=inicio["TIT"], format_func=lambda v: f"{v:.0f}")
st.sidebar.divider()
umbral = st.sidebar.slider("Umbral de la ventana segura: P(Crítico) ≤", 0.02, 0.50, 0.10, 0.01, format="%.2f")
solo_frecuentes = st.sidebar.checkbox("Excluir escenarios poco frecuentes de la ventana", value=True)

fila = grilla[(grilla["AT"] == at) & (grilla["TEY"] == tey) & (grilla["TIT"] == tit)].iloc[0]
p_crit = fila["P(Crítico)"]

# --- Resultado del escenario ---
st.title("Simulador what-if · Nivel de NOx de la turbina")
st.caption("Probabilidades calculadas con TabPFN (mejor modelo, F1 macro 0,853 en test). "
           "GTEP, CDP y TAT se completan con su valor típico para el escenario; AFDP, AP y AH en su mediana.")

c1, c2, c3 = st.columns(3)
c1.metric("P(Crítico)", f"{p_crit:.1%}")
c2.metric("Clase más probable", fila["Clase predicha"])
c3.metric("¿Dentro de la ventana segura?", "Sí" if p_crit <= umbral else "No")
if fila["Poco frecuente"]:
    tipicas = frec[(frec["AT"] == at) & (frec["TEY"] == tey)]["TIT"]
    sugerencia = (f" Con esta temperatura y carga, la TIT habitual es {tipicas.min():.0f}–{tipicas.max():.0f} °C."
                  if not tipicas.empty else " No hay horas reales parecidas con esta temperatura y carga.")
    st.warning("Escenario poco frecuente: esta combinación casi no aparece en los datos reales, "
               "así que la probabilidad es menos confiable." + sugerencia)

izq, der = st.columns([1, 1.4])

with izq:
    st.subheader("Probabilidad de cada clase")
    probs = pd.DataFrame({"Clase": CLASES, "Probabilidad": [fila[f"P({c})"] for c in CLASES]})
    barras = alt.Chart(probs).mark_bar().encode(
        x=alt.X("Clase:N", sort=CLASES, title=None),
        y=alt.Y("Probabilidad:Q", scale=alt.Scale(domain=[0, 1]), axis=alt.Axis(format="%")),
        color=alt.Color("Clase:N", scale=alt.Scale(domain=CLASES, range=COLORES), legend=None),
        tooltip=["Clase", alt.Tooltip("Probabilidad:Q", format=".1%")])
    texto = barras.mark_text(dy=-8).encode(text=alt.Text("Probabilidad:Q", format=".0%"))
    st.altair_chart(barras + texto, width="stretch")

with der:
    st.subheader(f"P(Crítico) según carga y TIT · AT = {at:.1f} °C")
    sub = grilla[grilla["AT"] == at].copy()
    sub["Ventana segura"] = (sub["P(Crítico)"] <= umbral) & ~(solo_frecuentes & sub["Poco frecuente"])
    base = alt.Chart(sub).encode(
        x=alt.X("TEY:O", title="Carga TEY (MWh)", axis=alt.Axis(format=".0f")),
        y=alt.Y("TIT:O", title="TIT (°C)", sort="descending", axis=alt.Axis(format=".0f")))
    mapa = base.mark_rect().encode(
        opacity=alt.condition("datum['Poco frecuente']", alt.value(0.25), alt.value(1.0)),
        color=alt.Color("P(Crítico):Q", scale=alt.Scale(scheme="redyellowgreen", reverse=True, domain=[0, 1])),
        tooltip=[alt.Tooltip("TEY:Q", format=".0f"), alt.Tooltip("TIT:Q", format=".0f"),
                 alt.Tooltip("P(Crítico):Q", format=".1%"), "Poco frecuente"])
    marca_segura = base.transform_filter("datum['Ventana segura']").mark_text(text="✓", color="black")
    actual = alt.Chart(pd.DataFrame({"TEY": [tey], "TIT": [tit]})).mark_point(
        shape="square", size=300, filled=False, color="black", strokeWidth=3).encode(x="TEY:O", y="TIT:O")
    st.altair_chart(mapa + marca_segura + actual, width="stretch")
    st.caption("✓ = ventana segura · cuadro negro = escenario actual · celdas tenues = combinaciones poco frecuentes "
               "(en la turbina real, la TIT sube junto con la carga)")

# --- Ventana recomendada para la temperatura elegida ---
st.subheader("Ventana de operación recomendada")
segura = sub[sub["Ventana segura"]]
if segura.empty:
    st.error(f"Con AT = {at:.1f} °C no hay combinaciones de carga y TIT con P(Crítico) ≤ {umbral:.0%}. "
             "Priorizar estas horas en el plan de intervención.")
else:
    st.success(f"Con AT = {at:.1f} °C: operar con carga entre **{segura['TEY'].min():.0f} y {segura['TEY'].max():.0f} MWh** "
               f"y TIT entre **{segura['TIT'].min():.0f} y {segura['TIT'].max():.0f} °C** "
               f"({len(segura)} de {len(sub)} combinaciones cumplen P(Crítico) ≤ {umbral:.0%}). "
               "El rango es el contorno de las combinaciones seguras: revisar el mapa, no todas las "
               "combinaciones dentro del rango son seguras.")
st.caption("La ventana muestra asociaciones aprendidas por el modelo, no un efecto causal comprobado; "
           "debe validarse con el área de operación antes de aplicarse.")
