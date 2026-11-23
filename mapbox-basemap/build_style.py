"""Generate station-basemap.json, a Mapbox GL style that recreates the station weather map look.

Run: python build_style.py   (writes station-basemap.json next to this file)
"""
import json
from pathlib import Path

# Palette sampled from the station screenshots
LAND = ["interpolate", ["linear"], ["zoom"], 8, "#363738", 11, "#6a6c6e"]
WATER = ["interpolate", ["linear"], ["zoom"], 8, "#25292d", 11, "#4f5458"]
LINE_DARK = "#121212"
GOLD = "#e8a626"
TAN = "#e9d4a8"
LABEL_WHITE = "#f4f4f4"
LABEL_BOX = "#161616"
STREET_YELLOW = "#f6d84c"
FONT_BOLD = ["DIN Pro Bold", "Arial Unicode MS Bold"]

# Mapbox Streets v8 country/state boundaries use worldview filters
WORLDVIEW = ["any", ["==", ["get", "worldview"], "all"], ["in", "US", ["get", "worldview"]]]


def w(*pairs, base=1.5):
    """Zoom-interpolated width: w(5, 1, 10, 4)."""
    expr = ["interpolate", ["exponential", base], ["zoom"]]
    for z, v in pairs:
        expr += [z, v]
    return expr


def road_filter(*classes):
    return ["in", ["get", "class"], ["literal", list(classes)]]


NOT_TUNNEL_BRIDGE = ["!=", ["get", "structure"], "tunnel"]

