import streamlit as st
import pandas as pd
import io
import json
import re
from calendar import month_name, monthrange
from datetime import date, datetime, timedelta

import charts
import data_io as dio
import iem
from palette import BAR_PALETTE, CHART_PALETTE, GRADIENTS, TEXT_COLORS, GRID_PALETTE, snap_settings

st.set_page_config(page_title="Max Graph Maker", page_icon="📊", layout="wide")

# --- 1. SETTINGS & SESSION STATE ---
# Chart settings: the master list for project files
state_defaults = {
    'last_c1': '#285DA3', 'last_c2': '#A3BCC6', 'show_v2': False,
    'chart_type': "Bar", 'width': 1920, 'height': 1080,
    'x_sz': 28, 'y_sz': 28, 'y_step': 10.0, 'y_auto': True,
    'bar_gap': 0.22, 'y_start_zero': True, 'x_bold': True, 'y_bold': True,
    'show_values': False, 'value_pos': "End", 'value_sz': 24, 'value_bold': True,
    'highlight_idx': "None", 'highlight_color': '#59C8FF',
    'line_width': 8, 'marker_size': 15, 'marker_symbol': 'Circle',
    'x_rot': 0, 'x_label_every': "Auto", 'x_label_band': True,
    'value_kind': "Number",  # "Date": values are days of the year (e.g. last 80° day by year), shown as "Oct 18"
    'num_decimals': "Auto", 'num_prefix': "", 'num_suffix': "", 'num_thousands': False, 'axis_units': False,
    'grid_show': True, 'grid_color': '#022E67', 'grid_alpha': 0.6, 'grid_width': 0.8, 'grid_style': "Solid",
    'date_labels': "Auto",
    # Bar and line colors come from the Weather Impact 2.0 palette (CHART_PALETTE); shaded bands keep IEM's colors for now
    # Running Total vs Normal (IEM #172)
    'rt_input': "Running totals", 'rt_obs_color': '#59C8FF', 'rt_norm_color': '#022E67',
    'rt_show_envelope': True, 'rt_env_color': '#D2B48C', 'rt_env_alpha': 1.0,
    'rt_show_extremes': True, 'rt_high_color': '#285DA3', 'rt_low_color': '#FF6B6B',
    'rt_show_fill': False, 'rt_surplus_color': '#2E9E4F', 'rt_deficit_color': '#B5651D', 'rt_fill_alpha': 0.35,
    'rt_callout': False,
    # Record & Normal Band (IEM #113)
    'rb_band_style': "Layered", 'rb_style': "Lines", 'rb_bar_color': '#285DA3', 'rb_high_color': '#FF6B6B',
    'rb_low_color': '#59C8FF', 'rb_normal_color': '#B4DAB3', 'rb_rec_high_color': '#F2C2A7',
    'rb_rec_low_color': '#BBBBE2', 'rb_record_color': '#4A5260', 'rb_band_alpha': 1.0, 'rb_record_lines': True,
    'rb_rec_high_line': '#FF6B6B', 'rb_rec_low_line': '#285DA3', 'rb_mark_records': True, 'rb_mark_shape': "Dot",
    'rb_mark_color': '#FFD633', 'rb_callout': False,
    # Year Ranking (IEM #107 / #189)
    'yr_order': "Sorted", 'yr_rank_dir': "Highest", 'yr_style': "Bars", 'yr_top_n': 0, 'yr_word': "highest",
    'yr_highlight': "", 'yr_color': '#285DA3', 'yr_hl_color': '#59C8FF', 'yr_avg_line': True,
    'yr_avg_color': '#022E67', 'yr_avg_label': False, 'yr_trend': False, 'yr_trend_color': '#FFD633',
    'yr_callout': False, 'yr_orient': "Vertical",
    # Range Bars (floating bars, IEM #10 style)
    'rg_orient': "Horizontal", 'rg_color': '#2ECC71', 'rg_hl_color': '#59C8FF', 'rg_highlight': "",
    'rg_labels': "None", 'rg_avg_lines': True, 'rg_avg_color': '#022E67', 'rg_last_n': 30, 'rg_callout': False,
    'bar_orient': "Vertical",
}

# Station-data (IEM) panel choices; saved with projects so the data can be fetched again
TODAY = date.today()
RT_STARTS = {"Jan 1": (1, 1), "Jul 1": (7, 1), "Oct 1": (10, 1)}
SEASONS = {"Winter (Dec–Feb)": ((12, 1), (2, 28)), "Spring (Mar–May)": ((3, 1), (5, 31)),
           "Summer (Jun–Aug)": ((6, 1), (8, 31)), "Fall (Sep–Nov)": ((9, 1), (11, 30))}
RB_MODES = ["Full year", "Month", "Date range"]
YR_PERIODS = ["Year to date", "Full year", "Month", "Season", "Custom dates"]
# "NCEI 1991–2020" always means NCEI's official normals (what the NWS climate report uses); never an approximation
NORMAL_PERIODS = {"NCEI 1991–2020": "ncei", "Full record": None}
IEM_FALLBACK_NOTE = "IEM 1991–2020 station averages (not official NCEI normals)"
MONTHS = list(month_name)[1:]
iem_defaults = {
    'iem_state': "OH", 'iem_station': "OHTCMH",  # Columbus Area, the home station
    'normal_period': "NCEI 1991–2020", 'normals_fallback': False,
    'rt_var': "Rain", 'rt_start': "Jan 1", 'rt_year': TODAY.year, 'rt_to_latest': True, 'rt_end': TODAY,
    'rt_extend': False,
    'rb_mode': "Full year", 'rb_month': MONTHS[TODAY.month - 1], 'rb_year': TODAY.year,
    'rb_range': (TODAY - timedelta(days=30), TODAY - timedelta(days=1)),
    'yr_var': "Total precipitation", 'yr_period': "Year to date", 'yr_month': MONTHS[TODAY.month - 1],
    'yr_season': list(SEASONS)[0], 'yr_custom': (date(TODAY.year, 1, 1), TODAY), 'yr_max_missing': 3,
    'rg_threshold': 32.0, 'rg_max_missing': 15,
}
# Internal counters, bumped to reset the data editor / uploaders; never saved to project files
internal_defaults = {'csv_uploader_key': 0, 'json_uploader_key': 0}

for key, val in {**state_defaults, **iem_defaults, **internal_defaults}.items():
    if key not in st.session_state: st.session_state[key] = val
for key in {**state_defaults, **iem_defaults}:
    # Re-assigning keeps widget-bound values alive while their widget is hidden (e.g. Line-only controls in Bar mode)
    st.session_state[key] = st.session_state[key]
if 'datasets' not in st.session_state:
    # One table per layout, so switching chart types never loses data
    st.session_state.datasets = {k: dio.sample_data(k) for k in dio.SCHEMAS}
    st.session_state.editor_keys = {k: 0 for k in dio.SCHEMAS}
    st.session_state.source_notes = {k: "Sample data" for k in dio.SCHEMAS}
    st.session_state.autoplot_mappings = {}
if 'table_kinds' not in st.session_state:
    st.session_state.table_kinds = {"Range Bars": "Date"}  # Whether each layout's table holds numbers or dates

