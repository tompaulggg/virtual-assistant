"""Google Calendar reader — reads events and provides schedule info."""

import os
import logging
from datetime import datetime, timedelta, timezone
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]


class CalendarReader:
    def __init__(self):
        self.creds = None
        self._service = None
        self._init_credentials()

    def _init_credentials(self):
        """Initialize Google Calendar credentials from env vars."""
        client_id = os.getenv("GOOGLE_CLIENT_ID", "")
        client_secret = os.getenv("GOOGLE_CLIENT_SECRET", "")
        refresh_token = os.getenv("GOOGLE_REFRESH_TOKEN", "")

        if not all([client_id, client_secret, refresh_token]):
            logger.warning("Google Calendar credentials not configured")
            return

        try:
            self.creds = Credentials(
                token=None,
                refresh_token=refresh_token,
                client_id=client_id,
                client_secret=client_secret,
                token_uri="https://oauth2.googleapis.com/token",
                scopes=SCOPES,
            )
            self.creds.refresh(Request())
            self._service = build("calendar", "v3", credentials=self.creds)
            logger.info("Google Calendar connected")
        except Exception as e:
            logger.error(f"Google Calendar auth failed: {e}")

    def _get_service(self):
        if not self._service:
            return None
        # Refresh token if expired
        if self.creds and self.creds.expired:
            try:
                self.creds.refresh(Request())
            except Exception as e:
                logger.error(f"Token refresh failed: {e}")
                return None
        return self._service

    def get_today_events(self) -> list[dict]:
        """Get all events for today."""
        return self.get_events_for_date(datetime.now())

    def get_tomorrow_events(self) -> list[dict]:
        """Get all events for tomorrow."""
        return self.get_events_for_date(datetime.now() + timedelta(days=1))

    def get_events_for_date(self, date: datetime) -> list[dict]:
        """Get events for a specific date."""
        service = self._get_service()
        if not service:
            return []

        start = date.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=1)

        # Convert to UTC ISO format
        tz = datetime.now(timezone.utc).astimezone().tzinfo
        start_utc = start.astimezone(timezone.utc).isoformat()
        end_utc = end.astimezone(timezone.utc).isoformat()

        try:
            result = service.events().list(
                calendarId="primary",
                timeMin=start_utc,
                timeMax=end_utc,
                singleEvents=True,
                orderBy="startTime",
            ).execute()

            events = []
            for item in result.get("items", []):
                start_info = item.get("start", {})
                end_info = item.get("end", {})

                # Handle all-day vs timed events
                if "dateTime" in start_info:
                    start_time = start_info["dateTime"]
                    end_time = end_info.get("dateTime", "")
                    all_day = False
                else:
                    start_time = start_info.get("date", "")
                    end_time = end_info.get("date", "")
                    all_day = True

                events.append({
                    "summary": item.get("summary", "Kein Titel"),
                    "start": start_time,
                    "end": end_time,
                    "location": item.get("location", ""),
                    "description": (item.get("description") or "")[:200],
                    "all_day": all_day,
                    "attendees": [
                        a.get("email", "") for a in item.get("attendees", [])
                    ],
                })

            return events
        except Exception as e:
            logger.error(f"Calendar fetch error: {e}")
            return []

    def get_upcoming_events(self, days: int = 7, max_results: int = 20) -> list[dict]:
        """Get upcoming events for the next N days."""
        service = self._get_service()
        if not service:
            return []

        now = datetime.now(timezone.utc).isoformat()
        end = (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()

        try:
            result = service.events().list(
                calendarId="primary",
                timeMin=now,
                timeMax=end,
                singleEvents=True,
                orderBy="startTime",
                maxResults=max_results,
            ).execute()

            events = []
            for item in result.get("items", []):
                start_info = item.get("start", {})
                start_time = start_info.get("dateTime", start_info.get("date", ""))

                events.append({
                    "summary": item.get("summary", "Kein Titel"),
                    "start": start_time,
                    "location": item.get("location", ""),
                })

            return events
        except Exception as e:
            logger.error(f"Upcoming events error: {e}")
            return []

    def format_events(self, events: list[dict], header: str = "") -> str:
        """Format events into a readable string."""
        if not events:
            return f"{header}\nKeine Termine." if header else "Keine Termine."

        lines = []
        if header:
            lines.append(header)

        for e in events:
            if e.get("all_day"):
                time_str = "Ganztägig"
            else:
                # Extract time from ISO datetime
                try:
                    dt = datetime.fromisoformat(e["start"])
                    time_str = dt.strftime("%H:%M")
                    if e.get("end"):
                        dt_end = datetime.fromisoformat(e["end"])
                        time_str += f"-{dt_end.strftime('%H:%M')}"
                except (ValueError, KeyError):
                    time_str = e.get("start", "?")

            line = f"• {time_str} — {e['summary']}"
            if e.get("location"):
                line += f" 📍 {e['location']}"
            lines.append(line)

        return "\n".join(lines)
