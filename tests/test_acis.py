"""ACIS parsing, checked against saved ACIS responses for Columbus Area (CMHthr) and Ohio's station list."""
import gzip
import json
from datetime import date
from pathlib import Path

import pandas as pd
import pytest

import acis
import iem

FIX = Path(__file__).parent / "fixtures"
DAILY = json.load(gzip.open(FIX / "acis_CMHthr_daily.json.gz", "rt"))
NORMALS = json.load(open(FIX / "acis_CMHthr_normals.json"))
STATIONS = json.load(gzip.open(FIX / "acis_OH_stations.json.gz", "rt"))


@pytest.fixture
def saved(monkeypatch):
    def post(endpoint, body):
        if endpoint == "StnMeta": return STATIONS
        return NORMALS if body["elems"][0].get("normal") else DAILY
    monkeypatch.setattr(acis, "_post", post)


@pytest.mark.parametrize("raw, value", [("0.25", 0.25), ("T", iem.TRACE), ("M", None), ("S", None), ("1.30A", 1.3),
                                        ("-5", -5.0), ("", None)])
def test_parse_value(raw, value):
    v = acis.parse_value(raw)
    assert (pd.isna(v) if value is None else v == value)


def test_daily_frame_matches_the_iem_layout(saved):
    d = acis.fetch_daily("CMHthr")
    assert list(d.columns) == ["high", "low", "precip", "snow"] and d.index.name == "date"
    assert d.index.min() == pd.Timestamp("1878-07-01") and d.index.max() == pd.Timestamp("2026-10-22")
    assert d.attrs["station_name"] == "Columbus Area"


def test_running_total_matches_the_nws_almanac(saved):
    """Jan 1 – Oct 22, 2026 at Columbus: 45.13" observed against a 34.81" normal (+10.32"), as ACIS and the
    CPC NWS Climate Almanac report it."""
    df, info = iem.running_total(acis.fetch_daily("CMHthr"), "precip", 2026, ncei=acis.fetch_normals("CMHthr"))
    last = df.iloc[-1]
    assert last["Date"] == pd.Timestamp("2026-10-22") and last["Observed"] == 45.13 and last["Normal"] == 34.81


def test_normals_cover_every_calendar_day(saved):
    n = acis.fetch_normals("CMHthr")
    assert len(n) == 366 and not n.isna().any().any() and list(n.columns) == ["precip", "snow", "high", "low"]
    assert n.loc["0229", "precip"] == 0 and round(n["precip"].sum(), 2) == 41.57


def test_missing_normals(monkeypatch):
    monkeypatch.setattr(acis, "_post", lambda e, b: {"data": [["2020-01-01", "M", "M", "M", "M"]] * 366})
    with pytest.raises(iem.NormalsUnavailable):
        acis.fetch_normals("XXXthr")


def test_station_list_puts_city_records_first(saved):
    st = acis.fetch_stations("OH", today=date(2026, 10, 23))
    threaded = st[st["id"].str.endswith("thr")]
    assert list(st.index[: len(threaded)]) == list(threaded.index)  # All threaded records come first
    assert "CMHthr" in threaded["id"].tolist() and len(threaded) == 12
    assert "Columbus Area (CMHthr) · since 1878" in st["label"].tolist()
    assert len(st) < 200  # Short-lived and closed stations are left out


def test_old_iem_station_ids():
    assert acis.from_iem_id("OHTCMH") == "CMHthr" and acis.from_iem_id("OH3384") is None
