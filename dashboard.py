import streamlit as st
import pandas as pd
import plotly.express as px
import os
from io import BytesIO

st.set_page_config(layout="wide", page_title="Conciliación Fusion vs Infolog")

st.title("📊 SnapShot Fusion Infolog")
st.markdown("Comparación entre **Fusion** e **Infolog** para **NEWPGA**")

# --- FUNCIONES DE MEMORIA AMPLIADAS ---
def guardar_en_memoria(df_comparativa, df_perdidos, df_fallas_fechas, total_cajas, total_pallets):
    df_comparativa.to_pickle("ultima_comparativa.pkl")
    df_perdidos.to_pickle("ultimo_reporte_perdidos.pkl")
    df_fallas_fechas.to_pickle("ultimo_fallas_fechas.pkl")
    
    with open("ultimas_metricas.txt", "w") as f:
        f.write(f"{total_cajas},{total_pallets}")

def cargar_de_memoria():
    if (os.path.exists("ultima_comparativa.pkl") and 
        os.path.exists("ultimo_reporte_perdidos.pkl") and 
        os.path.exists("ultimo_fallas_fechas.pkl")):
        
        comparativa = pd.read_pickle("ultima_comparativa.pkl")
        perdidos = pd.read_pickle("ultimo_reporte_perdidos.pkl")
        fallas_fechas = pd.read_pickle("ultimo_fallas_fechas.pkl")
        
        total_cajas, total_pallets = 0, 0
        if os.path.exists("ultimas_metricas.txt"):
            with open("ultimas_metricas.txt", "r") as f:
                datos = f.read().split(",")
                total_cajas = int(float(datos[0]))
                total_pallets = int(float(datos[1]))
                
        return comparativa, perdidos, fallas_fechas, total_cajas, total_pallets
    return None

