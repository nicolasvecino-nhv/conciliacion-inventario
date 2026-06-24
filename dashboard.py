import streamlit as st
import pandas as pd
import plotly.express as px
import os
from io import BytesIO

st.set_page_config(layout="wide", page_title="Conciliación Fusion vs Infolog")

st.title("📊 SnapShot Fusion Infolog")
st.markdown("Comparación entre **Fusion** e **Infolog** para **NEWPGA**")

# --- FUNCIONES DE MEMORIA (OPCIÓN 2) ---
def guardar_en_memoria(df):
    df.to_pickle("ultima_comparativa.pkl")

def cargar_de_memoria():
    if os.path.exists("ultima_comparativa.pkl"):
        return pd.read_pickle("ultima_comparativa.pkl")
    return None

# --- CARGA DE DATOS ---
st.sidebar.header("Carga de Datos")
file_fusion = st.sidebar.file_uploader("1. Subir Detalle de Inventario Fatima (Fusion)", type=['xlsx', 'csv'])
file_infolog = st.sidebar.file_uploader("2. Subir Reporte m90 (Infolog)", type=['xlsx', 'csv'])

# Revisar error de lectura
try:
    df_info = pd.read_excel(file_infolog)
    st.write("Columnas detectadas en Infolog:", list(df_info.columns)) # <-- LÍNEA TEMP PARA CORROBORAR
except:
    ...

# --- EQUIVALENCIAS DE ESTATUS ---
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

    # 3. IDENTIFICAR COLUMNA DE POSICIÓN EN INFOLOG (Nombre complejo de fórmula SQL)
    nombre_col_larga = "TRIM(GEPAL.ZONSTS||'-'|| RIGHT('000'||GEPAL.ALLSTS, 3) ||'-'|| RIGHT('0000'||GEPAL.DPLSTS, 4) ||'-'|| RIGHT('00'||GEPAL.NIVSTS, 2))"
    
    col_posicion_real = None
    for col in df_info.columns:
        if "GEPAL.ZONSTS" in str(col) or str(col).strip() == nombre_col_larga:
            col_posicion_real = col
            break
            
    # Respaldo: si no coincide el nombre exacto, usamos la columna I (índice 8)
    if col_posicion_real is None and len(df_info.columns) >= 9:
        col_posicion_real = df_info.columns[8]

    # Renombramos las columnas de Infolog
    dicc_rename_info = {
        'CODPRO': 'SKU',
        'CODLOT': 'LOTE',
        'MOTIMM': 'STATUS_ORIGINAL',
        'CAJAS': 'CANT_INFOLOG'
    }
    if col_posicion_real:
        dicc_rename_info[col_posicion_real] = 'POSICION'

    df_info = df_info.rename(columns=dicc_rename_info)

    # Forzar vacíos a 'Deposito' antes del mapeo
    df_info['STATUS_ORIGINAL'] = df_info['STATUS_ORIGINAL'].astype(str).str.strip().replace(['nan', 'None', ''], 'Deposito')
    df_info['STATUS'] = df_info['STATUS_ORIGINAL'].map(mapeo_estatus).fillna(df_info['STATUS_ORIGINAL'])
    
    # Asegurar formato de texto en la posición para el filtro
    if 'POSICION' in df_info.columns:
        df_info['POSICION'] = df_info['POSICION'].astype(str).str.strip()
    else:
        df_info['POSICION'] = ""

    # MEJORA 1: Cálculo de Pallets Perdidos (Estatus VAC o posición comienza con A-998)
    condicion_perdidos = (df_info['STATUS_ORIGINAL'] == 'VAC') | (df_info['POSICION'].str.startswith('A-998', na=False))
    df_perdidos = df_info[condicion_perdidos]
    total_perdidos = df_perdidos['CANT_INFOLOG'].sum()
    st.session_state['total_perdidos'] = total_perdidos

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
        if 'total_perdidos' not in st.session_state:
            st.session_state['total_perdidos'] = 0
    else:
        st.info("👋 Bienvenido. Por favor, sube los archivos en la barra lateral para comenzar.")

# --- VISUALIZACIÓN DE RESULTADOS ---
if comparativa is not None:
    # MÉTRICAS (Dividido en 5 columnas)
    col1, col2, col3, col4, col5 = st.columns(5)
    total_lineas = len(comparativa)
    iguales = len(comparativa[comparativa['Diferencia'] == 0])
    
    cant_perdidos = st.session_state.get('total_perdidos', 0)

    col1.metric("Conciliación (%)", f"{(iguales/total_lineas)*100:.2f}%")
    col2.metric("Total Fusion", f"{comparativa['CANT_FUSION'].sum():,.0f}")
    col3.metric("Total Infolog", f"{comparativa['CANT_INFOLOG'].sum():,.0f}")
    col4.metric("Dif. Neta", f"{comparativa['Diferencia'].sum():,.0f}")
    col5.metric(
        label="📦 Pallets Perdidos", 
        value=f"{cant_perdidos:,.0f}", 
        delta="- Alerta" if cant_perdidos > 0 else "Limpio", 
        delta_color="inverse"
    )

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
        
        # MEJORA 2: Formato visual y color para diferencias negativas
        def color_negativo_rojo(val):
            if isinstance(val, (int, float)) and val < 0:
                return 'color: #d62728; font-weight: bold;'
            return ''

        df_con_estilo = solo_errores.style.format({
            'CANT_FUSION': '{:,.0f}',
            'CANT_INFOLOG': '{:,.0f}',
            'Diferencia': '{:,.0f}'
        }).map(color_negativo_rojo, subset=['Diferencia'])
        
        st.dataframe(df_con_estilo, use_container_width=True)

    with tab2:
        st.subheader("🔍 Control de Mapeo de Estatus")
        st.write("Usa esta tabla para verificar cómo se agruparon los estatus.")
        
        try:
            if 'df_info' in locals():
                chequeo_mapeo = df_info[['STATUS_ORIGINAL', 'STATUS']].drop_duplicates().sort_values('STATUS_ORIGINAL')
                chequeo_mapeo.columns = ['Código en Infolog (Original)', 'Se muestra en Dashboard como:']
                st.dataframe(chequeo_mapeo, use_container_width=True, hide_index=True)
            else:
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