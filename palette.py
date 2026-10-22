"""Weather Impact 2.0 palette: the only colors allowed for text, axes, gridlines, bars and lines."""
import re

PALETTE = {"White": "#FFFFFF", "WI Navy": "#022E67", "Highlight Blue": "#59C8FF", "Breaking Red": "#D71B32",
           "Blue": "#285DA3", "Yellow": "#FFD633", "Green": "#2ECC71", "Coral": "#FF6B6B", "Gray": "#A3BCC6"}
TEXT_COLORS = {"White": PALETTE["White"], "WI Navy": PALETTE["WI Navy"]}  # Axes, axis labels, data labels, call-outs
GRID_PALETTE = {n: PALETTE[n] for n in ("White", "WI Navy", "Gray")}


def nearest_color(hex_val, allowed):
    """(name, hex) of the allowed color closest to `hex_val` in RGB."""
    rgb = lambda h: tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))
    target = rgb(hex_val)
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
