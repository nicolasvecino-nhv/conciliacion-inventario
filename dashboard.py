import streamlit as st
import pandas as pd
import plotly.express as px
import os
from io import BytesIO

st.set_page_config(layout="wide", page_title="Conciliación Fusion vs Infolog")

st.title("📊 SnapShot Fusion Infolog")
st.markdown("Comparación entre **Fusion** e **Infolog** para **NEWPGA**")

# --- FUNCIONES DE MEMORIA ---
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
    df_fusion['FECHA_VENC_FUSION'] = pd.to_datetime(df_fusion['FECHA_VENC_FUSION'], errors='coerce')

    # MAESTRO INDEPENDIENTE DE FECHAS DE FUSION (Por SKU y Lote, ignorando el Estatus)
    maestro_fechas_fusion = df_fusion.dropna(subset=['FECHA_VENC_FUSION']).groupby(['SKU', 'LOTE'])['FECHA_VENC_FUSION'].first().reset_index()

    # 3. IDENTIFICAR POSICIÓN, PALLET (COLUMNA U -> Índice 20) Y FECHA EN INFOLOG (COLUMNA W -> Índice 22)[cite: 2]
    nombre_col_larga = "TRIM(GEPAL.ZONSTS||'-'|| RIGHT('000'||GEPAL.ALLSTS, 3) ||'-'|| RIGHT('0000'||GEPAL.DPLSTS, 4) ||'-'|| RIGHT('00'||GEPAL.NIVSTS, 2))"
    
    col_posicion_real = None
    for col in df_info.columns:
        if "GEPAL.ZONSTS" in str(col) or str(col).strip() == nombre_col_larga:
            col_posicion_real = col
            break
            
    if col_posicion_real is None and len(df_info.columns) >= 9:
        col_posicion_real = df_info.columns[8]

    # Captura de columna U (Pallet / CODPAL)[cite: 2]
    if len(df_info.columns) >= 21:
        col_pallet_info = df_info.columns[20]
        df_info = df_info.rename(columns={col_pallet_info: 'PALLET'})
    else:
        df_info['PALLET'] = ""

    # Captura de columna W (Fecha Vencimiento)[cite: 2]
    if len(df_info.columns) >= 23:
        col_venc_info = df_info.columns[22]
        df_info = df_info.rename(columns={col_venc_info: 'FECHA_VENC_INFOLOG'})
    else:
        df_info['FECHA_VENC_INFOLOG'] = pd.NaT

    # Renombramos las columnas estándares de Infolog[cite: 2]
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
    df_info['FECHA_VENC_INFOLOG'] = pd.to_datetime(df_info['FECHA_VENC_INFOLOG'], errors='coerce')

    # Forzar vacíos a 'Deposito' antes del mapeo[cite: 2]
    df_info['STATUS_ORIGINAL'] = df_info['STATUS_ORIGINAL'].astype(str).str.strip().replace(['nan', 'None', ''], 'Deposito')
    df_info['STATUS'] = df_info['STATUS_ORIGINAL'].map(mapeo_estatus).fillna(df_info['STATUS_ORIGINAL'])
    
    if 'POSICION' in df_info.columns:
        df_info['POSICION'] = df_info['POSICION'].astype(str).str.strip()
    else:
        df_info['POSICION'] = ""

    # Lógica de Pallets Perdidos[cite: 2]
    condicion_perdidos = (df_info['STATUS_ORIGINAL'] == 'VAC') | (df_info['POSICION'].str.startswith('A-998', na=False))[cite: 2]
    df_perdidos_raw = df_info[condicion_perdidos].copy()[cite: 2]
    
    total_cajas_perdidas = df_perdidos_raw['CANT_INFOLOG'].sum()[cite: 2]
    total_pallets_perdidos = len(df_perdidos_raw)[cite: 2]
    
    st.session_state['total_cajas_perdidas'] = total_cajas_perdidas[cite: 2]
    st.session_state['total_pallets_perdidos'] = total_pallets_perdidos[cite: 2]
    
    df_reporte_perdidos = df_perdidos_raw[['SKU', 'LOTE', 'STATUS_ORIGINAL', 'POSICION', 'CANT_INFOLOG']].copy()[cite: 2]
    df_reporte_perdidos = df_reporte_perdidos.rename(columns={'STATUS_ORIGINAL': 'ESTATUS ORIGINAL', 'CANT_INFOLOG': 'CAJAS'})[cite: 2]
    st.session_state['df_reporte_perdidos'] = df_reporte_perdidos[cite: 2]

    # 4. NORMALIZACIÓN CRÍTICA RESTANTE[cite: 2]
    df_fusion['STATUS'] = df_fusion['STATUS'].astype(str).str.strip()
    df_info['STATUS'] = df_info['STATUS'].astype(str).str.strip()

    # 5. AGRUPACIONES PARA EL CUADRO DE DIFERENCIAS (Aquí agrupamos sin pallet para la comparación general)[cite: 2]
    fusion_agg = df_fusion.groupby(['SKU', 'LOTE', 'STATUS'])['CANT_FUSION'].sum().reset_index()[cite: 2]
    info_agg_volumen = df_info.groupby(['SKU', 'LOTE', 'STATUS'])['CANT_INFOLOG'].sum().reset_index()

    # 6. UNIÓN Y CÁLCULOS GENERALES[cite: 2]
    comparativa = pd.merge(fusion_agg, info_agg_volumen, on=['SKU', 'LOTE', 'STATUS'], how='outer')[cite: 2]
    comparativa['CANT_FUSION'] = comparativa['CANT_FUSION'].fillna(0)[cite: 2]
    comparativa['CANT_INFOLOG'] = comparativa['CANT_INFOLOG'].fillna(0)[cite: 2]
    comparativa['Diferencia'] = comparativa['CANT_FUSION'] - comparativa['CANT_INFOLOG'][cite: 2]
    
    # Cruce maestro de fechas para la pestaña general[cite: 2]
    comparativa = pd.merge(comparativa, maestro_fechas_fusion, on=['SKU', 'LOTE'], how='left')[cite: 2]
    comparativa['Vencimiento'] = comparativa['FECHA_VENC_FUSION'][cite: 2]
    comparativa['Caducidad'] = comparativa['Vencimiento'] - pd.Timedelta(days=180)[cite: 2]
    
    comparativa['Vencimiento_str'] = comparativa['Vencimiento'].dt.strftime('%Y-%m-%d').fillna('-')[cite: 2]
    comparativa['Caducidad_str'] = comparativa['Caducidad'].dt.strftime('%Y-%m-%d').fillna('-')[cite: 2]

    def clasificar(row):
        if row['Diferencia'] == 0: return "OK"
        if row['CANT_FUSION'] > 0 and row['CANT_INFOLOG'] == 0: return "Falta en Infolog"
        if row['CANT_INFOLOG'] > 0 and row['CANT_FUSION'] == 0: return "Falta en Fusion"
        return "Diferencia de Cantidad"

    comparativa['Tipo Error'] = comparativa.apply(clasificar, axis=1)[cite: 2]

    # 🆕 7. ESTRUCTURACIÓN DE AUDITORÍA DETALLADA (UNA LÍNEA POR PALLET DE INFOLOG)
    # Tomamos el listado completo de Infolog por pallet y le cruzamos la fecha maestra de Fusion
    audit_pallets = df_info[['SKU', 'LOTE', 'STATUS', 'PALLET', 'FECHA_VENC_INFOLOG']].copy()
    audit_pallets = pd.merge(audit_pallets, maestro_fechas_fusion, on=['SKU', 'LOTE'], how='left')

    def evaluar_delta_fechas(row):
        f_fusion = row['FECHA_VENC_FUSION']
        f_info = row['FECHA_VENC_INFOLOG']
        
        if pd.notna(f_fusion) and pd.isna(f_info):
            return "🚨 Infolog sin Fecha"[cite: 2]
            
        if pd.isna(f_fusion) or pd.isna(f_info):
            return "OK"[cite: 2]
            
        delta_dias = (f_info - f_fusion).days
        if delta_dias > 0 or delta_dias < -30:
            return "Falla Vencimiento (Desvío)"[cite: 2]
        return "OK"[cite: 2]

    audit_pallets['Estado Fecha'] = audit_pallets.apply(evaluar_delta_fechas, axis=1)
    
    audit_pallets['Venc_Fusion_str'] = audit_pallets['FECHA_VENC_FUSION'].dt.strftime('%Y-%m-%d').fillna('-')[cite: 2]
    audit_pallets['Venc_Infolog_str'] = audit_pallets['FECHA_VENC_INFOLOG'].dt.strftime('%Y-%m-%d').fillna('-')[cite: 2]

    # Filtramos para el reporte únicamente los desvíos (Anomalías o Vacíos)
    df_anomalias_fecha = audit_pallets[audit_pallets['Estado Fecha'].isin(["🚨 Infolog sin Fecha", "Falla Vencimiento (Desvío)"])].copy()
    
    # Ordenamos asignando máxima prioridad a las fechas vacías en Infolog
    if not df_anomalias_fecha.empty:
        df_anomalias_fecha['prioridad'] = df_anomalias_fecha['Estado Fecha'].apply(lambda x: 0 if "sin Fecha" in x else 1)[cite: 2]
        df_anomalias_fecha = df_anomalias_fecha.sort_values(by=['prioridad', 'SKU', 'LOTE']).drop(columns=['prioridad'])[cite: 2]
        
        # Le damos formato legible para presentación
        df_fallas_exportar = df_anomalias_fecha[['SKU', 'LOTE', 'STATUS', 'PALLET', 'Venc_Fusion_str', 'Venc_Infolog_str', 'Estado Fecha']].copy()
        df_fallas_exportar.columns = ['SKU', 'LOTE', 'ESTATUS', 'NUMERO PALLET', 'FECHA FUSION (Base)', 'FECHA INFOLOG', 'DIAGNÓSTICO CRUCE'][cite: 2]
        st.session_state['df_fallas_fechas_pallet'] = df_fallas_exportar
    else:
        st.session_state['df_fallas_fechas_pallet'] = pd.DataFrame()

    # GUARDAR EN MEMORIA PARA LA PRÓXIMA VEZ
    guardar_en_memoria(comparativa)
    st.sidebar.success("✅ Datos procesados y guardados en memoria.")[cite: 2]