# Allowed values for every widget-bound setting; shared by the widgets and project loading
LINE_COLOR_KEYS = ['last_c1', 'last_c2', 'highlight_color', 'rt_obs_color', 'rt_norm_color', 'rt_high_color', 'rt_low_color', 'rb_bar_color', 'rb_high_color', 'rb_low_color', 'rb_rec_high_line', 'rb_rec_low_line', 'rb_mark_color', 'yr_color', 'yr_hl_color', 'yr_avg_color', 'yr_trend_color', 'rg_color', 'rg_hl_color', 'rg_avg_color']
# Which colors each restricted setting may use; other color settings (shaded bands) are free for now
BAR_COLOR_KEYS = ['last_c1', 'last_c2', 'highlight_color', 'yr_color', 'yr_hl_color', 'rg_color', 'rg_hl_color']  # Can be gradients
PALETTE_SETS = {**{k: BAR_PALETTE if k in BAR_COLOR_KEYS else CHART_PALETTE for k in LINE_COLOR_KEYS}, 'grid_color': GRID_PALETTE}
MARKER_SYMBOLS = list(charts.MARKERS)
GRID_STYLES = charts.GRID_STYLES
CHOICES = {'chart_type': dio.CHART_TYPES, 'marker_symbol': MARKER_SYMBOLS,
           'num_decimals': ["Auto", "0", "1", "2", "3"], 'grid_style': list(GRID_STYLES), 'value_kind': ["Number", "Date"],
           'date_labels': ["Auto", "Month names", "Month + day", "Day numbers"], 'x_label_every': ["Auto", *charts.X_LABEL_STEPS],
           'rt_input': ["Running totals", "Daily amounts"], 'rb_style': ["Lines", "Bars"],
           'rb_band_style': ["Layered", "Simple"], 'rb_mark_shape': ["Dot", "Star"],
           'yr_order': ["Sorted", "By year"], 'yr_rank_dir': ["Highest", "Lowest"], 'yr_style': ["Bars", "Dots", "Line"],
           'bar_orient': ["Vertical", "Horizontal"], 'yr_orient': ["Vertical", "Horizontal"],
           'rg_orient': ["Horizontal", "Vertical"], 'rg_labels': ["None", "Ends", "Length"],
           'value_pos': ["End", "Inside"]}
RANGES = {
    'width': (100, 7680), 'height': (100, 7680), 'x_sz': (10, 100), 'y_sz': (10, 100),
    'value_sz': (5, 80), 'line_width': (1, 25), 'marker_size': (1, 50), 'x_rot': (-90, 90),
    'bar_gap': (0.0, 0.9), 'y_step': (0.01, 1e9), 'grid_alpha': (0.0, 1.0), 'grid_width': (0.5, 8.0),
    'rt_fill_alpha': (0.0, 1.0), 'rt_env_alpha': (0.0, 1.0), 'rb_band_alpha': (0.0, 1.0), 'yr_top_n': (0, 500),
    'rg_last_n': (0, 500),
}
COLOR_KEYS = ['last_c1', 'last_c2', 'highlight_color', 'grid_color', 'rt_obs_color', 'rt_norm_color',
              'rt_env_color', 'rt_high_color', 'rt_low_color', 'rt_surplus_color', 'rt_deficit_color',
              'rb_bar_color', 'rb_high_color', 'rb_low_color', 'rb_normal_color', 'rb_rec_high_color',
              'rb_rec_low_color', 'rb_record_color', 'rb_rec_high_line', 'rb_rec_low_line', 'rb_mark_color',
              'yr_color', 'yr_hl_color', 'yr_avg_color', 'yr_trend_color', 'rg_color', 'rg_hl_color', 'rg_avg_color']
TEXT_KEYS = {'num_prefix': 8, 'num_suffix': 8, 'yr_word': 20, 'yr_highlight': 12, 'rg_highlight': 40}  # Free-text settings and their max length

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
    if key in PALETTE_SETS:
        return val.upper() if isinstance(val, str) and val.upper() in PALETTE_SETS[key].values() else None
    if key in COLOR_KEYS:
        return val if isinstance(val, str) and re.fullmatch(r'#[0-9A-Fa-f]{6}', val) else None
    if key == 'highlight_idx':
        return val if val == "None" or (isinstance(val, int) and not isinstance(val, bool) and val >= 0) else None
    if isinstance(state_defaults.get(key), bool):
        return val if isinstance(val, bool) else None
    return None

def active_key():
    return dio.schema_key(st.session_state.chart_type)

# --- 2. CACHED DATA ACCESS ---
@st.cache_data(ttl=24 * 3600, show_spinner="Loading station list from IEM…")
def load_stations(state):
    return iem.fetch_stations(state)

@st.cache_data(ttl=6 * 3600, show_spinner="Downloading the station's daily history from IEM…")
def load_daily(station, state):
    return iem.fetch_daily(station, state)

@st.cache_data(ttl=24 * 3600, show_spinner="Getting the official NCEI 1991–2020 normals from IEM…")
def load_ncei(station, state, ncei_id):
    return iem.fetch_ncei_normals(station, state, ncei_id)

@st.cache_data(ttl=6 * 3600, show_spinner="Getting the autoplot data from IEM…")
def load_autoplot(csv_url):
    num = int(re.search(r"/plot/(\d+)/", csv_url).group(1))
    meta = iem.autoplot_meta(num)
    if not meta["data"]:
        raise iem.IEMError(f"Autoplot #{num} ({meta['title']}) doesn't offer its data for download.")
    return meta["title"], iem.fetch_autoplot_csv(csv_url)

@st.cache_data(max_entries=20, show_spinner=False)
def render_chart(df, s, txt_col):
    return charts.render(df, s, txt_col)

# --- 3. CALLBACKS ---
def set_preset_color(target_key, color_hex):
    """Native callback to update color instantly without double-reruns."""
    st.session_state[target_key] = color_hex

RANK_WORD_PAIRS = [("highest", "lowest"), ("wettest", "driest"), ("snowiest", "least snowy"), ("warmest", "coldest"),
                   ("latest", "earliest")]

def flip_rank_word():
    """Switching Highest/Lowest swaps a standard ranking word for its opposite (wettest <-> driest)."""
    ss = st.session_state
    for hi, lo in RANK_WORD_PAIRS:
        if ss.yr_word in (hi, lo):
            ss.yr_word = hi if ss.yr_rank_dir == "Highest" else lo
            return

def set_value_kind(key, kind):
    """Show the `key` table's values as numbers or as dates, with suitable defaults for dates."""
    ss = st.session_state
    ss.table_kinds[key] = kind
    if kind == "Date":
        ss.y_start_zero = False
        if key == "Year Ranking":
            ss.yr_word = "latest" if ss.yr_rank_dir == "Highest" else "earliest"
            ss.yr_order = "By year"
    elif ss.yr_word in ("latest", "earliest"):
        ss.yr_word = "highest"
    ss.value_kind = kind

