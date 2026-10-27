"""Chart rendering (matplotlib -> transparent PNG). No Streamlit here."""
import io
import math
import os
import re
from functools import lru_cache

import matplotlib
matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.font_manager as fm
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.patches import Rectangle
from matplotlib.ticker import FixedLocator, MaxNLocator

from data_io import DATE_REF_YEAR, format_number, round_day
from iem import ordinal, rank_of, record_counts
from palette import PALETTE, contrast_text, gradient_stops, solid

HERE = os.path.dirname(os.path.abspath(__file__))
GRID_STYLES = {"Solid": "-", "Dashed": "--", "Dotted": ":"}
MARKERS = {"Circle": "o", "Square": "s", "Triangle": "^", "Diamond": "D"}
MAX_Y_TICKS = 50
STRIP_COLOR, STRIP_TEXT = PALETTE["WI Navy"], PALETTE["White"]  # The X axis label strip
MAX_YEAR_LABELS = 25  # Year Ranking: label every year only up to this many bars


# The style guide's three Proxima Nova weights, by what the text is: Extrabold for key data (value labels, call-outs),
# Bold for labels (X axis names), Semibold for supporting information (Y axis numbers)
FONT_FILES = {"data": "proximanova-extrabold.ttf", "label": "proximanova-bold.ttf", "support": "proximanova-semibold.ttf"}
FALLBACK_WEIGHTS = {"data": "bold", "label": "bold", "support": "normal"}


def _font_file(name):
    """Path to a font file in the fonts folder; None if it's missing."""
    path = os.path.join(HERE, "fonts", name)
    return path if os.path.isfile(path) else None


@lru_cache(maxsize=1)
def load_fonts():
    """Return ({role: FontProperties}, using_fallback). FontProperties doesn't check the file, so check it here."""
    paths = {role: _font_file(name) for role, name in FONT_FILES.items()}
    if all(paths.values()):
        return {role: fm.FontProperties(fname=p) for role, p in paths.items()}, False
    return {role: fm.FontProperties(family='sans-serif', weight=w) for role, w in FALLBACK_WEIGHTS.items()}, True


def _font(role):
    return load_fonts()[0][role]


def y_limits(values, start_zero):
    """Axis range covering all values (positive or negative) with headroom for data labels."""
    values = [v for v in values if pd.notna(v)]
    lo, hi = (min(values), max(values)) if values else (0.0, 10.0)
    if start_zero: lo, hi = min(lo, 0.0), max(hi, 0.0)
    span = (hi - lo) or max(abs(hi), 1.0)
    top = hi + span * (0.25 if hi > 0 else 0.1)
    bottom = 0.0 if (start_zero and lo == 0) else lo - span * (0.25 if lo < 0 else 0.1)
    return bottom, top


def nice_step(lo, hi, max_ticks=10):
    """Smallest round interval (1, 2, 2.5, 5 x 10^n) that gives at most `max_ticks` ticks."""
    span = abs(hi - lo) or 1.0
    raw = span / max_ticks
    mag = 10 ** math.floor(math.log10(raw))
    return next(m * mag for m in (1, 2, 2.5, 5, 10) if m * mag >= raw)


DAY_STEPS = (1, 2, 5, 7, 14, 30, 61, 91)  # Round intervals when the values are dates


def _is_dates(s):
    return s.get('value_kind') == "Date"


def _date_ticks(lo, hi, step):
    """Day-of-year tick positions on calendar-friendly dates: month starts, the 1st and 15th, or weekly."""
    from datetime import date, timedelta
    ref = date(DATE_REF_YEAR, 1, 1)
    keep = {91: lambda d: d.day == 1 and d.month in (1, 4, 7, 10), 61: lambda d: d.day == 1 and d.month % 2 == 1,
            30: lambda d: d.day == 1, 14: lambda d: d.day in (1, 15), 7: lambda d: d.day in (1, 8, 15, 22)}.get(step)
    ticks = []
    for doy in range(math.ceil(lo), math.floor(hi) + 1):
        d = ref + timedelta(days=doy - 1)
        if (keep(d) if keep else doy % step == 0):
            ticks.append(doy)
    return ticks


def _start_zero(s):
    """Force the axis to 0 only for real numbers; day-of-year values have no meaningful zero."""
    return s['y_start_zero'] and not _is_dates(s)


# --- Shared styling ---

def _new_figure(s):
    fig, ax = plt.subplots(figsize=(s['width'] / 100, s['height'] / 100), dpi=100)
    fig.patch.set_alpha(0)
    ax.set_facecolor('none')
    return fig, ax


def _label_kw(s, txt_col):
    return dict(color=txt_col, fontproperties=_font("data"), fontsize=s['value_sz'])


def _style_y(ax, s, txt_col, y_lo, y_hi, axis="y"):
    """Range, interval (widened if it would draw too many ticks) and number format of the value axis, which is Y,
    or X for horizontal charts. Returns the interval used."""
    (ax.set_ylim if axis == "y" else ax.set_xlim)(y_lo, y_hi)
    value_axis = ax.yaxis if axis == "y" else ax.xaxis
    if s['y_auto'] and _is_dates(s):
        y_step = next((d for d in DAY_STEPS if d >= (y_hi - y_lo) / 10), DAY_STEPS[-1])
    else:
        y_step = nice_step(y_lo, y_hi) if s['y_auto'] else max(s['y_step'], (y_hi - y_lo) / MAX_Y_TICKS)
    ticks = _date_ticks(y_lo, y_hi, y_step) if s['y_auto'] and _is_dates(s) else []
    value_axis.set_major_locator(FixedLocator(ticks) if len(ticks) >= 2 else plt.MultipleLocator(y_step))
    # Whole-number intervals get whole-number labels (10, not 10.00) whatever the data-label decimals are
    axis_s = dict(s, num_decimals="0") if float(y_step).is_integer() and s['num_decimals'] != "Auto" else s
    value_axis.set_major_formatter(plt.FuncFormatter(lambda v, _: format_number(v, axis_s, units=s['axis_units'])))
    ax.tick_params(axis=axis, colors=txt_col, width=3, length=8, zorder=4)
    return y_step


