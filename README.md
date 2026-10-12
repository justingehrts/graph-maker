# Max Graph Maker

A Streamlit app for building chart graphics for on-air weather segments, exported as transparent PNGs for import into Max.

## Features

- Enter data in the table, paste cells straight from Excel/Google Sheets, or import a CSV/Excel file (first column = labels, next 1–2 columns = numbers)
- Bar or line charts with one or two series, a highlighted point, and optional data labels
- ★ Climate presets (pick them in the Chart Type row at the top) that can pull a station's full daily history from the Iowa Environmental Mesonet and are styled after IEM's own autoplots:
  - **Running Total vs Normal** (like #172): season-to-date rain or snow against normal, with the range of all years and the highest/lowest years
  - **Record & Normal Band** (like #113): daily highs and lows over warm/cool record bands and the normal range, for a month or a full year, with new records marked
  - **Year Ranking** (like #107 / #189): every year on record, by year or sorted, with one year highlighted and ranked (e.g. "5th wettest of 133 years"), an average line and an optional trend line
- Import the data behind any IEM autoplot by pasting the autoplot's page link
- Number formatting: decimal places, prefix/suffix units (e.g. `°`, `%`, `"`), thousands separators
- Control over size, fonts, colors (with brand color presets), gridlines, axis interval and label rotation
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
