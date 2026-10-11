"""Chart rendering (matplotlib -> transparent PNG). No Streamlit here."""
import io
import math
import os
from functools import lru_cache

import matplotlib
matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.font_manager as fm
import matplotlib.pyplot as plt
import pandas as pd

from data_io import format_number
from iem import ordinal, rank_of, record_counts

HERE = os.path.dirname(os.path.abspath(__file__))
GRID_STYLES = {"Solid": "-", "Dashed": "--", "Dotted": ":"}
MARKERS = {"Circle": "o", "Square": "s", "Triangle": "^", "Diamond": "D"}
MAX_Y_TICKS = 50
MAX_YEAR_LABELS = 25  # Year Ranking: label every year only up to this many bars


@lru_cache(maxsize=1)
def load_fonts():
    """Return (regular, bold, using_fallback). FontProperties doesn't check the file, so check it here."""
    reg, bold = os.path.join(HERE, "ProximaNova-Regular.ttf"), os.path.join(HERE, "ProximaNova-Bold.ttf")
    if os.path.isfile(reg) and os.path.isfile(bold):
        return fm.FontProperties(fname=reg), fm.FontProperties(fname=bold), False
    return fm.FontProperties(family='sans-serif'), fm.FontProperties(family='sans-serif', weight='bold'), True


def _font(bold):
    reg, b, _ = load_fonts()
    return b if bold else reg


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


# --- Shared styling ---

def _new_figure(s):
    fig, ax = plt.subplots(figsize=(s['width'] / 100, s['height'] / 100), dpi=100)
    fig.patch.set_alpha(0)
    ax.set_facecolor('none')
    return fig, ax


def _label_kw(s, txt_col):
    return dict(color=txt_col, fontproperties=_font(s['value_bold']), fontsize=s['value_sz'])


def _style_y(ax, s, txt_col, y_lo, y_hi):
    """Y range, interval (widened if it would draw too many ticks), number format and fonts. Returns the interval used."""
    ax.set_ylim(y_lo, y_hi)
    y_step = nice_step(y_lo, y_hi) if s['y_auto'] else max(s['y_step'], (y_hi - y_lo) / MAX_Y_TICKS)
    ax.yaxis.set_major_locator(plt.MultipleLocator(y_step))
    # Whole-number intervals get whole-number labels (10, not 10.00) whatever the data-label decimals are
    axis_s = dict(s, num_decimals="0") if float(y_step).is_integer() and s['num_decimals'] != "Auto" else s
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: format_number(v, axis_s, units=s['axis_units'])))
    ax.tick_params(axis='y', colors=txt_col, width=3, length=8, zorder=4)
    return y_step


def _finish(fig, ax, s, txt_col, y_lo, y_hi):
    """Fonts, spines, zero line and gridlines shared by every chart; returns PNG bytes."""
    ax.tick_params(axis='x', colors=txt_col, width=3, length=8, zorder=4)
    for tick in ax.get_yticklabels():
        tick.set_fontproperties(_font(s['y_bold'])); tick.set_fontsize(s['y_sz']); tick.set_color(txt_col)
    for tick in ax.get_xticklabels():
        tick.set_fontproperties(_font(s['x_bold'])); tick.set_fontsize(s['x_sz']); tick.set_color(txt_col)
        tick.set_rotation(s['x_rot'])
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    for side in ['left', 'bottom']:
        ax.spines[side].set_linewidth(4); ax.spines[side].set_color(txt_col); ax.spines[side].set_zorder(4)
    if y_lo < 0 < y_hi:
        ax.axhline(0, color=txt_col, linewidth=2, zorder=4)  # Baseline when the data crosses zero
    if s['grid_show']:
        ax.grid(True, axis='y', color=s['grid_color'], alpha=s['grid_alpha'], linewidth=s['grid_width'],
                linestyle=GRID_STYLES[s['grid_style']], zorder=1)
    ax.set_axisbelow(True)
    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", transparent=True)
    plt.close(fig)
    return buf.getvalue()


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


def _callout(ax, text, xy, s, txt_col, ha="center", offset=(0, 30)):
    ax.annotate(text, xy=xy, xytext=offset, textcoords="offset points", ha=ha, va="bottom", zorder=6,
                **_label_kw(s, txt_col))


# --- Basic bar / line ---