def store_table(key, df, note, notes=(), ignored=()):
    """Replace the `key` table, reset its editor and say what happened."""
    st.session_state.datasets[key] = df
    st.session_state.editor_keys[key] += 1
    st.session_state.source_notes[key] = note
    set_value_kind(key, df.attrs.get("value_kind", "Number"))
    if key == "Running Total vs Normal":
        # Daily amounts (e.g. a NOWData month) go up and down; running totals never go down
        obs = df["Observed"].dropna()
        st.session_state.rt_input = "Daily amounts" if (obs.diff().dropna() < 0).any() else "Running totals"
    extra = list(notes) + ([f"ignored columns: {', '.join(ignored)}"] if ignored else [])
    rows = f"{len(df)} row{'s' if len(df) != 1 else ''}"
    st.toast(f"Loaded {rows}" + (f" ({'; '.join(extra)})" if extra else ""))

def load_raw(raw, note):
    """Map a raw table (paste or file) onto the current chart type's columns. Returns False if unusable."""
    key = active_key()
    if raw.shape[1] < 2:
        st.error(f"The data needs at least 2 columns. Expected: {', '.join(dio.columns(key))}.")
        return False
    try:
        mapped, ignored = dio.map_columns(raw, key)
        df, notes = dio.normalize(mapped, key)
    except Exception as e:  # Unexpected layouts get a message instead of crashing the app
        st.error(f"Couldn't make sense of that data. Expected columns: {', '.join(dio.columns(key))}. Details: {e}")
        return False
    if df.empty:
        st.error(f"No rows of data found. Expected columns: {', '.join(dio.columns(key))}.")
        return False
    store_table(key, df, note, notes, ignored)
    return True

def handle_upload():
    f = st.session_state[f"csv_uploader_{st.session_state.csv_uploader_key}"]
    if not f: return
    try:
        if f.name.lower().endswith('.csv'):
            text = f.getvalue().decode("utf-8-sig", errors="replace")
            text = "\n".join(line for line in text.splitlines() if not line.startswith("#"))  # IEM comment lines
            raw = pd.read_csv(io.StringIO(text), dtype=str, keep_default_na=False)
        else:
            raw = pd.read_excel(f)
    except Exception as e:
        st.error(f"Couldn't read '{f.name}'. Make sure it's a valid CSV or Excel (.xlsx) file. Details: {e}")
        return
    if load_raw(raw, f"File: {f.name}"):
        st.session_state.csv_uploader_key += 1  # Clear the uploader so the same file can be imported again

def handle_paste():
    text = st.session_state.paste_text
    if not text.strip():
        st.error("Paste some cells first.")
        return
    try:
        raw = dio.parse_pasted(text)
    except Exception as e:
        st.error(f"Couldn't read the pasted data. Details: {e}")
        return
    if load_raw(raw, "Pasted data"):
        st.session_state.paste_text = ""

def handle_json():
    f = st.session_state[f"json_uploader_{st.session_state.json_uploader_key}"]
    if not f: return
    try:
        p = json.load(f)
        if 'datasets' in p:  # Version 2: one table per layout
            tables = {k: dio.normalize(pd.DataFrame(p['datasets'][k]), k)[0] for k in dio.SCHEMAS if k in p['datasets']}
        else:  # Version 1: a single Label / Value 1 / Value 2 table
            tables = {"Basic": dio.normalize(pd.DataFrame(p['data']), "Basic")[0]}
    except Exception as e:
        st.error(f"Couldn't load project file '{f.name}'. It may be corrupted. Details: {e}")
        return
    for k, df in tables.items():
        st.session_state.datasets[k] = df
        st.session_state.editor_keys[k] += 1
        st.session_state.source_notes[k] = str(p.get('source_notes', {}).get(k, f"Project: {f.name}"))[:200]
    settings = p.get('settings') if isinstance(p.get('settings'), dict) else {}
    old_order = {"Highest first": "Highest", "Lowest first": "Lowest"}.get(settings.get('yr_order'))
    if old_order:  # Earlier versions combined sort order and rank direction
        settings['yr_order'], settings['yr_rank_dir'] = "Sorted", old_order
    if 'y_step' in settings and 'y_auto' not in settings:
        settings['y_auto'] = False  # Older projects chose their Y interval by hand
    snapped = snap_settings(settings, PALETTE_SETS)  # Older projects: off-palette colors snap to the closest
    if snapped:
        st.toast("Colors outside the Weather Impact 2.0 palette were changed to the closest palette color: "
                 + ", ".join(snapped))
    # Only load known keys with valid values; anything else keeps its current setting
    for k, v in settings.items():
        if k not in state_defaults: continue
        safe_val = sanitize_setting(k, v)
        if safe_val is not None: st.session_state[k] = safe_val
    for k, v in (p.get('iem_query') or {}).items():
        if k == 'normal_period' and v == "1991–2020":
            v = "NCEI 1991–2020"  # Earlier versions' 1991–2020 setting; it now always means the official normals
        if k == 'normals_fallback' and isinstance(v, bool):
            st.session_state[k] = v
        elif k in ('iem_state', 'normal_period', 'rt_var', 'rt_start', 'rb_mode', 'rb_month', 'yr_var', 'yr_period',
                 'yr_month', 'yr_season') and isinstance(v, str) and v in iem_choices(k):
            st.session_state[k] = v
        elif k == 'iem_station' and isinstance(v, str) and re.fullmatch(r"[A-Z0-9]{3,10}", v):
            st.session_state[k] = v
    kinds = p.get('table_kinds') if isinstance(p.get('table_kinds'), dict) else {}
    st.session_state.table_kinds = {k: v for k, v in kinds.items() if k in dio.SCHEMAS and v in CHOICES['value_kind']}
    st.session_state.table_kinds.setdefault(active_key(), st.session_state.value_kind)
    if isinstance(p.get('autoplot_mappings'), dict):
        st.session_state.autoplot_mappings.update({str(n): {str(a): str(b) for a, b in m.items()}
                                                   for n, m in p['autoplot_mappings'].items() if isinstance(m, dict)})
    st.session_state.json_uploader_key += 1
    st.toast(f"Loaded project '{f.name}'")

def commit_table():
    """Keep the on-screen table's edits when switching chart types (the editor forgets them once hidden)."""
    k, df = st.session_state.get('_current_table', (None, None))
    if k is not None:
        st.session_state.datasets[k] = df
        st.session_state.editor_keys[k] += 1
    # Numbers or dates follow the table now on screen
    new_key = active_key()
    st.session_state.value_kind = st.session_state.table_kinds.get(new_key, "Number")

def change_value_kind():
    """Switching Numbers/Dates keeps the table's edits and redraws it in the new form."""
    k, df = st.session_state.get('_current_table', (None, None))
    if k is not None:
        st.session_state.datasets[k] = df
        st.session_state.editor_keys[k] += 1
    st.session_state.table_kinds[active_key()] = st.session_state.value_kind

def iem_choices(key):
    return {'iem_state': iem.STATES, 'normal_period': list(NORMAL_PERIODS), 'rt_var': ["Rain", "Snow"],
            'rt_start': list(RT_STARTS), 'rb_mode': RB_MODES, 'rb_month': MONTHS,
            'yr_var': list(iem.RANK_VARS), 'yr_period': YR_PERIODS, 'yr_month': MONTHS,
            'yr_season': list(SEASONS)}[key]

def unit_defaults(kind):
    """Number format suited to the data that was just loaded."""
    fmt = {"precip": ('"', "2"), "snow": ('"', "1"), "temp": ("°", "0")}[kind]
    st.session_state.num_suffix, st.session_state.num_decimals = fmt

