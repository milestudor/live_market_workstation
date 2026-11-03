# Part 4.1 demonstration · 30–60 seconds

Record the actual localhost app with the Yahoo feed active. If the chosen stocks are closed or quiet, state that openly and use the captured Yahoo replay; the submission still needs live-streaming evidence. Do not substitute the synthetic browser fixture for a live-provider demonstration.

Suggested 50-second walkthrough:

1. **0–12 s:** Show a selected symbol and updating Yahoo candlesticks. Point to source age and the connection panel; explain that connection status and data freshness differ.
2. **12–22 s:** Change to another symbol and a 5-minute interval. Show historical volume and the current bar's finality/coverage. If after-hours volume is unavailable, say so.
3. **22–38 s:** Switch to Replay. Scrub, play/pause, and return to Live. Explain that SQLite records each receipt and immutable revisions, and replay excludes later corrections.
4. **38–50 s:** Show database counters and one verification decision: duplicate receipts do not add volume, or later revisions cannot leak into earlier replay. Briefly show the test result if time allows.

For an unavailable-feed observation: stop the backend (browser reconnect warning) or run with `MARKET_LIVE=0` (explicit offline condition). A provider connection failure is also covered in automated tests. Distinguish the offline exercise from a real Yahoo outage.

Upload the combined demonstration/process video to an instructor-accessible host. Paste the link in `report.md`, verify access, and replace its submitted-commit placeholder with the commit from `git rev-parse HEAD`. No video has been recorded or uploaded by this app build.
