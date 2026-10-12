"""Table layouts per chart type, plus parsing/cleanup for pasted, imported and loaded data. No Streamlit here."""
import csv
import io
import re
from datetime import date

import numpy as np
import pandas as pd

BASIC_TYPES = ["Bar", "Line"]
PRESET_TYPES = ["Running Total vs Normal", "Record & Normal Band", "Year Ranking"]
CHART_TYPES = BASIC_TYPES + PRESET_TYPES
DATED_TYPES = ["Running Total vs Normal", "Record & Normal Band"]

# Column layouts. Bar and Line share the "Basic" table.
SCHEMAS = {
    "Basic": [("Label", "text"), ("Value 1", "num"), ("Value 2", "num")],
    # The last four are optional context (IEM #172 style): the highest/lowest years' totals and the range of all years
    "Running Total vs Normal": [("Date", "date"), ("Observed", "num"), ("Normal", "num"), ("Highest Year", "num"),
                                ("Lowest Year", "num"), ("Range Max", "num"), ("Range Min", "num")],
    "Record & Normal Band": [("Date", "date"), ("Actual High", "num"), ("Actual Low", "num"), ("Normal High", "num"),
                             ("Normal Low", "num"), ("Record High", "num"), ("Record Low", "num")],
    "Year Ranking": [("Year", "text"), ("Value", "num")],
}

DESCRIPTIONS = {
    "Bar": "Open-ended bar chart: any labels with one or two series of values.",
    "Line": "Open-ended line chart: any labels with one or two series of values.",
    "Running Total vs Normal": "Season-to-date rain or snow against normal, with the range and extremes of all years "
                               "(like IEM autoplot #172).",
    "Record & Normal Band": "Daily highs and lows over the normal and record ranges, with new records marked "
                            "(like IEM autoplot #113).",
    "Year Ranking": "Every year on record with one year highlighted and ranked (like IEM autoplots #107 / #189).",
}


def _norm(name):
    return re.sub(r"[^a-z0-9]", "", str(name).lower())


# Header names (normalized) that map to each column, as used by IEM, xmACIS, NOWData and spreadsheets
ALIASES = {
    "Date": ["date", "day", "valid", "obdate"],
    "Observed": ["observed", "obs", "accum", "accumulated", "precipitation", "precip", "pcpn", "snowfall", "snow",
                 "newsnow", "total", "actual"],
    "Normal": ["normal", "normals", "climo", "climatology", "average", "avg", "mean", "cprecip", "csnow"],
    "Actual High": ["high", "max", "maxt", "maxtemp", "maxtemperature", "maxtmpf", "hi"],
    "Actual Low": ["low", "min", "mint", "mintemp", "mintemperature", "mintmpf", "lo"],
    "Normal High": ["normalmax", "normalmaxt", "avghigh", "averagehigh", "climohigh", "highavg", "highnormal", "nmlhigh"],
    "Normal Low": ["normalmin", "normalmint", "avglow", "averagelow", "climolow", "lowavg", "lownormal", "nmllow"],
    "Record High": ["recordmax", "recordmaxt", "highmax", "maxhigh", "recordhightemp", "rechigh"],
    "Record Low": ["recordmin", "recordmint", "lowmin", "minlow", "recordlowtemp", "reclow"],
    "Highest Year": ["highestyear", "wettestyear", "maxyear"],
    "Lowest Year": ["lowestyear", "driestyear", "minyear"],
    "Range Max": ["rangemax", "envelopemax", "maxaccum"],
    "Range Min": ["rangemin", "envelopemin", "minaccum"],
    "Year": ["year", "yr", "season", "years", "binyear", "endingdate", "enddate", "ending"],
    "Value": ["value", "data", "total", "precipitation", "precip", "pcpn", "snowfall", "snow", "avg", "average",
              "mean", "avgtemp", "avghigh", "avglow", "avghightemp", "avglowtemp"],
}

MISSING_CODES = {"m", "", "-", "--", "na", "n/a", "nan", "none", "missing"}
TRACE_CODES = {"t", "trace", "tr"}
_NUMBER_LIKE = re.compile(r"^[\-−+]?[\d,]*\.?\d+\s*[A-Za-z°%\"']{0,3}$")


