"""Climate calculations checked against IEM's own published numbers for Ames (IATAME).

Fixtures were downloaded from IEM on 2026-10-11:
- iem_coop_IATAME.csv.gz: full daily record (cgi-bin/request/coop.py)
- autoplot172_*: autoplot #172 running totals (accum) for 2024-2025
- autoplot107_*: autoplot #107 period statistics per year for Jan 1 - Oct 10
- por_daily_climo_IATAME.json: /api/1/climodat/por_daily_climo daily records
"""
import gzip
import json
from datetime import date
from pathlib import Path

import pandas as pd
import pytest

import iem

FIX = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="module")
def daily():
    return iem.parse_daily_csv(gzip.open(FIX / "iem_coop_IATAME.csv.gz", "rt").read())


def test_parse_daily(daily):
    assert daily.index.min() == pd.Timestamp("1893-01-01")
    assert daily.attrs["station_name"] == "Ames Area"
    assert daily["snow"].isna().any()  # "M" became missing, not zero
    assert (daily["precip"] == iem.TRACE).any()  # traces kept as 0.0001


@pytest.mark.parametrize("year", [2024, 2025])
def test_running_total_matches_autoplot_172(daily, year):
    ref = pd.read_csv(FIX / "autoplot172_IATAME_precip_2024_2025.csv")
    ref = ref[ref["binyear"] == year]
    out, info = iem.running_total(daily, "precip", year, end=date(year, 10, 10))
    # Compare by date (IEM's #172 export leaves out one day in leap years)
    got = out.set_index("Date")["Observed"].reindex(pd.to_datetime(ref["day"]))
    assert got.notna().all()
    # IEM's accum counts each trace as 0.0001 and isn't rounded; ours counts traces as 0 and rounds to 0.01
    assert got.to_numpy() == pytest.approx(ref["accum"].to_numpy(), abs=0.015)
    assert info["season"] == str(year)


def test_running_total_normal_and_extension(daily):
    out, _ = iem.running_total(daily, "precip", 2025, end=date(2025, 6, 30), extend_normal=True)
    assert len(out) == 365 and out["Observed"].iloc[181:].isna().all() and out["Observed"].iloc[:181].notna().all()
    # Ames 1991-2020 annual precip is roughly 36 inches
    assert 33 < out["Normal"].iloc[-1] < 39
    assert out["Normal"].is_monotonic_increasing


def test_running_total_season_crossing_new_year(daily):
    out, info = iem.running_total(daily, "snow", 2024, start_month=7, start_day=1)
    assert info["season"] == "2024-25"
    assert out["Date"].iloc[0] == pd.Timestamp("2024-07-01") and out["Date"].iloc[-1] == pd.Timestamp("2025-06-30")


def test_yearly_values_match_autoplot_107(daily):
    ref = pd.read_csv(FIX / "autoplot107_IATAME_0101_1010.csv").set_index("yr")
    for var, col in [("Total precipitation", "precip"), ("Total snowfall", "snow"), ("Average high", "avg_high_temp")]:
        # No skipping here: IEM's table includes every year, whatever its missing days
        out, _ = iem.yearly_values(daily, var, (1, 1), (10, 10), max_missing=366)
        got = out.set_index(out["Year"].astype(int))["Value"]
        common = got.index.intersection(ref.index)
        assert len(common) > 120
        assert got.loc[common].to_numpy() == pytest.approx(ref.loc[common, col].to_numpy(), abs=0.01)


def test_yearly_values_skip_incomplete_years(daily):
    out, info = iem.yearly_values(daily, "Total snowfall", (1, 1), (12, 31), max_missing=3)
    assert "2026" not in out["Year"].tolist()  # current year isn't complete
    assert info["skipped_years"]  # snowfall has years with missing days


def test_yearly_values_season_crossing_year(daily):
    out, _ = iem.yearly_values(daily, "Total snowfall", (12, 1), (2, 28))
    assert out["Year"].iloc[-1].count("-") == 1


