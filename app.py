import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import io
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
    'width': 1920, 'height': 1080, 'text_choice': "White",
    'x_sz': 28, 'y_sz': 28, 'y_step': 10.0,
    'bar_gap': 0.22, 'y_start_zero': True,
    'x_bold': True, 'y_bold': True
}
for key, val in state_defaults.items():
    if key not in st.session_state: st.session_state[key] = val

# --- 3. SIDEBAR CONFIG ---
with st.sidebar:
    st.header("Graphic Config")
    w = st.number_input("Width (px)", value=st.session_state.width); st.session_state.width = w
    h = st.number_input("Height (px)", value=st.session_state.height); st.session_state.height = h
    
    st.session_state.last_c1 = st.color_picker("Series 1 Color", value=st.session_state.last_c1)
    st.session_state.show_v2 = st.checkbox("Show Series 2", value=st.session_state.show_v2)
    if st.session_state.show_v2:
        st.session_state.last_c2 = st.color_picker("Series 2 Color", value=st.session_state.last_c2)
    
    st.divider()
    st.session_state.y_step = st.number_input("Y-Axis Interval", value=float(st.session_state.y_step))
    st.session_state.y_start_zero = st.checkbox("Force Y to 0", value=st.session_state.y_start_zero)
    st.session_state.bar_gap = st.slider("Bar Gap", 0.0, 0.9, value=st.session_state.bar_gap)
    
    st.divider()
    st.session_state.x_sz = st.slider("Label Size", 10, 100, st.session_state.x_sz)
    st.session_state.x_bold = st.checkbox("Bold Labels", value=st.session_state.x_bold)
    st.session_state.y_sz = st.slider("Value Size", 10, 100, st.session_state.y_sz)
    st.session_state.y_bold = st.checkbox("Bold Values", value=st.session_state.y_bold)

    color_map = {"White": "white", "Black": "black"}
    st.session_state.text_choice = st.selectbox("Text Color", list(color_map.keys()))
    txt_col = color_map[st.session_state.text_choice]

# --- 4. DATA EDITOR ---
st.subheader("Data Input")
df_input = st.data_editor(st.session_state.main_df, num_rows="dynamic", use_container_width=True)

# --- 5. MATPLOTLIB DRAWING ENGINE ---
dpi = 100
fig_w, fig_h = st.session_state.width / dpi, st.session_state.height / dpi

# Create figure with the requested pixel dimensions
fig, ax = plt.subplots(figsize=(fig_w, fig_h), dpi=dpi)
fig.patch.set_alpha(0) 
ax.set_facecolor('none')

labels = df_input["Label"].tolist()
v1 = df_input["Value 1"].tolist()
x = range(len(labels))
width_val = 0.8 - st.session_state.bar_gap

if st.session_state.show_v2:
    v2 = df_input["Value 2"].tolist()
    ax.bar([i - width_val/4 for i in x], v1, width=width_val/2, color=st.session_state.last_c1)
    ax.bar([i + width_val/4 for i in x], v2, width=width_val/2, color=st.session_state.last_c2)
else:
    ax.bar(x, v1, width=width_val, color=st.session_state.last_c1)

# Axis Styling - Forced to follow Width/Height
ax.set_xticks(x)
ax.set_xticklabels(labels, fontproperties=prop_bold if st.session_state.x_bold else prop_reg, fontsize=st.session_state.x_sz, color=txt_col)

# Y Scaling logic
all_data = v1 + (df_input["Value 2"].tolist() if st.session_state.show_v2 else [])
y_max = max(all_data) * 1.15
y_min = 0 if st.session_state.y_start_zero else min(all_data) * 0.85
ax.set_ylim(y_min, y_max)

ax.yaxis.set_major_locator(plt.MultipleLocator(st.session_state.y_step))
ax.tick_params(axis='y', colors=txt_col, labelsize=st.session_state.y_sz)

# Set tick font properties individually
for label in ax.get_yticklabels():
    label.set_fontproperties(prop_bold if st.session_state.y_bold else prop_reg)

# Frame Styling
ax.spines['top'].set_visible(False)
ax.spines['right'].set_visible(False)
ax.spines['left'].set_color(txt_col)
ax.spines['bottom'].set_color(txt_col)
ax.grid(True, axis='y', color='gray', linestyle='--', alpha=0.3)

# --- 6. RENDER AND DOWNLOAD ---
buf = io.BytesIO()
plt.savefig(buf, format="png", transparent=True)
st.image(buf, use_container_width=True)

st.download_button(
    label="🚀 DOWNLOAD PNG",
    data=buf.getvalue(),
    file_name=f"weather_graphic_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png",
    mime="image/png"
)
