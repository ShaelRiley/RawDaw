"""Library-first harmony selection and a persistent personal progression bank."""
from __future__ import annotations

from fractions import Fraction
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QFormLayout, QLabel, QComboBox,
    QLineEdit, QPushButton, QListWidget, QListWidgetItem, QFileDialog, QDialog,
    QDialogButtonBox, QSpinBox, QMenu)

from . import progression_bank as lib
from .contracts import ContractError
from .gui_widgets import FlowLayout
from .music import NAMES, at, beat


class ProgressionBrowser(QWidget):
    def __init__(self, window):
        super().__init__(); self.window = window; self.bank = window.progression_bank
        self.editor = None; self.position = Fraction(0); self.key = None; self.rows = []
        layout = QVBoxLayout(self); layout.setContentsMargins(6, 6, 6, 6); layout.setSpacing(5)
        filters = FlowLayout()
        self.search = QLineEdit(); self.search.setMinimumWidth(150); self.search.setPlaceholderText('Search progressions…')
        self.search.setAccessibleName('Search chord progressions by name, sound, chords or use'); filters.addWidget(self.search)
        self.view = QComboBox()
        for label, value in [('Best fits', 'best'), ('All progressions', 'all'), ('Favorites', 'favorites'), ('My bank', 'user')]:
            self.view.addItem(label, value)
        self.view.setAccessibleName('Progression collection'); filters.addWidget(self.view)
        self.style = QComboBox(); self.style.setAccessibleName('Progression style'); self.style.setMinimumContentsLength(7)
        self.style.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon); filters.addWidget(self.style)
        layout.addLayout(filters)
        self.count = QLabel(); self.count.setWordWrap(True); self.count.setObjectName('muted'); layout.addWidget(self.count)
        self.list = QListWidget(); self.list.setMinimumHeight(80)
        self.list.setAccessibleName('Chord progression bank. Select then Preview or Load into song.'); layout.addWidget(self.list, 1)
        self.info = QLabel(); self.info.setWordWrap(True); self.info.setObjectName('muted'); self.info.setMaximumHeight(56); layout.addWidget(self.info)
        actions = FlowLayout(); self.preview = QPushButton('Preview'); self.preview.clicked.connect(self.preview_selected); actions.addWidget(self.preview)
        self.load = QPushButton('Load into song'); self.load.setObjectName('primary'); self.load.clicked.connect(self.load_selected); actions.addWidget(self.load)
        self.favorite = QPushButton('☆'); self.favorite.setAccessibleName('Toggle favorite progression'); self.favorite.clicked.connect(self.toggle_favorite); actions.addWidget(self.favorite)
        self.manage = QPushButton('Bank…'); self.manage.setAccessibleName('Import, export, save and manage chord progressions')
        self.menu = QMenu(self.manage)
        self.menu.addAction('Import progressions…', self.import_dialog)
        self.menu.addAction('Save current harmony to My bank…', self.save_current)
        self.menu.addAction('Create custom progression…', window.custom_dialog)
        self.menu.addSeparator()
        self.menu.addAction('Place one cycle at cursor', lambda: self.load_selected(repeat=False))
        self.menu.addAction('Progression details…', self.details)
        self.menu.addSeparator()
        self.export_action = self.menu.addAction('Export My bank…', self.export_dialog)
        self.remove_action = self.menu.addAction('Remove selected from My bank', self.remove_selected)
        self.undo_action = self.menu.addAction('Undo last bank change', self.undo_bank)
        self.menu.aboutToShow.connect(self.menu_state); self.manage.setMenu(self.menu); actions.addWidget(self.manage); layout.addLayout(actions)
        self.list.currentItemChanged.connect(self.describe)
        self.search.textChanged.connect(self.populate); self.view.currentIndexChanged.connect(self.populate); self.style.currentIndexChanged.connect(self.populate)
        self._styles()

    def _styles(self):
        previous = self.style.currentData(); self.style.blockSignals(True); self.style.clear(); self.style.addItem('All styles', '')
        for style in sorted({e['style'] for e in self.bank.all()}): self.style.addItem(style, style)
        self.style.setCurrentIndex(max(0, self.style.findData(previous))); self.style.blockSignals(False)

    def selected(self):
        row = self.list.currentItem()
        return row.data(Qt.ItemDataRole.UserRole) if row else None

    def refresh(self, editor, position):
        self.editor = editor; self.position = position; tone = at(editor.project['tonalityMap'], position)
        key = (editor.pack.manifest_hash, tone['tonic'], tone['mode'], self.bank.revision)
        if key != self.key:
            self.rows = lib.ranked(editor.pack, tone['tonic'], tone['mode'], self.bank.all()); self.key = key
            self._styles(); self.populate()

    def populate(self, *_):
        selected = self.selected(); identity = selected['id'] if selected else None
        query = self.search.text().strip().casefold(); style = self.style.currentData(); view = self.view.currentData()
        user_ids = {e['id'] for e in self.bank.entries}; rows = []
        for row in self.rows:
            e = row['entry']
            if style and e['style'] != style: continue
            if view == 'favorites' and e['id'] not in self.bank.favorites: continue
            if view == 'user' and e['id'] not in user_ids: continue
            search = ' '.join([e['name'], e['style'], e['section'], e['description'], e['sourceNotation'], *row['display'], *row['chordNames']]).casefold()
            if query and query not in search: continue
            rows.append(row)
        if view == 'best' and not query and not style:
            rows = [r for r in rows if r['recommended']][:12]
        self.list.blockSignals(True); self.list.clear()
        for row in rows:
            e = row['entry']; total = sum(Fraction(d) for d in e['durations']); unit = 'bars' if e['durationUnit'] == 'bars' else 'quarter beats'
            label = ('★ ' if e['id'] in self.bank.favorites else '') + e['name'] + ' · ' + ' – '.join(row['chordNames'])
            label += '\n' + ' – '.join(row['display']) + f' · {total} {unit} · {e["section"]}'
            item = QListWidgetItem(label); item.setData(Qt.ItemDataRole.UserRole, row)
            item.setToolTip(e['description'] + '\n' + row['explanation'] + '\nSource: ' + e['sourceNotation'] + ' (' + e['basis'] + ')')
            self.list.addItem(item)
            if e['id'] == identity: self.list.setCurrentItem(item)
        if self.list.currentItem() is None and rows: self.list.setCurrentRow(0)
        self.list.blockSignals(False)
        self.count.setText(f'{len(rows)} shown · {len(lib.catalog())} built-in · {len(self.bank.entries)} in My bank')
        self.describe()

    def describe(self, *_):
        row = self.selected(); enabled = row is not None and self.editor is not None
        self.preview.setEnabled(enabled); self.load.setEnabled(enabled); self.favorite.setEnabled(enabled)
        if not row:
            self.info.setText(self.bank.error or ('Import or save a progression using Bank…' if self.view.currentData() == 'user' else 'Choose All progressions or change the filters.'))
            return
        e = row['entry']; tone = at(self.editor.project['tonalityMap'], self.position)
        fit = 'Fits ' + tone['mode'].replace('_', ' ') if row['recommended'] else 'Authored for ' + ', '.join(m.replace('_', ' ') for m in e['modes'])
        self.info.setText(self.bank.error or f'{NAMES[tone["tonic"]]} · {fit}. {row["nativeChordCount"]} native / {row["reconstructedChordCount"]} reconstructed chords. Load fills song; Undo restores harmony.')
        self.info.setToolTip(self.bank.error or row['explanation']); self.favorite.setText('★' if e['id'] in self.bank.favorites else '☆')

    def _run(self, operation):
        try:
            return operation()
        except (ValueError, OSError, KeyError) as error:
            self.window.notice(str(error)); return None

    def preview_selected(self):
        row = self.selected()
        if not row or not self.editor: return
        def preview():
            project = lib.audition_project(self.editor, row['entry'], self.position)
            self.window.stop()
            return self.window.request_render(autoplay=True, preview_project=project,
                scope=dict(start=str(self.position), instance=None, kind='progression', loop=True))
        return self._run(preview)

    def load_selected(self, *, repeat=True):
        row = self.selected()
        if not row or not self.editor: return
        start = Fraction(0) if repeat else self.position
        self.window.change(lambda: lib.load_into(self.editor, row['entry'], start=start, repeat=repeat, grow_empty=repeat))

    def select_id(self, identity):
        for i in range(self.list.count()):
            if self.list.item(i).data(Qt.ItemDataRole.UserRole)['id'] == identity:
                self.list.setCurrentRow(i); return

    def changed(self, identity=None):
        if self.editor: self.refresh(self.editor, self.position)
        if identity: self.select_id(identity)

    def toggle_favorite(self):
        row = self.selected()
        if row:
            self._run(lambda: self.bank.toggle_favorite(row['id'])); self.changed(row['id'])

    def menu_state(self):
        row = self.selected()
        self.remove_action.setEnabled(bool(row and any(e['id'] == row['id'] for e in self.bank.entries)))
        self.undo_action.setEnabled(bool(self.bank.history)); self.export_action.setEnabled(bool(self.bank.entries))

    def import_files(self, paths, *, text_basis='major-relative', text_unit='bars'):
        def commit():
            entries = [e for path in paths for e in lib.load_file(path, text_basis=text_basis, text_unit=text_unit)]
            added, skipped = self.bank.import_entries(entries)
            self.view.setCurrentIndex(self.view.findData('user' if added else 'all')); self.changed(entries[0]['id'])
            self.window.notice(f'Imported {added} progressions into My bank; {skipped} already in the library. Your song is unchanged.')
            return added, skipped
        return self._run(commit)

    def import_dialog(self):
        paths, _ = QFileDialog.getOpenFileNames(self, 'Import progressions into My bank', str(self.window.data_dir),
            'Progression banks (*.json *.txt);;JSON bank (*.json);;Text progressions (*.txt)')
        if not paths: return
        basis = 'major-relative'; unit = 'bars'
        if any(Path(p).suffix.lower() != '.json' for p in paths):
            dialog = QDialog(self); dialog.setWindowTitle('Interpret text progressions'); layout = QVBoxLayout(dialog)
            help_text = QLabel('Choose the root notation used by your file. In A minor, major-relative ♭VI and mode-relative VI both mean F. Roman case preserves major/minor quality. Numeric degrees always follow the selected mode.'); help_text.setWordWrap(True); layout.addWidget(help_text)
            form = QFormLayout(); notation = QComboBox(); notation.addItem('Major-relative roots (common song charts)', 'major-relative'); notation.addItem('Mode-relative roots (Raw Daw)', 'mode-relative')
            duration = QComboBox(); duration.addItem('Measures / bars', 'bars'); duration.addItem('Quarter-note beats', 'beats')
            form.addRow('Roman numeral basis', notation); form.addRow('Duration unit', duration); layout.addLayout(form)
            example = QLabel('One progression per line: Name | I V vi IV | 1 1 1 1\nOmit durations to use one measure per chord.'); example.setWordWrap(True); layout.addWidget(example)
            buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel); buttons.accepted.connect(dialog.accept); buttons.rejected.connect(dialog.reject); layout.addWidget(buttons)
            if dialog.exec() != QDialog.DialogCode.Accepted: return
            basis = notation.currentData(); unit = duration.currentData()
        self.import_files(paths, text_basis=basis, text_unit=unit)

    def export_dialog(self):
        path, _ = QFileDialog.getSaveFileName(self, 'Export My progression bank', str(self.window.data_dir / 'My_progressions.json'), 'Progression bank (*.json)')
        if path:
            if not path.lower().endswith('.json'): path += '.json'
            def export():
                self.bank.export(path); self.window.notice('Exported progression bank to ' + path)
            self._run(export)

    def save_current(self):
        if not self.editor: return
        dialog = QDialog(self); dialog.setWindowTitle('Save current harmony to My bank'); layout = QVBoxLayout(dialog)
        form = QFormLayout(); name = QLineEdit('My progression'); bars = QSpinBox(); bars.setRange(1, 32); bars.setValue(4)
        form.addRow('Name', name); form.addRow('Measures from edit cursor', bars); layout.addLayout(form)
        help_text = QLabel('Save the chord lane from the cursor, up to the song ending. Exact chords and timing are retained in a reusable entry; your song stays unchanged.'); help_text.setWordWrap(True); layout.addWidget(help_text)
        error = QLabel(); error.setWordWrap(True); error.setObjectName('warning'); layout.addWidget(error)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel); buttons.rejected.connect(dialog.reject); layout.addWidget(buttons)
        def save():
            try:
                end = min(lib.advance_bars(self.editor.project, self.position, bars.value()), beat(self.editor.project['length']))
                entry = lib.capture(self.editor.project, self.position, end, name.text())
                added, _ = self.bank.import_entries([entry])
            except (ValueError, OSError) as exc: error.setText(str(exc)); return
            self.view.setCurrentIndex(self.view.findData('user' if added else 'all')); self.changed(entry['id'])
            self.window.notice('Saved to My bank.' if added else 'That progression is already in the library.'); dialog.accept()
        buttons.accepted.connect(save); dialog.exec()

    def remove_selected(self):
        row = self.selected()
        if row:
            self._run(lambda: self.bank.remove(row['id'])); self.changed()

    def undo_bank(self):
        self._run(self.bank.undo); self.changed()

    def details(self):
        row = self.selected()
        if not row: return
        e = row['entry']; dialog = QDialog(self); dialog.setWindowTitle(e['name']); layout = QVBoxLayout(dialog)
        text = '\n'.join([e['description'], '', 'Chord names: ' + ' – '.join(row['chordNames']),
            'Current Roman chords: ' + ' – '.join(row['display']), 'Durations: ' + ', '.join(e['durations']) + ' ' + e['durationUnit'],
            'Original notation: ' + e['sourceNotation'] + ' · ' + e['basis'], row['explanation'], '',
            *[c['source'] + '\n' + c['attribution'] + '\n' + c['license'] for c in e['credits']]])
        from PySide6.QtWidgets import QPlainTextEdit
        info = QPlainTextEdit(text); info.setReadOnly(True); layout.addWidget(info)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close); buttons.rejected.connect(dialog.reject); layout.addWidget(buttons); dialog.resize(650, 480); dialog.exec()