# --- CARGA DE DATOS ---
st.sidebar.header("Carga de Datos")
file_fusion = st.sidebar.file_uploader("1. Subir Detalle de Inventario Fatima (Fusion)", type=['xlsx', 'csv'])
file_infolog = st.sidebar.file_uploader("2. Subir Reporte m90 (Infolog)", type=['xlsx', 'csv'])

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
df_reporte_perdidos = pd.DataFrame()
df_fallas_fechas_pallet = pd.DataFrame()
total_cajas_perdidas = 0
total_pallets_perdidos = 0

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

    # 2. LIMPIEZA DE FUSION Y CAPTURA DE FECHA VENCIMIENTO (COLUMNA F -> Índice 5)
    if len(df_fusion.columns) >= 6:
        col_venc_fusion = df_fusion.columns[5]
        df_fusion = df_fusion.rename(columns={col_venc_fusion: 'FECHA_VENC_FUSION'})
    else:
        df_fusion['FECHA_VENC_FUSION'] = pd.NaT

    df_fusion = df_fusion.rename(columns={
        'Artículo': 'SKU',
        'Lote': 'LOTE',
        'Subinventario': 'STATUS',
        'Existencias físicas secundarias': 'CANT_FUSION'
    })
    
    # Normalización inicial de llaves
    df_fusion['SKU'] = df_fusion['SKU'].astype(str).str.strip()
    df_fusion['LOTE'] = df_fusion['LOTE'].astype(str).str.strip()
    
    # Lectura robusta de fechas en Fusion
    df_fusion['FECHA_VENC_FUSION'] = pd.to_datetime(df_fusion['FECHA_VENC_FUSION'], dayfirst=True, errors='coerce')

    # MAESTRO INDEPENDIENTE DE FECHAS DE FUSION (Por SKU y Lote, ignorando el Estatus)
    maestro_fechas_fusion = df_fusion.dropna(subset=['FECHA_VENC_FUSION']).groupby(['SKU', 'LOTE'])['FECHA_VENC_FUSION'].first().reset_index()

    # 3. IDENTIFICAR POSICIÓN, PALLET (COLUMNA U -> Índice 20) Y FECHA EN INFOLOG (COLUMNA V/W -> Índice 21/22)
    nombre_col_larga = "TRIM(GEPAL.ZONSTS||'-'|| RIGHT('000'||GEPAL.ALLSTS, 3) ||'-'|| RIGHT('0000'||GEPAL.DPLSTS, 4) ||'-'|| RIGHT('00'||GEPAL.NIVSTS, 2))"
    
    col_posicion_real = None
    for col in df_info.columns:
        if "GEPAL.ZONSTS" in str(col) or str(col).strip() == nombre_col_larga:
            col_posicion_real = col
            break
            
    if col_posicion_real is None and len(df_info.columns) >= 9:
        col_posicion_real = df_info.columns[8]

    # Captura de columna U (Pallet / CODPAL)
    if len(df_info.columns) >= 21:
        col_pallet_info = df_info.columns[20]
        df_info = df_info.rename(columns={col_pallet_info: 'PALLET'})
    else:
        df_info['PALLET'] = ""

    # Captura de fecha en Infolog (Buscamos preferentemente Columna V - DATFVI YYYYMMDD)
    if len(df_info.columns) >= 22:
        col_venc_info = df_info.columns[21] # Columna V (DATFVI)
        df_info = df_info.rename(columns={col_venc_info: 'FECHA_VENC_INFOLOG_RAW'})
    elif len(df_info.columns) >= 23:
        col_venc_info = df_info.columns[22] # Columna W como respaldo
        df_info = df_info.rename(columns={col_venc_info: 'FECHA_VENC_INFOLOG_RAW'})
    else:
        df_info['FECHA_VENC_INFOLOG_RAW'] = ""

    # Renombramos las columnas estándares de Infolog
    dicc_rename_info = {
        'CODPRO': 'SKU',
        'CODLOT': 'LOTE',
        'MOTIMM': 'STATUS_ORIGINAL',
        'CAJAS': 'CANT_INFOLOG'
    }
    if col_posicion_real:
        dicc_rename_info[col_posicion_real] = 'POSICION'

    df_info = df_info.rename(columns=dicc_rename_info)
    df_info['SKU'] = df_info['SKU'].astype(str).str.strip()
    df_info['LOTE'] = df_info['LOTE'].astype(str).str.strip()
    df_info['PALLET'] = df_info['PALLET'].astype(str).str.strip().replace(['nan', 'None', ''], '-')
    
    # 🆕 PARSEO ROBUSTO DE FECHAS DE INFOLOG (Soporta YYYYMMDD y DD/MM/YYYY)
    raw_dates = df_info['FECHA_VENC_INFOLOG_RAW'].astype(str).str.strip().str.replace('.0', '', regex=False)
    # Intentamos primero YYYYMMDD (Columna V)
    parsed_v = pd.to_datetime(raw_dates, format='%Y%m%d', errors='coerce')
    # Si falla, intentamos formato de fecha estándar (Columna W)
    parsed_w = pd.to_datetime(raw_dates, dayfirst=True, errors='coerce')
    # Combinamos ambas
    df_info['FECHA_VENC_INFOLOG'] = parsed_v.fillna(parsed_w)

    # Forzar vacíos a 'Deposito' antes del mapeo
    df_info['STATUS_ORIGINAL'] = df_info['STATUS_ORIGINAL'].astype(str).str.strip().replace(['nan', 'None', ''], 'Deposito')
    df_info['STATUS'] = df_info['STATUS_ORIGINAL'].map(mapeo_estatus).fillna(df_info['STATUS_ORIGINAL'])
    
    if 'POSICION' in df_info.columns:
        df_info['POSICION'] = df_info['POSICION'].astype(str).str.strip()
    else:
        df_info['POSICION'] = ""

    # Lógica de Pallets Perdidos
    condicion_perdidos = (df_info['STATUS_ORIGINAL'] == 'VAC') | (df_info['POSICION'].str.startswith('A-998', na=False))
    df_perdidos_raw = df_info[condicion_perdidos].copy()
    
    total_cajas_perdidas = df_perdidos_raw['CANT_INFOLOG'].sum()
    total_pallets_perdidos = len(df_perdidos_raw)
    
    df_reporte_perdidos = df_perdidos_raw[['SKU', 'LOTE', 'STATUS_ORIGINAL', 'POSICION', 'CANT_INFOLOG']].copy()
    df_reporte_perdidos = df_reporte_perdidos.rename(columns={'STATUS_ORIGINAL': 'ESTATUS ORIGINAL', 'CANT_INFOLOG': 'CAJAS'})

    # 4. NORMALIZACIÓN CRÍTICA RESTANTE
    df_fusion['STATUS'] = df_fusion['STATUS'].astype(str).str.strip()
    df_info['STATUS'] = df_info['STATUS'].astype(str).str.strip()

    # 5. AGRUPACIONES PARA EL CUADRO DE DIFERENCIAS
    fusion_agg = df_fusion.groupby(['SKU', 'LOTE', 'STATUS'])['CANT_FUSION'].sum().reset_index()
    info_agg_volumen = df_info.groupby(['SKU', 'LOTE', 'STATUS'])['CANT_INFOLOG'].sum().reset_index()

    # 6. UNIÓN Y CÁLCULOS GENERALES
    comparativa = pd.merge(fusion_agg, info_agg_volumen, on=['SKU', 'LOTE', 'STATUS'], how='outer')
    comparativa['CANT_FUSION'] = comparativa['CANT_FUSION'].fillna(0)
    comparativa['CANT_INFOLOG'] = comparativa['CANT_INFOLOG'].fillna(0)
    comparativa['Diferencia'] = comparativa['CANT_FUSION'] - comparativa['CANT_INFOLOG']
    
    # Cruce maestro de fechas para la pestaña general
    comparativa = pd.merge(comparativa, maestro_fechas_fusion, on=['SKU', 'LOTE'], how='left')
    comparativa['Vencimiento'] = comparativa['FECHA_VENC_FUSION']
    comparativa['Caducidad'] = comparativa['Vencimiento'] - pd.Timedelta(days=180)
    
    comparativa['Vencimiento_str'] = comparativa['Vencimiento'].dt.strftime('%Y-%m-%d').fillna('-')
    comparativa['Caducidad_str'] = comparativa['Caducidad'].dt.strftime('%Y-%m-%d').fillna('-')

    def clasificar(row):
        if row['Diferencia'] == 0: return "OK"
        if row['CANT_FUSION'] > 0 and row['CANT_INFOLOG'] == 0: return "Falta en Infolog"
        if row['CANT_INFOLOG'] > 0 and row['CANT_FUSION'] == 0: return "Falta en Fusion"
        return "Diferencia de Cantidad"

    comparativa['Tipo Error'] = comparativa.apply(clasificar, axis=1)

    # 7. ESTRUCTURACIÓN DE AUDITORÍA DETALLADA (UNA LÍNEA POR PALLET DE INFOLOG)
    audit_pallets = df_info[['SKU', 'LOTE', 'STATUS', 'PALLET', 'FECHA_VENC_INFOLOG']].copy()
    audit_pallets = pd.merge(audit_pallets, maestro_fechas_fusion, on=['SKU', 'LOTE'], how='left')

    def evaluar_delta_fechas(row):
        f_fusion = row['FECHA_VENC_FUSION']
        f_info = row['FECHA_VENC_INFOLOG']
        
        if pd.notna(f_fusion) and pd.isna(f_info):
            return "🚨 Infolog sin Fecha"
            
        if pd.isna(f_fusion) or pd.isna(f_info):
            return "OK"
            
        delta_dias = (f_info - f_fusion).days
        if delta_dias > 0 or delta_dias < -30:
            return "Falla Vencimiento (Desvío)"
        return "OK"

    audit_pallets['Estado Fecha'] = audit_pallets.apply(evaluar_delta_fechas, axis=1)
    
    audit_pallets['Venc_Fusion_str'] = audit_pallets['FECHA_VENC_FUSION'].dt.strftime('%Y-%m-%d').fillna('-')
    audit_pallets['Venc_Infolog_str'] = audit_pallets['FECHA_VENC_INFOLOG'].dt.strftime('%Y-%m-%d').fillna('-')

    # Filtramos para el reporte únicamente los desvíos (Anomalías o Vacíos)
    df_anomalias_fecha = audit_pallets[audit_pallets['Estado Fecha'].isin(["🚨 Infolog sin Fecha", "Falla Vencimiento (Desvío)"])].copy()
    
    # Ordenamos asignando máxima prioridad a las fechas vacías en Infolog
    if not df_anomalias_fecha.empty:
        df_anomalias_fecha['prioridad'] = df_anomalias_fecha['Estado Fecha'].apply(lambda x: 0 if "sin Fecha" in x else 1)
        df_anomalias_fecha = df_anomalias_fecha.sort_values(by=['prioridad', 'SKU', 'LOTE']).drop(columns=['prioridad'])
        
        df_fallas_exportar = df_anomalias_fecha[['SKU', 'LOTE', 'STATUS', 'PALLET', 'Venc_Fusion_str', 'Venc_Infolog_str', 'Estado Fecha']].copy()
        df_fallas_exportar.columns = ['SKU', 'LOTE', 'ESTATUS', 'NUMERO PALLET', 'FECHA FUSION (Base)', 'FECHA INFOLOG', 'DIAGNÓSTICO CRUCE']
        df_fallas_fechas_pallet = df_fallas_exportar
    else:
        df_fallas_fechas_pallet = pd.DataFrame()

    # GUARDAR TODO EN MEMORIA LOCAL
    guardar_en_memoria(comparativa, df_reporte_perdidos, df_fallas_fechas_pallet, total_cajas_perdidas, total_pallets_perdidos)
    st.sidebar.success("✅ Datos procesados y guardados de forma global.")

