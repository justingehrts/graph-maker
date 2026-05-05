import streamlit as st
import pandas as pd
import json
import base64
import os
from datetime import datetime

# --- 1. FONT CONFIGURATION ---
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
    'bar_gap_px': 20, 'y_start_zero': True
}
for key, val in state_defaults.items():
    if key not in st.session_state: st.session_state[key] = val

# --- 3. UI ---
st.subheader("Data Input")
df_input = st.data_editor(st.session_state.main_df, num_rows="dynamic", use_container_width=True)

with st.sidebar:
    st.header("Canvas Config")
    width = st.number_input("Target Width", value=st.session_state.width)
    height = st.number_input("Target Height", value=st.session_state.height)
    st.session_state.width, st.session_state.height = width, height
    
    st.session_state.last_c1 = st.color_picker("Series 1 Color", value=st.session_state.last_c1)
    st.session_state.show_v2 = st.checkbox("Show Series 2", value=st.session_state.show_v2)
    if st.session_state.show_v2:
        st.session_state.last_c2 = st.color_picker("Series 2 Color", value=st.session_state.last_c2)
    
    st.session_state.y_step = st.number_input("Y-Axis Interval", value=float(st.session_state.y_step))
    st.session_state.bar_gap_px = st.slider("Spacing Between Groups", 0, 100, 20)
    
    color_map = {"White": "#FFFFFF", "Black": "#000000"}
    st.session_state.text_choice = st.selectbox("Text Color", list(color_map.keys()))
    text_hex = color_map[st.session_state.text_choice]

# --- 4. CANVAS ENGINE (JAVASCRIPT) ---
# We bundle the data and settings into a JSON string to pass to JS
data_json = df_input.to_json(orient='records')

canvas_js = f"""
<div id="canvas-container" style="overflow: auto; background: #262730; padding: 20px; border-radius: 10px;">
    <canvas id="weatherCanvas" width="{width}" height="{height}" style="background: transparent; border: 1px solid #444;"></canvas>
</div>

<script>
(function() {{
    const canvas = document.getElementById('weatherCanvas');
    const ctx = canvas.getContext('2d');
    const data = {data_json};
    
    const width = {width};
    const height = {height};
    const margin = {{ top: 80, right: 80, bottom: 120, left: 150 }};
    const plotWidth = width - margin.left - margin.right;
    const plotHeight = height - margin.top - margin.bottom;
    
    // Calculate Data Scale
    const v1 = data.map(d => d['Value 1']);
    const v2 = data.map(d => d['Value 2'] || 0);
    const allVals = {st.session_state.show_v2} ? [...v1, ...v2] : v1;
    
    const maxVal = Math.max(...allVals);
    const minVal = {st.session_state.y_start_zero} ? 0 : Math.min(...allVals);
    const range = (maxVal - minVal) * 1.15; // 15% head room
    
    const getPlotY = (val) => margin.top + plotHeight - ((val - minVal) / range) * plotHeight;
    const getPlotX = (index) => margin.left + (index / data.length) * plotWidth;
    const barWidth = (plotWidth / data.length) - {st.session_state.bar_gap_px};

    // 1. Draw Background/Grid
    ctx.clearRect(0, 0, width, height);
    ctx.strokeStyle = 'rgba(128,128,128,0.3)';
    ctx.lineWidth = 2;
    ctx.beginPath();
    
    for (let i = minVal; i <= maxVal + (range*0.1); i += {st.session_state.y_step}) {{
        let y = getPlotY(i);
        ctx.moveTo(margin.left, y);
        ctx.lineTo(margin.left + plotWidth, y);
        
        // Y Labels
        ctx.fillStyle = "{text_hex}";
        ctx.font = "bold {st.session_state.y_sz}px Arial"; // Fallback to Arial if Proxima fails to load in canvas
        ctx.textAlign = "right";
        ctx.fillText(i, margin.left - 20, y + 10);
    }}
    ctx.stroke();

    // 2. Draw Bars (FORCE STRETCH)
    data.forEach((d, i) => {{
        const xBase = getPlotX(i) + ({st.session_state.bar_gap_px} / 2);
        
        // Series 1
        ctx.fillStyle = "{st.session_state.last_c1}";
        const yVal1 = getPlotY(d['Value 1']);
        const h1 = (margin.top + plotHeight) - yVal1;
        
        if ({st.session_state.show_v2}) {{
            const subWidth = barWidth / 2;
            ctx.fillRect(xBase, yVal1, subWidth - 2, h1);
            
            // Series 2
            ctx.fillStyle = "{st.session_state.last_c2}";
            const yVal2 = getPlotY(d['Value 2']);
            const h2 = (margin.top + plotHeight) - yVal2;
            ctx.fillRect(xBase + subWidth, yVal2, subWidth - 2, h2);
        }} else {{
            ctx.fillRect(xBase, yVal1, barWidth, h1);
        }}

        // X Labels
        ctx.fillStyle = "{text_hex}";
        ctx.textAlign = "center";
        ctx.font = "{st.session_state.x_sz}px Arial";
        ctx.fillText(d['Label'], xBase + (barWidth/2), margin.top + plotHeight + 50);
    }});

    // 3. Axes Lines
    ctx.strokeStyle = "{text_hex}";
    ctx.lineWidth = 4;
    ctx.beginPath();
    ctx.moveTo(margin.left, margin.top);
    ctx.lineTo(margin.left, margin.top + plotHeight);
    ctx.lineTo(margin.left + plotWidth, margin.top + plotHeight);
    ctx.stroke();

}})();
</script>
"""

# Render the custom canvas
st.components.v1.html(canvas_js, height=height + 100, width=width + 100)

# --- 5. DOWNLOAD LOGIC ---
if st.button("🚀 DOWNLOAD AS PNG"):
    js_download = """
    <script>
    (function() {
        const canvas = window.parent.document.getElementById('weatherCanvas');
        if(!canvas) { alert("Canvas not found"); return; }
        const link = document.createElement('a');
        link.download = 'weather_graphic.png';
        link.href = canvas.toDataURL("image/png");
        link.click();
    })();
    </script>
    """
    st.components.v1.html(js_download, height=0)