def schema_key(chart_type):
    return "Basic" if chart_type in BASIC_TYPES else chart_type


def columns(key):
    return [c for c, _ in SCHEMAS[key]]


# --- Number formatting ---

def format_number(v, s, units=True, signed=False):
    """Format a value per the Number Format settings; `units` adds the prefix/suffix, `signed` adds '+' to positives."""
    sep = ',' if s['num_thousands'] else ''
    if s['num_decimals'] == "Auto":
        txt = f"{v:{sep}.3f}".rstrip('0').rstrip('.')
    else:
        txt = f"{v:{sep}.{int(s['num_decimals'])}f}"
    if not txt.lstrip('-').strip('0.,'): txt = txt.lstrip('-')  # No "-0" from rounding
    if signed and not txt.startswith('-') and txt.strip('0.,'): txt = '+' + txt
    txt = txt.replace('-', '−')  # Typographic minus sign
    return f"{s['num_prefix']}{txt}{s['num_suffix']}" if units else txt


# --- Cleaning ---

def clean_numbers(series, keep_missing):
    """Numbers from messy cells: strips units/flags (75°, 1,280, 0.25A), T = trace -> 0, M = missing.

    Missing cells stay blank when `keep_missing`, else become 0. Returns (numbers, counts dict).
    """
    counts = {"trace": 0, "missing": 0, "bad": 0}
    if pd.api.types.is_numeric_dtype(series):
        nums = series.astype(float)
        counts["missing"] = int(nums.isna().sum())
    else:
        raw = series.astype(object).where(series.notna(), "")
        txt = raw.astype(str).str.strip()
        low = txt.str.lower()
        is_trace = low.isin(TRACE_CODES)
        is_missing = low.isin(MISSING_CODES)
        stripped = txt.str.replace('−', '-').str.replace(r'[^0-9.\-]', '', regex=True)
        nums = pd.to_numeric(stripped.mask(stripped == ''), errors='coerce')
        nums[is_trace] = 0.0
        counts["trace"] = int(is_trace.sum())
        counts["missing"] = int((low == "m").sum())
        counts["bad"] = int((nums.isna() & ~is_missing & ~is_trace).sum())
    if not keep_missing:
        nums = nums.fillna(0.0)
    return nums.astype(float), counts


def parse_dates(series):
    """Dates from common formats (2025-10-01, 10/1/2025, Oct 1, Excel dates). A date with no year takes the
    year most common among the other rows (or this year)."""
    if pd.api.types.is_datetime64_any_dtype(series):
        return series.dt.normalize()
    txt = series.astype(object).where(series.notna(), "").astype(str).str.strip()
    has_year = txt.str.contains(r"\d{4}") | txt.str.fullmatch(r"\d{1,2}/\d{1,2}/\d{2}")
    parsed = pd.to_datetime(txt.where(has_year), errors="coerce", format="mixed")
    if (~has_year & (txt != "")).any():
        years = parsed.dropna().dt.year
        year = int(years.mode().iloc[0]) if len(years) else date.today().year
        no_year = ~has_year & (txt != "")
        parsed[no_year] = pd.to_datetime(txt[no_year] + f" {year}", errors="coerce", format="mixed")
    return parsed.dt.normalize()


