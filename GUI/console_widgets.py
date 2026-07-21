# -*- coding: utf-8 -*-
"""
console_widgets.py

qtpy replacement for the Tk ANSIColorTextWidget + ConsoleRedirector pair.

One change here is not just cosmetic: in the Tk version, ConsoleRedirector.write()
could be called from backend_thread (since MBUTY_GUI's pipeline prints directly
via redirected stdout while running in a worker thread) and wrote straight into
the Tk Text widget from that thread. Tk mostly tolerates this in practice, but
it's not actually safe, and Qt is much less forgiving about it — touching a
QWidget from a non-GUI thread can corrupt state or crash outright, not just
misbehave. So ConsoleWriter here emits a Signal instead of touching the widget
directly. Qt signal emission is thread-safe by design, and connecting it with
Qt.QueuedConnection guarantees the slot that actually inserts text always runs
on the GUI thread — regardless of which thread called .write(). This is the
same class of problem as the dashboard-threading discussion earlier, solved
the same way (never touch GUI objects off the GUI thread), just via Qt's
native mechanism instead of a manual queue + polling loop.

Also folds in what used to be the separate `line_numbered_text.py` widget.
That module existed specifically to show line numbers next to the
redirected-stdout console — i.e. it was never a general-purpose text
editor, it was *this* widget's gutter. So rather than keep two widgets in
sync, the gutter lives directly on ANSIConsole. It uses the standard Qt
"code editor" pattern: a small side QWidget whose paintEvent is driven by
ANSIConsole's own blockCountChanged/updateRequest signals, so it always
repaints in step with scrolling and new output — no manual redraw calls
needed anywhere else in the app.
"""
import re

from qtpy.QtCore import QObject, Signal, Qt, QRect, QSize
from qtpy.QtGui import QTextCharFormat, QColor, QTextCursor, QPainter
from qtpy.QtWidgets import QPlainTextEdit, QWidget

from . import theme


ANSI_ESCAPE_PATTERN = re.compile(r'\x1b\[([0-9;]+)m')

COLOR_MAP = {
    '30': 'black', '31': 'red', '32': 'green', '33': 'yellow',
    '34': 'blue', '35': 'magenta', '36': 'cyan', '37': 'white',
    '90': 'gray', '91': 'lightcoral', '92': 'lightgreen', '93': 'lightyellow',
    '94': 'lightblue', '95': 'plum', '96': 'lightcyan', '97': 'white',
}


class _LineNumberArea(QWidget):
    """Thin side widget that just forwards paint events back to the console —
    it has no state of its own, ANSIConsole owns the drawing logic."""

    def __init__(self, console):
        super().__init__(console)
        self.console = console

    def sizeHint(self):
        return QSize(self.console.line_number_area_width(), 0)

    def paintEvent(self, event):
        self.console.line_number_area_paint_event(event)


class ANSIConsole(QPlainTextEdit):
    """
    A read-only console widget that interprets basic ANSI color/bold escape
    codes, styled as a monospace log panel via theme.py's "console" role.

    Parameters:
        show_line_numbers (bool): show the line-number gutter (default True,
            since this widget's main job is displaying redirected stdout
            and line numbers make it much easier to reference/report a
            specific line of pipeline output).
        theme_manager (ThemeManager, optional): if given, the gutter's
            colors follow light/dark mode changes automatically.
    """

    def __init__(self, parent=None, max_block_count=10000, show_line_numbers=True, theme_manager=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setProperty("role", "console")
        self.setMaximumBlockCount(max_block_count)  # caps memory growth on long runs
        self._default_format = QTextCharFormat()

        self.show_line_numbers = show_line_numbers
        self._gutter_bg = QColor(theme.LIGHT["surface_alt"])
        self._gutter_fg = QColor(theme.LIGHT["text_secondary"])

        if self.show_line_numbers:
            self._line_number_area = _LineNumberArea(self)
            self.blockCountChanged.connect(self._update_line_number_area_width)
            self.updateRequest.connect(self._update_line_number_area)
            self._update_line_number_area_width(0)

        if theme_manager is not None:
            theme_manager.theme_changed.connect(self._on_theme_changed)
            self._on_theme_changed(theme_manager.mode)

    def _on_theme_changed(self, mode):
        palette = theme.LIGHT if mode == "light" else theme.DARK
        self._gutter_bg = QColor(palette["surface_alt"])
        self._gutter_fg = QColor(palette["text_secondary"])
        if self.show_line_numbers:
            self._line_number_area.update()

    # ------------------------------------------------------------------
    # line-number gutter (standard QPlainTextEdit pattern)
    # ------------------------------------------------------------------
    def line_number_area_width(self):
        digits = len(str(max(1, self.blockCount())))
        return 10 + self.fontMetrics().horizontalAdvance('9') * digits

    def _update_line_number_area_width(self, _new_block_count):
        self.setViewportMargins(self.line_number_area_width(), 0, 0, 0)

    def _update_line_number_area(self, rect, dy):
        if dy:
            self._line_number_area.scroll(0, dy)
        else:
            self._line_number_area.update(0, rect.y(), self._line_number_area.width(), rect.height())
        if rect.contains(self.viewport().rect()):
            self._update_line_number_area_width(0)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.show_line_numbers:
            cr = self.contentsRect()
            self._line_number_area.setGeometry(
                QRect(cr.left(), cr.top(), self.line_number_area_width(), cr.height())
            )

    def line_number_area_paint_event(self, event):
        painter = QPainter(self._line_number_area)
        painter.fillRect(event.rect(), self._gutter_bg)

        block = self.firstVisibleBlock()
        block_number = block.blockNumber()
        top = round(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        bottom = top + round(self.blockBoundingRect(block).height())

        painter.setPen(self._gutter_fg)
        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                painter.drawText(
                    0, top, self._line_number_area.width() - 4, self.fontMetrics().height(),
                    Qt.AlignRight, str(block_number + 1),
                )
            block = block.next()
            top = bottom
            bottom = top + round(self.blockBoundingRect(block).height())
            block_number += 1

    def write(self, string):
        """
        Parse `string` for ANSI escape codes and append it with matching
        formatting. Safe to call only from the GUI thread — use ConsoleWriter
        below if output originates on a worker thread.
        """
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.End)

        parts = ANSI_ESCAPE_PATTERN.split(string)
        current_format = QTextCharFormat(self._default_format)

        for i, part in enumerate(parts):
            if i % 2 == 0:
                if part:
                    cursor.insertText(part, current_format)
            else:
                codes = part.split(';')
                for code in codes:
                    if code == '0':
                        current_format = QTextCharFormat(self._default_format)
                    elif code in COLOR_MAP:
                        current_format.setForeground(QColor(COLOR_MAP[code]))
                    elif code == '1':
                        current_format.setFontWeight(700)

        self.setTextCursor(cursor)
        self.ensureCursorVisible()

    def clear_console(self):
        self.clear()


class ConsoleWriter(QObject):
    """
    A drop-in `sys.stdout` replacement. Unlike the Tk ConsoleRedirector,
    this is safe to install while the pipeline is running in a background
    thread — write() only emits a signal, the connected slot does the
    actual widget update on the GUI thread.

        console = ANSIConsole()
        writer = ConsoleWriter()
        writer.text_written.connect(console.write, Qt.QueuedConnection)
        sys.stdout = writer
    """
    text_written = Signal(str)

    def __init__(self, original_stdout=None):
        super().__init__()
        self._fallback = original_stdout

    def write(self, string):
        self.text_written.emit(string)

    def flush(self):
        pass  # nothing to flush; Qt's event loop delivers the queued signal