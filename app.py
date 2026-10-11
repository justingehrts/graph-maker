import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import io
import json
import re
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

st.set_page_config(page_title="Max Graph Maker", page_icon="📊", layout="wide")

# --- 2. SESSION STATE ---
if 'main_df' not in st.session_state:
    st.session_state.main_df = pd.DataFrame({
        "Label": ["Mon", "Tue", "Wed", "Thu", "Fri"], 
        "Value 1": [75.0, 80.0, 50.0, 60.0, 75.0], 
        "Value 2": [65.0, 70.0, 10.0, 52.0, 37.0]
    })

# Used as our master list for clean JSON exports
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
    # Re-assigning keeps widget-bound values alive while their widget is hidden (e.g. Line-only controls in Bar mode)
    st.session_state[key] = st.session_state[key]

# Allowed values for every widget-bound setting; shared by the widgets and project loading
TEXT_COLORS = {"White": "white", "Black": "black", "Navy": "#022E67"}
MARKER_SYMBOLS = ["Circle", "Square", "Triangle", "Diamond"]
CHOICES = {'chart_type': ["Bar", "Line"], 'text_choice': list(TEXT_COLORS), 'marker_symbol': MARKER_SYMBOLS}
RANGES = {
    'width': (100, 7680), 'height': (100, 7680), 'x_sz': (10, 100), 'y_sz': (10, 100),
    'value_sz': (5, 80), 'line_width': (1, 25), 'marker_size': (1, 50), 'x_rot': (-90, 90),
    'bar_gap': (0.0, 0.9), 'y_step': (0.01, 1e9),
}
COLOR_KEYS = ['last_c1', 'last_c2', 'highlight_color']
MAX_Y_TICKS = 50

def sanitize_setting(key, val):
    """Return a value safe to put into the widget for `key`, or None if it can't be used."""
    if key in CHOICES:
        return val if val in CHOICES[key] else None
    if key in RANGES:
        if isinstance(val, bool) or not isinstance(val, (int, float)): return None
        lo, hi = RANGES[key]
        return type(lo)(min(max(val, lo), hi))
    if key in COLOR_KEYS:
        return val if isinstance(val, str) and re.fullmatch(r'#[0-9A-Fa-f]{6}', val) else None
    if key == 'highlight_idx':
        return val if val == "None" or (isinstance(val, int) and not isinstance(val, bool) and val >= 0) else None
    if isinstance(state_defaults.get(key), bool):
        return val if isinstance(val, bool) else None
    return None

# --- 3. CALLBACKS ---
def set_preset_color(target_key, color_hex):
    """Native callback to update color instantly without double-reruns."""
    st.session_state[target_key] = color_hex

def handle_upload():
    f = st.session_state.csv_uploader
    if f:
        try:
            new_df = pd.read_csv(f) if f.name.endswith('.csv') else pd.read_excel(f)
            
            incoming_cols = list(new_df.columns)
            rename_dict = {}
            if len(incoming_cols) > 0: rename_dict[incoming_cols[0]] = "Label"
            if len(incoming_cols) > 1: rename_dict[incoming_cols[1]] = "Value 1"
            if len(incoming_cols) > 2: rename_dict[incoming_cols[2]] = "Value 2"
            new_df = new_df.rename(columns=rename_dict)
            
            if "Label" in new_df.columns:
                new_df["Label"] = new_df["Label"].astype(str).str.replace(r' 00:00:00$', '', regex=True)
                
            if "Value 2" not in new_df.columns:
                new_df["Value 2"] = 0.0
                
            core_cols = ["Label", "Value 1", "Value 2"]
            st.session_state.main_df = new_df[core_cols].reset_index(drop=True)
            st.session_state.editor_key += 1
        except Exception as e:
            st.error(f"Failed to process file. Ensure it is a valid CSV or Excel document. Error: {e}")

