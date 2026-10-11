import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import io
import json
import os
import re
from datetime import datetime

st.set_page_config(page_title="Max Graph Maker", page_icon="📊", layout="wide")

# --- 1. FONT LOADING ---
path_reg = "ProximaNova-Regular.ttf"
path_bold = "ProximaNova-Bold.ttf"

@st.cache_resource
def load_fonts(reg_path, bold_path):
    """Return (regular, bold, using_fallback). FontProperties doesn't check the file, so check it here."""
    if os.path.isfile(reg_path) and os.path.isfile(bold_path):
        return fm.FontProperties(fname=reg_path), fm.FontProperties(fname=bold_path), False
    return fm.FontProperties(family='sans-serif'), fm.FontProperties(family='sans-serif', weight='bold'), True

prop_reg, prop_bold, font_fallback = load_fonts(path_reg, path_bold)

# --- 2. SESSION STATE ---
CORE_COLS = ["Label", "Value 1", "Value 2"]

if 'main_df' not in st.session_state:
    st.session_state.main_df = pd.DataFrame({
        "Label": ["Mon", "Tue", "Wed", "Thu", "Fri"],
        "Value 1": [75.0, 80.0, 50.0, 60.0, 75.0],
        "Value 2": [65.0, 70.0, 10.0, 52.0, 37.0]
    })

# Chart settings: the master list for project files
state_defaults = {
    'last_c1': '#045EA8', 'last_c2': '#C80000', 'show_v2': False,
    'chart_type': "Bar", 'width': 1920, 'height': 1080,
    'text_choice': "White", 'x_sz': 28, 'y_sz': 28, 'y_step': 10.0,
    'bar_gap': 0.22, 'y_start_zero': True, 'x_bold': True, 'y_bold': True,
    'show_values': False, 'value_sz': 24, 'value_bold': True,
    'highlight_idx': "None", 'highlight_color': '#FFD700',
    'line_width': 8, 'marker_size': 15, 'marker_symbol': 'Circle',
    'x_rot': 0,
    'num_decimals': "Auto", 'num_prefix': "", 'num_suffix': "", 'num_thousands': False, 'axis_units': False,
    'grid_show': True, 'grid_color': '#808080', 'grid_alpha': 0.3, 'grid_width': 0.8, 'grid_style': "Solid",
}
# Internal counters, bumped to reset the data editor / uploaders; never saved to project files
internal_defaults = {'editor_key': 0, 'csv_uploader_key': 0, 'json_uploader_key': 0}

for key, val in {**state_defaults, **internal_defaults}.items():
    if key not in st.session_state: st.session_state[key] = val
for key in state_defaults:
    # Re-assigning keeps widget-bound values alive while their widget is hidden (e.g. Line-only controls in Bar mode)
    st.session_state[key] = st.session_state[key]

# Allowed values for every widget-bound setting; shared by the widgets and project loading
TEXT_COLORS = {"White": "white", "Black": "black", "Navy": "#022E67"}
MARKER_SYMBOLS = ["Circle", "Square", "Triangle", "Diamond"]
GRID_STYLES = {"Solid": "-", "Dashed": "--", "Dotted": ":"}
CHOICES = {'chart_type': ["Bar", "Line"], 'text_choice': list(TEXT_COLORS), 'marker_symbol': MARKER_SYMBOLS,
           'num_decimals': ["Auto", "0", "1", "2", "3"], 'grid_style': list(GRID_STYLES)}
RANGES = {
    'width': (100, 7680), 'height': (100, 7680), 'x_sz': (10, 100), 'y_sz': (10, 100),
    'value_sz': (5, 80), 'line_width': (1, 25), 'marker_size': (1, 50), 'x_rot': (-90, 90),
    'bar_gap': (0.0, 0.9), 'y_step': (0.01, 1e9), 'grid_alpha': (0.0, 1.0), 'grid_width': (0.5, 8.0),
}
COLOR_KEYS = ['last_c1', 'last_c2', 'highlight_color', 'grid_color']
TEXT_KEYS = {'num_prefix': 8, 'num_suffix': 8}  # Free-text settings and their max length
# Brand presets for the series colors: name -> hex
COLOR_PRESETS = {"Navy": "#022E67", "Blue": "#045EA8", "Red": "#C80000", "White": "#FFFFFF"}
MAX_Y_TICKS = 50

