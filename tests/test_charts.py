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


def strips(ax):
    return [p for p in ax.patches if not p.get_clip_on() and p.get_facecolor()[:3] == (2 / 255, 46 / 255, 103 / 255)]


@pytest.mark.parametrize("ct", dio.CHART_TYPES)
def test_label_strip_on_every_vertical_chart(monkeypatch, ct):
    kw = dict(bar_orient="Vertical", yr_orient="Vertical", rg_orient="Vertical", x_rot=45, value_kind="Date" if ct == "Range Bars" else "Number")
    ax = drawn_axes(monkeypatch, ct, dio.sample_data(dio.schema_key(ct)), **kw)
    assert len(strips(ax)) == 1
    assert all(t.get_color() == "#FFFFFF" for t in ax.get_xticklabels() if t.get_text())


def test_no_strip_when_off_or_horizontal(monkeypatch):
    df = dio.sample_data("Basic")
    assert not strips(drawn_axes(monkeypatch, "Bar", df, x_label_band=False))
    ax = drawn_axes(monkeypatch, "Bar", df, bar_orient="Horizontal")
    assert not strips(ax) and all(t.get_color() == "white" for t in ax.get_yticklabels())


def test_fonts_by_role():
    """The style guide's weights: Extrabold for data, Bold for labels, Semibold for supporting numbers."""
    fonts, fallback = charts.load_fonts()
    assert fallback is False
    assert {r: Path(f.get_file()).name for r, f in fonts.items()} == {
        "data": "proximanova-extrabold.ttf", "label": "proximanova-bold.ttf", "support": "proximanova-semibold.ttf"}
    assert charts._font_file("NoSuchFont.ttf") is None


def test_chart_text_uses_the_weights_for_its_role(monkeypatch):
    df = pd.DataFrame({"Label": ["Mon", "Tue"], "Value 1": [40, 80], "Value 2": [None, None]})
    ax = drawn_axes(monkeypatch, "Bar", df, show_values=True)
    name = lambda t: Path(t.get_fontproperties().get_file()).name
    assert {name(t) for t in ax.texts} == {"proximanova-extrabold.ttf"}  # Value labels
    assert {name(t) for t in ax.get_xticklabels()} == {"proximanova-bold.ttf"}  # Category names
    assert {name(t) for t in ax.get_yticklabels()} == {"proximanova-semibold.ttf"}  # Numbers
    ax = drawn_axes(monkeypatch, "Bar", df, bar_orient="Horizontal")
    assert {name(t) for t in ax.get_yticklabels()} == {"proximanova-bold.ttf"}
    assert {name(t) for t in ax.get_xticklabels()} == {"proximanova-semibold.ttf"}


def test_missing_fonts_fall_back(monkeypatch):
    monkeypatch.setattr(charts, "_font_file", lambda name: None)
    charts.load_fonts.cache_clear()
    try:
        fonts, fallback = charts.load_fonts()
        assert fallback is True and fonts["data"].get_weight() == "bold" and fonts["support"].get_weight() == "normal"
        draw("Bar", pd.DataFrame({"Label": ["a"], "Value 1": [1], "Value 2": [None]}), show_values=True)
    finally:
        charts.load_fonts.cache_clear()


# --- Fitting the X axis labels ---

CITIES = ["Cincinnati", "Columbus", "Cleveland", "Dayton", "Toledo", "Akron", "Youngstown", "Mansfield", "Zanesville",
          "Wilmington", "Lima", "Springfield"]
AIRPORTS = ["Cincinnati/Northern Kentucky", "Columbus Port Columbus Intl", "Cleveland Hopkins Intl",
            "Dayton Intl Airport", "Toledo Express"]


FULL = dict(width=1920, height=1080)  # A real canvas; the 640-pixel test default is far tighter than anything used on air


def basic(labels):
    return pd.DataFrame({"Label": labels, "Value 1": range(10, 10 + len(labels)), "Value 2": [None] * len(labels)})


def visible_labels(monkeypatch, ct, df, **kw):
    """(text, pixel box) of each category label that ends up on the chart, left to right. Measured just before the
    figure is closed, while it can still be laid out."""
    seen = []
    real_close = charts.plt.close

    def measure_then_close(fig):
        ax = fig.axes[0]
        renderer = fig.canvas.get_renderer()
        lo, hi = sorted(ax.get_xlim())
        ticks = [t.label1 for t in ax.xaxis.get_major_ticks() if lo <= t.get_loc() <= hi and t.label1.get_text()]
        seen.extend((t.get_text(), t.get_window_extent(renderer)) for t in ticks)
        real_close(fig)

    monkeypatch.setattr(charts.plt, "close", measure_then_close)
    draw(ct, df, **kw)
    return sorted(seen, key=lambda item: item[1].x0)


