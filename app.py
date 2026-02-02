import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go

st.set_page_config(layout="wide", page_title="Dashboard de Másteres")
# (The rest of the initial setup and functions up to run() remain the same)
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
    # (The existing load_data function remains unchanged)
    df = pd.read_csv('masters_data.csv')
    numeric_cols = [
        'duracion_months', 'precio_total_eur', 'ranking_universidad', 
        'credito_ECTS', 'porcentaje_analitico', 'porcentaje_gerencial',
        'enfoque_practico', 'red_empresas_partners', 'tasa_empleabilidad_6m'
    ]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors='coerce')
    df['practicas_ofrecidas'] = df['practicas_ofrecidas'].astype(bool)
    df['inicio_proximo'] = pd.to_datetime(df['inicio_proximo'], errors='coerce')
    df['tasa_empleabilidad_6m'] = df['tasa_empleabilidad_6m'].fillna(df['tasa_empleabilidad_6m'].median())
    df['enfoque_practico'] = df['enfoque_practico'].fillna(df['enfoque_practico'].median())
    df['red_empresas_partners'] = df['red_empresas_partners'].fillna(df['red_empresas_partners'].median())
    return df

def normalize_to_100(series):
    """Normalizes a pandas series to a 0-100 scale."""
    if series.max() == series.min():
        return pd.Series(100, index=series.index)
    return 100 * (series - series.min()) / (series.max() - series.min())

def ajuste_perfil_score(df):
    """Calculates the profile fit score for an industrial engineer."""
    scores = pd.Series(0, index=df.index)
    # Keywords for industrial profile
    produccion_kws = ['procesos', 'producción', 'optimización', 'industrial', 'operations', 'operaciones', 'lean']
    logistica_kws = ['logística', 'supply chain']
    
    for i, row in df.iterrows():
        text_to_search = f"{row['programa']} {row['componentes_curriculares']}".lower()
        if any(kw in text_to_search for kw in produccion_kws):
            scores[i] += 30
        if any(kw in text_to_search for kw in logistica_kws):
            scores[i] += 20
        if row['practicas_ofrecidas']:
            scores[i] += 20
    return scores.clip(0, 100)

def costo_eficiencia_score(df):
    """Calculates the cost-efficiency score."""
    precio_por_credito = df['precio_total_eur'] / df['credito_ECTS'].replace(0, np.nan)
    precio_por_credito = precio_por_credito.fillna(precio_por_credito.median())
    # Inverse score: lower price is better
    if precio_por_credito.max() == precio_por_credito.min():
        return pd.Series(100, index=df.index)
    return 100 * (precio_por_credito.max() - precio_por_credito) / (precio_por_credito.max() - precio_por_credito.min())

def calculate_scores(df):
    """
    Calculates the final score for each master's program.
    """
    scored_df = df.copy()
    
    # --- Calculate Individual Score Components (0-100) ---
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

    # --- Calculate Final Weighted Score ---
    scored_df['Puntaje Final'] = (
        scored_df['ajuste_perfil_score'] * WEIGHTS['ajuste_perfil'] +
        scored_df['analitico_score'] * WEIGHTS['analitico'] +
        scored_df['gerencial_score'] * WEIGHTS['gerencial'] +
        scored_df['practico_total_score'] * WEIGHTS['practico'] +
        scored_df['empleabilidad_total_score'] * WEIGHTS['empleabilidad'] +
        scored_df['costo_score'] * WEIGHTS['costo']
    ).fillna(0)
    
    # --- Validation Checks ---
    warnings = []
    for i, row in scored_df.iterrows():
        warning_list = []
        if row['porcentaje_analitico'] + row['porcentaje_gerencial'] < 50:
            warning_list.append("No cumple el mix buscado (analítico + gerencial < 50%).")
        if row['enfoque_practico'] < 2 and not row['practicas_ofrecidas']:
            warning_list.append("Menor aplicabilidad industrial (teórico y sin prácticas).")
        if pd.isna(row['precio_total_eur']):
            warning_list.append("Precio no disponible, revisar manualmente.")
        warnings.append(" ".join(warning_list))
    scored_df['warnings'] = warnings

    return scored_df.sort_values(by='Puntaje Final', ascending=False)


