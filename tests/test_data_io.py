"""Parsing and cleanup of pasted / imported tables in the formats people copy from."""
from pathlib import Path

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


@pytest.mark.parametrize("key", ["Basic", "Record & Normal Band"])
def test_duplicate_header_names(key):
    # Pasting a header with repeated names used to crash the app
    df, _, ignored = load("Date\tHigh\tLow\tHigh\tLow\n2025-07-01\t88\t64\t90\t60\n", key)
    assert len(df) == 1 and ignored == ["High (2)", "Low (2)"]


def test_rows_wider_than_header_are_padded():
    df, _, ignored = load("Date\tHigh\tLow\n2025-07-01\t88\t64\t1\t2\n2025-07-02\t91\t70\n", "Record & Normal Band")
    assert df["Actual High"].tolist() == [88, 91] and ignored == ["Column 4", "Column 5"]


def test_quoted_csv_values():
    df, _, _ = load('Day,Total\n"Oct 1","1,280"\n', "Basic")
    assert df["Label"].tolist() == ["Oct 1"] and df["Value 1"].tolist() == [1280.0]


# --- Date values (e.g. an xmACIS "last date" by year) ---

XMACIS_LAST = (Path(__file__).parent / "fixtures" / "xmacis_last_date_by_year.txt").read_text()


def test_xmacis_last_date_by_year():
    df, notes, ignored = load(XMACIS_LAST, "Year Ranking")
    assert len(df) == 148 and df["Value"].notna().all() and ignored == []
    assert df["Year"].iloc[0] == "1878" and df["Value"].iloc[0] == 274  # Oct 1
    assert df["Year"].iloc[-1] == "2025" and df["Value"].iloc[-1] == 291  # Oct 18
    assert "values read as dates" in notes and df.attrs["value_kind"] == "Date"


@pytest.mark.parametrize("cell", ["16-Oct", "Oct 16", "October 16", "Oct. 16", "10/16", "2025-10-16", "10/16/2025"])
def test_date_forms(cell):
    days, counts = dio.clean_numbers(pd.Series([cell, "1-Oct"]), keep_missing=True)
    assert days.tolist() == [289, 274] and counts["dates"] == 2


def test_dates_across_new_year_sort_after_december():
    days, _ = dio.clean_numbers(pd.Series(["20-Nov", "5-Jan", "30-Dec", "M"]), keep_missing=True)
    assert days.iloc[1] > days.iloc[2] > days.iloc[0] and pd.isna(days.iloc[3])
    assert dio.day_of_year_text(days.iloc[1]) == "Jan 5"


def test_numbers_are_not_dates():
    nums, counts = dio.clean_numbers(pd.Series(["0.25", "T", "M", "1,280"]), keep_missing=True)
    assert counts["dates"] == 0 and nums.iloc[0] == 0.25 and nums.iloc[3] == 1280


def test_required_columns_fill_by_position_but_optional_ones_dont():
    raw = pd.DataFrame({"Date": ["2025-07-01"], "Hi": [90], "Lo": [70], "Departure": [3]})
    mapping = dio.guess_mapping(raw.columns, "Record & Normal Band")
    assert mapping == {"Date": "Date", "Actual High": "Hi", "Actual Low": "Lo"}  # "Departure" isn't a record


def test_date_formatting():
    s = {"value_kind": "Date", "num_thousands": False, "num_decimals": "2", "num_prefix": "", "num_suffix": '"'}
    assert dio.format_number(291, s) == "Oct 18" and dio.format_number(365, s) == "Dec 31"


def test_dates_shown_as_text_read_back_unchanged():
    days, _ = dio.clean_numbers(pd.Series(["20-Nov", "5-Jan", "30-Dec"]), keep_missing=True)
    again, counts = dio.clean_numbers(days.map(dio.day_of_year_text), keep_missing=True)
    assert again.tolist() == days.tolist() and counts["dates"] == 3


def test_range_bars_columns():
    assert dio.guess_mapping(["year", "spring", "fall", "spring_date", "fall_date", "season"], "Range Bars") == \
        {"Label": "year", "Start": "spring_date", "End": "fall_date"}  # IEM #10
    df, notes, _ = load("Season\tFirst\tLast\n2023-24\t12-Nov\t3-Apr\n2024-25\t28-Nov\t15-Mar\n", "Range Bars")
    assert df["Label"].tolist() == ["2023-24", "2024-25"] and "values read as dates" in notes
