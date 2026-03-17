import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(layout="wide", page_title="Conciliación Fusion vs Infolog")

st.title("📊 Dashboard de Comparativa de Inventario")
st.markdown("Comparación entre **Fusion (Fatima)** e **Infolog**")

# --- CARGA DE ARCHIVOS ---
st.sidebar.header("Carga de Datos")
file_fusion = st.sidebar.file_uploader("1. Subir Detalle de Inventario Fatima (Fusion)", type=['xlsx', 'csv'])
file_infolog = st.sidebar.file_uploader("2. Subir Reporte m90 (Infolog)", type=['xlsx', 'csv'])

# --- ESPACIO PARA TUS EQUIVALENCIAS ---
# Instrucciones: 'Valor en Infolog': 'Valor en Fusion'
mapeo_estatus = {
    None: 'Deposito',
    'REQ': 'RevisionDA',
    'CA2': 'Canal 2',
    'CUA': 'Quarent_DA',
    'SCR': 'Scrap',
    'REV': 'Revision',
    'DON': 'Donaciones',
    'DEV': 'Devolucion',
    'BLO': 'Bloqueo_DA',
    'SCQ': 'MuestrasDA',
    'FLV': 'Deposito',
    'LAO': 'Deposito',
    'PAN': 'Deposito',
    'DPG': 'Deposito',
    'DAN': 'Deposito',
    'VAC': 'Deposito',
    'IVT': 'Deposito',
    'VIC': 'Deposito',
    'REM': 'Deposito',
    'VEN': 'Deposito',
       
}

if file_fusion and file_infolog:
    # 1. Carga de datos
    df_fusion = pd.read_csv(file_fusion, encoding='latin-1', sep=None, engine='python') 
    df_info = pd.read_csv(file_infolog, encoding='latin-1', sep=None, engine='python')

    # 2. LIMPIEZA DE FUSION
    df_fusion = df_fusion.rename(columns={
        'Artículo': 'SKU',
        'Lote': 'LOTE',
        'Subinventario': 'STATUS',
        'Existencias físicas secundarias': 'CANT_FUSION'
    })

    # 3. LIMPIEZA DE INFOLOG Y TRADUCCIÓN DE ESTATUS
    df_info = df_info.rename(columns={
        'CODPRO': 'SKU',
        'CODLOT': 'LOTE',
        'MOTIMM': 'STATUS_ORIGINAL',
        'CAJAS': 'CANT_INFOLOG'
    })

    # Aplicamos la tabla de equivalencias
    # .strip() elimina espacios invisibles antes de buscar en la tabla
    df_info['STATUS'] = df_info['STATUS_ORIGINAL'].astype(str).str.strip().map(mapeo_estatus).fillna(df_info['STATUS_ORIGINAL'].astype(str).str.strip())

    # 4. NORMALIZACIÓN DE TEXTOS (SKU y Lote)
    for df in [df_fusion, df_info]:
        df['SKU'] = df['SKU'].astype(str).str.strip()
        df['LOTE'] = df['LOTE'].astype(str).str.strip()
        df['STATUS'] = df['STATUS'].astype(str).str.strip()

    # 5. AGRUPACIÓN
    fusion_agg = df_fusion.groupby(['SKU', 'LOTE', 'STATUS'])['CANT_FUSION'].sum().reset_index()
    info_agg = df_info.groupby(['SKU', 'LOTE', 'STATUS'])['CANT_INFOLOG'].sum().reset_index()

    # 6. UNIÓN Y CÁLCULOS
    comparativa = pd.merge(fusion_agg, info_agg, on=['SKU', 'LOTE', 'STATUS'], how='outer').fillna(0)
    comparativa['Diferencia'] = comparativa['CANT_FUSION'] - comparativa['CANT_INFOLOG']
    
    def clasificar(row):
        if row['Diferencia'] == 0: return "OK"
        if row['CANT_FUSION'] > 0 and row['CANT_INFOLOG'] == 0: return "Falta en Infolog"
        if row['CANT_INFOLOG'] > 0 and row['CANT_FUSION'] == 0: return "Falta en Fusion"
        return "Diferencia de Cantidad"

    comparativa['Tipo Error'] = comparativa.apply(clasificar, axis=1)

    # --- MÉTRICAS ---
    col1, col2, col3, col4 = st.columns(4)
    total_lineas = len(comparativa)
    iguales = len(comparativa[comparativa['Diferencia'] == 0])
    
    col1.metric("Conciliación (%)", f"{(iguales/total_lineas)*100:.2f}%")
    col2.metric("Total Cajas Fusion", f"{comparativa['CANT_FUSION'].sum():,.0f}")
    col3.metric("Total Cajas Infolog", f"{comparativa['CANT_INFOLOG'].sum():,.0f}")
    col4.metric("Diferencia Neta", f"{comparativa['Diferencia'].sum():,.0f}")

    # --- CUERPO DEL DASHBOARD ---
    tab1, tab2 = st.tabs(["📊 Análisis General", "🔍 Verificador de Estatus"])

    with tab1:
        st.subheader("Distribución de Diferencias")
        fig = px.pie(comparativa, names='Tipo Error', color='Tipo Error',
                     color_discrete_map={'OK':'#2ca02c', 'Falta en Infolog':'#ff7f0e', 'Falta en Fusion':'#d62728', 'Diferencia de Cantidad':'#1f77b4'})
        st.plotly_chart(fig, use_container_width=True)

        st.subheader("Detalle de Diferencias (Solo errores)")
        solo_errores = comparativa[comparativa['Diferencia'] != 0].sort_values(by='Diferencia', ascending=False)
        st.dataframe(solo_errores, use_container_width=True)

    with tab2:
        st.subheader("Control de Mapeo")
        st.write("Estos son los estatus originales encontrados en Infolog y cómo se están traduciendo:")
        resumen_mapeo = df_info[['STATUS_ORIGINAL', 'STATUS']].drop_duplicates()
        st.table(resumen_mapeo)

else:
    st.info("👋 Bienvenido. Por favor, sube los archivos en la barra lateral para procesar la información.")