def test_records_match_por_daily_climo(daily):
    ref = pd.DataFrame(json.load(open(FIX / "por_daily_climo_IATAME.json"))["data"])
    ref.index = pd.to_datetime(ref["date"]).dt.strftime("%m%d")
    # IEM's climo table may include days after our download; drop the current year on both sides by comparing
    # through 2025 only where the record wasn't set in 2026
    climo = iem.daily_climatology(daily.loc[:"2025-12-31"])
    ok = ~ref["high_max_years"].str.contains("2026") & ~ref["low_min_years"].str.contains("2026")
    assert (climo.loc[ref.index[ok], "record_high"] == ref.loc[ok, "high_max"]).mean() > 0.99
    assert (climo.loc[ref.index[ok], "record_low"] == ref.loc[ok, "low_min"]).mean() > 0.99


def test_record_band_excludes_displayed_year(daily):
    out, _ = iem.record_band(daily, date(2025, 7, 1), date(2025, 7, 31))
    assert len(out) == 31
    highs, lows = iem.record_counts(out)
    # Records are "before this year", so a new record shows as actual >= prior record
    assert (out.loc[highs, "Actual High"] >= out.loc[highs, "Record High"]).all()
    assert (out["Normal High"] > out["Normal Low"]).all()
    assert 80 < out["Normal High"].mean() < 90  # Ames July normal highs are mid-80s


def test_feb_29(daily):
    climo = iem.daily_climatology(daily)
    assert "0229" in climo.index and pd.notna(climo.loc["0229", "normal_high"])
    out, _ = iem.record_band(daily, date(2024, 2, 27), date(2024, 3, 2))
    assert out["Normal High"].notna().all()


def test_rank_and_ties():
    df = pd.DataFrame({"Year": ["2001", "2002", "2003", "2004"], "Value": [5.0, 7.0, 7.0, 1.0]})
    assert iem.rank_of(df, "2003") == (1, True, 4)
    assert iem.rank_of(df, "2001") == (3, False, 4)
    assert iem.rank_of(df, "2004", highest_first=False) == (1, False, 4)
    assert iem.rank_of(df, "1999") is None
    assert [iem.ordinal(n) for n in (1, 2, 3, 4, 11, 12, 13, 21, 22, 101)] == \
        ["1st", "2nd", "3rd", "4th", "11th", "12th", "13th", "21st", "22nd", "101st"]


@pytest.mark.parametrize("page,expected", [
    ("https://mesonet.agron.iastate.edu/plotting/auto/?q=189&network=IACLIMATE&station=IATAME&var=total_precip",
     "https://mesonet.agron.iastate.edu/plotting/auto/plot/189/network:IACLIMATE::station:IATAME::var:total_precip.csv"),
    ("https://mesonet.agron.iastate.edu/plotting/auto/plot/107/network:IACLIMATE::station:IATAME::sday:0101.png",
     "https://mesonet.agron.iastate.edu/plotting/auto/plot/107/network:IACLIMATE::station:IATAME::sday:0101.csv"),
])
def test_autoplot_url(page, expected):
    assert iem.autoplot_csv_url(page)[1] == expected


@pytest.mark.parametrize("bad", ["https://example.com/plotting/auto/?q=1", "https://mesonet.agron.iastate.edu/plotting/auto/"])
def test_autoplot_url_rejects(bad):
    with pytest.raises(iem.IEMError):
        iem.autoplot_csv_url(bad)


def test_network_errors_are_friendly(monkeypatch):
    import requests

    def boom(*a, **k):
        raise requests.ConnectionError("down")
    monkeypatch.setattr(iem.requests, "get", boom)
    with pytest.raises(iem.IEMError, match="Couldn't get data"):
        iem.fetch_stations("IA")


def test_running_total_history_like_autoplot_172(daily):
    out, info = iem.running_total(daily, "precip", 2025, end=date(2025, 10, 10))
    assert {"Highest Year", "Lowest Year", "Range Max", "Range Min"} <= set(out.columns)
    # The range covers every other year, and the highest/lowest years' final totals are its ends
    assert (out["Range Max"] >= out["Range Min"]).all()
    assert out["Highest Year"].iloc[-1] == out["Range Max"].iloc[-1] == info["highest"][1]
    assert out["Lowest Year"].iloc[-1] == out["Range Min"].iloc[-1] == info["lowest"][1]
    assert info["highest"][0] != "2025" and info["years"] > 100


def test_full_year_band_runs_past_latest_data(daily):
    part = daily.loc[:"2025-10-10"]
    out, _ = iem.record_band(part, date(2025, 1, 1), date(2025, 12, 31))
    assert len(out) == 365
    later = out["Date"] > pd.Timestamp("2025-10-10")
    assert out.loc[later, ["Actual High", "Actual Low"]].isna().all().all()
    assert out[["Normal High", "Normal Low", "Record High", "Record Low"]].notna().all().all()


