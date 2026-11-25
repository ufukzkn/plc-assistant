"""A Tk question entry with local, keyboard-accessible suggestions."""
import tkinter as tk
from tkinter import ttk


class QuestionEntry(ttk.Frame):
    def __init__(self, parent, variable, suggest, submit):
        super().__init__(parent)
        self.variable = variable
        self.suggest = suggest
        self.submit = submit
        self.entry = ttk.Entry(self, textvariable=variable)
        self.entry.pack(fill="x")
        self.panel = ttk.Frame(self)
        ttk.Label(self.panel, text="Şunu mu demek istediniz?").pack(anchor="w")
        self.choices = tk.Listbox(self.panel, height=1, exportselection=False,
                                  activestyle="none", takefocus=False)
        self.choices.pack(fill="x")
        self.choices.bind("<ButtonRelease-1>", self._click)
        self.entry.bind("<Down>", lambda _: self._move(1))
        self.entry.bind("<Up>", lambda _: self._move(-1))
        self.entry.bind("<Tab>", self._tab)
        self.entry.bind("<Escape>", self._escape)
        self.entry.bind("<Return>", self._enter)
        self.trace = variable.trace_add("write", self.refresh)
        self.bind("<Destroy>", self._cleanup)

    def refresh(self, *_):
        values = self.suggest(self.variable.get())
        self.choices.delete(0, tk.END)
        if values:
            self.choices.insert(tk.END, *values)
            self.choices.configure(height=len(values))
            self.panel.pack(fill="x", pady=(3, 0))
        else:
            self.panel.pack_forget()

    def _move(self, step):
        size = self.choices.size()
        if not size:
            return None
        selected = self.choices.curselection()
        index = (selected[0] + step) % size if selected else (0 if step > 0 else size - 1)
        self.choices.selection_clear(0, tk.END)
        self.choices.selection_set(index)
        self.choices.see(index)
        return "break"

    def _accept(self, index):
        self.variable.set(self.choices.get(index))
        self._hide()
        self.entry.icursor(tk.END)
        self.entry.focus_set()

    def _click(self, event):
        index = self.choices.nearest(event.y)
        if self.choices.size() and 0 <= index < self.choices.size():
            self._accept(index)
        return "break"

    def _tab(self, _):
        if self.choices.size():
            selected = self.choices.curselection()
            self._accept(selected[0] if selected else 0)
            return "break"
        return None

    def _hide(self):
        self.panel.pack_forget()
        self.choices.delete(0, tk.END)

    def _escape(self, _):
        if self.choices.size():
            self._hide()
            return "break"
        return None

    def _enter(self, _):
        selected = self.choices.curselection()
        if selected:
            self._accept(selected[0])
        else:
            self._hide()
            self.submit()
        return "break"

    def _cleanup(self, event):
        if event.widget is self:
            self.variable.trace_remove("write", self.trace)