def sanitize_setting(key, val):
    """Return a value safe to put into the widget for `key`, or None if it can't be used."""
    if key in CHOICES:
        return val if val in CHOICES[key] else None
    if key in RANGES:
        if isinstance(val, bool) or not isinstance(val, (int, float)): return None
        lo, hi = RANGES[key]
        return type(lo)(min(max(val, lo), hi))
    if key in TEXT_KEYS:
        return val if isinstance(val, str) and len(val) <= TEXT_KEYS[key] else None
    if key in COLOR_KEYS:
        return val if isinstance(val, str) and re.fullmatch(r'#[0-9A-Fa-f]{6}', val) else None
    if key == 'highlight_idx':
        return val if val == "None" or (isinstance(val, int) and not isinstance(val, bool) and val >= 0) else None
    if isinstance(state_defaults.get(key), bool):
        return val if isinstance(val, bool) else None
    return None

def normalize_df(df):
    """Coerce any table into Label (text) + Value 1/Value 2 (numbers). Returns (df, count of non-numeric cells zeroed)."""
    df = df.copy()
    for col in CORE_COLS:
        if col not in df.columns: df[col] = "" if col == "Label" else 0.0
    df["Label"] = df["Label"].fillna("").astype(str).str.replace(r' 00:00:00$', '', regex=True)
    bad_cells = 0
    for col in ["Value 1", "Value 2"]:
        raw = df[col]
        if not pd.api.types.is_numeric_dtype(raw):
            # Strip units and separators people paste along with numbers, e.g. 75°, 1,234, 0.5"
            raw = raw.astype(str).str.replace('\u2212', '-').str.replace(r'[^0-9.\-]', '', regex=True)
            raw = raw.mask((raw == '') | df[col].isna())
        nums = pd.to_numeric(raw, errors='coerce')
        bad_cells += int((nums.isna() & df[col].notna()).sum())
        df[col] = nums.fillna(0.0).astype(float)
    return df[CORE_COLS].reset_index(drop=True), bad_cells

def format_number(v, s, units=True):
    """Format a value per the Number Format settings; `units` adds the prefix/suffix."""
    sep = ',' if s['num_thousands'] else ''
    if s['num_decimals'] == "Auto":
        txt = f"{v:{sep}.3f}".rstrip('0').rstrip('.')
    else:
        txt = f"{v:{sep}.{int(s['num_decimals'])}f}"
    if not txt.lstrip('-').strip('0.,'): txt = txt.lstrip('-')  # No "-0" from rounding
    txt = txt.replace('-', '\u2212')  # Typographic minus sign
    return f"{s['num_prefix']}{txt}{s['num_suffix']}" if units else txt

# --- 3. CALLBACKS ---
def set_preset_color(target_key, color_hex):
    """Native callback to update color instantly without double-reruns."""
    st.session_state[target_key] = color_hex

def load_table(new_df):
    """Replace the chart data with a table whose first 3 columns are label, value 1, value 2. Returns False if unusable."""
    cols = list(new_df.columns)
    if len(cols) < 2:
        st.error("The data needs at least 2 columns: labels in the first column, then 1–2 columns of numbers.")
        return False
    new_df = new_df.rename(columns=dict(zip(cols[:3], CORE_COLS)))
    st.session_state.main_df, bad_cells = normalize_df(new_df)
    st.session_state.editor_key += 1
    notes = []
    if len(cols) > 3: notes.append(f"ignored extra columns: {', '.join(map(str, cols[3:]))}")
    if bad_cells: notes.append(f"{bad_cells} non-numeric value{'s' if bad_cells != 1 else ''} set to 0")
    st.toast(f"Imported {len(new_df)} row{'s' if len(new_df) != 1 else ''}" + (f" ({'; '.join(notes)})" if notes else ""))
    return True