MIN_SHRINK = 0.6  # Category names are never shrunk below this fraction of the X label size
_SEQUENCE_LABEL = re.compile(r"\s*[-+−$]?[\d.,]+[%°\"]?\s*")


def _is_sequence_label(text):
    """Years and plain numbers: labels that can be skipped (1990, 1992, …) without losing a name."""
    return _year_of(text) is not None or bool(_SEQUENCE_LABEL.fullmatch(str(text)))


def _label_extent(renderer, text, size, rot):
    """Horizontal pixels a label takes up (all its lines, allowing for rotation)."""
    fp = _font('label').copy()
    fp.set_size(size)
    measure = lambda t: renderer.get_text_width_height_descent(t, fp, False)
    lines = str(text).split("\n")
    width = max(measure(line)[0] for line in lines)
    height = measure("Hg")[1] * 1.2 * len(lines)
    angle = math.radians(rot)
    if abs(math.sin(angle)) > 0.26:  # Tilted past about 15 degrees, neighbors only need their line height apart
        return height / abs(math.sin(angle))
    return width * abs(math.cos(angle)) + height * abs(math.sin(angle))


def _wrap_label(renderer, text, size):
    """The label on two lines, split after a space or "/" where the longer line is shortest (or unchanged)."""
    text = str(text)
    best = None
    for m in re.finditer(r"[ /]", text):
        first, second = text[:m.end()].rstrip(), text[m.end():].lstrip()
        if first and second:
            width = max(_label_extent(renderer, first, size, 0), _label_extent(renderer, second, size, 0))
            if best is None or width < best[0]:
                best = (width, f"{first}\n{second}")
    return best[1] if best else text


