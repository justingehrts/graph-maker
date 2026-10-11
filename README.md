# Max Graph Maker

A Streamlit app for building bar and line chart graphics for on-air weather graphics, exported as transparent PNGs for import into Max.

## Features

- Enter data in the table, paste cells straight from Excel/Google Sheets, or import a CSV/Excel file (first column = labels, next 1–2 columns = numbers)
- Bar or line charts with one or two series, a highlighted point, and optional data labels
- Number formatting: decimal places, prefix/suffix units (e.g. `°`, `%`, `"`), thousands separators
- Control over size, fonts, colors (with brand color presets), gridlines, axis interval and label rotation
- No titles or legends: those are added in Max
- Download the chart as a transparent PNG
- Save and reload your data and settings as a project (JSON) file

## Running locally

Requires Python 3.11+.

```bash
pip install -r requirements.txt
streamlit run app.py
```

Then open http://localhost:8501.

## Running in GitHub Codespaces

Opening the repo in a Codespace installs the requirements and starts the app automatically (see `.devcontainer/devcontainer.json`).

That configuration starts Streamlit with CORS and XSRF protection turned off, which file uploads need behind the Codespaces proxy. Don't reuse those flags for a public deployment.

## Fonts

The app uses Proxima Nova (`ProximaNova-Regular.ttf`, `ProximaNova-Bold.ttf`) when the files are in the repo folder, and falls back to the default sans-serif font when they aren't. Proxima Nova is a commercial font, so make sure you're licensed to use and distribute it.