def handle_upload():
    f = st.session_state[f"csv_uploader_{st.session_state.csv_uploader_key}"]
    if not f: return
    try:
        new_df = pd.read_csv(f) if f.name.lower().endswith('.csv') else pd.read_excel(f)
    except Exception as e:
        st.error(f"Couldn't read '{f.name}'. Make sure it's a valid CSV or Excel (.xlsx) file. Details: {e}")
        return
    if load_table(new_df):
        st.session_state.csv_uploader_key += 1  # Clear the uploader so the same file can be imported again

def parse_pasted(text):
    """Parse cells copied from Excel/Sheets (tab-separated) or CSV text. A header row is detected and dropped."""
    sep = '\t' if '\t' in text else (';' if ';' in text and ',' not in text else ',')
    df = pd.read_csv(io.StringIO(text.strip()), sep=sep, header=None, dtype=str, skip_blank_lines=True)
    if len(df) > 1 and df.shape[1] > 1:
        # The first row is a header if its first value cell isn't a number
        first_value = str(df.iat[0, 1]).strip()
        if normalize_df(pd.DataFrame({"Value 1": [first_value]}))[1]:
            df = df.iloc[1:]
    return df

def handle_paste():
    text = st.session_state.paste_text
    if not text.strip():
        st.error("Paste some cells first: labels in the first column, then 1–2 columns of numbers.")
        return
    try:
        new_df = parse_pasted(text)
    except Exception as e:
        st.error(f"Couldn't read the pasted data. Details: {e}")
        return
    if load_table(new_df):
        st.session_state.paste_text = ""

def handle_json():
    f = st.session_state[f"json_uploader_{st.session_state.json_uploader_key}"]
    if not f: return
    try:
        p = json.load(f)
        df_json, _ = normalize_df(pd.DataFrame(p['data']))
    except Exception as e:
        st.error(f"Couldn't load project file '{f.name}'. It may be corrupted. Details: {e}")
        return
    st.session_state.main_df = df_json
    if isinstance(p.get('settings'), dict):
        # Only load known keys with valid values; anything else keeps its current setting
        for k, v in p['settings'].items():
            if k not in state_defaults: continue
            safe_val = sanitize_setting(k, v)
            if safe_val is not None: st.session_state[k] = safe_val
    st.session_state.editor_key += 1
    st.session_state.json_uploader_key += 1
    st.toast(f"Loaded project '{f.name}'")

# --- 4. CHART RENDERING ---
def y_limits(values, start_zero):
    """Axis range covering all values (positive or negative) with headroom for data labels."""
    lo, hi = (min(values), max(values)) if values else (0.0, 10.0)
    if start_zero: lo, hi = min(lo, 0.0), max(hi, 0.0)
    span = (hi - lo) or max(abs(hi), 1.0)
    top = hi + span * (0.25 if hi > 0 else 0.1)
    bottom = 0.0 if (start_zero and lo == 0) else lo - span * (0.25 if lo < 0 else 0.1)
    return bottom, top

