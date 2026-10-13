"""Discoverable pulse controls and a searchable, draggable native MIDI browser."""
from __future__ import annotations

from PySide6.QtCore import Qt, QMimeData
from PySide6.QtGui import QDrag, QPainter, QColor
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QLineEdit, QCheckBox, QPushButton, QListWidget, QListWidgetItem, QDialog,
    QDialogButtonBox, QTableWidget, QSpinBox)

from . import clip_library
from .gui_widgets import FlowLayout
from .music import at
from .pulse import PRESETS, settings, set_pulse

MIME = 'application/x-raw-daw-clip'


class PulseStrip(QWidget):
    def __init__(self):
        super().__init__();self.levels=[];self.setMinimumSize(150,26)
        self.setAccessibleName('Repeating measure accent levels')
    def paintEvent(self,event):
        p=QPainter(self);p.fillRect(self.rect(),QColor('#15231f'))
        for i,v in enumerate(self.levels):
            width=self.width()/len(self.levels);p.fillRect(round(i*width)+1,round((1-v)*self.height()),max(1,round(width)-2),max(1,round(v*self.height())),QColor('#83d6b1'))


class PulseControls(QWidget):
    def __init__(self,window):
        super().__init__();self.window=window;self.busy=False
        layout=FlowLayout();self.setLayout(layout);layout.addWidget(QLabel('Rhythmic Pulse Governor'))
        self.mode=QComboBox()
        for label,data in [('Off','off'),('Guide','guide'),('On','on')]:self.mode.addItem(label,data)
        self.mode.setAccessibleName('Rhythmic pulse mode');self.mode.currentIndexChanged.connect(self.apply)
        layout.addWidget(self.mode);self.preset=QComboBox();self.preset.addItems(PRESETS)
        self.preset.setAccessibleName('Accent preset');self.preset.currentTextChanged.connect(self.choose_preset);layout.addWidget(self.preset)
        edit=QPushButton('Edit accents…');edit.clicked.connect(self.edit);layout.addWidget(edit)
        self.strip=PulseStrip();layout.addWidget(self.strip);self.explain=QLabel();self.explain.setObjectName('muted');layout.addWidget(self.explain)
    def refresh(self,editor):
        self.busy=True;config=settings(editor.project)
        self.mode.setCurrentIndex(self.mode.findData(config['mode']))
        if self.preset.findText(config['preset'])<0:self.preset.addItem(config['preset'])
        self.preset.setCurrentText(config['preset']);self.strip.levels=config['levels'];self.strip.update()
        self.explain.setText({'off':'Authored volumes','guide':'Defaults for new notes; edit freely','on':'Pulse controls each hit’s volume'}[config['mode']])
        self.setToolTip('Accents repeat within each measure. On preserves stored note volumes; Off restores them. Guide seeds new notes only.')
        self.busy=False
    def apply(self,*_):
        if not self.busy and self.window.editor:self.window.change(lambda:set_pulse(self.window.editor,mode=self.mode.currentData()))
    def choose_preset(self,name):
        if not self.busy and self.window.editor and name in PRESETS:
            self.window.change(lambda:set_pulse(self.window.editor,preset=name,levels=[v/100 for v in PRESETS[name]],phaseBeat='0'))
    def edit(self):
        if not self.window.editor:return
        config=settings(self.window.editor.project);dialog=QDialog(self.window);dialog.setWindowTitle('Edit repeating measure accents');dialog.resize(780,250)
        layout=QVBoxLayout(dialog);label=QLabel('Each column is an equal part of the current measure. Set hit volume from 0% (silent) to 100%.');label.setWordWrap(True);layout.addWidget(label)
        table=QTableWidget(1,len(config['levels']));table.setHorizontalHeaderLabels([str(i+1) for i in range(len(config['levels']))]);table.setVerticalHeaderLabels(['Volume']);table.setMinimumHeight(100);controls=[]
        for i,value in enumerate(config['levels']):
            spin=QSpinBox();spin.setRange(0,100);spin.setValue(round(value*100));spin.setSuffix('%');spin.setAccessibleName('Accent '+str(i+1));table.setCellWidget(0,i,spin);table.setColumnWidth(i,64);controls.append(spin)
        layout.addWidget(table);buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel);buttons.accepted.connect(dialog.accept);buttons.rejected.connect(dialog.reject);layout.addWidget(buttons)
        if dialog.exec():self.window.change(lambda:set_pulse(self.window.editor,preset='Custom',levels=[c.value()/100 for c in controls]))


class ClipList(QListWidget):
    def __init__(self):
        super().__init__();self.setDragEnabled(True);self.setAccessibleName('One-measure MIDI clips. Select then Preview or Place; drag to an empty measure on the matching track.')
    def startDrag(self,actions):
        if not self.currentItem():return
        mime=QMimeData();mime.setData(MIME,self.currentItem().data(Qt.ItemDataRole.UserRole).encode())
        drag=QDrag(self);drag.setMimeData(mime);drag.exec(Qt.DropAction.CopyAction)


