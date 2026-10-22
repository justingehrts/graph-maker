"""End-to-end checks of the Streamlit app with AppTest. IEM calls are replaced by the saved Ames data."""
import gzip
from pathlib import Path

import pandas as pd
import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

import data_io as dio
import iem
from palette import PALETTE

APP = str(Path(__file__).parent.parent / "app.py")
FIX = Path(__file__).parent / "fixtures"
DAILY = iem.parse_daily_csv(gzip.open(FIX / "iem_coop_IATAME.csv.gz", "rt").read())
STATIONS = pd.DataFrame({"id": ["IATAME"], "name": ["Ames Area"], "county": ["Story"], "begin": [1893],
                         "ncei91": ["USW00094989"], "label": ["Ames Area (IATAME) · Story Co. · since 1893"]})
NCEI = pd.read_csv(FIX / "ncei_normals_OHTCMH.csv", dtype={"md": str}).set_index("md")  # Stand-in official normals


@pytest.fixture(autouse=True)
def fake_iem(monkeypatch):
    st.cache_data.clear()
    monkeypatch.setattr(iem, "fetch_stations", lambda state: STATIONS)
    monkeypatch.setattr(iem, "fetch_daily", lambda station, state: DAILY.loc[:"2025-10-10"])
    monkeypatch.setattr(iem, "fetch_ncei_normals", lambda station, state, ncei_id: NCEI)


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


def test_running_total_uses_official_ncei_normals():
    at = use_station("Running Total vs Normal", rt_year=2025)
    df = at.session_state.datasets["Running Total vs Normal"]
    days = pd.date_range("2025-01-01", "2025-10-10").strftime("%m%d")
    assert df["Normal"].iloc[-1] == round(NCEI["precip"].reindex(days).sum(), 2)
    assert "NCEI 1991–2020 normals (USW00094989, via IEM)" in at.session_state.source_notes["Running Total vs Normal"]


def test_full_record_option():
    at = use_station("Record & Normal Band", rb_mode="Month", rb_month="July", rb_year=2025, normal_period="Full record")
    assert "full-record averages" in at.session_state.source_notes["Record & Normal Band"]


def test_missing_ncei_normals_offer_iem_fallback(monkeypatch):
    def unavailable(station, state, ncei_id):
        raise iem.NormalsUnavailable("Couldn't get the NCEI normals from IEM: timeout.")
    monkeypatch.setattr(iem, "fetch_ncei_normals", unavailable)
    at = new(chart_type="Running Total vs Normal", iem_state="IA", iem_station="IATAME", rt_year=2025)
    before = at.session_state.datasets["Running Total vs Normal"].copy()
    widget(at, "button", "📥 Use this station data").click().run()
    assert problems(at) == [] and any("Couldn't get the NCEI normals" in w.value for w in at.warning)
    assert at.session_state.datasets["Running Total vs Normal"].equals(before)  # Nothing unofficial built
    widget(at, "button", "Use IEM 1991–2020 averages instead").click().run()
    note = at.session_state.source_notes["Running Total vs Normal"]
    assert "IEM 1991–2020 station averages (not official NCEI normals)" in note
    assert at.session_state.normals_fallback is True and not at.warning


def test_iem_outage_shows_friendly_error(monkeypatch):
    def down(state):
        raise iem.IEMError("Couldn't get data from the Iowa Environmental Mesonet (ConnectionError).")
    monkeypatch.setattr(iem, "fetch_stations", down)
    at = new(chart_type="Running Total vs Normal")
    assert not at.exception and any("Couldn't get data" in e.value for e in at.error)


XMACIS_LAST = (FIX / "xmacis_last_date_by_year.txt").read_text()