@st.cache_data(max_entries=20, show_spinner=False)
def render_chart(df, s, txt_col):
    """Draw the chart for data `df` and settings dict `s`. Returns (png bytes, Y interval actually used)."""
    fig, ax = plt.subplots(figsize=(s['width'] / 100, s['height'] / 100), dpi=100)
    fig.patch.set_alpha(0)
    ax.set_facecolor('none')

    labels = df["Label"].tolist()
    v1 = df["Value 1"].tolist()
    v2 = df["Value 2"].tolist() if s['show_v2'] else []
    x = list(range(len(labels)))
    val_font = prop_bold if s['value_bold'] else prop_reg
    label_kw = dict(color=txt_col, fontproperties=val_font, fontsize=s['value_sz'])

    # Highlight applies to series 1 at the chosen index
    c1 = [s['last_c1']] * len(v1)
    if s['highlight_idx'] != "None" and s['highlight_idx'] < len(c1):
        c1[s['highlight_idx']] = s['highlight_color']

    y_lo, y_hi = y_limits(v1 + v2, s['y_start_zero'])
    ax.set_ylim(y_lo, y_hi)

    if s['chart_type'] == "Bar":
        width_val = max(0.1, 0.8 - s['bar_gap']) # Hard floor applied
        if v2:
            bars = [ax.bar([i - width_val/4 for i in x], v1, width=width_val/2, color=c1, zorder=2),
                    ax.bar([i + width_val/4 for i in x], v2, width=width_val/2, color=s['last_c2'], zorder=2)]
        else:
            bars = [ax.bar(x, v1, width=width_val, color=c1, zorder=2)]
        if s['show_values']:
            for r in bars: ax.bar_label(r, labels=[format_number(v, s) for v in r.datavalues], padding=5, **label_kw)
    else:
        m_sym = {"Circle": "o", "Square": "s", "Triangle": "^", "Diamond": "D"}[s['marker_symbol']]
        series = [(v1, s['last_c1'], c1)] + ([(v2, s['last_c2'], [s['last_c2']] * len(v2))] if v2 else [])
        for vals, line_color, marker_colors in series:
            ax.plot(x, vals, color=line_color, linewidth=s['line_width'], zorder=2)
            ax.scatter(x, vals, color=marker_colors, s=s['marker_size']**2, marker=m_sym, zorder=3)
            if s['show_values']:
                offset = (y_hi - y_lo) * 0.03
                for i, v in enumerate(vals):
                    # Labels sit above positive points and below negative ones
                    ax.text(i, v + offset if v >= 0 else v - offset, format_number(v, s), ha='center',
                            va='bottom' if v >= 0 else 'top', zorder=5, **label_kw)

    # --- Axis lockdown ---
    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontproperties=prop_bold if s['x_bold'] else prop_reg, fontsize=s['x_sz'], color=txt_col, rotation=s['x_rot'])
    ax.tick_params(axis='x', colors=txt_col, width=3, length=8, zorder=4)

    # Widen the interval if it would draw an unreadable (or app-freezing) number of ticks
    y_step = max(s['y_step'], (y_hi - y_lo) / MAX_Y_TICKS)
    ax.yaxis.set_major_locator(plt.MultipleLocator(y_step))
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: format_number(v, s, units=s['axis_units'])))
    ax.tick_params(axis='y', colors=txt_col, width=3, length=8, zorder=4)

    for tick in ax.get_yticklabels():
        tick.set_fontproperties(prop_bold if s['y_bold'] else prop_reg)
        tick.set_fontsize(s['y_sz'])
    for tick in ax.get_xticklabels():
        tick.set_fontproperties(prop_bold if s['x_bold'] else prop_reg)
        tick.set_fontsize(s['x_sz'])

    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    for side in ['left', 'bottom']:
        ax.spines[side].set_linewidth(4); ax.spines[side].set_color(txt_col); ax.spines[side].set_zorder(4)
    if y_lo < 0 < y_hi:
        ax.axhline(0, color=txt_col, linewidth=2, zorder=4)  # Baseline when the data crosses zero
    if s['grid_show']:
        ax.grid(True, axis='y', color=s['grid_color'], alpha=s['grid_alpha'], linewidth=s['grid_width'],
                linestyle=GRID_STYLES[s['grid_style']], zorder=1)
    ax.set_axisbelow(True)

    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", transparent=True)
    plt.close(fig)
    return buf.getvalue(), y_step

