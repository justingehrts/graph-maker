"""Iowa Environmental Mesonet (IEM) data access and climate calculations.

Plain pandas + requests (no Streamlit), so everything here can be tested directly.
"""
import io
import re
from datetime import date, timedelta
from urllib.parse import urlparse, parse_qsl

import pandas as pd
import requests

BASE = "https://mesonet.agron.iastate.edu"
TIMEOUT = 90
TRACE = 0.0001  # IEM stores a trace of precip/snow as 0.0001

STATES = ["AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA", "HI", "ID", "IL", "IN", "IA", "KS",
          "KY", "LA", "ME", "MD", "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ", "NM", "NY",
          "NC", "ND", "OH", "OK", "OR", "PA", "PR", "RI", "SC", "SD", "TN", "TX", "UT", "VT", "VA", "WA",
          "WV", "WI", "WY"]


class IEMError(Exception):
    """A user-facing problem getting data from IEM."""


class NormalsUnavailable(IEMError):
    """Official NCEI normals couldn't be had for a station (none assigned, or IEM didn't return them)."""


def _get(url, params=None):
    try:
        r = requests.get(url, params=params, timeout=TIMEOUT)
        r.raise_for_status()
        return r
    except requests.Timeout as e:
        raise IEMError("The Iowa Environmental Mesonet took too long to respond. Try again in a minute.") from e
    except requests.RequestException as e:
        raise IEMError(f"Couldn't get data from the Iowa Environmental Mesonet ({e.__class__.__name__}). "
                       "Check the connection and try again.") from e


# --- Stations & daily data ---

def fetch_stations(state):
    """Climate (COOP / threaded 'Area') stations for a state: id, name, county, begin year, label."""
    data = _get(f"{BASE}/api/1/network/{state}CLIMATE.json").json().get("data", [])
    df = pd.DataFrame(data)
    if df.empty:
        return pd.DataFrame(columns=["id", "name", "county", "begin", "ncei91", "label"])
    df["begin"] = pd.to_datetime(df.get("archive_begin"), errors="coerce").dt.year
    df["county"] = df.get("county").fillna("")
    df["ncei91"] = df["ncei91"].fillna("") if "ncei91" in df else ""  # NCEI 1991-2020 normals station IEM assigns
    df = df[df["online"].fillna(False)] if "online" in df else df
    df["label"] = df.apply(lambda r: f"{r['name']} ({r['id']})"
                           + (f" · {r['county']} Co." if r["county"] else "")
                           + (f" · since {int(r['begin'])}" if pd.notna(r["begin"]) else ""), axis=1)
    return df[["id", "name", "county", "begin", "ncei91", "label"]].sort_values("name").reset_index(drop=True)


def parse_daily_csv(text):
    """Parse IEM's COOP download (coop.py) into a date-indexed frame of high, low, precip, snow."""
    df = pd.read_csv(io.StringIO(text), comment="#", na_values=["M"], skipinitialspace=True)
    if "day" not in df.columns:
        raise IEMError("IEM returned no daily data for this station.")
    df["date"] = pd.to_datetime(df["day"], format="%Y/%m/%d")
    out = df.set_index("date")[["high", "low", "precip", "snow"]].apply(pd.to_numeric, errors="coerce")
    out.attrs["station_name"] = str(df["station_name"].iloc[0]) if len(df) else ""
    return out.sort_index()


def fetch_daily(station, state, end=None):
    """Full period-of-record daily data for one climate station (one request)."""
    end = end or date.today()
    params = {"network": f"{state}CLIMATE", "stations": station, "year1": 1850, "month1": 1, "day1": 1,
              "year2": end.year, "month2": end.month, "day2": end.day, "vars[]": ["high", "low", "precip", "snow"],
              "what": "view", "delim": "comma", "gis": "no"}
    df = parse_daily_csv(_get(f"{BASE}/cgi-bin/request/coop.py", params).text)
    # Trim trailing days with no data yet (today, or a station that hasn't reported)
    has_data = df.notna().any(axis=1)
    return df.loc[: has_data[has_data].index.max()] if has_data.any() else df