def load_ncei_fixture():
    # Official NCEI 1991-2020 daily normals for Columbus Area (OHTCMH), as IEM serves them (saved 2026-10-12)
    n = pd.read_csv(FIX / "ncei_normals_OHTCMH.csv", dtype={"md": str}).set_index("md")
    n.attrs["ncei_id"] = "USW00014821"
    return n


def test_ncei_normals_match_nws_climate_report():
    # NWS daily climate report for Columbus, Oct 11 2026: precipitation since Jan 1 normal 33.80"
    n = load_ncei_fixture()
    assert len(n) == 366 and "0229" in n.index
    days = pd.date_range("2026-01-01", "2026-10-11").strftime("%m%d")
    assert round(n["precip"].reindex(days).sum(), 2) == 33.80


def test_running_total_uses_ncei_normals(daily):
    n = load_ncei_fixture()
    out, _ = iem.running_total(daily, "precip", 2026, extend_normal=True, ncei=n)
    assert out.loc[out["Date"] == "2026-10-11", "Normal"].iloc[0] == 33.80
    # Station averages are only used when no official normals are passed
    own, _ = iem.running_total(daily, "precip", 2026, extend_normal=True)
    assert own["Normal"].iloc[-1] != out["Normal"].iloc[-1]


def test_record_band_uses_ncei_normals(daily):
    out, _ = iem.record_band(daily, date(2024, 2, 28), date(2024, 3, 1), ncei=load_ncei_fixture())
    assert out["Normal High"].tolist() == [44.7, 44.9, 45.1] and out["Normal Low"].tolist() == [27.4, 27.5, 27.7]


def test_no_ncei_station_raises():
    with pytest.raises(iem.NormalsUnavailable, match="No official NCEI"):
        iem.fetch_ncei_normals("XX0000", "IA", "")


def test_freeze_seasons_match_autoplot_10(daily):
    # IEM #10 (last spring / first fall low below 32°) for Ames, saved 2026-10-14
    ref = pd.read_csv(FIX / "autoplot10_IATAME_low32.csv")
    out, _ = iem.freeze_seasons(daily, 32, strictly_below=True)
    m = out.merge(ref.assign(Label=ref["year"].astype(str)), on="Label")
    import data_io as dio
    fmt = lambda col: pd.to_datetime(m[col]).map(lambda t: f"{t:%b} {t.day}")
    assert len(m) == len(ref) == 133
    assert (m["Start"].map(dio.day_of_year_text) == fmt("spring_date")).all()
    assert (m["End"].map(dio.day_of_year_text) == fmt("fall_date")).all()
    assert out.attrs["value_kind"] == "Date"
    # The current year has its spring freeze but no fall freeze yet
    assert out["Label"].iloc[-1] == "2026" and pd.notna(out["Start"].iloc[-1]) and pd.isna(out["End"].iloc[-1])


def test_freeze_seasons_nws_counts_32_as_freezing(daily):
    nws, _ = iem.freeze_seasons(daily, 32)  # At or below 32°
    iem_style, _ = iem.freeze_seasons(daily, 32, strictly_below=True)
    both = nws.merge(iem_style, on="Label", suffixes=("_nws", "_iem")).dropna()
    # Counting 32° itself can only make the spring freeze later and the fall freeze earlier
    assert (both["Start_nws"] >= both["Start_iem"]).all() and (both["End_nws"] <= both["End_iem"]).all()
    assert (both["Start_nws"] != both["Start_iem"]).any()


def test_a_low_of_exactly_32_is_a_freeze():
    days = pd.date_range("2024-01-01", "2024-12-31")
    daily = pd.DataFrame({"high": 60.0, "low": 45.0, "precip": 0.0, "snow": 0.0}, index=days)
    daily.loc["2024-04-20", "low"] = 32  # Last spring freeze: exactly 32°
    daily.loc["2024-10-15", "low"] = 32  # First fall freeze: exactly 32°
    out, _ = iem.freeze_seasons(daily, 32)
    import data_io as dio
    assert [dio.day_of_year_text(out["Start"].iloc[0]), dio.day_of_year_text(out["End"].iloc[0])] == ["Apr 20", "Oct 15"]