# --- 5. DATA INPUT ---
# Rendered before the sidebar code so the sidebar can use the current row count
st.subheader("Data Input")
c1, c2 = st.columns(2)
with c1: st.file_uploader("📂 Import CSV/Excel", type=['csv','xlsx'], key=f"csv_uploader_{st.session_state.csv_uploader_key}", on_change=handle_upload)
with c2: st.file_uploader("💾 Load Project", type=['json'], key=f"json_uploader_{st.session_state.json_uploader_key}", on_change=handle_json)
with st.expander("📋 Paste from Excel / Google Sheets"):
    st.text_area("Paste cells here", key="paste_text", height=150,
                 placeholder="Copy the cells (labels in the first column, then 1–2 columns of numbers) and paste them here.\nA header row is optional.")
    st.button("Use pasted data", on_click=handle_paste)

# main_df is only the starting data; the editor keeps the edits itself, so its output is never fed back in
df_input = st.data_editor(
    st.session_state.main_df, num_rows="dynamic", width="stretch", key=f"editor_{st.session_state.editor_key}", hide_index=False,
    column_config={"Label": st.column_config.TextColumn("Label"),
                   "Value 1": st.column_config.NumberColumn("Value 1"),
                   "Value 2": st.column_config.NumberColumn("Value 2")})
df_clean, _ = normalize_df(df_input)

# --- 6. UI / SIDEBAR ---
def highlight_option_label(i, labels):
    """Show highlight choices by their label; add the row number when a label is blank or repeated."""
    if i == "None": return "None"
    label = labels[i].strip()
    if not label: return f"Row {i + 1}"
    return f"{label} (row {i + 1})" if labels.count(labels[i]) > 1 else label

def color_swatches(target):
    """Preset color buttons for the color setting `target`, painted in their own color; the active one gets a ring."""
    css = []
    for col, (name, hex_val) in zip(st.columns(len(COLOR_PRESETS)), COLOR_PRESETS.items()):
        key = f"{target}_{name.lower()}"
        active = st.session_state[target].upper() == hex_val
        col.button(name, key=key, help=f"{name} {hex_val}" + (" (selected)" if active else ""), width="stretch",
                   on_click=set_preset_color, args=(target, hex_val))
        text = "#000000" if hex_val == "#FFFFFF" else "#FFFFFF"
        ring = "box-shadow: 0 0 0 2px var(--st-background-color, #fff), 0 0 0 4px #FF4B4B;" if active else ""
        css.append(f".st-key-{key} button {{ background: {hex_val}; color: {text}; border: 1px solid #888; padding: 0 2px; {ring} }}"
                   f".st-key-{key} button p {{ font-size: 0.75rem; font-weight: 600; }}")
    st.html(f"<style>{''.join(css)}</style>")