def fetch_ncei_normals(station, state, ncei_id):
    """Official NCEI 1991-2020 daily normals for a station, by calendar day (MMDD, including 0229), via IEM.

    Precipitation and snowfall come from autoplot #172's data (cprecip / csnow), highs and lows from #99's
    (avg_high / avg_low, which IEM documents as the official NCEI 1991-2020 dataset). `ncei_id` is the normals
    station IEM assigns (the station list's ncei91 field). Raises NormalsUnavailable if they can't be had.
    """
    if not ncei_id:
        raise NormalsUnavailable("No official NCEI 1991–2020 normals are assigned to this station.")
    net = f"network:{state}CLIMATE::station:{station}"
    try:
        accum = pd.read_csv(io.StringIO(_get(f"{BASE}/plotting/auto/plot/172/{net}::var:precip::sdate:0101.csv").text))
        temps = pd.read_csv(io.StringIO(_get(f"{BASE}/plotting/auto/plot/99/{net}::year:2024.csv").text))  # Leap year: all 366 days
    except IEMError as e:
        raise NormalsUnavailable(f"Couldn't get the NCEI normals from IEM: {e}") from e
    except Exception as e:
        raise NormalsUnavailable("IEM returned the NCEI normals in an unexpected format.") from e
    try:
        # The normals repeat every year; take each calendar day's value from any year that has it
        precip = accum.assign(md=accum["sday"].astype(str).str.zfill(4)).groupby("md")[["cprecip", "csnow"]].first()
        hl = temps.assign(md=temps["sday"].astype(str).str.zfill(4)).set_index("md")[["avg_high", "avg_low"]]
        normals = pd.concat([precip, hl], axis=1).set_axis(["precip", "snow", "high", "low"], axis=1)
    except KeyError as e:
        raise NormalsUnavailable("IEM's data for this station doesn't include NCEI normals.") from e
    if len(normals) < 366 or normals.isna().any().any():
        raise NormalsUnavailable("IEM's NCEI normals for this station are incomplete.")
    normals.attrs["ncei_id"] = ncei_id
    return normals.sort_index()


# --- Shared helpers ---

def _sday(index):
    return index.strftime("%m%d")


def _normal_mask(daily, normal_years):
    return slice(None) if normal_years is None else (daily.index.year >= normal_years[0]) & (daily.index.year <= normal_years[1])


def season_window(year, start_month, start_day, end=None, data_end=None):
    """(start, end) dates for the 1-year season beginning on start_month/start_day of `year`."""
    start = date(year, start_month, start_day)
    season_end = date(year + 1, start_month, start_day) - timedelta(days=1)
    stop = min(d for d in [season_end, end, data_end] if d is not None)
    return start, stop, season_end


def season_label(year, start_month):
    return str(year) if start_month == 1 else f"{year}-{str(year + 1)[-2:]}"


# --- Running total vs normal ---

def season_history(amounts, start_month, start_day, n_days, max_missing=3):
    """Running totals for the first `n_days` of the season in every year with a complete window.

    Returns a DataFrame indexed by day of season (0..n_days-1), one column per starting year.
    Years missing more than `max_missing` days are left out, as IEM does.
    """
    first, last = amounts.index.min(), amounts.index.max()
    cols = {}
    for y in range(first.year - 1, last.year + 1):
        try:
            start = pd.Timestamp(y, start_month, start_day)
        except ValueError:
            continue
        end = start + pd.Timedelta(days=n_days - 1)
        if start < first or end > last:
            continue
        vals = amounts.reindex(pd.date_range(start, end))
        if vals.isna().sum() > max_missing:
            continue
        cols[y] = vals.fillna(0).cumsum().to_numpy()
    return pd.DataFrame(cols)