def handle_json():
    f = st.session_state.json_uploader
    if f:
        try:
            p = json.load(f)
            df_json = pd.DataFrame(p['data'])
            df_json["Label"] = df_json["Label"].astype(str)
            st.session_state.main_df = df_json
            
            if 'settings' in p: 
                # Only load known keys with valid values; anything else keeps its current setting
                for k, v in p['settings'].items():
                    if k not in state_defaults or k == 'editor_key': continue
                    safe_val = sanitize_setting(k, v)
                    if safe_val is not None: st.session_state[k] = safe_val
            st.session_state.editor_key += 1
        except Exception as e:
            st.error(f"Failed to load project file. It may be corrupted. Error: {e}")

# --- 4. UI / SIDEBAR ---
# Widgets are bound to session state via `key`, so each change applies on the first try
with st.sidebar:
    st.header("Graphic Config")
    st.number_input("Width (px)", *RANGES['width'], step=10, key='width')
    st.number_input("Height (px)", *RANGES['height'], step=10, key='height')
    
    chart_type = st.radio("Chart Type", CHOICES['chart_type'], key='chart_type')
    
    if chart_type == "Line":
        st.slider("Line Thickness", *RANGES['line_width'], key='line_width')
        st.slider("Point Size", *RANGES['marker_size'], key='marker_size')
        st.selectbox("Marker Style", MARKER_SYMBOLS, key='marker_symbol')
    else:
        st.slider("Bar Spacing / Gap", *RANGES['bar_gap'], key='bar_gap')
    
    st.checkbox("Show Second Series", key='show_v2')
    st.checkbox("Force Axis to 0", key='y_start_zero')
    
    st.divider()
    st.write("**Highlight Point**")
    h_opts = ["None"] + list(range(len(st.session_state.main_df)))
    if st.session_state.highlight_idx not in h_opts: st.session_state.highlight_idx = "None"
    st.selectbox("Index", h_opts, key='highlight_idx')
    st.color_picker("Highlight Color", key='highlight_color')

    st.divider()
    st.write("**Data Labels**")
    st.checkbox("Show Values", key='show_values')
    st.slider("Data Label Font Size", *RANGES['value_sz'], key='value_sz')
    st.checkbox("Data Bold", key='value_bold')

    st.divider()
    st.header("Typography & Intervals")
    st.number_input("Y Interval", min_value=RANGES['y_step'][0], max_value=RANGES['y_step'][1], key='y_step')
    st.slider("Axis Label Size (X)", *RANGES['x_sz'], key='x_sz')
    st.checkbox("Axis Label Bold (X)", key='x_bold')
    st.slider("Rotation (Degrees)", *RANGES['x_rot'], key='x_rot')
    st.slider("Axis Value Size (Y)", *RANGES['y_sz'], key='y_sz')
    st.checkbox("Axis Value Bold (Y)", key='y_bold')
    
    st.divider()
    st.selectbox("Text Color Preset", list(TEXT_COLORS), key='text_choice')
    txt_col = TEXT_COLORS[st.session_state.text_choice]

    st.write("**Data Colors**")
    presets = {"NY": "#022E67", "RB": "#045EA8", "RD": "#C80000", "WT": "#FFFFFF"}
    
    st.color_picker("S1 Picker", key='last_c1')
    cp1, cp2, cp3, cp4 = st.columns(4)
    cp1.button("NY", key="s1_ny", on_click=set_preset_color, args=('last_c1', presets["NY"]))
    cp2.button("RB", key="s1_rb", on_click=set_preset_color, args=('last_c1', presets["RB"]))
    cp3.button("RD", key="s1_rd", on_click=set_preset_color, args=('last_c1', presets["RD"]))
    cp4.button("WT", key="s1_wt", on_click=set_preset_color, args=('last_c1', presets["WT"]))

    st.color_picker("S2 Picker", key='last_c2')
    cp5, cp6, cp7, cp8 = st.columns(4)
    cp5.button("NY", key="s2_ny", on_click=set_preset_color, args=('last_c2', presets["NY"]))
    cp6.button("RB", key="s2_rb", on_click=set_preset_color, args=('last_c2', presets["RB"]))
    cp7.button("RD", key="s2_rd", on_click=set_preset_color, args=('last_c2', presets["RD"]))
    cp8.button("WT", key="s2_wt", on_click=set_preset_color, args=('last_c2', presets["WT"]))

