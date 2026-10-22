import streamlit as st
import pandas as pd
import requests
import json
import numpy as np
from datetime import datetime, timedelta, timezone

# =====================================================================
# 1. CONFIGURACIÓN
# =====================================================================
# ⚠️ PEGA AQUÍ TU URL REAL (LA NUEVA):
URL_GOOGLE_SCRIPT = "https://script.google.com/macros/s/AKfycbwf6-meppwDnTNdDDT1hmS06sh_WxRa2iqcmkfP8VkjzMAdBinm3xQf3GZzdjQAxLPF/exec"

st.set_page_config(layout="wide", page_title="Tracking de Pedidos", page_icon="📦")

ESTADOS_CAJAS_LISTAS = ["PICKING COMPLETO", "PREPARADA", "EN CONTROL", "CONTROLADA", "CARGANDO", "TOP SALIDA"]
ESTADOS_PALLETS_LISTOS = ["PALLETS COMPLETOS", "PREPARADA", "EN CONTROL", "CONTROLADA", "CARGANDO", "TOP SALIDA"]

# =====================================================================
# 2. MOTOR DE DATOS
# =====================================================================
@st.cache_data(ttl=30, show_spinner=False)
def obtener_datos_maestros():
    df_full = pd.DataFrame()
    try:
        resp = requests.get(URL_GOOGLE_SCRIPT, timeout=15)
        if resp.status_code == 200 and len(resp.json()) > 0:
            df_full = pd.DataFrame(resp.json())
            
            for col in ['Cajas_Picking', 'Pallets_Completos', 'Average_Picking', 'Orden_Carga']:
                if col in df_full.columns:
                    df_full[col] = pd.to_numeric(df_full[col], errors='coerce').fillna(0).astype(int)
            for col in ['Ruta', 'Id_Entrega', 'Estado', 'Cliente', 'Transporte']:
                if col in df_full.columns:
                    df_full[col] = df_full[col].astype(str).str.strip().str.upper()
            
            if 'Fecha_Cita' in df_full.columns:
                def parse_date(x):
                    try:
                        if pd.isna(x) or str(x).strip() in ["", "SIN FECHA", "NAN"]: return pd.NaT
                        s = str(x).strip()
                        if "/" in s and len(s) <= 12: return pd.to_datetime(f"{s}/{datetime.now().year}", format="%d/%m %H:%M/%Y", errors='coerce')
                        return pd.to_datetime(s, utc=True).tz_convert(None) - pd.Timedelta(hours=3)
                    except: return pd.NaT
                
                df_full['dt_real'] = df_full['Fecha_Cita'].apply(parse_date)
                df_full['Fecha_Cita_str'] = df_full['dt_real'].dt.strftime('%d/%m %H:%M').fillna("Sin Fecha")
    except: pass
    return df_full

def safe_time(val, base_dt):
    if pd.isna(val) or str(val).strip() == "": return pd.NaT
    try:
        val_str = str(val).strip()
        if len(val_str) <= 5 and ":" in val_str and pd.notna(base_dt):
            return pd.to_datetime(f"{base_dt.strftime('%Y-%m-%d')} {val_str}", errors='coerce')
        dt = pd.to_datetime(val_str, errors='coerce')
        if pd.notna(dt) and dt.year < 2000 and pd.notna(base_dt): return dt.replace(year=base_dt.year, month=base_dt.month, day=base_dt.day)
        return dt
    except: return pd.NaT

if 'perfil' not in st.session_state: st.session_state.perfil = None

def logout():
    st.session_state.perfil = None
    obtener_datos_maestros.clear()

