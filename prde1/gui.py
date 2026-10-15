"""PRDE1 native desktop composition slice, with rendered PCM audition playback."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import sys
import tempfile
import uuid
from fractions import Fraction
from pathlib import Path

from .desktop_startup import begin_startup_log, configure_audio, startup_stage

configure_audio()  # Also protect direct `python -m prde1.gui` and embedded windows.

from PySide6.QtCore import Qt, QProcess, QSettings, QStandardPaths, QTimer, QUrl, qVersion
from PySide6.QtGui import QAction, QColor, QFont, QKeySequence, QIcon
from PySide6.QtMultimedia import QAudioOutput, QMediaDevices, QMediaPlayer
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QFormLayout, QLabel, QPushButton, QComboBox, QSpinBox, QSlider, QCheckBox, QLineEdit,
    QDockWidget, QSplitter, QScrollArea, QTabWidget, QTableWidget, QTableWidgetItem,
    QListWidget, QListWidgetItem, QFileDialog, QMessageBox, QDialog, QDialogButtonBox,
    QPlainTextEdit, QAbstractItemView, QHeaderView, QSizePolicy)

from . import __version__
from .contracts import ROOT, ContractError, RATE, SLOTS, atomic_json, canonical_bytes, read_json
from .editor import Editor, atomic_copy, chord_label, measures, new_project, seconds_to_beat
from .governor import context
from .gui_widgets import COLORS, ROLES, SLOT_NAMES, ChordDialog, EventDialog, FlowLayout, StepTable, Timeline, spin
from .music import MODES, NAMES, at, beat, quarter_seconds, roman
from .pack import Pack
from .project import load_project, save_project
from .step_widgets import StepSequencer
from .mixing import DRUM_PRESETS, DRUM_COMPRESSOR, BASS_SIDECHAIN, apply_punch_mix, drum_eq
from .library_widgets import PulseControls, ClipBrowser
from . import clip_library
from . import progression_bank
from .progression_widgets import ProgressionBrowser

STYLE='''
QMainWindow, QDialog, QWidget { background: #171e27; color: #e3ebf4; }
QLabel#brand { font-size: 23px; font-weight: 700; color: #eef6ff; }
QLabel#muted { color: #b1c0d0; }
QLabel#warning { color: #ffc598; }
QLabel#guidance { color: #a6e5ce; padding: 7px; background: #233a36; border-radius: 5px; }
QPushButton { background: #2b3746; border: 1px solid #56677b; border-radius: 5px; padding: 6px 12px; min-height: 20px; }
QPushButton:hover { background: #35465a; }
QPushButton:pressed { background: #455d74; }
QPushButton#primary { background: #31745d; border-color: #6ab99b; font-weight: 600; }
QPushButton:disabled { color: #8895a5; border-color: #354152; background: #202a36; }
QPushButton:focus, QComboBox:focus, QLineEdit:focus, QAbstractSpinBox:focus, QTableWidget:focus, QListWidget:focus { border: 2px solid #82c5ff; }
QComboBox, QLineEdit, QAbstractSpinBox { background: #111821; border: 1px solid #54677d; border-radius: 4px; padding: 4px; min-height: 20px; }
QComboBox QAbstractItemView { background: #202b39; selection-background-color: #335c80; }
QTabWidget::pane { border: 1px solid #3b4b5f; }
QTabBar::tab { background: #253242; padding: 7px 14px; border: 1px solid #3b4b5f; }
QTabBar::tab:selected { background: #3b5067; color: #fff; }
QTableWidget, QListWidget, QPlainTextEdit { background: #141c26; alternate-background-color: #1e2a38; gridline-color: #36465a; border: 1px solid #43556c; selection-background-color: #315f83; selection-color: #fff; }
QHeaderView::section { background: #263445; color: #dce7f2; padding: 5px; border: 1px solid #3b4b5f; }
QDockWidget::title { background: #253242; padding: 7px; }
QMenuBar, QMenu, QStatusBar { background: #202c3a; }
QMenu::item:selected { background: #3b5976; }
QScrollBar { background: #1e2936; }
QScrollBar::handle { background: #586f89; min-width: 25px; min-height: 25px; }
QCheckBox { spacing: 8px; }
QToolTip { background: #e4edf6; color: #102031; padding: 5px; border: 1px solid #43556c; }
'''


def button(text,callback,primary=False):
    value=QPushButton(text);value.clicked.connect(callback)
    if primary:value.setObjectName('primary')
    return value


def item(text,data=None):
    result=QTableWidgetItem(str(text));result.setFlags(Qt.ItemFlag.ItemIsSelectable|Qt.ItemFlag.ItemIsEnabled)
    if data is not None:result.setData(Qt.ItemDataRole.UserRole,data)
    return result


class DrumEqDialog(QDialog):
    def __init__(self,slot,settings,parent=None):
        super().__init__(parent);self.setWindowTitle(SLOT_NAMES[slot]+' · EQ');self.resize(380,380)
        layout=QVBoxLayout(self);help_text=QLabel('Independent high-pass, body/presence bell and air shelf. These affect playback and export.');help_text.setWordWrap(True);layout.addWidget(help_text)
        self.on=QCheckBox('EQ enabled');self.on.setChecked(settings['on']);layout.addWidget(self.on)
        form=QFormLayout();self.controls={}
        for key,label,low,high,digits,suffix in [
            ('highpassHz','Low cut',20,2000,0,' Hz'),('bellHz','Bell frequency',30,16000,0,' Hz'),
            ('bellDb','Bell boost / cut',-12,12,1,' dB'),('bellQ','Bell width · Q',.3,4,2,''),
            ('shelfHz','Air shelf frequency',1000,18000,0,' Hz'),('shelfDb','Air shelf boost / cut',-12,12,1,' dB')]:
            widget=spin(low,high,settings[key],digits,suffix);widget.setAccessibleName(label);self.controls[key]=widget;form.addRow(label,widget)
        layout.addLayout(form)
        def reset():
            values=drum_eq(slot);self.on.setChecked(True)
            for key,widget in self.controls.items():widget.setValue(values[key])
        layout.addWidget(button('Use '+DRUM_PRESETS[slot][0],reset))
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept);buttons.rejected.connect(self.reject);layout.addWidget(buttons)
    def values(self):return dict(on=self.on.isChecked(),**{key:widget.value() for key,widget in self.controls.items()})


class MainWindow(QMainWindow):
    def __init__(self,project_path=None,pack_path=None,*,data_dir=None,remember=True,safe_workspace=False):
        super().__init__();self.setObjectName('prde1Window');self.setWindowTitle('Raw Daw')
        self.setWindowIcon(QIcon(str(ROOT/'prde1/data/raw-daw.svg')))
        self._safe_workspace=safe_workspace
        self.resize(1366,800);self.setMinimumSize(900,650);self.setStyleSheet(STYLE)
        self.editor=None;self.pack=None;self.selected_id='';self.role='rhythm';self.cursor=Fraction(0)
        self._refreshing=False;self._closing=False;self._plan=None;self._job=None;self._generation=0;self._compact=None;self._scale_value=1
        self._layout_ready=False;self._layout_changing=False
        self._preview_key=None;self._pending_seek=0;self._settings=QSettings('ShaelRiley','PRDE1') if remember else None
        self._playback_scope=None
        self._note_preview=None
        self.data_dir=Path(data_dir or QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppLocalDataLocation))
        self.data_dir.mkdir(parents=True,exist_ok=True)
        self.progression_bank=progression_bank.Bank(self.data_dir/'progressions.json')
        self.recovery_dir=self.data_dir/'recovery';self.recovery_dir.mkdir(exist_ok=True)
        self.recovery_file=self.recovery_dir/(uuid.uuid4().hex+'.json')
        self.workspace=tempfile.TemporaryDirectory(prefix='prde1-desktop-');self.work=Path(self.workspace.name)
        self.process=QProcess(self);self.process.finished.connect(self._render_finished);self.process.errorOccurred.connect(self._process_error)
        startup_stage('Creating PCM audio player')
        self.player=QMediaPlayer(self);self.audio=QAudioOutput(self);self.audio.setVolume(1.0);self.player.setAudioOutput(self.audio)
        self.player.setPlaybackRate(1.0)
        self.player.positionChanged.connect(self._play_position);self.player.playbackStateChanged.connect(self._play_state)
        self.player.mediaStatusChanged.connect(self._media_status);self.player.errorOccurred.connect(lambda *_:self.notice('Playback: '+self.player.errorString()))
        self.devices=QMediaDevices(self);self.devices.audioOutputsChanged.connect(self._devices_changed)
        self._make_actions();self._make_center();self._make_inspector();self._make_browser();self._make_mixer()
        startup_stage('Enumerating audio outputs')
        self._devices_changed();self.autosave_timer=QTimer(self);self.autosave_timer.setInterval(15000);self.autosave_timer.timeout.connect(self.autosave);self.autosave_timer.start()
        self._recoveries=sorted(self.recovery_dir.glob('*.json'),key=lambda p:p.stat().st_mtime,reverse=True)
        self.recover_button.setVisible(bool(self._recoveries))
        startup_stage('Loading project')
        self._bootstrap(project_path,pack_path)
        if self.progression_bank.error:self.notice(self.progression_bank.error)
        if self._safe_workspace:
            startup_stage('Recovery workspace: central tabs; saved geometry, docks and scale preserved')
            self._apply_scale(1)
        elif self._settings:
            startup_stage('Restoring workspace and interface scale')
            geometry=self._settings.value('geometry');state=self._settings.value('layout')
            if geometry:self.restoreGeometry(geometry)
            if state:self.restoreState(state)
            self._apply_scale(float(self._settings.value('scale',1)))
        else:self._apply_scale(1)
        # Geometry/state/font restoration can emit resize events synchronously.
        # Move panels only after all widgets and saved preferences are ready.
        self._layout_ready=True;self._responsive_layout()
        startup_stage('Responsive workspace ready')

    def _make_actions(self):
        file=self.menuBar().addMenu('File');edit=self.menuBar().addMenu('Edit');view=self.menuBar().addMenu('View')
        def action(menu,text,slot,key=None):
            value=QAction(text,self);value.triggered.connect(slot)
            if key:value.setShortcut(QKeySequence(key))
            menu.addAction(value);return value
        action(file,'New song from active pack',self.new_song,'Ctrl+N');action(file,'Load Song Pack…',self.load_pack_dialog)
        action(file,'Open project…',self.open_project_dialog,'Ctrl+O');action(file,'Save project',self.save,'Ctrl+S')
        action(file,'Save project as…',lambda:self.save(True),'Ctrl+Shift+S');action(file,'Export stereo WAV…',self.export_dialog,'Ctrl+E')
        action(file,'Quit',self.close,'Ctrl+Q')
        self.undo_action=action(edit,'Undo',self.undo,'Ctrl+Z');self.redo_action=action(edit,'Redo',self.redo,'Ctrl+Shift+Z')
        action(edit,'Duplicate selected pattern…',self.copy_dialog,'Ctrl+D');action(edit,'Make independent',self.detach_selected)
        action(edit,'Regenerate variation',lambda:self.change(self.editor.regenerate))
        action(view,'Reset workspace',self.reset_layout);self.focus_action=action(view,'Focus view',self.focus_view,'Ctrl+Shift+F');self.focus_action.setCheckable(True)
        self.play_action=QAction('Play / Pause',self);self.play_action.setShortcut(QKeySequence('Space'));self.play_action.setShortcutContext(Qt.ShortcutContext.WindowShortcut);self.play_action.triggered.connect(self.play);self.addAction(self.play_action)
        # Space belongs to a focused grid or text field; the shortcut is enabled elsewhere.
        QApplication.instance().focusChanged.connect(self._focus_changed)

    def _make_center(self):
        central=QWidget();layout=QVBoxLayout(central);layout.setContentsMargins(12,10,12,8);layout.setSpacing(8);self.setCentralWidget(central)
        top=FlowLayout();mascot=QLabel();mascot.setPixmap(self.windowIcon().pixmap(40,40));mascot.setAccessibleName('Raw Daw dog mascot: half black, half white face and spiked collar');top.addWidget(mascot)
        brand=QLabel('Raw Daw');brand.setObjectName('brand');top.addWidget(brand)
        self.save_status=QLabel('');self.save_status.setObjectName('muted');top.addWidget(self.save_status);top.addStretch()
        top.addWidget(button('Open project',self.open_project_dialog));top.addWidget(button('Save',self.save))
        self.play_button=button('Play',self.play,True);self.play_button.setAccessibleName('Play or pause current arrangement');top.addWidget(self.play_button)
        self.stop_button=button('Stop',self.stop);top.addWidget(self.stop_button)
        self.loop_song=QCheckBox('Loop song');self.loop_song.setAccessibleName('Loop the entire song during playback')
        self.loop_song.setToolTip('Repeat the rendered song from beginning to ending. This setting is saved with the project; exported WAVs contain one song.')
        self.loop_song.clicked.connect(self.set_playback_loop);top.addWidget(self.loop_song)
        self.export_button=button('Export WAV',self.export_dialog);top.addWidget(self.export_button);layout.addLayout(top)
        # Keep transport visible while an enlarged workspace scrolls vertically.
        self.body=QWidget();body_layout=QVBoxLayout(self.body);body_layout.setContentsMargins(0,0,0,0);body_layout.setSpacing(8)
        self.body_scroll=QScrollArea();self.body_scroll.setWidget(self.body);self.body_scroll.setWidgetResizable(True)
        self.body_scroll.setFrameShape(QScrollArea.Shape.NoFrame);layout.addWidget(self.body_scroll,1);layout=body_layout
        self.song_controls=QWidget();layout.addWidget(self.song_controls)
        layout=QVBoxLayout(self.song_controls);layout.setContentsMargins(0,0,0,0);layout.setSpacing(8)
        guide=QHBoxLayout();self.guidance=QLabel('Load a Song Pack to begin.');self.guidance.setObjectName('guidance');self.guidance.setWordWrap(True);guide.addWidget(self.guidance,1)
        self.recover_button=button('Recover unsaved session',self.recover);guide.addWidget(self.recover_button);layout.addLayout(guide)
        govern=FlowLayout();govern.addWidget(QLabel('Chord Governor'))
        self.tonic=QComboBox();self.tonic.addItems(NAMES);self.tonic.setAccessibleName('Key at edit cursor');govern.addWidget(self.tonic)
        self.mode=QComboBox()
        for name in MODES:self.mode.addItem(name.replace('_',' ').title(),name)
        self.mode.setAccessibleName('Mode at edit cursor');govern.addWidget(self.mode)
        govern.addWidget(button('Set key here',self.set_tonality));govern.addWidget(button('Edit chord',lambda:self.edit_chord(self.cursor)))
        self.progression_button=button('Choose progression',self.choose_progression,True);govern.addWidget(self.progression_button)
        custom_button=button('Custom…',self.custom_dialog);custom_button.setAccessibleName('Create a custom chord progression')
        custom_button.setToolTip('Write your own chord progression and save it to My bank');govern.addWidget(custom_button);govern.addStretch();layout.addLayout(govern)
        self.pulse_controls=PulseControls(self);layout.addWidget(self.pulse_controls)
        timing=FlowLayout();timing.addWidget(QLabel('Tempo'))
        self.tempo=spin(20,300,120,1,' qBPM');self.tempo.setAccessibleName('Quarter-note tempo at edit cursor');self.tempo.editingFinished.connect(self.set_tempo);timing.addWidget(self.tempo)
        self.meter=QComboBox()
        for text,n,d in [('4/4',4,4),('3/4',3,4),('6/8',6,8),('2/4',2,4),('5/4',5,4),('7/8',7,8)]:self.meter.addItem(text,(n,d))
        self.meter.setAccessibleName('Meter at current measure');timing.addWidget(self.meter)
        self.grid=QComboBox()
        for n in (3,4,6,8):self.grid.addItem(str(n)+' cells/bar',n)
        self.grid.setAccessibleName('Chord Governor grid');timing.addWidget(self.grid)
        timing.addWidget(button('Set meter/grid here',self.set_meter))
        timing.addWidget(QLabel('Song'))
        self.bars=QSpinBox();self.bars.setRange(1,512);self.bars.setSuffix(' bars');self.bars.setKeyboardTracking(False);self.bars.editingFinished.connect(self.resize_song);timing.addWidget(self.bars)
        self.duration=QLabel();timing.addWidget(self.duration);timing.addStretch()
        self.zoom=QSlider(Qt.Orientation.Horizontal);self.zoom.setRange(50,200);self.zoom.setValue(100);self.zoom.setMaximumWidth(110);self.zoom.setAccessibleName('Timeline zoom');self.zoom.valueChanged.connect(self.set_zoom);timing.addWidget(QLabel('Zoom'));timing.addWidget(self.zoom);layout.addLayout(timing)
        layout=body_layout
        self.splitter=QSplitter(Qt.Orientation.Vertical);self.splitter.setSizePolicy(QSizePolicy.Policy.Expanding,QSizePolicy.Policy.Ignored);layout.addWidget(self.splitter,1)
        self.timeline=Timeline();self.timeline.selected.connect(self.select);self.timeline.chord_requested.connect(self.edit_chord)
        self.timeline.instance_moved.connect(self.move_clip);self.timeline.instance_resized.connect(self.resize_clip)
        self.timeline.move_requested.connect(self.move_clip_dialog);self.timeline.length_requested.connect(self.loop_clip_dialog)
        self.timeline.track_loop_requested.connect(self.toggle_track_loop)
        self.timeline_scroll=QScrollArea();self.timeline_scroll.setWidget(self.timeline);self.timeline_scroll.setWidgetResizable(True);self.timeline_scroll.horizontalScrollBar().valueChanged.connect(self._scroll_changed)
        # The timeline scrolls within its own pane. Its full track height must
        # not force note controls below a small or enlarged-text viewport.
        policy=self.timeline_scroll.sizePolicy();policy.setVerticalPolicy(QSizePolicy.Policy.Ignored);self.timeline_scroll.setSizePolicy(policy);self.timeline_scroll.setMinimumHeight(100)
        self.splitter.addWidget(self.timeline_scroll)
        self.dock_tabs=QTabWidget();self.splitter.addWidget(self.dock_tabs);self.splitter.setSizes([360,260])
        self.sequencer=StepSequencer(self.change,self.audition_steps,self.copy_dialog,self.detach_selected,self.remove_selected,self,preview_note=self.preview_note)
        self._step_pane_sizes=None
        self.sequencer.focus_editor.toggled.connect(self.expand_step_editor)
        self.sequencer.layout_changed.connect(lambda:QTimer.singleShot(0,self.fit_step_panes))
        self.dock_tabs.currentChanged.connect(lambda:QTimer.singleShot(0,self.fit_step_panes))
        if self._settings:self.sequencer.preview_click.setChecked(self._settings.value('previewNotes',True,type=bool))
        self.sequencer.preview_click.toggled.connect(self.set_note_preview_enabled)
        self.steps=self.sequencer.grid;self.step_resolution=self.sequencer.resolution
        self.pattern_heading=self.sequencer.heading;self.step_help=self.sequencer.help
        self.dock_tabs.addTab(self.sequencer,'Step sequencer')
        event_panel=QWidget();events_layout=QVBoxLayout(event_panel);tools=QHBoxLayout();tools.addWidget(QLabel('Exact event timing · no automatic quantization'),1)
        tools.addWidget(button('Edit selected step',self.edit_selected_event));tools.addWidget(button('Delete step',self.delete_selected_event));events_layout.addLayout(tools)
        self.events=QTableWidget(0,9);self.events.setObjectName('eventList');self.events.setHorizontalHeaderLabels(['State','Beat','Gate','Choice','Note volume %','Play %','Change %','Variation','Lock'])
        self.events.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows);self.events.setAlternatingRowColors(True);self.events.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.events.cellDoubleClicked.connect(lambda *_:self.edit_selected_event());self.events.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents);self.events.horizontalHeader().setStretchLastSection(True)
        events_layout.addWidget(self.events);self.dock_tabs.addTab(event_panel,'Event list')
        self.issues=QPlainTextEdit();self.issues.setReadOnly(True);self.issues.setAccessibleName('Coverage conflicts and render warnings');self.dock_tabs.addTab(self.issues,'Coverage & warnings')
        bottom=QHBoxLayout();self.position=QLabel('Edit 1:1 · Stopped');bottom.addWidget(self.position)
        self.seek=QSlider(Qt.Orientation.Horizontal);self.seek.setRange(0,1000);self.seek.setAccessibleName('Playback position');self.seek.sliderReleased.connect(self.seek_player);bottom.addWidget(self.seek,1)
        self.outputs=QComboBox();self.outputs.setMaximumWidth(240);self.outputs.setAccessibleName('Audio output device');self.outputs.currentIndexChanged.connect(self.choose_output);bottom.addWidget(self.outputs);layout.addLayout(bottom)
        self.message=QLabel();self.message.setObjectName('warning');self.message.setWordWrap(True);layout.addWidget(self.message)

    def expand_step_editor(self,on):
        self.song_controls.setVisible(not on);self.timeline_scroll.setVisible(not on)
        if on:
            self._step_pane_sizes=self.splitter.sizes();self.splitter.setSizes([0,sum(self._step_pane_sizes)])
        elif self._step_pane_sizes:
            self.splitter.setSizes(self._step_pane_sizes);self._step_pane_sizes=None
        self.fit_step_panes()

    def fit_step_panes(self):
        # QSplitter's ignored vertical policy otherwise compresses the editor
        # below its layout minimum when fonts grow, overlapping live controls.
        s=self.sequencer
        if self.dock_tabs.currentWidget() is not s:
            self.dock_tabs.setMinimumHeight(0);self.splitter.setMinimumHeight(0);return
        editor_height=s.minimumSizeHint().height()
        if s.details.isChecked():editor_height=max(editor_height,s.layout().heightForWidth(s.width()))
        needed=editor_height+self.dock_tabs.tabBar().sizeHint().height()+12
        self.dock_tabs.setMinimumHeight(needed)
        layout=self.body.layout();others=[]
        for index in range(layout.count()):
            widget=layout.itemAt(index).widget()
            if widget is not None and widget is not self.splitter and not widget.isHidden():others.append(widget.height())
        available=max(0,self.body_scroll.viewport().height()-sum(others)-layout.spacing()*len(others))
        timeline=self.timeline_scroll.minimumHeight()
        keep_timeline=self.timeline_scroll.isVisible() and available>=needed+timeline+self.splitter.handleWidth()
        reserved=timeline+self.splitter.handleWidth() if keep_timeline else 0
        self.splitter.setMinimumHeight(needed+reserved)
        self.splitter.setSizes([timeline if keep_timeline else 0,max(needed,available-reserved)])

    def _make_inspector(self):
        self.inspector_dock=None
        if not self._safe_workspace:
            self.inspector_dock=QDockWidget('Inspector',self);self.inspector_dock.setObjectName('inspectorDock')
        panel=QWidget();layout=QVBoxLayout(panel);self.selection_label=QLabel('Select a track');self.selection_label.setWordWrap(True);layout.addWidget(self.selection_label)
        form=QFormLayout();self.track=QComboBox()
        for role in ROLES:self.track.addItem(role.title(),role)
        self.track.setCurrentIndex(1);self.track.currentIndexChanged.connect(self.select_role);form.addRow('Track',self.track)
        self.gain=spin(-96,12,-8,1,' dB');self.gain.editingFinished.connect(self.inspector_mix);form.addRow('Level',self.gain)
        self.pan=spin(-100,100,0,0,' %');self.pan.editingFinished.connect(self.inspector_mix);form.addRow('Pan',self.pan)
        self.muted=QCheckBox('Muted');self.muted.clicked.connect(self.inspector_mix);form.addRow('',self.muted);layout.addLayout(form)
        self.loop_track=QCheckBox('Loop track to song end');self.loop_track.setAccessibleName('Loop selected track to song end')
        self.loop_track.setToolTip('Repeat the current track arrangement from its first clip to its last clip, preserving gaps. Disable this to place clips after that cycle.')
        self.loop_track.clicked.connect(lambda:self.toggle_track_loop(self.role));layout.addWidget(self.loop_track)
        layout.addWidget(button('Loop selected clip…',self.loop_clip_dialog));layout.addWidget(button('Move selected clip…',self.move_clip_dialog))
        layout.addWidget(button('Add pattern here',self.add_pattern));layout.addWidget(button('New song',self.new_song));layout.addWidget(button('Regenerate variation',lambda:self.change(self.editor.regenerate)))
        self.inspector_info=QLabel();self.inspector_info.setWordWrap(True);self.inspector_info.setObjectName('muted');layout.addWidget(self.inspector_info)
        layout.addStretch();scale_label=QLabel('Interface scale');layout.addWidget(scale_label);self.scale=QComboBox()
        for label,value in [('100%',1),('125%',1.25),('150%',1.5)]:self.scale.addItem(label,value)
        self.scale.currentIndexChanged.connect(lambda:self._apply_scale(self.scale.currentData()));layout.addWidget(self.scale)
        self.inspector_panel=panel
        if self._safe_workspace:self.dock_tabs.addTab(panel,'Inspector')
        else:self.inspector_dock.setWidget(panel);self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea,self.inspector_dock)

    def _make_browser(self):
        self.browser_dock=None
        tabs=QTabWidget();self.browser_tabs=tabs
        if self._safe_workspace:self.dock_tabs.addTab(tabs,'Browser')
        else:
            self.browser_dock=QDockWidget('Browser',self);self.browser_dock.setObjectName('browserDock')
            self.browser_dock.setWidget(tabs);self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea,self.browser_dock)
        pack_panel=QWidget();layout=QVBoxLayout(pack_panel);layout.addWidget(button('Load Song Pack…',self.load_pack_dialog))
        self.pack_label=QLabel();self.pack_label.setWordWrap(True);layout.addWidget(self.pack_label)
        layout.addWidget(QLabel('Full-length demos'))
        self.full_demos=QComboBox();self.full_demos.setAccessibleName('Full-length song demos')
        self.full_demos.setMinimumContentsLength(16);self.full_demos.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        for path in sorted((ROOT/'packs').glob('*_full.prdeproj')):
            project=load_project(path);seconds=round(quarter_seconds(beat(project['length']),project['tempoMap']))
            title=project['title'].removesuffix(' — full-length demo')
            self.full_demos.addItem(f'{title} · {seconds//60}:{seconds%60:02d}',project['packReference']['packId'])
        self.full_demos.setCurrentIndex(max(0,self.full_demos.findData('parachute')));layout.addWidget(self.full_demos)
        self.full_demo_button=button('Load full demo',lambda:self.load_full_demo(self.full_demos.currentData()))
        self.full_demo_button.setEnabled(self.full_demos.count()>0);layout.addWidget(self.full_demo_button)
        self.catalog_summary=QLabel();self.catalog_summary.setWordWrap(True);layout.addWidget(self.catalog_summary)
        self.arrangements=QListWidget();self.arrangements.setAccessibleName('Included pack arrangements');self.arrangements.itemDoubleClicked.connect(lambda _:self.load_arrangement());layout.addWidget(self.arrangements,1)
        for path in sorted((ROOT/'packs').glob('*.prdeproj')):
            try:project=load_project(path)
            except (ValueError,OSError):continue
            row=QListWidgetItem(path.stem.replace('_',' ').title());row.setData(Qt.ItemDataRole.UserRole,str(path));row.setToolTip(project['title']);self.arrangements.addItem(row)
        self.catalog_summary.setText(f"{len(list((ROOT/'packs').glob('*.prdepack')))} Song Packs · {self.arrangements.count()} editable arrangements · {self.full_demos.count()} full demos")
        layout.addWidget(button('Load arrangement',self.load_arrangement));tabs.addTab(pack_panel,'Packs')
        self.progression_browser=ProgressionBrowser(self);self.presets=self.progression_browser.list;tabs.addTab(self.progression_browser,'Progressions')
        pattern_panel=QWidget();layout=QVBoxLayout(pattern_panel);self.source_clips=QListWidget();layout.addWidget(QLabel('Patterns recovered from active source'));layout.addWidget(self.source_clips,1);layout.addWidget(button('Place source pattern here',self.place_source));tabs.addTab(pattern_panel,'Patterns')
        self.clip_browser=ClipBrowser(self);tabs.insertTab(0,self.clip_browser,'MIDI clips');tabs.setCurrentWidget(self.progression_browser)
        self.timeline.clip_dropped.connect(self.drop_clip)
        if not self._safe_workspace:self.resizeDocks([self.inspector_dock,self.browser_dock],[205,245],Qt.Orientation.Horizontal)

    def _make_mixer(self):
        panel=QWidget();layout=QVBoxLayout(panel);self.mixer=QTableWidget(0,5);self.mixer.setHorizontalHeaderLabels(['Channel / bus','Level · dB','Pan · %','Mute','Drum EQ'])
        self.mixer.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch);layout.addWidget(self.mixer,1)
        layout.addWidget(button('Apply punch mix · drum EQ + buses + kick → bass',lambda:self.change(lambda:self.editor.apply('Apply punch mix',apply_punch_mix))))
        label=QLabel('Each drum → its EQ → drum compressor + boost → master. The kick ducks only bass. Older saved mixes retain their sound until you apply a preset.');label.setWordWrap(True);label.setObjectName('muted');layout.addWidget(label)
        self.dock_tabs.insertTab(2,panel,'Mixer')
        processing_panel=QWidget();processing_layout=QVBoxLayout(processing_panel);scroll=QScrollArea();scroll.setWidgetResizable(True)
        inner=QWidget();form=QFormLayout(inner);self.dynamics_controls={}
        definitions=[('drumBusCompressor','Drum bus compressor',DRUM_COMPRESSOR),
                     ('bassSidechain','Kick → bass sidechain',BASS_SIDECHAIN),
                     ('compressor','Master compressor',dict(on=True,thresholdDb=-18,ratio=2,attackMs=10,releaseMs=150,makeupDb=0))]
        for key,title,defaults in definitions:
            enabled=QCheckBox(title);enabled.clicked.connect(lambda _,key=key:self.set_dynamics(key));form.addRow(enabled)
            widgets={'on':enabled}
            for parameter,label_text in [('thresholdDb','Threshold'),('ratio','Ratio'),('attackMs','Attack'),('releaseMs','Release'),('makeupDb','Makeup / boost'),('maxDuckDb','Maximum duck')]:
                if parameter not in defaults:continue
                low,high,digits,suffix={'thresholdDb':(-60 if key=='bassSidechain' else -48,0,1,' dB'),'ratio':(1,20,1,':1'),
                    'attackMs':(.1,100,1,' ms'),'releaseMs':(10,2000,0,' ms'),'makeupDb':(-12,12,1,' dB'),'maxDuckDb':(0,18,1,' dB')}[parameter]
                widget=spin(low,high,defaults[parameter],digits,suffix);widget.setAccessibleName(title+' '+label_text)
                widget.editingFinished.connect(lambda key=key:self.set_dynamics(key));widgets[parameter]=widget;form.addRow(label_text,widget)
            self.dynamics_controls[key]=widgets
        self.compressor=self.dynamics_controls['compressor']['on'];self.threshold=self.dynamics_controls['compressor']['thresholdDb'];self.ratio=self.dynamics_controls['compressor']['ratio']
        scroll.setWidget(inner);processing_layout.addWidget(scroll)
        note=QLabel('Static settings are saved and undoable. Bypass removes that processor’s gain as well. Reverb, delay and VST inserts remain forthcoming.');note.setWordWrap(True);processing_layout.addWidget(note)
        self.dock_tabs.insertTab(3,processing_panel,'Dynamics')

    def _bootstrap(self,project_path,pack_path):
        if project_path:
            self.load_session(Path(project_path),Path(pack_path) if pack_path else None);return
        if self._settings:
            previous=self._settings.value('project');previous_pack=self._settings.value('pack')
            if previous and Path(previous).is_file() and previous_pack and Path(previous_pack).is_file():
                if self.load_session(Path(previous),Path(previous_pack)):return
        if pack_path:self.load_pack(Path(pack_path));return
        path=ROOT/'packs/parachute_a.prdeproj'
        if not path.exists():path=next(iter(sorted((ROOT/'packs').glob('*.prdeproj'))),None)
        if path:self.load_session(path)
        else:self.notice('Choose Load Song Pack in the Browser to begin.')

    def notice(self,text):self.message.setText(text)

    def confirm_discard(self):
        if not self.editor or not self.editor.dirty:return True
        answer=QMessageBox.question(self,'Unsaved project','Save your current project before continuing?',
            QMessageBox.StandardButton.Save|QMessageBox.StandardButton.Discard|QMessageBox.StandardButton.Cancel,QMessageBox.StandardButton.Save)
        if answer==QMessageBox.StandardButton.Save:return self.save()
        if answer==QMessageBox.StandardButton.Discard:self.recovery_file.unlink(missing_ok=True)
        return answer==QMessageBox.StandardButton.Discard

    def find_pack(self,project,path):
        candidates=[path.parent/(project['packReference']['packId']+'.prdepack'),ROOT/'packs'/(project['packReference']['packId']+'.prdepack')]
        if self.pack and self.pack.manifest['packId']==project['packReference']['packId']:candidates.insert(0,self.pack.path)
        for candidate in candidates:
            if candidate.is_file():
                try:
                    with Pack(candidate) as bank:
                        if bank.manifest_hash==project['packReference']['manifestSha256']:return candidate
                except (ValueError,OSError):continue
        value,_=QFileDialog.getOpenFileName(self,'Choose the exact Song Pack used by this project',str(path.parent),'Song Pack (*.prdepack)')
        return Path(value) if value else None

    def load_session(self,path,pack_path=None):
        try:
            project=load_project(path);pack_path=pack_path or self.find_pack(project,path)
            if pack_path is None:return False
            bank=Pack(pack_path)
            try:
                bundled=path.resolve().parent==(ROOT/'packs').resolve()
                editor=Editor(project,bank,None if bundled else path);editor.saved=canonical_bytes(editor.project)
            except Exception:bank.close();raise
            self._activate(editor,bank);self.notice('')
            if self._settings:self._settings.setValue('project',str(path.resolve()));self._settings.setValue('pack',str(bank.path.resolve()))
            return True
        except (ValueError,OSError,KeyError) as error:self.notice('Could not open project: '+str(error));return False

    def _activate(self,editor,bank):
        self.stop();old=self.pack;self.pack=bank;self.editor=editor
        self._preview_key=None;self.player.setSource(QUrl())
        if old is not None:old.close()
        selection=editor.project['editorContext']['selection']
        self.selected_id=next((i['id'] for i in editor.project['instances'] if i['id']==selection or i['patternId']==selection),'')
        self.cursor=beat(editor.project['editorContext']['scrollBeat'])
        if self.selected_id:self.role=editor.pattern(self.selected_id)['role'];self.cursor=beat(editor.instance(self.selected_id)['beat'])
        if self.cursor>=beat(editor.project['length']):self.cursor=Fraction(0)
        self.refresh();self.timeline_scroll.horizontalScrollBar().setValue(round(float(beat(editor.project['editorContext']['scrollBeat']))*self.timeline.pixels_per_beat))

    def load_pack(self,path):
        try:
            bank=Pack(path);tonic=0;mode='major'
            for source in sorted((ROOT/'packs').glob('*.prdeproj')):
                try:prototype=load_project(source)
                except (ValueError,OSError):continue
                if prototype['packReference']==dict(packId=bank.manifest['packId'],manifestSha256=bank.manifest_hash):
                    tonic=prototype['tonalityMap'][0]['tonic'];mode=prototype['tonalityMap'][0]['mode'];break
            editor=Editor(new_project(bank,tonic,mode),bank);editor.saved=canonical_bytes(editor.project);self._activate(editor,bank);return True
        except (ValueError,OSError) as error:self.notice('Could not load Song Pack: '+str(error));return False

    def load_pack_dialog(self):
        value,_=QFileDialog.getOpenFileName(self,'Load Song Pack',str(ROOT/'packs'),'Song Pack (*.prdepack)')
        if value and self.confirm_discard():self.load_pack(Path(value))

    def open_project_dialog(self):
        value,_=QFileDialog.getOpenFileName(self,'Open project',str(self.data_dir),'PRDE1 project (*.prdeproj)')
        if value and self.confirm_discard():self.load_session(Path(value))

    def load_arrangement(self):
        row=self.arrangements.currentItem()
        if row and self.confirm_discard():self.load_session(Path(row.data(Qt.ItemDataRole.UserRole)))

    def load_full_demo(self,pack_id='parachute'):
        if self.confirm_discard():return self.load_session(ROOT/'packs'/(pack_id+'_full.prdeproj'))
        return False

    def new_song(self):
        if not self.editor or not self.confirm_discard():return
        tone=at(self.editor.project['tonalityMap'],self.cursor)
        # Reuse the validated bank; do not close its materialized samples.
        self.stop();self.editor=Editor(new_project(self.pack,tone['tonic'],tone['mode']),self.pack);self.editor.saved=canonical_bytes(self.editor.project)
        self.selected_id='';self.cursor=Fraction(0);self._preview_key=None;self.player.setSource(QUrl());self.refresh()
        self.choose_progression()

    def save(self,save_as=False):
        if not self.editor:return False
        path=None
        if save_as or self.editor.path is None:
            suggested=self.editor.path or self.data_dir/'My_song.prdeproj'
            value,_=QFileDialog.getSaveFileName(self,'Save project',str(suggested),'PRDE1 project (*.prdeproj)')
            if not value:return False
            path=Path(value)
            if path.suffix!='.prdeproj':path=path.with_name(path.name+'.prdeproj')
        try:
            self.editor.save(path)
            if self._settings:self._settings.setValue('project',str(self.editor.path.resolve()));self._settings.setValue('pack',str(self.pack.path.resolve()))
            self.recovery_file.unlink(missing_ok=True);self.refresh();self.notice('Saved '+str(self.editor.path));return True
        except (ValueError,OSError) as error:self.notice('Save failed; your session remains open: '+str(error));return False

    def autosave(self):
        if not self.editor or not self.editor.dirty or self._closing:return
        try:
            atomic_json(self.recovery_file,dict(format='prde1-desktop-recovery-1',project=self.editor.project,
                pack=str(self.pack.path.resolve()),path=str(self.editor.path.resolve()) if self.editor.path else None))
            self.save_status.setText('Unsaved · recovery copy saved')
        except OSError as error:self.notice('Recovery copy failed — save to another location: '+str(error))

    def recover(self):
        if not self._recoveries or not self.confirm_discard():return
        recovery=self._recoveries[0]
        try:
            if recovery.stat().st_size>16*1024*1024:raise ContractError('Recovery manifest exceeds 16 MiB')
            record=read_json(recovery.read_bytes())
            if record['format']!='prde1-desktop-recovery-1':raise ContractError('Unknown recovery format')
            bank=Pack(Path(record['pack']))
            try:editor=Editor(record['project'],bank,record['path']);editor.saved=None
            except Exception:bank.close();raise
            self._activate(editor,bank);recovery.unlink();self._recoveries.pop(0);self.recover_button.setVisible(bool(self._recoveries));self.autosave();self.notice('Recovered unsaved session. Save it when ready.')
        except (ValueError,OSError,KeyError) as error:self.notice('Recovery failed; the recovery file is retained: '+str(error))

    def change(self,operation,*,keep_note_preview=False):
        if not self.editor:return
        serial=self.editor.serial
        try:operation()
        except (ValueError,OSError,KeyError,StopIteration) as error:
            if self._note_preview:self._note_preview.stop()
            self.notice(str(error));self.refresh();return
        if self.editor.serial!=serial:
            self.editor.project['editorContext']['selection']=self.selected_id
            self.stop(stop_notes=not keep_note_preview);self._preview_key=None;self.player.setSource(QUrl());self.notice('');self.refresh();self.autosave()

    def undo(self):self.change(self.editor.undo) if self.editor else None
    def redo(self):self.change(self.editor.redo) if self.editor else None

    def select(self,role,position,instance_id):
        if not self.editor:return
        self.cursor=position
        if role:self.role=role
        self.selected_id=instance_id
        if instance_id:self.role=self.editor.pattern(instance_id)['role']
        self.editor.project['editorContext']['selection']=instance_id
        self.refresh()
        if instance_id:self.dock_tabs.setCurrentWidget(self.sequencer)
        self.fit_step_panes()

    def select_role(self):
        if not self._refreshing and self.editor:
            role=self.track.currentData()
            from .project import arrangement_spans
            match=next((i for i,p,start,length,_ in arrangement_spans(self.editor.project) if p['role']==role and start<=self.cursor<start+length),None)
            self.select(role,self.cursor,match['id'] if match else '')

    def move_clip(self,instance_id,position):
        def op():
            self.editor.move_instance(instance_id,position);self.selected_id=instance_id;self.cursor=position
        self.change(op)

    def resize_clip(self,instance_id,length):
        self.change(lambda:self.editor.resize_instance(instance_id,length))

    def _clip_position_dialog(self,instance_id,length):
        instance_id=instance_id or self.selected_id
        if not self.editor or not instance_id:self.notice('Select a clip on the timeline first.');return
        dialog=QDialog(self);dialog.setWindowTitle('Loop clip length' if length else 'Move clip');layout=QVBoxLayout(dialog)
        help_text=QLabel('Repeat the editable source pattern for this many quarter-note beats. A fractional final cycle is allowed.' if length else 'Move this clip to a quarter-note beat position. Occupied material is protected.')
        help_text.setWordWrap(True);layout.addWidget(help_text)
        value=QLineEdit(str(self.editor.instance_length(instance_id) if length else self.editor.instance(instance_id)['beat']))
        value.setAccessibleName('Clip playback length in beats' if length else 'Clip start position in beats');layout.addWidget(value)
        error=QLabel();error.setWordWrap(True);error.setObjectName('warning');layout.addWidget(error)
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel);layout.addWidget(buttons);buttons.rejected.connect(dialog.reject)
        def apply():
            try:
                position=beat(value.text())
                operation=self.editor.resize_instance if length else self.editor.move_instance
                operation(instance_id,position)
            except (ValueError,OSError,KeyError) as problem:error.setText(str(problem));return
            if not length:self.cursor=position
            self.selected_id=instance_id;self.stop();self._preview_key=None;self.player.setSource(QUrl());self.refresh();self.autosave();dialog.accept()
        buttons.accepted.connect(apply);value.selectAll();value.setFocus();dialog.exec()

    def move_clip_dialog(self,instance_id=''):
        self._clip_position_dialog(instance_id,False)

    def loop_clip_dialog(self,instance_id=''):
        self._clip_position_dialog(instance_id,True)

    def toggle_track_loop(self,role):
        if self.editor:self.change(lambda:self.editor.set_track_loop(role,role not in self.editor.project.get('trackLoops',{})))

    def set_playback_loop(self,on):
        if not self.editor or self._refreshing:return
        self.editor.set_playback_loop(on);self._sync_player_loop();self.refresh();self.autosave()

    def _sync_player_loop(self):
        loop=self._playback_scope['loop'] if self._playback_scope else bool(self.editor and self.editor.project.get('loopPlayback',False))
        self.player.setLoops(QMediaPlayer.Loops.Infinite if loop else QMediaPlayer.Loops.Once)

    def set_tonality(self):
        if self.editor:self.change(lambda:self.editor.set_map('tonalityMap',self.cursor,dict(tonic=self.tonic.currentIndex(),mode=self.mode.currentData()),'Set key and mode'))

    def set_tempo(self):
        if self.editor and not self._refreshing:
            if any(lane['takes'] for lane in self.editor.project['vocals']):
                answer=QMessageBox.question(self,'Tempo and recorded vocals','Recorded takes stay anchored in seconds and may no longer align. Change tempo?',QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No,QMessageBox.StandardButton.No)
                if answer!=QMessageBox.StandardButton.Yes:self.refresh();return
            self.change(lambda:self.editor.set_map('tempoMap',self.cursor,dict(quarterBpm=self.tempo.value()),'Change tempo'))

    def set_meter(self):
        if not self.editor:return
        start=next(start for start,length,_ in measures(self.editor.project) if start<=self.cursor<start+length)
        n,d=self.meter.currentData()
        self.change(lambda:self.editor.set_map('meterMap',start,dict(numerator=n,denominator=d,governorSegments=self.grid.currentData()),'Change meter/grid without quantizing'))

    def resize_song(self):
        if self.editor and not self._refreshing:self.change(lambda:self.editor.resize(self.bars.value()))

    def set_zoom(self,value):
        if self.editor and not self._refreshing:self.editor.project['editorContext']['zoom']=value/100;self.timeline.refresh(self.editor,self.selected_id,self.cursor)

    def _scroll_changed(self,value):
        if self.editor and not self._refreshing:self.editor.project['editorContext']['scrollBeat']=str(Fraction(value/self.timeline.pixels_per_beat).limit_denominator(100000))

    def edit_chord(self,position):
        if not self.editor:return
        dialog=ChordDialog(self.editor,position,self)
        if dialog.exec()==QDialog.DialogCode.Accepted:self.change(lambda:self.editor.set_chord(position,dialog.value()))

    def custom_dialog(self):
        if not self.editor:return
        dialog=QDialog(self);dialog.setWindowTitle('Custom progression');dialog.setMinimumWidth(470);layout=QVBoxLayout(dialog)
        help_text=QLabel('Author Roman chords with their exact qualities, e.g. i IIImaj7 VI iv. Numbers 1–7 explicitly derive the quality from the mode.');help_text.setWordWrap(True);layout.addWidget(help_text)
        form=QFormLayout();chords=QLineEdit(' '.join(roman(v['chord']) for v in self.editor.project['harmony'][:16]));durations=QLineEdit('1');form.addRow('Chord sequence',chords);form.addRow('Duration per chord · one value or a list',durations)
        unit=QComboBox();unit.addItem('Measures / bars','bars');unit.addItem('Quarter-note beats','beats');form.addRow('Duration unit',unit)
        basis=QComboBox();basis.addItem('Mode-relative roots (Raw Daw)','mode-relative');basis.addItem('Major-relative roots (common song charts)','major-relative');form.addRow('Roman numeral basis',basis)
        name=QLineEdit('My progression');form.addRow('Bank name',name);layout.addLayout(form)
        chords.setObjectName('progressionNotation');durations.setObjectName('progressionDurations');name.setObjectName('progressionName')
        chords.setAccessibleName('Custom chord sequence');durations.setAccessibleName('Duration per custom chord');name.setAccessibleName('Custom progression bank name')
        save_to_bank=QCheckBox('Save to My bank for future songs');save_to_bank.setChecked(True);layout.addWidget(save_to_bank)
        preview=QLabel('This replaces only the chord lane, repeating the sequence to the song ending. Instrumental patterns are retained.');preview.setWordWrap(True);layout.addWidget(preview)
        error=QLabel();error.setObjectName('warning');error.setWordWrap(True);layout.addWidget(error)
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel);buttons.rejected.connect(dialog.reject);layout.addWidget(buttons)
        def apply():
            try:
                import re
                tokens=re.split(r'[\s,–—-]+',chords.text().strip());kind='degrees' if all(t in tuple(str(i) for i in range(1,8)) for t in tokens) else 'chords'
                entry=progression_bank.validate_entry(dict(name=name.text(),kind=kind,basis='mode-relative' if kind=='degrees' else basis.currentData(),sequence=chords.text(),
                    durations=durations.text().replace(',',' ').split(),durationUnit=unit.currentData()))
                candidate=Editor(self.editor.project,self.pack);progression_bank.load_into(candidate,entry,grow_empty=True)
                if save_to_bank.isChecked():self.progression_bank.import_entries([entry])
                self.editor.apply('Load custom progression: '+entry['name'],lambda _:candidate.project)
            except (ValueError,KeyError,OSError) as e:error.setText(str(e));return
            dialog.accept()
        buttons.accepted.connect(apply)
        if dialog.exec()==QDialog.DialogCode.Accepted:self.stop();self._preview_key=None;self.player.setSource(QUrl());self.refresh();self.autosave()

    def apply_preset(self):
        self.progression_browser.load_selected()

    def choose_progression(self):
        self.browser_tabs.setCurrentWidget(self.progression_browser)
        if self.focus_action.isChecked():self.focus_action.setChecked(False);self.focus_view()
        if self.dock_tabs.indexOf(self.browser_tabs)>=0:self.dock_tabs.setCurrentWidget(self.browser_tabs)
        elif self.browser_dock:self.browser_dock.show();self.browser_dock.raise_()
        self.progression_browser.search.setFocus()

    def _free_space(self,role,position,length,exclude=''):
        self.editor.check_instance_space(role,position,length,exclude)

    def add_pattern(self):
        if not self.editor:return
        length=next(length for start,length,_ in measures(self.editor.project) if start<=self.cursor<start+length)
        def op():self._free_space(self.role,self.cursor,length);self.selected_id=self.editor.add_pattern(self.role,self.cursor,length)
        self.change(op)

    def place_source(self):
        if not self.editor or not self.source_clips.currentItem():return
        _,pattern=self.source_clips.currentItem().data(Qt.ItemDataRole.UserRole)
        def op():
            meter=at(self.editor.project['meterMap'],self.cursor);bar=Fraction(4*meter['numerator'],meter['denominator'])
            if beat(pattern['length'])!=bar:raise ContractError('Source pattern meter differs. No automatic timing conversion is applied')
            self._free_space(pattern['role'],self.cursor,beat(pattern['length']))
            self.selected_id=self.editor.add_pattern(pattern['role'],self.cursor,beat(pattern['length']),pattern);self.role=pattern['role']
        self.change(op)

    def place_clip(self,clip=None,position=None):
        clip=clip or self.clip_browser.selected()
        if not self.editor or not clip:return
        position=self.cursor if position is None else position
        bar=clip_library.bar_at(self.editor.project,position)
        if bar is None:return
        position=bar[0];reports=[]
        def op():
            self.selected_id,report=clip_library.place(self.editor,clip,position)
            reports.extend(report);self.role=clip['role'];self.cursor=position
        serial=self.editor.serial;self.change(op)
        if self.editor.serial!=serial:
            self.dock_tabs.setCurrentWidget(self.sequencer)
            self.notice('Placed '+clip['name']+('. '+ '; '.join(reports) if reports else ''))

    def drop_clip(self,clip_id,role,position):
        try:
            clip=clip_library.find(clip_id)
            if clip['role']!=role:raise ContractError('Drop this clip on its '+('Chords' if clip['role']=='rhythm' else clip['role'].title())+' track.')
            self.place_clip(clip,position)
        except (ValueError,KeyError,StopIteration) as error:self.notice(str(error))

    def preview_clip(self):
        clip=self.clip_browser.selected()
        if not self.editor or not clip:return
        try:
            start=clip_library.bar_at(self.editor.project,self.cursor)[0]
            project=clip_library.audition(self.editor,clip,start)
            _,reports=clip_library.native_pattern(self.editor,clip,start)
            self.stop();self._playback_scope=dict(start=str(start),instance=None,loop=True,kind='library')
            self.request_render(autoplay=True,preview_project=project,scope=self._playback_scope)
            self.notice('Previewing '+clip['name']+('. '+'; '.join(reports) if reports else ''))
        except (ValueError,KeyError,StopIteration) as error:self.notice(str(error))

    def export_library_midi(self):
        clip=self.clip_browser.selected()
        if not clip:return
        path,_=QFileDialog.getSaveFileName(self,'Save source MIDI clip',clip['id']+'.mid','MIDI (*.mid)')
        if path:
            try:
                target=Path(path)
                if target.suffix.lower() not in ('.mid','.midi'):target=target.with_suffix('.mid')
                # The bundled source performance is distinct from resolved pattern MIDI.
                from .contracts import atomic_json
                raw=clip_library.midi_bytes(clip);source=self.work/'library-export.mid';source.write_bytes(raw);atomic_copy(source,target)
                atomic_json(target.with_suffix('.credits.json'),{k:v for k,v in clip.items() if k!='pattern'})
                self.notice('Saved source MIDI and its license credits. Placed-pattern Export MIDI uses your current harmony and pulse.')
            except (ValueError,OSError,KeyError) as error:self.notice(str(error))

    def copy_dialog(self):
        if not self.editor or not self.selected_id:self.notice('Select a pattern on the timeline first.');return
        dialog=QDialog(self);dialog.setWindowTitle('Duplicate pattern');layout=QVBoxLayout(dialog);form=QFormLayout();destination=QComboBox()
        for n,(start,_,_) in enumerate(measures(self.editor.project)):destination.addItem('Measure '+str(n+1),start)
        instance=self.editor.instance(self.selected_id);next_position=beat(instance['beat'])+beat(self.editor.pattern(self.selected_id)['length']);index=destination.findData(next_position)
        destination.setCurrentIndex(max(0,index));form.addRow('Destination',destination);layout.addLayout(form)
        linked=QCheckBox('Linked Repeat · edits affect every linked occurrence');harmony=QCheckBox('Include Harmony · replace destination chords');layout.addWidget(linked);layout.addWidget(harmony)
        help_text=QLabel('Ordinary copies are independent and follow the destination harmony.');help_text.setWordWrap(True);layout.addWidget(help_text)
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel);buttons.accepted.connect(dialog.accept);buttons.rejected.connect(dialog.reject);layout.addWidget(buttons)
        if dialog.exec()!=QDialog.DialogCode.Accepted:return
        if harmony.isChecked() and QMessageBox.warning(self,'Replace destination harmony','Include Harmony overwrites destination chord events. Continue?',QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No,QMessageBox.StandardButton.No)!=QMessageBox.StandardButton.Yes:return
        def op():
            pattern=self.editor.pattern(self.selected_id);self._free_space(pattern['role'],destination.currentData(),beat(pattern['length']))
            self.selected_id=self.editor.copy(self.selected_id,destination.currentData(),linked.isChecked(),harmony.isChecked());self.cursor=destination.currentData()
        self.change(op)

    def detach_selected(self):
        if self.editor and self.selected_id:self.change(lambda:self.editor.detach(self.selected_id))

    def remove_selected(self):
        if self.editor and self.selected_id:
            def op():self.editor.remove_instance(self.selected_id);self.selected_id=''
            self.change(op)

    def toggle_step(self,row,column):
        self.sequencer.toggle(row,column)

    def edit_selected_event(self):
        if not self.editor or not self.selected_id or self.events.currentRow()<0:return
        event_id=self.events.item(self.events.currentRow(),0).data(Qt.ItemDataRole.UserRole)
        event=next(e for e in self.editor.pattern(self.selected_id)['events'] if e['id']==event_id)
        dialog=EventDialog(self.editor,self.selected_id,event,self)
        if dialog.exec()==QDialog.DialogCode.Accepted:self.stop();self._preview_key=None;self.player.setSource(QUrl());self.refresh();self.autosave()

    def delete_selected_event(self):
        if self.editor and self.selected_id and self.events.currentRow()>=0:
            event_id=self.events.item(self.events.currentRow(),0).data(Qt.ItemDataRole.UserRole);self.change(lambda:self.editor.delete_event(self.selected_id,event_id))

    def inspector_mix(self):
        if self.editor and not self._refreshing:self.change(lambda:self.editor.set_mix(self.role,gainDb=self.gain.value(),pan=self.pan.value()/100,muted=self.muted.isChecked()))

    def set_compressor(self):
        self.set_dynamics('compressor')

    def set_dynamics(self,key):
        if self.editor and not self._refreshing:
            widgets=self.dynamics_controls[key]
            values={name:widget.isChecked() if name=='on' else widget.value() for name,widget in widgets.items()}
            self.change(lambda:self.editor.apply('Adjust '+key,lambda p:p['mix'].__setitem__(key,values)))

    def edit_drum_eq(self,name):
        if not self.editor:return
        slot=name[6:];ch=self.editor.project['mix']['channels'][name]
        dialog=DrumEqDialog(slot,ch.get('eq',drum_eq(slot,ch['eqPreset']=='drum-punch')),self)
        if dialog.exec()==QDialog.DialogCode.Accepted:self.change(lambda:self.editor.set_mix(name,eqPreset='custom',eq=dialog.values()))

    def refresh(self):
        if not self.editor:return
        self._refreshing=True;project=self.editor.project
        ids={i['id'] for i in project['instances']}
        if self.selected_id not in ids:self.selected_id=''
        if self.selected_id:self.role=self.editor.pattern(self.selected_id)['role']
        self.cursor=min(self.cursor,beat(project['length'])-Fraction(1,1000000))
        tone=at(project['tonalityMap'],self.cursor);meter=at(project['meterMap'],self.cursor)
        self.tonic.setCurrentIndex(tone['tonic']);self.mode.setCurrentIndex(self.mode.findData(tone['mode']));self.tempo.setValue(at(project['tempoMap'],self.cursor)['quarterBpm'])
        meter_index=self.meter.findData((meter['numerator'],meter['denominator']))
        if meter_index<0:self.meter.addItem(f'{meter["numerator"]}/{meter["denominator"]}',(meter['numerator'],meter['denominator']));meter_index=self.meter.count()-1
        self.meter.setCurrentIndex(meter_index);self.grid.setCurrentIndex(self.grid.findData(meter['governorSegments']));self.bars.setValue(len(measures(project)));self.zoom.setValue(round(project['editorContext']['zoom']*100))
        seconds=quarter_seconds(beat(project['length']),project['tempoMap']);self.duration.setText(f'{int(seconds)//60}:{int(seconds)%60:02d}')
        self.track.setCurrentIndex(self.track.findData(self.role));channel=project['mix']['channels'][self.role]
        self.gain.setValue(channel['gainDb']);self.pan.setValue(channel['pan']*100);self.muted.setChecked(channel['muted'])
        self.loop_track.setChecked(self.role in project.get('trackLoops',{}));self.loop_song.setChecked(project.get('loopPlayback',False));self._sync_player_loop()
        self.selection_label.setText(('Editing '+self.role.title()+' pattern' if self.selected_id else self.role.title()+' track')+'\n'+self.edit_position(beat(self.editor.instance(self.selected_id)['beat']) if self.selected_id else self.cursor))
        self.inspector_info.setText(('Whole chord events' if self.role=='rhythm' else 'Single prepared notes' if self.role in ('lead','bass') else 'Fixed kit sounds')+'\nOne active Song Pack\nVariation revision '+str(project['variation']['revision']))
        from .music import QUALITIES
        source=self.pack.manifest['source']
        permission=f"\n{source['license']} · noncommercial" if 'BY-NC' in source['license'] else ''
        self.pack_label.setText(source['title']+f'\n128 lead / bass pitches · {len(QUALITIES)*12} chord options'+permission)
        self.pack_label.setToolTip('Every MIDI pitch and registered chord is playable. Additional inversions are prepared when used. Native recordings and source-derived waveforms retain this pack’s instrument sound.')
        self.undo_action.setEnabled(bool(self.editor.undo_stack));self.redo_action.setEnabled(bool(self.editor.redo_stack))
        self.undo_action.setText('Undo '+self.editor.undo_stack[-1][0] if self.editor.undo_stack else 'Undo');self.redo_action.setText('Redo '+self.editor.redo_stack[-1][0] if self.editor.redo_stack else 'Redo')
        self.save_status.setText('Unsaved changes' if self.editor.dirty else ('Saved' if self.editor.path else 'Editable starter · '+__version__))
        self.setWindowTitle(project['title']+(' *' if self.editor.dirty else '')+' — Raw Daw')
        self.pulse_controls.refresh(self.editor);self.clip_browser.refresh(self.editor,self.cursor)
        self.timeline.refresh(self.editor,self.selected_id,self.cursor);self.refresh_steps();self.refresh_mixer();self.refresh_browser()
        try:
            self._plan=self.editor.plan();conflicts=self._plan['conflicts'];warnings=self._plan['warnings']
            self.issues.setPlainText(('Conflicts — authored events are retained\n'+'\n'.join(v['eventId']+': '+v['message'] for v in conflicts) if conflicts else 'All active requests resolve. Native and source-derived samples use the same mixer.')+
                '\n\nNatural limits and source notices\n'+'\n'.join(dict.fromkeys(warnings))+'\n\nSource credits\n'+'\n'.join(v['attribution']+'\n'+v['license'] for v in project['credits']))
            missing=any(v['code'].startswith('missing_') for v in conflicts)
            self.guidance.setText('Choose a covered chord or edit the flagged step — see Coverage & warnings.' if missing else f'{len(conflicts)} incompatible events are preserved and withheld. Review Coverage & warnings.' if conflicts else 'Drag clips to move; extend right edges to loop. Use ↻ to repeat tracks. Select a block to edit its steps.')
            if not project['instances']:self.guidance.setText('Choose a chord progression, then preview and place one-bar MIDI clips from the Browser. Edit any placed pattern below.')
            self.play_button.setEnabled(not missing);self.export_button.setEnabled(not missing)
        except (ValueError,OSError,KeyError) as error:
            self._plan=None;self.issues.setPlainText(str(error));self.guidance.setText('This project requests processing outside the current desktop slice. Its saved state is preserved.');self.play_button.setEnabled(False);self.export_button.setEnabled(False)
        self._refreshing=False;self._play_position(self.player.position());self._play_state(self.player.playbackState())

    def refresh_steps(self,*_):
        if not self.editor:return
        self.events.setRowCount(0);self.sequencer.refresh(self.editor,self.selected_id)
        if not self.selected_id:return
        pattern=self.editor.pattern(self.selected_id)
        events=sorted(pattern['events'],key=lambda e:(beat(e['beat']),e['id']));self.events.setRowCount(len(events))
        for row,event in enumerate(events):
            e=event['expression'];choice=event['choice'];label='Whole chord' if pattern['role']=='rhythm' else choice['soundIdentity'] if pattern['role']=='drums' else ('MIDI '+str(choice['exactMidi']) if e['lockExactPitch'] else 'Tone '+str(choice['tone']+1)+' · MIDI ~'+str(choice['registerMidi']))
            values=['Enabled' if event['enabled'] else 'Disabled',event['beat'],event['duration'],label,round(e['velocity']*100),e['playPercent'],e['changePercent'],e['variation'],'Exact pitch' if e['lockExactPitch'] else 'Role' if e['locked'] else 'Off']
            for column,value in enumerate(values):self.events.setItem(row,column,item(value,event['id'] if column==0 else None))

    def refresh_mixer(self):
        project=self.editor.project;channels=[*project['mix']['channels'].items(),('master',project['mix']['master'])]
        if not hasattr(self,'_mix_widgets'):
            self._mix_widgets={};self.mixer.setRowCount(len(channels))
            for row,(name,value) in enumerate(channels):
                self.mixer.setItem(row,0,item(name));gain=spin(-96,12,value['gainDb'],1);pan=spin(-100,100,value['pan']*100,0);mute=QCheckBox('Muted')
                gain.editingFinished.connect(lambda name=name,w=gain:self.inspector_channel(name,gainDb=w.value()))
                pan.setEnabled(name!='master');pan.editingFinished.connect(lambda name=name,w=pan:self.inspector_channel(name,pan=w.value()/100))
                mute.clicked.connect(lambda checked,name=name:self.inspector_channel(name,muted=checked))
                self.mixer.setCellWidget(row,1,gain);self.mixer.setCellWidget(row,2,pan);self.mixer.setCellWidget(row,3,mute)
                eq=button('EQ…',lambda _,name=name:self.edit_drum_eq(name)) if name.startswith('drums.') else None
                if eq:self.mixer.setCellWidget(row,4,eq)
                self._mix_widgets[name]=(gain,pan,mute,eq)
        for name,value in channels:
            gain,pan,mute,eq=self._mix_widgets[name]
            for widget in (gain,pan,mute):widget.blockSignals(True)
            gain.setValue(value['gainDb']);pan.setValue(value['pan']*100);mute.setChecked(value['muted'])
            for widget in (gain,pan,mute):widget.blockSignals(False)
            if eq:
                enabled=value.get('eq',{}).get('on',value['eqPreset']=='drum-punch')
                eq.setText(('On' if enabled else 'Off')+' · EQ…');eq.setAccessibleName(name+' EQ '+('On' if enabled else 'Off'))
        for key,widgets in self.dynamics_controls.items():
            defaults=DRUM_COMPRESSOR if key=='drumBusCompressor' else BASS_SIDECHAIN if key=='bassSidechain' else dict(makeupDb=0)
            values=dict(defaults,**project['mix'].get(key,{'on':False}))
            for name,widget in widgets.items():
                widget.blockSignals(True)
                if name=='on':widget.setChecked(values['on'])
                else:widget.setValue(values[name])
                widget.blockSignals(False)

    def inspector_channel(self,name,**values):
        if not self._refreshing:self.change(lambda:self.editor.set_mix(name,**values))

    def refresh_browser(self):
        self.progression_browser.refresh(self.editor,self.cursor)
        self.source_clips.clear()
        for row,pattern in self.editor.source_patterns():
            value=QListWidgetItem(pattern['role'].title()+' · '+row['id'].replace('_',' '));value.setData(Qt.ItemDataRole.UserRole,(row,pattern));value.setToolTip(pattern['provenance']['changes']);self.source_clips.addItem(value)

    def edit_position(self,position=None):
        position=self.cursor if position is None else position
        for index,(start,length,_) in enumerate(measures(self.editor.project)):
            if start<=position<start+length:return f'Measure {index+1} · beat {position-start+1}'
        return 'Song ending'

    def _focus_changed(self,old,new):
        if new is None:return
        editing=isinstance(new,(QLineEdit,QPlainTextEdit,QTableWidget)) or new is getattr(self,'steps',None) or new is getattr(self,'events',None)
        self.play_action.setEnabled(not editing)

    def _apply_scale(self,value):
        if value is None:return
        self._scale_value=value
        font=QFont(QApplication.instance().font());font.setPointSizeF(10*value);self.setFont(font)
        self.setStyleSheet(STYLE+f'\nQWidget {{ font-size: {10*value}pt; }}\nQLabel#brand {{ font-size: 23px; }}')
        if self.editor:
            self.timeline.header=max(108,self.timeline.fontMetrics().horizontalAdvance('GOVERNOR')+18)
            self.timeline.refresh(self.editor,self.selected_id,self.cursor)
        self.scale.blockSignals(True);self.scale.setCurrentIndex(self.scale.findData(value));self.scale.blockSignals(False)
        if self._settings and not self._safe_workspace:self._settings.setValue('scale',value)
        self._responsive_layout()
        self.fit_step_panes()

    def resizeEvent(self,event):
        super().resizeEvent(event)
        if hasattr(self,'browser_dock'):
            self._responsive_layout();QTimer.singleShot(0,self.fit_step_panes)

    def _responsive_layout(self):
        if not self._layout_ready or self._layout_changing:return
        if self._safe_workspace:
            self._compact='tabs';return
        compact='tabs' if self.width()<1280 or self._scale_value>1 else 'wide'
        if self._compact==compact or self.focus_action.isChecked():return
        self._layout_changing=True
        try:
            panels=((self.inspector_panel,self.inspector_dock,'Inspector',Qt.DockWidgetArea.LeftDockWidgetArea),
                    (self.browser_tabs,self.browser_dock,'Browser',Qt.DockWidgetArea.RightDockWidgetArea))
            for panel,dock,title,area in panels:
                if compact=='tabs':
                    self.removeDockWidget(dock);dock.hide()
                    # Explicitly release the old dock layout before QTabWidget
                    # takes ownership. Keep one live copy of each panel.
                    if dock.widget() is panel:dock.setWidget(None)
                    if self.dock_tabs.indexOf(panel)<0:self.dock_tabs.addTab(panel,title)
                else:
                    index=self.dock_tabs.indexOf(panel)
                    if index>=0:self.dock_tabs.removeTab(index)
                    if dock.widget() is not panel:dock.setWidget(panel)
                    self.addDockWidget(area,dock);dock.show();panel.show()
            # Do not tabify native docks here. Qt 6.8.3 on the Deck crashed in
            # that call while restoring scale; compact panels use central tabs.
            self._compact=compact
        finally:self._layout_changing=False

    def focus_view(self):
        focus=self.focus_action.isChecked()
        if self._safe_workspace:
            if focus:self.dock_tabs.setCurrentIndex(0)
            return
        if focus:self.inspector_dock.hide();self.browser_dock.hide()
        else:self._compact=None;self._responsive_layout()

    def reset_layout(self):
        if self._safe_workspace:
            self.focus_action.setChecked(False);self.splitter.setSizes([360,260]);return
        self._layout_changing=True
        try:self.inspector_dock.setFloating(False);self.browser_dock.setFloating(False)
        finally:self._layout_changing=False
        self.focus_action.setChecked(False)
        self._compact=None;self._responsive_layout()
        if self._compact=='wide':self.resizeDocks([self.inspector_dock,self.browser_dock],[205,245],Qt.Orientation.Horizontal)
        self.splitter.setSizes([360,260])

    def _devices_changed(self):
        if self._note_preview:self._note_preview.set_device()
        current=self.audio.device().id();devices=self.devices.audioOutputs();self.outputs.blockSignals(True);self.outputs.clear()
        for device in devices:self.outputs.addItem(device.description(),device)
        if not devices:self.outputs.addItem('No audio output detected',None)
        else:
            index=next((i for i,d in enumerate(devices) if d.id()==current),0);self.outputs.setCurrentIndex(index);self.audio.setDevice(devices[index])
        self.outputs.blockSignals(False)
        if self.player.playbackState()==QMediaPlayer.PlaybackState.PlayingState and not any(d.id()==current for d in devices):
            self.stop();self.notice('Audio output disconnected. Choose an output and press Play; playback was stopped.')

    def choose_output(self):
        if self._note_preview:self._note_preview.set_device()
        device=self.outputs.currentData()
        if device is not None:self.audio.setDevice(device)

    def play(self):
        if not self.editor:return
        if self._job:self.notice('Preparing audio. Stop cancels it.');return
        state=self.player.playbackState()
        if state==QMediaPlayer.PlaybackState.PlayingState:self.player.pause();return
        if state==QMediaPlayer.PlaybackState.PausedState and self._preview_key==self.editor.fingerprint:self.player.play();return
        self.request_render(autoplay=True)

    def stop(self,*,stop_notes=True):
        if stop_notes and self._note_preview:self._note_preview.stop()
        self._generation+=1;self._job=None
        if self.process.state()!=QProcess.ProcessState.NotRunning:self.process.kill();self.process.waitForFinished(2000)
        self.player.stop();self.timeline.play_beat=None;self.timeline.update();self.seek.setValue(0)
        self.play_button.setText('Play');self.stop_button.setText('Stop')
        self._playback_scope=None;self.sequencer.playhead(None)

    def set_note_preview_enabled(self,on):
        if self._settings:self._settings.setValue('previewNotes',on)
        if not on and self._note_preview:self._note_preview.stop()

    def preview_note(self,instance_id,identity,position,event_id=None):
        from .sequencer import placement_preview_plan
        from .note_preview import NotePreview
        try:
            plan=placement_preview_plan(self.editor,instance_id,identity,position,event_id)
            if self._note_preview is None:self._note_preview=NotePreview(self.work/'notes',lambda:self.outputs.currentData(),self.notice,self)
            return self._note_preview.request(plan,self.pack.root,self.pack.manifest_hash)
        except (ValueError,OSError,StopIteration) as error:
            if self._note_preview:self._note_preview.stop()
            self.notice('Note preview: '+str(error))

    def audition_steps(self,instance_id,row,column,loop):
        from .sequencer import audition_project
        def render():
            project,start=audition_project(self.editor,instance_id,row,column)
            self.stop()
            self.request_render(autoplay=True,preview_project=project,scope=dict(instance=instance_id,start=str(start),loop=loop,kind='note' if row else 'pattern'))
        try:render()
        except (ValueError,OSError) as error:self.notice(str(error))

    def request_render(self,*,autoplay=False,destination=None,preview_project=None,scope=None):
        """Preview and export share one resolved native plan; every job owns its output."""
        if not self.editor:return False
        if self._job:self.notice('An audio render is already running. Stop it before starting another.');return False
        try:
            if preview_project is None:plan=self.editor.plan()
            else:
                from .governor import resolve
                plan=resolve(preview_project,self.pack)
            if any(v['code'].startswith('missing_') for v in plan['conflicts']):raise ContractError('Prepared sound requests are missing. Resolve Coverage & warnings before export/playback')
            executable=ROOT/'build/prde1-render'
            if not executable.is_file():raise ContractError('Native renderer is missing. Relaunch with run-raw-daw.sh to build it')
        except (ValueError,OSError) as error:self.notice(str(error));return False
        key=self.editor.fingerprint
        source_key=key
        if preview_project is not None:key+=':'+hashlib.sha256(canonical_bytes(preview_project)).hexdigest()
        if destination is None:
            self._playback_scope=scope
            if scope is not None:scope['tempoMap']=preview_project['tempoMap']
        if destination is None and self._preview_key==key and (self.work/'preview.wav').is_file():
            if autoplay:self._start_player(self.work/'preview.wav')
            return True
        self._generation+=1;generation=self._generation;folder=self.work/str(generation);folder.mkdir()
        path=folder/'plan.json';path.write_bytes(canonical_bytes(plan));output=folder/'render.wav'
        self._job=dict(generation=generation,key=key,output=output,autoplay=autoplay,destination=Path(destination) if destination else None,
                       project=copy.deepcopy(self.editor.project),plan=plan,sourceKey=source_key,previewProject=preview_project,scope=scope)
        self.process.setProgram(str(executable));self.process.setArguments([str(path),str(self.pack.root),str(output),'0'])
        self.process.start();self.play_button.setText('Preparing…');self.stop_button.setText('Cancel render');self.notice('Preparing the current arrangement; editing or Stop cancels this render.')
        return True

    def _process_error(self,error):
        if self._job and error==QProcess.ProcessError.FailedToStart:self._job=None;self.play_button.setText('Play');self.stop_button.setText('Stop');self.notice('Renderer could not start: '+self.process.errorString())

    def _render_finished(self,exit_code,exit_status):
        job=self._job;self._job=None
        output=bytes(self.process.readAllStandardOutput());error=bytes(self.process.readAllStandardError()).decode('utf-8','replace')
        if job is None or job['generation']!=self._generation or self._closing:return
        self.play_button.setText('Play');self.stop_button.setText('Stop')
        if exit_code!=0 or exit_status!=QProcess.ExitStatus.NormalExit:self.notice('Render failed; any existing export is intact: '+error.strip());return
        if job['sourceKey']!=self.editor.fingerprint:self.notice('The arrangement changed; render again to hear the current edit.');return
        try:
            report=json.loads(output)
            if job['destination']:
                atomic_copy(job['output'],job['destination']);report.update(credits=job['project']['credits'],packReference=job['project']['packReference'],
                    conflicts=job['plan']['conflicts'],warnings=job['plan']['warnings'])
                atomic_json(job['destination'].with_suffix('.report.json'),report);self.notice('Exported '+str(job['destination']))
            else:
                atomic_copy(job['output'],self.work/'preview.wav');self._preview_key=job['key'];self.notice('Preview ready · '+str(len(job['plan']['events']))+' source events')
                self._playback_scope=job['scope']
                if self._playback_scope:self._playback_scope['tempoMap']=job['previewProject']['tempoMap']
                if job['autoplay']:self._start_player(self.work/'preview.wav')
        except (ValueError,OSError) as error:self.notice('Could not finish the render: '+str(error))

    def _start_player(self,path):
        if self.outputs.currentData() is None:self.notice('Preview rendered, but no audio output is available. Connect/select an output and press Play.');return
        self._pending_seek=0 if self._playback_scope else round(quarter_seconds(self.cursor,self.editor.project['tempoMap'])*1000)
        self._sync_player_loop()
        self.player.setSource(QUrl.fromLocalFile(str(path)));self.player.play()

    def _media_status(self,status):
        if status in (QMediaPlayer.MediaStatus.LoadedMedia,QMediaPlayer.MediaStatus.BufferedMedia) and self._pending_seek:
            position=self._pending_seek;self._pending_seek=0;self.player.setPosition(position)
        if status==QMediaPlayer.MediaStatus.EndOfMedia:self.timeline.play_beat=None;self.timeline.update();self.sequencer.playhead(None)

    def _play_state(self,state):
        if self._job:return
        self.play_button.setText('Pause' if state==QMediaPlayer.PlaybackState.PlayingState else 'Resume' if state==QMediaPlayer.PlaybackState.PausedState else 'Play')

    def _play_position(self,milliseconds):
        if not self.editor:return
        if self.player.playbackState()!=QMediaPlayer.PlaybackState.StoppedState:
            if self._playback_scope:
                absolute=beat(self._playback_scope['start'])+seconds_to_beat(milliseconds/1000,self._playback_scope.get('tempoMap',self.editor.project['tempoMap']))
            else:absolute=seconds_to_beat(milliseconds/1000,self.editor.project['tempoMap'])
            self.timeline.play_beat=absolute;self.timeline.update()
            if self.selected_id:
                from .project import arrangement_spans
                active=next((absolute-start for instance,pattern,start,length,_ in arrangement_spans(self.editor.project)
                    if instance['id']==self.selected_id and start<=absolute<start+length),None)
                self.sequencer.playhead(active%beat(self.editor.pattern(self.selected_id)['length']) if active is not None else None)
        state='Preparing' if self._job else self.player.playbackState().name.replace('State','')
        self.position.setText('Edit: '+self.edit_position()+f' · {state} {milliseconds//60000}:{milliseconds//1000%60:02d}')
        if self.player.duration()>0 and not self.seek.isSliderDown():self.seek.setValue(round(milliseconds/self.player.duration()*1000))

    def seek_player(self):
        if self.player.duration()>0:self.player.setPosition(round(self.seek.value()/1000*self.player.duration()))

    def export_dialog(self):
        if not self.editor:return
        value,_=QFileDialog.getSaveFileName(self,'Export stereo WAV',str(self.data_dir/'My_song.wav'),'Stereo WAV (*.wav)')
        if value:
            path=Path(value)
            if path.suffix.lower()!='.wav':path=path.with_name(path.name+'.wav')
            self.request_render(destination=path)

    def closeEvent(self,event):
        if not self.confirm_discard():event.ignore();return
        self._closing=True;self.stop();self.autosave_timer.stop()
        if self._note_preview:self._note_preview.close()
        if self._settings and not self._safe_workspace:self._settings.setValue('geometry',self.saveGeometry());self._settings.setValue('layout',self.saveState())
        self.player.setSource(QUrl());self.recovery_file.unlink(missing_ok=True)
        if self.pack:self.pack.close();self.pack=None
        self.workspace.cleanup();event.accept()


def main(argv=None):
    parser=argparse.ArgumentParser(description='Raw Daw desktop editor')
    parser.add_argument('--project',type=Path);parser.add_argument('--pack',type=Path)
    parser.add_argument('--safe-workspace',action='store_true',help='Use central tabs and the built-in Fusion style without restoring or replacing saved layout/scale')
    options=parser.parse_args(argv)
    begin_startup_log();startup_stage('Creating desktop application with Qt ' + qVersion())
    app=QApplication.instance() or QApplication(sys.argv[:1]);app.setApplicationName('PRDE1');app.setOrganizationName('ShaelRiley')
    app.setApplicationDisplayName('Raw Daw');app.setWindowIcon(QIcon(str(ROOT/'prde1/data/raw-daw.svg')))
    if options.safe_workspace:app.setStyle('Fusion')
    startup_stage('Display platform: '+app.platformName()+'; widget style: '+app.style().objectName())
    screen=app.primaryScreen()
    if screen:
        geometry=screen.availableGeometry()
        startup_stage(f'Available screen: {geometry.width()}x{geometry.height()}; device scale: {screen.devicePixelRatio():g}')
    window=MainWindow(options.project,options.pack,safe_workspace=options.safe_workspace)
    startup_stage('Showing desktop window')
    window.show()
    startup_stage('Desktop window shown; entering event loop')
    return app.exec()


if __name__=='__main__':raise SystemExit(main())

