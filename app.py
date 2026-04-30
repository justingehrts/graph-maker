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
    'show_values': False, 'value_sz': 24, 'value_bold': True,
    'highlight_idx': "None", 'highlight_color': '#FFD700'
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
            'value_bold': s.get('value_bold', True),
            'highlight_idx': s.get('highlight_idx', "None"),
            'highlight_color': s.get('highlight_color', '#FFD700')
        })
        st.session_state.editor_key += 1

# --- 4. DATA ENTRY ---
st.subheader("Data Input")
c_up1, c_up2 = st.columns(2)
with c_up1: st.file_uploader("📂 Import CSV/Excel", type=['csv', 'xlsx'], key="csv_uploader", on_change=handle_upload)
with c_up2: st.file_uploader("💾 Load Project", type=['json'], key="json_uploader", on_change=handle_json)

# RESTORED ROW NUMBERS: hide_index=False ensures user can see indices for highlighting
df_input = st.data_editor(st.session_state.main_df, num_rows="dynamic", use_container_width=True, key=f"editor_v{st.session_state.editor_key}", hide_index=False)
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
    st.write("**Highlight Point**")
    h_opts = ["None"] + list(range(len(df_input)))
    try:
        curr_h_idx = h_opts.index(st.session_state.highlight_idx)
    except:
        curr_h_idx = 0
    st.session_state.highlight_idx = st.selectbox("Index to Highlight", h_opts, index=curr_h_idx)
    st.session_state.highlight_color = st.color_picker("Highlight Color", value=st.session_state.highlight_color)

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
    
    st.session_state.x_sz = st.slider("Axis Label Size", 12, 120, st.session_state.x_sz)
    st.session_state.x_bold = st.checkbox("Axis Label Bold", value=st.session_state.x_bold)
    st.session_state.y_sz = st.slider("Axis Value Size", 12, 120, st.session_state.y_sz)
    st.session_state.y_bold = st.checkbox("Axis Value Bold", value=st.session_state.y_bold)
    
    st.divider()
    color_map = {"White": "white", "Black": "black", "Navy": "rgb(2, 46, 103)"}
    st.session_state.text_choice = st.selectbox("Text Color", list(color_map.keys()), index=list(color_map.keys()).index(st.session_state.text_choice))
    ui_color = color_map[st.session_state.text_choice]
    
    st.write("**Data Colors**")
    st.write("S1 Presets")
    favs = st.columns(4)
    if favs[0].button("RB"): st.session_state.last_c1 = '#045EA8'; st.rerun()
    if favs[1].button("NY"): st.session_state.last_c1 = '#022E67'; st.rerun()
    if favs[2].button("RD"): st.session_state.last_c1 = '#C80000'; st.rerun()
    if favs[3].button("WT"): st.session_state.last_c1 = '#FFFFFF'; st.rerun()
    
    c1_pick, c2_pick = st.columns(2)
    st.session_state.last_c1 = c1_pick.color_picker("S1 Picker", value=st.session_state.last_c1)
    st.session_state.last_c2 = c2_pick.color_picker("S2 Color", value=st.session_state.last_c2)

    st.divider()
    st.download_button("💾 SAVE PROJECT", data=json.dumps({"data": df_input.to_dict(orient='records'), "settings": {"color_v1": st.session_state.last_c1, "color_v2": st.session_state.last_c2, "show_v2": show_v2, "chart_type": chart_type, "orientation": st.session_state.orientation, "line_width": st.session_state.line_width, "show_markers": st.session_state.show_markers, "marker_size": st.session_state.marker_size, "marker_symbol": st.session_state.marker_symbol, "bar_gap": st.session_state.bar_gap, "y_start_zero": y_start_zero, "width": width, "height": height, "text_choice": st.session_state.text_choice, "x_bold": st.session_state.x_bold, "y_bold": st.session_state.y_bold, "x_sz": st.session_state.x_sz, "y_sz": st.session_state.y_sz, "grid_layer": grid_choice, "y_step": st.session_state.y_step, "show_values": st.session_state.show_values, "value_sz": st.session_state.value_sz, "value_bold": st.session_state.value_bold, "highlight_idx": st.session_state.highlight_idx, "highlight_color": st.session_state.highlight_color}}), file_name=f"weather_project_{datetime.now().strftime('%Y%m%d')}.json")

# --- 6. GRAPH LOGIC ---
is_h = (st.session_state.orientation == "Horizontal")
x_font = "ProximaBold" if st.session_state.x_bold else "ProximaRegular"
y_font = "ProximaBold" if st.session_state.y_bold else "ProximaRegular"
val_font_fam = "ProximaBold" if st.session_state.value_bold else "ProximaRegular"

preview_bg = "#262730" if ui_color == "white" else "rgba(0,0,0,0)"

st.markdown(f"""<style>{font_css_base} 
.js-plotly-plot .main-svg text {{ fill: {ui_color} !important; }}
.stPlotlyChart {{ background-color: {preview_bg}; border-radius: 10px; padding: 10px; }}
</style>""", unsafe_allow_html=True)

df_p = df_input.copy()
labels, v1 = df_p["Label"], df_p["Value 1"]
v2 = df_p["Value 2"] if (show_v2 and "Value 2" in df_p.columns) else None

colors_v1 = [st.session_state.last_c1] * len(df_p)
if st.session_state.highlight_idx != "None":
    try:
        colors_v1[int(st.session_state.highlight_idx)] = st.session_state.highlight_color
    except:
        pass

all_vals = pd.concat([v1, v2]) if (show_v2 and v2 is not None) else v1
data_min, data_max = all_vals.min(), all_vals.max()

