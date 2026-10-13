"""Cakewalk-style default step editor: pitch/kit rows and musical expression."""
from __future__ import annotations
import copy
import math
from fractions import Fraction
from pathlib import Path

from PySide6.QtCore import Qt, Signal, QEvent
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QToolButton, QMenu, QComboBox, QCheckBox, QSpinBox, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView, QFileDialog, QInputDialog, QSlider)

from .contracts import ContractError, SLOTS
from .gui_widgets import FlowLayout, COLORS, SLOT_NAMES, spin
from .music import REGISTERS, beat, at, chord_identity
from .sequencer import settings, event_row, note_name


class StepGrid(QTableWidget):
    activated = Signal(int, int)
    gesture = Signal(object, str)
    velocity = Signal(int, int, float)
    flam = Signal(int, int)
    command = Signal(str)
    typed_note = Signal(int)

    def __init__(self):
        super().__init__(); self.drag = None; self.play_column = -1; self.step_entry = False
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setAccessibleName('Step sequencer. Pitch or instrument rows, time columns. Arrows navigate; Space toggles; Delete erases; Control-drag ties; Shift-drag changes note volume.')
        self.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
        self.horizontalHeader().setDefaultSectionSize(44); self.verticalHeader().setDefaultSectionSize(30)
        self.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)

    def event(self, event):
        if event.type() == QEvent.Type.ShortcutOverride and event.key() in (Qt.Key.Key_Space, Qt.Key.Key_Return, Qt.Key.Key_Delete):
            event.accept(); return True
        return super().event(event)

    def mousePressEvent(self, event):
        index = self.indexAt(event.position().toPoint())
        if not index.isValid(): return super().mousePressEvent(event)
        row, col = index.row(), index.column(); self.setCurrentCell(row, col)
        cell = self.item(row, col); data = cell.data(Qt.ItemDataRole.UserRole) or {}
        mods = event.modifiers(); right = event.button() == Qt.MouseButton.RightButton
        mode = 'split' if right and mods & Qt.KeyboardModifier.ControlModifier else 'tie' if mods & Qt.KeyboardModifier.ControlModifier else 'velocity' if mods & Qt.KeyboardModifier.ShiftModifier else 'erase' if right else 'paint'
        self.drag = dict(first=(row,col), cells=[(row,col)], mode=mode, y=event.position().y(), value=data.get('velocity', .8), free=bool(mods & Qt.KeyboardModifier.AltModifier))
        event.accept()

    def mouseMoveEvent(self, event):
        if not self.drag:return super().mouseMoveEvent(event)
        index = self.indexAt(event.position().toPoint())
        if index.isValid():
            row = index.row() if self.drag['free'] else self.drag['first'][0]
            cell = row, index.column()
            previous=self.drag['cells'][-1]
            if row==previous[0] and cell[1]!=previous[1]:
                direction=1 if cell[1]>previous[1] else -1
                for col in range(previous[1]+direction,cell[1]+direction,direction):
                    if (row,col) not in self.drag['cells']:self.drag['cells'].append((row,col))
            elif cell not in self.drag['cells']:self.drag['cells'].append(cell)
            self.setCurrentCell(*cell)
        event.accept()

    def mouseReleaseEvent(self, event):
        if not self.drag:return super().mouseReleaseEvent(event)
        drag = self.drag; self.drag = None
        if drag['mode'] == 'velocity':
            self.velocity.emit(*drag['first'], max(0,min(1,drag['value'] + (drag['y'] - event.position().y()) / 100)))
        else:self.gesture.emit(drag['cells'],drag['mode'])
        event.accept()

    def mouseDoubleClickEvent(self, event):
        self.drag = None; index = self.indexAt(event.position().toPoint())
        if index.isValid():self.flam.emit(index.row(),index.column())
        event.accept()

    def keyPressEvent(self, event):
        key = event.key(); modifiers = event.modifiers()
        if modifiers & Qt.KeyboardModifier.AltModifier and key in (Qt.Key.Key_Left, Qt.Key.Key_Right):
            self.command.emit('left' if key == Qt.Key.Key_Left else 'right');event.accept();return
        if modifiers & Qt.KeyboardModifier.AltModifier and key in (Qt.Key.Key_Up, Qt.Key.Key_Down):
            self.command.emit('column_up' if key == Qt.Key.Key_Up else 'column_down');event.accept();return
        if modifiers & Qt.KeyboardModifier.ControlModifier:
            actions={Qt.Key.Key_C:'copy',Qt.Key.Key_X:'cut',Qt.Key.Key_V:'paste',Qt.Key.Key_R:'step_entry'}
            if key in actions:self.command.emit(actions[key]);event.accept();return
        if key in (Qt.Key.Key_Space,Qt.Key.Key_Return,Qt.Key.Key_Enter) and self.currentRow() >= 0:
            self.activated.emit(self.currentRow(),self.currentColumn());event.accept();return
        if key in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            self.gesture.emit([(i.row(),i.column()) for i in self.selectedIndexes()], 'erase');event.accept();return
        if self.step_entry:
            keys='ZSXDCVGBHNJM'
            if event.text().upper() in keys and len(event.text()) == 1:
                self.typed_note.emit(keys.index(event.text().upper()));event.accept();return
            if key in (Qt.Key.Key_Period,Qt.Key.Key_Comma):
                self.setCurrentCell(max(0,self.currentRow()),(self.currentColumn() + (1 if key == Qt.Key.Key_Period else -1)) % max(1,self.columnCount()));event.accept();return
        super().keyPressEvent(event)

    def paintEvent(self,event):
        super().paintEvent(event)
        if 0 <= self.play_column < self.columnCount():
            painter=QPainter(self.viewport());painter.setPen(QPen(QColor('#fff0a7'),2))
            x=self.columnViewportPosition(self.play_column)
            painter.drawRect(x,0,self.columnWidth(self.play_column)-1,self.viewport().height()-1);painter.end()

    def resizeEvent(self,event):
        super().resizeEvent(event)
        if self.currentItem() is not None:self.scrollToItem(self.currentItem(),QAbstractItemView.ScrollHint.EnsureVisible)


