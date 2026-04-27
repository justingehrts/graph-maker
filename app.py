import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import base64
import json
from datetime import datetime
import os

# --- 1. FONT CONFIGURATION (Relative Paths for Web) ---
path_reg = "ProximaNova-Regular.ttf"
path_bold = "ProximaNova-Bold.ttf"

def get_base64_font(path):
    try:
        if os.path.exists(path):
            with open(path, "rb") as f:
                return base64.b64encode(f.read()).decode()
        return ""
    except: return ""

reg_b64, bold_b64 = get_base64_font(path_reg), get_base64_font(path_bold)
font_css_base = f"""
@font-face {{ font-family: 'ProximaRegular'; src: url(data:font/truetype;base64,{reg_b64}) format('truetype'); }}
@font-face {{ font-family: 'ProximaBold'; src: url(data:font/truetype;base64,{bold_b64}) format('truetype'); font-weight: bold; }}
"""

st.set_page_config(page_title="Weather Graphic Pro", layout="wide")

# --- 2. SESSION STATE ---
if 'main_df' not in st.session_state:
    st.session_state.main_df = pd.DataFrame({
        "Label": ["Mon", "Tue", "Wed", "Thu", "Fri"], 
        "Value 1": [75.0, 80.0, 50.0, 60.0, 75.0],
        "Value 2": [65.0, 70.0, 10.0, 52.0, 37.0]
    })

state_defaults = {
    'last_c1': '#045EA8', 'last_c2': '#C80000', 'show_v2': False, 
    'chart_type': "Bar", 'orientation': "Vertical",
    'editor_key': 0, 'line_width': 12, 'show_markers': True,
    'marker_size': 18, 'marker_symbol': 'circle',
    'bar_gap': 0.22, 'y_start_zero': True, 'text_choice': "White",
    'width': 1000, 'height': 800, 'grid_layer': "Above Data",
    'x_bold': True, 'y_bold': True, 'y_step': 10.0,
    'x_sz': 28, 'y_sz': 28, 
    'show_values': False, 'value_sz': 24, 'value_bold': True
}
for key, val in state_defaults.items():
    if key not in st.session_state: st.session_state[key] = val

# --- 3. CALLBACKS ---
def handle_upload():
    f = st.session_state.csv_uploader
    if f:
        df = pd.read_csv(f) if f.name.endswith('.csv') else pd.read_excel(f)
        df.columns = ["Label", "Value 1"] + list(df.columns[2:])
        st.session_state.main_df = df.reset_index(drop=True)
        st.session_state.editor_key += 1

def handle_json():
    f = st.session_state.json_uploader
    if f:
        p = json.load(f)
        st.session_state.main_df = pd.DataFrame(p['data'])
        s = p.get('settings', {})
        st.session_state.update({
            'last_c1': s.get('color_v1', '#045EA8'), 'last_c2': s.get('color_v2', '#C80000'),
            'show_v2': s.get('show_v2', False), 'chart_type': s.get('chart_type', "Bar"), 
            'orientation': s.get('orientation', "Vertical"), 'line_width': s.get('line_width', 12), 
            'show_markers': s.get('show_markers', True), 'marker_size': s.get('marker_size', 18), 
            'marker_symbol': s.get('marker_symbol', 'circle'), 'bar_gap': s.get('bar_gap', 0.22), 
            'y_start_zero': s.get('y_start_zero', True), 'width': s.get('width', 1000), 
            'height': s.get('height', 800), 'text_choice': s.get('text_choice', "White"), 
            'x_bold': s.get('x_bold', True), 'y_bold': s.get('y_bold', True), 
            'grid_layer': s.get('grid_layer', "Above Data"), 'y_step': s.get('y_step', 10.0), 
            'x_sz': s.get('x_sz', 28), 'y_sz': s.get('y_sz', 28),
            'show_values': s.get('show_values', False), 'value_sz': s.get('value_sz', 24), 
            'value_bold': s.get('value_bold', True)
        })
        st.session_state.editor_key += 1

# --- 4. DATA ENTRY ---
st.subheader("Data Input")
c_up1, c_up2 = st.columns(2)
with c_up1: st.file_uploader("📂 Import CSV/Excel", type=['csv', 'xlsx'], key="csv_uploader", on_change=handle_upload)
with c_up2: st.file_uploader("💾 Load Project", type=['json'], key="json_uploader", on_change=handle_json)

df_input = st.data_editor(st.session_state.main_df, num_rows="dynamic", use_container_width=True, key=f"editor_v{st.session_state.editor_key}", hide_index=True)
if not df_input.equals(st.session_state.main_df):
    st.session_state.main_df = df_input
    st.rerun()

# --- 5. SIDEBAR ---
with st.sidebar:
    st.header("Graphic Config")
    width = st.number_input("Width", value=st.session_state.width); st.session_state.width = width
    height = st.number_input("Height", value=st.session_state.height); st.session_state.height = height
    
    chart_opts = ["Bar", "Line"]
    chart_type = st.radio("Type", chart_opts, index=chart_opts.index(st.session_state.chart_type)); st.session_state.chart_type = chart_type
    
    if chart_type == "Bar":
        orient_opts = ["Vertical", "Horizontal"]
        st.session_state.orientation = st.radio("Orientation", orient_opts, index=orient_opts.index(st.session_state.orientation))
    else:
        st.session_state.orientation = "Vertical"
    
    grid_choice = st.radio("Grid Layer", ["Below Data", "Above Data"], index=1 if st.session_state.grid_layer == "Above Data" else 0)
    st.session_state.grid_layer = grid_choice
    l_val = "above traces" if grid_choice == "Above Data" else "below traces"

    show_v2 = st.checkbox("Show Second Series", value=st.session_state.show_v2); st.session_state.show_v2 = show_v2
    y_start_zero = st.checkbox("Force Axis to 0", value=st.session_state.y_start_zero); st.session_state.y_start_zero = y_start_zero
    
    st.divider()
    st.write("**Data Labels**")
    st.session_state.show_values = st.checkbox("Show Values on Plot", value=st.session_state.show_values)
    st.session_state.value_sz = st.slider("Data Font Size", 10, 80, value=st.session_state.value_sz)
    st.session_state.value_bold = st.checkbox("Data Bold", value=st.session_state.value_bold)

    if chart_type == "Line":
        st.divider()
        st.write("**Markers**")
        line_w = st.slider("Line Width", 1, 30, value=st.session_state.line_width); st.session_state.line_width = line_w
        markers = st.checkbox("Show Points", value=st.session_state.show_markers); st.session_state.show_markers = markers
        st.session_state.marker_size = st.slider("Point Size", 5, 60, value=st.session_state.marker_size)
        m_sym = st.selectbox("Symbol", ["Circle", "Square"], index=0 if st.session_state.marker_symbol == 'circle' else 1); st.session_state.marker_symbol = m_sym.lower()
    else:
        st.session_state.bar_gap = st.slider("Bar Spacing", 0.0, 0.9, value=st.session_state.bar_gap)
    
    st.divider()
    st.header("Typography & Intervals")
    step_label = "X-Axis Interval" if st.session_state.orientation == "Horizontal" else "Y-Axis Interval"
    st.session_state.y_step = st.number_input(step_label, min_value=0.1, value=float(st.session_state.y_step), step=1.0)
    
    st.session_state.x_sz = st.slider("Axis Label Size", 12