def test_date_values_in_year_ranking():
    at = new()
    widget(at, "radio", "Chart Type").set_value("Year Ranking").run()
    at.text_area[0].input(XMACIS_LAST).run()
    widget(at, "button", "Use pasted data").click().run()
    assert problems(at) == []
    ss = at.session_state
    assert ss.value_kind == "Date" and ss.yr_word == "latest" and ss.yr_order == "By year"
    df = ss.datasets["Year Ranking"]
    summary = next(m.value for m in at.markdown if m.value.startswith("**2025:"))
    assert "latest of 148 years (Oct 18)" in summary and "average Oct" in summary
    # Trend line labeled in days per decade; Lowest flips the word to "earliest"
    widget(at, "checkbox", "Trend line").check().run()
    widget(at, "radio", "Rank from").set_value("Lowest").run()
    assert problems(at) == [] and ss.yr_word == "earliest"
    assert len(df) == 148


def test_date_values_in_bar_then_numbers_switch_back():
    at = new()
    at.text_area[0].input(XMACIS_LAST).run()
    widget(at, "button", "Use pasted data").click().run()
    assert problems(at) == [] and at.session_state.value_kind == "Date"
    assert at.session_state.datasets["Basic"]["Value 1"].iloc[-1] == 291
    at.text_area[0].input("Day\tHigh\nMon\t70\nTue\t72\n").run()
    widget(at, "button", "Use pasted data").click().run()
    assert problems(at) == [] and at.session_state.value_kind == "Number"


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


def test_station_defaults_to_columbus(monkeypatch):
    columbus = pd.DataFrame({"id": ["OHTCMH"], "name": ["Columbus Area"], "county": ["Franklin"], "begin": [1878],
                             "ncei91": ["USW00014821"], "label": ["Columbus Area (OHTCMH) · Franklin Co. · since 1878"]})
    asked = []
    monkeypatch.setattr(iem, "fetch_stations", lambda state: asked.append(state) or columbus)
    at = new(chart_type="Running Total vs Normal")
    assert at.session_state.iem_state == "OH" and at.session_state.iem_station == "OHTCMH" and asked == ["OH"]
    assert at.selectbox(key="iem_station").value == "OHTCMH" and problems(at) == []


def test_date_tables_show_dates_not_day_numbers():
    at = new()
    at.text_area[0].input(XMACIS_LAST).run()
    widget(at, "button", "Use pasted data").click().run()
    shown = at.dataframe[0].value  # The data editor as displayed
    assert shown["Value 1"].iloc[0] == "Oct 1" and shown["Value 1"].iloc[-1] == "Oct 18"
    assert shown["Value 2"].iloc[0] == ""  # Unused second series stays blank, not "Dec 31"
    # Switching to Numbers shows the stored day numbers; back to Dates restores the dates, data unchanged
    widget(at, "radio", "Values are").set_value("Number").run()
    assert at.dataframe[0].value["Value 1"].iloc[0] == 274
    widget(at, "radio", "Values are").set_value("Date").run()
    assert problems(at) == [] and at.dataframe[0].value["Value 1"].iloc[-1] == "Oct 18"
    assert at.session_state.datasets["Basic"]["Value 1"].iloc[-1] == 291


def test_x_axis_label_choices():
    import charts
    years = [str(y) for y in range(1878, 2026)]
    pick = lambda mode, keep=(): [years[i] for i in charts.label_positions(years, {"x_label_every": mode}, keep)]
    assert pick("Years ending in 0")[:3] == ["1880", "1890", "1900"] and pick("Years ending in 0")[-1] == "2020"
    assert pick("Years ending in 0 or 5")[:3] == ["1880", "1885", "1890"]
    assert pick("Years ending in 0", keep=[147])[-2:] == ["2010", "2025"]  # Kept 2025 pushes out the too-close 2020
    assert len(pick("Every label")) == 148 and pick("Every 10th")[:2] == ["1878", "1888"]
    seasons = ["2019-20", "2020-21", "2021-22"]
    assert charts.label_positions(seasons, {"x_label_every": "Years ending in 0"}) == [1]
    assert charts.label_positions(["Mon", "Tue"], {"x_label_every": "Years ending in 0"}) == [0, 1]  # Not years: Auto
    at = new()
    at.text_area[0].input(XMACIS_LAST).run()
    widget(at, "button", "Use pasted data").click().run()
    for mode in ("Years ending in 0 or 5", "Every label"):
        widget(at, "selectbox", "X Axis Labels").set_value(mode).run()
        assert problems(at) == []
    widget(at, "radio", "Chart Type").set_value("Year Ranking").run()
    widget(at, "selectbox", "X Axis Labels").set_value("Years ending in 0").run()
    assert problems(at) == []


