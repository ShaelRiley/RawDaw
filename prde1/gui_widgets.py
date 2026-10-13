"""Native desktop views; musical permission remains in the shared core."""
from __future__ import annotations

import copy
from fractions import Fraction

from PySide6.QtCore import Qt, Signal, QRectF, QRect, QSize
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (QWidget, QTableWidget, QDialog, QVBoxLayout, QFormLayout,
    QLabel, QComboBox, QLineEdit, QDoubleSpinBox, QCheckBox, QDialogButtonBox, QSpinBox, QLayout)

from .contracts import SLOTS
from .editor import chord_label, measures
from .governor import context
from .music import at, beat, chord_identity, NAMES, QUALITIES, roman

COLORS={'lead':'#b795ef','rhythm':'#e1b56a','bass':'#70b9ec','drums':'#75c7ac'}
ROLES=('lead','rhythm','bass','drums')
SLOT_NAMES={'kick':'Kick','snare':'Snare','hatClosed':'Closed hat','hatOpen':'Open hat',
            'tom1':'Low tom','tom2':'High tom','extra1':'Extra 1','extra2':'Extra 2'}


class FlowLayout(QLayout):
    """Controls wrap as text scales instead of forcing a window wider than its screen."""
    def __init__(self):
        super().__init__();self.entries=[];self.setContentsMargins(0,0,0,0);self.setSpacing(6)
    def addItem(self,value):self.entries.append(value)
    def count(self):return len(self.entries)
    def itemAt(self,index):return self.entries[index] if 0<=index<len(self.entries) else None
    def takeAt(self,index):return self.entries.pop(index) if 0<=index<len(self.entries) else None
    def addStretch(self,*_):pass
    def expandingDirections(self):return Qt.Orientation(0)
    def hasHeightForWidth(self):return True
    def heightForWidth(self,width):return self.arrange(QRect(0,0,width,0),False)
    def minimumSize(self):
        size=QSize(0,0)
        for value in self.entries:size=size.expandedTo(value.minimumSize())
        if self.geometry().width()>0:size.setHeight(self.heightForWidth(self.geometry().width()))
        return size
    def sizeHint(self):return self.minimumSize()
    def setGeometry(self,rect):
        before=self.minimumSize().height();super().setGeometry(rect);height=self.arrange(rect,True)
        if height!=before:self.invalidate()
    def arrange(self,rect,place):
        x=rect.x();y=rect.y();line_height=0
        for value in self.entries:
            hint=value.sizeHint();width=min(hint.width(),rect.width())
            if x>rect.x() and x+width>rect.right()+1:x=rect.x();y+=line_height+self.spacing();line_height=0
            if place:value.setGeometry(QRect(x,y,width,hint.height()))
            x+=width+self.spacing();line_height=max(line_height,hint.height())
        return y-rect.y()+line_height


def spin(low,high,value=0,decimals=1,suffix=''):
    widget=QDoubleSpinBox();widget.setRange(low,high);widget.setDecimals(decimals)
    widget.setValue(value);widget.setSuffix(suffix);widget.setKeyboardTracking(False)
    return widget


class StepTable(QTableWidget):
    activated=Signal(int,int)
    def keyPressEvent(self,event):
        if event.key() in (Qt.Key.Key_Space,Qt.Key.Key_Return,Qt.Key.Key_Enter) and self.currentRow()>=0:
            self.activated.emit(self.currentRow(),self.currentColumn());event.accept()
        else:super().keyPressEvent(event)


