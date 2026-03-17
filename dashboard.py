import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(layout="wide", page_title="Conciliación Fusion vs Infolog")

st.title("📊 Dashboard de Comparativa de Inventario")
st.markdown("Comparación entre **Fusion (Fatima)** e **Infolog**")

# --- CARGA DE ARCHIVOS ---
file_fusion = st.sidebar.file_uploader("Subir Detalle de Inventario Fatima (Fusion)", type=['xlsx', 'csv'])
file_infolog = st.sidebar.file_uploader("Subir Reporte m90 (Infolog)", type=['xlsx', 'csv'])

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

    # 3. LIMPIEZA DE INFOLOG
    df_info = df_info.rename(columns={
        'CODPRO': 'SKU',
        'CODLOT': 'LOTE',
        'MOTIMM': 'STATUS',
        'CAJAS': 'CANT_INFOLOG'
    })

    # 4. NORMALIZACIÓN (Aquí es donde estaba el error de espacios)
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

    # --- GRÁFICOS ---
    st.subheader("Análisis de Diferencias")
    fig = px.pie(comparativa, names='Tipo Error', title='Distribución por Tipo de Hallazgo')
    st.plotly_chart(fig)

    # --- TABLA DETALLE ---
    st.subheader("Detalle de Diferencias (Solo errores)")
    solo_errores = comparativa[comparativa['Diferencia'] != 0].sort_values(by='Diferencia', ascending=False)
    st.dataframe(solo_errores, use_container_width=True)

else:
    st.info("Por favor, sube ambos archivos de Excel en la barra lateral para comenzar.")