class ClipBrowser(QWidget):
    def __init__(self,window):
        super().__init__();self.window=window;self.editor=None;self.position=0
        self.data=clip_library.catalog();self.favorites=set(window._settings.value('favoriteClips',[],type=list) if window._settings else [])
        layout=QVBoxLayout(self);layout.setContentsMargins(6,6,6,6);layout.setSpacing(6)
        filters=FlowLayout();self.search=QLineEdit();self.search.setMinimumWidth(160);self.search.setPlaceholderText('Search clips…');self.search.setAccessibleName('Search MIDI patterns');filters.addWidget(self.search)
        self.role=QComboBox()
        for label,value in [('All roles',''),('Bass','bass'),('Drums','drums'),('Lead','lead'),('Chords','rhythm')]:self.role.addItem(label,value)
        self.role.setAccessibleName('Clip instrument');filters.addWidget(self.role);self.style=QComboBox();self.style.addItem('All styles','')
        for style in sorted({c['style'] for c in self.data['clips']}):self.style.addItem(style,style)
        self.style.setAccessibleName('Clip style');self.style.setMinimumContentsLength(6);self.style.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon);filters.addWidget(self.style);layout.addLayout(filters)
        options=FlowLayout();self.match_meter=QCheckBox('Match meter');self.match_meter.setChecked(True);options.addWidget(self.match_meter);self.favorites_only=QCheckBox('Favorites');options.addWidget(self.favorites_only)
        self.count=QLabel();self.count.setObjectName('muted');options.addWidget(self.count);layout.addLayout(options)
        self.list=ClipList();self.list.setMinimumHeight(100);layout.addWidget(self.list,1)
        self.info=QLabel('Choose a clip to preview or place.');self.info.setWordWrap(True);self.info.setObjectName('muted');self.info.setMaximumHeight(64);layout.addWidget(self.info)
        actions=FlowLayout();preview=QPushButton('Preview');preview.clicked.connect(window.preview_clip);actions.addWidget(preview);place=QPushButton('Place');place.setObjectName('primary');place.clicked.connect(window.place_clip);actions.addWidget(place);self.favorite=QPushButton('☆');self.favorite.setAccessibleName('Toggle favorite clip');self.favorite.clicked.connect(self.toggle_favorite);actions.addWidget(self.favorite)
        export=QPushButton('Save source MIDI…');export.clicked.connect(window.export_library_midi);actions.addWidget(export);layout.addLayout(actions)
        self.list.currentItemChanged.connect(self.describe);self.list.itemDoubleClicked.connect(lambda _:window.place_clip())
        self.search.textChanged.connect(self.populate);self.role.currentIndexChanged.connect(self.populate);self.style.currentIndexChanged.connect(self.populate);self.match_meter.toggled.connect(self.populate);self.favorites_only.toggled.connect(self.populate)
    def selected(self):
        row=self.list.currentItem();return clip_library.find(row.data(Qt.ItemDataRole.UserRole)) if row else None
    def refresh(self,editor,position):
        meter=at(editor.project['meterMap'],position);key=(meter['numerator'],meter['denominator'])
        changed=self.editor is None or self.meter!=key;self.editor=editor;self.position=position;self.meter=key
        if changed:self.populate()
    def populate(self,*_):
        selected=self.list.currentItem().data(Qt.ItemDataRole.UserRole) if self.list.currentItem() else None
        self.list.clear();query=self.search.text().strip().casefold()
        for c in self.data['clips']:
            if self.role.currentData() and c['role']!=self.role.currentData():continue
            if self.style.currentData() and c['style']!=self.style.currentData():continue
            if self.match_meter.isChecked() and self.editor and c['meter']!=list(self.meter):continue
            if self.favorites_only.isChecked() and c['id'] not in self.favorites:continue
            if query and query not in ' '.join(str(c[k]) for k in ('name','role','style','section','origin','license')).casefold():continue
            label=('★ ' if c['id'] in self.favorites else '')+({'rhythm':'Chords'}.get(c['role'],c['role'].title()))+' · '+c['name']
            row=QListWidgetItem(label);row.setData(Qt.ItemDataRole.UserRole,c['id']);row.setToolTip(c['name']+'\n'+c['section']+' · '+str(c['hits'])+' hits\n'+c['origin']+' · '+c['license']);self.list.addItem(row)
            if c['id']==selected:self.list.setCurrentItem(row)
        self.count.setText(f"{self.list.count()} / {len(self.data['clips'])} one-bar clips")
        if not self.list.currentItem() and self.list.count():self.list.setCurrentRow(0)
    def describe(self,*_):
        c=self.selected()
        if not c:self.info.setText('No matching clips. Adjust the filters.');return
        self.info.setText(f"{c['meter'][0]}/{c['meter'][1]} · {c['hits']} hits · {c['section']}\n{c['origin']} · {c['license']}")
        self.info.setToolTip(c['attribution']+'\n'+c['sourceUrl']+'\n'+c['pattern']['provenance']['changes'])
        self.favorite.setText('★' if c['id'] in self.favorites else '☆')
    def toggle_favorite(self):
        c=self.selected()
        if not c:return
        if c['id'] in self.favorites:self.favorites.remove(c['id'])
        else:self.favorites.add(c['id'])
        if self.window._settings:self.window._settings.setValue('favoriteClips',sorted(self.favorites))
        self.populate()