def normalize(df, key):
    """Coerce a table to the `key` layout. Returns (df, notes): notes are short user-facing remarks."""
    df = df.copy()
    notes = []
    for col, kind in SCHEMAS[key]:
        if col not in df.columns:
            df[col] = "" if kind == "text" else (pd.NaT if kind == "date" else np.nan)
    df = df[columns(key)].reset_index(drop=True)
    totals = {"trace": 0, "missing": 0, "bad": 0}
    for col, kind in SCHEMAS[key]:
        if kind == "text":
            df[col] = df[col].astype(object).where(df[col].notna(), "").astype(str).str.strip()
            df[col] = df[col].str.replace(r'[ T]00:00:00$', '', regex=True)  # Excel / IEM dates read as text
            if col == "Year":  # xmACIS ranked lists give an ending date (2012-12-31); keep the year
                df[col] = df[col].str.replace(r'^(\d{4})-\d{2}-\d{2}$', r'\1', regex=True).str.replace(r'\.0$', '', regex=True)
        elif kind == "date":
            df[col] = parse_dates(df[col])
        else:
            df[col], c = clean_numbers(df[col], keep_missing=key != "Basic")
            for k in totals: totals[k] += c[k]
    # Drop rows that aren't data: unreadable dates, or summary rows like "Sum"/"Mean" in a Year column
    first, kind = SCHEMAS[key][0]
    if kind == "date":
        bad = df[first].isna()
    elif key == "Year Ranking":
        bad = ~df[first].str.contains(r"\d", regex=True)
    else:
        bad = pd.Series(False, index=df.index)
    if bad.any():
        notes.append(f"dropped {_plural(int(bad.sum()), 'row')} that weren't data (summary rows or unreadable dates)")
        df = df[~bad].reset_index(drop=True)
    if totals["missing"] and key != "Basic": notes.append(f"{_plural(totals['missing'], 'missing value')} (M) left blank")
    if totals["trace"]: notes.append(f"{_plural(totals['trace'], 'trace value')} (T) counted as 0")
    if totals["bad"]: notes.append(f"{_plural(totals['bad'], 'non-numeric value')} "
                                   + ("set to 0" if key == "Basic" else "left blank"))
    if key == "Year Ranking" and df["Year"].duplicated().any():
        notes.append("some years appear more than once")
    return df, notes


def _plural(n, word):
    return f"{n} {word}{'s' if n != 1 else ''}"


# --- Column matching ---

def guess_mapping(cols, key):
    """{layout column: source column} by header name, falling back to position.

    Basic tables always use position (first column = labels, next two = values), as before.
    """
    cols = list(cols)
    wanted = columns(key)
    if key != "Basic":
        mapping, used = {}, set()
        # Exact names first, then aliases, so "Record High" beats a plain "High"
        for pass_names in (lambda c: [_norm(c)], lambda c: ALIASES.get(c, [])):
            for target in wanted:
                if target in mapping: continue
                for src in cols:
                    if src not in used and _norm(src) in pass_names(target):
                        mapping[target] = src
                        used.add(src)
                        break
        if mapping:
            return mapping
    return dict(zip(wanted, cols))


# Number columns that are date parts or counts, so they make poor chart values
DATE_PART_COLUMNS = {"month", "day", "year", "yr", "doy", "sday", "index", "row", "binyear", "dayofmonth", "years", "count"}


def guess_autoplot_mapping(raw, key):
    """Default column choices for an IEM autoplot table. For Basic charts: the first column as the label,
    then the first number columns that aren't date parts (so #113 gives valid / avg_high / max_high)."""
    if key != "Basic":
        return guess_mapping([str(c) for c in raw.columns], key)
    cols = [str(c) for c in raw.columns]
    values = [c for c in cols[1:] if _norm(c) not in DATE_PART_COLUMNS
              and pd.to_numeric(raw[c], errors="coerce").notna().mean() > 0.5]
    return dict(zip(columns(key), [cols[0]] + values[:2]))


def unique_names(names):
    """Column names made unique ("High", "High (2)") so each one picks out exactly one column."""
    seen, out = {}, []
    for name in (str(n).strip() or f"Column {i + 1}" for i, n in enumerate(names)):
        seen[name] = seen.get(name, 0) + 1
        out.append(name if seen[name] == 1 else f"{name} ({seen[name]})")
    return out


def map_columns(raw, key):
    """Pick the `key` layout's columns out of `raw`. Returns (df with layout columns, ignored source column names)."""
    raw = raw.set_axis(unique_names(raw.columns), axis=1)
    mapping = guess_mapping(raw.columns, key)
    out = pd.DataFrame({t: raw[src] for t, src in mapping.items()})
    return out, [str(c) for c in raw.columns if c not in mapping.values()]


def _data_like(cell):
    cell = str(cell).strip()
    if not cell: return False
    if cell.lower() in TRACE_CODES | MISSING_CODES - {""}: return True
    if _NUMBER_LIKE.match(cell): return True
    return bool(re.search(r"\d", cell)) and pd.notna(pd.to_datetime(cell, errors="coerce", format="mixed"))