else:
    comparativa = cargar_de_memoria()[cite: 2]
    if comparativa is not None:
        st.sidebar.info("ℹ️ Mostrando última consulta guardada.")[cite: 2]
        if 'total_cajas_perdidas' not in st.session_state:[cite: 2]
            st.session_state['total_cajas_perdidas'] = 0[cite: 2]
            st.session_state['total_pallets_perdidos'] = 0[cite: 2]
            st.session_state['df_reporte_perdidos'] = pd.DataFrame()[cite: 2]
            st.session_state['df_fallas_fechas_pallet'] = pd.DataFrame()
    else:
        st.info("👋 Bienvenido. Por favor, sube los archivos en la barra lateral para comenzar.")[cite: 2]

# --- VISUALIZACIÓN DE RESULTADOS ---
if comparativa is not None:
    # MÉTRICAS
    col1, col2, col3, col4, col5 = st.columns(5)[cite: 2]
    total_lineas = len(comparativa)[cite: 2]
    iguales = len(comparativa[comparativa['Diferencia'] == 0])[cite: 2]
    
    cajas_p = st.session_state.get('total_cajas_perdidas', 0)[cite: 2]
    pallets_p = st.session_state.get('total_pallets_perdidos', 0)[cite: 2]

    col1.metric("Conciliación (%)", f"{(iguales/total_lineas)*100:.2f}%")[cite: 2]
    col2.metric("Total Fusion", f"{comparativa['CANT_FUSION'].sum():,.0f}")[cite: 2]
    col3.metric("Total Infolog", f"{comparativa['CANT_INFOLOG'].sum():,.0f}")[cite: 2]
    col4.metric("Dif. Neta", f"{comparativa['Diferencia'].sum():,.0f}")[cite: 2]
    
    col5.metric(
        label="📦 Pallets Perdidos (Cajas / Plts)", 
        value=f"{cajas_p:,.0f} / {pallets_p}", 
        delta="Alerta" if pallets_p > 0 else "Limpio",[cite: 2]
        delta_color="inverse" if pallets_p > 0 else "normal"[cite: 2]
    )

    tab1, tab2, tab3 = st.tabs(["📊 Análisis General y Diferencias", "🔍 Auditoría de Estatus y Fechas", "🚨 Detalle Pallets Perdidos"])[cite: 2]

    with tab1:
        st.subheader("Distribución de Diferencias")[cite: 2]
        fig = px.pie(comparativa, names='Tipo Error', color='Tipo Error',[cite: 2]
                     color_discrete_map={'OK':'#2ca02c', 'Falta en Infolog':'#ff7f0e', 'Falta en Fusion':'#d62728', 'Diferencia de Cantidad':'#1f77b4'})[cite: 2]
        st.plotly_chart(fig, use_container_width=True)[cite: 2]

        st.subheader("Detalle de Diferencias (Solo errores) con Vencimiento Seguro de Fusion")[cite: 2]
        solo_errores = comparativa[comparativa['Diferencia'] != 0].sort_values(by='Diferencia', ascending=False)[cite: 2]
        
        solo_errores['Vencimiento'] = solo_errores['Vencimiento_str'][cite: 2]
        solo_errores['Caducidad'] = solo_errores['Caducidad_str'][cite: 2]

        columnas_reporte = ['SKU', 'LOTE', 'STATUS', 'CANT_FUSION', 'CANT_INFOLOG', 'Diferencia', 'Tipo Error', 'Vencimiento', 'Caducidad'][cite: 2]
        df_errores_final = solo_errores[columnas_reporte][cite: 2]

        output = BytesIO()[cite: 2]
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:[cite: 2]
            df_errores_final.to_excel(writer, index=False, sheet_name='Errores_Inventario')[cite: 2]
        processed_data = output.getvalue()[cite: 2]

        st.download_button(
            label="📥 Descargar Errores con Vencimientos Fusion (.xlsx)",[cite: 2]
            data=processed_data,[cite: 2]
            file_name="errores_y_vencimientos_fusion.xlsx",[cite: 2]
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"[cite: 2]
        )
        
        def color_negativo_rojo(val):[cite: 2]
            if isinstance(val, (int, float)) and val < 0:[cite: 2]
                return 'color: #d62728; font-weight: bold;'[cite: 2]
            return ''[cite: 2]

        df_con_estilo = df_errores_final.style.format({[cite: 2]
            'CANT_FUSION': '{:,.0f}',[cite: 2]
            'CANT_INFOLOG': '{:,.0f}',[cite: 2]
            'Diferencia': '{:,.0f}'[cite: 2]
        }).map(color_negativo_rojo, subset=['Diferencia'])[cite: 2]
        
        st.dataframe(df_con_estilo, use_container_width=True, hide_index=True)[cite: 2]

    with tab2:
        st.subheader("🔍 Control Cruzado de Fechas (Prioridad: Infolog Vacío por Pallet)")
        st.write("Se exponen los pallets individuales con fecha faltante en Infolog y luego los desvíos operativos mayores a 30 días.")
        
        df_fallas_mostrar = st.session_state.get('df_fallas_fechas_pallet', pd.DataFrame())
        
        if not df_fallas_mostrar.empty:
            st.error(f"⚠️ Se detectaron {len(df_fallas_mostrar)} pallets con novedades o fallas de vencimiento.")[cite: 2]
            
            # EXPORTAR CONTROL DE FECHAS A EXCEL (.xlsx)[cite: 2]
            output_fechas = BytesIO()[cite: 2]
            with pd.ExcelWriter(output_fechas, engine='xlsxwriter') as writer:[cite: 2]
                df_fallas_mostrar.to_excel(writer, index=False, sheet_name='Control_Vencimientos')[cite: 2]
            processed_data_fechas = output_fechas.getvalue()[cite: 2]

            st.download_button(
                label="📥 Descargar Reporte de Vencimientos por Pallet (.xlsx)",
                data=processed_data_fechas,
                file_name="reporte_auditoria_vencimientos.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"[cite: 2]
            )
            
            st.dataframe(df_fallas_mostrar, use_container_width=True, hide_index=True)
        else:
            st.success("🎉 ¡Excelente! Todos los vencimientos están cargados en Infolog y cumplen con los deltas admitidos.")[cite: 2]

        st.subheader("Mapeo General de Estatus")[cite: 2]
        try:[cite: 2]
            if 'df_info' in locals():[cite: 2]
                chequeo_mapeo = df_info[['STATUS_ORIGINAL', 'STATUS']].drop_duplicates().sort_values('STATUS_ORIGINAL')[cite: 2]
                chequeo_mapeo.columns = ['Código en Infolog (Original)', 'Se muestra en Dashboard como:'][cite: 2]
                st.dataframe(chequeo_mapeo, use_container_width=True, hide_index=True)[cite: 2]
            else:[cite: 2]
                st.info("Mostrando estatus de la última carga guardada:")[cite: 2]
                resumen_status = comparativa[['STATUS']].drop_duplicates().sort_values('STATUS')[cite: 2]
                st.dataframe(resumen_status, use_container_width=True, hide_index=True)[cite: 2]
        except Exception as e:[cite: 2]
            st.warning("No se puede mostrar el detalle del mapeo.")[cite: 2]

    with tab3:[cite: 2]
        st.subheader("🚨 Detalle de Pallets Perdidos en Infolog")[cite: 2]
        st.write("Registros que cumplen con estatus **VAC** o ubicaciones que inician con **A-998**.")[cite: 2]
        
        df_p_mostrar = st.session_state.get('df_reporte_perdidos', pd.DataFrame())[cite: 2]
        
        if not df_p_mostrar.empty:[cite: 2]
            output_p = BytesIO()[cite: 2]
            with pd.ExcelWriter(output_p, engine='xlsxwriter') as writer:[cite: 2]
                df_p_mostrar.to_excel(writer, index=False, sheet_name='Pallets_Perdidos')[cite: 2]
            processed_data_p = output_p.getvalue()[cite: 2]

            st.download_button([cite: 2]
                label="📥 Descargar Reporte de Pérdidas en Excel (.xlsx)",[cite: 2]
                data=processed_data_p,[cite: 2]
                file_name="reporte_pallets_perdidos.xlsx",[cite: 2]
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"[cite: 2]
            )
            
            df_p_estilo = df_p_mostrar.style.format({'CAJAS': '{:,.0f}'})[cite: 2]
            st.dataframe(df_p_estilo, use_container_width=True, hide_index=True)[cite: 2]
        else:[cite: 2]
            st.success("🎉 ¡Excelente! No se registran pallets perdidos en la consulta actual.")[cite: 2]