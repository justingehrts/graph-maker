# Station weather basemap (Mapbox)

`station-basemap.json` is a Mapbox GL style that recreates the station's weather-map basemap:
dark gray land, black county and state lines, gold interstates that relax to tan when zoomed in,
white boxed town names (wide view) and yellow street names (tight view).

`build_style.py` generates it (edit colors/widths at the top, then `python build_style.py`).
`preview.html` loads it with a token; serve this folder (`python -m http.server`) and open it.

## Using it in Mapbox Studio
Studio can't import raw style JSON through the UI, so either use the JSON directly in Mapbox GL JS
(`new mapboxgl.Map({style: <this json>})`) or create it via the Styles API (`POST /styles/v1/{user}`).

## Things to know
- **County lines** use `mapbox.boundaries-adm2-v3` (Mapbox Boundaries, may need to be enabled on the account).
  Free alternative: upload Census `cb_*_us_county_500k` as a tileset and point the `counties` source and `source-layer` at it.
- **Fonts:** `DIN Pro Bold` stands in for the station font; upload the real one in Studio and swap `FONT_BOLD`.
- **Label boxes:** the station's dark boxes are approximated with a heavy text halo. True rectangles need
  a stretchable 9-slice sprite with `icon-text-fit`.
- **Which towns show** is driven by `symbolrank` in the `place-labels` layer, so it won't match the station's
  hand-picked list exactly. For an exact list, filter on `["in", ["get","name"], ["literal", [...]]]`.
- **Shields** come from the `streets-v12` sprite (Mapbox's own interstate/US/state shield art).
- The style was validated against the Mapbox style spec but not rendered (no Mapbox token in this session).
