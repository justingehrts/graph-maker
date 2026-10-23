# Max Graph Maker

A Streamlit app for building chart graphics for on-air weather segments, exported as transparent PNGs for import into Max.

## Features

- Enter data in the table, paste cells straight from Excel/Google Sheets, or import a CSV/Excel file (first column = labels, next 1–2 columns = numbers)
- Bar or line charts with one or two series, a highlighted point, and optional data labels, which can sit past the end of each bar or inside it (in White or WI Navy, whichever reads better on the bar)
- ★ Climate presets (pick them in the Chart Type row at the top) that can pull a station's full daily history from the Iowa Environmental Mesonet and are styled after IEM's own autoplots:
  - **Running Total vs Normal** (like #172): season-to-date rain or snow against normal, with the range of all years and the highest/lowest years
  - **Record & Normal Band** (like #113): daily highs and lows over warm/cool record bands and the normal range, for a month or a full year, with new records marked
  - **Year Ranking** (like #107 / #189): every year on record, by year or sorted, with one year highlighted and ranked (e.g. "5th wettest of 133 years"), an average line and an optional trend line
  - **Range Bars** (like #10): floating bars from a start to an end. From station data the app builds the growing season for every year: the last spring and first fall low at or below a threshold (32° and below by default, the NWS definition of a freeze)
- Horizontal bars for Bar charts and Year Ranking, suited to sorted top-N lists and named rows (cities, event types)
- Import the data behind any IEM autoplot by pasting the autoplot's page link
- Number formatting: decimal places, prefix/suffix units (e.g. `°`, `%`, `"`), thousands separators
- Control over size, fonts, colors, gridlines, axis interval and label rotation
- Colors follow the Weather Impact 2.0 palette (`palette.py`), chosen by clicking color chiclets:
  - **Text and axes** (including data labels and call-outs): always WI Navy, for Max's white backgrounds. Vertical charts put their X axis labels in white on a WI Navy strip (can be turned off under Axes)
  - **Bars, lines and markers:** WI Navy, Highlight Blue, Breaking Red (for Weather Impact Alert states), Blue, Yellow, Green, Coral or Gray (no White, which would vanish on Max's white background)
  - **Bar gradients:** Navy, Highlight Blue and Red, for Bar charts, Year Ranking and Range Bars; the stronger color is at the bar's end
  - **Gridlines:** White, WI Navy or Gray
  - **Shaded bands** (record and normal ranges, above/below-normal fills) keep their own color pickers for now
  - Older project files with other colors load with each one changed to the closest palette color
- No titles or legends: those are added in Max
- Download the chart as a transparent PNG
- Save and reload your data and settings as a project (JSON) file

## Data sources

**Iowa Environmental Mesonet (IEM)**, Iowa State University: [mesonet.agron.iastate.edu](https://mesonet.agron.iastate.edu/).

- **Presets:** for any state's climate stations, the app downloads the station's full daily record in a single request. It then works out running totals, normals, daily records and yearly rankings itself. "Area" stations are the long-term threaded records for a city.
- **Normals:** two choices.
  - **NCEI 1991–2020** (the default) uses NCEI's official 1991–2020 daily normals, the same ones the NWS daily climate report uses. IEM serves them through autoplots #172 (rain, snow) and #99 (highs, lows).
  - **Full record** uses averages over the station's whole history, as IEM's #113 does.
  - If the official normals can't be had, nothing is drawn with unofficial numbers. The app explains why and offers IEM's averages of the station's own 1991–2020 data instead, labeled as "not official NCEI normals".
- **Records:** IEM's records can also differ slightly from NWS official records.
- **Official numbers:** when you need them, paste or import data from xmACIS, NOWData or another source instead. The table accepts `T` (trace) and `M` (missing), and drops summary rows like "Sum" and "Mean".
- **Dates as values:** a column of dates, such as an xmACIS "last date" per year (`16-Oct`, `Oct 16`, `10/16` or `2025-10-16`), is read as dates. The chart then shows them as "Oct 16", ranks them as latest or earliest, and labels any trend line in days per decade.
- **Autoplot import:** in "Import from an IEM autoplot", paste the address of a plot made at [mesonet.agron.iastate.edu/plotting/auto](https://mesonet.agron.iastate.edu/plotting/auto/). Then choose which of its columns go into the chart. Not every autoplot offers its data for download.

## Running locally

Requires Python 3.11+.

```bash
pip install -r requirements.txt
streamlit run app.py
```

Then open http://localhost:8501.

To run the tests:

```bash
pip install -r requirements-dev.txt
pytest
```

The tests use saved IEM data for Ames, Iowa (`tests/fixtures`) and check the app's calculations against IEM's own published numbers. They don't need a network connection.

## Running in GitHub Codespaces

Opening the repo in a Codespace installs the requirements and starts the app automatically (see `.devcontainer/devcontainer.json`).

That configuration starts Streamlit with CORS and XSRF protection turned off, which file uploads need behind the Codespaces proxy. Don't reuse those flags for a public deployment.

## Fonts

The app uses Proxima Nova (`ProximaNova-Regular.ttf`, `ProximaNova-Bold.ttf`) when the files are in the repo folder, and falls back to the default sans-serif font when they aren't. Proxima Nova is a commercial font, so make sure you're licensed to use and distribute it.
