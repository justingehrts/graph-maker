"""End-to-end checks of the Streamlit app with AppTest. IEM calls are replaced by the saved Ames data."""
import gzip
from pathlib import Path

import pandas as pd
import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

import iem

APP = str(Path(__file__).parent.parent / "app.py")
FIX = Path(__file__).parent / "fixtures"
DAILY = iem.parse_daily_csv(gzip.open(FIX / "iem_coop_IATAME.csv.gz", "rt").read())
STATIONS = pd.DataFrame({"id": ["IATAME"], "name": ["Ames Area"], "county": ["Story"], "begin": [1893],
                         "label": ["Ames Area (IATAME) · Story Co. · since 1893"]})


@pytest.fixture(autouse=True)
def fake_iem(monkeypatch):
    st.cache_data.clear()
    monkeypatch.setattr(iem, "fetch_stations", lambda state: STATIONS)
    monkeypatch.setattr(iem, "fetch_daily", lambda station, state: DAILY.loc[:"2025-10-10"])


def new(**state):
    at = AppTest.from_file(APP, default_timeout=90)
    for k, v in state.items():
        at.session_state[k] = v
    at.run()
    return at


def problems(at):
    return [e.message for e in at.exception] + [e.value for e in at.error]


def widget(at, kind, label):
    return next(w for w in getattr(at, kind) if w.label == label)


def test_baseline_has_no_errors_or_warnings():
    at = new()
    assert problems(at) == [] and not at.warning


def test_every_setting_change_applies_first_time():
    at = new()
    for v in (40, 50, 60):
        widget(at, "slider", "X Axis Label Size").set_value(v).run()
    assert at.session_state.x_sz == 60


def test_hidden_controls_keep_their_values():
    at = new()
    widget(at, "radio", "Chart Type").set_value("Line").run()
    widget(at, "slider", "Line Thickness").set_value(20).run()
    widget(at, "radio", "Chart Type").set_value("Bar").run()
    widget(at, "radio", "Chart Type").set_value("Line").run()
    assert at.session_state.line_width == 20 and problems(at) == []


def test_manual_y_interval_guard():
    at = new()
    widget(at, "checkbox", "Automatic Y Interval").uncheck().run()
    widget(at, "number_input", "Y Interval").set_value(0.01).run()
    assert problems(at) == [] and any("too small" in c.value for c in at.caption)


def test_highlight_by_label_and_paste():
    at = new()
    hl = widget(at, "selectbox", "Highlight Point")
    assert hl.options == ["None", "Mon", "Tue", "Wed", "Thu", "Fri"]
    at.text_area[0].input("Day\tHigh\nSat\t70°\nSun\t72°\n").run()
    widget(at, "button", "Use pasted data").click().run()
    assert at.session_state.datasets["Basic"]["Label"].tolist() == ["Sat", "Sun"]
    assert widget(at, "selectbox", "Highlight Point").options == ["None", "Sat", "Sun"]


def test_paste_with_extra_and_duplicate_columns():
    at = new()
    at.text_area[0].input("Day\tHigh\tLow\tHigh\tLow\nSat\t70\t50\t71\t51\tx\n").run()
    widget(at, "button", "Use pasted data").click().run()
    assert problems(at) == []
    assert at.session_state.datasets["Basic"].values.tolist() == [["Sat", 70.0, 50.0]]


@pytest.mark.parametrize("chart", ["Running Total vs Normal", "Record & Normal Band", "Year Ranking"])
def test_presets_render_sample_data(chart):
    at = new()
    widget(at, "radio", "Chart Type").set_value(chart).run()
    assert problems(at) == []
    assert any(m.value.startswith("**") for m in at.markdown)  # The summary line


def test_switching_chart_types_keeps_each_table():
    at = new()
    widget(at, "radio", "Chart Type").set_value("Year Ranking").run()
    at.text_area[0].input("Year\tValue\n2001\t5\n2002\t7\n").run()
    widget(at, "button", "Use pasted data").click().run()
    widget(at, "radio", "Chart Type").set_value("Bar").run()
    widget(at, "radio", "Chart Type").set_value("Year Ranking").run()
    assert at.session_state.datasets["Year Ranking"]["Year"].tolist() == ["2001", "2002"]
    assert at.session_state.datasets["Basic"]["Label"].iloc[0] == "Mon"


def use_station(chart, **choices):
    at = new(chart_type=chart, iem_state="IA", iem_station="IATAME", **choices)
    widget(at, "button", "📥 Use this station data").click().run()
    assert problems(at) == []
    return at


def test_running_total_from_iem():
    at = use_station("Running Total vs Normal", rt_year=2025)
    df = at.session_state.datasets["Running Total vs Normal"]
    assert df["Date"].iloc[0] == pd.Timestamp("2025-01-01") and df["Date"].iloc[-1] == pd.Timestamp("2025-10-10")
    assert at.session_state.source_notes["Running Total vs Normal"].startswith("IEM · Ames Area (IATAME)")
    assert at.session_state.num_suffix == '"'
    assert any("Through Oct 10" in m.value for m in at.markdown)
    assert "wettest:" in at.session_state.source_notes["Running Total vs Normal"]
    assert df["Range Max"].notna().all()