if not y_start_zero:
    v_range = abs(data_max - data_min) if data_max != data_min else 10
    limit_range = [data_min - (v_range * 0.15), data_max + (v_range * 0.25)]
else:
    limit_range = [0, max(0, data_max) + (abs(max(0, data_max)) * 0.2 or 10)]

fig = go.Figure()
l_pad = max(180, st.session_state.x_sz * 4) if is_h else max(130, st.session_state.y_sz * 2.8)
b_pad = max(130, st.session_state.y_sz * 2.8) if is_h else max(130, st.session_state.x_sz * 3.2)

fig.update_layout(
    font=dict(color=ui_color), width=width, height=height,
    margin=dict(l=l_pad, r=max(100, st.session_state.x_sz*1.5), t=100, b=b_pad),
    xaxis=dict(
        tickfont=dict(size=st.session_state.y_sz if is_h else st.session_state.x_sz, family=y_font if is_h else x_font), 
        showline=True, linewidth=4, linecolor=ui_color,
        showgrid=True if is_h else False, gridcolor='rgba(128,128,128,0.3)',
        range=limit_range if is_h else None, dtick=st.session_state.y_step if is_h else None,
        zeroline=False, layer=l_val
        type='category', 
        tickmode='linear',  # Forces Plotly to show every tick
        tickfont=dict(size=st.session_state.x_sz, family=x_font),
    ),
    yaxis=dict(
        tickfont=dict(size=st.session_state.x_sz if is_h else st.session_state.y_sz, family=x_font if is_h else y_font), 
        showline=True, linewidth=4, linecolor=ui_color,
        showgrid=False if is_h else True, gridcolor='rgba(128,128,128,0.3)',
        range=None if is_h else limit_range, dtick=None if is_h else st.session_state.y_step,
        zeroline=False, layer=l_val, autorange="reversed" if is_h else None
    ),
    bargap=st.session_state.bar_gap if chart_type == "Bar" else None,
    showlegend=False, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)'
)

val_font = dict(size=st.session_state.value_sz, family=val_font_fam, color=ui_color)
bar_pos = "outside" if st.session_state.show_values else "none"
line_mode = 'text+lines+markers' if (st.session_state.show_values and st.session_state.show_markers) else ('text+lines' if st.session_state.show_values else ('lines+markers' if st.session_state.show_markers else 'lines'))

if chart_type == "Bar":
    if is_h:
        fig.add_trace(go.Bar(y=labels, x=v1, orientation='h', marker_color=colors_v1, text=v1 if st.session_state.show_values else "", textposition=bar_pos, textfont=val_font, cliponaxis=False))
        if v2 is not None: fig.add_trace(go.Bar(y=labels, x=v2, orientation='h', marker_color=st.session_state.last_c2, text=v2 if st.session_state.show_values else "", textposition=bar_pos, textfont=val_font, cliponaxis=False))
    else:
        fig.add_trace(go.Bar(x=labels, y=v1, marker_color=colors_v1, text=v1 if st.session_state.show_values else "", textposition=bar_pos, textfont=val_font, cliponaxis=False))
        if v2 is not None: fig.add_trace(go.Bar(x=labels, y=v2, marker_color=st.session_state.last_c2, text=v2 if st.session_state.show_values else "", textposition=bar_pos, textfont=val_font, cliponaxis=False))
else:
    m_dict = dict(size=st.session_state.marker_size, symbol=st.session_state.marker_symbol)
    fig.add_trace(go.Scatter(x=labels, y=v1, line=dict(color=st.session_state.last_c1, width=st.session_state.line_width), mode=line_mode, text=v1 if st.session_state.show_values else "", textposition="top center", textfont=val_font, marker=dict(color=colors_v1, **m_dict)))
    if v2 is not None: fig.add_trace(go.Scatter(x=labels, y=v2, line=dict(color=st.session_state.last_c2, width=st.session_state.line_width), mode=line_mode, text=v2 if st.session_state.show_values else "", textposition="top center", textfont=val_font, marker=dict(color=st.session_state.last_c2, **m_dict)))

st.plotly_chart(fig, use_container_width=False, config={'displayModeBar': False})

# --- 7. PNG EXPORT ---
t_stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
if st.button("🚀 DOWNLOAD PNG"):
    clean_css = font_css_base.replace('\n', ' ').replace('\r', '')
    js = f"""
    <script>
    (function() {{
        const g = window.parent.document.querySelector('.js-plotly-plot');
        if (!g) return;
        const svg = g.querySelector('svg.main-svg');
        const cln = svg.cloneNode(true);
        cln.setAttribute("width", "{width}"); cln.setAttribute("height", "{height}"); cln.setAttribute("viewBox", "0 0 {width} {height}");
        const gridLayer = cln.querySelector('.gridlayer');
        if (gridLayer && "{grid_choice}" === "Above Data") {{ cln.appendChild(gridLayer); }}
        const s = document.createElementNS("http://www.w3.org/2000/svg", "style");
        s.textContent = `{clean_css} text {{ fill: {ui_color} !important; }}`;
        cln.insertBefore(s, cln.firstChild);
        const xml = new XMLSerializer().serializeToString(cln);
        const img = new Image();
        img.onload = function() {{
            const canvas = document.createElement('canvas');
            canvas.width = {width}; canvas.height = {height};
            const ctx = canvas.getContext('2d'); ctx.drawImage(img, 0, 0);
            const a = document.createElement("a");
            a.href = canvas.toDataURL("image/png"); a.download = "weather_graphic_{t_stamp}.png"; a.click();
        }};
        img.src = "data:image/svg+xml;base64," + btoa(unescape(encodeURIComponent(xml)));
    }})();
    </script>
    """
    st.components.v1.html(js, height=0)
