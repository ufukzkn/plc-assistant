import tkinter as tk
import unittest
from unittest.mock import patch

from conversation import route, summary
from main import App
from question_corpus import suggest

ROWS = [
    ("CIO110.00", "OUT", "08CC", "FA04 06E0"),
    ("CIO110.01", "OUT", "08D0", "FA04 06E1"),
    ("W11.00", "KEEP", "08D4", "F305 E0B0"),
]
LABELS = {"CIO110.00": "POMPA 1", "W11.00": "ÖRNEK ALARM"}


class SearchTests(unittest.TestCase):
    def test_prefix_ascii_and_typo(self):
        for text in ("çalı", "cali", "çalşııyor mu", "calisyor mu"):
            with self.subTest(text=text):
                self.assertEqual(suggest(text)[0], "çalışıyor mu?")
        self.assertEqual(suggest("rastgele metin"), [])
        self.assertEqual(suggest("çalışıyor mu?"), [])

    def test_address_and_label_suggestions_route_to_the_right_row(self):
        for query in ("CIO110.00 çalı", "çalı CIO110.00", "pompa"):
            with self.subTest(query=query):
                proposed = suggest(query, ROWS, LABELS)[0]
                self.assertEqual(proposed, "CIO110.00 çalışıyor mu?")
                self.assertEqual(route(proposed, ROWS, labels=LABELS), ROWS[0])
        self.assertEqual(suggest("CIO110.00 veya W11.00", ROWS, LABELS), [])
        self.assertNotIn("CIO110.00 çalışıyor mu?", suggest("pompa", ROWS + ROWS[:1], LABELS))
        self.assertEqual(suggest("alarm", ROWS, LABELS, "CIO110.00")[0], "hangi alarmlar var?")

    def test_status_followup_uses_current_row(self):
        self.assertEqual(suggest("çalı", ROWS, LABELS, "W11.00")[0], "W11.00 çalışıyor mu?")
        current = route("çalışıyor mu?", ROWS, current=ROWS[0], labels=LABELS)
        answer = summary(current, ROWS, {}, {"CIO110.00": 1}, LABELS, "çalışıyor mu?")
        self.assertIn("CIO110.00 — POMPA 1: aktif (1)", answer)
        with self.assertRaises(ValueError):
            route("çalışıyor mu?", ROWS, labels=LABELS)


class QuestionEntryTests(unittest.TestCase):
    def setUp(self):
        try:
            self.app = App()
        except tk.TclError as error:
            if "display" not in str(error):
                raise
            self.skipTest(f"Tk ekranı kullanılamıyor: {error}")
        self.addCleanup(self.app.root.destroy)
        self.app.rows = ROWS
        self.app.labels = LABELS
        self.app.render()
        self.app.root.update()

    def test_main_entry_suggest_accept_and_submit(self):
        form = self.app.question_entry
        form.entry.focus_force()
        self.app.root.update()
        self.app.question.set("çalı")
        self.app.root.update()
        self.assertTrue(form.panel.winfo_viewable())
        self.assertEqual(form.choices.get(0), "çalışıyor mu?")
        form.entry.event_generate("<Escape>")
        self.app.root.update()
        self.assertFalse(form.panel.winfo_viewable())
        self.app.question.set("CIO110.00 çalı")
        self.app.root.update()
        form.entry.event_generate("<Down>")
        form.entry.event_generate("<Return>")
        self.app.root.update()
        self.assertEqual(self.app.question.get(), "CIO110.00 çalışıyor mu?")
        self.assertFalse(form.panel.winfo_viewable())
        with patch("main.open_detail") as open_detail:
            form.entry.event_generate("<Return>")
            self.app.root.update()
            open_detail.assert_called_once_with(self.app, ROWS[0], auto=True, question="CIO110.00 çalışıyor mu?")

    def test_detail_entry_accepts_followup_and_cleans_up_on_close(self):
        from detail import open_detail
        from question_entry import QuestionEntry

        original_children = set(self.app.root.winfo_children())
        open_detail(self.app, ROWS[0])
        self.app.root.update()
        window, = set(self.app.root.winfo_children()) - original_children

        def walk(widget):
            yield widget
            for child in widget.winfo_children():
                yield from walk(child)

        form = next(widget for widget in walk(window) if isinstance(widget, QuestionEntry))
        form.variable.set("çalı")
        self.app.root.update()
        self.assertEqual(form.choices.get(0), "CIO110.00 çalışıyor mu?")
        form.entry.focus_force()
        form.entry.event_generate("<Tab>")
        self.app.root.update()
        self.assertEqual(form.variable.get(), "CIO110.00 çalışıyor mu?")
        form.entry.event_generate("<Return>")
        self.app.root.update()
        self.assertFalse(form.variable.get())
        window.destroy()
        self.assertEqual(form.variable.trace_info(), [])
