"""Low-memory iCalendar import regression tests."""
import unittest
from datetime import date
from icalendar import Calendar

from google_calendar_import import _calendar_records, _iter_calendar_batches

ICAL = ("BEGIN:VCALENDAR\r\nVERSION:2.0\r\n"
        "BEGIN:VEVENT\r\n"
        "UID:weekly-music\r\n"
        "SUMMARY:Lesson\r\n"
        "DTSTART:20261010T150000Z\r\n"
        "DTEND:20261010T155500Z\r\n"
        "RRULE:FREQ=WEEKLY;COUNT=4\r\n"
        "END:VEVENT\r\n"
        "BEGIN:VEVENT\r\n"
        "UID:other-1\r\nSUMMARY:Other\r\n"
        "DTSTART:20261011T150000Z\r\n"
        "DTEND:20261011T160000Z\r\n"
        "END:VEVENT\r\n"
        "BEGIN:VEVENT\r\n"
        "UID:weekly-music\r\n"
        "SUMMARY:Moved lesson\r\n"
        "RECURRENCE-ID:20261017T150000Z\r\n"
        "DTSTART:20261017T160000Z\r\n"
        "DTEND:20261017T165500Z\r\n"
        "END:VEVENT\r\n"
        "BEGIN:VEVENT\r\n"
        "UID:other-2\r\nSUMMARY:Other 2\r\n"
        "DTSTART:20261012T150000Z\r\n"
        "DTEND:20261012T160000Z\r\n"
        "END:VEVENT\r\n"
        "END:VCALENDAR\r\n").encode("utf-8")


class CalendarBatchImportTests(unittest.TestCase):
    def test_chunks_parse_and_keep_series_exceptions_together(self):
        batches = list(_iter_calendar_batches(ICAL, batch_size=2))
        self.assertGreaterEqual(len(batches), 2)
        parsed = [Calendar.from_ical(raw) for raw in batches]
        all_components = [
            component for cal in parsed for component in cal.walk("VEVENT")
        ]
        self.assertEqual(len(all_components), 4)
        # The recurring master and its changed occurrence must share a batch.
        self.assertTrue(any(
            sum(str(event.get("UID")) == "weekly-music"
                for event in cal.walk("VEVENT")) == 2
            for cal in parsed
        ))

    def test_recurring_override_has_correct_time_after_chunking(self):
        all_records = {}
        for raw in _iter_calendar_batches(ICAL, batch_size=2):
            records, cancelled, _ = _calendar_records(
                raw, "test.ics", date(2026, 10, 1), date(2026, 11, 1)
            )
            self.assertEqual(cancelled, set())
            all_records.update(records)
        self.assertEqual(len(all_records), 6)
        moved = [r for r in all_records.values()
                 if r["title"] == "Moved lesson"]
        self.assertEqual(len(moved), 1)
        self.assertEqual(moved[0]["due"], "2026-10-17")
        self.assertEqual(moved[0]["due_time"], "12:00")

    def test_incomplete_calendar_rejected(self):
        with self.assertRaises(ValueError):
            list(_iter_calendar_batches(
                b"BEGIN:VCALENDAR\r\nBEGIN:VEVENT\r\nUID:a\r\n",
                batch_size=2,
            ))


if __name__ == "__main__":
    unittest.main()