def render_basic(df, s, txt_col):
    fig, ax = _new_figure(s)
    labels = df["Label"].tolist()
    v1 = df["Value 1"].tolist()
    v2 = df["Value 2"].tolist() if s['show_v2'] else []
    x = list(range(len(labels)))
    label_kw = _label_kw(s, txt_col)

    # Highlight applies to series 1 at the chosen index
    c1 = [s['last_c1']] * len(v1)
    if s['highlight_idx'] != "None" and s['highlight_idx'] < len(c1):
        c1[s['highlight_idx']] = s['highlight_color']

    y_lo, y_hi = y_limits(v1 + v2, s['y_start_zero'])
    if s['chart_type'] == "Bar":
        width_val = max(0.1, 0.8 - s['bar_gap'])  # Hard floor applied
        if v2:
            bars = [ax.bar([i - width_val/4 for i in x], v1, width=width_val/2, color=c1, zorder=2),
                    ax.bar([i + width_val/4 for i in x], v2, width=width_val/2, color=s['last_c2'], zorder=2)]
        else:
            bars = [ax.bar(x, v1, width=width_val, color=c1, zorder=2)]
        if s['show_values']:
            for r in bars: ax.bar_label(r, labels=[format_number(v, s) for v in r.datavalues], padding=5, **label_kw)
    else:
        m_sym = MARKERS[s['marker_symbol']]
        series = [(v1, s['last_c1'], c1)] + ([(v2, s['last_c2'], [s['last_c2']] * len(v2))] if v2 else [])
        for vals, line_color, marker_colors in series:
            ax.plot(x, vals, color=line_color, linewidth=s['line_width'], zorder=2)
            ax.scatter(x, vals, color=marker_colors, s=s['marker_size']**2, marker=m_sym, zorder=3)
            if s['show_values']:
                offset = (y_hi - y_lo) * 0.03
                for i, v in enumerate(vals):
                    # Labels sit above positive points and below negative ones
                    ax.text(i, v + offset if v >= 0 else v - offset, format_number(v, s), ha='center',
                            va='bottom' if v >= 0 else 'top', zorder=5, **label_kw)

    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    y_step = _style_y(ax, s, txt_col, y_lo, y_hi)
    return _finish(fig, ax, s, txt_col, y_lo, y_hi), y_step


# --- Running total vs normal ---

def running_series(df, s):
    """(dates, observed running total, normal running total), adding up daily amounts when the table holds those."""
    d = df.dropna(subset=["Date"]).sort_values("Date")
    obs, norm = d["Observed"].astype(float), d["Normal"].astype(float)
    if s['rt_input'] == "Daily amounts":
        last = obs.last_valid_index()
        obs = obs.fillna(0).cumsum().where(obs.index <= last) if last is not None else obs
        norm = norm.fillna(0).cumsum()
    return pd.to_datetime(d["Date"]), obs, norm


def render_running_total(df, s, txt_col):
    fig, ax = _new_figure(s)
    dates, obs, norm = running_series(df, s)
    lw = s['line_width']
    ax.plot(dates, norm, color=s['rt_norm_color'], linewidth=max(1, lw * 0.6), linestyle="--", zorder=3)
    both = obs.notna() & norm.notna()
    if both.any():
        ax.fill_between(dates, obs, norm, where=both & (obs >= norm), interpolate=True, color=s['rt_surplus_color'],
                        alpha=s['rt_fill_alpha'], linewidth=0, zorder=2)
        ax.fill_between(dates, obs, norm, where=both & (obs < norm), interpolate=True, color=s['rt_deficit_color'],
                        alpha=s['rt_fill_alpha'], linewidth=0, zorder=2)
    ax.plot(dates, obs, color=s['rt_obs_color'], linewidth=lw, zorder=4, solid_capstyle="round")
    y_lo, y_hi = y_limits(list(obs) + list(norm), s['y_start_zero'])
    if s['rt_callout'] and obs.last_valid_index() is not None:
        i = obs.last_valid_index()
        dep = obs[i] - norm[i]
        text = f"{format_number(abs(dep), s)} {'above' if dep >= 0 else 'below'} normal"
        _callout(ax, text, (dates[i], obs[i]), s, txt_col, ha="right", offset=(-10, 20))
    _date_axis(ax, dates, s)
    y_step = _style_y(ax, s, txt_col, y_lo, y_hi)
    return _finish(fig, ax, s, txt_col, y_lo, y_hi), y_step


# --- Record & normal band ---

