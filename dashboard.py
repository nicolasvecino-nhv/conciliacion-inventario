import streamlit as st
import pandas as pd
import requests
import json
import numpy as np
import plotly.graph_objects as go
import urllib.parse
from datetime import datetime, timedelta, timezone

# =====================================================================
# 1. CONFIGURACIÓN
# =====================================================================
# ⚠️ PEGA AQUÍ TU URL REAL DE GOOGLE APPS SCRIPT (LA NUEVA):
URL_GOOGLE_SCRIPT = "https://script.google.com/macros/s/AKfycbylHM876ujBH7BeL-DqhJasqKdZ__f4Ua-v1-wrMNJjjbsU9vskhTiyTj_q1iXIVrqU/exec"

st.set_page_config(layout="wide", page_title="Tracking de Pedidos", page_icon="📦")

ESTADOS_CAJAS_LISTAS = ["PICKING COMPLETO", "PREPARADA", "EN CONTROL", "CONTROLADA", "CARGANDO", "TOP SALIDA", "DESPACHADA", "DESPACHADO"]
ESTADOS_PALLETS_LISTOS = ["PALLETS COMPLETOS", "PREPARADA", "EN CONTROL", "CONTROLADA", "CARGANDO", "TOP SALIDA", "DESPACHADA", "DESPACHADO"]
ESTADOS_LISTA = ["PENDIENTE", "CARENCIA", "LANZADA", "EN PREPARACIÓN", "PICKING COMPLETO", "PALLETS COMPLETOS", "PREPARADA", "EN CONTROL", "CONTROLADA", "CARGANDO", "TOP SALIDA", "DESPACHADA"]
ESTADO_PESO = {estado: i+1 for i, estado in enumerate(ESTADOS_LISTA)}

# =====================================================================
# 2. MOTOR DE DATOS
# =====================================================================
@st.cache_data(ttl=15, show_spinner=False)
def obtener_datos():
    try:
        resp = requests.get(URL_GOOGLE_SCRIPT, timeout=15)
        if resp.status_code == 200 and len(resp.json()) > 0:
            df = pd.DataFrame(resp.json())
            for col in ['Cajas_Picking', 'Pallets_Completos', 'Average_Picking', 'Orden_Carga']:
                if col in df.columns: df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).astype(int)
            for col in ['Ruta', 'Id_Entrega', 'Estado', 'Cliente', 'Transporte']:
                if col in df.columns: df[col] = df[col].astype(str).str.strip().str.upper()
            return df
    except: pass
    return pd.DataFrame()

@st.cache_data(ttl=30, show_spinner=False)
def obtener_tiempos_despachos():
    try:
        meses = {1:"Enero", 2:"Febrero", 3:"Marzo", 4:"Abril", 5:"Mayo", 6:"Junio", 7:"Julio", 8:"Agosto", 9:"Septiembre", 10:"Octubre", 11:"Noviembre", 12:"Diciembre"}
        mes_actual = meses[datetime.now(timezone(timedelta(hours=-3))).month]
        sheet_id = "1V8lkm7RmxJMqzb4pQMHrxQX5bSW2K8tF_bO7A8cJpHM"
        
        # ⚠️ CORRECCIÓN AQUÍ: Ahora busca "Despacho Mes" (Ej: "Despacho Octubre")
        url_csv = f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv&sheet={urllib.parse.quote(f'Despacho {mes_actual}')}"
        
        df_t = pd.read_csv(url_csv, dtype=str) 
        if len(df_t.columns) >= 13:
            df_t = df_t.iloc[:, [0, 11, 12]].copy()
            df_t.columns = ['Ruta', 'Ingreso_Str', 'Egreso_Str']
            df_t = df_t.dropna(subset=['Ruta'])
            df_t['Ruta'] = df_t['Ruta'].astype(str).str.strip().str.replace('.0', '', regex=False).str.upper()
            return df_t
    except: pass
    return pd.DataFrame()