class ExpressionLane(QWidget):
    edited=Signal(int,float)
    def __init__(self, grid):
        super().__init__();self.grid=grid;self.values=[];self.minimum=0;self.maximum=1;self.pending=None;self.setFixedHeight(62);self.setAccessibleName('Step expression bars; click or drag to edit')
        grid.horizontalScrollBar().valueChanged.connect(self.update)
    def paintEvent(self,event):
        painter=QPainter(self);painter.fillRect(self.rect(),QColor('#111820'))
        origin=self.grid.verticalHeader().width()+self.grid.frameWidth()
        for col,value in enumerate(self.values):
            x=origin+self.grid.columnViewportPosition(col);width=self.grid.columnWidth(col)
            painter.setPen(QColor('#314557'));painter.drawRect(x,2,width-1,self.height()-4)
            if value is not None:
                scale=(self.height()-8)/(self.maximum-self.minimum);baseline=self.height()-4+self.minimum*scale
                y=baseline-value*scale;painter.fillRect(x+4,int(min(baseline,y)),width-8,max(1,int(abs(baseline-y))),QColor('#76c9bb'))
        painter.end()
    def edit_at(self,event):
        origin=self.grid.verticalHeader().width()+self.grid.frameWidth()
        x=int(event.position().x())-origin;column=self.grid.horizontalHeader().logicalIndexAt(x)
        if 0<=column<len(self.values) and self.values[column] is not None:
            value=max(self.minimum,min(self.maximum,self.minimum+(self.height()-event.position().y())/self.height()*(self.maximum-self.minimum)))
            if self.pending is not None:
                self.pending[column]=value
                if column<len(self.values):self.values[column]=value
                self.update()
    def mousePressEvent(self,event):self.pending={};self.edit_at(event)
    def mouseMoveEvent(self,event):
        if event.buttons() & Qt.MouseButton.LeftButton:self.edit_at(event)
    def mouseReleaseEvent(self,event):
        self.edit_at(event);values=self.pending or {};self.pending=None
        self.parent().draw_expression(values)