else:
    datos_memoria = cargar_de_memoria()
    if datos_memoria is not None:
        comparativa, df_reporte_perdidos, df_fallas_fechas_pallet, total_cajas_perdidas, total_pallets_perdidos = datos_memoria
        st.sidebar.info("ℹ️ Mostrando última consulta guardada.")
    else:
        st.info("👋 Bienvenido. Por favor, sube los archivos en la barra lateral para comenzar.")

# --- VISUALIZACIÓN DE RESULTADOS ---
if comparativa is not None:
    # MÉTRICAS
    col1, col2, col3, col4, col5 = st.columns(5)
    total_lineas = len(comparativa)
    iguales = len(comparativa[comparativa['Diferencia'] == 0])

    col1.metric("Conciliación (%)", f"{(iguales/total_lineas)*100:.2f}%")
    col2.metric("Total Fusion", f"{comparativa['CANT_FUSION'].sum():,.0f}")
    col3.metric("Total Infolog", f"{comparativa['CANT_INFOLOG'].sum():,.0f}")
    col4.metric("Dif. Neta", f"{comparativa['Diferencia'].sum():,.0f}")
    
    col5.metric(
        label="📦 Pallets Perdidos (Cajas / Plts)", 
        value=f"{total_cajas_perdidas:,.0f} / {total_pallets_perdidos}", 
        delta="Alerta" if total_pallets_perdidos > 0 else "Limpio", 
        delta_color="inverse" if total_pallets_perdidos > 0 else "normal"
    )

    tab1, tab2, tab3 = st.tabs(["📊 Análisis General y Diferencias", "🔍 Auditoría de Estatus y Fechas", "🚨 Detalle Pallets Perdidos"])

    with tab1:
        st.subheader("Distribución de Diferencias")
        fig = px.pie(comparativa, names='Tipo Error', color='Tipo Error',
                     color_discrete_map={'OK':'#2ca02c', 'Falta en Infolog':'#ff7f0e', 'Falta en Fusion':'#d62728', 'Diferencia de Cantidad':'#1f77b4'})
        st.plotly_chart(fig, use_container_width=True)

        st.subheader("Detalle de Diferencias (Solo errores) con Vencimiento Seguro de Fusion")
        solo_errores = comparativa[comparativa['Diferencia'] != 0].sort_values(by='Diferencia', ascending=False)
        
        solo_errores['Vencimiento'] = solo_errores['Vencimiento_str']
        solo_errores['Caducidad'] = solo_errores['Caducidad_str']

        columnas_reporte = ['SKU', 'LOTE', 'STATUS', 'CANT_FUSION', 'CANT_INFOLOG', 'Diferencia', 'Tipo Error', 'Vencimiento', 'Caducidad']
        df_errores_final = solo_errores[columnas_reporte]

        output = BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df_errores_final.to_excel(writer, index=False, sheet_name='Errores_Inventario')
        processed_data = output.getvalue()

        st.download_button(
            label="📥 Descargar Errores con Vencimientos Fusion (.xlsx)",
            data=processed_data,
            file_name="errores_y_vencimientos_fusion.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        
        def color_negativo_rojo(val):
            if isinstance(val, (int, float)) and val < 0:
                return 'color: #d62728; font-weight: bold;'
            return ''

        df_con_estilo = df_errores_final.style.format({
            'CANT_FUSION': '{:,.0f}',
            'CANT_INFOLOG': '{:,.0f}',
            'Diferencia': '{:,.0f}'
        }).map(color_negativo_rojo, subset=['Diferencia'])
        
        st.dataframe(df_con_estilo, use_container_width=True, hide_index=True)

    with tab2:
        st.subheader("🔍 Control Cruzado de Fechas (Prioridad: Infolog Vacío por Pallet)")
        st.write("Se exponen los pallets individuales con fecha faltante en Infolog y luego los desvíos operativos mayores a 30 días.")
        
        if not df_fallas_fechas_pallet.empty:
            st.error(f"⚠️ Se detectaron {len(df_fallas_fechas_pallet)} pallets con novedades o fallas de vencimiento.")
            
            output_fechas = BytesIO()
            with pd.ExcelWriter(output_fechas, engine='xlsxwriter') as writer:
                df_fallas_fechas_pallet.to_excel(writer, index=False, sheet_name='Control_Vencimientos')
            processed_data_fechas = output_fechas.getvalue()

            st.download_button(
                label="📥 Descargar Reporte de Vencimientos por Pallet (.xlsx)",
                data=processed_data_fechas,
                file_name="reporte_auditoria_vencimientos.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
            
            st.dataframe(df_fallas_fechas_pallet, use_container_width=True, hide_index=True)
        else:
            st.success("🎉 ¡Excelente! Todos los vencimientos están cargados en Infolog y cumplen con los deltas admitidos.")

        st.subheader("Mapeo General de Estatus")
        try:
            if 'df_info' in locals():
                chequeo_mapeo = df_info[['STATUS_ORIGINAL', 'STATUS']].drop_duplicates().sort_values('STATUS_ORIGINAL')
                chequeo_mapeo.columns = ['Código en Infolog (Original)', 'Se muestra en Dashboard como:']
                st.dataframe(chequeo_mapeo, use_container_width=True, hide_index=True)
            else:
                st.info("Mostrando estatus de la última carga guardada:")
                resumen_status = comparativa[['STATUS']].drop_duplicates().sort_values('STATUS')
                st.dataframe(resumen_status, use_container_width=True, hide_index=True)
        except Exception as e:
            st.warning("No se puede mostrar el detalle del mapeo.")

    with tab3:
        st.subheader("🚨 Detalle de Pallets Perdidos en Infolog")
        st.write("Registros que cumplen con estatus **VAC** o ubicaciones que inician con **A-998**.")
        
        if not df_reporte_perdidos.empty:
            output_p = BytesIO()
            with pd.ExcelWriter(output_p, engine='xlsxwriter') as writer:
                df_reporte_perdidos.to_excel(writer, index=False, sheet_name='Pallets_Perdidos')
            processed_data_p = output_p.getvalue()

            st.download_button(
                label="📥 Descargar Reporte de Pérdidas en Excel (.xlsx)",
                data=processed_data_p,
                file_name="reporte_pallets_perdidos.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
            
            df_p_estilo = df_reporte_perdidos.style.format({'CAJAS': '{:,.0f}'})
            st.dataframe(df_p_estilo, use_container_width=True, hide_index=True)
        else:
            st.success("🎉 ¡Excelente! No se registran pallets perdidos en la consulta actual.")