# --- 5. DATA INPUT ---
st.subheader("Data Input")
c1, c2 = st.columns(2)
with c1: st.file_uploader("📂 Import CSV/Excel", type=['csv','xlsx'], key="csv_uploader", on_change=handle_upload)
with c2: st.file_uploader("💾 Load Project", type=['json'], key="json_uploader", on_change=handle_json)

df_input = st.data_editor(st.session_state.main_df, num_rows="dynamic", use_container_width=True, key=f"editor_{st.session_state.editor_key}", hide_index=False, column_config={"Label": st.column_config.TextColumn("Label")})

df_clean = df_input.copy()
df_clean["Label"] = df_clean["Label"].fillna("").astype(str).str.replace(r' 00:00:00$', '', regex=True)
df_clean["Value 1"] = pd.to_numeric(df_clean["Value 1"], errors='coerce').fillna(0.0)
if "Value 2" in df_clean.columns:
    df_clean["Value 2"] = pd.to_numeric(df_clean["Value 2"], errors='coerce').fillna(0.0)

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
    width_val = max(0.1, 0.8 - st.session_state.bar_gap) # Hard floor applied
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

all_data = v1 + (df_clean["Value 2"].tolist() if (st.session_state.show_v2 and "Value 2" in df_clean.columns) else [])
ax.set_ylim(0 if st.session_state.y_start_zero else min(all_data or [0]) * 0.9, max(all_data or [10]) * 1.25)

# Widen the interval if it would draw an unreadable (or app-freezing) number of ticks
y_lo, y_hi = ax.get_ylim()
y_step = max(st.session_state.y_step, abs(y_hi - y_lo) / MAX_Y_TICKS)
if y_step > st.session_state.y_step:
    st.caption(f"⚠️ Y Interval {st.session_state.y_step:g} is too small for this data range; using {y_step:.3g} instead.")
ax.yaxis.set_major_locator(plt.MultipleLocator(y_step))
ax.tick_params(axis='y', colors=txt_col, width=3, length=8, zorder=4)

for tick in ax.get_yticklabels():
    tick.set_fontproperties(prop_bold if st.session_state.y_bold else prop_reg)
    tick.set_fontsize(st.session_state.y_sz)
for tick in ax.get_xticklabels():
    tick.set_fontproperties(prop_bold if st.session_state.x_bold else prop_reg)
    tick.set_fontsize(st.session_state.x_sz)

ax.spines['top'].set_visible(False)
ax.spines['right'].set_visible(False)
ax.spines['left'].set_linewidth(4); ax.spines['left'].set_color(txt_col); ax.spines['left'].set_zorder(4)
ax.spines['bottom'].set_linewidth(4); ax.spines['bottom'].set_color(txt_col); ax.spines['bottom'].set_zorder(4)
ax.grid(True, axis='y', color='gray', linestyle='-', alpha=0.3, zorder=1)

# --- 9. EXPORT ---
fig.tight_layout() 
buf = io.BytesIO()
plt.savefig(buf, format="png", transparent=True) 
st.image(buf, use_container_width=True)
plt.close(fig)

# Setup export downloads side-by-side
col_dl1, col_dl2 = st.columns(2)

with col_dl1:
    st.download_button("🚀 DOWNLOAD PNG", data=buf.getvalue(), file_name=f"weather_graphic_{datetime.now().strftime('%H%M%S')}.png", mime="image/png", use_container_width=True)

with col_dl2:
    # Generates a strictly clean dictionary for saving
    clean_settings = {k: st.session_state[k] for k in state_defaults.keys() if k in st.session_state}
    project_json = json.dumps({"data": df_clean.to_dict(orient='records'), "settings": clean_settings})
    
    st.download_button("💾 SAVE PROJECT (JSON)", data=project_json, file_name="max_graph_project.json", mime="application/json", use_container_width=True)
