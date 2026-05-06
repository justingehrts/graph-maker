import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import io
import json
from datetime import datetime

# --- 1. FONT LOADING ---
path_reg = "ProximaNova-Regular.ttf"
path_bold = "ProximaNova-Bold.ttf"

@st.cache_data
def load_fonts(reg_path, bold_path):
    try:
        return fm.FontProperties(fname=reg_path), fm.FontProperties(fname=bold_path)
    except:
        return fm.FontProperties(family='sans-serif'), fm.FontProperties(family='sans-serif', weight='bold')

prop_reg, prop_bold = load_fonts(path_reg, path_bold)

st.set_page_config(page_title="Max Graph Maker", layout="wide")

# --- 2. SESSION STATE ---
if 'main_df' not in st.session_state:
    st.session_state.main_df = pd.DataFrame({
        "Label": ["Mon", "Tue", "Wed", "Thu", "Fri"], 
        "Value 1": [75, 80, 50, 60, 75], 
        "Value 2": [65, 70, 10, 52, 37]
    })

state_defaults = {
    'last_c1': '#045EA8', 'last_c2': '#C80000', 'show_v2': False, 
    'chart_type': "Bar", 'width': 1920, 'height': 1080, 
    'text_choice': "White", 'x_sz': 28, 'y_sz': 28, 'y_step': 10.0,
    'bar_gap': 0.22, 'y_start_zero': True, 'x_bold': True, 'y_bold': True,
    'show_values': False, 'value_sz': 24, 'value_bold': True,
    'highlight_idx': "None", 'highlight_color': '#FFD700',
    'line_width': 8, 'marker_size': 15, 'marker_symbol': 'Circle',
    'editor_key': 0, 'x_rot': 0
}
for key, val in state_defaults.items():
    if key not in st.session_state: st.session_state[key] = val

# --- 3. CALLBACKS ---
def handle_upload():
    f = st.session_state.csv_uploader
    if f:
        df = pd.read_csv(f) if f.name.endswith('.csv') else pd.read_excel(f)
        df.columns = ["Label", "Value 1"] + list(df.columns[2:])
        df["Label"] = df["Label"].astype(str).str.replace(r' 00:00:00$', '', regex=True)
        st.session_state.main_df = df.reset_index(drop=True)
        st.session_state.editor_key += 1

def handle_json():
    f = st.session_state.json_uploader
    if f:
        p = json.load(f)
        df_json = pd.DataFrame(p['data'])
        df_json["Label"] = df_json["Label"].astype(str)
        st.session_state.main_df = df_json
        if 'settings' in p: st.session_state.update(p['settings'])
        st.session_state.editor_key += 1

