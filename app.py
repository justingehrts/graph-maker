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

st.set_page_config(page_title="Max Graph Maker", page_icon="📊", layout="wide")

# --- 1. SETTINGS & SESSION STATE ---
# Chart settings: the master list for project files
state_defaults = {
    'last_c1': '#045EA8', 'last_c2': '#C80000', 'show_v2': False,
    'chart_type': "Bar", 'width': 1920, 'height': 1080,
    'text_choice': "White", 'x_sz': 28, 'y_sz': 28, 'y_step': 10.0, 'y_auto': True,
    'bar_gap': 0.22, 'y_start_zero': True, 'x_bold': True, 'y_bold': True,
    'show_values': False, 'value_sz': 24, 'value_bold': True,
    'highlight_idx': "None", 'highlight_color': '#FFD700',
    'line_width': 8, 'marker_size': 15, 'marker_symbol': 'Circle',
    'x_rot': 0,
    'num_decimals': "Auto", 'num_prefix': "", 'num_suffix': "", 'num_thousands': False, 'axis_units': False,
    'grid_show': True, 'grid_color': '#808080', 'grid_alpha': 0.3, 'grid_width': 0.8, 'grid_style': "Solid",
    'date_labels': "Auto",
    # Preset defaults follow IEM's autoplot colors, brightened only where a line would vanish on a dark background
    # Running Total vs Normal (IEM #172)
    'rt_input': "Running totals", 'rt_obs_color': '#FF2020', 'rt_norm_color': '#FFFFFF',
    'rt_show_envelope': True, 'rt_env_color': '#D2B48C', 'rt_env_alpha': 1.0,
    'rt_show_extremes': True, 'rt_high_color': '#3060FF', 'rt_low_color': '#A52A2A',
    'rt_show_fill': False, 'rt_surplus_color': '#2E9E4F', 'rt_deficit_color': '#B5651D', 'rt_fill_alpha': 0.35,
    'rt_callout': False,
    # Record & Normal Band (IEM #113)
    'rb_band_style': "Layered", 'rb_style': "Lines", 'rb_bar_color': '#775321', 'rb_high_color': '#E8483B',
    'rb_low_color': '#3FA9F5', 'rb_normal_color': '#B4DAB3', 'rb_rec_high_color': '#F2C2A7',
    'rb_rec_low_color': '#BBBBE2', 'rb_record_color': '#4A5260', 'rb_band_alpha': 1.0, 'rb_record_lines': True,
    'rb_rec_high_line': '#E8231B', 'rb_rec_low_line': '#2E2EA0', 'rb_mark_records': True, 'rb_mark_shape': "Dot",
    'rb_mark_color': '#FFD700', 'rb_callout': False,
    # Year Ranking (IEM #107 / #189)
    'yr_order': "Sorted", 'yr_rank_dir': "Highest", 'yr_style': "Bars", 'yr_top_n': 0, 'yr_word': "highest",
    'yr_highlight': "", 'yr_color': '#FF0000', 'yr_hl_color': '#00A000', 'yr_avg_line': True,
    'yr_avg_color': '#1F77B4', 'yr_avg_label': False, 'yr_trend': False, 'yr_trend_color': '#FFFFFF',
    'yr_callout': False,
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
    'iem_state': "IA", 'iem_station': None, 'normal_period': "NCEI 1991–2020", 'normals_fallback': False,
    'rt_var': "Rain", 'rt_start': "Jan 1", 'rt_year': TODAY.year, 'rt_to_latest': True, 'rt_end': TODAY,
    'rt_extend': False,
    'rb_mode': "Full year", 'rb_month': MONTHS[TODAY.month - 1], 'rb_year': TODAY.year,
    'rb_range': (TODAY - timedelta(days=30), TODAY - timedelta(days=1)),
    'yr_var': "Total precipitation", 'yr_period': "Year to date", 'yr_month': MONTHS[TODAY.month - 1],
    'yr_season': list(SEASONS)[0], 'yr_custom': (date(TODAY.year, 1, 1), TODAY), 'yr_max_missing': 3,
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

# Allowed values for every widget-bound setting; shared by the widgets and project loading
TEXT_COLORS = {"White": "white", "Black": "black", "Navy": "#022E67"}
MARKER_SYMBOLS = list(charts.MARKERS)
GRID_STYLES = charts.GRID_STYLES
CHOICES = {'chart_type': dio.CHART_TYPES, 'text_choice': list(TEXT_COLORS), 'marker_symbol': MARKER_SYMBOLS,
           'num_decimals': ["Auto", "0", "1", "2", "3"], 'grid_style': list(GRID_STYLES),
           'date_labels': ["Auto", "Month names", "Month + day", "Day numbers"],
           'rt_input': ["Running totals", "Daily amounts"], 'rb_style': ["Lines", "Bars"],
           'rb_band_style': ["Layered", "Simple"], 'rb_mark_shape': ["Dot", "Star"],
           'yr_order': ["Sorted", "By year"], 'yr_rank_dir': ["Highest", "Lowest"], 'yr_style': ["Bars", "Dots", "Line"]}
RANGES = {
    'width': (100, 7680), 'height': (100, 7680), 'x_sz': (10, 100), 'y_sz': (10, 100),
    'value_sz': (5, 80), 'line_width': (1, 25), 'marker_size': (1, 50), 'x_rot': (-90, 90),
    'bar_gap': (0.0, 0.9), 'y_step': (0.01, 1e9), 'grid_alpha': (0.0, 1.0), 'grid_width': (0.5, 8.0),
    'rt_fill_alpha': (0.0, 1.0), 'rt_env_alpha': (0.0, 1.0), 'rb_band_alpha': (0.0, 1.0), 'yr_top_n': (0, 500),
}
COLOR_KEYS = ['last_c1', 'last_c2', 'highlight_color', 'grid_color', 'rt_obs_color', 'rt_norm_color',
              'rt_env_color', 'rt_high_color', 'rt_low_color', 'rt_surplus_color', 'rt_deficit_color',
              'rb_bar_color', 'rb_high_color', 'rb_low_color', 'rb_normal_color', 'rb_rec_high_color',
              'rb_rec_low_color', 'rb_record_color', 'rb_rec_high_line', 'rb_rec_low_line', 'rb_mark_color',
              'yr_color', 'yr_hl_color', 'yr_avg_color', 'yr_trend_color']
TEXT_KEYS = {'num_prefix': 8, 'num_suffix': 8, 'yr_word': 20, 'yr_highlight': 12}  # Free-text settings and their max length
# Brand presets for the series colors: name -> hex
COLOR_PRESETS = {"Navy": "#022E67", "Blue": "#045EA8", "Red": "#C80000", "White": "#FFFFFF"}

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

def store_table(key, df, note, notes=(), ignored=()):
    """Replace the `key` table, reset its editor and say what happened."""
    st.session_state.datasets[key] = df
    st.session_state.editor_keys[key] += 1
    st.session_state.source_notes[key] = note
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
            "Year Ranking": "★ Year Ranking"}.get(c, c)

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
        stations, daily = None, None
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