def test_record_band_from_iem():
    at = use_station("Record & Normal Band", rb_mode="Month", rb_month="July", rb_year=2025)
    df = at.session_state.datasets["Record & Normal Band"]
    assert len(df) == 31 and at.session_state.num_suffix == "°"


def test_record_band_full_year_like_autoplot_113():
    at = use_station("Record & Normal Band", rb_mode="Full year", rb_year=2025)
    df = at.session_state.datasets["Record & Normal Band"]
    assert len(df) == 365 and df["Actual High"].iloc[-1] != df["Actual High"].iloc[-1]  # Blank after Oct 10
    assert at.session_state.rb_style == "Bars"
    for style in ("Simple", "Layered"):
        widget(at, "radio", "Band style").set_value(style).run()
        assert problems(at) == []


def test_year_ranking_from_iem():
    at = use_station("Year Ranking", yr_var="Total snowfall", yr_period="Season", yr_season="Winter (Dec–Feb)",
                     yr_max_missing=20)
    df = at.session_state.datasets["Year Ranking"]
    assert df["Year"].iloc[-1] == "2024-25"
    assert at.session_state.yr_word == "snowiest"
    assert any("2024-25:" in m.value and "snowiest of" in m.value for m in at.markdown)
    assert at.session_state.yr_order == "By year"
    widget(at, "checkbox", "Trend line").check().run()
    widget(at, "radio", "Order").set_value("Sorted").run()
    widget(at, "radio", "Style").set_value("Line").run()
    assert problems(at) == []


def test_year_ranking_says_when_latest_year_is_left_out():
    # Ames is missing 16 snow reports in winter 2024-25, more than the default allowance of 3
    at = use_station("Year Ranking", yr_var="Total snowfall", yr_period="Season", yr_season="Winter (Dec–Feb)")
    assert "2024-25 is left out" in at.session_state.source_notes["Year Ranking"]
    assert any("2024-25 is left out" in c.value for c in at.caption)


def test_iem_outage_shows_friendly_error(monkeypatch):
    def down(state):
        raise iem.IEMError("Couldn't get data from the Iowa Environmental Mesonet (ConnectionError).")
    monkeypatch.setattr(iem, "fetch_stations", down)
    at = new(chart_type="Running Total vs Normal")
    assert not at.exception and any("Couldn't get data" in e.value for e in at.error)


def test_big_basic_chart_thins_labels():
    import charts
    labels = [str(d) for d in pd.date_range("2000-01-01", "2000-12-31").day]
    assert len(charts._thinned(len(labels))) <= 26 and charts._thinned(5) == [0, 1, 2, 3, 4]
    assert 100 in charts._thinned(366, keep=[100])
    at = new()
    at.text_area[0].input("\n".join(f"{l}\t{i % 40}" for i, l in enumerate(labels))).run()
    widget(at, "button", "Use pasted data").click().run()
    assert problems(at) == [] and len(at.session_state.datasets["Basic"]) == 366


def test_autoplot_113_guess_for_basic(monkeypatch):
    raw = pd.DataFrame({"valid": ["2000-01-01T00:00:00", "2000-01-02T00:00:00"], "month": [1, 1], "day": [1, 2],
                        "years": [148, 148], "avg_high": [38.8, 38.6], "max_high": [67, 64]})
    monkeypatch.setattr(iem, "autoplot_meta", lambda n: {"title": "Daily Climatology", "data": True})
    monkeypatch.setattr(iem, "fetch_autoplot_csv", lambda url: raw)
    at = new()
    at.text_input(key="ap_url").input("https://mesonet.agron.iastate.edu/plotting/auto/?q=113&station=OHTCMH").run()
    assert [at.selectbox(key=f"ap_map_113_{t}").value for t in ("Label", "Value 1", "Value 2")] == ["valid", "avg_high", "max_high"]
    widget(at, "button", "Use this autoplot data").click().run()
    assert at.session_state.datasets["Basic"]["Label"].tolist() == ["2000-01-01", "2000-01-02"]


def test_autoplot_import(monkeypatch):
    raw = pd.DataFrame({"yr": [2001, 2002, 2003], "data": [30.5, 41.2, 28.0]})
    monkeypatch.setattr(iem, "autoplot_meta", lambda n: {"title": "Yearly totals", "data": True})
    monkeypatch.setattr(iem, "fetch_autoplot_csv", lambda url: raw)
    at = new(chart_type="Year Ranking")
    at.text_input(key="ap_url").input("https://mesonet.agron.iastate.edu/plotting/auto/?q=189&station=IATAME").run()
    widget(at, "button", "Use this autoplot data").click().run()
    assert problems(at) == []
    assert at.session_state.datasets["Year Ranking"]["Value"].tolist() == [30.5, 41.2, 28.0]
    assert at.session_state.autoplot_mappings["189"] == {"Year": "yr", "Value": "data"}