def build_from_iem(daily, station_label, ncei_id="", use_iem_normals=False):
    """Compute the active preset's table from the station's daily record.

    With "NCEI 1991–2020" chosen, the official NCEI normals are required. If they can't be had, nothing is built
    and the problem is shown with an offer to use IEM's 1991–2020 station averages (`use_iem_normals`) instead.
    """
    ss = st.session_state
    ct = ss.chart_type
    ss.normals_problem = None
    ncei, normal_years, notes_extra = None, None, []
    normals = "full-record averages"
    if ct != "Year Ranking" and NORMAL_PERIODS[ss.normal_period] == "ncei":
        if use_iem_normals:
            normal_years, normals = (1991, 2020), IEM_FALLBACK_NOTE
            notes_extra = ["using IEM station averages, not official NCEI normals"]
            ss.normals_fallback = True
        else:
            try:
                ncei = load_ncei(ss.iem_station, ss.iem_state, ncei_id)
            except iem.NormalsUnavailable as e:
                # Remember which request failed so the offer only shows for it
                ss.normals_problem = (ss.iem_station, ct, str(e))
                return
            normals = f"NCEI 1991–2020 normals ({ncei.attrs.get('ncei_id', ncei_id)}, via IEM)"
            ss.normals_fallback = False
    span = f"{daily.index.min().year}–{daily.index.max().year}"
    try:
        if ct == "Running Total vs Normal":
            var = "precip" if ss.rt_var == "Rain" else "snow"
            m, d = RT_STARTS[ss.rt_start]
            df, info = iem.running_total(daily, var, ss.rt_year, m, d, None if ss.rt_to_latest else ss.rt_end,
                                         normal_years, ss.rt_extend, ncei=ncei)
            unit_defaults(var)
            ss.y_start_zero = True
            notes = [f"{info['missing_days']} missing days counted as 0"] if info['missing_days'] else []
            note = f"IEM · {station_label} · {ss.rt_var.lower()} {info['season']} · {normals}"
            if info['highest']:
                unit = ss.num_suffix
                word = ("wettest", "driest") if var == "precip" else ("snowiest", "least snowy")
                note += (f" · {word[0]}: {info['highest'][0]} ({info['highest'][1]}{unit}), "
                         f"{word[1]}: {info['lowest'][0]} ({info['lowest'][1]}{unit}) of {info['years']} years")
        elif ct == "Record & Normal Band":
            if ss.rb_mode == "Month":
                mi = MONTHS.index(ss.rb_month) + 1
                start, end = date(ss.rb_year, mi, 1), date(ss.rb_year, mi, monthrange(ss.rb_year, mi)[1])
            elif ss.rb_mode == "Full year":
                start, end = date(ss.rb_year, 1, 1), date(ss.rb_year, 12, 31)
            else:
                start, end = ss.rb_range if len(ss.rb_range) == 2 else (ss.rb_range[0], ss.rb_range[0])
            if start > daily.index.max().date():
                st.error("There's no data for that period yet.")
                return
            # Normals and records cover the whole period; actual highs/lows stop at the latest data (like IEM #113)
            df, info = iem.record_band(daily, start, end, normal_years, ncei=ncei)
            unit_defaults("temp")
            if (end - start).days > 62:
                ss.rb_style = "Bars"  # Daily high-low bars read best over long periods, as in IEM #113
            missing = int(df.loc[df["Date"] <= daily.index.max(), ["Actual High", "Actual Low"]].isna().any(axis=1).sum())
            notes = [f"{missing} days with missing temperatures"] if missing else []
            shown = "–".join(sorted({str(start.year), str(end.year)}))
            note = f"IEM · {station_label} · records {span}, not counting {shown} · {normals}"
        elif ct == "Range Bars":
            thr = float(ss.rg_threshold)
            # A low equal to the threshold counts (32° is a freeze), as the NWS defines it
            df, info = iem.freeze_seasons(daily, thr, strictly_below=False, max_missing=int(ss.rg_max_missing))
            ss.y_start_zero = False
            ss.rg_highlight = df["Label"].iloc[-1] if len(df) else ""
            skipped = info['skipped_years']
            notes = [f"left out {len(skipped)} year{'s' if len(skipped) != 1 else ''} with more than "
                     f"{ss.rg_max_missing} missing lows"] if skipped else []
            if len(df) and pd.isna(df["End"].iloc[-1]):
                notes.append(f"{df['Label'].iloc[-1]} has no fall freeze yet")
            note = f"IEM · {station_label} · growing season: last spring / first fall low ≤ {thr:g}° · {span}"
        else:
            start_md, end_md, label = ranking_window(daily)
            df, info = iem.yearly_values(daily, ss.yr_var, start_md, end_md, int(ss.yr_max_missing))
            col = iem.RANK_VARS[ss.yr_var][0]
            unit_defaults("temp" if col in ("high", "low", "avg") else col)
            if col in ("high", "low", "avg"): ss.num_decimals = "1"
            ss.y_start_zero = col not in ("high", "low", "avg")
            words = {"precip": ("wettest", "driest"), "snow": ("snowiest", "least snowy")}.get(col, ("warmest", "coldest"))
            ss.yr_word = words[ss.yr_rank_dir != "Highest"]
            ss.yr_highlight = ""
            ss.yr_order = "By year"  # What IEM shows (#107); "Sorted" is a sidebar click away
            skipped = info['skipped_years']
            notes = [f"left out {len(skipped)} year{'s' if len(skipped) != 1 else ''} with more than "
                     f"{ss.yr_max_missing} missing days"] if skipped else []
            note = f"IEM · {station_label} · {ss.yr_var.lower()}, {label} · {span}"
            if skipped and (df.empty or skipped[-1] > df["Year"].iloc[-1]):
                # The most recent period is the one people usually want; never drop it silently
                note += (f" · ⚠️ {skipped[-1]} is left out: more than {ss.yr_max_missing} days of missing data "
                         "(raise the allowance under the station data to include it)")
    except iem.IEMError as e:
        st.error(str(e))
        return
    store_table(dio.schema_key(ct), df, note, notes + notes_extra)

def ranking_window(daily):
    """(start (M, D), end (M, D), label) for the Year Ranking period choice."""
    ss = st.session_state
    last = daily.index.max()
    if ss.yr_period == "Year to date":
        return (1, 1), (last.month, last.day), f"Jan 1–{last:%b} {last.day}"
    if ss.yr_period == "Full year":
        return (1, 1), (12, 31), "full year"
    if ss.yr_period == "Month":
        mi = MONTHS.index(ss.yr_month) + 1
        return (mi, 1), (mi, 28 if mi == 2 else monthrange(2001, mi)[1]), ss.yr_month
    if ss.yr_period == "Season":
        s, e = SEASONS[ss.yr_season]
        return s, e, ss.yr_season.split(" (")[0].lower()
    start, end = ss.yr_custom if len(ss.yr_custom) == 2 else (ss.yr_custom[0], ss.yr_custom[0])
    end_md = (2, 28) if (end.month, end.day) == (2, 29) else (end.month, end.day)
    start_md = (3, 1) if (start.month, start.day) == (2, 29) else (start.month, start.day)
    return start_md, end_md, f"{start:%b} {start.day}–{end:%b} {end.day}"