layers = [
    {"id": "background", "type": "background", "paint": {"background-color": LAND}},
    {
        "id": "water", "type": "fill", "source": "composite", "source-layer": "water",
        "paint": {"fill-color": WATER},
    },
    # County lines (needs Mapbox Boundaries; see README for a free Census-tileset alternative)
    {
        "id": "county-lines", "type": "line", "source": "counties",
        "source-layer": "boundaries_admin_2", "minzoom": 5,
        "filter": ["all", ["==", ["get", "iso_3166_1"], "US"], WORLDVIEW],
        "layout": {"line-join": "round"},
        "paint": {"line-color": LINE_DARK, "line-width": w((5, 0.4), (9, 1), (13, 2)),
                  "line-opacity": 0.85},
    },
    {
        "id": "state-lines", "type": "line", "source": "composite", "source-layer": "admin",
        "filter": ["all", ["==", ["get", "admin_level"], 1], ["==", ["get", "maritime"], "false"],
                   ["==", ["get", "disputed"], "false"], WORLDVIEW],
        "layout": {"line-join": "round", "line-cap": "round"},
        "paint": {"line-color": LINE_DARK, "line-width": w((4, 1.2), (7, 2.5), (12, 5))},
    },
    # Local roads: thin tan, only when zoomed in
    {
        "id": "road-local", "type": "line", "source": "composite", "source-layer": "road",
        "minzoom": 9.5,
        "filter": ["all", road_filter("street", "street_limited", "service", "tertiary", "track"),
                   NOT_TUNNEL_BRIDGE],
        "layout": {"line-join": "round", "line-cap": "round"},
        "paint": {"line-color": TAN, "line-opacity": 0.75, "line-width": w((10, 0.3), (13, 0.8), (16, 2))},
    },
    {
        "id": "road-secondary-primary", "type": "line", "source": "composite", "source-layer": "road",
        "minzoom": 8,
        "filter": road_filter("secondary", "primary"),
        "layout": {"line-join": "round", "line-cap": "round"},
        "paint": {"line-color": TAN, "line-opacity": 0.9, "line-width": w((8, 0.5), (12, 1.5), (16, 4))},
    },
    # Highways: dark casing + gold core that relaxes to tan when zoomed in
    {
        "id": "highway-casing", "type": "line", "source": "composite", "source-layer": "road",
        "filter": road_filter("motorway", "trunk", "motorway_link", "trunk_link"),
        "layout": {"line-join": "round", "line-cap": "round"},
        "paint": {"line-color": LINE_DARK,
                  "line-opacity": ["interpolate", ["linear"], ["zoom"], 9, 0.9, 12, 0],
                  "line-width": w((5, 2.5), (9, 6), (12, 9))},
    },
    {
        "id": "highway", "type": "line", "source": "composite", "source-layer": "road",
        "filter": road_filter("motorway", "trunk", "motorway_link", "trunk_link"),
        "layout": {"line-join": "round", "line-cap": "round"},
        "paint": {"line-color": ["interpolate", ["linear"], ["zoom"], 8, GOLD, 11.5, TAN],
                  "line-width": w((5, 1.2), (9, 3.5), (12, 3), (16, 7))},
    },
    # Labels
    {
        "id": "road-names", "type": "symbol", "source": "composite", "source-layer": "road",
        "minzoom": 11.5,
        "filter": ["all", ["has", "name"], road_filter("street", "street_limited", "tertiary",
                                                       "secondary", "primary", "trunk", "service")],
        "layout": {
            "symbol-placement": "line", "text-field": ["upcase", ["get", "name"]],
            "text-font": FONT_BOLD, "text-size": w((12, 11), (16, 16)),
            "text-letter-spacing": 0.05, "text-max-angle": 30,
        },
        "paint": {"text-color": STREET_YELLOW, "text-halo-color": "#222", "text-halo-width": 1,
                  "text-halo-blur": 0.5},
    },
    {
        "id": "road-shields", "type": "symbol", "source": "composite", "source-layer": "road",
        "minzoom": 6.5,
        "filter": ["all", ["has", "shield"], ["has", "reflen"], ["<=", ["get", "reflen"], 6]],
        "layout": {
            "symbol-placement": ["step", ["zoom"], "point", 11, "line"],
            "symbol-spacing": 400,
            "icon-image": ["image", ["concat", ["get", "shield"], "-", ["to-string", ["get", "reflen"]]]],
            "icon-size": ["interpolate", ["linear"], ["zoom"], 6.5, 0.7, 12, 1],
            "text-field": ["get", "ref"], "text-font": ["DIN Pro Bold", "Arial Unicode MS Bold"],
            "text-size": 11, "text-rotation-alignment": "viewport", "icon-rotation-alignment": "viewport",
        },
        "paint": {"text-color": ["match", ["get", "shield_text_color"], "white", "#fff", "yellow", "#ff0", "#fff"]},
    },
    {
        "id": "place-labels", "type": "symbol", "source": "composite", "source-layer": "place_label",
        "filter": ["all", ["==", ["get", "class"], "settlement"],
                   ["<=", ["get", "symbolrank"],
                    ["step", ["zoom"], 8, 6, 10, 7, 12, 8, 14, 9, 16, 11, 18]]],
        "layout": {
            "text-field": ["upcase", ["get", "name"]], "text-font": FONT_BOLD,
            "text-size": w((5, 11), (8, 14), (12, 20)),
            "text-letter-spacing": 0.03, "text-max-width": 8,
            "symbol-sort-key": ["get", "symbolrank"],
        },
        "paint": {"text-color": LABEL_WHITE, "text-halo-color": LABEL_BOX,
                  "text-halo-width": 3.5, "text-halo-blur": 0},
    },
]

style = {
    "version": 8,
    "name": "Station Weather Basemap",
    "metadata": {"note": "Generated by build_style.py"},
    "center": [-82.8, 40.3], "zoom": 6.4,
    "sources": {
        "composite": {"type": "vector", "url": "mapbox://mapbox.mapbox-streets-v8"},
        "counties": {"type": "vector", "url": "mapbox://mapbox.boundaries-adm2-v3"},
    },
    "sprite": "mapbox://sprites/mapbox/streets-v12",
    "glyphs": "mapbox://fonts/mapbox/{fontstack}/{range}.pbf",
    "layers": layers,
}

out = Path(__file__).with_name("station-basemap.json")
out.write_text(json.dumps(style, indent=2) + "\n")
print(f"wrote {out} ({len(layers)} layers)")
