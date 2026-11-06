# Backlog

Ideas we've talked through and decided to hold. Not promised; add one when it starts coming up in real use.

## Bar order (sort the bars from the chart's sidebar)

**Why hold:** Year Ranking already ranks, and sorting in Excel before pasting takes seconds. The table can't be sorted by clicking its headers, because Streamlit turns that off for tables where rows can be added or deleted.

**The idea:** an "Order" radio for Bar charts, in the style of Year Ranking's Sorted / By year radio.
- **Choices:** Table order (today's behavior), Highest first, Lowest first, and maybe A–Z.
- **Where:** Canvas & Chart, next to "Bar direction". Bar charts only (a line is usually a sequence, so sorting would scramble it).
- **Chart only:** the table keeps the order you typed, so Table order always brings it back.
- **Details to settle:**
  - the highlighted bar follows its label (it's stored as a row number today);
  - with two series, sort by Series 1;
  - blanks sort last, ties keep table order;
  - on horizontal bars, "Highest first" puts the largest at the top.
- **Size:** about an hour with tests.

## Almanac-style charts (from the NWS Climate Almanac)

**Why hold:** xmACIS and cli-MATE are better at querying, and getting data from them is quick for you. We decided not to build a general query tool.
- Threshold day counts per year (e.g. days at or above 90°) as a Year Ranking option.
- Decadal averages as bars.

## Canvas size presets

**Why hold:** the sizes for the new Weather Impact graphics package aren't known yet.
- When they are: a size dropdown above the Width and Height boxes, with those sizes. The boxes stay for custom sizes.

## More of IEM autoplot #113 for Climo Band

**Why hold:** Climo Band already covers #113's "Daily Maximum / Minimums". Its other options weren't wanted yet.
- **Daily precipitation:** each day's record and average rainfall, with the year's observed amounts.
- **A second observed year:** draw two years together, e.g. this year against last.
- **Daily range:** the spread between each day's high and low, against its normal and record spread.
- **Average highs and lows:** just the normal high and low lines with the observed ones, without the record bands.