def apply_autoplot(num, title, raw, targets):
    key = active_key()
    mapping = {t: st.session_state[f"ap_map_{num}_{t}"] for t in targets}
    chosen = {t: src for t, src in mapping.items() if src != "(none)"}
    if len(chosen) < 2:
        st.error("Pick a column for at least the first two fields.")
        return
    df, notes = dio.normalize(pd.DataFrame({t: raw[src] for t, src in chosen.items()}), key)
    st.session_state.autoplot_mappings[str(num)] = chosen
    store_table(key, df, f"IEM autoplot #{num}: {title}", notes)

# --- 4. CHART TYPE & DATA INPUT ---
def chart_type_label(c):
    return {"Running Total vs Normal": "★ Running Total", "Record & Normal Band": "★ Record Band",
            "Year Ranking": "★ Year Ranking", "Range Bars": "★ Range Bars"}.get(c, c)

ct = st.session_state.chart_type
key = active_key()
is_preset = ct in dio.PRESET_TYPES
# Chart type decides which table and options appear, so it sits above the data rather than in the styling sidebar
st.radio("Chart Type", dio.CHART_TYPES, key='chart_type', format_func=chart_type_label, horizontal=True,
         on_change=commit_table, help="★ Presets are climate charts that can pull station data from IEM.")
st.caption(dio.DESCRIPTIONS[ct])
st.subheader("Data Input")

if is_preset:
    with st.expander("🛰️ Station data from the Iowa Environmental Mesonet (IEM)", expanded=True):
        cs, cn = st.columns([1, 3])
        cs.selectbox("State", iem.STATES, key='iem_state')
        stations, daily, ncei_ids = None, None, {}
        try:
            stations = load_stations(st.session_state.iem_state)
        except iem.IEMError as e:
            st.error(str(e))
        if stations is not None:
            ids = stations["id"].tolist()
            labels = dict(zip(stations["id"], stations["label"]))
            ncei_ids = dict(zip(stations["id"], stations["ncei91"]))
            if st.session_state.iem_station not in ids: st.session_state.iem_station = None
            cn.selectbox("Station", ids, key='iem_station', format_func=lambda i: labels.get(i, i),
                         placeholder="Choose a station (type to search)",
                         help="'Area' stations are the long-term threaded records for a city.")
        if st.session_state.iem_station:
            try:
                daily = load_daily(st.session_state.iem_station, st.session_state.iem_state)
            except iem.IEMError as e:
                st.error(str(e))
        if daily is not None and not daily.empty:
            first, last = daily.index.min().date(), daily.index.max().date()
            station_label = f"{daily.attrs.get('station_name') or st.session_state.iem_station} ({st.session_state.iem_station})"
            st.caption(f"{station_label}: daily data {first:%b} {first.day}, {first.year} – {last:%b} {last.day}, {last.year}")
            years = list(range(last.year, first.year - 1, -1))
            ss = st.session_state
            if ct == "Running Total vs Normal":
                c1, c2, c3 = st.columns(3)
                c1.radio("Variable", ["Rain", "Snow"], key='rt_var', horizontal=True)
                c2.selectbox("Season starts", list(RT_STARTS), key='rt_start',
                             help="Snow seasons usually start Jul 1; water years Oct 1.")
                if ss.rt_year not in years: ss.rt_year = years[0]
                start_month = RT_STARTS[ss.rt_start][0]
                c3.selectbox("Season", years, key='rt_year', format_func=lambda y: iem.season_label(y, start_month))
                c1, c2, c3 = st.columns(3)
                c1.checkbox("Through the latest data", key='rt_to_latest')
                if not ss.rt_to_latest:
                    ss.rt_end = min(max(ss.rt_end, first), last)
                    c2.date_input("Through", key='rt_end', min_value=first, max_value=last)
                c3.checkbox("Show the normal for the rest of the season", key='rt_extend')
                st.radio("Normal period", list(NORMAL_PERIODS), key='normal_period', horizontal=True)
            elif ct == "Record & Normal Band":
                c1, c2, c3 = st.columns(3)
                c1.radio("Period", RB_MODES, key='rb_mode')
                if ss.rb_mode == "Date range":
                    year_end = date(last.year, 12, 31)  # Normals and records can run past the latest data
                    ss.rb_range = tuple(min(max(d, first), year_end) for d in ss.rb_range)
                    c2.date_input("Dates", key='rb_range', min_value=first, max_value=year_end)
                else:
                    if ss.rb_mode == "Month": c2.selectbox("Month", MONTHS, key='rb_month')
                    if ss.rb_year not in years: ss.rb_year = years[0]
                    c3.selectbox("Year", years, key='rb_year')
                st.radio("Normal period", list(NORMAL_PERIODS), key='normal_period', horizontal=True,
                         help="IEM's #113 plot uses averages over the full record; pick Full record to match it.")
            elif ct == "Range Bars":
                c1, c2 = st.columns(2)
                c1.number_input("Freeze threshold (°F)", -40.0, 60.0, step=1.0, key='rg_threshold',
                                help="32° for a freeze, 28° for a hard freeze. Lows at the threshold count.")
                c2.number_input("Leave out years missing more than this many lows", 0, 90, key='rg_max_missing')
                st.caption("Builds the growing season for every year: the last spring low (Jan–Jun) and the first fall "
                           "low (Jul–Dec) at or below the threshold, e.g. 32° and below. Pick how many years to show "
                           "under ★ Preset Options.")
            else:
                c1, c2, c3 = st.columns(3)
                c1.selectbox("Variable", list(iem.RANK_VARS), key='yr_var')
                c2.selectbox("Period", YR_PERIODS, key='yr_period')
                if ss.yr_period == "Month":
                    c3.selectbox("Month", MONTHS, key='yr_month')
                elif ss.yr_period == "Season":
                    c3.selectbox("Season", list(SEASONS), key='yr_season')
                elif ss.yr_period == "Custom dates":
                    c3.date_input("Dates (the year is ignored)", key='yr_custom')
                st.number_input("Leave out years missing more than this many days", 0, 60, key='yr_max_missing')
            ncei_id = ncei_ids.get(ss.iem_station, "")
            st.button("📥 Use this station data", type="primary", on_click=build_from_iem, args=(daily, station_label, ncei_id))
            problem = ss.get('normals_problem')
            if problem and problem[:2] == (ss.iem_station, ct) and NORMAL_PERIODS[ss.normal_period] == "ncei":
                st.warning(f"{problem[2]} The chart wasn't changed. You can use IEM's averages of this station's own "
                           "1991–2020 data instead (close to, but not, the official NCEI normals), try again, "
                           "or choose Full record.")
                st.button("Use IEM 1991–2020 averages instead", on_click=build_from_iem,
                          args=(daily, station_label, ncei_id, True))

c1, c2 = st.columns(2)
with c1: st.file_uploader("📂 Import CSV/Excel", type=['csv', 'xlsx'], key=f"csv_uploader_{st.session_state.csv_uploader_key}", on_change=handle_upload)
with c2: st.file_uploader("💾 Load Project", type=['json'], key=f"json_uploader_{st.session_state.json_uploader_key}", on_change=handle_json)
with st.expander("📋 Paste from Excel / Google Sheets / xmACIS / NOWData"):
    st.text_area("Paste cells here", key="paste_text", height=150,
                 placeholder=f"Expected columns: {', '.join(dio.columns(key))}.\nA header row is optional; "
                             "T (trace) and M (missing) are understood.")
    st.button("Use pasted data", on_click=handle_paste)