def unificar_fechas(fecha_val):
    try:
        if pd.isna(fecha_val) or str(fecha_val).strip() in ["", "SIN FECHA", "NAN", "NaT"]: return pd.NaT
        s = str(fecha_val).strip()
        if "/" in s and len(s) <= 12: return pd.to_datetime(f"{s}/{datetime.now().year}", format="%d/%m %H:%M/%Y", errors='coerce')
        return pd.to_datetime(s, utc=True).tz_convert(None) - pd.Timedelta(hours=3)
    except: return pd.NaT

def safe_time(val, base_dt):
    if pd.isna(val) or str(val).strip() == "": return pd.NaT
    try:
        val_str = str(val).strip()
        if len(val_str) <= 5 and ":" in val_str and pd.notna(base_dt): return pd.to_datetime(f"{base_dt.strftime('%Y-%m-%d')} {val_str}", errors='coerce')
        dt = pd.to_datetime(val_str, errors='coerce')
        if pd.notna(dt) and dt.year < 2000 and pd.notna(base_dt): return dt.replace(year=base_dt.year, month=base_dt.month, day=base_dt.day)
        return dt
    except: return pd.NaT

def get_current_shift_info(now):
    hour = now.hour
    if 6 <= hour < 14: sn, et, n1, n2 = "Turno Mañana (06-14)", now.replace(hour=14, minute=0, second=0, microsecond=0), "Turno Tarde (14-22)", "Turno Noche (22-06)"
    elif 14 <= hour < 22: sn, et, n1, n2 = "Turno Tarde (14-22)", now.replace(hour=22, minute=0, second=0, microsecond=0), "Turno Noche (22-06)", "Turno Mañana (06-14)"
    else:
        sn, n1, n2 = "Turno Noche (22-06)", "Turno Mañana (06-14)", "Turno Tarde (14-22)"
        et = (now + timedelta(days=1)).replace(hour=6, minute=0, second=0, microsecond=0) if hour >= 22 else now.replace(hour=6, minute=0, second=0, microsecond=0)
    eff = max(0, (et - now).total_seconds() / 3600.0 * 0.75)
    return [{"name": sn+" (ACTUAL)", "eff": eff}, {"name": n1, "eff": 6.0}, {"name": n2, "eff": 6.0}]

if 'perfil' not in st.session_state: st.session_state.perfil = None
def logout(): st.session_state.perfil = None; obtener_datos.clear(); obtener_tiempos_despachos.clear()

