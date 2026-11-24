"""
ICS Timezone Proxy Server
=========================
Fetches an ICS calendar feed and converts all UTC timestamps to explicit
local time (with TZID), so Galaxy Fit 3 / ICSx5 displays them correctly.

Usage:
	pip install flask requests icalendar pytz

	# Set your timezone (default: America/Los_Angeles)
	export TZ_NAME="America/Los_Angeles"

	python ics_proxy.py

Then in ICSx5, replace your calendar URL with:
	http://<your-phone-ip>:5000/calendar

Or to proxy a specific URL on the fly:
	http://localhost:5000/calendar?url=https://...
"""

import os
import re
import requests
from datetime import datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from flask import Flask, request, Response
from icalendar import Calendar, Event, vDatetime, vText

app = Flask(__name__)

# ── Config ────────────────────────────────────────────────────────────────────

DEFAULT_ICS_URL = (
	"https://csumb.instructure.com/feeds/calendars/"
	"user_Jeg7S6lsObh6z7D9ZHDNxFl2jNgOAR8lX5IqiLAX.ics"
)
TZ_NAME = os.environ.get("TZ_NAME", "America/Los_Angeles")

# ── Helpers ───────────────────────────────────────────────────────────────────

def get_local_tz() -> ZoneInfo:
	try:
		return ZoneInfo(TZ_NAME)
	except ZoneInfoNotFoundError:
		app.logger.warning(f"Unknown timezone '{TZ_NAME}', falling back to UTC")
		return ZoneInfo("UTC")


def convert_dt(dt, local_tz: ZoneInfo):
	"""
	Convert a datetime to the local timezone.
	Handles:
	  - UTC-aware datetimes  (DTSTART:...Z)
	  - Other tz-aware datetimes
	  - Naive datetimes (assumed UTC, as Canvas produces)
	Returns a tz-aware datetime in local_tz, or the original date if it's a date.
	"""
	if not isinstance(dt, datetime):
		# It's a date-only value — leave it alone
		return dt

	if dt.tzinfo is None:
		# Naive → assume UTC
		dt = dt.replace(tzinfo=timezone.utc)

	return dt.astimezone(local_tz)


def fix_calendar(raw_ics: bytes, local_tz: ZoneInfo) -> bytes:
	"""
	Parse the ICS, convert every UTC/naive DTSTART and DTEND to local time,
	and serialise back to bytes.
	"""
	cal = Calendar.from_ical(raw_ics)
	new_cal = Calendar()

	# Copy top-level calendar properties
	for key, value in cal.items():
		new_cal.add(key, value)

	tz_id = str(local_tz)  # e.g. "America/Los_Angeles"

	for component in cal.walk():
		if component.name == "VCALENDAR":
			continue  # already handled above

		new_component = component.__class__()

		for key, value in component.items():
			if key in ("DTSTART", "DTEND", "DUE", "RECURRENCE-ID"):
				raw_dt = component.decoded(key)
				converted = convert_dt(raw_dt, local_tz)

				if isinstance(converted, datetime):
					# Write as floating local time with TZID parameter so
					# clients (ICSx5, Etar, Galaxy Fit 3) treat it as local.
					new_val = vDatetime(converted.replace(tzinfo=None))
					new_val.params["TZID"] = tz_id
					new_component.add(key, new_val)
				else:
					# Date-only — keep as-is
					new_component.add(key, converted)
			else:
				new_component.add(key, value)

		new_cal.add_component(new_component)

	return new_cal.to_ical()


# ── Route ─────────────────────────────────────────────────────────────────────

@app.route("/calendar")
def proxy_calendar():
	ics_url = request.args.get("url", DEFAULT_ICS_URL)
	local_tz = get_local_tz()

	try:
		resp = requests.get(ics_url, timeout=15)
		resp.raise_for_status()
	except requests.RequestException as e:
		return Response(f"Failed to fetch calendar: {e}", status=502)

	try:
		fixed = fix_calendar(resp.content, local_tz)
	except Exception as e:
		app.logger.exception("Error processing ICS")
		return Response(f"Error processing calendar: {e}", status=500)

	return Response(
		fixed,
		status=200,
		mimetype="text/calendar",
		headers={
			"Content-Disposition": 'attachment; filename="calendar.ics"',
			"Cache-Control": "no-cache",
		},
	)


@app.route("/")
def index():
	return (
		f"<h3>ICS Timezone Proxy</h3>"
		f"<p>Timezone: <code>{TZ_NAME}</code></p>"
		f"<p>Default feed: <code>{DEFAULT_ICS_URL}</code></p>"
		f"<p>Subscribe to: <code>http://&lt;this-host&gt;:5000/calendar</code></p>"
		f"<p>Or pass a custom URL: "
		f"<code>http://&lt;this-host&gt;:5000/calendar?url=&lt;ics-url&gt;</code></p>"
	)


if __name__ == "__main__":
	app.run(host="0.0.0.0", port=5000, debug=False)
