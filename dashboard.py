import streamlit as st
import pandas as pd
import requests
import json
import numpy as np
from datetime import datetime, timedelta, timezone

# =====================================================================
# CONFIGURACIÓN DE CONEXIÓN
# =====================================================================
# ⚠️ PEGA AQUÍ TU URL REAL DE GOOGLE APPS SCRIPT:
URL_GOOGLE_SCRIPT = "TU_NUEVA_URL_AQUI"

st.set_page_config(layout="wide", page_title="Tracking de Pedidos", page_icon="📦")

# =====================================================================
# SISTEMA DE LOGIN Y PERFILES
# =====================================================================
if 'demoras_pendientes' not in st.session_state:
    st.session_state.demoras_pendientes = {}

if 'perfil' not in st.session_state:
    st.session_state.perfil = None

if st.session_state.perfil is None:
    st.markdown("<h2 style='text-align: center;'>👋 Bienvenido al Sistema WMS</h2>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; margin-bottom: 30px;'>Por favor, selecciona tu perfil de ingreso:</p>", unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("🧑‍🔧 Operación (Armado en Pista)", use_container_width=True):
            st.session_state.perfil = "Operacion"
            st.rerun()
    with col2:
        if st.button("👁️ Visualizador (Solo Monitor)", use_container_width=True):
            st.session_state.perfil = "Visualizador"
            st.rerun()
    with col3:
        if st.button("⚙️ Supervisor (Carga de Datos)", use_container_width=True):
            st.session_state.perfil = "Supervisor"
            st.rerun()
    st.stop() 

st.sidebar.markdown(f"**🟢 Conectado como:**<br>{st.session_state.perfil}", unsafe_allow_html=True)
if st.sidebar.button("Cerrar Sesión / Cambiar Rol"):
    st.session_state.perfil = None
    st.rerun()

# =====================================================================
# CSS PARA KPIs Y TARJETAS (ADAPTABLE A MODO CLARO/OSCURO)
# =====================================================================
st.markdown("""
    <style>
    /* Usamos variables nativas de Streamlit para que se adapte al tema del usuario */
    .kpi-box { background-color: var(--secondary-background-color); color: var(--text-color); padding: 12px 5px; border-radius: 6px; border-top: 4px solid #E55B3C; text-align: center; box-shadow: 1px 1px 3px rgba(0,0,0,0.2);}
    .kpi-title { font-size: 11px; text-transform: uppercase; letter-spacing: 0.5px; opacity: 0.8;}
    .kpi-value { font-size: 20px; font-weight: bold; margin-top: 4px;}
    
    .monitor-card { padding: 15px; border-radius: 10px; margin-bottom: 15px; color: white; font-family: sans-serif; box-shadow: 2px 2px 5px rgba(0,0,0,0.3); }
    .card-red { background-color: #b71c1c; border-left: 8px solid #ff5252; }
    .card-yellow { background-color: #f57f17; border-left: 8px solid #ffeb3b; }
    .card-green { background-color: #2e7d32; border-left: 8px solid #69f0ae; }
    .card-title { font-size: 22px; font-weight: bold; margin-bottom: 5px; border-bottom: 1px solid rgba(255,255,255,0.2); padding-bottom: 5px;}
    .card-foco { font-size: 18px; font-weight: bold; margin-top: 10px; text-transform: uppercase; }
    .card-text { font-size: 14px; margin: 2px 0; }
    </style>
""", unsafe_allow_html=True)

st.title("📦 Tablero de Seguimiento y Preparado de Pedidos")

ESTADOS_LISTA = ["PENDIENTE", "CARENCIA", "LANZADA", "EN PREPARACIÓN", "PREPARADA", "EN CONTROL", "CONTROLADA", "CARGANDO", "TOP SALIDA", "DESPACHADA"]
ESTADOS_PREPARADOS = ["PREPARADA", "EN CONTROL", "CONTROLADA", "CARGANDO", "TOP SALIDA"]
ESTADO_PESO = {estado: i+1 for i, estado in enumerate(ESTADOS_LISTA)}

def unificar_fechas(fecha_val):
    try:
        if pd.isna(fecha_val) or fecha_val == "Sin Fecha": return pd.NaT
        s = str(fecha_val).strip()
        if "/" in s and len(s) <= 12: 
            año = datetime.now().year
            return pd.to_datetime(f"{s}/{año}", format="%d/%m %H:%M/%Y")
        else:
            dt = pd.to_datetime(s, utc=True)
            return dt.tz_convert(None) - pd.Timedelta(hours=3)
    except:
        return pd.NaT

tab_operarios, tab_monitor, tab_supervisor = st.tabs(["📲 Vista Operativa", "📱 Monitor de Cargas", "⚙️ Carga de Reportes"])

# ---------------------------------------------------------------------
# PESTAÑA 1: VISTA OPERATIVA (PISTA)
# ---------------------------------------------------------------------
with tab_operarios:
    st.subheader("Tablero de Estados de Armado")
    
    if st.session_state.demoras_pendientes:
        st.error("🚨 ATENCIÓN: Tienes camiones marcados como DESPACHADA que superaron las 3 horas desde la cita. Es obligatorio ingresar un motivo para liberarlos.")
        motivos = {}
        for id_ent, datos in st.session_state.demoras_pendientes.items():
            motivos[id_ent] = st.text_input(f"⚠️ Motivo para Orden {id_ent} (Demora: {datos['horas']:.1f} hs):", key=f"motivo_{id_ent}")
            
        if st.button("Confirmar Despachos Retrasados", type="primary"):
            with st.spinner("Guardando justificaciones..."):
                for id_ent, motivo_texto in motivos.items():
                    payload = {
                        "accion": "ACTUALIZAR_ESTADO", "Id_Entrega": id_ent,
                        "Estado": "DESPACHADA", "Motivo_Demora": motivo_texto if motivo_texto else "Sin justificación ingresada"
                    }
                    requests.post(URL_GOOGLE_SCRIPT, data=json.dumps(payload))
                st.session_state.demoras_pendientes = {} 
                st.success("✅ Justificaciones guardadas. Despachos confirmados.")
                st.rerun()
        st.stop() 

    if URL_GOOGLE_SCRIPT == "TU_NUEVA_URL_AQUI":
        st.info("👆 Pega tu enlace de Google Script en la línea 12.")
    else:
        try:
            respuesta = requests.get(URL_GOOGLE_SCRIPT)
            datos_json = respuesta.json()
            
            if respuesta.status_code == 200 and len(datos_json) > 0:
                df_bd = pd.DataFrame(datos_json)
                
                if 'Cajas_Picking' in df_bd.columns: df_bd['Cajas_Picking'] = pd.to_numeric(df_bd['Cajas_Picking'], errors='coerce').fillna(0).astype(int)
                if 'Pallets_Completos' in df_bd.columns: df_bd['Pallets_Completos'] = pd.to_numeric(df_bd['Pallets_Completos'], errors='coerce').fillna(0).astype(int)
                if 'Average_Picking' in df_bd.columns: df_bd['Average_Picking'] = pd.to_numeric(df_bd['Average_Picking'], errors='coerce').fillna(0).astype(int)
                if 'Orden_Carga' in df_bd.columns: df_bd['Orden_Carga'] = pd.to_numeric(df_bd['Orden_Carga'], errors='coerce').fillna(0).astype(int)
                
                df_bd = df_bd[df_bd['Estado'] != "DESPACHADA"]
                
                if df_bd.empty:
                    st.success("🎉 Todas las órdenes activas han sido despachadas.")
                else:
                    # CÁLCULOS PARA LOS KPIs
                    total_pedidos = len(df_bd)
                    total_rutas = df_bd['Ruta'].nunique()
                    df_ya_preparadas = df_bd[df_bd['Estado'].isin(ESTADOS_PREPARADOS)]
                    
                    df_pendientes = df_bd[~df_bd['Estado'].isin(ESTADOS_PREPARADOS)].copy()
                    
                    cajas_pendientes = df_bd['Cajas_Picking'].sum() - df_ya_preparadas['Cajas_Picking'].sum()
                    pallets_pendientes = df_bd['Pallets_Completos'].sum() - df_ya_preparadas['Pallets_Completos'].sum()
                    cajas_lanzadas = df_bd[df_bd['Estado'] == 'LANZADA']['Cajas_Picking'].sum()
                    pedidos_listos = len(df_bd[df_bd['Estado'] == 'TOP SALIDA'])
                    
                    # --- NUEVO CÁLCULO DE HORAS DE PICKING ---
                    df_pendientes['Productividad_Hr'] = np.where(df_pendientes['Average_Picking'] > 0, (df_pendientes['Average_Picking'] / 10.0) * 124.0, 124.0)
                    df_pendientes['Horas_Estimadas'] = np.where(df_pendientes['Cajas_Picking'] > 0, df_pendientes['Cajas_Picking'] / df_pendientes['Productividad_Hr'], 0)
                    horas_picking_decimal = df_pendientes['Horas_Estimadas'].sum()
                    
                    # Convertimos de decimal a formato HH:MM
                    minutos_totales = int(horas_picking_decimal * 60)
                    horas = minutos_totales // 60
                    minutos = minutos_totales % 60
                    horas_picking_str = f"{horas:02d}:{minutos:02d}"
                    # -----------------------------------------
                    
                    k1, k2, k3, k4, k5, k6, k7 = st.columns(7)
                    with k1: st.markdown(f"<div class='kpi-box'><div class='kpi-title'>Total Rutas</div><div class='kpi-value'>{total_rutas}</div></div>", unsafe_allow_html=True)
                    with k2: st.markdown(f"<div class='kpi-box'><div class='kpi-title'>Órdenes Activas</div><div class='kpi-value'>{total_pedidos}</div></div>", unsafe_allow_html=True)
                    with k3: st.markdown(f"<div class='kpi-box'><div class='kpi-title'>Pallets Ptes</div><div class='kpi-value'>{pallets_pendientes}</div></div>", unsafe_allow_html=True)
                    with k4: st.markdown(f"<div class='kpi-box'><div class='kpi-title'>Cajas Ptes</div><div class='kpi-value'>{cajas_pendientes}</div></div>", unsafe_allow_html=True)
                    with k5: st.markdown(f"<div class='kpi-box'><div class='kpi-title'>Horas Pick</div><div class='kpi-value'>{horas_picking_str}</div></div>", unsafe_allow_html=True)
                    with k6: st.markdown(f"<div class='kpi-box'><div class='kpi-title'>Cajas Lanzadas</div><div class='kpi-value'>{cajas_lanzadas}</div></div>", unsafe_allow_html=True)
                    with k7: st.markdown(f"<div class='kpi-box'><div class='kpi-title'>Top Salida</div><div class='kpi-value'>{pedidos_listos}</div></div>", unsafe_allow_html=True)
                    
                    st.write("---")
                    
                    if 'Fecha_Cita' in df_bd.columns:
                        df_bd['dt_real'] = df_bd['Fecha_Cita'].apply(unificar_fechas)
                        df_bd = df_bd.sort_values(by=['dt_real', 'Ruta', 'Orden_Carga'])
                        df_bd['Fecha_Cita'] = df_bd['dt_real'].dt.strftime('%d/%m %H:%M').fillna("Sin Fecha")
                    else:
                        df_bd = df_bd.sort_values(by=['Ruta', 'Orden_Carga'])
                        
                    columnas_ver = ['Fecha_Cita', 'Ruta', 'Orden_Carga', 'Id_Entrega', 'Estado', 'Cliente', 'Transporte', 'Cajas_Picking', 'Pallets_Completos', 'Average_Picking', 'dt_real']
                    columnas_ver = [c for c in columnas_ver if c in df_bd.columns]
                    df_mostrar = df_bd[columnas_ver].copy()
                    
                    rutas_unicas = list(df_mostrar['Ruta'].unique())
                    def resaltar_rutas(row):
                        color = "rgba(128, 128, 128, 0.2)" if rutas_unicas.index(row['Ruta']) % 2 == 0 else "transparent"
                        return [f"background-color: {color}"] * len(row)
                    
                    df_estilizado = df_mostrar.style.apply(resaltar_rutas, axis=1)
                    
                    columnas_deshabilitadas = ['Fecha_Cita', 'Ruta', 'Orden_Carga', 'Id_Entrega', 'Cliente', 'Transporte', 'Cajas_Picking', 'Pallets_Completos', 'Average_Picking', 'dt_real']
                    
                    if st.session_state.perfil == "Operacion":
                        df_editado = st.data_editor(
                            df_estilizado,
                            column_config={"Estado": st.column_config.SelectboxColumn("Estado Actual", options=ESTADOS_LISTA, required=True), "dt_real": None}, 
                            disabled=columnas_deshabilitadas,
                            use_container_width=True, hide_index=True
                        )
                        if st.button("💾 Guardar Avance Operativo"):
                            with st.spinner("Verificando Tiempos..."):
                                cambios = df_editado.compare(df_mostrar) 
                                if not cambios.empty:
                                    for index in cambios.index:
                                        nuevo_estado = str(df_editado.loc[index, 'Estado'])
                                        id_entrega = str(df_editado.loc[index, 'Id_Entrega'])
                                        
                                        if nuevo_estado == "DESPACHADA" and 'dt_real' in df_mostrar.columns:
                                            fecha_cita = df_mostrar.loc[index, 'dt_real']
                                            ahora = datetime.now()
                                            diferencia_horas = (ahora - fecha_cita).total_seconds() / 3600
                                            
                                            if diferencia_horas > 3:
                                                st.session_state.demoras_pendientes[id_entrega] = {'horas': diferencia_horas}
                                                continue 
                                                
                                        payload = {"accion": "ACTUALIZAR_ESTADO", "Id_Entrega": id_entrega, "Estado": nuevo_estado}
                                        requests.post(URL_GOOGLE_SCRIPT, data=json.dumps(payload))
                                        
                                    if not st.session_state.demoras_pendientes:
                                        st.success("✅ Estados actualizados.")
                                    st.rerun()
                    else:
                        df_mostrar_vis = df_mostrar.drop(columns=['dt_real']) if 'dt_real' in df_mostrar.columns else df_mostrar
                        df_estilizado_vis = df_mostrar_vis.style.apply(resaltar_rutas, axis=1)
                        st.dataframe(df_estilizado_vis, use_container_width=True, hide_index=True)
                        
        except Exception as e:
            st.error(f"Error conectando a la BD: {e}")

# ---------------------------------------------------------------------
# PESTAÑA 2: MONITOR DE CARGAS
# ---------------------------------------------------------------------
with tab_monitor:
    st.subheader("🎯 Estado General por Horario de Cita")
    if URL_GOOGLE_SCRIPT != "TU_NUEVA_URL_AQUI":
        try:
            resp_mon = requests.get(URL_GOOGLE_SCRIPT)
            datos_mon = resp_mon.json()
            if len(datos_mon) > 0:
                df_mon = pd.DataFrame(datos_mon)
                df_mon = df_mon[df_mon['Estado'] != "DESPACHADA"]
                if 'Fecha_Cita' in df_mon.columns:
                    df_mon['Fecha_Cita_dt'] = df_mon['Fecha_Cita'].apply(unificar_fechas)
                    df_mon = df_mon.dropna(subset=['Fecha_Cita_dt'])
                    df_mon['Fecha_Cita'] = df_mon['Fecha_Cita_dt'].dt.strftime('%d/%m %H:%M')
                
                if df_mon.empty:
                    st.success("Todo despachado. Nada pendiente a monitorear.")
                else:
                    tz_arg = timezone(timedelta(hours=-3))
                    ahora = datetime.now(tz_arg).replace(tzinfo=None)
                    grupos = df_mon.groupby('Fecha_Cita')
                    horarios_ordenados = df_mon[['Fecha_Cita', 'Fecha_Cita_dt']].drop_duplicates().sort_values('Fecha_Cita_dt')
                    
                    for _, row_hora in horarios_ordenados.iterrows():
                        fecha_str, fecha_dt = row_hora['Fecha_Cita'], row_hora['Fecha_Cita_dt']
                        grupo = grupos.get_group(fecha_str)
                        minutos_desde_cita = (ahora - fecha_dt).total_seconds() / 60
                        grupo['Peso_Estado'] = grupo['Estado'].map(ESTADO_PESO)
                        peor_peso = grupo['Peso_Estado'].min()
                        
                        if peor_peso <= 2: foco = "🚀 FOCO: LANZAMIENTO"
                        elif peor_peso <= 4: foco = "📦 FOCO: PREPARACIÓN"
                        elif peor_peso <= 6: foco = "🔎 FOCO: CONTROL"
                        else: foco = "🚛 FOCO: CARGA"
                        
                        if minutos_desde_cita >= 0: 
                            if peor_peso < 7: clase_color, estado_tiempo = "card-red", "🚨 ROJO: Cita cumplida y faltan controlar"
                            elif peor_peso < 9:
                                if minutos_desde_cita <= 180: clase_color, estado_tiempo = "card-yellow", "🟡 AMARILLO: En ventana de 3hs"
                                else: clase_color, estado_tiempo = "card-red", "🚨 ROJO: Vencieron las 3hs"
                            else: clase_color, estado_tiempo = "card-green", "🟢 VERDE: Lista para despachar"
                        else: clase_color, estado_tiempo = "card-green", f"🟢 VERDE: Faltan {int(abs(minutos_desde_cita))} min. para la cita"
                        
                        st.markdown(f"""
                        <div class="monitor-card {clase_color}">
                            <div class="card-title">⏰ Cita: {fecha_str}</div>
                            <div class="card-text">{estado_tiempo}</div>
                            <div class="card-text"><b>{len(grupo)}</b> Órdenes en este bloque.</div>
                            <div class="card-foco">{foco}</div>
                        </div>""", unsafe_allow_html=True)
        except Exception as e: st.error(f"Error cargando monitor: {e}")

# ---------------------------------------------------------------------
# PESTAÑA 3: CARGA SUPERVISOR
# ---------------------------------------------------------------------
with tab_supervisor:
    st.subheader("Subir Planificación del Día")
    
    if st.session_state.perfil != "Supervisor":
        st.warning("⚠️ Solo el perfil 'Supervisor' tiene permisos para cargar nuevas planificaciones.")
    else:
        col1, col2 = st.columns(2)
        with col1: file_plan = st.file_uploader("1. Reporte 'Planificación Dana' (Excel)", type=["xlsx", "xls"])
        with col2: file_maestro = st.file_uploader("2. 'Maestro Materiales' (Excel)", type=["xlsx", "xls"])
        
        if st.button("Procesar y Cargar al Sistema"):
            if file_plan and file_maestro:
                try:
                    df_plan = pd.read_excel(file_plan)
                    
                    df_plan = df_plan.rename(columns={
                        "FechaHoraDespacho": 'Fecha_Cita', 
                        "IdRuta": 'Ruta', 
                        "Número de orden de ventas de origen": 'Orden_Entrega', 
                        "IdEntrega": 'Id_Entrega', 
                        "Nombre de organización": 'Cliente', 
                        "IdTransportista": 'Transporte', 
                        "Artículo": 'Codigo', 
                        "Cantidad solicitada secundaria": 'Cantidad_Cajas',
                        "OrdenCarga": 'Orden_Descarga' 
                    })
                    
                    df_maestro = pd.read_excel(file_maestro).rename(columns={"Artículo - Nombre": 'Codigo', "LPK - Cajas por Pallet": 'LPK'})
                    df_completo = pd.merge(df_plan, df_maestro[['Codigo', 'LPK']], on='Codigo', how='left')
                    df_completo['Cantidad_Cajas'] = pd.to_numeric(df_completo['Cantidad_Cajas'], errors='coerce').fillna(0)
                    df_completo['LPK'] = pd.to_numeric(df_completo['LPK'], errors='coerce').fillna(1) 
                    
                    fechas_excel = pd.to_datetime(df_completo['Fecha_Cita'], errors='coerce')
                    if fechas_excel.dt.tz is not None: fechas_excel = fechas_excel.dt.tz_convert(None)
                    fechas_excel = fechas_excel - pd.Timedelta(hours=3)
                    df_completo['Fecha_Cita'] = fechas_excel.dt.strftime('%d/%m %H:%M').fillna("Sin Fecha")
                    
                    df_completo['Pallets_Completos'] = (df_completo['Cantidad_Cajas'] // df_completo['LPK']).astype(int)
                    df_completo['Cajas_Picking'] = (df_completo['Cantidad_Cajas'] % df_completo['LPK']).astype(int)
                    df_completo['Lineas_Picking'] = np.where(df_completo['Cajas_Picking'] > 0, 1, 0)
                    
                    df_agrupado = df_completo.groupby(['Fecha_Cita', 'Ruta', 'Orden_Entrega', 'Id_Entrega', 'Cliente', 'Transporte']).agg({
                        'Cajas_Picking': 'sum', 
                        'Pallets_Completos': 'sum', 
                        'Lineas_Picking': 'sum',
                        'Orden_Descarga': 'min'
                    }).reset_index()
                    
                    df_agrupado['Average_Picking'] = np.where(df_agrupado['Lineas_Picking'] > 0, np.ceil(df_agrupado['Cajas_Picking'] / df_agrupado['Lineas_Picking']), 0).astype(int)
                    
                    if 'Orden_Descarga' in df_agrupado.columns:
                        df_agrupado['Orden_Carga'] = df_agrupado.groupby('Ruta')['Orden_Descarga'].rank(ascending=False, method='min').fillna(1).astype(int)
                    else:
                        df_agrupado['Orden_Carga'] = 1
                        
                    if URL_GOOGLE_SCRIPT != "TU_NUEVA_URL_AQUI":
                        try:
                            resp = requests.get(URL_GOOGLE_SCRIPT)
                            if resp.status_code == 200 and len(resp.json()) > 0:
                                ids_existentes = pd.DataFrame(resp.json())['Id_Entrega'].astype(str).tolist()
                                df_agrupado = df_agrupado[~df_agrupado['Id_Entrega'].astype(str).isin(ids_existentes)]
                        except: pass 
                                
                    if df_agrupado.empty: st.warning("⚠️ Órdenes ya cargadas. Sin duplicados.")
                    else:
                        df_agrupado = df_agrupado.sort_values(by=['Fecha_Cita', 'Ruta', 'Orden_Carga'])
                        st.success(f"✅ Se cargarán {len(df_agrupado)} órdenes nuevas:")
                        if URL_GOOGLE_SCRIPT == "TU_NUEVA_URL_AQUI": st.warning("⚠️ Falta pegar la URL de Google.")
                        else:
                            with st.spinner("Enviando pedidos..."):
                                for _, row in df_agrupado.iterrows():
                                    payload = {
                                        "accion": "CARGAR_PLAN", "Fecha_Cita": str(row['Fecha_Cita']), "Ruta": str(row['Ruta']), 
                                        "Orden_Entrega": str(row['Orden_Entrega']), "Id_Entrega": str(row['Id_Entrega']), 
                                        "Cliente": str(row['Cliente']), "Transporte": str(row['Transporte']), 
                                        "Cajas_Picking": int(row['Cajas_Picking']), "Pallets_Completos": int(row['Pallets_Completos']), 
                                        "Average_Picking": int(row['Average_Picking']), "Orden_Carga": int(row['Orden_Carga'])
                                    }
                                    requests.post(URL_GOOGLE_SCRIPT, data=json.dumps(payload))
                                st.info("🚀 ¡Datos enviados!")
                except Exception as e: st.error(f"❌ Ocurrió un error leyendo el Excel: {e}")
