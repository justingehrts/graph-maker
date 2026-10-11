"""Parsing and cleanup of pasted / imported tables in the formats people copy from."""
import pandas as pd
import pytest

import data_io as dio


def load(text, key):
    raw = dio.parse_pasted(text)
    mapped, ignored = dio.map_columns(raw, key)
    df, notes = dio.normalize(mapped, key)
    return df, notes, ignored


# A NOWData "daily data for a month" table copied from the browser (tab-separated, summary rows at the bottom)
NOWDATA = """Date\tMax Temperature\tMin Temperature\tAvg Temperature\tAvg Temperature Departure\tHDD\tCDD\tPrecipitation\tNew Snow\tSnow Depth
2025-07-01\t88\t64\t76.0\t-0.2\t0\t11\t0.00\t0.0\t0
2025-07-02\t91\t70\t80.5\t4.2\t0\t16\tT\t0.0\t0
2025-07-03\tM\t66\tM\tM\tM\tM\t0.42\t0.0\t0
Sum\t-\t-\t-\t-\t0\t27\t0.42\t0.0\t-
Average\t89.5\t66.7\t78.3\t2.0\t-\t-\t-\t-\t-
Normal\t85.9\t64.1\t75.0\t-\t0\t11\t0.14\t0.0\t-
"""


def test_nowdata_daily_table_for_record_band():
    df, notes, ignored = load(NOWDATA, "Record & Normal Band")
    assert len(df) == 3  # Sum / Average / Normal rows dropped
    assert df["Actual High"].tolist()[:2] == [88, 91] and pd.isna(df["Actual High"].iloc[2])  # M stays blank
    assert df["Actual Low"].tolist() == [64, 70, 66]
    assert df["Date"].iloc[0] == pd.Timestamp("2025-07-01")
    assert any("dropped 3 rows" in n for n in notes) and any("missing" in n for n in notes)
    assert "Precipitation" in ignored


def test_nowdata_precip_for_running_total():
    df, notes, _ = load(NOWDATA, "Running Total vs Normal")
    assert df["Observed"].tolist() == [0.0, 0.0, 0.42]  # T counted as 0
    assert any("trace" in n for n in notes)


# An xmACIS seasonal ranking (Rank, Value, Ending Date, Missing Days), values with flags
XMACIS_RANK = """Rank,Value,Ending Date,Missing Days
1,55.60A,1993-12-31,0
2,48.21,2010-12-31,1
3,T,1956-12-31,0
4,M,1934-12-31,40
"""


def test_xmacis_ranked_list():
    df, notes, ignored = load(XMACIS_RANK, "Year Ranking")
    assert df["Year"].tolist() == ["1993", "2010", "1956", "1934"]
    assert df["Value"].iloc[0] == 55.6 and df["Value"].iloc[2] == 0.0 and pd.isna(df["Value"].iloc[3])
    assert "Rank" in ignored


def test_headerless_paste_uses_position():
    df, _, _ = load("Oct 1\t0.1\t0.1\nOct 2\t0.5\t0.2\n", "Running Total vs Normal")
    assert df["Date"].dt.month.tolist() == [10, 10] and df["Observed"].tolist() == [0.1, 0.5]


def test_header_detection_and_units_basic():
    df, notes, _ = load("Day\tHigh\tLow\nMon\t75°\t50°\nTue\t1,280\t52\nWed\tT\t−3\n", "Basic")
    assert df["Label"].tolist() == ["Mon", "Tue", "Wed"]
    assert df["Value 1"].tolist() == [75.0, 1280.0, 0.0] and df["Value 2"].tolist() == [50.0, 52.0, -3.0]


def test_basic_missing_becomes_zero_presets_stay_blank():
    basic, _ = dio.normalize(pd.DataFrame({"Label": ["a"], "Value 1": ["M"], "Value 2": [None]}), "Basic")
    assert basic["Value 1"].iloc[0] == 0.0
    rt, _ = dio.normalize(pd.DataFrame({"Date": ["2025-01-01"], "Observed": ["M"]}), "Running Total vs Normal")
    assert pd.isna(rt["Observed"].iloc[0])


def test_exact_header_beats_alias():
    raw = pd.DataFrame({"High": [90], "Record High": [101], "Normal High": [85], "Date": ["2025-07-01"]})
    mapped, _ = dio.map_columns(raw, "Record & Normal Band")
    assert mapped["Record High"].iloc[0] == 101 and mapped["Actual High"].iloc[0] == 90 and mapped["Normal High"].iloc[0] == 85


@pytest.mark.parametrize("v,kw,expected", [
    (2.31, dict(num_suffix='"', num_decimals="2"), '+2.31"'),
    (-0.5, dict(num_decimals="1"), "−0.5"),
    (0.0, {}, "0"),
])
def test_format_signed(v, kw, expected):
    s = {"num_thousands": False, "num_decimals": "Auto", "num_prefix": "", "num_suffix": "", **kw}
    assert dio.format_number(v, s, signed=True) == expected


def test_samples_and_records_roundtrip():
    for key in dio.SCHEMAS:
        df = dio.sample_data(key)
        back, _ = dio.normalize(pd.DataFrame(dio.to_records(df)), key)
        assert list(back.columns) == dio.columns(key) and len(back) == len(df)