def running_total(daily, var, year, start_month=1, start_day=1, end=None, normal_years=(1991, 2020),
                  extend_normal=False, max_missing=3, ncei=None):
    """Observed and normal running totals of `var` ('precip' or 'snow') for one season, plus the history
    IEM's autoplot #172 shows: the range of every other year's running total, and the years with the
    highest and lowest totals.

    Returns (DataFrame[Date, Observed, Normal, Highest Year, Lowest Year, Range Max, Range Min], info).
    Missing days add nothing to the total. The normal is the cumulative sum of the daily normals: the official
    NCEI ones when `ncei` (from fetch_ncei_normals) is given, else the station's average for each calendar day
    over `normal_years` (None = the full record).
    """
    data_end = daily.index.max().date()
    start, stop, season_end = season_window(year, start_month, start_day, end, data_end)
    if stop < start:
        raise IEMError(f"No data yet for the {season_label(year, start_month)} season.")
    dates = pd.date_range(start, season_end if extend_normal else stop)
    digits = 2 if var == "precip" else 1  # Precision people quote: 12.43" of rain, 23.5" of snow
    amounts = daily[var].mask(daily[var] == TRACE, 0.0)  # A trace adds nothing to a total
    if ncei is not None:
        climo = ncei[var]
    else:
        norm_daily = amounts[_normal_mask(daily, normal_years)]
        climo = norm_daily.groupby(_sday(norm_daily.index)).mean()
    normal = climo.reindex(_sday(dates)).fillna(0).cumsum().round(digits).to_numpy()
    obs_daily = amounts.reindex(pd.date_range(start, stop))
    observed = obs_daily.fillna(0).cumsum().round(digits).reindex(dates).to_numpy()
    out = pd.DataFrame({"Date": dates, "Observed": observed, "Normal": normal})
    info = {"missing_days": int(obs_daily.isna().sum()), "start": start, "end": stop,
            "season": season_label(year, start_month), "highest": None, "lowest": None}
    history = season_history(amounts, start_month, start_day, len(dates), max_missing).drop(columns=[year], errors="ignore")
    if not history.empty:
        finals = history.iloc[-1]
        hi_year, lo_year = int(finals.idxmax()), int(finals.idxmin())
        out["Highest Year"] = history[hi_year].round(digits).to_numpy()
        out["Lowest Year"] = history[lo_year].round(digits).to_numpy()
        out["Range Max"] = history.max(axis=1).round(digits).to_numpy()
        out["Range Min"] = history.min(axis=1).round(digits).to_numpy()
        info.update(highest=(season_label(hi_year, start_month), round(float(finals[hi_year]), digits)),
                    lowest=(season_label(lo_year, start_month), round(float(finals[lo_year]), digits)),
                    years=len(history.columns))
    return out, info


# --- Daily records & normals band ---

def daily_climatology(daily, normal_years=(1991, 2020), exclude_years=(), smooth_days=15):
    """Per calendar day (MMDD): smoothed normal high/low and record high/low (with year), from the daily record.

    Records ignore `exclude_years` so a chart can show whether the displayed period set new records.
    Normals use a centered `smooth_days` rolling mean around the calendar (single-day averages are noisy).
    """
    keep = ~daily.index.year.isin(list(exclude_years))
    rec = daily[keep]
    by_day = rec.groupby(_sday(rec.index))
    record_high, record_low = by_day["high"].max(), by_day["low"].min()
    rh_year = rec["high"].groupby(_sday(rec.index)).apply(lambda s: _record_years(s, s.max()))
    rl_year = rec["low"].groupby(_sday(rec.index)).apply(lambda s: _record_years(s, s.min()))
    norm = daily[_normal_mask(daily, normal_years)]
    means = norm.groupby(_sday(norm.index))[["high", "low"]].mean()
    if smooth_days > 1:
        # Smooth around the year: skip Feb 29 (too few years), wrap Dec->Jan, then fill Feb 29 from its neighbors
        regular = means.drop(index="0229", errors="ignore")
        pad = smooth_days
        wrapped = pd.concat([regular.iloc[-pad:], regular, regular.iloc[:pad]])
        smooth = wrapped.rolling(smooth_days, center=True, min_periods=1).mean().iloc[pad:-pad]
        if "0229" in means.index:
            smooth.loc["0229"] = (smooth.loc["0228"] + smooth.loc["0301"]) / 2
        means = smooth.sort_index()
    return pd.DataFrame({"normal_high": means["high"], "normal_low": means["low"], "record_high": record_high,
                         "record_high_year": rh_year, "record_low": record_low, "record_low_year": rl_year})


def _record_years(s, value):
    return " ".join(str(y) for y in sorted(s.index.year[s == value].unique())) if pd.notna(value) else ""


def record_band(daily, start, end, normal_years=(1991, 2020), ncei=None):
    """Actual high/low with normal and (prior) record high/low for each day from start to end.

    Normals are the official NCEI ones when `ncei` is given, else the station's averages over `normal_years`.
    """
    dates = pd.date_range(start, end)
    climo = daily_climatology(daily, normal_years, exclude_years=sorted(set(dates.year)))
    if ncei is not None:
        climo["normal_high"], climo["normal_low"] = ncei["high"].reindex(climo.index), ncei["low"].reindex(climo.index)
    c = climo.reindex(_sday(dates))
    actual = daily.reindex(dates)
    out = pd.DataFrame({"Date": dates, "Actual High": actual["high"].to_numpy(), "Actual Low": actual["low"].to_numpy(),
                        "Normal High": c["normal_high"].round(1).to_numpy(), "Normal Low": c["normal_low"].round(1).to_numpy(),
                        "Record High": c["record_high"].to_numpy(), "Record Low": c["record_low"].to_numpy()})
    return out, {"missing_days": int(actual[["high", "low"]].isna().any(axis=1).sum())}