class Timeline(QWidget):
    selected=Signal(str,object,str)  # role, exact edit position, occurrence ID
    chord_requested=Signal(object)
    def __init__(self,parent=None):
        super().__init__(parent);self.editor=None;self.cursor=Fraction(0);self.play_beat=None;self.selected_id=''
        self.pixels_per_beat=44;self.header=108;self.row_height=50;self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAccessibleName('Song timeline. Arrow keys move the edit cursor; Enter edits a chord. Use the event list to edit steps.')
        self.setMinimumHeight(334);self.setObjectName('songTimeline')

    def refresh(self,editor,selection,cursor):
        self.editor=editor;self.selected_id=selection;self.cursor=cursor
        self.pixels_per_beat=44*editor.project['editorContext']['zoom']
        self.setMinimumWidth(max(640,self.header+round(float(beat(editor.project['length']))*self.pixels_per_beat)+20))
        self.update()

    def x(self,position):return self.header+float(position)*self.pixels_per_beat

    def position(self,x):
        raw=Fraction(max(0,(x-self.header)/self.pixels_per_beat)).limit_denominator(1000000)
        bars=measures(self.editor.project)
        for start,length,meter in bars:
            if start<=raw<start+length:
                step=Fraction(4*meter['numerator'],meter['denominator'])/meter['governorSegments']
                return start+int((raw-start)/step)*step
        return bars[-1][0]

    def paintEvent(self,event):
        p=QPainter(self);p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(),QColor('#151b23'))
        if not self.editor:return
        project=self.editor.project;end=beat(project['length'])
        for row,name in enumerate(('GOVERNOR','LEAD','RHYTHM','BASS','DRUM KIT','VOCAL 1')):
            top=30+row*self.row_height
            p.fillRect(QRectF(0,top,self.width(),self.row_height),QColor('#1d2631' if row%2==0 else '#18212b'))
            p.setPen(QColor('#c5d2df'));p.drawText(QRectF(8,top,self.header-12,self.row_height),Qt.AlignmentFlag.AlignVCenter,name)
        for index,(start,length,meter) in enumerate(measures(project)):
            x=self.x(start);p.setPen(QPen(QColor('#3c4a5a'),1));p.drawLine(round(x),26,round(x),330)
            p.setPen(QColor('#c9d5e2'));p.drawText(QRectF(x+7,0,140,26),Qt.AlignmentFlag.AlignVCenter,f'{index+1}   {meter["numerator"]}/{meter["denominator"]}')
            step=Fraction(4*meter['numerator'],meter['denominator'])/meter['governorSegments']
            for n in range(1,meter['governorSegments']):
                cell=self.x(start+n*step)
                p.setPen(QPen(QColor('#293645'),1,Qt.PenStyle.DotLine));p.drawLine(round(cell),30,round(cell),330)
        for index,entry in enumerate(project['harmony']):
            start=beat(entry['beat']);stop=beat(project['harmony'][index+1]['beat']) if index+1<len(project['harmony']) else end
            x=self.x(start);width=self.x(stop)-x
            _,_,_,legal=context(project,start)
            p.setPen(QColor('#73d4b1' if legal else '#f3ab76'));p.setBrush(QColor('#24473f' if legal else '#533d2e'))
            p.drawRoundedRect(QRectF(x+2,34,max(2,width-4),41),5,5)
            p.setPen(QColor('#edf7f3'));p.drawText(QRectF(x+10,35,max(0,width-15),38),Qt.AlignmentFlag.AlignVCenter,chord_label(project,start))
        patterns={v['id']:v for v in project['patterns']}
        for instance in project['instances']:
            pattern=patterns[instance['patternId']];row=ROLES.index(pattern['role'])+1
            start=beat(instance['beat']);x=self.x(start);width=float(beat(pattern['length']))*self.pixels_per_beat
            top=30+row*self.row_height;selected=instance['id']==self.selected_id
            color=COLORS[pattern['role']]
            p.setBrush(QColor(color).darker(290));p.setPen(QPen(QColor('#f4f8ff' if selected else color),2 if selected else 1))
            p.drawRoundedRect(QRectF(x+3,top+5,max(3,width-6),40),5,5)
            p.setPen(QColor('#e4edf6'))
            tag='Linked' if instance['linked'] else 'Independent'
            p.drawText(QRectF(x+10,top+7,max(0,width-18),19),Qt.AlignmentFlag.AlignVCenter,f'{pattern["role"].title()} · {tag}')
            for e in pattern['events']:
                if not e['enabled']:continue
                ex=self.x(start+beat(e['beat']));ew=max(2,min(18,float(beat(e['duration']))*self.pixels_per_beat))
                p.fillRect(QRectF(ex+4,top+31,ew,6),QColor(color))
        p.setPen(QColor('#97a7b9'));p.drawText(QRectF(self.header+10,286,self.width()-self.header-20,38),Qt.AlignmentFlag.AlignVCenter,'Recording and vocal comping are in the next development stage.')
        p.setPen(QPen(QColor('#71b9ff'),2));p.drawLine(round(self.x(self.cursor)),26,round(self.x(self.cursor)),332)
        if self.play_beat is not None:
            p.setPen(QPen(QColor('#81e6b7'),2));p.drawLine(round(self.x(self.play_beat)),26,round(self.x(self.play_beat)),332)

    def mousePressEvent(self,event):
        if not self.editor or event.position().x()<self.header:return
        self.setFocus();position=self.position(event.position().x());row=int((event.position().y()-30)//self.row_height)
        role=ROLES[row-1] if 1<=row<=4 else ''
        found=''
        if role:
            patterns={p['id']:p for p in self.editor.project['patterns']}
            for instance in self.editor.project['instances']:
                pattern=patterns[instance['patternId']];start=beat(instance['beat'])
                if pattern['role']==role and start<=position<start+beat(pattern['length']):found=instance['id']
        self.selected.emit(role,position,found)

    def mouseDoubleClickEvent(self,event):
        if self.editor and 30<=event.position().y()<80:self.chord_requested.emit(self.position(event.position().x()))

    def keyPressEvent(self,event):
        if not self.editor:return
        meter=at(self.editor.project['meterMap'],self.cursor)
        step=Fraction(4*meter['numerator'],meter['denominator'])/meter['governorSegments']
        if event.key() in (Qt.Key.Key_Left,Qt.Key.Key_Right):
            delta=-step if event.key()==Qt.Key.Key_Left else step
            self.selected.emit('',max(Fraction(0),min(beat(self.editor.project['length'])-step,self.cursor+delta)),self.selected_id)
        elif event.key() in (Qt.Key.Key_Return,Qt.Key.Key_Enter):self.chord_requested.emit(self.cursor)
        else:super().keyPressEvent(event)


class ChordDialog(QDialog):
    def __init__(self,editor,position,parent=None):
        super().__init__(parent);self.editor=editor;self.position=position;self.setWindowTitle('Edit governing chord')
        self.setMinimumWidth(420);layout=QVBoxLayout(self);form=QFormLayout();layout.addLayout(form)
        current=at(editor.project['harmony'],position)['chord']
        self.degree=QComboBox();self.degree.addItems(['1 · I','2 · II','3 · III','4 · IV','5 · V','6 · VI','7 · VII']);self.degree.setCurrentIndex(current['degree']-1)
        self.quality=QComboBox()
        for name in QUALITIES:self.quality.addItem(name,name)
        self.quality.setCurrentIndex(self.quality.findData(current['quality']))
        self.alteration=QComboBox()
        for name,n in [('Unaltered',0),('Flatten root',-1),('Sharpen root',1)]:self.alteration.addItem(name,n)
        self.alteration.setCurrentIndex(self.alteration.findData(current['alteration']))
        self.inversion=QComboBox();self.inversion.addItems(['Root position','1st inversion','2nd inversion','3rd inversion']);self.inversion.setCurrentIndex(current['inversion'])
        form.addRow('Degree',self.degree);form.addRow('Quality',self.quality);form.addRow('Root alteration',self.alteration);form.addRow('Inversion',self.inversion)
        self.explanation=QLabel();self.explanation.setWordWrap(True);layout.addWidget(self.explanation)
        layout.addWidget(QLabel('Every chord is playable. Native sounds are preferred; unrecorded chords are reconstructed.'))
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel);buttons.accepted.connect(self.accept);buttons.rejected.connect(self.reject);layout.addWidget(buttons)
        self.buttons=buttons
        for box in (self.degree,self.quality,self.alteration,self.inversion):box.currentIndexChanged.connect(self.explain)
        self.explain()

    def value(self):return dict(degree=self.degree.currentIndex()+1,quality=self.quality.currentData(),alteration=self.alteration.currentData(),inversion=self.inversion.currentIndex())

    def explain(self):
        chord=self.value();tone=at(self.editor.project['tonalityMap'],self.position)
        root,pitches,legal=chord_identity(tone['tonic'],tone['mode'],chord)
        sample=self.editor.pack.mappings.get(('rhythm',root,chord['quality'],chord['inversion']))
        valid_inversion=chord['inversion']<len(QUALITIES[chord['quality']])
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(valid_inversion)
        status='Native whole chord' if sample else 'Playable · reconstructed whole chord'
        if not legal:status+=' · borrowed chord outside the selected mode'
        if not valid_inversion:status='This chord has no such inversion'
        self.explanation.setText(chord_label(self.editor.project,self.position,chord)+'\n'+status)


