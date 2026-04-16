import streamlit as st
import pandas as pd
import plotly.express as px
import os
from io import BytesIO

st.set_page_config(layout="wide", page_title="Conciliación Fusion vs Infolog")

st.title("📊 SnapShot Fusion Infolog")
st.markdown("Comparación entre **Fusion** e **Infolog** para **NEWPGA**")

# --- FUNCIONES DE MEMORIA (OPCIÓN 2) ---
# Guardamos los resultados en un archivo tipo 'pickle' que Python lee muy rápido
def guardar_en_memoria(df):
    df.to_pickle("ultima_comparativa.pkl")

def cargar_de_memoria():
    if os.path.exists("ultima_comparativa.pkl"):
        return pd.read_pickle("ultima_comparativa.pkl")
    return None

# --- CARGA DE ARCHIVOS ---
st.sidebar.header("Carga de Datos")
file_fusion = st.sidebar.file_uploader("1. Subir Detalle de Inventario Fatima (Fusion)", type=['xlsx', 'csv'])
file_infolog = st.sidebar.file_uploader("2. Subir Reporte m90 (Infolog)", type=['xlsx', 'csv'])

# --- ESPACIO PARA TUS EQUIVALENCIAS ---
mapeo_estatus = {
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
    'nan': 'Deposito',
    '': 'Deposito',
    'IVT': 'Deposito',
    'VEN': 'Deposito',
    'VIC': 'Deposito',
    'REM': 'Deposito',
    'MUE': 'MuestrasDA',

}

comparativa = None

# Si el usuario sube AMBOS archivos, procesamos de nuevo
if file_fusion and file_infolog:
    # 1. Carga de datos
    try:
        df_fusion = pd.read_excel(file_fusion)
    except:
        df_fusion = pd.read_csv(file_fusion, encoding='latin-1', sep=None, engine='python')
    
    try:
        df_info = pd.read_excel(file_infolog)
    except:
        df_info = pd.read_csv(file_infolog, encoding='latin-1', sep=None, engine='python')

    # 2. LIMPIEZA DE FUSION
    df_fusion = df_fusion.rename(columns={
        'Artículo': 'SKU',
        'Lote': 'LOTE',
        'Subinventario': 'STATUS',
        'Existencias físicas secundarias': 'CANT_FUSION'
    })

    # 3. LIMPIEZA DE INFOLOG Y TRADUCCIÓN
    df_info = df_info.rename(columns={
        'CODPRO': 'SKU',
        'CODLOT': 'LOTE',
        'MOTIMM': 'STATUS_ORIGINAL',
        'CAJAS': 'CANT_INFOLOG'
    })

    # Forzar vacíos a 'Deposito' antes del mapeo
    df_info['STATUS_ORIGINAL'] = df_info['STATUS_ORIGINAL'].astype(str).str.strip().replace(['nan', 'None', ''], 'Deposito')
    df_info['STATUS'] = df_info['STATUS_ORIGINAL'].map(mapeo_estatus).fillna(df_info['STATUS_ORIGINAL'])

    # 4. NORMALIZACIÓN CRÍTICA
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

    # GUARDAR EN MEMORIA PARA LA PRÓXIMA VEZ
    guardar_en_memoria(comparativa)
    st.sidebar.success("✅ Datos procesados y guardados en memoria.")

else:
    # Si no hay archivos subidos, intentamos cargar lo último que se guardó
    comparativa = cargar_de_memoria()
    if comparativa is not None:
        st.sidebar.info("ℹ️ Mostrando última consulta guardada.")
    else:
        st.info("👋 Bienvenido. Por favor, sube los archivos en la barra lateral para comenzar."
        "Desarr")

# --- VISUALIZACIÓN DE RESULTADOS ---
if comparativa is not None:
    # MÉTRICAS
    col1, col2, col3, col4 = st.columns(4)
    total_lineas = len(comparativa)
    iguales = len(comparativa[comparativa['Diferencia'] == 0])
    
    col1.metric("Conciliación (%)", f"{(iguales/total_lineas)*100:.2f}%")
    col2.metric("Total Fusion", f"{comparativa['CANT_FUSION'].sum():,.0f}")
    col3.metric("Total Infolog", f"{comparativa['CANT_INFOLOG'].sum():,.0f}")
    col4.metric("Dif. Neta", f"{comparativa['Diferencia'].sum():,.0f}")

    tab1, tab2 = st.tabs(["📊 Análisis General", "🔍 Verificador de Estatus"])

    with tab1:
        st.subheader("Distribución de Diferencias")
        fig = px.pie(comparativa, names='Tipo Error', color='Tipo Error',
                     color_discrete_map={'OK':'#2ca02c', 'Falta en Infolog':'#ff7f0e', 'Falta en Fusion':'#d62728', 'Diferencia de Cantidad':'#1f77b4'})
        st.plotly_chart(fig, use_container_width=True)

        st.subheader("Detalle de Diferencias (Solo errores)")
        solo_errores = comparativa[comparativa['Diferencia'] != 0].sort_values(by='Diferencia', ascending=False)
        
        # --- FUNCIÓN PARA DESCARGAR EXCEL ---
        output = BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            solo_errores.to_excel(writer, index=False, sheet_name='Errores_Inventario')
        processed_data = output.getvalue()

        st.download_button(
            label="📥 Descargar Errores en Excel (.xlsx)",
            data=processed_data,
            file_name="errores_inventario_conciliacion.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        
        st.dataframe(solo_errores, use_container_width=True)

    with tab2:
        st.subheader("🔍 Control de Mapeo de Estatus")
        st.write("Usa esta tabla para verificar cómo se agruparon los estatus.")
        
        # Intentamos obtener la info de los archivos recién subidos
        # Si no existen (porque cargamos de memoria), usamos la tabla comparativa
        try:
            if 'df_info' in locals():
                # Si acabamos de subir los archivos
                chequeo_mapeo = df_info[['STATUS_ORIGINAL', 'STATUS']].drop_duplicates().sort_values('STATUS_ORIGINAL')
                chequeo_mapeo.columns = ['Código en Infolog (Original)', 'Se muestra en Dashboard como:']
                st.dataframe(chequeo_mapeo, use_container_width=True, hide_index=True)
            else:
                # Si estamos viendo datos viejos guardados en memoria
                st.info("Mostrando estatus unificados de la última carga guardada:")
                resumen_status = comparativa[['STATUS']].drop_duplicates().sort_values('STATUS')
                st.dataframe(resumen_status, use_container_width=True, hide_index=True)
        except Exception as e:
            st.warning("No se puede mostrar el detalle del mapeo en este momento.")

        st.info("""
        **Tip para validación:**
        Si ves que un código no tiene su equivalente correcto, debes agregarlo a la lista `mapeo_estatus` 
        en tu código de GitHub y volver a subir los archivos.
        """)