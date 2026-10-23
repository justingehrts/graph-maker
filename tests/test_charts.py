"""Rendering checks for the horizontal and floating-bar options (every combination draws without errors)."""
import re
from pathlib import Path

import pandas as pd
import pytest

import charts
import data_io as dio

APP = Path(__file__).parent.parent / "app.py"
ns = {}
exec(re.search(r"state_defaults = \{.*?\n\}", APP.read_text(), re.S).group(0), ns)
BASE = dict(ns["state_defaults"], width=640, height=360)


def draw(ct, df, **kw):
    png, step = charts.render(df, dict(BASE, chart_type=ct, **kw), "white")
    assert png[:4] == b"\x89PNG" and step > 0
    return png


@pytest.mark.parametrize("two", [False, True])
@pytest.mark.parametrize("kind", ["Number", "Date"])
def test_horizontal_bar(two, kind):
    df = pd.DataFrame({"Label": ["Columbus", "Dayton", "Cincinnati"], "Value 1": [2.4, -0.6, 1.1], "Value 2": [1.0, 0.5, -1.5]})
    if kind == "Date":
        df[["Value 1", "Value 2"]] = [[280, 290], [275, 300], [295, 285]]
    draw("Bar", df, bar_orient="Horizontal", show_v2=two, show_values=True, highlight_idx=0, value_kind=kind)


@pytest.mark.parametrize("style", ["Bars", "Dots"])
@pytest.mark.parametrize("order", ["Sorted", "By year"])
def test_horizontal_year_ranking(style, order):
    df = dio.sample_data("Year Ranking")
    draw("Year Ranking", df, yr_orient="Horizontal", yr_style=style, yr_order=order, yr_top_n=15, show_values=True,
         yr_callout=True, yr_avg_label=True, yr_trend=True)  # Trend is skipped when horizontal


@pytest.mark.parametrize("orient", ["Horizontal", "Vertical"])
@pytest.mark.parametrize("labels", ["None", "Ends", "Length"])
def test_range_bars(orient, labels):
    df = dio.sample_data("Range Bars")
    df.loc[len(df)] = ["2026", 112.0, float("nan")]  # No fall freeze yet
    opts = dict(value_kind="Date", rg_orient=orient, rg_labels=labels, rg_highlight="2025", rg_callout=True,
                y_start_zero=False)
    draw("Range Bars", df, **opts)
    assert charts.summary(df, dict(BASE, chart_type="Range Bars", **opts)).startswith("2025: ")


def test_range_bars_season_across_new_year_and_numbers():
    snow = pd.DataFrame({"Label": ["2023-24", "2024-25"], "Start": [316.0, 333.0], "End": [94.0, 74.0]})  # Nov -> Apr
    s = dict(BASE, chart_type="Range Bars", value_kind="Date", rg_highlight="2024-25")
    d = charts.range_series(snow, s)
    assert (d["End"] > d["Start"]).all()
    # Average dates and average length always agree (Nov 21 to Mar 25 is 124 days)
    assert charts.summary(snow, s) == "2024-25: Nov 29 – Mar 15 (106 days) · average Nov 21 – Mar 25 (124 days)"
    temps = pd.DataFrame({"Label": ["Columbus", "Dayton"], "Start": [41.0, 39.0], "End": [68.0, 66.0]})
    s = dict(BASE, chart_type="Range Bars", value_kind="Number", rg_highlight="", num_suffix="°")
    assert charts.summary(temps, s) == "Average 40° – 67° (27°)"
    draw("Range Bars", temps, value_kind="Number", rg_labels="Length")


def test_range_bars_last_n_rows():
    df = dio.sample_data("Range Bars")
    assert len(charts.range_series(df, dict(BASE, value_kind="Date", rg_last_n=10))) == 10


NAVY_GRAD, BLUE_GRAD = "#045EA8-#022E67", "#59C8FF-#99DDFF"


def drawn_axes(monkeypatch, ct, df, **kw):
    """Render, returning the chart's axes so tests can look at what was drawn."""
    seen = {}
    real = charts._finish
    monkeypatch.setattr(charts, "_finish", lambda fig, ax, *a, **k: seen.setdefault("ax", ax) and real(fig, ax, *a, **k))
    draw(ct, df, **kw)
    return seen["ax"]


@pytest.mark.parametrize("orient", ["Vertical", "Horizontal"])
def test_gradient_bars_and_inside_labels(monkeypatch, orient):
    df = pd.DataFrame({"Label": ["Mon", "Tue", "Wed"], "Value 1": [80, 2, 60], "Value 2": [None] * 3})
    ax = drawn_axes(monkeypatch, "Bar", df, bar_orient=orient, last_c1=BLUE_GRAD, highlight_idx=2,
                    highlight_color=NAVY_GRAD, show_values=True, value_pos="Inside")
    assert len(ax.images) == 3  # One gradient per bar
    labels = {t.get_text(): t for t in ax.texts}
    assert labels["80"].get_color() == "#022E67"  # WI Navy on Highlight Blue
    assert labels["60"].get_color() == "#FFFFFF"  # White on navy
    assert labels["2"].get_color() == "white"  # Too short: past the end, in the axis color
    assert labels["80"].get_position()[1 if orient == "Vertical" else 0] < 80  # Inside the bar


def test_gradient_bars_in_year_ranking_and_range_bars(monkeypatch):
    ax = drawn_axes(monkeypatch, "Year Ranking", dio.sample_data("Year Ranking"), yr_color=NAVY_GRAD, yr_top_n=10)
    assert len(ax.images) >= 10
    ax = drawn_axes(monkeypatch, "Range Bars", dio.sample_data("Range Bars"), rg_color=BLUE_GRAD, value_kind="Date")
    assert ax.images


def test_gradient_colors_become_solid_for_lines():
    draw("Line", pd.DataFrame({"Label": ["a", "b"], "Value 1": [1, 2], "Value 2": [None, None]}), last_c1=NAVY_GRAD,
         highlight_idx=0, highlight_color=BLUE_GRAD)
    draw("Year Ranking", dio.sample_data("Year Ranking"), yr_style="Dots", yr_color=NAVY_GRAD)