def test_range_bars_from_columbus_station_data(monkeypatch):
    columbus = pd.DataFrame({"id": ["OHTCMH"], "name": ["Columbus Area"], "county": ["Franklin"], "begin": [1878],
                             "ncei91": ["USW00014821"], "label": ["Columbus Area (OHTCMH) · Franklin Co. · since 1878"]})
    monkeypatch.setattr(iem, "fetch_stations", lambda state: columbus)
    at = new(chart_type="Range Bars")  # Columbus Area is the default station
    widget(at, "button", "📥 Use this station data").click().run()
    assert problems(at) == []
    df = at.session_state.datasets["Range Bars"]
    assert len(df) > 100 and at.session_state.value_kind == "Date"
    assert at.session_state.rg_highlight == df["Label"].iloc[-1] == "2025"  # Stand-in data runs through Oct 10, 2025
    assert "growing season: last spring / first fall low ≤ 32°" in at.session_state.source_notes["Range Bars"]
    assert any(m.value.startswith("**2025: ") and "average" in m.value for m in at.markdown)
    assert at.dataframe[0].value["Start"].iloc[0].split()[0] in ("Mar", "Apr", "May")  # Shown as dates
    for label_mode in ("Ends", "Length"):
        widget(at, "radio", "Labels on bars").set_value(label_mode).run()
    widget(at, "radio", "Bar direction").set_value("Vertical").run()
    assert problems(at) == []


def test_bar_direction_options():
    at = new()
    widget(at, "radio", "Bar direction").set_value("Horizontal").run()
    assert problems(at) == []
    widget(at, "radio", "Chart Type").set_value("Year Ranking").run()
    widget(at, "radio", "Order").set_value("Sorted").run()
    widget(at, "radio", "Bar direction").set_value("Horizontal").run()
    assert problems(at) == [] and any("trend line is available with vertical" in c.value for c in at.caption) is False



BAND_PICKERS = {"rt_env_color", "rt_surplus_color", "rt_deficit_color", "rb_normal_color", "rb_rec_high_color",
                "rb_rec_low_color", "rb_record_color"}


def chips(at, target):
    return [b for b in at.button if b.key and b.key.startswith(f"chip_{target}_")]


@pytest.mark.parametrize("chart", dio.CHART_TYPES)
def test_only_palette_colors_are_offered(chart):
    at = new(chart_type=chart)
    assert problems(at) == []
    assert {p.key for p in at.color_picker} <= BAND_PICKERS  # Shaded bands keep their pickers for now
    assert len(chips(at, "text_choice")) == 2 and len(chips(at, "grid_color")) == 3
    assert len(chips(at, "last_c1")) == (len(PALETTE) if chart in dio.BASIC_TYPES else 0)
    targets = {b.key[5:].rsplit("_", 1)[0] for b in at.button if b.key and b.key.startswith("chip_")}
    for t in targets - {"text_choice"}:  # Every default is one of the colors offered for it
        assert any(at.session_state[t] in b.help for b in chips(at, t)), t


def test_clicking_a_chiclet_sets_the_color():
    at = new()
    chips(at, "last_c1")[list(PALETTE).index("Coral")].click().run()
    assert at.session_state.last_c1 == PALETTE["Coral"]
    assert "(selected)" in chips(at, "last_c1")[list(PALETTE).index("Coral")].help
    chips(at, "text_choice")[1].click().run()
    assert at.session_state.text_choice == "WI Navy" and problems(at) == []