def run():
    """
    Main function to run the Streamlit app.
    """
    st.title("Comparador de Másteres en Data y Gestión")
    st.markdown("""
    Para una **ingeniera industrial** que busca un máster mixto (gerencial + analítico). 
    El dashboard ordena los programas según un puntaje calculado en base a tus preferencias.
    """)
    
    df = load_data()
    scored_df = calculate_scores(df)

    # --- Sidebar Filters ---
    st.sidebar.header("Filtros")
    
    # ... (filtering logic remains the same)
    cities = st.sidebar.multiselect(
        "Ciudad",
        options=scored_df['ciudad'].unique(),
        default=scored_df['ciudad'].unique()
    )
    program_types = st.sidebar.multiselect(
        "Modalidad",
        options=scored_df['tipo_programa'].unique(),
        default=scored_df['tipo_programa'].unique()
    )
    max_price = int(scored_df['precio_total_eur'].max())
    price_range = st.sidebar.slider("Rango de Precio (EUR)", 0, max_price, (0, max_price))
    min_score = st.sidebar.slider("Puntaje Mínimo", 0, 100, 0)
    practicas = st.sidebar.checkbox("Solo con prácticas ofrecidas", value=False)
    
    filtered_df = scored_df[
        (scored_df['ciudad'].isin(cities)) &
        (scored_df['tipo_programa'].isin(program_types)) &
        (scored_df['precio_total_eur'].between(price_range[0], price_range[1])) &
        (scored_df['Puntaje Final'] >= min_score)
    ]
    if practicas:
        filtered_df = filtered_df[filtered_df['practicas_ofrecidas'] == True]

    st.header(f"Mostrando {len(filtered_df)} de {len(scored_df)} programas")
    
    if filtered_df.empty:
        st.warning("No se encontraron programas que cumplan con los filtros seleccionados.")
    else:
        # --- Main View: Top 5 and Table ---
        st.subheader("Top 5 Recomendados")
        # ... (Top 5 display remains the same)
        for i, row in filtered_df.head(5).iterrows():
            with st.container(border=True):
                col1, col2, col3 = st.columns([3, 1, 1])
                with col1:
                    st.markdown(f"**{row['programa']}** | *{row['universidad']}*")
                    st.caption(f"{row['ciudad']} - {row['tipo_programa']}")
                with col2:
                    st.metric("Puntaje Final", f"{row['Puntaje Final']:.1f}")
                with col3:
                    st.metric("Precio", f"€{row['precio_total_eur']:,.0f}")

        st.subheader("Tabla Comparativa Completa")
        # ... (Dataframe display remains the same)
        st.dataframe(filtered_df[[
            'universidad', 'programa', 'ciudad', 'tipo_programa', 'Puntaje Final', 
            'precio_total_eur', 'ajuste_perfil_score', 'analitico_score', 'gerencial_score', 
            'practico_total_score', 'empleabilidad_total_score', 'costo_score'
        ]].style.format('{:.1f}'))

        # --- Visualizations ---
        st.subheader("Visualizaciones")
        
        c1, c2 = st.columns(2)
        
        with c1:
            st.markdown("**Puntaje Final vs. Precio**")
            chart_data = filtered_df[['precio_total_eur', 'Puntaje Final', 'credito_ECTS']].copy()
            chart_data.rename(columns={'credito_ECTS': 'ECTS'}, inplace=True)
            st.scatter_chart(
                chart_data,
                x='precio_total_eur',
                y='Puntaje Final',
                size='ECTS',
                color='#3498db'
            )

        with c2:
            st.markdown("**Comparativa en Radar**")
            options = filtered_df['programa'].tolist()
            selected_programs = st.multiselect(
                "Selecciona hasta 4 programas para comparar:",
                options=options,
                default=options[:min(4, len(options))],
                max_selections=4
            )
            
            if selected_programs:
                radar_fig = go.Figure()
                
                categories = ['Ajuste Perfil', 'Analítico', 'Gerencial', 'Práctico', 'Empleabilidad', 'Costo-Eficiencia']
                
                for program in selected_programs:
                    program_data = filtered_df[filtered_df['programa'] == program].iloc[0]
                    values = [
                        program_data['ajuste_perfil_score'],
                        program_data['analitico_score'],
                        program_data['gerencial_score'],
                        program_data['practico_total_score'],
                        program_data['empleabilidad_total_score'],
                        program_data['costo_score']
                    ]
                    radar_fig.add_trace(go.Scatterpolar(
                        r=values,
                        theta=categories,
                        fill='toself',
                        name=program
                    ))
                
                radar_fig.update_layout(
                    polar=dict(radialaxis=dict(visible=True, range=[0, 100])),
                    showlegend=True
                )
                st.plotly_chart(radar_fig, use_container_width=True)
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import pyperclip

# (All previous code down to the end of the "Visualizations" section remains the same)
# ...

        # --- Detailed Analysis and Recommendation ---
        st.subheader("Análisis Detallado y Recomendación")
        
        detail_options = filtered_df['programa'].tolist()
        program_to_detail = st.selectbox(
            "Selecciona un programa para ver el detalle:",
            options=detail_options
        )
        
        if program_to_detail:
            detail_data = filtered_df[filtered_df['programa'] == program_to_detail].iloc[0]
            
            # --- Recommendation Template ---
            def get_ajuste_text(score):
                if score >= 70: return "alto"
                if score >= 40: return "medio"
                return "bajo"

            ajuste_score = detail_data['ajuste_perfil_score']
            
            # Simple logic to extract "motivos"
            motivo1 = f"Fuerte componente en { 'análisis de datos' if detail_data['analitico_score'] > 60 else 'gestión' }."
            motivo2 = f"Excelente {'enfoque práctico' if detail_data['practico_total_score'] > 60 else 'balance teórico-práctico'}."
            motivo3 = f"Buenas perspectivas de {'empleabilidad' if detail_data['empleabilidad_total_score'] > 60 else 'networking'}."
            
            recommendation_text = f"""
            Para una ingeniera industrial, el programa **{detail_data['programa']}** de *{detail_data['universidad']}* tiene un **ajuste profesional {get_ajuste_text(ajuste_score)}** (score {ajuste_score:.0f}).

            - **Ventaja clave:** {detail_data['pros']}
            - **Desventaja clave:** {detail_data['contras']}

            **Motivos para elegirlo:**
            1. {motivo1}
            2. {motivo2}
            3. {motivo3}

            **Precio:** €{detail_data['precio_total_eur']:,.0f}.
            **Enlace:** {detail_data['url_oficial']}
            """
            
            st.markdown(recommendation_text)
            
            if st.button("Copiar Recomendación"):
                pyperclip.copy(recommendation_text)
                st.success("¡Recomendación copiada al portapapeles!")


if __name__ == "__main__":
    run()
