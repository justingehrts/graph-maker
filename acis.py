"""ACIS (Applied Climate Information System, data.rcc-acis.org) data access: the official NWS station data
behind xmACIS and NOWData.

Returns the same frames as iem.py's fetchers, so every climate calculation in iem.py works on either source.
Plain pandas + requests (no Streamlit), so everything here can be tested directly.
"""
import re
from datetime import date

import pandas as pd
import requests

from iem import TRACE, IEMError, NormalsUnavailable

BASE = "https://data.rcc-acis.org"
TIMEOUT = 90
ELEMS = ["maxt", "mint", "pcpn", "snow"]
COLUMNS = ["high", "low", "precip", "snow"]
MIN_YEARS = 30  # Shortest record worth listing (threaded "Area" records are always listed)


class ACISError(IEMError):
    """ACIS couldn't be reached or returned something unusable."""


def _post(endpoint, body):
    try:
        r = requests.post(f"{BASE}/{endpoint}", json=body, timeout=TIMEOUT)
        r.raise_for_status()
        data = r.json()
    except requests.Timeout as e:
        raise ACISError("ACIS (the NWS climate data service) took too long to respond. Try again in a minute.") from e
    except (requests.RequestException, ValueError) as e:
        raise ACISError(f"Couldn't get data from ACIS, the NWS climate data service ({e.__class__.__name__}). "
                        "Check the connection and try again.") from e
    if "error" in data:
        raise ACISError(f"ACIS couldn't answer: {data['error']}")
    return data


def parse_value(v):
    """An ACIS daily value as a number: T (trace) is TRACE; M (missing) and S (included in a later day's
    total) are missing; an A suffix (a total accumulated over several days) is dropped."""
    if v == "T": return TRACE
    m = re.fullmatch(r"(-?\d+(?:\.\d+)?)A?", str(v).strip())
    return float(m.group(1)) if m else float("nan")


def _frame(rows, columns):
    df = pd.DataFrame([[parse_value(v) for v in r[1:]] for r in rows], columns=columns,
                      index=pd.to_datetime([r[0] for r in rows]))
    return df.rename_axis("date")


# --- Stations ---

def _station_row(meta, today):
    sids = dict(reversed(s.split(" ", 1)) for s in meta.get("sids", []) if " " in s)  # {type: id}
    threaded = "9" in sids
    sid = sids.get("9") or sids.get("2") or sids.get("1") or sids.get("3")  # ThreadEx, COOP, WBAN, FAA
    ranges = [r for r in meta.get("valid_daterange", []) if len(r) == 2]
    if not sid or not ranges: return None
    begin, end = min(date.fromisoformat(r[0]) for r in ranges), max(date.fromisoformat(r[1]) for r in ranges)
    if not threaded and ((today - end).days > 366 or end.year - begin.year < MIN_YEARS):
        return None  # Keep the list to stations still reporting with a long record
    return {"id": sid, "name": meta["name"].title() if meta["name"].isupper() else meta["name"],
            "threaded": threaded, "begin": begin.year}


def fetch_stations(state, today=None):
    """Stations for a state worth charting: the threaded "Area" records (a city's long-term record), then
    stations still reporting with at least MIN_YEARS of data. Columns: id, name, county, begin, label."""
    data = _post("StnMeta", {"state": state, "meta": ["name", "sids", "county", "valid_daterange"],
                             "elems": ["maxt", "pcpn"]})
    rows = [r for r in (_station_row(m, today or date.today()) for m in data.get("meta", [])) if r]
    df = pd.DataFrame(rows, columns=["id", "name", "threaded", "begin"])
    if df.empty:
        return pd.DataFrame(columns=["id", "name", "county", "begin", "label"])
    df = df.drop_duplicates("id").sort_values(["threaded", "name"], ascending=[False, True]).reset_index(drop=True)
    df["county"] = ""
    df["label"] = df.apply(lambda r: f"{r['name']} ({r['id']}) · since {r['begin']}", axis=1)
    return df[["id", "name", "county", "begin", "label"]]


# --- Daily data & normals ---

def fetch_daily(sid, end=None):
    """Full period-of-record daily high, low, precip and snow for one station (one request)."""
    data = _post("StnData", {"sid": sid, "sdate": "por", "edate": (end or date.today()).isoformat(),
                             "elems": [{"name": e} for e in ELEMS], "meta": ["name"]})
    rows = data.get("data") or []
    if not rows:
        raise ACISError("ACIS returned no daily data for this station.")
    df = _frame(rows, COLUMNS)
    has_data = df.notna().any(axis=1)  # Trim trailing days with no data yet
    df = df.loc[: has_data[has_data].index.max()] if has_data.any() else df
    df.attrs["station_name"] = data.get("meta", {}).get("name", "")
    return df


def fetch_normals(sid):
    """Official NCEI 1991-2020 daily normals by calendar day (MMDD, including 0229): daily precip and snow
    amounts, and normal high and low. Raises NormalsUnavailable if ACIS doesn't have them for the station."""
    try:
        data = _post("StnData", {"sid": sid, "sdate": "2020-01-01", "edate": "2020-12-31",  # A leap year: 366 days
                                 "elems": [{"name": e, "normal": "1"} for e in ELEMS]})
    except ACISError as e:
        raise NormalsUnavailable(f"Couldn't get the NCEI normals from ACIS: {e}") from e
    rows = data.get("data") or []
    if len(rows) != 366:
        raise NormalsUnavailable("ACIS has no NCEI 1991–2020 normals for this station.")
    df = _frame(rows, COLUMNS)
    df.index = df.index.strftime("%m%d")
    df = df.rename_axis("md")
    # NCEI gives Feb 29 no precip or snow normal of its own; it adds nothing to a running total
    if "0229" in df.index:
        df.loc["0229", ["precip", "snow"]] = df.loc["0229", ["precip", "snow"]].fillna(0.0)
    df[["precip", "snow"]] = df[["precip", "snow"]].mask(df[["precip", "snow"]] == TRACE, 0.0)
    if df.isna().any().any():
        raise NormalsUnavailable("ACIS's NCEI 1991–2020 normals for this station are incomplete.")
    df.attrs["ncei_id"] = sid
    return df[["precip", "snow", "high", "low"]]


# Earlier projects saved IEM's threaded station ids (e.g. OHTCMH); ACIS calls the same record CMHthr
def from_iem_id(iem_id):
    m = re.fullmatch(r"[A-Z]{2}T([A-Z0-9]{3,5})", str(iem_id or ""))
    return f"{m.group(1)}thr" if m else None