def assert_no_overlap(labels):
    for (a, box_a), (b, box_b) in zip(labels, labels[1:]):
        assert box_a.x1 <= box_b.x0, f"{a!r} runs into {b!r}"


@pytest.mark.parametrize("names, kw", [
    (CITIES, {}),
    (AIRPORTS, {}),
    (CITIES, dict(x_label_band=False)),
    ([str(y) for y in range(1990, 2026)], {}),
    ([str(y) for y in range(1990, 2026)], dict(show_values=True, x_sz=40)),
    ([f"Station {i}" for i in range(30)], {}),
])
def test_x_labels_never_overlap(monkeypatch, names, kw):
    assert_no_overlap(visible_labels(monkeypatch, "Bar", basic(names), **kw))


def test_long_names_wrap_and_every_city_keeps_its_label(monkeypatch):
    shown = [t for t, _ in visible_labels(monkeypatch, "Bar", basic(AIRPORTS), **FULL)]
    assert shown[0] == "Cincinnati/\nNorthern Kentucky" and len(shown) == 5
    cities = [t for t, _ in visible_labels(monkeypatch, "Bar", basic(CITIES), **FULL)]
    assert cities == CITIES  # Names shrink to fit rather than being dropped


def test_years_are_skipped_evenly_and_the_highlighted_one_stays(monkeypatch):
    names = [str(y) for y in range(1990, 2026)]
    shown = [t for t, _ in visible_labels(monkeypatch, "Bar", basic(names), highlight_idx=5, **FULL)]
    assert "1995" in shown and 4 < len(shown) < 36  # 1995 isn't on the regular spacing but is kept


def test_explicit_label_spacing_is_respected(monkeypatch):
    names = [str(y) for y in range(1990, 2026)]
    shown = visible_labels(monkeypatch, "Bar", basic(names), x_label_every="Every 2nd")
    assert len(shown) == 18  # Not thinned further, even where they're tight


def test_rotated_labels_still_draw(monkeypatch):
    assert len(visible_labels(monkeypatch, "Bar", basic(AIRPORTS), x_rot=45, **FULL)) == 5
    assert len(visible_labels(monkeypatch, "Line", basic(CITIES), x_rot=-30, **FULL)) == 12


def test_short_labels_are_left_alone(monkeypatch):
    shown = [t for t, _ in visible_labels(monkeypatch, "Bar", basic(["Mon", "Tue", "Wed", "Thu", "Fri"]))]
    assert shown == ["Mon", "Tue", "Wed", "Thu", "Fri"]


# --- Fixed axis range ---

def axis_limits(monkeypatch, ct, df, horizontal=False, **kw):
    seen = {}
    real_close = charts.plt.close

    def grab(fig):
        ax = fig.axes[0]
        seen["limits"] = ax.get_xlim() if horizontal else ax.get_ylim()
        real_close(fig)

    monkeypatch.setattr(charts.plt, "close", grab)
    draw(ct, df, **kw)
    return seen["limits"]


def test_axis_range_settings(monkeypatch):
    df = basic(["a", "b", "c"]).assign(**{"Value 1": [20, 55, 80]})
    auto = axis_limits(monkeypatch, "Bar", df)
    assert auto[0] == 0 and auto[1] > 80  # Headroom above the tallest bar
    assert axis_limits(monkeypatch, "Bar", df, y_max=100) == (0, 100)
    assert axis_limits(monkeypatch, "Bar", df, y_min=10, y_max=100) == (10, 100)
    assert axis_limits(monkeypatch, "Bar", df, y_min=-20)[0] == -20  # Minimum alone; the top stays automatic
    assert axis_limits(monkeypatch, "Bar", df, y_min=None, y_max=None) == auto
    assert axis_limits(monkeypatch, "Bar", df, y_min=90, y_max=50) == auto  # Reversed: ignored
    assert axis_limits(monkeypatch, "Bar", df, y_max=-5) == auto  # Top below the automatic bottom: ignored
    assert axis_limits(monkeypatch, "Bar", df, horizontal=True, bar_orient="Horizontal", y_max=100) == (0, 100)


@pytest.mark.parametrize("ct", ["Line", "Year Ranking", "Running Total vs Normal", "Record & Normal Band", "Range Bars"])
def test_axis_range_on_every_chart_type(monkeypatch, ct):
    df = dio.sample_data(dio.schema_key(ct))
    kw = dict(rg_orient="Vertical") if ct == "Range Bars" else {}
    assert axis_limits(monkeypatch, ct, df, y_min=-50, y_max=500, **kw) == (-50, 500)


def test_axis_range_ignored_for_dates(monkeypatch):
    df = dio.sample_data("Range Bars")
    auto = axis_limits(monkeypatch, "Range Bars", df, value_kind="Date")
    assert axis_limits(monkeypatch, "Range Bars", df, value_kind="Date", y_min=1, y_max=2) == auto