# --- 4. UI / SIDEBAR ---
with st.sidebar:
    st.header("Graphic Config")
    w = st.number_input("Width (px)", value=st.session_state.width); st.session_state.width = w
    h = st.number_input("Height (px)", value=st.session_state.height); st.session_state.height = h
    
    chart_type = st.radio("Chart Type", ["Bar", "Line"], index=0 if st.session_state.chart_type == "Bar" else 1)
    st.session_state.chart_type = chart_type
    
    if chart_type == "Line":
        st.session_state.line_width = st.slider("Line Thickness", 1, 25, st.session_state.line_width)
        st.session_state.marker_size = st.slider("Point Size", 1, 50, st.session_state.marker_size)
        st.session_state.marker_symbol = st.selectbox("Marker Style", ["Circle", "Square", "Triangle", "Diamond"], index=["Circle", "Square", "Triangle", "Diamond"].index(st.session_state.marker_symbol))
    else:
        st.session_state.bar_gap = st.slider("Bar Spacing / Gap", 0.0, 0.9, value=st.session_state.bar_gap)
    
    st.session_state.show_v2 = st.checkbox("Show Second Series", value=st.session_state.show_v2)
    st.session_state.y_start_zero = st.checkbox("Force Axis to 0", value=st.session_state.y_start_zero)
    
    st.divider()
    st.write("**Highlight Point**")
    h_opts = ["None"] + list(range(len(st.session_state.main_df)))
    st.session_state.highlight_idx = st.selectbox("Index", h_opts, index=0)
    st.session_state.highlight_color = st.color_picker("Highlight Color", value=st.session_state.highlight_color)

    st.divider()
    st.write("**Data Labels**")
    st.session_state.show_values = st.checkbox("Show Values", value=st.session_state.show_values)
    st.session_state.value_sz = st.slider("Data Label Font Size", 5, 80, st.session_state.value_sz)
    st.session_state.value_bold = st.checkbox("Data Bold", value=st.session_state.value_bold)

    st.divider()
    st.header("Typography & Intervals")
    st.session_state.y_step = st.number_input("Y Interval", value=float(st.session_state.y_step))
    st.session_state.x_sz = st.slider("Axis Label Size (X)", 10, 100, st.session_state.x_sz)
    st.session_state.x_bold = st.checkbox("Axis Label Bold (X)", value=st.session_state.x_bold)
    st.session_state.x_rot = st.slider("Rotation (Degrees)", -90, 90, st.session_state.x_rot)
    st.session_state.y_sz = st.slider("Axis Value Size (Y)", 10, 100, st.session_state.y_sz)
    st.session_state.y_bold = st.checkbox("Axis Value Bold (Y)", value=st.session_state.y_bold)
    
    st.divider()
    color_map = {"White": "white", "Black": "black", "Navy": "#022E67"}
    st.session_state.text_choice = st.selectbox("Text Color Preset", list(color_map.keys()), index=list(color_map.keys()).index(st.session_state.text_choice))
    txt_col = color_map[st.session_state.text_choice]

    # --- RESTORED COLOR PRESETS ---
    st.write("**Data Colors**")
    presets = {"NY": "#022E67", "RB": "#045EA8", "RD": "#C80000", "WT": "#FFFFFF"}
    
    st.session_state.last_c1 = st.color_picker("S1 Picker", value=st.session_state.last_c1)
    cp1, cp2, cp3, cp4 = st.columns(4)
    if cp1.button("NY", key="s1_ny"): st.session_state.last_c1 = presets["NY"]; st.rerun()
    if cp2.button("RB", key="s1_rb"): st.session_state.last_c1 = presets["RB"]; st.rerun()
    if cp3.button("RD", key="s1_rd"): st.session_state.last_c1 = presets["RD"]; st.rerun()
    if cp4.button("WT", key="s1_wt"): st.session_state.last_c1 = presets["WT"]; st.rerun()

    st.session_state.last_c2 = st.color_picker("S2 Picker", value=st.session_state.last_c2)
    cp5, cp6, cp7, cp8 = st.columns(4)
    if cp5.button("NY", key="s2_ny"): st.session_state.last_c2 = presets["NY"]; st.rerun()
    if cp6.button("RB", key="s2_rb"): st.session_state.last_c2 = presets["RB"]; st.rerun()
    if cp7.button("RD", key="s2_rd"): st.session_state.last_c2 = presets["RD"]; st.rerun()
    if cp8.button("WT", key="s2_wt"): st.session_state.last_c2 = presets["WT"]; st.rerun()
    
    if st.button("🔄 APPLY SETTINGS"):
        st.rerun()

# --- 5. DATA INPUT ---
st.subheader("Data Input")
c1, c2 = st.columns(2)
with c1: st.file_uploader("📂 Import CSV/Excel", type=['csv','xlsx'], key="csv_uploader", on_change=handle_upload)
with c2: st.file_uploader("💾 Load Project", type=['json'], key="json_uploader", on_change=handle_json)

df_input = st.data_editor(st.session_state.main_df, num_rows="dynamic", use_container_width=True, key=f"editor_{st.session_state.editor_key}", hide_index=False, column_config={"Label": st.column_config.TextColumn("Label")})

df_clean = df_input.copy()
df_clean["Label"] = df_clean["Label"].fillna("").astype(str).str.replace(r' 00:00:00$', '', regex=True)
df_clean["Value 1"] = pd.to_numeric(df_clean["Value 1"], errors='coerce').fillna(0)
if "Value 2" in df_clean.columns:
    df_clean["Value 2"] = pd.to_numeric(df_clean["Value 2"], errors='coerce').fillna(0)

if not df_input.equals(st.session_state.main_df):
    st.session_state.main_df = df_input
    st.rerun()

# --- 6. PREVIEW CONTRAST CSS ---
preview_bg = "#262730" if txt_col == "white" else "white"
st.markdown(f"""<style> [data-testid="stImage"] {{ background-color: {preview_bg}; border-radius: 10px; padding: 20px; }} </style>""", unsafe_allow_html=True)

# --- 7. MATPLOTLIB ENGINE ---
dpi = 100
fig_w, fig_h = st.session_state.width / dpi, st.session_state.height / dpi
fig, ax = plt.subplots(figsize=(fig_w, fig_h), dpi=dpi)
fig.patch.set_alpha(0) 
ax.set_facecolor('none')

labels = df_clean["Label"].tolist()
v1 = df_clean["Value 1"].tolist()
x = range(len(labels))

symbol_map = {"Circle": "o", "Square": "s", "Triangle": "^", "Diamond": "D"}
m_sym = symbol_map.get(st.session_state.marker_symbol, "o")
val_font = prop_bold if st.session_state.value_bold else prop_reg