with st.expander("🌐 Import from an IEM autoplot"):
    st.caption("Make a plot at [mesonet.agron.iastate.edu/plotting/auto](https://mesonet.agron.iastate.edu/plotting/auto/), "
               "copy the page address, and paste it here to restyle its data for Max.")
    ap_url = st.text_input("Autoplot page link", key="ap_url", placeholder="https://mesonet.agron.iastate.edu/plotting/auto/?q=189&…")
    if ap_url.strip():
        try:
            num, csv_url = iem.autoplot_csv_url(ap_url)
            title, raw = load_autoplot(csv_url)
        except iem.IEMError as e:
            st.error(str(e))
        else:
            st.caption(f"**#{num}: {title}** · {len(raw)} rows · columns: {', '.join(map(str, raw.columns))}")
            st.dataframe(raw.head(5), hide_index=True)
            targets = dio.columns(key)
            saved = st.session_state.autoplot_mappings.get(str(num), {})
            options = ["(none)"] + [str(c) for c in raw.columns]
            guess = dio.guess_autoplot_mapping(raw.rename(columns=str), key)
            for col, target in zip(st.columns(len(targets)), targets):
                default = saved.get(target)
                if default not in options: default = guess.get(target, "(none)")
                col.selectbox(target, options, index=options.index(default), key=f"ap_map_{num}_{target}")
            st.button("Use this autoplot data", on_click=apply_autoplot, args=(num, title, raw.rename(columns=str), targets))

cap, tmpl = st.columns([4, 1])
cap.caption(f"Columns: {', '.join(dio.columns(key))} · Source: {st.session_state.source_notes[key]}")
tmpl.download_button("Blank template (CSV)", dio.template_csv(key), file_name=f"{key.lower().replace(' ', '_').replace('&', 'and')}_template.csv",
                     mime="text/csv", width="stretch")

show_dates = st.session_state.value_kind == "Date"
table = st.session_state.datasets[key]
column_config = {}
for col, kind in dio.SCHEMAS[key]:
    if kind == "num" and show_dates:
        # Dates are stored as day of year; show and edit them as "Oct 18" (read back the same way as a paste)
        table = table.assign(**{col: table[col].map(
            lambda v: "" if pd.isna(v) or (key == "Basic" and v == 0) else dio.day_of_year_text(v))})
        column_config[col] = st.column_config.TextColumn(col, help='Dates, e.g. "Oct 18"')
    else:
        column_config[col] = (st.column_config.DateColumn(col, format="YYYY-MM-DD") if kind == "date"
                              else st.column_config.NumberColumn(col) if kind == "num" else st.column_config.TextColumn(col))
# The stored table is only the starting data; the editor keeps the edits itself, so its output is never fed back in
df_input = st.data_editor(
    table, num_rows="dynamic", width="stretch", hide_index=is_preset,
    key=f"editor_{key}_{st.session_state.editor_keys[key]}_{st.session_state.value_kind}", column_config=column_config)
df_clean, _ = dio.normalize(df_input, key)
st.session_state._current_table = (key, df_clean)

# --- 5. UI / SIDEBAR ---
def highlight_option_label(i, labels):
    """Show highlight choices by their label; add the row number when a label is blank or repeated."""
    if i == "None": return "None"
    label = labels[i].strip()
    if not label: return f"Row {i + 1}"
    return f"{label} (row {i + 1})" if labels.count(labels[i]) > 1 else label

def horizontal_chart():
    """Whether the current chart puts its categories on the left (so its values run along the bottom)."""
    ss = st.session_state
    return ((ss.chart_type == "Bar" and ss.bar_orient == "Horizontal")
            or (ss.chart_type == "Year Ranking" and ss.yr_orient == "Horizontal" and ss.yr_style != "Line")
            or (ss.chart_type == "Range Bars" and ss.rg_orient == "Horizontal"))

def palette_chiclets(label, target, options=CHART_PALETTE):
    """Choose a color by clicking one of a row of small color squares (named on hover; a ring marks the selection).

    Stores the hex in `target`. Gradients
    ("#END-#BASE") get a second row, lined up under the solid colors.
    """
    current = st.session_state[target]
    names = {h: n for n, h in {**BAR_PALETTE, **options}.items()}
    st.markdown(f"<div style='font-size:14px;margin-bottom:2px'>{label}: <b>{names.get(current, current)}</b></div>",
                unsafe_allow_html=True)
    css = []
    solids = [item for item in options.items() if item[1] not in GRADIENTS.values()]
    grads = [item for item in options.items() if item[1] in GRADIENTS.values()]
    cells = list(st.columns(len(solids), gap="small"))
    if grads: cells += st.columns(len(solids), gap="small")[:len(grads)]
    for i, (col, (name, hex_val)) in enumerate(zip(cells, solids + grads)):
        btn_key = f"chip_{target}_{i}"
        active = current == hex_val
        col.button("\u00a0", key=btn_key, help=f"{name} {hex_val.replace('-', ' to ')}" + (" (selected)" if active else ""),
                   width="stretch",
                   on_click=set_preset_color, args=(target, hex_val))
        ring = "box-shadow: 0 0 0 2px var(--st-background-color, #fff), 0 0 0 4px #FF4B4B;" if active else ""
        sel = f".st-key-{btn_key} button"
        ends = hex_val.split("-")  # A gradient's value end at the top, as on a vertical bar
        fill = f"linear-gradient(to bottom, {ends[0]}, {ends[1]})" if len(ends) == 2 else hex_val
        css.append(f"{sel}, {sel}:hover, {sel}:focus, {sel}:active {{ background: {fill} !important; "
                   f"border: 1px solid #6B7A8F; min-height: 26px; height: 26px; padding: 0; border-radius: 6px; {ring} }}"
                   f"{sel}:hover {{ border-color: #FF4B4B; }}")
    st.html(f"<style>{''.join(css)}</style>")