def parse_pasted(text):
    """Cells copied from Excel/Sheets/NOWData (tab-separated) or CSV text -> DataFrame of strings.

    The first row is used as the header when none of its cells look like data.
    """
    text = text.strip("\n")
    sep = '\t' if '\t' in text else (';' if ';' in text and ',' not in text else ',')
    rows = [r for r in csv.reader(io.StringIO(text), delimiter=sep) if any(c.strip() for c in r)]
    # Rows can have different numbers of cells (e.g. extra cells past the header); pad them to the widest row
    width = max((len(r) for r in rows), default=0)
    df = pd.DataFrame([r + [""] * (width - len(r)) for r in rows], dtype=str)
    if df.empty:
        return df
    df = df.loc[:, ~(df == "").all()]  # Empty columns from trailing tabs
    if len(df) > 1 and df.shape[1] > 1 and not any(_data_like(c) for c in df.iloc[0]):
        header = unique_names(df.iloc[0])
        df = df.iloc[1:].reset_index(drop=True)
        df.columns = header
    else:
        df.columns = [f"Column {i + 1}" for i in range(df.shape[1])]
    return df


# --- Samples, templates, serialization ---

def sample_data(key):
    """Example data so each chart type shows something right away."""
    rng = np.random.default_rng(7)
    if key == "Basic":
        return pd.DataFrame({"Label": ["Mon", "Tue", "Wed", "Thu", "Fri"], "Value 1": [75.0, 80.0, 50.0, 60.0, 75.0],
                             "Value 2": [65.0, 70.0, 10.0, 52.0, 37.0]})
    if key == "Running Total vs Normal":
        dates = pd.date_range("2025-01-01", "2025-10-10")
        doy = dates.dayofyear.to_numpy()
        normal_daily = 0.06 + 0.12 * np.exp(-((doy - 170) / 60) ** 2)
        rain = np.where(rng.random(len(dates)) < 0.28, rng.gamma(0.9, 0.38, len(dates)), 0.0)
        years = [np.cumsum(np.where(rng.random(len(dates)) < 0.28, rng.gamma(0.9, 0.38 * f, len(dates)), 0.0))
                 for f in rng.uniform(0.5, 1.6, 40)]
        hist = np.array(years)
        return pd.DataFrame({"Date": dates, "Observed": np.round(np.cumsum(rain), 2),
                             "Normal": np.round(np.cumsum(normal_daily), 2),
                             "Highest Year": np.round(hist[hist[:, -1].argmax()], 2),
                             "Lowest Year": np.round(hist[hist[:, -1].argmin()], 2),
                             "Range Max": np.round(hist.max(axis=0), 2), "Range Min": np.round(hist.min(axis=0), 2)})
    if key == "Record & Normal Band":
        dates = pd.date_range("2025-07-01", "2025-07-31")
        t = np.arange(len(dates))
        nh, nl = 86 - 0.03 * t, 64 - 0.02 * t
        ah = np.round(nh + rng.normal(1.5, 5, len(t)))
        al = np.round(nl + rng.normal(1, 4, len(t)))
        rh = np.round(nh + 14 + rng.normal(0, 2, len(t)))
        rl = np.round(nl - 16 + rng.normal(0, 2, len(t)))
        ah[[8, 9]] = rh[[8, 9]] + [1, 0]  # A couple of record days
        return pd.DataFrame({"Date": dates, "Actual High": ah, "Actual Low": al, "Normal High": np.round(nh, 1),
                             "Normal Low": np.round(nl, 1), "Record High": rh, "Record Low": rl})
    years = np.arange(1990, 2026)
    return pd.DataFrame({"Year": years.astype(str), "Value": np.round(rng.normal(36, 6, len(years)), 2)})


def template_csv(key):
    return ",".join(columns(key)) + "\n"


def to_records(df):
    """JSON-safe rows (dates as ISO text, blanks as null)."""
    out = df.copy()
    for col in out.columns:
        if pd.api.types.is_datetime64_any_dtype(out[col]):
            out[col] = out[col].dt.strftime("%Y-%m-%d")
    out = out.astype(object).where(out.notna(), None)
    return out.to_dict(orient="records")