if st.session_state.perfil is None:
    st.markdown("<h2 style='text-align: center;'>👋 Bienvenido al Sistema WMS</h2>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("🧑‍🔧 Operación (Solo Visualización)", use_container_width=True): st.session_state.perfil = "Operacion"; st.rerun()
    with col2:
        if st.button("👁️ Visualizador (Solo Monitor)", use_container_width=True): st.session_state.perfil = "Visualizador"; st.rerun()
    with col3:
        if st.button("⚙️ Supervisor (Carga de Datos)", use_container_width=True): st.session_state.perfil = "Supervisor"; st.rerun()
    st.stop() 

st.sidebar.markdown(f"**🟢 Conectado como:**<br>{st.session_state.perfil}", unsafe_allow_html=True)
st.sidebar.button("Cerrar Sesión / Cambiar Rol", on_click=logout)

st.markdown("""
    <style>
    .kpi-box { background-color: #1E1E24; color: #FFFFFF; padding: 12px 5px; border-radius: 6px; border-top: 4px solid #E55B3C; text-align: center; box-shadow: 1px 1px 3px rgba(0,0,0,0.5);}
    .kpi-title { font-size: 11px; text-transform: uppercase; opacity: 0.8;}
    .kpi-value { font-size: 20px; font-weight: bold; margin-top: 4px;}
    </style>
""", unsafe_allow_html=True)

st.title("📦 Tablero de Seguimiento y Preparado de Pedidos")

# =====================================================================
# 4. PROCESAMIENTO DE TIEMPOS
# =====================================================================
df_full = obtener_datos_maestros()
if not df_full.empty and 'Ingreso_Real' in df_full.columns:
    df_full['dt_Ingreso'] = df_full.apply(lambda r: safe_time(r.get('Ingreso_Real'), r.get('dt_real')), axis=1)
    df_full['dt_Egreso'] = df_full.apply(lambda r: safe_time(r.get('Egreso_Real'), r.get('dt_real')), axis=1)
    
    df_full['Estadia_Hs'] = (df_full['dt_Egreso'] - df_full['dt_Ingreso']).dt.total_seconds() / 3600
    df_full['Estadia_Hs'] = df_full['Estadia_Hs'].apply(lambda x: x if x > 0 else np.nan)
    
    df_full['Inicio_Carga'] = df_full[['dt_real', 'dt_Ingreso']].max(axis=1)
    df_full['Tiempo_Carga_Hs'] = (df_full['dt_Egreso'] - df_full['Inicio_Carga']).dt.total_seconds() / 3600
    df_full['Tiempo_Carga_Hs'] = df_full['Tiempo_Carga_Hs'].apply(lambda x: x if x > 0 else np.nan)
    
    df_full['Ingreso'] = df_full['dt_Ingreso'].dt.strftime('%H:%M').fillna('-')
    df_full['Egreso'] = df_full['dt_Egreso'].dt.strftime('%H:%M').fillna('-')
    df_full['Estadia (Hs)'] = df_full['Estadia_Hs'].apply(lambda x: f"{x:.1f}" if pd.notna(x) else "-")
else:
    df_full['Ingreso'], df_full['Egreso'], df_full['Estadia (Hs)'], df_full['Tiempo_Carga_Hs'], df_full['Estadia_Hs'] = '-', '-', '-', np.nan, np.nan

tab_operarios, tab_monitor, tab_resumen = st.tabs(["📲 Vista Operativa", "📱 Monitor de Cargas", "📊 Resumen Ejecutivo"])

with tab_operarios:
    st.subheader("Tablero de Estados de Armado (Lectura Automática)")
    
    if df_full.empty or 'Estado' not in df_full.columns: st.info("Aguardando datos de la base...")
    else:
        df_activa = df_full[~df_full['Estado'].str.contains('DESPACHAD', na=False, case=False)].copy()
        
        if df_activa.empty: st.success("🎉 Todas las órdenes han sido despachadas.")
        else:
            cajas_listas = df_activa[df_activa['Estado'].isin(ESTADOS_CAJAS_LISTAS)]['Cajas_Picking'].sum()
            df_ptes = df_activa[~df_activa['Estado'].isin(ESTADOS_CAJAS_LISTAS)].copy()
            df_ptes['Prod_Hr'] = np.where(df_ptes['Average_Picking'] > 0, (df_ptes['Average_Picking'] / 10.0) * 124.0, 124.0)
            horas_dec = np.where(df_ptes['Cajas_Picking'] > 0, df_ptes['Cajas_Picking'] / df_ptes['Prod_Hr'], 0).sum()
            
            k1, k2, k3, k4, k5, k6, k7 = st.columns(7)
            k1.markdown(f"<div class='kpi-box'><div class='kpi-title'>Total Rutas</div><div class='kpi-value'>{df_activa['Ruta'].nunique()}</div></div>", unsafe_allow_html=True)
            k2.markdown(f"<div class='kpi-box'><div class='kpi-title'>Órdenes Activas</div><div class='kpi-value'>{len(df_activa)}</div></div>", unsafe_allow_html=True)
            k3.markdown(f"<div class='kpi-box'><div class='kpi-title'>Pallets Ptes</div><div class='kpi-value'>{df_activa['Pallets_Completos'].sum() - df_activa[df_activa['Estado'].isin(ESTADOS_PALLETS_LISTOS)]['Pallets_Completos'].sum()}</div></div>", unsafe_allow_html=True)
            k4.markdown(f"<div class='kpi-box'><div class='kpi-title'>Cajas Ptes</div><div class='kpi-value'>{df_activa['Cajas_Picking'].sum() - cajas_listas}</div></div>", unsafe_allow_html=True)
            k5.markdown(f"<div class='kpi-box'><div class='kpi-title'>Horas Pick</div><div class='kpi-value'>{f'{int(horas_dec * 60) // 60:02d}:{int(horas_dec * 60) % 60:02d}'}</div></div>", unsafe_allow_html=True)
            k6.markdown(f"<div class='kpi-box'><div class='kpi-title'>Cajas Pista</div><div class='kpi-value'>{df_activa[df_activa['Estado'].isin(['LANZADA', 'EN PREPARACIÓN'])]['Cajas_Picking'].sum()}</div></div>", unsafe_allow_html=True)
            k7.markdown(f"<div class='kpi-box'><div class='kpi-title'>Top Salida</div><div class='kpi-value'>{len(df_activa[df_activa['Estado'] == 'TOP SALIDA'])}</div></div>", unsafe_allow_html=True)
            
            st.write("---")
            col_b1, col_b2, col_b3 = st.columns([1, 2, 1])
            with col_b2:
                # 🚀 ESTE BOTÓN LE AVISA A GOOGLE QUE EXPORTE LOS DATOS ANTES DE ACTUALIZAR LA PANTALLA
                if st.button("🔄 Sincronizar Horarios desde Embarques", use_container_width=True):
                    with st.spinner("Importando horarios desde el Excel de embarques a la base maestra..."):
                        requests.post(URL_GOOGLE_SCRIPT, data=json.dumps({"accion": "SINCRONIZAR_TIEMPOS"}))
                    obtener_datos_maestros.clear()
                    st.rerun()
            st.write("")

            cols_to_sort = [c for c in ['dt_real', 'Ruta', 'Orden_Carga'] if c in df_activa.columns]
            if cols_to_sort: df_activa = df_activa.sort_values(by=cols_to_sort)
            if 'Fecha_Cita_str' in df_activa.columns: df_activa['Fecha_Cita'] = df_activa['Fecha_Cita_str']
            
            columnas_ver = ['Fecha_Cita', 'Ruta', 'Orden_Carga', 'Id_Entrega', 'Estado', 'Ingreso', 'Egreso', 'Estadia (Hs)', 'Cliente', 'Transporte', 'Cajas_Picking', 'Pallets_Completos', 'Average_Picking']
            df_mostrar = df_activa[[c for c in columnas_ver if c in df_activa.columns]].copy()
            st.dataframe(df_mostrar, use_container_width=True, hide_index=True)

with tab_monitor:
    st.subheader("🎯 Monitor por Horario de Cita")
    st.info("Pestaña activa en monitoreo de 3hs...")

with tab_resumen:
    st.markdown("<h2 style='text-align: left;'>📊 Resumen Ejecutivo y Tiempos</h2>", unsafe_allow_html=True)
    if not df_full.empty and 'dt_real' in df_full.columns and 'Estado' in df_full.columns:
        hoy = datetime.now(timezone(timedelta(hours=-3))).date()
        df_hoy = df_full[df_full['dt_real'].dt.date == hoy].copy()
        
        c1, c2, c3 = st.columns(3)
        if not df_hoy.empty:
            c1.metric("Cajas Pickeadas (Hoy)", f"{df_hoy[df_hoy['Estado'].isin(ESTADOS_CAJAS_LISTAS)]['Cajas_Picking'].sum()} / {df_hoy['Cajas_Picking'].sum()}")
            c3.metric("Rutas Despachadas (Hoy)", f"{df_hoy[df_hoy['Estado'].str.contains('DESPACHAD', na=False, case=False)]['Ruta'].nunique()} / {df_hoy['Ruta'].nunique()}")
            
        st.write("---")
        periodos = [{"nombre": "Ayer", "filtro": lambda d: d == (hoy - timedelta(days=1))}, {"nombre": "Hoy", "filtro": lambda d: d == hoy}]
        datos_tabla = []
        for p in periodos:
            df_p = df_full[df_full['dt_real'].apply(lambda x: p["filtro"](x.date()) if pd.notna(x) else False)]
            rut_p = df_p['Ruta'].nunique()
            caj_p = df_p['Cajas_Picking'].sum()
            t_estadia = df_p['Estadia_Hs'].mean() if 'Estadia_Hs' in df_p.columns else np.nan
            t_carga = df_p['Tiempo_Carga_Hs'].mean() if 'Tiempo_Carga_Hs' in df_p.columns else np.nan
            datos_tabla.append({"Período": p["nombre"], "Rutas Plan": rut_p, "Rutas Ok": df_p[df_p['Estado'].str.contains('DESPACHAD', na=False, case=False)]['Ruta'].nunique(), "Cajas Plan": int(caj_p), "Cajas Ok": int(df_p[df_p['Estado'].isin(ESTADOS_CAJAS_LISTAS)]['Cajas_Picking'].sum()), "Estadía Prom.": f"{t_estadia:.1f} hs" if pd.notna(t_estadia) else "-", "Carga Real Prom.": f"{t_carga:.1f} hs" if pd.notna(t_carga) else "-"})
            
        st.dataframe(pd.DataFrame(datos_tabla), use_container_width=True, hide_index=True)
    else: st.info("Recolectando datos históricos...")