column_config = {}
for col, kind in dio.SCHEMAS[key]:
    column_config[col] = (st.column_config.DateColumn(col, format="YYYY-MM-DD") if kind == "date"
                          else st.column_config.NumberColumn(col) if kind == "num" else st.column_config.TextColumn(col))
# The stored table is only the starting data; the editor keeps the edits itself, so its output is never fed back in
df_input = st.data_editor(
    st.session_state.datasets[key], num_rows="dynamic", width="stretch", hide_index=is_preset,
    key=f"editor_{key}_{st.session_state.editor_keys[key]}", column_config=column_config)
df_clean, _ = dio.normalize(df_input, key)
st.session_state._current_table = (key, df_input)

# --- 5. UI / SIDEBAR ---
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
        btn_key = f"{target}_{name.lower()}"
        active = st.session_state[target].upper() == hex_val
        col.button(name, key=btn_key, help=f"{name} {hex_val}" + (" (selected)" if active else ""), width="stretch",
                   on_click=set_preset_color, args=(target, hex_val))
        text = "#000000" if hex_val == "#FFFFFF" else "#FFFFFF"
        ring = "box-shadow: 0 0 0 2px var(--st-background-color, #fff), 0 0 0 4px #FF4B4B;" if active else ""
        css.append(f".st-key-{btn_key} button {{ background: {hex_val}; color: {text}; border: 1px solid #888; padding: 0 2px; {ring} }}"
                   f".st-key-{btn_key} button p {{ font-size: 0.75rem; font-weight: 600; }}")
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
            st.slider("Bar Spacing / Gap", *RANGES['bar_gap'], key='bar_gap')
        if not is_preset:
            st.checkbox("Show Second Series", key='show_v2')

    if is_preset:
        with st.expander("⭐ Preset Options", expanded=True):
            if ct == "Running Total vs Normal":
                st.radio("Table values are", CHOICES['rt_input'], key='rt_input', horizontal=True,
                         help="Daily amounts are added up for you.")
                st.slider("Line Thickness", *RANGES['line_width'], key='line_width')
                a, b = st.columns(2)
                a.color_picker("This year", key='rt_obs_color')
                b.color_picker("Normal (dashed)", key='rt_norm_color')
                st.checkbox("Range of all years (shaded)", key='rt_show_envelope')
                if st.session_state.rt_show_envelope:
                    a, b = st.columns(2)
                    a.color_picker("Range color", key='rt_env_color')
                    b.slider("Range opacity", *RANGES['rt_env_alpha'], key='rt_env_alpha')
                st.checkbox("Highest and lowest years", key='rt_show_extremes')
                if st.session_state.rt_show_extremes:
                    a, b = st.columns(2)
                    a.color_picker("Highest year", key='rt_high_color')
                    b.color_picker("Lowest year", key='rt_low_color')
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
                        a, b = st.columns(2)
                        a.color_picker("Record-high line", key='rb_rec_high_line')
                        b.color_picker("Record-low line", key='rb_rec_low_line')
                st.radio("Show actual temperatures as", CHOICES['rb_style'], key='rb_style', horizontal=True)
                a, b = st.columns(2)
                if st.session_state.rb_style == "Bars":
                    a.color_picker("Bars", key='rb_bar_color')
                else:
                    a.color_picker("Actual high", key='rb_high_color')
                    b.color_picker("Actual low", key='rb_low_color')
                    st.slider("Line Thickness", *RANGES['line_width'], key='line_width')
                st.checkbox("Mark new records", key='rb_mark_records')
                if st.session_state.rb_mark_records:
                    a, b = st.columns(2)
                    a.radio("Marker", CHOICES['rb_mark_shape'], key='rb_mark_shape', horizontal=True)
                    b.color_picker("Marker color", key='rb_mark_color')
                    st.slider("Marker size", *RANGES['marker_size'], key='marker_size')
                st.checkbox("Call-out on chart (e.g. 2 record highs)", key='rb_callout')
            else:
                year_opts = [""] + sorted(df_clean.dropna(subset=["Value"])["Year"].astype(str).unique(), reverse=True)
                if st.session_state.yr_highlight not in year_opts: st.session_state.yr_highlight = ""
                st.selectbox("Highlight year", year_opts, key='yr_highlight', format_func=lambda y: y or "Latest year")
                st.radio("Order", CHOICES['yr_order'], key='yr_order', horizontal=True,
                         help="By year matches IEM's plots; Sorted lines the years up from highest (or lowest).")
                st.radio("Rank from", CHOICES['yr_rank_dir'], key='yr_rank_dir', horizontal=True,
                         help="Highest for wettest/warmest/snowiest; Lowest for driest/coldest.")
                st.text_input("Ranking word", key='yr_word', max_chars=TEXT_KEYS['yr_word'],
                              help='Used in the rank, e.g. "3rd wettest of 130 years".')
                st.radio("Style", CHOICES['yr_style'], key='yr_style', horizontal=True)
                if st.session_state.yr_style != "Bars": st.slider("Dot size", *RANGES['marker_size'], key='marker_size')
                if st.session_state.yr_order == "Sorted":
                    st.number_input("Show top N years (0 = all)", *RANGES['yr_top_n'], key='yr_top_n',
                                    help="The highlighted year is always shown.")
                a, b = st.columns(2)
                a.color_picker("Year color", key='yr_color')
                b.color_picker("Highlight color", key='yr_hl_color')
                st.checkbox("Average line", key='yr_avg_line')
                if st.session_state.yr_avg_line:
                    a, b = st.columns(2)
                    a.color_picker("Average color", key='yr_avg_color')
                    b.checkbox("Label it", key='yr_avg_label')
                if st.session_state.yr_order == "By year":
                    st.checkbox("Trend line", key='yr_trend', help="A straight-line fit, labeled with its change per decade.")
                    if st.session_state.yr_trend: st.color_picker("Trend color", key='yr_trend_color')
                st.checkbox("Call-out on chart (e.g. 3rd wettest of 130 years)", key='yr_callout')

    with st.expander("🎨 Colors", expanded=not is_preset):
        st.selectbox("Text Color", list(TEXT_COLORS), key='text_choice')
        if not is_preset:
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
        else:
            st.caption("Chart colors for presets are in Preset Options.")

    with st.expander("🔢 Data Labels & Number Format"):
        if ct in dio.DATED_TYPES:
            st.caption("Value labels aren't drawn on this chart; the font settings apply to the call-out.")
        else:
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

# --- 6. PREVIEW CONTRAST CSS ---
preview_bg = "#262730" if txt_col == "white" else "white"
st.markdown(f"""<style> [data-testid="stImage"] {{ background-color: {preview_bg}; border-radius: 10px; padding: 20px; }} </style>""", unsafe_allow_html=True)

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
                               "autoplot_mappings": st.session_state.autoplot_mappings})
    st.download_button("💾 SAVE PROJECT (JSON)", data=project_json, file_name="max_graph_project.json", mime="application/json", width="stretch")