if st.session_state.chart_type == "Bar":
    width_val = 0.8 - st.session_state.bar_gap
    colors = [st.session_state.last_c1] * len(v1)
    if st.session_state.highlight_idx != "None":
        try: colors[int(st.session_state.highlight_idx)] = st.session_state.highlight_color
        except: pass
        
    if st.session_state.show_v2 and "Value 2" in df_clean.columns:
        v2 = df_clean["Value 2"].tolist()
        r1 = ax.bar([i - width_val/4 for i in x], v1, width=width_val/2, color=st.session_state.last_c1, zorder=2)
        r2 = ax.bar([i + width_val/4 for i in x], v2, width=width_val/2, color=st.session_state.last_c2, zorder=2)
        if st.session_state.show_values:
            ax.bar_label(r1, padding=5, color=txt_col, fontproperties=val_font, fontsize=st.session_state.value_sz, fmt='%g')
            ax.bar_label(r2, padding=5, color=txt_col, fontproperties=val_font, fontsize=st.session_state.value_sz, fmt='%g')
    else:
        r = ax.bar(x, v1, width=width_val, color=colors, zorder=2)
        if st.session_state.show_values:
            ax.bar_label(r, padding=5, color=txt_col, fontproperties=val_font, fontsize=st.session_state.value_sz, fmt='%g')
else:
    m_colors = [st.session_state.last_c1] * len(v1)
    if st.session_state.highlight_idx != "None":
        try: m_colors[int(st.session_state.highlight_idx)] = st.session_state.highlight_color
        except: pass
    ax.plot(x, v1, color=st.session_state.last_c1, linewidth=st.session_state.line_width, zorder=2)
    ax.scatter(x, v1, color=m_colors, s=st.session_state.marker_size**2, marker=m_sym, zorder=3)
    if st.session_state.show_v2 and "Value 2" in df_clean.columns:
        v2 = df_clean["Value 2"].tolist()
        ax.plot(x, v2, color=st.session_state.last_c2, linewidth=st.session_state.line_width, marker=m_sym, markersize=st.session_state.marker_size, zorder=2)
    if st.session_state.show_values:
        for i, v in enumerate(v1):
            clean_val = f"{v:g}" 
            ax.text(i, v + (max(v1 or [1])*0.03), clean_val, color=txt_col, fontproperties=val_font, fontsize=st.session_state.value_sz, ha='center', zorder=5)

# --- 8. AXIS LOCKDOWN ---
ax.set_xticks(x)
ax.set_xticklabels(labels, fontproperties=prop_bold if st.session_state.x_bold else prop_reg, fontsize=st.session_state.x_sz, color=txt_col, rotation=st.session_state.x_rot)
ax.tick_params(axis='x', colors=txt_col, width=3, length=8, zorder=4)

ax.yaxis.set_major_locator(plt.MultipleLocator(st.session_state.y_step))
ax.tick_params(axis='y', colors=txt_col, width=3, length=8, zorder=4)

# Force individual font properties to prevent cross-talk
for tick in ax.get_yticklabels():
    tick.set_fontproperties(prop_bold if st.session_state.y_bold else prop_reg)
    tick.set_fontsize(st.session_state.y_sz)
for tick in ax.get_xticklabels():
    tick.set_fontproperties(prop_bold if st.session_state.x_bold else prop_reg)
    tick.set_fontsize(st.session_state.x_sz)

all_data = v1 + (df_clean["Value 2"].tolist() if (st.session_state.show_v2 and "Value 2" in df_clean.columns) else [])
ax.set_ylim(0 if st.session_state.y_start_zero else min(all_data or [0]) * 0.9, max(all_data or [10]) * 1.25)

ax.spines['top'].set_visible(False)
ax.spines['right'].set_visible(False)
ax.spines['left'].set_linewidth(4); ax.spines['left'].set_color(txt_col); ax.spines['left'].set_zorder(4)
ax.spines['bottom'].set_linewidth(4); ax.spines['bottom'].set_color(txt_col); ax.spines['bottom'].set_zorder(4)
ax.grid(True, axis='y', color='gray', linestyle='-', alpha=0.3, zorder=1)

# --- 9. EXPORT ---
buf = io.BytesIO()
plt.savefig(buf, format="png", transparent=True, bbox_inches='tight', pad_inches=0.1)
st.image(buf, use_container_width=True)
plt.close(fig)

st.download_button("🚀 DOWNLOAD PNG", data=buf.getvalue(), file_name=f"weather_graphic_{datetime.now().strftime('%H%M%S')}.png", mime="image/png")

if st.button("💾 SAVE PROJECT SETTINGS"):
    st.download_button("Confirm JSON Download", data=json.dumps({"data": df_input.to_dict(orient='records'), "settings": {k:v for k,v in st.session_state.items() if k not in ['main_df','editor_key','csv_uploader','json_uploader']}}), file_name="weather_project.json")
