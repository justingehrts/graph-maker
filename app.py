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
    'chart_type': "Bar", 'width': 1920, 'height': 1080, 
    'text_choice': "White", 'x_sz': 28, 'y_sz': 28, 'y_step': 10.0,
    'bar_gap': 0.22, 'y_start_zero': True, 'x_bold': True, 'y_bold': True,
    'show_values': False, 'value_sz': 24, 'value_bold': True,
    'highlight_idx': "None", 'highlight_color': '#FFD700',
    'line_width': 8, 'marker_size': 12, 'editor_key': 0
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
        st.session_state.update(s)
        st.session_state.editor_key += 1

# --- 4. UI / SIDEBAR ---
with st.sidebar:
    st.header("Graphic Config")
    w = st.number_input("Width (px)", value=st.session_state.width); st.session_state.width = w
    h = st.number_input("Height (px)", value=st.session_state.height); st.session_state.height = h
    
    chart_type = st.radio("Chart Type", ["Bar", "Line"], index=0 if st.session_state.chart_type == "Bar" else 1)
    st.session_state.chart_type = chart_type
    
    st.session_state.last_c1 = st.color_picker("Series 1 Color", value=st.session_state.last_c1)
    st.session_state.show_v2 = st.checkbox("Show Series 2", value=st.session_state.show_v2)
    if st.session_state.show_v2:
        st.session_state.last_c2 = st.color_picker("Series 2 Color", value=st.session_state.last_c2)
    
    st.divider()
    st.write("**Highlight Point**")
    h_opts = ["None"] + list(range(len(st.session_state.main_df)))
    st.session_state.highlight_idx = st.selectbox("Index", h_opts, index=0)
    st.session_state.highlight_color = st.color_picker("Color", value=st.session_state.highlight_color)

    st.divider()
    st.write("**Data Labels**")
    st.session_state.show_values = st.checkbox("Show Values", value=st.session_state.show_values)
    st.session_state.value_sz = st.slider("Data Size", 5, 80, st.session_state.value_sz)
    st.session_state.value_bold = st.checkbox("Data Bold", value=st.session_state.value_bold)

    st.divider()
    st.session_state.y_step = st.number_input("Y Interval", value=float(st.session_state.y_step))
    st.session_state.bar_gap = st.slider("Gap/Spacing", 0.0, 0.9, value=st.session_state.bar_gap)
    
    st.session_state.x_sz = st.slider("Label Size", 10, 100, st.session_state.x_sz)
    st.session_state.y_sz = st.slider("Value Size", 10, 100, st.session_state.y_sz)

    color_map = {"White": "white", "Black": "black"}
    st.session_state.text_choice = st.selectbox("Text Color", list(color_map.keys()))
    txt_col = color_map[st.session_state.text_choice]

# --- 5. DATA INPUT ---
st.subheader("Data Input")
c1, c2 = st.columns(2)
with c1: st.file_uploader("📂 Import CSV", type=['csv','xlsx'], key="csv_uploader", on_change=handle_upload)
with c2: st.file_uploader("💾 Load Project", type=['json'], key="json_uploader", on_change=handle_json)

df_input = st.data_editor(st.session_state.main_df, num_rows="dynamic", use_container_width=True, key=f"editor_{st.session_state.editor_key}")

# --- 6. MATPLOTLIB ENGINE ---
dpi = 100
fig_w, fig_h = st.session_state.width / dpi, st.session_state.height / dpi
fig, ax = plt.subplots(figsize=(fig_w, fig_h), dpi=dpi)
fig.patch.set_alpha(0) 
ax.set_facecolor('none')

labels = df_input["Label"].tolist()
v1 = df_input["Value 1"].tolist()
x = range(len(labels))

# Set Global Font for Values
val_font = prop_bold if st.session_state.value_bold else prop_reg

if st.session_state.chart_type == "Bar":
    width_val = 0.8 - st.session_state.bar_gap
    colors = [st.session_state.last_c1] * len(v1)
    if st.session_state.highlight_idx != "None":
        colors[int(st.session_state.highlight_idx)] = st.session_state.highlight_color
        
    if st.session_state.show_v2:
        v2 = df_input["Value 2"].tolist()
        rects1 = ax.bar([i - width_val/4 for i in x], v1, width=width_val/2, color=st.session_state.last_c1)
        rects2 = ax.bar([i + width_val/4 for i in x], v2, width=width_val/2, color=st.session_state.last_c2)
        if st.session_state.show_values:
            ax.bar_label(rects1, padding=5, color=txt_col, fontproperties=val_font, fontsize=st.session_state.value_sz)
            ax.bar_label(rects2, padding=5, color=txt_col, fontproperties=val_font, fontsize=st.session_state.value_sz)
    else:
        rects = ax.bar(x, v1, width=width_val, color=colors)
        if st.session_state.show_values:
            ax.bar_label(rects, padding=5, color=txt_col, fontproperties=val_font, fontsize=st.session_state.value_sz)
else:
    ax.plot(x, v1, color=st.session_state.last_c1, marker='o', linewidth=st.session_state.line_width, markersize=st.session_state.marker_size)
    if st.session_state.show_v2:
        v2 = df_input["Value 2"].tolist()
        ax.plot(x, v2, color=st.session_state.last_c2, marker='o', linewidth=st.session_state.line_width, markersize=st.session_state.marker_size)
    if st.session_state.show_values:
        for i, v in enumerate(v1):
            ax.text(i, v + (max(v1)*0.02), str(v), color=txt_col, fontproperties=val_font, fontsize=st.session_state.value_sz, ha='center')

# Axes Styling
ax.set_xticks(x)
ax.set_xticklabels(labels, fontproperties=prop_bold if st.session_state.x_bold else prop_reg, fontsize=st.session_state.x_sz, color=txt_col)
ax.yaxis.set_major_locator(plt.MultipleLocator(st.session_state.y_step))
ax.tick_params(axis='y', colors=txt_col, labelsize=st.session_state.y_sz)

for label in ax.get_yticklabels():
    label.set_fontproperties(prop_bold if st.session_state.y_bold else prop_reg)

# Range
all_data = v1 + (df_input["Value 2"].tolist() if st.session_state.show_v2 else [])
ax.set_ylim(0 if st.session_state.y_start_zero else min(all_data)*0.9, max(all_data)*1.2)

# Frame
ax.spines['top'].set_visible(False); ax.spines['right'].set_visible(False)
ax.spines['left'].set_color(txt_col); ax.spines['bottom'].set_color(txt_col)
ax.grid(True, axis='y', color='gray', linestyle='--', alpha=0.3)

# --- 7. EXPORT ---
buf = io.BytesIO()
plt.savefig(buf, format="png", transparent=True, bbox_inches='tight', pad_inches=0.1)
st.image(buf, use_container_width=True)

st.download_button("🚀 DOWNLOAD PNG", data=buf.getvalue(), file_name="weather_graphic.png", mime="image/png")

# Save Project Settings
if st.button("💾 SAVE PROJECT SETTINGS"):
    settings = {
        "last_c1": st.session_state.last_c1, "last_c2": st.session_state.last_c2,
        "show_v2": st.session_state.show_v2, "chart_type": st.session_state.chart_type,
        "width": st.session_state.width, "height": st.session_state.height,
        "x_sz": st.session_state.x_sz, "y_sz": st.session_state.y_sz,
        "value_sz": st.session_state.value_sz, "value_bold": st.session_state.value_bold
    }
    st.download_button("Click to Download JSON", data=json.dumps({"data": df_input.to_dict(orient='records'), "settings": settings}), file_name="project.json")
