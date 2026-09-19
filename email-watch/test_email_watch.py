#!/usr/bin/env python3
"""Tests for the deterministic parts of email-watch: MIME body selection, .ics parsing and
body cleaning. No network, no database, no model — these run anywhere.

    python3 -m unittest test_email_watch -v
"""
import base64
import unittest

import email_watch as ew


def b64(text):
    return base64.urlsafe_b64encode(text.encode()).decode()


def part(mime, text, filename=None):
    p = {"mimeType": mime, "body": {"data": b64(text)}}
    if filename:
        p["filename"] = filename
    return p


def message(*parts, mime="multipart/mixed"):
    return {"payload": {"mimeType": mime, "body": {}, "parts": list(parts)}}


class BodySelection(unittest.TestCase):

    def test_prefers_plain_over_html_at_any_depth(self):
        msg = message({"mimeType": "multipart/alternative", "body": {}, "parts": [
            part("text/html", "<p>html version</p>"),
            part("text/plain", "plain version"),
        ]})
        self.assertEqual(ew.message_body(msg), "plain version")

    def test_skips_attachment_parts(self):
        """An attached .txt walked before the body must not be returned as the message."""
        msg = message(part("text/plain", "attached spreadsheet dump", filename="data.txt"),
                      part("text/plain", "the actual body"))
        self.assertEqual(ew.message_body(msg), "the actual body")

    def test_singlepart_body(self):
        msg = {"payload": {"mimeType": "text/plain", "body": {"data": b64("just this")}}}
        self.assertEqual(ew.message_body(msg), "just this")


class Calendar(unittest.TestCase):

    ICS = ("BEGIN:VCALENDAR\r\n"
           "METHOD:REQUEST\r\n"
           "BEGIN:VEVENT\r\n"
           "SUMMARY:Dentist \r\n"
           " appointment\r\n"                      # folded: the space before CRLF is content
           "DTSTART;TZID=Europe/London:20260915T090000\r\n"
           "DTEND;TZID=Europe/London:20260915T093000\r\n"
           "LOCATION:12 High St\\, London\r\n"
           "STATUS:CONFIRMED\r\n"
           "END:VEVENT\r\n"
           "END:VCALENDAR\r\n")

    def test_tzid_event_unfolded_and_unescaped(self):
        ev, = ew.parse_ics(self.ICS)
        self.assertEqual(ev["title"], "Dentist appointment")
        self.assertEqual(ev["start"], "2026-09-15T09:00+01:00")
        self.assertEqual(ev["end"], "2026-09-15T09:30+01:00")
        self.assertEqual(ev["location"], "12 High St, London")
        self.assertEqual(ev["tz"], "Europe/London")

    def test_all_day_and_utc_forms(self):
        allday, = ew.parse_ics("BEGIN:VEVENT\nSUMMARY:Trip\nDTSTART;VALUE=DATE:20260920\nEND:VEVENT")
        self.assertEqual(allday["start"], "2026-09-20")
        utc, = ew.parse_ics("BEGIN:VEVENT\nSUMMARY:Call\nDTSTART:20260920T140000Z\nEND:VEVENT")
        self.assertEqual(utc["start"], "2026-09-20T14:00+00:00")
        self.assertEqual(utc["tz"], "UTC")

    def test_cancel_method_marks_event(self):
        ev, = ew.parse_ics(self.ICS.replace("METHOD:REQUEST", "METHOD:CANCEL")
                                   .replace("STATUS:CONFIRMED\r\n", ""))
        self.assertEqual(ev["status"], "CANCEL")

    def test_inline_calendar_part_without_filename_is_found(self):
        """The case google_api misses entirely: an invite whose .ics carries no filename."""
        msg = message(part("text/plain", "See attached invite"),
                      part("text/calendar", self.ICS))
        events = ew.message_calendar(msg)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["title"], "Dentist appointment")


