"""Compact, native Qt surfaces for the step sequencer.

These classes only display editor state.  The item model retains its ordinary
text, accessibility descriptions and musical data; no playback or editing rules
live in the paint path.

``StepDelegate`` reads the existing UserRole dictionary (enabled, velocity,
allowed) and optional continuing, flam and muted fields.  Its parent should be
the step table, whose ``step_beat`` and ``play_column`` attributes are observed.
``BeatHeader.set_step_beat`` accepts the exact Fraction used by that table.
``StepRowHeader.set_rows`` receives row dictionaries, full labels and short MIDI
addresses.  The header emits row indices, never mutates those dictionaries, and
offers ``button_rect(row, action)`` in viewport coordinates for all five targets.
"""
from __future__ import annotations

import math
from fractions import Fraction

from PySide6.QtCore import QEvent, QPoint, QRect, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPen, QPolygon
from PySide6.QtWidgets import QHeaderView, QStyle, QStyledItemDelegate, QToolTip


CYAN = QColor('#72cadd')
AMBER = QColor('#edbe62')


def _gradient(rect, top, bottom):
    gradient = QLinearGradient(0, rect.top(), 0, rect.bottom())
    gradient.setColorAt(0, QColor(top))
    gradient.setColorAt(1, QColor(bottom))
    return gradient


def _font_scale(widget):
    # Native font metrics follow both interface scaling and the platform's DPI.
    return max(.85, min(1.8, widget.fontMetrics().height() / 16))


class StepDelegate(QStyledItemDelegate):
    """Beveled step buttons with velocity stripes and held-note bridges."""

    def sizeHint(self, option, index):
        scale = max(.85, option.fontMetrics.height() / 16)
        return QSize(round(29 * scale), round(27 * scale))

    def paint(self, painter, option, index):
        values = index.data(Qt.ItemDataRole.UserRole) or {}
        table = self.parent()
        if not hasattr(table, 'play_column'):
            table = option.widget
        step = Fraction(getattr(table, 'step_beat', Fraction(1, 4)))
        group = math.floor(index.column() * step)
        enabled = bool(values.get('enabled'))
        continuing = bool(values.get('continuing', index.data() == '—'))
        allowed = values.get('allowed', True)
        muted = bool(values.get('muted'))
        playing = index.column() == getattr(table, 'play_column', -1)
        selected = bool(option.state & QStyle.StateFlag.State_Selected)
        focused = bool(option.state & QStyle.StateFlag.State_HasFocus)
        current = bool(table is not None and hasattr(table, 'currentIndex') and table.currentIndex() == index)
        painter.save()
        painter.setClipRect(option.rect)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        rect = QRect(option.rect)
        rect.setHeight(min(rect.height(),getattr(table,'button_height',rect.height())))
        painter.fillRect(option.rect,QColor('#292f33'))
        painter.fillRect(rect, QColor('#303538' if group % 2 else '#373c3f'))
        if playing:
            painter.fillRect(rect, QColor(237, 190, 98, 29))
        painter.setPen(QColor('#202426'))
        painter.drawLine(rect.bottomLeft(), rect.bottomRight())
        if index.column() * step % 1 == 0:
            painter.setPen(QColor('#15191b'))
            painter.drawLine(rect.topLeft(), rect.bottomLeft())
        inset = max(2, round(option.fontMetrics.height() / 7))
        pad = rect.adjusted(inset, 4, -inset - 1, -5)
        if pad.width() <= 2 or pad.height() <= 2:
            painter.restore()
            return
        painter.fillRect(pad.adjusted(0, 1, 1, 1), QColor('#171c1f'))
        if enabled or continuing:
            top, bottom = ('#334e54', '#22383d') if not muted else ('#454e51', '#343d40')
        elif not allowed:
            top, bottom = ('#696e71', '#444a4e') if not group % 2 else ('#5b6164', '#3c4245')
        else:
            top, bottom = ('#a0a5a8', '#737a7e') if not group % 2 else ('#838b90', '#5e676c')
        painter.fillRect(pad, _gradient(pad, top, bottom))
        painter.setPen(QColor('#b1b7b9' if not enabled and allowed else '#687b80'))
        painter.drawLine(pad.topLeft(), pad.topRight())
        painter.drawLine(pad.topLeft(), pad.bottomLeft())
        painter.setPen(QColor('#353c40'))
        painter.drawLine(pad.bottomLeft(), pad.bottomRight())
        painter.drawLine(pad.topRight(), pad.bottomRight())
        if enabled:
            velocity = max(0, min(1, float(values.get('velocity', .8))))
            inside = pad.adjusted(3, 3, -3, -3)
            height = max(1, round(inside.height() * velocity))
            ink = QColor('#7e969c') if muted else CYAN
            # Stacked horizontal segments retain the recognizable pad silhouette
            # while making soft notes visibly different from accented attacks.
            painter.setPen(QPen(ink, 1))
            for y in range(inside.bottom(), inside.bottom() - height, -3):
                painter.drawLine(inside.left(), y, inside.right(), y)
            if values.get('flam'):
                painter.setPen(QColor('#d9f4fa' if not muted else '#9ba8ac'))
                painter.drawLine(pad.left() + 3, pad.top() + 3, pad.left() + 3, pad.top() + 6)
                painter.drawLine(pad.left() + 5, pad.top() + 2, pad.left() + 5, pad.top() + 6)
        elif continuing:
            painter.setPen(QPen(QColor('#65878f') if muted else QColor('#5aa0ad'), 2))
            painter.drawLine(rect.left(), pad.center().y(), rect.right(), pad.center().y())
            painter.setPen(QColor('#9bced8'))
            painter.drawLine(pad.left() + 4, pad.center().y() - 2, pad.right() - 4, pad.center().y() - 2)
        elif values.get('events'):
            painter.setPen(QColor('#3a4449'))
            painter.drawPoint(pad.center())
        if not allowed:
            painter.setPen(QPen(AMBER if enabled else QColor('#899195'), 1))
            painter.drawLine(pad.right()-5,pad.top()+3,pad.right()-2,pad.top()+6)
            painter.drawLine(pad.right()-5,pad.top()+6,pad.right()-2,pad.top()+3)
        if selected or current:
            painter.setPen(QPen(QColor('#b5ecf6') if focused or current else QColor('#5d94a1'), 1))
            painter.drawRect(pad.adjusted(-1, -1, 1, 1))
        if playing:
            painter.setPen(QPen(AMBER, 1))
            painter.drawLine(rect.left(), rect.top(), rect.left(), rect.bottom())
            painter.drawLine(rect.right(), rect.top(), rect.right(), rect.bottom())
        painter.restore()