# Widgets are bound to session state via `key`, so each change applies on the first try
with st.sidebar:
    st.header("Graphic Config")
    if charts.load_fonts()[2]: st.caption("⚠️ Proxima Nova font files not found; using the default sans-serif font.")

    with st.expander("📐 Canvas & Chart", expanded=True):
        cw, ch = st.columns(2)
        cw.number_input("Width (px)", *RANGES['width'], step=10, key='width')
        ch.number_input("Height (px)", *RANGES['height'], step=10, key='height')
        if ct == "Line":
            st.slider("Line Thickness", *RANGES['line_width'], key='line_width')
            st.slider("Point Size", *RANGES['marker_size'], key='marker_size')
            st.selectbox("Marker Style", MARKER_SYMBOLS, key='marker_symbol')
        elif ct == "Bar":
            st.radio("Bar direction", CHOICES['bar_orient'], key='bar_orient', horizontal=True,
                     help="Horizontal suits named rows: rankings, cities, event types.")
            st.slider("Bar Spacing / Gap", *RANGES['bar_gap'], key='bar_gap')
        if not is_preset:
            st.checkbox("Show Second Series", key='show_v2')

    if is_preset:
        with st.expander("⭐ Preset Options", expanded=True):
            if ct == "Running Total vs Normal":
                st.radio("Table values are", CHOICES['rt_input'], key='rt_input', horizontal=True,
                         help="Daily amounts are added up for you.")
                st.slider("Line Thickness", *RANGES['line_width'], key='line_width')
                palette_chiclets("This year", 'rt_obs_color')
                palette_chiclets("Normal (dashed)", 'rt_norm_color')
                st.checkbox("Range of all years (shaded)", key='rt_show_envelope')
                if st.session_state.rt_show_envelope:
                    a, b = st.columns(2)
                    a.color_picker("Range color", key='rt_env_color')
                    b.slider("Range opacity", *RANGES['rt_env_alpha'], key='rt_env_alpha')
                st.checkbox("Highest and lowest years", key='rt_show_extremes')
                if st.session_state.rt_show_extremes:
                    palette_chiclets("Highest year", 'rt_high_color')
                    palette_chiclets("Lowest year", 'rt_low_color')
                st.checkbox("Shade above/below normal", key='rt_show_fill')
                if st.session_state.rt_show_fill:
                    a, b = st.columns(2)
                    a.color_picker("Above normal", key='rt_surplus_color')
                    b.color_picker("Below normal", key='rt_deficit_color')
                    st.slider("Shading opacity", *RANGES['rt_fill_alpha'], key='rt_fill_alpha')
                st.checkbox('Call-out on chart (e.g. 2.31" above normal)', key='rt_callout')
            elif ct == "Record & Normal Band":
                st.radio("Band style", CHOICES['rb_band_style'], key='rb_band_style', horizontal=True,
                         help="Layered matches IEM: warm record-high band, normal range, cool record-low band.")
                a, b = st.columns(2)
                a.color_picker("Normal range", key='rb_normal_color')
                if st.session_state.rb_band_style == "Layered":
                    b.color_picker("Record-high band", key='rb_rec_high_color')
                    a.color_picker("Record-low band", key='rb_rec_low_color')
                else:
                    b.color_picker("Record band", key='rb_record_color')
                st.slider("Band opacity", *RANGES['rb_band_alpha'], key='rb_band_alpha')
                if st.session_state.rb_band_style == "Layered":
                    st.checkbox("Record lines", key='rb_record_lines')
                    if st.session_state.rb_record_lines:
                        palette_chiclets("Record-high line", 'rb_rec_high_line')
                        palette_chiclets("Record-low line", 'rb_rec_low_line')
                st.radio("Show actual temperatures as", CHOICES['rb_style'], key='rb_style', horizontal=True)
                if st.session_state.rb_style == "Bars":
                    palette_chiclets("Bars", 'rb_bar_color')
                else:
                    palette_chiclets("Actual high", 'rb_high_color')
                    palette_chiclets("Actual low", 'rb_low_color')
                    st.slider("Line Thickness", *RANGES['line_width'], key='line_width')
                st.checkbox("Mark new records", key='rb_mark_records')
                if st.session_state.rb_mark_records:
                    st.radio("Marker", CHOICES['rb_mark_shape'], key='rb_mark_shape', horizontal=True)
                    palette_chiclets("Marker color", 'rb_mark_color')
                    st.slider("Marker size", *RANGES['marker_size'], key='marker_size')
                st.checkbox("Call-out on chart (e.g. 2 record highs)", key='rb_callout')
            elif ct == "Year Ranking":
                year_opts = [""] + sorted(df_clean.dropna(subset=["Value"])["Year"].astype(str).unique(), reverse=True)
                if st.session_state.yr_highlight not in year_opts: st.session_state.yr_highlight = ""
                st.selectbox("Highlight year", year_opts, key='yr_highlight', format_func=lambda y: y or "Latest year")
                st.radio("Order", CHOICES['yr_order'], key='yr_order', horizontal=True,
                         help="By year matches IEM's plots; Sorted lines the years up from highest (or lowest).")
                st.radio("Rank from", CHOICES['yr_rank_dir'], key='yr_rank_dir', horizontal=True, on_change=flip_rank_word,
                         help="Highest for wettest/warmest/snowiest/latest; Lowest for driest/coldest/earliest.")
                st.text_input("Ranking word", key='yr_word', max_chars=TEXT_KEYS['yr_word'],
                              help='Used in the rank, e.g. "3rd wettest of 130 years".')
                st.radio("Style", CHOICES['yr_style'], key='yr_style', horizontal=True)
                if st.session_state.yr_style != "Line":
                    st.radio("Bar direction", CHOICES['yr_orient'], key='yr_orient', horizontal=True,
                             help="Horizontal reads best for a sorted top-N list.")
                if st.session_state.yr_style != "Bars": st.slider("Dot size", *RANGES['marker_size'], key='marker_size')
                if st.session_state.yr_order == "Sorted":
                    st.number_input("Show top N years (0 = all)", *RANGES['yr_top_n'], key='yr_top_n',
                                    help="The highlighted year is always shown.")
                yr_options = BAR_PALETTE if st.session_state.yr_style == "Bars" else CHART_PALETTE
                palette_chiclets("Year color", 'yr_color', yr_options)
                palette_chiclets("Highlight color", 'yr_hl_color', yr_options)
                st.checkbox("Average line", key='yr_avg_line')
                if st.session_state.yr_avg_line:
                    palette_chiclets("Average color", 'yr_avg_color')
                    st.checkbox("Label the average", key='yr_avg_label')
                if st.session_state.yr_order == "By year":
                    if st.session_state.yr_orient == "Horizontal" and st.session_state.yr_style != "Line":
                        st.caption("The trend line is available with vertical bars.")
                    else:
                        st.checkbox("Trend line", key='yr_trend', help="A straight-line fit, labeled with its change per decade.")
                        if st.session_state.yr_trend: palette_chiclets("Trend color", 'yr_trend_color')
                st.checkbox("Call-out on chart (e.g. 3rd wettest of 130 years)", key='yr_callout')
            if ct == "Range Bars":
                labels_rg = df_clean.dropna(subset=["Start"])["Label"].astype(str).tolist()
                opts = [""] + list(reversed(labels_rg))
                if st.session_state.rg_highlight not in opts: st.session_state.rg_highlight = ""
                st.selectbox("Highlight row", opts, key='rg_highlight', format_func=lambda l: l or "None")
                st.radio("Bar direction", CHOICES['rg_orient'], key='rg_orient', horizontal=True)
                st.number_input("Show the last N rows (0 = all)", *RANGES['rg_last_n'], key='rg_last_n',
                                help="More than about 40 bars get too thin to read on air.")
                st.radio("Labels on bars", CHOICES['rg_labels'], key='rg_labels', horizontal=True,
                         help='Ends: "Apr 15 · Oct 30". Length: "198 days" (or the difference for numbers).')
                palette_chiclets("Bar color", 'rg_color', BAR_PALETTE)
                palette_chiclets("Highlight color", 'rg_hl_color', BAR_PALETTE)
                st.checkbox("Average start and end lines", key='rg_avg_lines')
                if st.session_state.rg_avg_lines: palette_chiclets("Average line color", 'rg_avg_color')
                st.checkbox("Call-out on chart (e.g. 198 days)", key='rg_callout')

    with st.expander("🎨 Colors", expanded=not is_preset):
        st.caption("Weather Impact 2.0 palette only. Text, axes, data labels and call-outs are WI Navy for Max's "
                   "white background.")
        if not is_preset:
            bar_options = BAR_PALETTE if ct == "Bar" else CHART_PALETTE  # Gradients are for bars only
            palette_chiclets("Series 1", 'last_c1', bar_options)
            if st.session_state.show_v2:
                palette_chiclets("Series 2", 'last_c2', bar_options)
            st.divider()
            labels = df_clean["Label"].tolist()
            h_opts = ["None"] + list(range(len(labels)))
            if st.session_state.highlight_idx not in h_opts: st.session_state.highlight_idx = "None"
            st.selectbox("Highlight Point", h_opts, key='highlight_idx', format_func=lambda i: highlight_option_label(i, labels),
                         help="Draws one point (Series 1) in the highlight color.")
            palette_chiclets("Highlight", 'highlight_color', bar_options)
        else:
            st.caption("Chart colors for presets are in Preset Options.")

    with st.expander("🔢 Data Labels & Number Format"):
        if ct in dio.DATED_TYPES:
            st.caption("Value labels aren't drawn on this chart; the font settings apply to the call-out.")
        elif ct == "Range Bars":
            st.caption('Choose the labels on the bars under ★ Preset Options ("Labels on bars").')
        else:
            st.checkbox("Show Values on Chart", key='show_values')
            if st.session_state.show_values and (ct == "Bar" or (ct == "Year Ranking" and st.session_state.yr_style == "Bars")):
                st.radio("Label position", CHOICES['value_pos'], key='value_pos', horizontal=True,
                         format_func=lambda k: {"End": "Past the end", "Inside": "Inside the bar"}[k],
                         help="Inside labels are White or WI Navy, whichever reads better on the bar. A bar too short "
                              "for its label gets it past the end.")
        st.slider("Data Label Font Size", *RANGES['value_sz'], key='value_sz')
        st.checkbox("Data Labels Bold", key='value_bold')
        st.radio("Values are", CHOICES['value_kind'], key='value_kind', horizontal=True,
                 format_func=lambda k: {"Number": "Numbers", "Date": "Dates"}[k],
                 on_change=change_value_kind,
                 help="Dates (e.g. a last-frost date per year) show as \"Oct 18\"; picked automatically when you paste "
                      "or import data.")
        if st.session_state.value_kind == "Date":
            st.caption("Dates ignore decimal places, prefix and suffix.")
        st.selectbox("Decimal Places", CHOICES['num_decimals'], key='num_decimals',
                     help="Auto shows up to 3 decimals and drops trailing zeros.")
        cp, cs = st.columns(2)
        cp.text_input("Prefix", key='num_prefix', max_chars=TEXT_KEYS['num_prefix'], placeholder="e.g. $")
        cs.text_input("Suffix", key='num_suffix', max_chars=TEXT_KEYS['num_suffix'], placeholder='e.g. ° % " mph')
        st.checkbox("Thousands Separator (1,000)", key='num_thousands')
        st.checkbox("Prefix/Suffix on Y Axis Too", key='axis_units')

    with st.expander("📏 Axes"):
        st.checkbox("Automatic Y Interval", key='y_auto', help="Picks a round interval with about 10 or fewer steps.")
        if not st.session_state.y_auto:
            st.number_input("Y Interval", min_value=RANGES['y_step'][0], max_value=RANGES['y_step'][1], key='y_step')
        if ct != "Record & Normal Band":
            st.checkbox("Force Y Axis to Start at 0", key='y_start_zero')
        st.slider("Y Axis Value Size", *RANGES['y_sz'], key='y_sz')
        st.checkbox("Y Axis Values Bold", key='y_bold')
        if ct in dio.DATED_TYPES:
            st.selectbox("Date Labels", CHOICES['date_labels'], key='date_labels',
                         help="Auto uses month names for periods longer than about two months.")
        if ct not in dio.DATED_TYPES:
            st.selectbox("X Axis Labels", CHOICES['x_label_every'], key='x_label_every',
                         help="Which bars get a label. The year options pick labels by their year "
                              "(e.g. 1880, 1885, 1890); a highlighted bar always keeps its label. If labels "
                              "crowd, pick a wider spacing, a smaller X label size, or rotate them.")
        st.slider("X Axis Label Size", *RANGES['x_sz'], key='x_sz')
        st.checkbox("X Axis Labels Bold", key='x_bold')
        st.slider("X Label Rotation (Degrees)", *RANGES['x_rot'], key='x_rot')
        if not horizontal_chart():
            st.checkbox("Navy strip behind X axis labels", key='x_label_band',
                        help="White labels on a WI Navy strip under the chart, as on Weather Impact bar graphics.")

    with st.expander("▦ Gridlines"):
        st.checkbox("Show Gridlines", key='grid_show')
        if st.session_state.grid_show:
            palette_chiclets("Gridline color", 'grid_color', GRID_PALETTE)
            st.slider("Opacity", *RANGES['grid_alpha'], key='grid_alpha')
            st.slider("Thickness", *RANGES['grid_width'], step=0.1, key='grid_width')
            st.selectbox("Style", list(GRID_STYLES), key='grid_style')