class Cleaning(unittest.TestCase):

    def test_hidden_preheader_is_dropped(self):
        html = ('<div style="display:none;font-size:0">Your weekly deals await you now</div>'
                '<p>Order A123 ships Tuesday</p>')
        out = ew.to_text(html)
        self.assertNotIn("weekly deals", out)
        self.assertIn("Order A123 ships Tuesday", out)

    def test_urls_are_removed_not_marked(self):
        out = ew.to_text("Track it at https://example.com/a?b=c#d now")
        self.assertNotIn("http", out)
        self.assertNotIn("[link]", out)
        self.assertIn("Track it at", out)

    def test_quoted_chain_trimmed_to_a_bounded_tail(self):
        """The reply is what matters, but "yes, Friday works" is meaningless without the
        question it answers, so a bounded tail of the quote stays."""
        body = "Yes, Friday works.\n\nOn 1 Jan 2026, Bob wrote:\n> original question\n> more"
        out = ew.strip_quotes(body)
        self.assertTrue(out.startswith("Yes, Friday works."))
        self.assertIn("original question", out)
        long_thread = "Confirmed.\n\nOn 1 Jan 2026, Bob wrote:\n" + "> filler line\n" * 500
        self.assertLess(len(ew.strip_quotes(long_thread)), ew.QUOTE_KEEP + 100)

    def test_body_quoted_from_line_one_is_kept_whole(self):
        opens_with_quote = "> everything here is quoted\n> still quoted"
        self.assertEqual(ew.strip_quotes(opens_with_quote), opens_with_quote)

    def test_font_size_zero_container_is_not_hidden(self):
        """Measured on real mail: layout cells carry font-size:0 and children set their own.
        Treating that as hidden emptied two 40KB bodies completely."""
        html = ('<table><tr><td style="font-size:0;line-height:0">'
                '<p style="font-size:14px">Your flight BA117 departs 09:40</p></td></tr></table>')
        self.assertIn("BA117", ew.to_text(html))

    def test_html_that_parses_to_nothing_is_retried_without_skip_rules(self):
        html = ('<div style="display:none">'
                + "Real content that is the whole body. " * 40 + "</div>")   # > HTML_RETRY_SOURCE
        self.assertIn("Real content", ew.to_text(html))

    def test_footer_cut_only_once_real_content_precedes_it(self):
        text = "Booking confirmed for 3 October.\n" * 4 + "Unsubscribe from these emails"
        self.assertNotIn("Unsubscribe", ew.strip_footer(text))
        early = "Unsubscribe requests are handled here.\n" + "Details follow.\n" * 6
        self.assertIn("Unsubscribe", ew.strip_footer(early))  # the marker is the subject

    def test_disclaimer_needs_the_back_half_not_just_content_before_it(self):
        """A signature disclaimer sits mid-email with real content below; one fired at 18% of
        an important email and removed 1,123 characters of it."""
        body = ("Please approve the invoice by Friday.\n" * 4
                + "This message is confidential.\n"
                + "The meeting moved to 3pm on 14 October.\n" * 4)
        self.assertIn("14 October", ew.strip_footer(body))
        trailing = "Please approve the invoice by Friday.\n" * 8 + "This message is confidential."
        self.assertNotIn("confidential", ew.strip_footer(trailing))

    def test_repeated_lines_collapse(self):
        self.assertEqual(ew.dedupe_lines("Manage booking\nFlight AB12\nManage booking"),
                         "Manage booking\nFlight AB12")

    def test_budget_keeps_head_and_tail(self):
        text = "S" + "x" * 500 + "E"
        out = ew.budget(text, 100)
        self.assertTrue(out.startswith("S"))
        self.assertTrue(out.endswith("E"))
        self.assertLessEqual(len(out), 100)

    def test_denoise_falls_back_when_rules_strip_everything(self):
        """A body that is one long quote must survive, not come back empty."""
        raw = "Subject line\n" + "On 1 Jan 2026, Bob wrote:\n" + "> quoted detail\n" * 40
        text, plain_chars = ew.denoise(raw)
        self.assertGreater(len(text), ew.DENOISE_FLOOR)
        self.assertGreater(plain_chars, 0)


class Report(unittest.TestCase):

    MAIL = {"id": "abc123", "from": '"British Airways" <no-reply@ba.com>',
            "subject": "Booking confirmed BA117"}

    def block(self, **kw):
        res = {"important": True, "action": "check in online by 19 Sep"}
        res.update(kw.pop("res", {}))
        return ew.block(self.MAIL, res, kw.get("cal", []), kw.get("trips", []),
                        kw.get("todos", []), kw.get("bills", []))

    def test_block_order_and_link(self):
        lines = self.block(cal=["BA117, 20 Sep — added"], trips=["Tokyo, 20 Sep–27 Sep"])
        self.assertEqual(lines[0], "British Airways — Booking confirmed BA117")
        self.assertEqual(lines[1], "Action: check in online by 19 Sep")
        self.assertEqual(lines[2], "Calendar: BA117, 20 Sep — added")
        self.assertEqual(lines[3], "Trip: Tokyo, 20 Sep–27 Sep")
        self.assertTrue(lines[-1].startswith("[Open email](https://mail.google.com/"))

    def test_label_is_not_repeated_per_value(self):
        lines = self.block(todos=["sign contract (due 18 Sep)", "renew passport"])
        todo = [ln for ln in lines if ln.startswith("To-do")]
        self.assertEqual(todo, ["To-do: sign contract (due 18 Sep); renew passport"])

    def test_absent_fields_produce_no_empty_labels(self):
        lines = self.block(res={"action": ""})
        self.assertFalse([ln for ln in lines if ln.rstrip().endswith(":")])
        self.assertEqual(len(lines), 2)          # title and link only

    def test_render_numbers_emails_and_separates_notices(self):
        out = ew.render([self.block(), self.block()], ["Timezone: Europe/London (home)."])
        self.assertIn("Email watch · 2 emails", out)
        self.assertIn("\n**1. British Airways", out)
        self.assertIn("\n**2. British Airways", out)
        self.assertIn("\nAction: check in online by 19 Sep", out)
        self.assertTrue(out.rstrip().endswith("Timezone: Europe/London (home)."))

    def test_deadline_matches_the_date_style_used_everywhere_else(self):
        self.assertEqual(ew.deadline("2027-01-31"), "31 Jan")
        self.assertEqual(ew.deadline("2026-09-20T14:30"), "20 Sep 14:30")
        self.assertEqual(ew.deadline("whenever"), "whenever")   # passed through, not dropped

    def test_render_singular_and_notice_only(self):
        self.assertIn("· 1 email**\n", ew.render([self.block()], []))
        self.assertEqual(ew.render([], ["Timezone: Asia/Tokyo."]), "Timezone: Asia/Tokyo.")
        self.assertEqual(ew.render([], []), "")


if __name__ == "__main__":
    unittest.main()
