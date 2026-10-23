"""Weather Impact 2.0 palette: the only colors allowed for text, axes, gridlines, bars and lines."""
import re

PALETTE = {"White": "#FFFFFF", "WI Navy": "#022E67", "Highlight Blue": "#59C8FF", "Breaking Red": "#D71B32",
           "Blue": "#285DA3", "Yellow": "#FFD633", "Green": "#2ECC71", "Coral": "#FF6B6B", "Gray": "#A3BCC6"}
TEXT_COLORS = {"White": PALETTE["White"], "WI Navy": PALETTE["WI Navy"]}  # Axes, axis labels, data labels, call-outs
GRID_PALETTE = {n: PALETTE[n] for n in ("White", "WI Navy", "Gray")}
# Bar gradients, stored as "#END-#BASE": the first color is at the bar's value end, the second at its base
GRADIENTS = {"Navy Gradient": "#045EA8-#022E67", "Highlight Blue Gradient": "#59C8FF-#99DDFF",
             "Red Gradient": "#D71B32-#8D181F"}
BAR_PALETTE = {**PALETTE, **GRADIENTS}
# The palette color that stands in for a gradient where a solid color is needed (lines, dots)
_GRADIENT_SOLID = {"#045EA8-#022E67": PALETTE["WI Navy"], "#59C8FF-#99DDFF": PALETTE["Highlight Blue"],
                   "#D71B32-#8D181F": PALETTE["Breaking Red"]}


def gradient_stops(color):
    """(end color, base color) for a gradient value, or None for a solid color."""
    return tuple(color.split("-")) if color in _GRADIENT_SOLID else None


def solid(color):
    """A solid color for `color`: itself, or the palette color behind a gradient."""
    return _GRADIENT_SOLID.get(color, color)


def _luminance(hex_val):
    """WCAG relative luminance."""
    channels = [int(hex_val[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    r, g, b = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_text(color):
    """White or WI Navy, whichever reads better on `color` (a gradient counts as the average of its two ends)."""
    lum = sum(map(_luminance, gradient_stops(color) or (color,))) / len(gradient_stops(color) or (color,))
    ratio = lambda t: (max(lum, _luminance(t)) + 0.05) / (min(lum, _luminance(t)) + 0.05)
    return max(TEXT_COLORS.values(), key=ratio)


def nearest_color(hex_val, allowed):
    """(name, hex) of the allowed color closest to `hex_val` in RGB."""
    rgb = lambda h: tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))
    target = rgb(hex_val)
    allowed = {n: h for n, h in allowed.items() if len(h) == 7}  # Gradients are never a nearest match
    return min(allowed.items(), key=lambda item: sum((a - b) ** 2 for a, b in zip(rgb(item[1]), target)))


def snap_settings(settings, sets):
    """Snap off-palette colors in `settings` (in place) to the closest allowed color.

    `sets` maps each restricted setting to its allowed {name: hex}. Returns the changes as "#OLD → Name" notes.
    """
    if settings.get('text_choice') in ("Black", "Navy"):  # Earlier text choices
        settings['text_choice'] = "WI Navy"
    notes = []
    for k, allowed in sets.items():
        v = settings.get(k)
        if isinstance(v, str) and re.fullmatch(r'#[0-9A-Fa-f]{6}', v) and v.upper() not in allowed.values():
            name, settings[k] = nearest_color(v.upper(), allowed)
            notes.append(f"{v.upper()} → {name}")
    return sorted(set(notes))
