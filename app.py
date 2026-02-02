import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import pyperclip

st.set_page_config(layout="wide", page_title="Dashboard de Másteres v2.0")

# --- Scoring Weights ---
WEIGHTS = {
    'ajuste_perfil': 0.25,
    'analitico': 0.20,
    'gerencial': 0.15,
    'practico': 0.15,
    'empleabilidad': 0.15,
    'costo': 0.10
}

@st.cache_data
def load_data():
    # Load the new, enriched dataset
    df = pd.read_csv('masters_data_v2.csv')
    numeric_cols = [
        'duracion_months', 'precio_total_eur', 'ranking_universidad', 
        'credito_ECTS', 'porcentaje_analitico', 'porcentaje_gerencial',
        'enfoque_practico', 'red_empresas_partners', 'tasa_empleabilidad_6m'
    ]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors='coerce')
    df['practicas_ofrecidas'] = df['practicas_ofrecidas'].astype(bool)
    df['inicio_proximo'] = pd.to_datetime(df['inicio_proximo'], errors='coerce')
    
    # Fill NaNs for scoring columns
    for col in ['tasa_empleabilidad_6m', 'enfoque_practico', 'red_empresas_partners', 'precio_total_eur']:
        df[col] = df[col].fillna(df[col].median())
        
    df.rename(columns={'programa': 'Programa'}, inplace=True)
    return df

# (All scoring functions remain the same)
def normalize_to_100(series):
    if series.max() == series.min():
        return pd.Series(100, index=series.index)
    return 100 * (series - series.min()) / (series.max() - series.min())

def ajuste_perfil_score(df):
    scores = pd.Series(0, index=df.index)
    produccion_kws = ['procesos', 'producción', 'optimización', 'industrial', 'operations', 'operaciones', 'lean', 'supply chain', 'logística']
    for i, row in df.iterrows():
        text_to_search = f"{row['Programa']} {row['componentes_curriculares']}".lower()
        if any(kw in text_to_search for kw in produccion_kws):
            scores[i] += 40
        if row['practicas_ofrecidas']:
            scores[i] += 20
    return scores.clip(0, 100)

def costo_eficiencia_score(df):
    precio_por_credito = df['precio_total_eur'] / df['credito_ECTS'].replace(0, np.nan)
    precio_por_credito = precio_por_credito.fillna(precio_por_credito.median())
    if precio_por_credito.max() == precio_por_credito.min():
        return pd.Series(100, index=df.index)
    return 100 * (precio_por_credito.max() - precio_por_credito) / (precio_por_credito.max() - precio_por_credito.min())

def calculate_scores(df):
    scored_df = df.copy()
    scored_df['ajuste_perfil_score'] = ajuste_perfil_score(scored_df)
    scored_df['analitico_score'] = scored_df['porcentaje_analitico']
    scored_df['gerencial_score'] = scored_df['porcentaje_gerencial']
    practico_score = normalize_to_100(scored_df['enfoque_practico'])
    practicas_score = scored_df['practicas_ofrecidas'] * 100
    scored_df['practico_total_score'] = (practico_score * 0.7 + practicas_score * 0.3)
    empleabilidad_score = normalize_to_100(scored_df['tasa_empleabilidad_6m'])
    red_empresas_score = normalize_to_100(scored_df['red_empresas_partners'])
    scored_df['empleabilidad_total_score'] = (empleabilidad_score * 0.6 + red_empresas_score * 0.4)
    scored_df['costo_score'] = costo_eficiencia_score(scored_df)
    scored_df['Puntaje Final'] = (
        scored_df['ajuste_perfil_score'] * WEIGHTS['ajuste_perfil'] +
        scored_df['analitico_score'] * WEIGHTS['analitico'] +
        scored_df['gerencial_score'] * WEIGHTS['gerencial'] +
        scored_df['practico_total_score'] * WEIGHTS['practico'] +
        scored_df['empleabilidad_total_score'] * WEIGHTS['empleabilidad'] +
        scored_df['costo_score'] * WEIGHTS['costo']
    ).fillna(0)
    return scored_df.sort_values(by='Puntaje Final', ascending=False)


def run():
    st.title("Dashboard de Másteres v2.0")
    st.markdown("Análisis mejorado con una selección de programas híbridos y con mejor relación calidad-precio.")
    
    df = load_data()
    # Filter out expensive programs as requested
    df = df[df['precio_total_eur'] < 20000].copy()
    scored_df = calculate_scores(df)

    st.sidebar.header("Filtros")
    cities = st.sidebar.multiselect("Ciudad", options=scored_df['ciudad'].unique(), default=scored_df['ciudad'].unique())
    program_types = st.sidebar.multiselect("Modalidad", options=scored_df['tipo_programa'].unique(), default=scored_df['tipo_programa'].unique())
    max_price = int(scored_df['precio_total_eur'].max())
    price_range = st.sidebar.slider("Rango de Precio (EUR)", 0, max_price, (0, max_price))
    min_score = st.sidebar.slider("Puntaje Mínimo", 0, 100, 0)
    
    filtered_df = scored_df[
        (scored_df['ciudad'].isin(cities)) &
        (scored_df['tipo_programa'].isin(program_types)) &
        (scored_df['precio_total_eur'].between(price_range[0], price_range[1])) &
        (scored_df['Puntaje Final'] >= min_score)
    ]

    st.header(f"Mostrando {len(filtered_df)} de {len(scored_df)} programas")
    
    if filtered_df.empty:
        st.warning("No se encontraron programas que cumplan con los filtros seleccionados.")
    else:
        # (The Top 5 and Table views remain largely the same)
        st.subheader("Top 5 Recomendados")
        for i, row in filtered_df.head(5).iterrows():
            with st.container(border=True):
                col1, col2, col3 = st.columns([3, 1, 1])
                with col1:
                    st.markdown(f"**{row['Programa']}** | *{row['universidad']}*")
                with col2:
                    st.metric("Puntaje Final", f"{row['Puntaje Final']:.1f}")
                with col3:
                    st.metric("Precio", f"€{row['precio_total_eur']:,.0f}")
        
        st.subheader("Tabla Comparativa Completa")
        #...
        
        # --- NEW: Improved Detailed Analysis View ---
        st.header("Análisis Detallado por Programa")
        program_to_detail = st.selectbox("Selecciona un programa para un análisis en profundidad:", options=filtered_df['Programa'].tolist())
        
        if program_to_detail:
            detail_data = filtered_df[filtered_df['Programa'] == program_to_detail].iloc[0]
            
            tab1, tab2, tab3 = st.tabs(["Análisis del Consultor", "Pros y Contras", "Datos Clave"])

            with tab1:
                st.subheader(f"Análisis para: {detail_data['Programa']}")
                st.markdown(detail_data['analisis_consultor'])

            with tab2:
                st.subheader("Puntos Fuertes")
                st.success(f"**Pro:** {detail_data['pros']}")
                
                st.subheader("Puntos Débiles")
                st.warning(f"**Contra:** {detail_data['contras']}")

            with tab3:
                st.subheader("Información Esencial")
                st.metric("Precio Total", f"€{detail_data['precio_total_eur']:,.0f}")
                st.metric("Duración", f"{detail_data['duracion_months']:.0f} meses")
                st.metric("Créditos ECTS", f"{detail_data['credito_ECTS']:.0f}")
                st.markdown(f"**Modalidad:** {detail_data['tipo_programa']}")
                st.markdown(f"**Idioma:** {detail_data['idioma']}")
                st.markdown(f"---")
                st.markdown(f"**[Visitar web oficial]({detail_data['url_oficial']})**")

if __name__ == "__main__":
    run()