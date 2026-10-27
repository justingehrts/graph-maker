# Max Graph Maker

A Streamlit app for building chart graphics for on-air weather segments, exported as transparent PNGs for import into Max.

## Features

- Enter data in the table, paste cells straight from Excel/Google Sheets, or import a CSV/Excel file (first column = labels, next 1–2 columns = numbers)
- Bar or line charts with one or two series, any number of highlighted points, and optional data labels, which can sit past the end of each bar or inside it (in White or WI Navy, whichever reads better on the bar)
- ★ Climate presets (pick them in the Chart Type row at the top) that can pull a station's full daily history from ACIS (the official NWS data behind xmACIS and NOWData) and are styled after IEM's autoplots:
  - **Running Total vs Normal** (like #172): season-to-date rain or snow against normal, with the range of all years and the highest/lowest years
  - **Record & Normal Band** (like #113): daily highs and lows over warm/cool record bands and the normal range, for a month or a full year, with new records marked
  - **Year Ranking** (like #107 / #189): every year on record, by year or sorted, with one year highlighted and ranked (e.g. "5th wettest of 133 years"), an average line and an optional trend line
  - **Range Bars** (like #10): floating bars from a start to an end. From station data the app builds the growing season for every year: the last spring and first fall low at or below a threshold (32° and below by default, the NWS definition of a freeze)
- Horizontal bars for Bar charts and Year Ranking, suited to sorted top-N lists and named rows (cities, event types)
- Import the data behind any IEM autoplot by pasting the autoplot's page link
- Number formatting: decimal places, prefix/suffix units (e.g. `°`, `%`, `"`), thousands separators
- Control over size, colors, gridlines, axis interval and label rotation
- Optional fixed value-axis range (Y minimum and maximum, blank for automatic), e.g. 0 to 100 so percent bars compare from graphic to graphic
- X axis labels fit themselves: long names wrap onto two lines, names that still don't fit shrink, and years or numbers are skipped evenly (highlighted bars always keep their label)
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

**ACIS** (Applied Climate Information System, [data.rcc-acis.org](https://data.rcc-acis.org/)) for the presets: the official NWS station data behind xmACIS, NOWData and the NWS Climate Almanac.

- **Presets:** for any state, the app lists the threaded "Area" stations (a city's long-term record, e.g. Columbus Area since 1878) first, then stations still reporting with at least 30 years of data. It downloads the station's full daily record in one request and works out running totals, normals, daily records and yearly rankings itself.
- **Normals:** two choices.
  - **NCEI 1991–2020** (the default) uses NCEI's official 1991–2020 daily normals from ACIS, the same ones the NWS climate reports use.
  - **Full record** uses averages over the station's whole history, as IEM's #113 does.
  - If the official normals can't be had, nothing is drawn with unofficial numbers. The app explains why and offers the station's own 1991–2020 averages instead, labeled as "not official NCEI normals".
- **If ACIS is down:** the app offers the **Iowa Environmental Mesonet (IEM)**, Iowa State University ([mesonet.agron.iastate.edu](https://mesonet.agron.iastate.edu/)), which has the same station records but can differ slightly from the official numbers. Charts made from it say "IEM (unofficial)" in their source note.
- **Official numbers:** when you need them, paste or import data from xmACIS, NOWData or another source instead. The table accepts `T` (trace) and `M` (missing), and drops summary rows like "Sum" and "Mean". A Rank column (xmACIS's, whether it's numbers or dashes) is left out, since it only numbers the rows.
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

The charts use Proxima Nova in the Weather Impact 2.0 style guide's three weights, from the `fonts` folder: Extrabold for data labels and call-outs, Bold for X axis labels and Semibold for Y axis numbers. The app falls back to the default sans-serif font when those files aren't there. Proxima Nova is a commercial font, so make sure you're licensed to use and distribute it.