def render_record_band(df, s, txt_col):
    fig, ax = _new_figure(s)
    d = df.dropna(subset=["Date"]).sort_values("Date").reset_index(drop=True)
    x = pd.to_datetime(d["Date"])
    alpha = s['rb_band_alpha']
    rec = d[["Record Low", "Record High"]].notna().all(axis=1)
    if rec.any():
        ax.fill_between(x, d["Record Low"], d["Record High"], where=rec, color=s['rb_record_color'], alpha=alpha,
                        linewidth=0, zorder=1.5, step=None)
    nrm = d[["Normal Low", "Normal High"]].notna().all(axis=1)
    if nrm.any():
        ax.fill_between(x, d["Normal Low"], d["Normal High"], where=nrm, color=s['rb_normal_color'],
                        alpha=min(1.0, alpha + 0.3), linewidth=0, zorder=1.6)
    lw = s['line_width']
    if s['rb_style'] == "Bars":
        ok = d[["Actual Low", "Actual High"]].notna().all(axis=1)
        ax.bar(x[ok], (d["Actual High"] - d["Actual Low"])[ok], bottom=d["Actual Low"][ok], width=0.65,
               color=s['rb_high_color'], zorder=3)
    else:
        ax.plot(x, d["Actual High"], color=s['rb_high_color'], linewidth=lw, zorder=3)
        ax.plot(x, d["Actual Low"], color=s['rb_low_color'], linewidth=lw, zorder=3)
    highs, lows = record_counts(d)
    if s['rb_mark_records']:
        size = max(60, (s['marker_size'] * 1.6) ** 2)
        ax.scatter(x[highs], d.loc[highs, "Actual High"], marker="*", s=size, color=s['rb_mark_color'],
                   edgecolors=txt_col, linewidths=1, zorder=5)
        ax.scatter(x[lows], d.loc[lows, "Actual Low"], marker="*", s=size, color=s['rb_mark_color'],
                   edgecolors=txt_col, linewidths=1, zorder=5)
    if s['rb_callout']:
        ax.text(0.01, 0.98, record_text(int(highs.sum()), int(lows.sum())), transform=ax.transAxes, ha="left",
                va="top", zorder=6, **_label_kw(s, txt_col))
    values = d[["Actual High", "Actual Low", "Normal High", "Normal Low", "Record High", "Record Low"]].stack().tolist()
    y_lo, y_hi = y_limits(values, False)
    _date_axis(ax, x, s)
    y_step = _style_y(ax, s, txt_col, y_lo, y_hi)
    return _finish(fig, ax, s, txt_col, y_lo, y_hi), y_step


def record_text(n_highs, n_lows):
    parts = [f"{n} record {kind}{'s' if n != 1 else ''}" for n, kind in [(n_highs, "high"), (n_lows, "low")] if n]
    return " · ".join(parts) or "No records set"


# --- Year ranking ---

def ranking_highlight(df, s):
    """The year to highlight: the setting if present in the table, else the latest year."""
    years = df.dropna(subset=["Value"])["Year"].astype(str)
    if s['yr_highlight'] and s['yr_highlight'] in years.tolist():
        return s['yr_highlight']
    return max(years) if len(years) else None


def rank_text(df, s, year):
    r = rank_of(df, year, highest_first=s['yr_order'] == "Highest first")
    if not r: return None
    rank, tied, count = r
    return f"{'T-' if tied else ''}{ordinal(rank)} {s['yr_word']} of {count} years".strip()


def render_year_ranking(df, s, txt_col):
    fig, ax = _new_figure(s)
    d = df.dropna(subset=["Value"]).copy()
    d["Year"] = d["Year"].astype(str)
    d = d.sort_values(["Value", "Year"], ascending=[s['yr_order'] != "Highest first", True]).reset_index(drop=True)
    hl = ranking_highlight(d, s)
    if s['yr_top_n'] and len(d) > s['yr_top_n']:
        top = d.iloc[:s['yr_top_n']]
        d = top if hl in top["Year"].tolist() else pd.concat([top, d[d["Year"] == hl]], ignore_index=True)
    x = list(range(len(d)))
    vals = d["Value"].tolist()
    is_hl = (d["Year"] == hl).tolist()
    colors = [s['highlight_color'] if h else s['yr_color'] for h in is_hl]
    if s['yr_style'] == "Dots":
        ax.scatter(x, vals, color=colors, s=s['marker_size'] ** 2, zorder=3)
    else:
        ax.bar(x, vals, width=0.7 if len(d) <= 40 else 0.85, color=colors, zorder=2)
    y_lo, y_hi = y_limits(vals, s['y_start_zero'])
    label_all = len(d) <= MAX_YEAR_LABELS
    if s['show_values']:
        offset = (y_hi - y_lo) * 0.02
        for i, v in enumerate(vals):
            if label_all or is_hl[i]:
                ax.text(i, v + offset if v >= 0 else v - offset, format_number(v, s), ha='center',
                        va='bottom' if v >= 0 else 'top', zorder=5, **_label_kw(s, txt_col))
    if s['yr_callout'] and hl in d["Year"].tolist():
        i = is_hl.index(True)
        text = rank_text(df.dropna(subset=["Value"]), s, hl)
        if text:
            # Sit above the bar's own value label when those are on
            _callout(ax, text, (i, vals[i]), s, txt_col, offset=(0, 30 + (s['value_sz'] * 1.8 if s['show_values'] else 0)))
    shown = [i for i in x if label_all or is_hl[i]]
    ax.set_xticks(shown)
    ax.set_xticklabels([d["Year"].iloc[i] for i in shown])
    if len(d): ax.set_xlim(-0.7, len(d) - 0.3)
    y_step = _style_y(ax, s, txt_col, y_lo, y_hi)
    png = _finish(fig, ax, s, txt_col, y_lo, y_hi)
    return png, y_step


RENDERERS = {"Bar": render_basic, "Line": render_basic, "Running Total vs Normal": render_running_total,
             "Record & Normal Band": render_record_band, "Year Ranking": render_year_ranking}


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
        return f"{hl}: {text} ({format_number(value, s)})"
    return None
