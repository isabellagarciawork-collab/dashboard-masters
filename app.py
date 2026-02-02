import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import pyperclip

st.set_page_config(layout="wide", page_title="Dashboard de Másteres v3.0")

# --- LÓGICA DE DATOS Y SCORING ---

@st.cache_data
def load_data(data_path):
    """Carga y pre-procesa los datos desde el CSV."""
    df = pd.read_csv(data_path)
    numeric_cols = [
        'duracion_months', 'precio_total_eur', 'credito_ECTS', 
        'porcentaje_analitico', 'porcentaje_gerencial', 'enfoque_practico'
    ]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    df['practicas_ofrecidas'] = df['practicas_ofrecidas'].astype(bool)
    return df

def calculate_scores(df):
    """Calcula los puntajes normalizados y el puntaje final."""
    scored_df = df.copy()
    
    # Normalización de métricas a una escala 0-100
    # Costo (inverso): menor precio, mayor puntaje
    min_cost = scored_df['precio_total_eur'].min()
    max_cost = scored_df['precio_total_eur'].max()
    if max_cost > min_cost:
        scored_df['costo_score'] = 100 * (max_cost - scored_df['precio_total_eur']) / (max_cost - min_cost)
    else:
        scored_df['costo_score'] = 100

    # Práctico: enfoque práctico y si ofrece prácticas
    practico_norm = 100 * scored_df['enfoque_practico'] / 5
    # Asegurarse que practicas_ofrecidas es numérica para el cálculo
    practicas_numeric = scored_df['practicas_ofrecidas'].astype(int) * 100
    scored_df['practico_score'] = (practico_norm * 0.6) + (practicas_numeric * 0.4)

    # Ajuste de Perfil para Ing. Industrial
    scored_df['ajuste_perfil_score'] = scored_df.apply(
        lambda row: sum([
            40 if any(kw in str(row['keywords']).lower() for kw in ['operaciones', 'procesos', 'supply chain']) else 0,
            30 if any(kw in str(row['keywords']).lower() for kw in ['industria 4.0', 'digital']) else 0,
            30 if any(kw in str(row['keywords']).lower() for kw in ['analitica', 'datos']) else 0
        ]), axis=1
    )
    
    # Pesos para el puntaje final
    weights = {'ajuste_perfil': 0.30, 'analitico': 0.25, 'gerencial': 0.15, 'practico': 0.20, 'costo': 0.10}
    
    scored_df['Puntaje Final'] = (
        scored_df['ajuste_perfil_score'] * weights['ajuste_perfil'] +
        scored_df['porcentaje_analitico'] * weights['analitico'] +
        scored_df['porcentaje_gerencial'] * weights['gerencial'] +
        scored_df['practico_score'] * weights['practico'] +
        scored_df['costo_score'] * weights['costo']
    ) / 100 # Dividir por 100 para un puntaje final sobre 100

    return scored_df.sort_values(by='Puntaje Final', ascending=False)

# --- INICIALIZACIÓN DE LA APP ---

# Inicializar estado de sesión para las notas
if 'notas_personales' not in st.session_state:
    st.session_state.notas_personales = {}

# Cargar y procesar datos
df = load_data('masters_data_v3.csv')
scored_df = calculate_scores(df)

# --- UI DEL DASHBOARD ---

st.title("Dashboard de Decisión de Másteres v3.0")
st.markdown("Una herramienta de análisis para **Ingenieros/as Industriales** buscando un perfil híbrido en Operaciones, Tecnología y Datos.")

# --- SECCIÓN DE CONCLUSIONES Y DATOS CLAVE ---
with st.expander("Ver Conclusiones y Datos Clave del Análisis"):
    st.subheader("Veredicto del Consultor")
    st.info("""
    Para un perfil de Ingeniería Industrial, el máster ideal no es ni un MBA puro ni un Data Science puro. 
    El objetivo es encontrar programas que actúen como un **puente**, aplicando tecnología y datos para optimizar 
    el core de la ingeniería: **operaciones, procesos y cadena de suministro.** Los programas con mayor puntaje 
    en este dashboard reflejan ese equilibrio.
    """)

    # Métricas clave
    avg_price = scored_df['precio_total_eur'].mean()
    # Asegúrate de que idxmax() se llame en una Serie, no en un DataFrame
    best_value = scored_df.loc[scored_df['costo_score'].idxmax()]
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Programas Analizados", f"{len(scored_df)}")
    col2.metric("Precio Promedio", f"€{avg_price:,.0f}")
    col3.metric("Mejor Calidad/Precio", best_value['programa'], help=f"Puntaje de costo: {best_value['costo_score']:.0f}/100")

# --- FILTROS Y VISTA PRINCIPAL ---
st.sidebar.header("Filtros de Selección")
min_price, max_price = st.sidebar.slider(
    "Rango de Precio (€)", 
    int(scored_df['precio_total_eur'].min()), 
    int(scored_df['precio_total_eur'].max()),
    (int(scored_df['precio_total_eur'].min()), int(scored_df['precio_total_eur'].max()))
)
min_score = st.sidebar.slider("Puntaje Final Mínimo", 0, 100, 40)
ciudades = st.sidebar.multiselect("Ciudad", options=scored_df['ciudad'].unique(), default=scored_df['ciudad'].unique())

filtered_df = scored_df[
    (scored_df['precio_total_eur'].between(min_price, max_price)) &
    (scored_df['Puntaje Final'] >= min_score) &
    (scored_df['ciudad'].isin(ciudades))
]

st.header("Ranking de Programas Filtrados")

if filtered_df.empty:
    st.warning("No se encontraron programas con los filtros actuales. Intenta ampliar los rangos.")
else:
    for index, row in filtered_df.iterrows():
        with st.container(border=True):
            col1, col2, col3 = st.columns([4, 1, 1])
            with col1:
                st.markdown(f"#### {row['programa']}")
                st.caption(f"{row['universidad']} | {row['ciudad']} | {row['modalidad']}")
            with col2:
                st.metric("Puntaje Final", f"{row['Puntaje Final']:.1f}")
            with col3:
                st.metric("Precio", f"€{row['precio_total_eur']:,.0f}")
            
            # --- SECCIÓN DE DETALLE Y NOTAS ---
            with st.expander("Ver Análisis Detallado y Dejar Notas"):
                tab1, tab2, tab3 = st.tabs(["Análisis del Consultor", "Detalles y Métricas", "Mis Notas Personales"])

                with tab1:
                    st.markdown(row['analisis_consultor'])
                
                with tab2:
                    st.markdown(f"**Componentes Clave:** {row['componentes_curriculares']}")
                    st.markdown(f"**Salida Laboral Típica:** {row['salida_laboral']}")
                    
                    c1, c2, c3 = st.columns(3)
                    c1.progress(int(row['porcentaje_analitico']), text=f"Foco Analítico ({row['porcentaje_analitico']}%)")
                    c2.progress(int(row['porcentaje_gerencial']), text=f"Foco Gerencial ({row['porcentaje_gerencial']}%)")
                    c3.progress(int(row['practico_score']), text=f"Orientación Práctica ({int(row['practico_score'])}%)")

                with tab3:
                    st.info("Tus notas se guardan solo durante esta sesión del navegador.")
                    # Usamos el 'id' del programa para una clave única en el session_state
                    nota_guardada = st.session_state.notas_personales.get(row['id'], "")
                    nota_actual = st.text_area("Escribe aquí tus conclusiones, preguntas o ideas...", value=nota_guardada, key=f"nota_{row['id']}")
                    st.session_state.notas_personales[row['id']] = nota_actual

if __name__ == "__main__":
    run()