if st.session_state.perfil is None:
    st.markdown("<h2 style='text-align: center;'>👋 Bienvenido al WMS</h2>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    with c1: 
        if st.button("🧑‍🔧 Operación (Solo Lectura)", use_container_width=True): st.session_state.perfil = "Operacion"; st.rerun()
    with c2: 
        if st.button("👁️ Visualizador", use_container_width=True): st.session_state.perfil = "Visualizador"; st.rerun()
    with c3: 
        if st.button("⚙️ Supervisor", use_container_width=True): st.session_state.perfil = "Supervisor"; st.rerun()
    st.stop()

st.sidebar.markdown(f"**🟢 Conectado:** {st.session_state.perfil}")
st.sidebar.button("Cerrar Sesión", on_click=logout)

st.markdown("""<style>.kpi-box { background-color: #1E1E24; color: white; padding: 12px 5px; border-radius: 6px; border-top: 4px solid #E55B3C; text-align: center; box-shadow: 1px 1px 3px rgba(0,0,0,0.5);} .kpi-title { font-size: 11px; text-transform: uppercase; opacity: 0.8;} .kpi-value { font-size: 20px; font-weight: bold; margin-top: 4px;} .monitor-card { padding: 15px; border-radius: 10px; margin-bottom: 15px; color: white; border-left: 8px solid; } .card-red { background-color: #b71c1c; border-color: #ff5252; } .card-yellow { background-color: #f57f17; border-color: #ffeb3b; } .card-green { background-color: #2e7d32; border-color: #69f0ae; }</style>""", unsafe_allow_html=True)

st.title("📦 Tablero de Seguimiento y Preparado (Automático)")

# =====================================================================
# PROCESAMIENTO CRUCE DE TIEMPOS
# =====================================================================
df_full = obtener_datos()
if not df_full.empty:
    if 'Fecha_Cita' in df_full.columns:
        df_full['dt_real'] = df_full['Fecha_Cita'].apply(unificar_fechas)
        df_full['Fecha_Cita_str'] = df_full['dt_real'].dt.strftime('%d/%m %H:%M').fillna("Sin Fecha")
    
    if 'Ingreso_Real' not in df_full.columns: df_full['Ingreso_Real'] = np.nan
    if 'Egreso_Real' not in df_full.columns: df_full['Egreso_Real'] = np.nan
    
    # ⚠️ CRUCE AL VUELO CON GOOGLE SHEETS
    if 'Ruta' in df_full.columns:
        df_tiempos = obtener_tiempos_despachos()
        if not df_tiempos.empty:
            df_full = pd.merge(df_full, df_tiempos, on='Ruta', how='left')
            # Si el script ya guardó en "Ingreso_Real", usamos ese. Si no, usamos el de "Ingreso_Str" que cruzamos en vivo.
            df_full['Ingreso_Final'] = df_full['Ingreso_Str'].fillna(df_full['Ingreso_Real'])
            df_full['Egreso_Final'] = df_full['Egreso_Str'].fillna(df_full['Egreso_Real'])
        else:
            df_full['Ingreso_Final'] = df_full['Ingreso_Real']
            df_full['Egreso_Final'] = df_full['Egreso_Real']
            
        if 'dt_real' in df_full.columns:
            df_full['dt_Ingreso'] = df_full.apply(lambda r: safe_time(r.get('Ingreso_Final'), r.get('dt_real')), axis=1)
            df_full['dt_Egreso'] = df_full.apply(lambda r: safe_time(r.get('Egreso_Final'), r.get('dt_real')), axis=1)
            
            df_full['Estadia_Hs'] = (df_full['dt_Egreso'] - df_full['dt_Ingreso']).dt.total_seconds() / 3600
            df_full['Inicio_Carga'] = df_full[['dt_real', 'dt_Ingreso']].max(axis=1)
            df_full['Tiempo_Carga_Hs'] = (df_full['dt_Egreso'] - df_full['Inicio_Carga']).dt.total_seconds() / 3600
            
            df_full['Ingreso'] = df_full['dt_Ingreso'].dt.strftime('%H:%M').fillna('-')
            df_full['Egreso'] = df_full['dt_Egreso'].dt.strftime('%H:%M').fillna('-')
            df_full['Estadia (Hs)'] = df_full['Estadia_Hs'].apply(lambda x: f"{x:.1f}" if pd.notna(x) and x>0 else "-")
else:
    st.info("Sin datos. Pega la URL de Apps Script en la línea 14.")

tab_op, tab_mon, tab_sup, tab_res = st.tabs(["📲 Vista Operativa", "📱 Monitor", "⚙️ Supervisor", "📊 Resumen Ejecutivo (Flujo Continuo)"])

with tab_op:
    if not df_full.empty and 'Estado' in df_full.columns:
        df_activa = df_full[~df_full['Estado'].str.contains('DESPACHAD', na=False, case=False)].copy()
        
        if df_activa.empty: st.success("🎉 Todas las órdenes activas han sido despachadas.")
        else:
            cajas_listas = df_activa[df_activa['Estado'].isin(ESTADOS_CAJAS_LISTAS)]['Cajas_Picking'].sum()
            df_ptes = df_activa[~df_activa['Estado'].isin(ESTADOS_CAJAS_LISTAS)].copy()
            df_ptes['Prod_Hr'] = np.where(df_ptes['Average_Picking'] > 0, (df_ptes['Average_Picking'] / 10.0) * 124.0, 124.0)
            h_dec = np.where(df_ptes['Cajas_Picking'] > 0, df_ptes['Cajas_Picking'] / df_ptes['Prod_Hr'], 0).sum()
            
            k1, k2, k3, k4, k5, k6, k7 = st.columns(7)
            k1.markdown(f"<div class='kpi-box'><div class='kpi-title'>Total Rutas</div><div class='kpi-value'>{df_activa['Ruta'].nunique()}</div></div>", unsafe_allow_html=True)
            k2.markdown(f"<div class='kpi-box'><div class='kpi-title'>Órdenes</div><div class='kpi-value'>{len(df_activa)}</div></div>", unsafe_allow_html=True)
            k3.markdown(f"<div class='kpi-box'><div class='kpi-title'>Pallets Ptes</div><div class='kpi-value'>{df_activa['Pallets_Completos'].sum() - df_activa[df_activa['Estado'].isin(ESTADOS_PALLETS_LISTOS)]['Pallets_Completos'].sum()}</div></div>", unsafe_allow_html=True)
            k4.markdown(f"<div class='kpi-box'><div class='kpi-title'>Cajas Ptes</div><div class='kpi-value'>{df_activa['Cajas_Picking'].sum() - cajas_listas}</div></div>", unsafe_allow_html=True)
            k5.markdown(f"<div class='kpi-box'><div class='kpi-title'>Horas Pick</div><div class='kpi-value'>{f'{int(h_dec * 60) // 60:02d}:{int(h_dec * 60) % 60:02d}'}</div></div>", unsafe_allow_html=True)
            k6.markdown(f"<div class='kpi-box'><div class='kpi-title'>Cajas Pista</div><div class='kpi-value'>{df_activa[df_activa['Estado'].isin(['LANZADA', 'EN PREPARACIÓN'])]['Cajas_Picking'].sum()}</div></div>", unsafe_allow_html=True)
            k7.markdown(f"<div class='kpi-box'><div class='kpi-title'>Top Salida</div><div class='kpi-value'>{len(df_activa[df_activa['Estado'] == 'TOP SALIDA'])}</div></div>", unsafe_allow_html=True)
            
            st.write("---")
            col_b1, col_b2, col_b3 = st.columns([1, 2, 1])
            with col_b2:
                if st.button("🔄 Sincronizar Horarios desde GSheets", use_container_width=True):
                    with st.spinner("Solicitando a Google que busque los horarios..."):
                        resp = requests.post(URL_GOOGLE_SCRIPT, data=json.dumps({"accion": "SINCRONIZAR_TIEMPOS"}))
                        try:
                            res_json = resp.json()
                            if "Error" in res_json.get("status", ""):
                                st.error(f"Google devolvió un error: {res_json.get('detalle', 'Revisa el nombre de la solapa o los permisos.')}")
                            else:
                                obtener_datos.clear()
                                obtener_tiempos_despachos.clear()
                                st.success("Sincronización finalizada. Recargando...")
                                st.rerun()
                        except: st.error(f"Error de conexión con Apps Script: {resp.text}")
            
            st.write("")
            cols_ver = ['Fecha_Cita_str', 'Ruta', 'Orden_Carga', 'Id_Entrega', 'Estado', 'Ingreso', 'Egreso', 'Estadia (Hs)', 'Cajas_Picking', 'Pallets_Completos']
            df_mostrar = df_activa[[c for c in cols_ver if c in df_activa.columns]].sort_values(by=['Fecha_Cita_str', 'Ruta'])
            st.dataframe(df_mostrar, use_container_width=True, hide_index=True)

with tab_mon:
    st.subheader("🎯 Monitor por Horario de Cita")
    if not df_full.empty and 'Estado' in df_full.columns:
        df_mon = df_full[~df_full['Estado'].str.contains('DESPACHAD', na=False, case=False)].copy()
        if df_mon.empty: st.success("Todo despachado.")
        elif 'dt_real' in df_mon.columns:
            ahora = datetime.now(timezone(timedelta(hours=-3))).replace(tzinfo=None)
            df_mon = df_mon.dropna(subset=['dt_real'])
            df_mon['Fecha_Cita'] = df_mon['dt_real'].dt.strftime('%d/%m %H:%M')
            for f_str, grupo in df_mon.groupby('Fecha_Cita'):
                f_dt = grupo['dt_real'].iloc[0]
                min_dif = (ahora - f_dt).total_seconds() / 60
                p_peso = grupo['Estado'].map(ESTADO_PESO).min() if 'Estado' in grupo.columns else 12
                if min_dif >= 0: c_col, txt = ("card-red", "🚨 Cita cumplida (Faltan controlar)") if p_peso < 8 else (("card-yellow", "🟡 En ventana de 3hs") if min_dif <= 180 else ("card-red", "🚨 Vencieron las 3hs"))
                else: c_col, txt = "card-green", f"🟢 Faltan {int(abs(min_dif))} min."
                st.markdown(f"""<div class="monitor-card {c_col}"><div class="card-title">⏰ Cita: {f_str}</div><div class="card-text">{txt} | Órdenes: {len(grupo)}</div></div>""", unsafe_allow_html=True)

with tab_sup:
    st.info("Sube el Excel de Planificación aquí.")

with tab_res:
    st.markdown("## 📊 Flujo Continuo: Consumo de Cola Pendiente (Burn-up)")
    if not df_full.empty and 'dt_real' in df_full.columns and 'Estado' in df_full.columns:
        hoy_dt = datetime.now(timezone(timedelta(hours=-3))).replace(tzinfo=None)
        shifts = get_current_shift_info(hoy_dt)
        
        c1, c2, c3 = st.columns(3)
        dot_t1 = c1.number_input(f"🧑‍🤝‍🧑 {shifts[0]['name']}", min_value=1, value=5)
        dot_t2 = c2.number_input(f"🧑‍🤝‍🧑 {shifts[1]['name']}", min_value=1, value=5)
        dot_t3 = c3.number_input(f"🧑‍🤝‍🧑 {shifts[2]['name']}", min_value=1, value=5)
        
        df_pendientes = df_full[~df_full['Estado'].str.contains('DESPACHAD', na=False, case=False)].copy()
        if not df_pendientes.empty and 'Average_Picking' in df_pendientes.columns:
            df_pendientes['Prod_Hr'] = np.where(df_pendientes['Average_Picking'] > 0, (df_pendientes['Average_Picking'] / 10.0) * 124.0, 124.0)
            df_pendientes['Horas_Estimadas'] = np.where(df_pendientes['Cajas_Picking'] > 0, df_pendientes['Cajas_Picking'] / df_pendientes['Prod_Hr'], 0)
            tot_ph, tot_cjs = df_pendientes['Horas_Estimadas'].sum(), df_pendientes['Cajas_Picking'].sum()
            avg_cjs_ph = tot_cjs / tot_ph if tot_ph > 0 else 0
        else: tot_ph, tot_cjs, avg_cjs_ph = 0, 0, 0

        w_rem = tot_ph
        y_v, c_hs, c_txt, u_hs, u_txt = [], [], [], [], []
        for s, dot in zip(shifts, [dot_t1, dot_t2, dot_t3]):
            y_v.append(f"<b>{s['name']}</b><br>Disp: {s['eff']:.1f}hs")
            cap = s['eff'] * dot
            cjs_cap = int(cap * avg_cjs_ph)
            c_hs.append(s['eff']); c_txt.append(f"{s['eff']:.1f} hs disp (Cubre {cjs_cap} cjs)")
            
            if w_rem >= cap: u_hs.append(s['eff']); u_txt.append(f"{s['eff']:.1f} hs uso ➡️ Sigue"); w_rem -= cap
            elif w_rem > 0: d_i = w_rem / dot; u_hs.append(d_i); u_txt.append(f"{d_i:.1f} hs uso ({int(w_rem*avg_cjs_ph)} cjs) 🏁 FIN"); w_rem = 0
            else: u_hs.append(0); u_txt.append("Libre")

        fig = go.Figure()
        fig.add_trace(go.Bar(y=y_v[::-1], x=c_hs[::-1], name='Capacidad Instalada (Disp.)', orientation='h', marker=dict(color='#2e7d32'), text=c_txt[::-1], textposition='inside'))
        fig.add_trace(go.Bar(y=y_v[::-1], x=u_hs[::-1], name='Cola Pendiente (Uso)', orientation='h', marker=dict(color='#f57f17'), text=u_txt[::-1], textposition='inside'))
        fig.update_layout(barmode='group', bargap=0.15, height=450, margin=dict(l=0, r=0, t=30, b=0), plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', font=dict(color='white'), legend=dict(orientation="h", yanchor="bottom"))
        st.plotly_chart(fig, use_container_width=True)