def _fit_labels(fig, ax, s, labels, keep, thin):
    """Make the category labels of a vertical chart fit their slots; returns the font size to use for them.

    A label too wide for its slot is wrapped onto two lines (unless labels are rotated). Names that still don't
    fit are shrunk, down to MIN_SHRINK of the size; years and numbers are skipped evenly instead (and so are names
    that can't fit even when shrunk), but only when `thin` (the X Axis Labels choice is Auto). Labels in `keep`
    (highlighted bars) always stay.
    """
    renderer = fig.canvas.get_renderer()
    n, size, rot = len(labels), s['x_sz'], s['x_rot']
    shown = sorted({int(round(t)) for t in ax.get_xticks() if 0 <= round(t) < n and abs(t - round(t)) < 1e-6})
    if not shown:
        return size
    lo, hi = ax.get_xlim()
    axes_width = ax.get_window_extent(renderer).width
    slot = axes_width / abs(hi - lo)
    gaps = sorted(b - a for a, b in zip(shown, shown[1:]))
    step = gaps[len(gaps) // 2] if gaps else 1
    pad = size * 0.4 * fig.dpi / 72
    texts = {i: str(labels[i]) for i in shown}
    keep = {k for k in keep if 0 <= k < n}
    if rot == 0:
        texts = {i: _wrap_label(renderer, t, size) if _label_extent(renderer, t, size, rot) + pad > slot * step else t
                 for i, t in texts.items()}

    def collide(sz):
        """Whether neighboring labels touch, with those at the ends nudged inside the axes (as the strip does)."""
        boxes = []
        for i in shown:
            width = _label_extent(renderer, texts[i], sz, rot)
            left = min(max((i - min(lo, hi)) * slot - width / 2, 0), max(axes_width - width, 0))
            boxes.append((left, left + width))
        return any(a[1] + pad > b[0] for a, b in zip(boxes, boxes[1:]))

    names = not all(_is_sequence_label(labels[i]) for i in shown)
    scale = 1.0
    while collide(size * scale):
        if names and scale > MIN_SHRINK:
            scale = max(MIN_SHRINK, scale * 0.94)
        elif thin and len(shown) > 1:
            step *= 2  # Skip every other label
            fewer = _make_room(set(shown[::2]), keep, step)
            if fewer == shown:  # Only the labels that must stay are left
                break
            shown = fewer
        else:
            break
    ax.set_xticks(shown)
    ax.set_xticklabels([texts.get(i, str(labels[i])) for i in shown])
    ax.set_xlim(lo, hi)
    return size * scale


def _finish(fig, ax, s, txt_col, y_lo, y_hi, zero_line=True, horizontal=False, fit_labels=None):
    """Fonts, spines, zero line and gridlines shared by every chart; returns PNG bytes.

    The "X axis label" settings style the category labels and the "Y axis value" settings the numbers, so on a
    horizontal chart (values along the bottom) they swap axes. Rotation applies to vertical charts only.
    `fit_labels` ({labels, keep, thin}, for vertical charts with one slot per category) wraps, shrinks or skips
    category labels that would overlap.
    """
    x_size = s['x_sz']

    def style_ticks():
        ax.tick_params(axis='y' if horizontal else 'x', colors=txt_col, width=3, length=8, zorder=4)
        values, categories = (ax.get_xticklabels(), ax.get_yticklabels()) if horizontal else (ax.get_yticklabels(), ax.get_xticklabels())
        for tick in values:
            tick.set_fontproperties(_font('support')); tick.set_fontsize(s['y_sz']); tick.set_color(txt_col)
        for tick in categories:
            tick.set_fontproperties(_font('label')); tick.set_fontsize(x_size); tick.set_color(txt_col)
            if not horizontal: tick.set_rotation(s['x_rot'])

    style_ticks()
    if fit_labels and not horizontal:
        fig.tight_layout()  # The axes' final width decides how much room each label has
        x_size = _fit_labels(fig, ax, s, **fit_labels)
        style_ticks()
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    for side in ['left', 'bottom']:
        ax.spines[side].set_linewidth(4); ax.spines[side].set_color(txt_col); ax.spines[side].set_zorder(4)
    if zero_line and y_lo < 0 < y_hi:  # Baseline when the data crosses zero
        (ax.axvline if horizontal else ax.axhline)(0, color=txt_col, linewidth=2, zorder=4)
    if s['grid_show']:
        ax.grid(True, axis='x' if horizontal else 'y', color=s['grid_color'], alpha=s['grid_alpha'], linewidth=s['grid_width'],
                linestyle=GRID_STYLES[s['grid_style']], zorder=1)
    ax.set_axisbelow(True)
    band = s.get('x_label_band') and not horizontal
    if band:  # White category labels centered in a WI Navy strip under the plot
        pad_pt = x_size * 0.45
        ax.tick_params(axis='x', which='both', length=0, pad=pad_pt, labelcolor=STRIP_TEXT)
        ax.spines['bottom'].set_visible(False)
    fig.tight_layout()
    if band:
        _label_strip(fig, ax, pad_pt)
    buf = io.BytesIO()
    fig.savefig(buf, format="png", transparent=True)
    plt.close(fig)
    return buf.getvalue()


def _label_strip(fig, ax, pad_pt):
    """The WI Navy strip behind the X axis labels: as tall as the tallest label (rotated ones too) plus padding."""
    renderer = fig.canvas.get_renderer()
    lo, hi = sorted(ax.get_xlim())
    shown = [t.label1 for t in ax.xaxis.get_major_ticks()
             if lo <= t.get_loc() <= hi and t.label1.get_visible() and t.label1.get_text()]
    pad_px = pad_pt * fig.dpi / 72
    band_px = max((t.get_window_extent(renderer).height for t in shown), default=0) + 2 * pad_px
    if ax.get_window_extent(renderer).y0 < band_px + 4:  # Make room at the bottom of the image
        fig.subplots_adjust(bottom=(band_px + 4) / (fig.get_figheight() * fig.dpi))
    box = ax.get_window_extent(renderer)
    for t in shown:  # A label at the very end of the axis (e.g. "Jan" on a date axis) moves inside the strip
        ext = t.get_window_extent(renderer)
        if ext.x0 < box.x0: t.set_horizontalalignment('left')
        elif ext.x1 > box.x1: t.set_horizontalalignment('right')
    frac = band_px / box.height
    ax.add_patch(Rectangle((0, -frac), 1, frac, transform=ax.transAxes, clip_on=False, color=STRIP_COLOR,
                           linewidth=0, zorder=0.2))


def _date_axis(ax, dates, s):
    """Readable date ticks: months for long spans, a handful of days for short ones (per the Date labels setting)."""
    span = (dates.max() - dates.min()).days if len(dates) else 0
    mode = s['date_labels']
    if mode == "Auto":
        mode = "Month names" if span > 62 else "Month + day"
    if mode == "Month names":
        ax.xaxis.set_major_locator(mdates.MonthLocator())
        fmt = lambda d: f"{d:%b}"
    else:
        step = max(1, -(-span // 8))  # About 8 labels
        ax.xaxis.set_major_locator(mdates.DayLocator(interval=step) if span > 8 else mdates.DayLocator())
        fmt = (lambda d: str(d.day)) if mode == "Day numbers" else (lambda d: f"{d:%b} {d.day}")
    ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: fmt(mdates.num2date(x))))
    if len(dates):
        pad = pd.Timedelta(days=0.6)
        ax.set_xlim(dates.min() - pad, dates.max() + pad)


def _callout(ax, text, xy, s, txt_col, ha="center", offset=(0, 30), va="bottom"):
    ax.annotate(text, xy=xy, xytext=offset, textcoords="offset points", ha=ha, va=va, zorder=6,
                **_label_kw(s, txt_col))


def _categories(ax, labels, shown, horizontal):
    """Category labels at positions 0..n-1; horizontal charts list them top to bottom in table order."""
    n = len(labels)
    if horizontal:
        ax.set_yticks(shown)
        ax.set_yticklabels([labels[i] for i in shown])
        if n: ax.set_ylim(n - 0.4, -0.6)
    else:
        ax.set_xticks(shown)
        ax.set_xticklabels([labels[i] for i in shown])
        if n: ax.set_xlim(-0.6, n - 0.4)


def _paint_gradients(ax, patches, colors, horizontal):
    """Fill bars whose color is a gradient, from its first color at the bar's value end to its second at the base.

    Bars are drawn with solid colors first; a gradient image clipped to each bar then covers it.
    """
    ramp = np.linspace(0, 1, 256)
    for p, c in zip(patches, colors):
        stops = gradient_stops(c)
        x0, y0, w, h = p.get_x(), p.get_y(), p.get_width(), p.get_height()
        if not stops or not all(np.isfinite([x0, y0, w, h])) or w == 0 or h == 0: continue
        # Base (y0 or x0) to value end (y0 + h or x0 + w); flipped extents handle bars below zero
        img = ramp[None, :] if horizontal else ramp[:, None]
        im = ax.imshow(img, cmap=LinearSegmentedColormap.from_list("bar", [stops[1], stops[0]]), aspect="auto",
                       origin="lower", extent=(x0, x0 + w, y0, y0 + h), interpolation="bilinear",
                       zorder=p.get_zorder())
        im.set_clip_path(p)


def _bar(ax, horizontal, pos, length, colors, thick, base=None, zorder=2):
    """Bars (vertical or horizontal) in palette colors or gradients; returns the BarContainer."""
    kw = dict(color=[solid(c) for c in colors], zorder=zorder)
    if horizontal:
        bars = ax.barh(pos, length, height=thick, left=base, **kw)
    else:
        bars = ax.bar(pos, length, width=thick, bottom=base, **kw)
    _paint_gradients(ax, bars.patches, colors, horizontal)
    return bars


def _bar_labels(ax, patches, texts, colors, s, txt_col, horizontal, span):
    """Value labels past each bar's end, or inside it near the end ("Inside" position) in White or WI Navy,
    whichever reads better on the bar. Bars too short for their label get it past the end instead."""
    axis_px = (s['width'] if horizontal else s['height']) * 0.8  # Rough length of the value axis in pixels
    per_px = span / axis_px
    for p, text, c in zip(patches, texts, colors):
        if horizontal:
            pos, start, length = p.get_y() + p.get_height() / 2, p.get_x(), p.get_width()
            text_px = len(text) * s['value_sz'] * 0.62 * 100 / 72
        else:
            pos, start, length = p.get_x() + p.get_width() / 2, p.get_y(), p.get_height()
            text_px = s['value_sz'] * 1.2 * 100 / 72
        if not np.isfinite(length): continue
        end, sign = start + length, 1 if length >= 0 else -1
        pad = per_px * 10
        inside = s.get('value_pos') == "Inside" and abs(length) >= text_px * per_px + 2 * pad
        v = end - sign * pad if inside else end + sign * span * 0.02
        out = sign if not inside else -sign  # Which way the text runs from its anchor
        kw = dict(zorder=5, **_label_kw(s, contrast_text(c) if inside else txt_col))
        if horizontal:
            ax.text(v, pos, text, ha='left' if out > 0 else 'right', va='center', **kw)
        else:
            ax.text(pos, v, text, ha='center', va='bottom' if out > 0 else 'top', **kw)


def _end_label(ax, pos, v, text, s, txt_col, horizontal, pad):
    """A value label just past the end of a bar (above/below it, or right/left of it when horizontal)."""
    kw = dict(zorder=5, **_label_kw(s, txt_col))
    if horizontal:
        ax.text(v + pad if v >= 0 else v - pad, pos, text, ha='left' if v >= 0 else 'right', va='center', **kw)
    else:
        ax.text(pos, v + pad if v >= 0 else v - pad, text, ha='center', va='bottom' if v >= 0 else 'top', **kw)


# --- Basic bar / line ---

MAX_X_LABELS = 25  # More rows than this get every Nth label: readable on air and much faster to draw


def _thinned(n, keep=()):
    """Tick positions for n categories: all of them, or every Nth plus any in `keep`."""
    if n <= MAX_X_LABELS:
        return list(range(n))
    step = math.ceil(n / MAX_X_LABELS)
    return sorted(set(range(0, n, step)) | {k for k in keep if 0 <= k < n})


X_LABEL_STEPS = {"Every label": 1, "Every 2nd": 2, "Every 5th": 5, "Every 10th": 10,
                 "Years ending in 0 or 5": 5, "Years ending in 0": 10}


def _year_of(label):
    m = re.match(r"\s*(\d{4})", str(label))
    return int(m.group(1)) if m else None


def label_positions(labels, s, keep=()):
    """Which category labels to show, per the X Axis Labels setting. `keep` (e.g. a highlighted bar) always shows.

    "Years ending in 0 / 0 or 5" pick labels by their year (works for "2024-25" seasons too); if the labels
    aren't years they fall back to Auto.
    """
    n, mode = len(labels), s.get('x_label_every', "Auto")
    keep = {k for k in keep if k is not None and 0 <= k < n}
    if mode.startswith("Years"):
        years = [_year_of(l) for l in labels]
        if n and all(y is not None for y in years):
            return _make_room({i for i, y in enumerate(years) if y % X_LABEL_STEPS[mode] == 0}, keep, X_LABEL_STEPS[mode])
        mode = "Auto"
    if mode == "Auto":
        return _thinned(n, keep)
    return _make_room(set(range(0, n, X_LABEL_STEPS[mode])), keep, X_LABEL_STEPS[mode])


def _make_room(picked, keep, step):
    """Add the `keep` labels, dropping regular labels too close to them to read (e.g. 2020 next to a kept 2025)."""
    gap = math.ceil(step * 0.6)
    near = {i for i in picked for k in keep if i != k and abs(i - k) < gap}
    return sorted((picked - near) | keep)


def render_basic(df, s, txt_col):
    fig, ax = _new_figure(s)
    labels = df["Label"].tolist()
    v1 = df["Value 1"].tolist()
    v2 = df["Value 2"].tolist() if s['show_v2'] else []
    x = list(range(len(labels)))
    label_kw = _label_kw(s, txt_col)

    # Highlight applies to series 1 at the chosen index
    c1 = [s['last_c1']] * len(v1)
    hl = s['highlight_idx'] if s['highlight_idx'] != "None" and s['highlight_idx'] < len(c1) else None
    if hl is not None:
        c1[hl] = s['highlight_color']

    y_lo, y_hi = y_limits(v1 + v2, _start_zero(s))
    horizontal = s['chart_type'] == "Bar" and s['bar_orient'] == "Horizontal"
    if s['chart_type'] == "Bar":
        width_val = max(0.1, 0.8 - s['bar_gap'])  # Hard floor applied
        c2 = [s['last_c2']] * len(v2)
        if v2:
            bars = [(_bar(ax, horizontal, [i - width_val/4 for i in x], v1, c1, width_val/2), c1),
                    (_bar(ax, horizontal, [i + width_val/4 for i in x], v2, c2, width_val/2), c2)]
        else:
            bars = [(_bar(ax, horizontal, x, v1, c1, width_val), c1)]
        if s['show_values']:
            for r, colors in bars:
                _bar_labels(ax, r.patches, [format_number(v, s) for v in r.datavalues], colors, s, txt_col,
                            horizontal, y_hi - y_lo)
    else:
        m_sym = MARKERS[s['marker_symbol']]
        series = [(v1, solid(s['last_c1']), [solid(c) for c in c1])] + (
            [(v2, solid(s['last_c2']), [solid(s['last_c2'])] * len(v2))] if v2 else [])
        for vals, line_color, marker_colors in series:
            ax.plot(x, vals, color=line_color, linewidth=s['line_width'], zorder=2)
            ax.scatter(x, vals, color=marker_colors, s=s['marker_size']**2, marker=m_sym, zorder=3)
            if s['show_values']:
                offset = (y_hi - y_lo) * 0.03
                for i, v in enumerate(vals):
                    # Labels sit above positive points and below negative ones
                    ax.text(i, v + offset if v >= 0 else v - offset, format_number(v, s), ha='center',
                            va='bottom' if v >= 0 else 'top', zorder=5, **label_kw)

    _categories(ax, labels, label_positions(labels, s, keep=[hl]), horizontal)
    y_step = _style_y(ax, s, txt_col, y_lo, y_hi, axis="x" if horizontal else "y")
    fit = dict(labels=labels, keep={hl} - {None}, thin=s['x_label_every'] == "Auto")
    return _finish(fig, ax, s, txt_col, y_lo, y_hi, horizontal=horizontal, fit_labels=fit), y_step


# --- Running total vs normal (IEM autoplot #172 style) ---

def running_series(df, s):
    """(dates, observed running total, normal running total), adding up daily amounts when the table holds those."""
    d = df.dropna(subset=["Date"]).sort_values("Date")
    obs, norm = d["Observed"].astype(float), d["Normal"].astype(float)
    if s['rt_input'] == "Daily amounts":
        last = obs.last_valid_index()
        obs = obs.fillna(0).cumsum().where(obs.index <= last) if last is not None else obs
        norm = norm.fillna(0).cumsum()
    return pd.to_datetime(d["Date"]), obs, norm


def _optional(df, col):
    """A context column as floats, or None when the table doesn't have it (e.g. pasted official data)."""
    if col not in df.columns: return None
    vals = df[col].astype(float)
    return vals if vals.notna().any() else None


def render_running_total(df, s, txt_col):
    fig, ax = _new_figure(s)
    dates, obs, norm = running_series(df, s)
    d = df.dropna(subset=["Date"]).sort_values("Date")
    lw = s['line_width']
    values = list(obs) + list(norm)
    rmax, rmin = _optional(d, "Range Max"), _optional(d, "Range Min")
    if s['rt_show_envelope'] and rmax is not None and rmin is not None:
        ax.fill_between(dates, rmin, rmax, color=s['rt_env_color'], alpha=s['rt_env_alpha'], linewidth=0, zorder=1.2)
        values += list(rmax) + list(rmin)
    if s['rt_show_extremes']:
        for col, color in (("Highest Year", s['rt_high_color']), ("Lowest Year", s['rt_low_color'])):
            vals = _optional(d, col)
            if vals is not None:
                ax.plot(dates, vals, color=color, linewidth=max(1, lw * 0.6), zorder=2.5)
                values += list(vals)
    ax.plot(dates, norm, color=s['rt_norm_color'], linewidth=max(1, lw * 0.6), linestyle="--", zorder=3)
    both = obs.notna() & norm.notna()
    if s['rt_show_fill'] and both.any():
        ax.fill_between(dates, obs, norm, where=both & (obs >= norm), interpolate=True, color=s['rt_surplus_color'],
                        alpha=s['rt_fill_alpha'], linewidth=0, zorder=2)
        ax.fill_between(dates, obs, norm, where=both & (obs < norm), interpolate=True, color=s['rt_deficit_color'],
                        alpha=s['rt_fill_alpha'], linewidth=0, zorder=2)
    ax.plot(dates, obs, color=s['rt_obs_color'], linewidth=lw, zorder=4, solid_capstyle="round")
    y_lo, y_hi = y_limits(values, s['y_start_zero'])
    if s['rt_callout'] and obs.last_valid_index() is not None:
        i = obs.last_valid_index()
        dep = obs[i] - norm[i]
        text = f"{format_number(abs(dep), s)} {'above' if dep >= 0 else 'below'} normal"
        _callout(ax, text, (dates[i], obs[i]), s, txt_col, ha="right", offset=(-10, 20))
    _date_axis(ax, dates, s)
    y_step = _style_y(ax, s, txt_col, y_lo, y_hi)
    return _finish(fig, ax, s, txt_col, y_lo, y_hi), y_step


# --- Record & normal band (IEM autoplot #113 style) ---

def render_record_band(df, s, txt_col):
    fig, ax = _new_figure(s)
    d = df.dropna(subset=["Date"]).sort_values("Date").reset_index(drop=True)
    x = pd.to_datetime(d["Date"])
    alpha, lw = s['rb_band_alpha'], s['line_width']
    rh, rl, nh, nl = d["Record High"], d["Record Low"], d["Normal High"], d["Normal Low"]
    step = "mid"  # Daily values drawn as day-wide steps, as IEM does
    if s['rb_band_style'] == "Layered":
        # Record high down to normal high (warm), normal range, normal low down to record low (cool)
        warm = rh.notna() & nh.notna()
        cool = rl.notna() & nl.notna()
        if warm.any():
            ax.fill_between(x, nh, rh, where=warm, step=step, color=s['rb_rec_high_color'], alpha=alpha, linewidth=0, zorder=1.4)
        if cool.any():
            ax.fill_between(x, rl, nl, where=cool, step=step, color=s['rb_rec_low_color'], alpha=alpha, linewidth=0, zorder=1.4)
        if s['rb_record_lines']:
            ax.step(x, rh, where=step, color=s['rb_rec_high_line'], linewidth=max(1, lw * 0.2), zorder=1.7)
            ax.step(x, rl, where=step, color=s['rb_rec_low_line'], linewidth=max(1, lw * 0.2), zorder=1.7)
        normal_alpha = alpha
    else:
        rec = rh.notna() & rl.notna()
        if rec.any():
            ax.fill_between(x, rl, rh, where=rec, step=step, color=s['rb_record_color'], alpha=alpha, linewidth=0, zorder=1.5)
        normal_alpha = min(1.0, alpha + 0.3)
    nrm = nl.notna() & nh.notna()
    if nrm.any():
        ax.fill_between(x, nl, nh, where=nrm, step=step, color=s['rb_normal_color'], alpha=normal_alpha,
                        linewidth=0, zorder=1.6)
    if s['rb_style'] == "Bars":
        ok = d[["Actual Low", "Actual High"]].notna().all(axis=1)
        ax.bar(x[ok], (d["Actual High"] - d["Actual Low"])[ok], bottom=d["Actual Low"][ok], width=0.8,
               color=s['rb_bar_color'], zorder=3)
    else:
        ax.plot(x, d["Actual High"], color=s['rb_high_color'], linewidth=lw, zorder=3)
        ax.plot(x, d["Actual Low"], color=s['rb_low_color'], linewidth=lw, zorder=3)
    highs, lows = record_counts(d)
    if s['rb_mark_records']:
        star = s['rb_mark_shape'] == "Star"
        size = max(40, (s['marker_size'] * (1.6 if star else 1.0)) ** 2)
        for mask, col in ((highs, "Actual High"), (lows, "Actual Low")):
            ax.scatter(x[mask], d.loc[mask, col], marker="*" if star else "o", s=size, color=s['rb_mark_color'],
                       edgecolors=txt_col if star else "#022E67", linewidths=1.5, zorder=5)
    if s['rb_callout']:
        ax.text(0.01, 0.98, record_text(int(highs.sum()), int(lows.sum())), transform=ax.transAxes, ha="left",
                va="top", zorder=6, **_label_kw(s, txt_col))
    values = d[["Actual High", "Actual Low", "Normal High", "Normal Low", "Record High", "Record Low"]].stack().tolist()
    lo, hi = (min(values), max(values)) if values else (0.0, 100.0)
    pad = (hi - lo or 10) * 0.05
    y_lo, y_hi = lo - pad, hi + pad * (3 if s['rb_callout'] else 1)  # Snug, like IEM; room for the call-out
    _date_axis(ax, x, s)
    y_step = _style_y(ax, s, txt_col, y_lo, y_hi)
    return _finish(fig, ax, s, txt_col, y_lo, y_hi, zero_line=False), y_step


def record_text(n_highs, n_lows):
    parts = [f"{n} record {kind}{'s' if n != 1 else ''}" for n, kind in [(n_highs, "high"), (n_lows, "low")] if n]
    return " · ".join(parts) or "No records set"


# --- Year ranking (IEM autoplot #107 / #189 style) ---

def ranking_highlight(df, s):
    """The year to highlight: the setting if present in the table, else the latest year."""
    years = df.dropna(subset=["Value"])["Year"].astype(str)
    if s['yr_highlight'] and s['yr_highlight'] in years.tolist():
        return s['yr_highlight']
    return max(years) if len(years) else None


def rank_text(df, s, year):
    r = rank_of(df, year, highest_first=s['yr_rank_dir'] == "Highest")
    if not r: return None
    rank, tied, count = r
    return f"{'T-' if tied else ''}{ordinal(rank)} {s['yr_word']} of {count} years".strip()


def _year_numbers(labels):
    """Starting year of each label ("2024-25" -> 2024), or None if any label has no year."""
    nums = labels.str.extract(r"^(\d{4})")[0]
    return None if nums.isna().any() else nums.astype(int)


def render_year_ranking(df, s, txt_col):
    fig, ax = _new_figure(s)
    full = df.dropna(subset=["Value"]).copy()
    full["Year"] = full["Year"].astype(str)
    hl = ranking_highlight(full, s)
    years = _year_numbers(full["Year"])
    horizontal = s['yr_orient'] == "Horizontal" and s['yr_style'] != "Line"
    by_year = s['yr_order'] == "By year" and years is not None
    if by_year:
        d = full.assign(_x=years).sort_values("_x").reset_index(drop=True)
    else:
        d = full.sort_values(["Value", "Year"], ascending=[s['yr_rank_dir'] == "Lowest", True]).reset_index(drop=True)
        if s['yr_top_n'] and len(d) > s['yr_top_n']:
            top = d.iloc[:s['yr_top_n']]
            d = top if hl in top["Year"].tolist() else pd.concat([top, d[d["Year"] == hl]], ignore_index=True)
    # Vertical by-year charts put the years on a numeric axis; everything else uses one slot per row
    numeric_years = by_year and not horizontal
    x = d["_x"].tolist() if numeric_years else list(range(len(d)))
    vals = d["Value"].tolist()
    is_hl = (d["Year"] == hl).tolist()
    colors = [s['yr_hl_color'] if h else s['yr_color'] for h in is_hl]
    bars = None
    if s['yr_style'] == "Dots":
        ax.scatter(*((vals, x) if horizontal else (x, vals)), color=[solid(c) for c in colors],
                   s=s['marker_size'] ** 2, zorder=3)
    elif s['yr_style'] == "Line":
        ax.plot(x, vals, color=solid(s['yr_color']), linewidth=max(1, s['line_width'] * 0.5), zorder=2.5)
        ax.scatter(x, vals, color=[solid(c) for c in colors], s=s['marker_size'] ** 2, zorder=3)
    else:
        bars = _bar(ax, horizontal, x, vals, colors, 0.8 if by_year or len(d) > 40 else 0.7)
    y_lo, y_hi = y_limits(vals, _start_zero(s))
    label_kw = _label_kw(s, txt_col)
    if s['yr_avg_line'] and len(full):
        avg = full["Value"].mean()
        (ax.axvline if horizontal else ax.axhline)(avg, color=s['yr_avg_color'], linewidth=max(1, s['line_width'] * 0.4), zorder=4)
        if s['yr_avg_label']:
            if horizontal:
                ax.annotate(f"Avg: {format_number(avg, s)}", xy=(avg, 0), xycoords=("data", "axes fraction"),
                            xytext=(6, 6), textcoords="offset points", ha="left", va="bottom", zorder=6, **label_kw)
            else:
                ax.annotate(f"Avg: {format_number(avg, s)}", xy=(1, avg), xycoords=("axes fraction", "data"),
                            xytext=(-6, 6), textcoords="offset points", ha="right", va="bottom", zorder=6, **label_kw)
    if s['yr_trend'] and numeric_years and len(d) > 2:
        slope, intercept = np.polyfit(d["_x"], d["Value"], 1)
        xs = np.array([d["_x"].min(), d["_x"].max()])
        ax.plot(xs, intercept + slope * xs, color=s['yr_trend_color'], linewidth=max(1, s['line_width'] * 0.4),
                linestyle="--", zorder=4)
        rate = (f"{slope * 10:+.1f} days".replace("-", "\u2212") if _is_dates(s)
                else format_number(slope * 10, s, signed=True))
        # Below the line, so it doesn't collide with the average label above
        ax.annotate(f"{rate} per decade", xy=(xs[-1], intercept + slope * xs[-1]),
                    xytext=(-6, -10), textcoords="offset points", ha="right", va="top", zorder=6, **label_kw)
    label_all = len(d) <= MAX_YEAR_LABELS
    if s['show_values']:
        shown = [i for i, h in enumerate(is_hl) if label_all or h]
        if bars is not None:
            _bar_labels(ax, [bars.patches[i] for i in shown], [format_number(vals[i], s) for i in shown],
                        [colors[i] for i in shown], s, txt_col, horizontal, y_hi - y_lo)
        else:
            for i in shown:
                _end_label(ax, x[i], vals[i], format_number(vals[i], s), s, txt_col, horizontal, (y_hi - y_lo) * 0.02)
    if s['yr_callout'] and hl in d["Year"].tolist():
        i = is_hl.index(True)
        text = rank_text(full, s, hl)
        if text:
            if horizontal:  # Past the end of the bar (and its value label)
                _callout(ax, text, (vals[i], x[i]), s, txt_col, ha="left", va="center",
                         offset=(12 + (s['value_sz'] * 3.5 if s['show_values'] else 0), 0))
            else:  # Above the bar's own value label when those are on
                _callout(ax, text, (x[i], vals[i]), s, txt_col,
                         offset=(0, 30 + (s['value_sz'] * 1.8 if s['show_values'] else 0)))
    mode = s.get('x_label_every', "Auto")
    fit = None
    if numeric_years:
        # Years are the axis values here, so "every 5th" and "ending in 0 or 5" are the same thing
        ax.xaxis.set_major_locator(MaxNLocator(nbins=10, integer=True) if mode == "Auto"
                                   else plt.MultipleLocator(X_LABEL_STEPS[mode]))
        if len(x): ax.set_xlim(min(x) - 1, max(x) + 1)
    else:
        keep = [is_hl.index(True)] if any(is_hl) else []
        shown = ([i for i in x if label_all or is_hl[i]] if mode == "Auto" and not by_year
                 else label_positions(d["Year"].tolist(), s, keep=keep))
        _categories(ax, d["Year"].tolist(), shown, horizontal)
        fit = dict(labels=d["Year"].tolist(), keep=set(keep), thin=mode == "Auto")
    y_step = _style_y(ax, s, txt_col, y_lo, y_hi, axis="x" if horizontal else "y")
    return _finish(fig, ax, s, txt_col, y_lo, y_hi, horizontal=horizontal, fit_labels=fit), y_step


# --- Range bars (floating bars, e.g. growing season per year; IEM autoplot #10 style) ---

def range_series(df, s):
    """Rows to draw (last N if set) with Start and End; dates whose End is before Start continue into next year."""
    d = df.dropna(subset=["Start"]).reset_index(drop=True)
    d = d.assign(Label=d["Label"].astype(str), Start=d["Start"].astype(float), End=d["End"].astype(float))
    if _is_dates(s):
        d.loc[d["End"] < d["Start"], "End"] += 365  # A Nov-Apr season ends in the following year
    if s['rg_last_n'] and len(d) > s['rg_last_n']:
        d = d.iloc[-s['rg_last_n']:].reset_index(drop=True)
    return d


def range_length_text(start, end, s):
    """Length of a range: whole days between the dates as shown, or the difference for numbers."""
    if pd.isna(start) or pd.isna(end): return ""
    return f"{round_day(end) - round_day(start)} days" if _is_dates(s) else format_number(end - start, s)


def range_highlight(d, s):
    return s['rg_highlight'] if s['rg_highlight'] in d["Label"].tolist() else None


def render_range_bars(df, s, txt_col):
    fig, ax = _new_figure(s)
    d = range_series(df, s)
    horizontal = s['rg_orient'] == "Horizontal"
    hl = range_highlight(d, s)
    pos = list(range(len(d)))
    start, end = d["Start"].tolist(), d["End"].tolist()
    colors = [s['rg_hl_color'] if l == hl else s['rg_color'] for l in d["Label"]]
    full = d["End"].notna()
    if full.any():
        _bar(ax, horizontal, d.index[full], d.loc[full, "End"] - d.loc[full, "Start"],
             [c for c, f in zip(colors, full) if f], 0.7, base=d.loc[full, "Start"])
    open_rows = ~full  # No end yet (e.g. this year's fall freeze hasn't happened): mark the start only
    if open_rows.any():
        pts = (d.loc[open_rows, "Start"], d.index[open_rows])
        ax.scatter(*(pts if horizontal else pts[::-1]), marker="|" if horizontal else "_", s=(s['marker_size'] * 2) ** 2,
                   linewidths=4, color=[solid(c) for c, o in zip(colors, open_rows) if o], zorder=3)
    values = start + [e for e in end if pd.notna(e)]
    lo, hi = (min(values), max(values)) if values else (0.0, 10.0)
    span = (hi - lo) or 10.0
    # Snug like IEM's plots, with room past the ends for labels / call-out when they're on
    room = 0.18 if (s['rg_labels'] != "None" or s['rg_callout']) else 0.04
    y_lo = lo - span * (room if s['rg_labels'] == "Ends" else 0.04)
    y_hi = hi + span * room
    if _start_zero(s): y_lo = min(y_lo, 0.0)
    pad = (y_hi - y_lo) * 0.01
    if s['rg_avg_lines'] and len(d):
        for avg in (np.nanmean(start), np.nanmean([e for e in end if pd.notna(e)] or [np.nan])):
            if pd.notna(avg):
                (ax.axvline if horizontal else ax.axhline)(avg, color=s['rg_avg_color'], linestyle="--",
                                                           linewidth=max(1, s['line_width'] * 0.3), zorder=4)
    kw = dict(zorder=5, **_label_kw(s, txt_col))
    for i in pos:
        if s['rg_labels'] == "Ends":
            texts = [(start[i], format_number(start[i], s), -1)] + ([(end[i], format_number(end[i], s), 1)] if pd.notna(end[i]) else [])
        elif s['rg_labels'] == "Length" and pd.notna(end[i]):
            texts = [(end[i], range_length_text(start[i], end[i], s), 1)]
        else:
            texts = []
        for v, text, side in texts:
            if horizontal:
                ax.text(v + side * pad, i, text, ha='left' if side > 0 else 'right', va='center', **kw)
            else:
                ax.text(i, v + side * pad, text, ha='center', va='bottom' if side > 0 else 'top', **kw)
    if s['rg_callout'] and hl is not None:
        i = d["Label"].tolist().index(hl)
        if pd.notna(end[i]):
            text = range_length_text(start[i], end[i], s)
            extra = s['value_sz'] * 3.5 if s['rg_labels'] != "None" else 0
            if horizontal:
                _callout(ax, text, (end[i], i), s, txt_col, ha="left", va="center", offset=(12 + extra, 0))
            else:
                _callout(ax, text, (i, end[i]), s, txt_col, offset=(0, 20 + (s['value_sz'] * 1.6 if extra else 0)))
    names = d["Label"].tolist()
    keep = [names.index(hl)] if hl else []
    _categories(ax, names, label_positions(names, s, keep=keep), horizontal)
    y_step = _style_y(ax, s, txt_col, y_lo, y_hi, axis="x" if horizontal else "y")
    fit = dict(labels=names, keep=set(keep), thin=s['x_label_every'] == "Auto")
    return _finish(fig, ax, s, txt_col, y_lo, y_hi, horizontal=horizontal, zero_line=not _is_dates(s), fit_labels=fit), y_step


RENDERERS = {"Bar": render_basic, "Line": render_basic, "Running Total vs Normal": render_running_total,
             "Record & Normal Band": render_record_band, "Year Ranking": render_year_ranking,
             "Range Bars": render_range_bars}


def render(df, s, txt_col):
    """Draw the chart for `s['chart_type']`. Returns (png bytes, Y interval actually used)."""
    return RENDERERS[s['chart_type']](df, s, txt_col)


def summary(df, s):
    """One-line numbers for the preset charts (to type into Max), or None for basic charts."""
    ct = s['chart_type']
    if ct == "Running Total vs Normal":
        dates, obs, norm = running_series(df, s)
        i = obs.last_valid_index()
        if i is None or pd.isna(norm[i]): return None
        dep = obs[i] - norm[i]
        pct = f" ({obs[i] / norm[i] * 100:.0f}% of normal)" if norm[i] > 0 else ""
        return (f"Through {dates[i]:%b} {dates[i].day}: observed {format_number(obs[i], s)} · normal "
                f"{format_number(norm[i], s)} · {format_number(dep, s, signed=True)}{pct}")
    if ct == "Record & Normal Band":
        d = df.dropna(subset=["Date"])
        highs, lows = record_counts(d)
        avg, norm = (d["Actual High"] + d["Actual Low"]) / 2, (d["Normal High"] + d["Normal Low"]) / 2
        known = avg.notna() & norm.notna()
        above = int((avg[known] > norm[known]).sum())
        return f"{record_text(int(highs.sum()), int(lows.sum()))} · {above} of {int(known.sum())} days above normal"
    if ct == "Year Ranking":
        d = df.dropna(subset=["Value"])
        hl = ranking_highlight(d, s)
        text = rank_text(d, s, hl) if hl else None
        if not text: return None
        value = d.loc[d["Year"].astype(str) == hl, "Value"].iloc[0]
        return f"{hl}: {text} ({format_number(value, s)}) · average {format_number(d['Value'].mean(), s)}"
    if ct == "Range Bars":
        d = range_series(df, s)
        if d.empty: return None
        both = d.dropna(subset=["End"])
        a_start, a_end = both["Start"].mean(), both["End"].mean()
        avg = (f"average {format_number(a_start, s)} – {format_number(a_end, s)} "
               f"({range_length_text(a_start, a_end, s)})") if len(both) else ""
        hl = range_highlight(d, s)
        if hl is None: return avg[:1].upper() + avg[1:] or None
        row = d[d["Label"] == hl].iloc[0]
        span = (f"{format_number(row['Start'], s)} – {format_number(row['End'], s)} "
                f"({range_length_text(row['Start'], row['End'], s)})" if pd.notna(row["End"])
                else f"{format_number(row['Start'], s)} – (no end yet)")
        return f"{hl}: {span}" + (f" · {avg}" if avg else "")
    return None
