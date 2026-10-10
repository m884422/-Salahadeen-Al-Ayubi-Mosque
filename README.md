# Salahadeen Masjid prayer calendar feed

Subscribable calendar: `https://<your-github-user>.github.io/<repo>/prayer.ics`

## One-time setup (free, ~10 minutes)
1. Create a GitHub repo and upload this folder (keep `.github/`, `docs/`, `data/`, `build_feed.py`, `requirements.txt`).
2. Repo **Settings → Pages → Source: Deploy from a branch → main → /docs**.
3. Repo **Settings → Actions → General → Workflow permissions: Read and write**.
4. Run the **Update prayer calendar** workflow once from the Actions tab.

The workflow then re-runs daily, reads today's Begins/Iqamah times from the mosque homepage and republishes `prayer.ics`.

## Subscribe on iPhone
Settings → Calendar → Accounts → Add Account → Other → **Add Subscribed Calendar** → paste
`webcal://<your-github-user>.github.io/<repo>/prayer.ics` → Save.
Then Calendar → Edit → the calendar → Auto-Refresh: set to the most frequent option.

## Subscribe on Google Calendar
calendar.google.com → Other calendars (+) → **From URL** → paste the `https://…/prayer.ics` link.
Google refreshes subscribed calendars only every few hours to a day, and it does not reliably apply alarms from the feed; set notifications on that calendar yourself (see notes).

## Reminder logic
- Begins time → alarm.
- Iqamah minus 10 min → alarm.
- If Begins and Iqamah are the same time (e.g. Maghrib, Isha) → alarms 10 min before and on time.

## Notes
- Times are stored in UTC inside the file, so every phone shows them in its own timezone (e.g. Quebec time). Reminders fire at the correct moment for Manchester.
- The homepage only shows the current day, so the feed gets one new day per daily run. Days before the first run are not included, and future days appear only as the homepage reaches them.
- If the mosque changes today's times during the day, the next daily run updates that day's events.
- Friday Jumu'ah is not included.
- Test locally: `python3 build_feed.py` (no packages needed).