class EventDialog(QDialog):
    def __init__(self,editor,instance_id,event,parent=None):
        super().__init__(parent);self.editor=editor;self.instance_id=instance_id;self.event=copy.deepcopy(event)
        pattern=editor.pattern(instance_id);self.role=pattern['role'];self.setWindowTitle('Edit '+self.role+' step')
        self.setMinimumWidth(430);layout=QVBoxLayout(self);form=QFormLayout();layout.addLayout(form)
        self.position=QLineEdit(event['beat']);self.duration=QLineEdit(event['duration']);self.enabled=QCheckBox('Enabled');self.enabled.setChecked(event['enabled'])
        form.addRow('Position · quarter-note beats',self.position);form.addRow('Gate · beats (fractions allowed)',self.duration);form.addRow('',self.enabled)
        choice=event['choice'];expression=event['expression']
        self.tone=QComboBox();self.tone.addItems(['Root','3rd / second chord tone','5th / third chord tone','7th / fourth chord tone','Chord tone 5','Chord tone 6','Chord tone 7']);self.tone.setCurrentIndex(choice['tone'])
        self.register=QSpinBox();self.register.setRange(0,127);self.register.setValue(choice['registerMidi'])
        self.exact=QComboBox();self.exact.addItem('Follow chord tone',None)
        absolute=beat(editor.instance(instance_id)['beat'])+beat(event['beat'])
        if self.role in ('lead','bass'):
            notes=editor.covered_notes(self.role,absolute)
            if choice['exactMidi'] is not None and choice['exactMidi'] not in notes:notes.append(choice['exactMidi'])
            for note in sorted(notes):self.exact.addItem(f'{NAMES[note%12]}{note//12-1} · MIDI {note}'+(' · conflicts here' if note not in editor.covered_notes(self.role,absolute) else ''),note)
            self.exact.setCurrentIndex(max(0,self.exact.findData(choice['exactMidi'])))
            form.addRow('Relative chord tone',self.tone);form.addRow('Preferred MIDI register',self.register);form.addRow('Exact prepared note',self.exact)
        self.sound=QComboBox()
        if self.role=='drums':
            for slot in SLOTS:
                value=editor.pack.instruments['drums'][slot]
                self.sound.addItem(SLOT_NAMES[slot]+' · '+value['displayName']+(' · unavailable' if value['status']!='available' else ''),value['soundIdentity'])
                if value['status']!='available':self.sound.model().item(self.sound.count()-1).setEnabled(False)
            index=self.sound.findData(choice['soundIdentity'])
            if index<0:self.sound.addItem('Unresolved: '+choice['soundIdentity'],choice['soundIdentity']);index=self.sound.count()-1
            self.sound.setCurrentIndex(index);form.addRow('Fixed drum sound',self.sound)
        self.velocity=spin(0,100,expression['velocity']*100,0,' %');self.velocity.setAccessibleName('Note volume (velocity)');self.velocity.setToolTip('Volume of this note, saved as velocity. Row dynamics and mixer levels apply afterwards.');self.attack=spin(0,100,expression['attackMs'],1,' ms')
        self.play=spin(0,100,expression['playPercent'],0,' %');self.change=spin(0,100,expression['changePercent'],0,' %')
        self.variation=QComboBox()
        for label,value in [('None','none'),('Nearby chord note','nearby_note'),('Double hit','double'),('Shorter gate','gate')]:self.variation.addItem(label,value)
        self.variation.setCurrentIndex(self.variation.findData(expression['variation']))
        self.locked=QCheckBox('Lock rhythm and role');self.locked.setChecked(expression['locked'])
        self.lock_exact=QCheckBox('Lock exact pitch');self.lock_exact.setChecked(expression['lockExactPitch']);self.lock_exact.setEnabled(self.role in ('lead','bass'))
        self.exact.currentIndexChanged.connect(lambda:self.lock_exact.setChecked(self.exact.currentData() is not None))
        for label,widget in [('Note volume (velocity)',self.velocity),('Attack',self.attack),('Play probability',self.play),('Change probability',self.change),('Variation',self.variation),('',self.locked),('',self.lock_exact)]:form.addRow(label,widget)
        limits=[(s['frames']-s['onsetFrame'])/48000 for s in editor.pack.samples.values() if s['role']==self.role]
        info='Whole chord trigger; sustains for its authored gate.' if self.role=='rhythm' else 'One chord tone at a time; sustains for its authored gate.' if self.role in ('lead','bass') else 'Drum addresses are fixed sound identities.'
        if self.role=='drums' and limits:info+=f' Natural hit durations: {min(limits):.2f}–{max(limits):.2f} seconds.'
        help_text=QLabel(info);help_text.setWordWrap(True);layout.addWidget(help_text)
        self.error=QLabel();self.error.setWordWrap(True);self.error.setObjectName('warning');layout.addWidget(self.error)
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel);buttons.accepted.connect(self.accept);buttons.rejected.connect(self.reject);layout.addWidget(buttons)

    def value(self):
        updated=copy.deepcopy(self.event);updated.update(beat=str(beat(self.position.text())),duration=str(beat(self.duration.text())),enabled=self.enabled.isChecked())
        updated['choice'].update(tone=self.tone.currentIndex(),registerMidi=self.register.value(),exactMidi=self.exact.currentData(),
                                 soundIdentity=self.sound.currentData() if self.role=='drums' else self.event['choice']['soundIdentity'])
        updated['expression'].update(velocity=self.velocity.value()/100,attackMs=self.attack.value(),playPercent=self.play.value(),
            changePercent=self.change.value(),variation=self.variation.currentData(),locked=self.locked.isChecked(),lockExactPitch=self.lock_exact.isChecked())
        if self.lock_exact.isChecked() and updated['choice']['exactMidi'] is None:raise ValueError('Choose an exact prepared note to lock')
        return updated

    def accept(self):
        try:
            self.editor.edit_event(self.instance_id,self.event['id'],self.value())
        except (ValueError,KeyError) as error:self.error.setText(str(error));return
        super().accept()