class BeatHeader(QHeaderView):
    """Two-tier exact-beat ruler with one marker per visible step column.

    ``step_beat`` is a public Fraction.  ``set_step_beat`` repaints after a grid
    resolution change; beat numbers remain accurate for non-unit fractions.
    """

    def __init__(self, parent=None):
        super().__init__(Qt.Orientation.Horizontal, parent)
        self.step_beat = Fraction(1, 4)
        self.setSectionsClickable(True)
        self.setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
        self.setDefaultSectionSize(29)
        self.setMinimumSectionSize(20)
        self.setHighlightSections(False)
        self.setAccessibleName('Step sequencer beat ruler')
        self.setAccessibleDescription('Beat numbers above one marker per step. Amber marks the playing column.')
        self.refresh_metrics()

    def set_step_beat(self, value):
        value = Fraction(value)
        if value <= 0:
            raise ValueError('Step length must be positive')
        self.step_beat = value
        self.viewport().update()

    def refresh_metrics(self):
        self.setFixedHeight(round(42 * _font_scale(self)))
        self.updateGeometry()
        self.viewport().update()

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() in (QEvent.Type.FontChange, QEvent.Type.StyleChange) and hasattr(self, 'step_beat'):
            self.refresh_metrics()

    def sizeHint(self):
        return QSize(super().sizeHint().width(), round(42 * _font_scale(self)))

    def _visible_columns(self):
        if self.count() == 0:
            return range(0)
        first = self.logicalIndexAt(0)
        last = self.logicalIndexAt(self.viewport().width() - 1)
        if first < 0:
            first = 0
        if last < 0:
            last = self.count() - 1
        return range(first, last + 1)

    def _beat_x(self, position):
        column = min(self.count() - 1, max(0, math.floor(position / self.step_beat)))
        local = (position - column * self.step_beat) / self.step_beat
        return self.sectionViewportPosition(column) + round(float(local) * self.sectionSize(column))

    def paintEvent(self, event):
        painter = QPainter(self.viewport())
        painter.setClipRect(event.rect())
        painter.fillRect(self.viewport().rect(), _gradient(self.rect(), '#575d61', '#3d4448'))
        split = round(self.height() * .59)
        painter.setPen(QColor('#242b30'))
        painter.drawLine(0, split, self.viewport().width(), split)
        visible = self._visible_columns()
        if not visible:
            painter.end()
            return
        table = self.parent()
        play_column = getattr(table, 'play_column', -1)
        marker_height = max(3, round(_font_scale(self) * 3))
        for column in visible:
            x = self.sectionViewportPosition(column)
            width = self.sectionSize(column)
            group = math.floor(column * self.step_beat)
            painter.fillRect(x, split + 1, width, self.height() - split - 1, QColor('#42494d' if group % 2 else '#4d555a'))
            playing = column == play_column
            marker = QRect(x + max(3, width // 5), split + max(4, (self.height() - split - marker_height) // 2), max(3, width - max(6, width * 2 // 5)), marker_height)
            painter.fillRect(marker.adjusted(0, 1, 0, 1), QColor('#21272a'))
            painter.fillRect(marker, AMBER if playing else QColor('#222c31'))
            painter.setPen(QColor('#7b868b'))
            painter.drawLine(marker.left(), marker.bottom() + 1, marker.right(), marker.bottom() + 1)
            if playing:
                painter.fillRect(x, 0, width, split, QColor(237, 190, 98, 30))
        first_beat = max(0, math.ceil(visible.start * self.step_beat))
        last_beat = math.ceil(visible.stop * self.step_beat) - 1
        font = QFont(self.font())
        font.setBold(True)
        painter.setFont(font)
        pixels_per_beat = self.sectionSize(visible.start) / float(self.step_beat)
        label_stride = max(1, math.ceil(self.fontMetrics().horizontalAdvance('000') / pixels_per_beat))
        for position in range(first_beat, last_beat + 1):
            x = self._beat_x(Fraction(position))
            painter.setPen(QColor('#242b2f'))
            painter.drawLine(x, 2, x, self.height() - 1)
            if position % label_stride == 0:
                painter.setPen(QColor('#d0d9de'))
                painter.drawText(QRect(x + 6, 1, max(30, self.sectionSize(min(self.count() - 1, math.floor(Fraction(position) / self.step_beat)))) - 6, split - 2), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, str(position + 1))
        painter.setPen(QColor('#242b2f'))
        painter.drawLine(0, self.height() - 1, self.viewport().width(), self.height() - 1)
        painter.end()


class StepRowHeader(QHeaderView):
    """Instrument strips with independent audition, details, mute and solo hits.

    ``rows``, ``labels``, ``addresses``, ``selected_row`` and ``expanded_row`` are
    public presentation state.  Call ``set_rows`` after editor refresh, and the
    two selection setters when focus/details change.  ``button_rect`` accepts
    'select', 'audition', 'mute', 'solo' or 'details'.  All signals carry the row
    index; persistence and undo are the editor's responsibility.  Normal
    ``sectionClicked`` still fires once per click.
    """

    row_selected = Signal(int)
    audition = Signal(int)
    mute_toggled = Signal(int)
    solo_toggled = Signal(int)
    details_toggled = Signal(int)

    def __init__(self, parent=None):
        super().__init__(Qt.Orientation.Vertical, parent)
        self.rows = []
        self.labels = []
        self.addresses = []
        self.selected_row = -1
        self.expanded_row = -1
        self._pressed = None
        self._hover = None
        self.strip_width = 250
        self.setSectionsClickable(True)
        self.setHighlightSections(False)
        self.setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
        self.setMinimumSectionSize(23)
        self.setMouseTracking(True)
        self.setAccessibleName('Step sequencer pitch and instrument strips')
        self.setAccessibleDescription('Select a row by its name. Triangle auditions; arrow shows row controls; M mutes; S solos. The same controls are available below the grid.')
        self.refresh_metrics()

    def set_rows(self, rows, labels, addresses=None):
        self.rows = list(rows)
        self.labels = [str(value) for value in labels]
        self.addresses = [str(value) if value is not None else '' for value in (addresses or [''] * len(self.rows))]
        self.viewport().update()

    def set_selected_row(self, row):
        self.selected_row = int(row)
        self.viewport().update()

    def set_expanded_row(self, row):
        self.expanded_row = int(row)
        self.viewport().update()

    def refresh_metrics(self):
        scale = _font_scale(self)
        self.strip_width = round(250 + (scale - 1) * 110)
        self.setFixedWidth(self.strip_width)
        self.setDefaultSectionSize(round(27 * scale))
        self.updateGeometry()
        self.viewport().update()

    def sizeHint(self):
        return QSize(self.strip_width, self.defaultSectionSize())

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() in (QEvent.Type.FontChange, QEvent.Type.StyleChange) and hasattr(self, 'strip_width'):
            self.refresh_metrics()

    def button_rect(self, row, action):
        """Return a target rectangle in header-viewport coordinates."""
        if not 0 <= row < self.count():
            return QRect()
        scale = _font_scale(self)
        y = self.sectionViewportPosition(row)
        height = min(self.sectionSize(row),getattr(self.parent(),'button_height',self.defaultSectionSize()))
        width = self.viewport().width()
        edge = max(4, round(5 * scale))
        button = min(height - 6, round(21 * scale))
        gap = max(3, round(4 * scale))
        solo = QRect(width - edge - button, y + (height - button) // 2, button, button)
        mute = solo.translated(-button - gap, 0)
        details_width, audition_width = round(18 * scale), round(21 * scale)
        details = QRect(edge, y + 2, details_width, height - 4)
        audition = QRect(details.right() + 2, y + 2, audition_width, height - 4)
        select = QRect(audition.right() + gap, y + 1, max(1, mute.left() - audition.right() - gap * 2), height - 2)
        return {'select': select, 'details': details, 'audition': audition, 'mute': mute, 'solo': solo}.get(action, QRect())

    def _hit(self, point):
        row = self.logicalIndexAt(point)
        if row < 0 or row >= len(self.rows):
            return None
        for action in ('details', 'audition', 'mute', 'solo'):
            if self.button_rect(row, action).contains(point):
                return row, action
        return row, 'select'

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._pressed = self._hit(event.position().toPoint())
            self.viewport().update()
            # Native vertical-header presses select every cell in the row and
            # replace the current time column.  Instrument controls instead
            # keep the user's current step and let the editor select the row.
            event.accept()
            return
        elif event.button() == Qt.MouseButton.RightButton:
            hit = self._hit(event.position().toPoint())
            if hit is not None:
                # Context-menu edits must target the strip under the pointer.
                self.row_selected.emit(hit[0])
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        pressed, self._pressed = self._pressed, None
        hit = self._hit(event.position().toPoint())
        if event.button() == Qt.MouseButton.LeftButton:
            if hit is not None and hit == pressed:
                row, action = hit
                self.sectionClicked.emit(row)
                # The details handler selects its own row after deciding
                # whether to expand another strip or close the current one.
                if action != 'details':
                    self.row_selected.emit(row)
                signal = {'audition': self.audition, 'mute': self.mute_toggled, 'solo': self.solo_toggled, 'details': self.details_toggled}.get(action)
                if signal is not None:
                    signal.emit(row)
            event.accept()
        elif event.button() == Qt.MouseButton.RightButton:
            event.accept()
        else:
            super().mouseReleaseEvent(event)
        self.viewport().update()

    def mouseMoveEvent(self, event):
        hit = self._hit(event.position().toPoint())
        if hit != self._hover:
            self._hover = hit
            self.viewport().update()
        if event.buttons() & (Qt.MouseButton.LeftButton | Qt.MouseButton.RightButton):
            event.accept()
            return
        super().mouseMoveEvent(event)

    def viewportEvent(self, event):
        if event.type() == QEvent.Type.Leave:
            self._hover = None
            self.viewport().update()
        elif event.type() == QEvent.Type.ToolTip:
            hit = self._hit(event.pos())
            if hit is not None:
                row, action = hit
                label = self.labels[row] if row < len(self.labels) else str(row + 1)
                full_label = self.model().headerData(row, Qt.Orientation.Vertical, Qt.ItemDataRole.DisplayRole) if self.model() is not None else None
                if isinstance(full_label, str) and full_label:
                    label = full_label
                text = {'select': label, 'details': 'Show row controls: ' + label,
                        'audition': 'Audition ' + label, 'mute': 'Mute ' + label,
                        'solo': 'Solo ' + label}[action]
                QToolTip.showText(event.globalPos(), text, self.viewport(), self.button_rect(row, action))
                return True
        return super().viewportEvent(event)

    def _draw_button(self, painter, rect, text, active, hovered, pressed):
        top, bottom = ('#71858d', '#3f5862') if active else ('#6e777c', '#485156')
        if pressed:
            top, bottom = bottom, top
        painter.fillRect(rect, _gradient(rect, top, bottom))
        painter.setPen(QColor('#a2b0b6' if hovered else '#879298'))
        painter.drawLine(rect.topLeft(), rect.topRight())
        painter.drawLine(rect.topLeft(), rect.bottomLeft())
        painter.setPen(QColor('#242d32'))
        painter.drawLine(rect.bottomLeft(), rect.bottomRight())
        painter.drawLine(rect.topRight(), rect.bottomRight())
        if active:
            painter.setPen(AMBER if text == 'S' else CYAN)
        else:
            painter.setPen(QColor('#e0e5e8'))
        font = QFont(self.font())
        font.setBold(True)
        font.setPointSizeF(max(7, font.pointSizeF() - 1))
        painter.setFont(font)
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, text)

    def paintSection(self, painter, rect, logical_index):
        if not rect.isValid():
            return
        painter.save()
        painter.setClipRect(rect)
        painter.fillRect(rect,QColor('#30383d'))
        rect=QRect(rect)
        rect.setHeight(min(rect.height(),getattr(self.parent(),'button_height',self.defaultSectionSize())))
        row = self.rows[logical_index] if 0 <= logical_index < len(self.rows) else {}
        selected = logical_index == self.selected_row
        painter.fillRect(rect, _gradient(rect, '#364d56' if selected else '#424b50', '#283b43' if selected else '#313a40'))
        painter.setPen(QColor('#58646b'))
        painter.drawLine(rect.topLeft(), rect.topRight())
        painter.setPen(QColor('#20292f'))
        painter.drawLine(rect.bottomLeft(), rect.bottomRight())
        painter.drawLine(rect.topRight(), rect.bottomRight())
        if selected:
            painter.fillRect(rect.left(), rect.top() + 1, 3, rect.height() - 1, CYAN)
        scale = _font_scale(self)
        details = self.button_rect(logical_index, 'details')
        audition = self.button_rect(logical_index, 'audition')
        center = details.center()
        arm = max(3, round(3 * scale))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(CYAN if logical_index == self.expanded_row else QColor('#aab9c0'))
        points = [QPoint(center.x() - arm, center.y() - arm // 2), QPoint(center.x() + arm, center.y() - arm // 2), QPoint(center.x(), center.y() + arm)] if logical_index == self.expanded_row else [QPoint(center.x() - arm // 2, center.y() - arm), QPoint(center.x() - arm // 2, center.y() + arm), QPoint(center.x() + arm, center.y())]
        painter.drawPolygon(QPolygon(points))
        audition_pad = audition.adjusted(1, 3, -2, -3)
        painter.fillRect(audition_pad, _gradient(audition_pad, '#707d84' if self._hover == (logical_index, 'audition') else '#58656d', '#34424b'))
        painter.setPen(QColor('#7e8b92'))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(audition_pad)
        center = audition_pad.center()
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor('#e1edf1'))
        painter.drawPolygon(QPolygon([QPoint(center.x() - 2, center.y() - 4), QPoint(center.x() - 2, center.y() + 4), QPoint(center.x() + 4, center.y())]))
        select = self.button_rect(logical_index, 'select')
        address_width = round(35 * scale)
        address_rect = QRect(select.right() - address_width, select.top() + 4, address_width, select.height() - 8)
        name_rect = select.adjusted(1, 0, -address_width - 5, 0)
        label = self.labels[logical_index] if logical_index < len(self.labels) else ''
        painter.setFont(self.font())
        painter.setPen(QColor('#7bd2e5') if not row.get('muted') else QColor('#83969f'))
        painter.drawText(name_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, self.fontMetrics().elidedText(label, Qt.TextElideMode.ElideRight, name_rect.width()))
        address = self.addresses[logical_index] if logical_index < len(self.addresses) else ''
        painter.fillRect(address_rect, QColor('#26333b'))
        painter.setPen(QColor('#52616a'))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(address_rect)
        font = QFont(self.font())
        font.setPointSizeF(max(7, font.pointSizeF() - 1))
        painter.setFont(font)
        painter.setPen(QColor('#80c3d2'))
        painter.drawText(address_rect.adjusted(2, 0, -2, 0), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, address)
        for action, letter, active in (('mute', 'M', row.get('muted', False)), ('solo', 'S', row.get('solo', False))):
            self._draw_button(painter, self.button_rect(logical_index, action), letter, active,
                              self._hover == (logical_index, action), self._pressed == (logical_index, action))
        painter.restore()