# Widgets are bound to session state via `key`, so each change applies on the first try
with st.sidebar:
    st.header("Graphic Config")
    if font_fallback: st.caption("⚠️ Proxima Nova font files not found; using the default sans-serif font.")

    with st.expander("📐 Canvas & Chart", expanded=True):
        cw, ch = st.columns(2)
        cw.number_input("Width (px)", *RANGES['width'], step=10, key='width')
        ch.number_input("Height (px)", *RANGES['height'], step=10, key='height')
        chart_type = st.radio("Chart Type", CHOICES['chart_type'], key='chart_type', horizontal=True)
        if chart_type == "Line":
            st.slider("Line Thickness", *RANGES['line_width'], key='line_width')
            st.slider("Point Size", *RANGES['marker_size'], key='marker_size')
            st.selectbox("Marker Style", MARKER_SYMBOLS, key='marker_symbol')
        else:
            st.slider("Bar Spacing / Gap", *RANGES['bar_gap'], key='bar_gap')
        st.checkbox("Show Second Series", key='show_v2')

    with st.expander("🎨 Colors", expanded=True):
        st.selectbox("Text Color", list(TEXT_COLORS), key='text_choice')
        st.color_picker("Series 1 Color", key='last_c1')
        color_swatches('last_c1')
        if st.session_state.show_v2:
            st.color_picker("Series 2 Color", key='last_c2')
            color_swatches('last_c2')
        st.divider()
        labels = df_clean["Label"].tolist()
        h_opts = ["None"] + list(range(len(labels)))
        if st.session_state.highlight_idx not in h_opts: st.session_state.highlight_idx = "None"
        st.selectbox("Highlight Point", h_opts, key='highlight_idx', format_func=lambda i: highlight_option_label(i, labels),
                     help="Draws one point (Series 1) in the highlight color.")
        st.color_picker("Highlight Color", key='highlight_color')

    with st.expander("🔢 Data Labels & Number Format"):
        st.checkbox("Show Values on Chart", key='show_values')
        st.slider("Data Label Font Size", *RANGES['value_sz'], key='value_sz')
        st.checkbox("Data Labels Bold", key='value_bold')
        st.selectbox("Decimal Places", CHOICES['num_decimals'], key='num_decimals',
                     help="Auto shows up to 3 decimals and drops trailing zeros.")
        cp, cs = st.columns(2)
        cp.text_input("Prefix", key='num_prefix', max_chars=TEXT_KEYS['num_prefix'], placeholder="e.g. $")
        cs.text_input("Suffix", key='num_suffix', max_chars=TEXT_KEYS['num_suffix'], placeholder='e.g. ° % " mph')
        st.checkbox("Thousands Separator (1,000)", key='num_thousands')
        st.checkbox("Prefix/Suffix on Y Axis Too", key='axis_units')

    with st.expander("📏 Axes"):
        st.number_input("Y Interval", min_value=RANGES['y_step'][0], max_value=RANGES['y_step'][1], key='y_step')
        st.checkbox("Force Y Axis to Start at 0", key='y_start_zero')
        st.slider("Y Axis Value Size", *RANGES['y_sz'], key='y_sz')
        st.checkbox("Y Axis Values Bold", key='y_bold')
        st.slider("X Axis Label Size", *RANGES['x_sz'], key='x_sz')
        st.checkbox("X Axis Labels Bold", key='x_bold')
        st.slider("X Label Rotation (Degrees)", *RANGES['x_rot'], key='x_rot')

    with st.expander("▦ Gridlines"):
        st.checkbox("Show Gridlines", key='grid_show')
        if st.session_state.grid_show:
            st.color_picker("Gridline Color", key='grid_color')
            st.slider("Opacity", *RANGES['grid_alpha'], key='grid_alpha')
            st.slider("Thickness", *RANGES['grid_width'], step=0.1, key='grid_width')
            st.selectbox("Style", list(GRID_STYLES), key='grid_style')

    txt_col = TEXT_COLORS[st.session_state.text_choice]

# --- 7. PREVIEW CONTRAST CSS ---
preview_bg = "#262730" if txt_col == "white" else "white"
st.markdown(f"""<style> [data-testid="stImage"] {{ background-color: {preview_bg}; border-radius: 10px; padding: 20px; }} </style>""", unsafe_allow_html=True)

# --- 8. PREVIEW & EXPORT ---
settings = {k: st.session_state[k] for k in state_defaults}
png_bytes, y_step_used = render_chart(df_clean, settings, txt_col)
if y_step_used > settings['y_step']:
    st.caption(f"⚠️ Y Interval {settings['y_step']:g} is too small for this data range; using {y_step_used:.3g} instead.")
st.image(png_bytes, width="stretch")

# Setup export downloads side-by-side
col_dl1, col_dl2 = st.columns(2)

with col_dl1:
    st.download_button("🚀 DOWNLOAD PNG", data=png_bytes, file_name=f"weather_graphic_{datetime.now().strftime('%H%M%S')}.png", mime="image/png", width="stretch")

with col_dl2:
    project_json = json.dumps({"data": df_clean.to_dict(orient='records'), "settings": settings})
    st.download_button("💾 SAVE PROJECT (JSON)", data=project_json, file_name="max_graph_project.json", mime="application/json", width="stretch")