txt_col = TEXT_COLORS["WI Navy"]  # Max's backgrounds are white

# --- 6. PREVIEW BACKGROUND ---
st.markdown("""<style> [data-testid="stImage"] { background-color: white; border-radius: 10px; padding: 20px; } </style>""", unsafe_allow_html=True)

# --- 7. PREVIEW & EXPORT ---
settings = {k: st.session_state[k] for k in state_defaults}
if df_clean.empty:
    st.info("Add some data to the table to see the chart.")
    st.stop()
png_bytes, y_step_used = render_chart(df_clean, settings, txt_col)
info_line = charts.summary(df_clean, settings)
if info_line:
    st.markdown(f"**{info_line}**")
    st.caption(f"Source: {st.session_state.source_notes[key]}")
if not settings['y_auto'] and y_step_used > settings['y_step']:
    st.caption(f"⚠️ Y Interval {settings['y_step']:g} is too small for this data range; using {y_step_used:.3g} instead.")
st.image(png_bytes, width="stretch")

# Setup export downloads side-by-side
col_dl1, col_dl2 = st.columns(2)

with col_dl1:
    st.download_button("🚀 DOWNLOAD PNG", data=png_bytes, file_name=f"weather_graphic_{datetime.now().strftime('%H%M%S')}.png", mime="image/png", width="stretch")

with col_dl2:
    iem_query = {k: (v.isoformat() if isinstance(v, date) else [d.isoformat() for d in v] if isinstance(v, tuple) else v)
                 for k, v in ((k, st.session_state[k]) for k in iem_defaults)}
    datasets = {k: dio.to_records(df) for k, df in st.session_state.datasets.items()}
    datasets[key] = dio.to_records(df_clean)  # Include unsaved table edits for the chart on screen
    project_json = json.dumps({"version": 2, "chart_type": ct, "settings": settings, "datasets": datasets,
                               "source_notes": st.session_state.source_notes, "iem_query": iem_query,
                               "autoplot_mappings": st.session_state.autoplot_mappings,
                               "table_kinds": st.session_state.table_kinds})
    st.download_button("💾 SAVE PROJECT (JSON)", data=project_json, file_name="max_graph_project.json", mime="application/json", width="stretch")