class StepSequencer(QWidget):
    def __init__(self,change,audition,duplicate,detach,remove,parent=None):
        super().__init__(parent);self.change=change;self.audition=audition;self.editor=None;self.instance_id='';self.rows=[];self.config=None;self.clipboard=None;self.refreshing=False;self.column_focus=0
        layout=QVBoxLayout(self);layout.setContentsMargins(6,6,6,6)
        toolbar=FlowLayout();self.heading=QLabel('Select a pattern');toolbar.addWidget(self.heading)
        self.length=spin(.25,64,4,2,' beats');self.length.setAccessibleName('Pattern length in beats');self.length.editingFinished.connect(self.set_length);toolbar.addWidget(self.length)
        self.resolution=QComboBox()
        for n in range(1,17):self.resolution.addItem(str(n)+' steps/beat',n)
        self.resolution.setCurrentIndex(3);self.resolution.setAccessibleName('Steps per beat');self.resolution.currentIndexChanged.connect(self.set_resolution);toolbar.addWidget(self.resolution)
        self.entry_mode=QComboBox();self.entry_mode.addItem('Mono entry','mono');self.entry_mode.addItem('Poly entry','poly');self.entry_mode.currentIndexChanged.connect(lambda:self.config_change(entryMode=self.entry_mode.currentData()));toolbar.addWidget(self.entry_mode)
        self.pitch_mode=QComboBox();self.pitch_mode.addItem('Follow harmony','follow');self.pitch_mode.addItem('Lock pitches','exact');self.pitch_mode.currentIndexChanged.connect(lambda:self.config_change(pitchMode=self.pitch_mode.currentData()));toolbar.addWidget(self.pitch_mode)
        self.play_button=QPushButton('Play pattern');self.play_button.clicked.connect(self.play_pattern);toolbar.addWidget(self.play_button)
        self.loop=QCheckBox('Loop');self.loop.setChecked(True);toolbar.addWidget(self.loop)
        self.record=QCheckBox('Step entry');self.record.setToolTip('Enter notes with Space or the Z S X D C V G B H N J M keys. Period inserts a rest; comma goes back.');self.record.toggled.connect(lambda value:setattr(self.grid,'step_entry',value));toolbar.addWidget(self.record)
        self.pattern_menu=QToolButton();self.pattern_menu.setText('Pattern ▾');self.pattern_menu.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup);menu=QMenu(self.pattern_menu)
        for title,fn in [('Save pattern…',self.save_pattern),('Load pattern…',self.load_pattern),('Import note MIDI…',self.import_midi),('Export note MIDI…',self.export_midi),('Clear pattern',lambda:self.pattern_action('clear')),
                         ('Quantize to grid',lambda:self.pattern_action('quantize')),('Fit to quarters…',self.fit),('Duplicate',duplicate),('Make independent',detach),('Remove pattern',remove)]:
            menu.addAction(title,fn)
        self.pattern_menu.setMenu(menu);toolbar.addWidget(self.pattern_menu)
        self.row_menu=QToolButton();self.row_menu.setText('Row ▾');self.row_menu.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup);row_menu=QMenu(self.row_menu)
        for title,fn in [('Insert row…',self.insert_row),('Delete row',lambda:self.row_action('delete')),('Rename row…',self.rename_row),
                         ('Move row up',lambda:self.row_action('up')),('Move row down',lambda:self.row_action('down')),
                         ('Cut row',lambda:self.row_action('cut')),('Copy row',lambda:self.row_action('copy')),('Paste row',lambda:self.row_action('paste')),
                         ('Shift left',lambda:self.row_action('left')),('Shift right',lambda:self.row_action('right')),('Reverse row',lambda:self.row_action('reverse')),
                         ('Clear row',lambda:self.row_action('clear')),('Tie selected steps',lambda:self.tie(False)),('Split tied step',lambda:self.tie(True))]:row_menu.addAction(title,fn)
        fill=row_menu.addMenu('Fill every…')
        for n in range(1,17):fill.addAction(str(n)+' steps',lambda n=n:self.row_action('fill',every=n))
        self.row_menu.setMenu(row_menu);toolbar.addWidget(self.row_menu);layout.addLayout(toolbar)
        self.grid=StepGrid();self.grid.setObjectName('stepGrid');layout.addWidget(self.grid,1)
        self.grid.activated.connect(self.toggle);self.grid.gesture.connect(self.gesture);self.grid.velocity.connect(self.set_velocity);self.grid.flam.connect(self.toggle_flam);self.grid.command.connect(self.row_action);self.grid.typed_note.connect(self.type_note)
        self.grid.currentCellChanged.connect(self.focus_row);self.grid.verticalHeader().sectionClicked.connect(self.audition_row)
        self.grid.verticalHeader().setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu);self.grid.verticalHeader().customContextMenuRequested.connect(lambda point:row_menu.exec(self.grid.verticalHeader().mapToGlobal(point)))
        dynamics=FlowLayout();dynamics.addWidget(QLabel('Note volume'))
        self.note_volume_slider=QSlider(Qt.Orientation.Horizontal);self.note_volume_slider.setRange(0,100);self.note_volume_slider.setTracking(False)
        self.note_volume_slider.setMinimumWidth(120);self.note_volume_slider.setMaximumWidth(200);self.note_volume_slider.setAccessibleName('Focused note volume slider')
        self.note_volume_slider.valueChanged.connect(lambda value:self.set_note_volume(value/100));dynamics.addWidget(self.note_volume_slider)
        self.note_volume=spin(0,100,80,1,' %');self.note_volume.setKeyboardTracking(False);self.note_volume.setAccessibleName('Focused note volume percentage')
        self.note_volume.valueChanged.connect(lambda value:self.set_note_volume(value/100));dynamics.addWidget(self.note_volume)
        self.note_volume_context=QLabel('Select a note');self.note_volume_context.setTextFormat(Qt.TextFormat.PlainText);dynamics.addWidget(self.note_volume_context)
        self.note_volume_midi=QLabel();self.note_volume_midi.hide()
        for widget in (self.note_volume,self.note_volume_slider):widget.setToolTip('Volume of the focused note, saved as velocity. Row dynamics and mixer levels apply afterwards. A slider drag is one undoable edit.')
        layout.insertLayout(1,dynamics)
        self.help=QLabel();self.help.setWordWrap(True);self.help.setObjectName('muted');layout.addWidget(self.help)
        bottom=FlowLayout();self.row_label=QLabel('Row');self.row_label.setTextFormat(Qt.TextFormat.PlainText);bottom.addWidget(self.row_label)
        self.row_muted=QCheckBox('Mute');self.row_solo=QCheckBox('Solo')
        for name,w in [('muted',self.row_muted),('solo',self.row_solo)]:w.clicked.connect(lambda _,name=name,w=w:self.row_change(**{name:w.isChecked()}));dynamics.addWidget(w)
        self.details=QCheckBox('More controls');self.details.toggled.connect(lambda on:(self.advanced_panel.setVisible(on),self.row_panel.setVisible(on)));dynamics.addWidget(self.details)
        self.preview_click=QCheckBox('Audition on entry');bottom.addWidget(self.preview_click)
        self.default_velocity=spin(0,100,80,0,' %');self.default_velocity.setAccessibleName('Default new note volume');self.default_velocity.editingFinished.connect(lambda:self.config_change(defaultVelocity=self.default_velocity.value()/100));bottom.addWidget(QLabel('New note volume'));bottom.addWidget(self.default_velocity)
        self.parameter=QComboBox()
        for label,key in [('Volume / velocity','velocity'),('Duration','duration'),('Play probability','playPercent'),('Change probability','changePercent'),('Timing offset','offsetBeat')]:self.parameter.addItem(label,key)
        self.parameter.currentIndexChanged.connect(self.refresh_lane);bottom.addWidget(self.parameter)
        self.show_lane=QCheckBox('Dynamics bars');self.show_lane.toggled.connect(lambda on:self.lane.setVisible(on));dynamics.addWidget(self.show_lane)
        self.advanced_panel=QWidget();self.advanced_panel.setLayout(bottom);layout.addWidget(self.advanced_panel);self.advanced_panel.hide()
        self.row_panel=QWidget();controls=FlowLayout();self.row_controls={}
        for name,label,low,high,value in [('velocityScale','Velocity ×',0,2,1),('velocityOffset','Velocity ± %',-100,100,0),('gatePercent','Gate %',1,200,100),
                                        ('swingPercent','Swing %',1,99,50),('offsetPercent','Offset %',-50,50,0),('flamPercent','Flam %',-50,50,12)]:
            w=spin(low,high,value,2);w.setAccessibleName(label);w.setMaximumWidth(90);w.editingFinished.connect(lambda name=name,w=w:self.row_change(**{name:w.value()/100 if name=='velocityOffset' else w.value()}))
            controls.addWidget(QLabel(label));controls.addWidget(w);self.row_controls[name]=w
        self.row_panel.setLayout(controls);layout.addWidget(self.row_panel);self.row_panel.hide()
        self.lane=ExpressionLane(self.grid);self.lane.edited.connect(self.set_parameter);layout.addWidget(self.lane);self.show_lane.setChecked(True)
        self.refresh_volume()

    def active(self):return self.editor is not None and bool(self.instance_id)
    def current_row(self):
        index=self.grid.currentRow()
        return self.rows[index] if 0<=index<len(self.rows) else None
    def config_change(self,**values):
        if self.active() and not self.refreshing:self.change(lambda:self.editor.set_sequencer(self.instance_id,**values))
    def row_change(self,**values):
        row=self.current_row()
        if row and not self.refreshing:self.change(lambda:self.editor.set_row(self.instance_id,row['id'],**values))
    def set_resolution(self,*_):
        if self.active() and not self.refreshing:
            value=self.resolution.currentData()
            self.config_change(stepBeat=str(Fraction(1,value)) if type(value) is int else value)
    def set_length(self):
        if self.active() and not self.refreshing:self.change(lambda:self.editor.pattern_action(self.instance_id,'length',value=Fraction(str(self.length.value()))))
    def pattern_action(self,action):
        if self.active():self.change(lambda:self.editor.pattern_action(self.instance_id,action))
    def fit(self):
        if not self.active():return
        value,ok=QInputDialog.getDouble(self,'Fit pattern','Quarter-note beats',float(beat(self.editor.pattern(self.instance_id)['length'])),.25,64,2)
        if ok:self.change(lambda:self.editor.pattern_action(self.instance_id,'fit',value=Fraction(str(value))))
    def selected_matches(self,row,col):
        return self.grid_matches.get((self.rows[row]['id'],col*beat(self.config['stepBeat'])),[])
    def focused_event(self):
        row=self.current_row();col=self.grid.currentColumn()
        if not self.active() or row is None or col<0:return None
        matches=self.selected_matches(self.grid.currentRow(),col)
        enabled=next((e for e in matches if e['enabled']),None)
        if enabled is not None:return enabled
        position=col*beat(self.config['stepBeat']);pattern=self.editor.pattern(self.instance_id);instance=self.editor.instance(self.instance_id)
        held=[e for e in pattern['events'] if e['enabled'] and beat(e['beat'])<position<beat(e['beat'])+beat(e['duration']) and event_row(self.editor.project,self.editor.pack,instance,pattern,e)==row['id']]
        return max(held,key=lambda e:beat(e['beat']),default=matches[0] if matches else None)
    def refresh_volume(self):
        event=self.focused_event();was_refreshing=self.refreshing;self.refreshing=True
        self.note_volume.setEnabled(event is not None);self.note_volume_slider.setEnabled(event is not None)
        value=event['expression']['velocity'] if event else 0
        self.note_volume.setValue(value*100);self.note_volume_slider.setValue(round(value*100))
        self.note_volume.setToolTip('Volume of the focused note, saved as velocity '+str(round(value*127))+'/127. Row dynamics and mixer levels apply afterwards.')
        row=self.current_row()
        self.note_volume_context.setText((row['label'] or (note_name(row['note']) if row['note'] is not None else SLOT_NAMES.get(row['sound'],'Whole chord')))+' · beat '+event['beat'] if event else 'Select a note')
        self.note_volume_midi.setText('Velocity '+str(round(value*127))+'/127' if event else '')
        self.refreshing=was_refreshing
    def set_note_volume(self,value):
        if self.refreshing:return
        event=self.focused_event()
        if event is None:return
        event_id=event['id']
        def edit(pattern,_):next(e for e in pattern['events'] if e['id']==event_id)['expression']['velocity']=value
        self.change(lambda:self.editor._step_edit(self.instance_id,'Set note volume',edit))
    def toggle(self,row,col):
        if not self.active():return
        matches=self.selected_matches(row,col);enabled=not any(e['enabled'] for e in matches)
        self.gesture([(row,col)],'paint' if enabled else 'erase')
        if self.record.isChecked():self.grid.setCurrentCell(row,(col+1)%self.grid.columnCount())
    def gesture(self,cells,mode):
        if not self.active() or not cells:return
        step=beat(self.config['stepBeat']);converted=[(self.rows[row]['id'],col*step) for row,col in cells]
        if mode in ('tie','split'):
            row=cells[0][0];cols=[c for r,c in cells if r==row]
            self.change(lambda:self.editor.tie_steps(self.instance_id,self.rows[row]['id'],min(cols)*step,max(cols)*step,split=mode=='split'))
        else:
            self.change(lambda:self.editor.paint_steps(self.instance_id,converted,enabled=mode=='paint',exact=self.config['pitchMode']=='exact'))
            if mode=='paint' and self.preview_click.isChecked():self.audition_row(cells[-1][0])
        self.grid.setCurrentCell(*cells[-1])
    def set_velocity(self,row,col,value):
        matches=self.selected_matches(row,col)
        if matches:self.change(lambda:self.editor.edit_step_values(self.instance_id,{e['id'] for e in matches},velocity=value))
    def toggle_flam(self,row,col):
        if not self.active():return
        matches=self.selected_matches(row,col)
        if not matches:self.gesture([(row,col)],'paint');matches=self.selected_matches(row,col)
        if matches:self.change(lambda:self.editor.edit_step_values(self.instance_id,{e['id'] for e in matches},flam=not matches[0].get('flam',False)))
    def type_note(self,semitone):
        if not self.active():return
        row=self.current_row()
        if self.editor.pattern(self.instance_id)['role']=='drums':
            if semitone<len(self.rows):self.toggle(semitone,max(0,self.grid.currentColumn()))
        elif row and row['note'] is not None:
            note=row['note']//12*12+semitone
            index=next((i for i,r in enumerate(self.rows) if r['note']==note),None)
            if index is not None:self.toggle(index,max(0,self.grid.currentColumn()))
    def row_action(self,action,**values):
        if action=='step_entry':self.record.toggle();return
        if not self.active() or self.current_row() is None:return
        row=self.current_row();pattern=self.editor.pattern(self.instance_id);instance=self.editor.instance(self.instance_id)
        events=[copy.deepcopy(e) for e in pattern['events'] if event_row(self.editor.project,self.editor.pack,instance,pattern,e)==row['id']]
        if action in ('column_up','column_down'):
            self.change(lambda:self.editor.transpose_column(self.instance_id,max(0,self.grid.currentColumn())*beat(self.config['stepBeat']),1 if action=='column_up' else -1));return
        if action in ('copy','cut'):self.clipboard=(pattern['role'],events)
        if action=='copy':return
        if action=='paste':
            if self.clipboard is None:return
            if self.clipboard[0]!=pattern['role']:self.window().notice('Paste row steps on a matching instrument role');return
            values['payload']=self.clipboard[1]
        if action in ('left','right'):values['step']=-1 if action=='left' else 1;action='shift'
        if action=='fill':values['start']=max(0,self.grid.currentColumn())
        self.change(lambda:self.editor.row_action(self.instance_id,row['id'],action,**values))
    def tie(self,split):
        row=self.grid.currentRow();cols=[i.column() for i in self.grid.selectedIndexes() if i.row()==row]
        if row>=0 and cols:self.gesture([(row,min(cols)),(row,max(cols))],'split' if split else 'tie')
    def insert_row(self):
        if not self.active():return
        role=self.editor.pattern(self.instance_id)['role'];config=copy.deepcopy(self.config)
        from .sequencer import row_defaults
        if role in REGISTERS:
            existing={r['note'] for r in self.rows};choices=[n for n in range(REGISTERS[role][0],REGISTERS[role][1]+1) if n not in existing]
            labels=[note_name(n)+' · MIDI '+str(n) for n in choices]
        elif role=='drums':choices=[s for s in SLOTS if s not in {r['sound'] for r in self.rows}];labels=[SLOT_NAMES[s] for s in choices]
        else:return
        if not choices:return
        label,ok=QInputDialog.getItem(self,'Insert row','Pitch / kit instrument',labels,0,False)
        if ok:config['rows'].insert(max(0,self.grid.currentRow()),row_defaults(role,choices[labels.index(label)]));self.config_change(rows=config['rows'])
    def rename_row(self):
        row=self.current_row()
        if not row:return
        text,ok=QInputDialog.getText(self,'Rename row','Name',text=row['label'])
        if ok:self.row_change(label=text)
    def save_pattern(self):
        if not self.active():return
        name,_=QFileDialog.getSaveFileName(self,'Save step pattern','My_pattern.prdepattern','PRDE1 step pattern (*.prdepattern)')
        if name:self.change(lambda:self.editor.save_pattern(self.instance_id,Path(name)))
    def load_pattern(self):
        if not self.active():return
        name,_=QFileDialog.getOpenFileName(self,'Load step pattern','','PRDE1 step pattern (*.prdepattern)')
        if name:self.change(lambda:self.editor.load_pattern(self.instance_id,Path(name)))
    def audition_row(self,row):
        if self.active() and 0<=row<len(self.rows):self.audition(self.instance_id,self.rows[row],max(0,self.grid.currentColumn()),False)
    def play_pattern(self):
        if self.active():self.audition(self.instance_id,None,0,self.loop.isChecked())

    def import_midi(self):
        if not self.active():return
        name,_=QFileDialog.getOpenFileName(self,'Import note MIDI · keep current song tempo/harmony','','Standard MIDI (*.mid *.midi)')
        if not name:return
        path=Path(name);mapping={}
        if self.editor.pattern(self.instance_id)['role']=='drums':
            from .midi import inspect_midi
            try:
                if path.stat().st_size>4*1024*1024:raise ContractError('MIDI file exceeds four MiB')
                notes=inspect_midi(path.read_bytes())['notes']
                known={r['midiAddress'] for r in self.editor.pack.instruments['drums'].values() if r['status']=='available'}|{35,36,38,40,41,42,43,44,45,46,47,48,50}
                available=[slot for slot,r in self.editor.pack.instruments['drums'].items() if r['status']=='available']
                labels=[SLOT_NAMES[slot]+' · '+self.editor.pack.instruments['drums'][slot]['displayName'] for slot in available]
                for note in sorted({n['note'] for n in notes}-known):
                    label,ok=QInputDialog.getItem(self,'Map imported drum','MIDI note '+str(note)+' → kit instrument',labels,0,False)
                    if not ok:return
                    mapping[note]=available[labels.index(label)]
            except (ValueError,OSError) as error:self.window().notice(str(error));return
        def op():
            notices=self.editor.import_midi(self.instance_id,path,mapping)
            if notices:self.window().notice('Imported note timing and velocity. Song tempo/harmony and mixer controls remain as set.')
        self.change(op)

    def export_midi(self):
        if not self.active():return
        name,_=QFileDialog.getSaveFileName(self,'Export realized note MIDI','My_pattern.mid','Standard MIDI (*.mid)')
        if name:self.change(lambda:self.editor.export_midi(self.instance_id,Path(name)))
    def focus_row(self,*_):
        if self.refreshing:return
        row=self.current_row()
        self.refreshing=True
        if row:
            self.row_label.setText(row['label'] or (note_name(row['note']) if row['note'] is not None else SLOT_NAMES.get(row['sound'],'Whole chord')))
            self.row_muted.setChecked(row['muted']);self.row_solo.setChecked(row['solo'])
            for name,w in self.row_controls.items():w.setValue(row[name]*100 if name=='velocityOffset' else row[name])
        self.refreshing=False;self.refresh_volume();self.refresh_lane()
    def refresh_lane(self,*_):
        if not self.active() or self.current_row() is None:return
        parameter=self.parameter.currentData();self.lane.minimum=-.5 if parameter=='offsetBeat' else 0;self.lane.maximum=.5 if parameter=='offsetBeat' else 100 if parameter.endswith('Percent') else 2 if parameter=='duration' else 1
        self.lane.setAccessibleName('Per-note volume bars for the focused row' if parameter=='velocity' else 'Step '+self.parameter.currentText()+' bars for the focused row')
        self.lane.setToolTip('Drag each bar to set that note\'s '+('volume (velocity)' if parameter=='velocity' else self.parameter.currentText().lower())+'. Empty steps stay empty; each drag is one undoable edit.')
        values=[]
        for col in range(self.grid.columnCount()):
            matches=self.selected_matches(self.grid.currentRow(),col)
            e=next((e for e in matches if e['enabled']),None)
            value=float(Fraction(e.get('offsetBeat','0'))) if e and parameter=='offsetBeat' else float(beat(e['duration'])/beat(self.config['stepBeat'])) if e and parameter=='duration' else e['expression'][parameter] if e else None
            values.append(value)
        self.lane.values=values;self.lane.update()
    def set_parameter(self,col,value):
        row=self.grid.currentRow()
        if row<0:return
        matches=self.selected_matches(row,col);key=self.parameter.currentData()
        if not matches:return
        if key=='duration':value=str(max(Fraction(1,48000),(Fraction(str(value))*beat(self.config['stepBeat'])).limit_denominator(9600)))
        elif key=='offsetBeat':value=str(Fraction(str(value)).limit_denominator(9600))
        self.change(lambda:self.editor.edit_step_values(self.instance_id,{e['id'] for e in matches},**{key:value}))
    def draw_expression(self,values):
        row=self.grid.currentRow()
        if row<0:return
        key=self.parameter.currentData();updates={}
        for col,value in values.items():
            matches=self.selected_matches(row,col)
            if key=='duration':value=str(max(Fraction(1,48000),(Fraction(str(value))*beat(self.config['stepBeat'])).limit_denominator(9600)))
            elif key=='offsetBeat':value=str(Fraction(str(value)).limit_denominator(9600))
            for e in matches:updates[e['id']]=value
        def edit(pattern,_):
            for event in pattern['events']:
                if event['id'] in updates:
                    if key in ('duration','offsetBeat'):event[key]=updates[event['id']]
                    else:event['expression'][key]=updates[event['id']]
        if updates:self.change(lambda:self.editor._step_edit(self.instance_id,'Draw step expression',edit))
    def refresh(self,editor,instance_id):
        previous=(self.grid.currentRow(),self.grid.currentColumn());old_id=self.instance_id
        self.editor=editor;self.instance_id=instance_id;self.refreshing=True
        self.grid.clear()
        if not instance_id:
            self.grid.setRowCount(0);self.grid.setColumnCount(0);self.heading.setText('Select a pattern on the timeline');self.lane.values=[];self.lane.update();self.refreshing=False;self.refresh_volume();return
        pattern=editor.pattern(instance_id);instance=editor.instance(instance_id);role=pattern['role']
        self.config=settings(pattern,editor.pack);self.rows=self.config['rows'];step=beat(self.config['stepBeat']);columns=math.ceil(beat(pattern['length'])/step)
        if role in REGISTERS:
            from .sequencer import pitch,row_defaults
            used={pitch(editor.project,editor.pack,instance,e) for e in pattern['events']}
            present={r['note'] for r in self.rows}
            for note in sorted(used-present,reverse=True):
                if REGISTERS[role][0]<=note<=REGISTERS[role][1]:self.rows.append(row_defaults(role,note))
        self.length.setMaximum(max(64,float(beat(pattern['length']))));self.length.setValue(float(beat(pattern['length'])))
        resolution=1/step;index=self.resolution.findData(int(resolution)) if resolution.denominator==1 else -1
        if index<0:
            index=self.resolution.findData(str(step))
            if index<0:self.resolution.addItem('Custom · '+str(step)+' beat/step',str(step));index=self.resolution.count()-1
        self.resolution.setCurrentIndex(index)
        self.entry_mode.setCurrentIndex(self.entry_mode.findData(self.config['entryMode']));self.pitch_mode.setCurrentIndex(self.pitch_mode.findData(self.config['pitchMode']));self.pitch_mode.setVisible(role in REGISTERS)
        self.entry_mode.setEnabled(role!='rhythm');self.pitch_mode.setToolTip('Pitch choice for new notes. Existing steps retain their individual locks.')
        self.default_velocity.setValue(self.config['defaultVelocity']*100)
        self.heading.setText(role.title()+' steps'+(' · Linked Repeat' if instance['linked'] else ''))
        self.grid.setRowCount(len(self.rows));self.grid.setColumnCount(columns)
        self.grid.setHorizontalHeaderLabels([str(int(col*step)+1)+'.'+str(col%max(1,round(1/step))+1) for col in range(columns)])
        def row_label(row):
            if row['label']:return row['label']
            if row['note'] is not None:return note_name(row['note'])+' · '+str(row['note'])
            if role!='drums':return 'Whole chord'
            record=editor.pack.instruments['drums'][row['sound']];label=SLOT_NAMES[row['sound']]
            if record['status']!='available':return label+' · unassigned'
            sample=editor.pack.samples[record['sampleId']]
            if sample['id'].startswith('hybrid_'):return label+' · modeled'
            return label+' · '+record['displayName'] if row['sound'].startswith('extra') else label
        labels=[row_label(row) for row in self.rows]
        self.grid.setVerticalHeaderLabels(labels)
        matches={};row_events={};events=sorted(pattern['events'],key=lambda e:(beat(e['beat']),e['id']))
        for event in events:
            identity=event_row(editor.project,editor.pack,instance,pattern,event)
            matches.setdefault((identity,beat(event['beat'])),[]).append(event)
            row_events.setdefault(identity,[]).append(event)
        self.grid_matches=matches
        first_active=None
        for row,r in enumerate(self.rows):
            record=editor.pack.instruments['drums'][r['sound']] if role=='drums' else None
            for col in range(columns):
                position=col*step;found=matches.get((r['id'],position),[]);enabled=next((e for e in found if e['enabled']),None)
                continuing=next((e for e in row_events.get(r['id'],[]) if e['enabled'] and beat(e['beat'])<position<beat(e['beat'])+beat(e['duration'])),None)
                allowed=not record or record['status']=='available'
                if role in REGISTERS:
                    absolute=beat(instance['beat'])+position;tone=at(editor.project['tonalityMap'],absolute)
                    _,pitches,_=chord_identity(tone['tonic'],tone['mode'],at(editor.project['harmony'],absolute)['chord']);allowed=r['note']%12 in pitches
                text=('F ' if enabled and enabled.get('flam') else '')+str(round(enabled['expression']['velocity']*100)) if enabled else '—' if continuing else 'off' if found else '·' if allowed else '×'
                item=QTableWidgetItem(text);item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                item.setBackground(QColor(COLORS[role]).darker(130 if enabled else 230 if continuing else 380) if allowed else QColor('#222b36'))
                item.setForeground(QColor('#f4f7fb' if enabled else '#a1b4c6' if allowed else '#536779'))
                if enabled and first_active is None:first_active=(row,col)
                if r['muted']:item.setForeground(QColor('#738293'))
                data=dict(enabled=bool(enabled),events=[e['id'] for e in found],allowed=allowed,velocity=enabled['expression']['velocity'] if enabled else .8)
                item.setData(Qt.ItemDataRole.UserRole,data)
                description=labels[row]+', beat '+str(position)+', '+('enabled' if enabled else 'sustain' if continuing else 'empty')
                if not allowed:description+='; outside governing chord' if role in REGISTERS else '; unassigned kit slot'
                if enabled:description+=f", note volume {round(enabled['expression']['velocity']*100)}% (velocity {round(enabled['expression']['velocity']*127)}/127), play {enabled['expression']['playPercent']}%, gate {enabled['duration']} beats"
                item.setData(Qt.ItemDataRole.AccessibleTextRole,description);item.setToolTip(description);self.grid.setItem(row,col,item)
        offgrid=sum(bool(beat(e['beat'])/step%1) for e in events)
        self.help.setText(f'Drag the bars to shape note volume; Shift-drag a step adjusts it. {offgrid} off-grid notes retained.')
        self.help.setToolTip('Left-click/drag draws; right-click erases; Ctrl-drag ties; Shift-drag adjusts note volume; double-click adds a flam. More controls exposes new-note defaults, other expression and row timing.')
        if old_id==instance_id and 0<=previous[0]<len(self.rows) and 0<=previous[1]<columns:self.grid.setCurrentCell(*previous)
        else:
            focus=first_active or (len(self.rows)//2,0);self.grid.setCurrentCell(*focus);self.grid.scrollToItem(self.grid.item(*focus),QAbstractItemView.ScrollHint.PositionAtCenter)
        self.refreshing=False;self.focus_row()

    def playhead(self,position):
        column=math.floor(position/beat(self.config['stepBeat'])) if self.active() and self.config and position is not None else -1
        if column!=self.grid.play_column:self.grid.play_column=column;self.grid.viewport().update()