def record_counts(df):
    """New or tied records in a Record & Normal Band table: (record highs, record lows)."""
    highs = (df["Actual High"] >= df["Record High"]) & df["Actual High"].notna() & df["Record High"].notna()
    lows = (df["Actual Low"] <= df["Record Low"]) & df["Actual Low"].notna() & df["Record Low"].notna()
    return highs, lows


# --- Year ranking ---

RANK_VARS = {
    "Total precipitation": ("precip", "sum"),
    "Total snowfall": ("snow", "sum"),
    "Average high": ("high", "mean"),
    "Average low": ("low", "mean"),
    "Average temperature": ("avg", "mean"),
}


def yearly_values(daily, rank_var, start_md, end_md, max_missing=3):
    """One value per year for the window start_md..end_md (MM, DD tuples; may cross Dec 31).

    Years missing more than `max_missing` days (or not yet complete) are left out.
    Returns (DataFrame[Year, Value], info).
    """
    col, how = RANK_VARS[rank_var]
    data = daily.assign(avg=(daily["high"] + daily["low"]) / 2)[col]
    if how == "sum":
        data = data.mask(data == TRACE, 0.0)  # A trace adds nothing to a total
    crosses = end_md < start_md
    data_end = daily.index.max()
    rows, skipped = [], []
    for y in range(daily.index.year.min(), daily.index.year.max() + 1):
        try:
            start = pd.Timestamp(y, *start_md)
            end = pd.Timestamp(y + 1 if crosses else y, *end_md)
        except ValueError:  # Feb 29 in a non-leap year
            continue
        if start < daily.index.min() or end > data_end:
            continue
        vals = data.loc[start:end]
        missing = (end - start).days + 1 - int(vals.notna().sum())
        label = f"{y}-{str(y + 1)[-2:]}" if crosses else str(y)
        if missing > max_missing:
            skipped.append(label)
            continue
        rows.append((label, round(vals.sum() if how == "sum" else vals.mean(), 2)))
    out = pd.DataFrame(rows, columns=["Year", "Value"])
    return out, {"skipped_years": skipped}


def ordinal(n):
    return f"{n}{'th' if 11 <= n % 100 <= 13 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


def rank_of(df, year_label, highest_first=True):
    """Rank of `year_label` in a Year Ranking table: (rank, tied, count) or None when absent/blank."""
    valid = df.dropna(subset=["Value"])
    match = valid[valid["Year"].astype(str) == str(year_label)]
    if match.empty:
        return None
    v = match["Value"].iloc[0]
    better = (valid["Value"] > v) if highest_first else (valid["Value"] < v)
    rank = int(better.sum()) + 1
    tied = int((valid["Value"] == v).sum()) > 1
    return rank, tied, len(valid)


# --- Autoplot import ---

_AUTOPLOT_PATH = re.compile(r"/plotting/auto/plot/(\d+)/(.*?)(?:\.(?:png|csv|xlsx|txt|json|svg|pdf))?$")


def autoplot_csv_url(page_url):
    """Turn an IEM autoplot page URL (…/plotting/auto/?q=189&station=…) into its CSV export URL. Returns (plot number, url)."""
    u = urlparse(page_url.strip())
    if u.hostname != "mesonet.agron.iastate.edu":
        raise IEMError("That isn't an IEM autoplot link. It should start with https://mesonet.agron.iastate.edu/plotting/auto/")
    m = _AUTOPLOT_PATH.search(u.path)
    if m:  # Already a direct plot/export link
        num, args = m.group(1), m.group(2).strip("/")
    else:
        params = dict(parse_qsl(u.query))
        num = params.pop("q", "")
        if not num.isdigit():
            raise IEMError("Couldn't find the autoplot number in that link (the '?q=' part). "
                           "Copy the address of the autoplot page after making the plot.")
        args = "::".join(f"{k}:{v}" for k, v in params.items())
    return int(num), f"{BASE}/plotting/auto/plot/{num}/{args}.csv" if args else f"{BASE}/plotting/auto/plot/{num}/.csv"


def autoplot_meta(num):
    meta = _get(f"{BASE}/plotting/auto/meta/{num}.json").json()
    return {"title": meta.get("title", f"Autoplot #{num}"), "data": bool(meta.get("data"))}


def fetch_autoplot_csv(csv_url):
    text = _get(csv_url).text
    try:
        df = pd.read_csv(io.StringIO(text), comment="#")
    except Exception as e:
        raise IEMError("IEM didn't return a data table for that plot. Check the plot's options on the IEM page.") from e
    if df.empty or df.shape[1] < 2:
        raise IEMError("IEM returned an empty table for that plot.")
    return df
