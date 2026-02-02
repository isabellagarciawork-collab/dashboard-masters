1 import streamlit as st
     2 import pandas as pd
     3 import numpy as np
     4
     5 # --- CONFIGURACIÓN DE LA PÁGINA ---
     6 st.set_page_config(layout="wide", page_title="Dashboard de Másteres v3.0")
     7
     8 # --- LÓGICA DE DATOS Y SCORING ---
     9
    10 @st.cache_data
    11 def load_data(data_path):
    12     """Carga y pre-procesa los datos desde el CSV."""
    13     df = pd.read_csv(data_path)
    14     numeric_cols = [
    15         'duracion_months', 'precio_total_eur', 'credito_ECTS',
    16         'porcentaje_analitico', 'porcentaje_gerencial', 'enfoque_practico'
    17     ]
    18     for col in numeric_cols:
    19         df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    20     df['practicas_ofrecidas'] = df['practicas_ofrecidas'].astype(bool)
    21     return df
    22
    23 def calculate_scores(df):
    24     """Calcula los puntajes normalizados y el puntaje final."""
    25     scored_df = df.copy()
    26
    27     # Normalización de métricas a una escala 0-100
    28     # Costo (inverso): menor precio, mayor puntaje
    29     min_cost = scored_df['precio_total_eur'].min()
    30     max_cost = scored_df['precio_total_eur'].max()
    31     if max_cost > min_cost:
    32         scored_df['costo_score'] = 100 * (max_cost - scored_df['precio_total_eur']) / (max_cost - min_cost)
    33     else:
    34         scored_df['costo_score'] = 100
    35
    36     # Práctico: enfoque práctico y si ofrece prácticas
    37     practico_norm = 100 * scored_df['enfoque_practico'] / 5
    38     practicas_numeric = scored_df['practicas_ofrecidas'].astype(int) * 100
    39     scored_df['practico_score'] = (practico_norm * 0.6) + (practicas_numeric * 0.4)
    40
    41     # Ajuste de Perfil para Ing. Industrial
    42     scored_df['ajuste_perfil_score'] = scored_df.apply(
    43         lambda row: sum([
    44             40 if any(kw in str(row['keywords']).lower() for kw in ['operaciones', 'procesos', 'supply chain']) else 0,
    45             30 if any(kw in str(row['keywords']).lower() for kw in ['industria 4.0', 'digital']) else 0,
    46             30 if any(kw in str(row['keywords']).lower() for kw in ['analitica', 'datos']) else 0
    47         ]), axis=1
    48     )
    49
    50     # Pesos para el puntaje final
    51     weights = {'ajuste_perfil': 0.30, 'analitico': 0.25, 'gerencial': 0.15, 'practico': 0.20, 'costo': 0.10}
    52
    53     scored_df['Puntaje Final'] = (
    54         scored_df['ajuste_perfil_score'] * weights['ajuste_perfil'] +
    55         scored_df['porcentaje_analitico'] * weights['analitico'] +
    56         scored_df['porcentaje_gerencial'] * weights['gerencial'] +
    57         scored_df['practico_score'] * weights['practico'] +
    58         scored_df['costo_score'] * weights['costo']
    59     ) / 100 # Dividir por 100 para un puntaje final sobre 100
    60
    61     return scored_df.sort_values(by='Puntaje Final', ascending=False)
    62
    63 # --- INICIALIZACIÓN DE LA APP ---
    64
    65 # Inicializar estado de sesión para las notas
    66 if 'notas_personales' not in st.session_state:
    67     st.session_state.notas_personales = {}
    68
    69 # Cargar y procesar datos
    70 try:
    71     df = load_data('masters_data_v3.csv')
    72     scored_df = calculate_scores(df)
    73 except FileNotFoundError:
    74     st.error("Error crítico: No se encuentra el archivo `masters_data_v3.csv`. Asegúrate de que está en el repositorio de
       GitHub.")
    75     st.stop()
    76
    77
    78 # --- UI DEL DASHBOARD ---
    79
    80 st.title("Dashboard de Decisión de Másteres v3.0")
    81 st.markdown("Una herramienta de análisis para **Ingenieros/as Industriales** buscando un perfil híbrido en Operaciones,
       Tecnología y Datos.")
    82
    83 # --- SECCIÓN DE CONCLUSIONES Y DATOS CLAVE ---
    84 with st.expander("Ver Conclusiones y Datos Clave del Análisis"):
    85     st.subheader("Veredicto del Consultor")
    86     st.info("""
    87     Para un perfil de Ingeniería Industrial, el máster ideal no es ni un MBA puro ni un Data Science puro.
    88     El objetivo es encontrar programas que actúen como un **puente**, aplicando tecnología y datos para optimizar
    89     el core de la ingeniería: **operaciones, procesos y cadena de suministro.** Los programas con mayor puntaje
    90     en este dashboard reflejan ese equilibrio.
    91     """)
    92
    93     # Métricas clave
    94     avg_price = scored_df['precio_total_eur'].mean()
    95     best_value = scored_df.loc[scored_df['costo_score'].idxmax()]
    96
    97     col1, col2, col3 = st.columns(3)
    98     col1.metric("Programas Analizados", f"{len(scored_df)}")
    99     col2.metric("Precio Promedio", f"€{avg_price:,.0f}")
   100     col3.metric("Mejor Calidad/Precio", best_value['programa'], help=f"Puntaje de costo: {best_value['costo_score']:.0f}/100")
   101
   102 # --- FILTROS Y VISTA PRINCIPAL ---
   103 st.sidebar.header("Filtros de Selección")
   104 min_price, max_price = st.sidebar.slider(
   105     "Rango de Precio (€)",
   106     int(scored_df['precio_total_eur'].min()),
   107     int(scored_df['precio_total_eur'].max()),
   108     (int(scored_df['precio_total_eur'].min()), int(scored_df['precio_total_eur'].max()))
   109 )
   110 min_score = st.sidebar.slider("Puntaje Final Mínimo", 0, 100, 40)
   111 ciudades = st.sidebar.multiselect("Ciudad", options=scored_df['ciudad'].unique(), default=scored_df['ciudad'].unique())
   112
   113 filtered_df = scored_df[
   114     (scored_df['precio_total_eur'].between(min_price, max_price)) &
   115     (scored_df['Puntaje Final'] >= min_score) &
   116     (scored_df['ciudad'].isin(ciudades))
   117 ]
   118
   119 st.header("Ranking de Programas Filtrados")
   120
   121 if filtered_df.empty:
   122     st.warning("No se encontraron programas con los filtros actuales. Intenta ampliar los rangos.")
   123 else:
   124     for index, row in filtered_df.iterrows():
   125         with st.container(border=True):
   126             col1, col2, col3 = st.columns([4, 1, 1])
   127             with col1:
   128                 st.markdown(f"#### {row['programa']}")
   129                 st.caption(f"{row['universidad']} | {row['ciudad']} | {row['modalidad']}")
   130             with col2:
   131                 st.metric("Puntaje Final", f"{row['Puntaje Final']:.1f}")
   132             with col3:
   133                 st.metric("Precio", f"€{row['precio_total_eur']:,.0f}")
   134
   135             # --- SECCIÓN DE DETALLE Y NOTAS ---
   136             with st.expander("Ver Análisis Detallado y Dejar Notas"):
   137                 tab1, tab2, tab3 = st.tabs(["Análisis del Consultor", "Detalles y Métricas", "Mis Notas Personales"])
   138
   139                 with tab1:
   140                     st.markdown(str(row['analisis_consultor']))
   141
   142                 with tab2:
   143                     st.markdown(f"**Componentes Clave:** {row['componentes_curriculares']}")
   144                     st.markdown(f"**Salida Laboral Típica:** {row['salida_laboral']}")
   145
   146                     c1, c2, c3 = st.columns(3)
   147                     c1.progress(int(row['porcentaje_analitico']), text=f"Foco Analítico ({row['porcentaje_analitico']}%)")
   148                     c2.progress(int(row['porcentaje_gerencial']), text=f"Foco Gerencial ({row['porcentaje_gerencial']}%)")
   149                     c3.progress(int(row['practico_score']), text=f"Orientación Práctica ({int(row['practico_score'])}%)")
   150
   151                 with tab3:
   152                     st.info("Tus notas se guardan solo durante esta sesión del navegador.")
   153                     # Usamos el 'id' del programa para una clave única en el session_state
   154                     nota_guardada = st.session_state.notas_personales.get(row['id'], "")
   155                     nota_actual = st.text_area("Escribe aquí tus conclusiones, preguntas o ideas...", value=nota_guardada,
       key=f"nota_{row['id']}")
   156                     st.session_state.notas_personales[row['id']] = nota_actual
