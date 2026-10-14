"""Native desktop views; musical permission remains in the shared core."""
from __future__ import annotations

import copy
from fractions import Fraction

from PySide6.QtCore import Qt, Signal, QRectF, QRect, QSize
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (QWidget, QTableWidget, QDialog, QVBoxLayout, QFormLayout,
    QLabel, QComboBox, QLineEdit, QDoubleSpinBox, QCheckBox, QDialogButtonBox, QSpinBox, QLayout, QMenu)

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
    clip_dropped=Signal(str,str,object)
    instance_moved=Signal(str,object)
    instance_resized=Signal(str,object)
    move_requested=Signal(str)
    length_requested=Signal(str)
    track_loop_requested=Signal(str)
    def __init__(self,parent=None):
        super().__init__(parent);self.editor=None;self.cursor=Fraction(0);self.play_beat=None;self.selected_id=''
        self.pixels_per_beat=44;self.header=108;self.row_height=50;self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAccessibleName('Song timeline. Drag a clip to move it; drag its right edge to repeat it. Shift and arrow keys move a selected clip; Control and arrow keys change its loop length. Control L toggles track looping. Enter edits a chord. The context menu offers Move and Loop length.')
        self.setMinimumHeight(334);self.setObjectName('songTimeline')
        self.setAcceptDrops(True);self.setMouseTracking(True);self._drag=None;self._drop_preview=None
        self.setToolTip('Drag MIDI clips from the Browser. Drag a block to move it; drag its right edge to loop it. Right-click for exact Move / Loop length. Click ↻ beside a track name to loop that track to the song ending.')

    def _clip_drop(self,event):
        from .library_widgets import MIME
        from . import clip_library
        if not self.editor or not event.mimeData().hasFormat(MIME):return None
        raw=bytes(event.mimeData().data(MIME))
        if len(raw)>100:return None
        try:clip=clip_library.find(raw.decode('ascii'))
        except (ValueError,KeyError,UnicodeError,StopIteration):return None
        row=int((event.position().y()-30)//self.row_height)
        if not 1<=row<=4 or event.position().x()<self.header:return None
        role=ROLES[row-1]
        if clip['role']!=role:return None
        bar=clip_library.bar_at(self.editor.project,self.position(event.position().x()))
        if bar is None:return None
        return clip['id'],role,bar[0],bar[1]

    def dragEnterEvent(self,event):
        from .library_widgets import MIME
        if event.mimeData().hasFormat(MIME):event.acceptProposedAction()

    def dragMoveEvent(self,event):
        self._drop_preview=self._clip_drop(event);self.update()
        if self._drop_preview:
            event.acceptProposedAction();self._scroll_drag(event.position())
        else:event.ignore()

    def dragLeaveEvent(self,event):
        self._drop_preview=None;self.update();event.accept()

    def dropEvent(self,event):
        target=self._clip_drop(event);self._drop_preview=None;self.update()
        if target:
            clip_id,role,start,_=target
            self.clip_dropped.emit(clip_id,role,start);event.acceptProposedAction()

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

    def snap(self,x):
        """Nearest governing grid boundary, including the exact song ending."""
        end=beat(self.editor.project['length'])
        raw=Fraction(max(0,(x-self.header)/self.pixels_per_beat)).limit_denominator(1000000)
        if raw>=end:return end
        for start,length,meter in measures(self.editor.project):
            if start<=raw<start+length:
                step=Fraction(4*meter['numerator'],meter['denominator'])/meter['governorSegments']
                return min(start+length,start+int((raw-start)/step+Fraction(1,2))*step)
        return end

    def _occurrences(self):
        from .project import arrangement_spans
        return arrangement_spans(self.editor.project)

    def _hit(self,x,y):
        row=int((y-30)//self.row_height)
        if not 1<=row<=4:return None
        role=ROLES[row-1]
        for occurrence in reversed(list(self._occurrences())):
            instance,pattern,start,length,*_=occurrence
            if pattern['role']==role and self.x(start)+2<=x<=self.x(start+length)-2:
                return instance,pattern,start,length
        return None

    def _scroll_drag(self,position):
        parent=self.parentWidget()
        while parent is not None:
            if hasattr(parent,'ensureVisible'):
                parent.ensureVisible(round(position.x()),round(position.y()),35,0);break
            parent=parent.parentWidget()

    def paintEvent(self,event):
        p=QPainter(self);p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(),QColor('#151b23'))
        if not self.editor:return
        project=self.editor.project;end=beat(project['length'])
        for row,name in enumerate(('GOVERNOR','LEAD','RHYTHM','BASS','DRUM KIT','VOCAL 1')):
            top=30+row*self.row_height
            p.fillRect(QRectF(0,top,self.width(),self.row_height),QColor('#1d2631' if row%2==0 else '#18212b'))
            p.setPen(QColor('#c5d2df'));p.drawText(QRectF(8,top,self.header-(32 if 1<=row<=4 else 12),self.row_height),Qt.AlignmentFlag.AlignVCenter,name)
            if 1<=row<=4:
                enabled=ROLES[row-1] in project.get('trackLoops',{})
                p.setPen(QColor('#81e6b7' if enabled else '#8395aa'))
                p.drawText(QRectF(self.header-26,top,24,self.row_height),Qt.AlignmentFlag.AlignCenter,'↻')
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
        for instance,pattern,start,length,ghost in self._occurrences():
            row=ROLES.index(pattern['role'])+1
            x=self.x(start);width=float(length)*self.pixels_per_beat;source_length=beat(pattern['length'])
            if x>event.rect().right() or x+width<event.rect().left():continue
            top=30+row*self.row_height;selected=instance['id']==self.selected_id and not ghost
            color=COLORS[pattern['role']]
            p.setOpacity(.38 if ghost else 1)
            p.setBrush(QColor(color).darker(290));p.setPen(QPen(QColor('#f4f8ff' if selected else color),2 if selected else 1))
            p.drawRoundedRect(QRectF(x+3,top+5,max(3,width-6),40),5,5)
            p.setPen(QColor('#e4edf6'))
            tag='Track loop' if ghost else '↻ '+str(length/source_length)+' cycles' if length>source_length else 'Linked' if instance['linked'] else 'Independent'
            p.drawText(QRectF(x+10,top+7,max(0,width-18),19),Qt.AlignmentFlag.AlignVCenter,f'{pattern["role"].title()} · {tag}')
            left=max(Fraction(0),Fraction(max(0,event.rect().left()-self.header)/self.pixels_per_beat).limit_denominator(1000000)-start)
            right=min(length,Fraction(max(0,event.rect().right()-self.header)/self.pixels_per_beat).limit_denominator(1000000)-start)
            cycle=max(Fraction(0),int(left/source_length)*source_length)
            while cycle<right:
                if cycle:
                    edge=self.x(start+cycle);p.setPen(QPen(QColor(color),1,Qt.PenStyle.DashLine));p.drawLine(round(edge),top+8,round(edge),top+42)
                for e in pattern['events']:
                    position=cycle+beat(e['beat'])
                    if not e['enabled'] or position>=length:continue
                    ex=self.x(start+position);ew=max(2,min(18,float(min(beat(e['duration']),length-position))*self.pixels_per_beat))
                    p.fillRect(QRectF(ex+4,top+31,ew,6),QColor(color))
                cycle+=source_length
            if not ghost:
                p.setPen(QPen(QColor('#f4f8ff' if selected else color),2))
                p.drawLine(round(x+width-7),top+14,round(x+width-7),top+37)
            p.setOpacity(1)
        if self._drag and self._drag.get('changed'):
            drag=self._drag;row=ROLES.index(drag['role'])+1;start=drag['target'] if drag['mode']=='move' else drag['start'];length=drag['length'] if drag['mode']=='move' else drag['target']
            p.setBrush(QColor('#6fb6ec44'));p.setPen(QPen(QColor('#e7f5ff'),2,Qt.PenStyle.DashLine))
            p.drawRoundedRect(QRectF(self.x(start)+3,35+row*self.row_height,max(3,float(length)*self.pixels_per_beat-6),40),5,5)
        if self._drop_preview:
            _,role,start,length=self._drop_preview;row=ROLES.index(role)+1
            p.setBrush(QColor('#71b9ff33'));p.setPen(QPen(QColor('#9bcaff'),2,Qt.PenStyle.DashLine))
            p.drawRoundedRect(QRectF(self.x(start)+3,35+row*self.row_height,float(length)*self.pixels_per_beat-6,40),5,5)
        p.setPen(QColor('#97a7b9'));p.drawText(QRectF(self.header+10,286,self.width()-self.header-20,38),Qt.AlignmentFlag.AlignVCenter,'Recording and vocal comping are in the next development stage.')
        p.setPen(QPen(QColor('#71b9ff'),2));p.drawLine(round(self.x(self.cursor)),26,round(self.x(self.cursor)),332)
        if self.play_beat is not None:
            p.setPen(QPen(QColor('#81e6b7'),2));p.drawLine(round(self.x(self.play_beat)),26,round(self.x(self.play_beat)),332)

    def mousePressEvent(self,event):
        if not self.editor:return
        row=int((event.position().y()-30)//self.row_height)
        if event.position().x()<self.header:
            if 1<=row<=4 and event.position().x()>=self.header-30 and event.button()==Qt.MouseButton.LeftButton:self.track_loop_requested.emit(ROLES[row-1])
            return
        self.setFocus();position=self.position(event.position().x());row=int((event.position().y()-30)//self.row_height)
        role=ROLES[row-1] if 1<=row<=4 else ''
        hit=self._hit(event.position().x(),event.position().y());found=hit[0]['id'] if hit else ''
        self.selected.emit(role,position,found)
        if hit and event.button()==Qt.MouseButton.LeftButton:
            instance,pattern,start,length=hit
            # Repeated track blocks select their source; move/resize the solid block.
            if start!=beat(instance['beat']):return
            mode='resize' if self.x(start+length)-event.position().x()<=11 else 'move'
            self._drag=dict(id=found,role=role,mode=mode,start=start,length=length,pressX=event.position().x(),target=length if mode=='resize' else start,changed=False)
            self.setCursor(Qt.CursorShape.SizeHorCursor if mode=='resize' else Qt.CursorShape.ClosedHandCursor)

    def mouseMoveEvent(self,event):
        if not self.editor:return
        if self._drag:
            drag=self._drag
            if abs(event.position().x()-drag['pressX'])<4 and not drag['changed']:return
            end=beat(self.editor.project['length'])
            if drag['mode']=='move':
                target=self.snap(self.x(drag['start'])+event.position().x()-drag['pressX'])
                drag['target']=max(Fraction(0),min(end-drag['length'],target));drag['changed']=drag['target']!=drag['start']
            else:
                meter=at(self.editor.project['meterMap'],drag['start'])
                step=Fraction(4*meter['numerator'],meter['denominator'])/meter['governorSegments']
                drag['target']=max(step,self.snap(event.position().x())-drag['start']);drag['changed']=drag['target']!=drag['length']
            self._scroll_drag(event.position());self.update();event.accept();return
        hit=self._hit(event.position().x(),event.position().y())
        if hit and hit[2]==beat(hit[0]['beat']):
            self.setCursor(Qt.CursorShape.SizeHorCursor if self.x(hit[2]+hit[3])-event.position().x()<=11 else Qt.CursorShape.OpenHandCursor)
        else:self.unsetCursor()

    def mouseReleaseEvent(self,event):
        drag=self._drag;self._drag=None;self.unsetCursor();self.update()
        if drag and drag['changed']:
            signal=self.instance_moved if drag['mode']=='move' else self.instance_resized
            signal.emit(drag['id'],drag['target']);event.accept()

    def contextMenuEvent(self,event):
        if not self.editor:return
        hit=self._hit(event.pos().x(),event.pos().y()) if event.reason()!=event.Reason.Keyboard else None
        selected=hit[0]['id'] if hit else self.selected_id
        role=hit[1]['role'] if hit else self.editor.pattern(selected)['role'] if selected else ''
        if hit:self.selected.emit(role,self.position(event.pos().x()),selected)
        menu=QMenu(self)
        if selected:
            menu.addAction('Move clip…',lambda:self.move_requested.emit(selected))
            menu.addAction('Loop length…',lambda:self.length_requested.emit(selected))
            menu.addAction('Restore one source cycle',lambda:self.instance_resized.emit(selected,beat(self.editor.pattern(selected)['length'])))
        if role:
            enabled=role in self.editor.project.get('trackLoops',{})
            action=menu.addAction('Loop '+role.title()+' track to song end',lambda:self.track_loop_requested.emit(role));action.setCheckable(True);action.setChecked(enabled)
        if menu.actions():menu.exec(event.globalPos())

    def mouseDoubleClickEvent(self,event):
        if self.editor and 30<=event.position().y()<80:self.chord_requested.emit(self.position(event.position().x()))

    def keyPressEvent(self,event):
        if not self.editor:return
        meter=at(self.editor.project['meterMap'],self.cursor)
        step=Fraction(4*meter['numerator'],meter['denominator'])/meter['governorSegments']
        if event.key()==Qt.Key.Key_Escape and self._drag:
            self._drag=None;self.unsetCursor();self.update();event.accept()
        elif event.key()==Qt.Key.Key_L and event.modifiers()&Qt.KeyboardModifier.ControlModifier and self.selected_id:
            self.track_loop_requested.emit(self.editor.pattern(self.selected_id)['role']);event.accept()
        elif event.key() in (Qt.Key.Key_Left,Qt.Key.Key_Right) and self.selected_id and event.modifiers()&(Qt.KeyboardModifier.ShiftModifier|Qt.KeyboardModifier.ControlModifier):
            direction=-1 if event.key()==Qt.Key.Key_Left else 1
            if event.modifiers()&Qt.KeyboardModifier.ControlModifier:
                length=self.editor.instance_length(self.selected_id);source=beat(self.editor.pattern(self.selected_id)['length'])
                self.instance_resized.emit(self.selected_id,max(step,length+direction*source))
            else:self.instance_moved.emit(self.selected_id,max(Fraction(0),beat(self.editor.instance(self.selected_id)['beat'])+direction*step))
            event.accept()
        elif event.key() in (Qt.Key.Key_Left,Qt.Key.Key_Right):
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
        self.inversion=QComboBox();self.update_inversions();self.inversion.setCurrentIndex(current['inversion'])
        form.addRow('Degree',self.degree);form.addRow('Quality',self.quality);form.addRow('Root alteration',self.alteration);form.addRow('Inversion',self.inversion)
        self.explanation=QLabel();self.explanation.setWordWrap(True);layout.addWidget(self.explanation)
        note=QLabel('Every chord is playable. Native sounds are preferred; missing voicings are prepared from this pack’s source waveforms.');note.setWordWrap(True);layout.addWidget(note)
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel);buttons.accepted.connect(self.accept);buttons.rejected.connect(self.reject);layout.addWidget(buttons)
        self.buttons=buttons
        self.quality.currentIndexChanged.connect(self.update_inversions)
        for box in (self.degree,self.quality,self.alteration,self.inversion):box.currentIndexChanged.connect(self.explain)
        self.explain()

    def update_inversions(self):
        previous=self.inversion.currentIndex();self.inversion.blockSignals(True);self.inversion.clear()
        labels=['Root position','1st inversion','2nd inversion','3rd inversion','4th inversion','5th inversion','6th inversion']
        self.inversion.addItems(labels[:len(QUALITIES[self.quality.currentData()])]);self.inversion.setCurrentIndex(max(0,min(previous,self.inversion.count()-1)));self.inversion.blockSignals(False)

    def value(self):return dict(degree=self.degree.currentIndex()+1,quality=self.quality.currentData(),alteration=self.alteration.currentData(),inversion=self.inversion.currentIndex())

    def explain(self):
        chord=self.value();tone=at(self.editor.project['tonalityMap'],self.position)
        root,pitches,legal=chord_identity(tone['tonic'],tone['mode'],chord)
        sample=self.editor.pack.mappings.get(('rhythm',root,chord['quality'],chord['inversion']))
        valid_inversion=chord['inversion']<len(QUALITIES[chord['quality']])
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(valid_inversion)
        status='Native whole chord' if sample else 'Playable · source-derived whole chord'
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
            from .percussion import records
            for slot,value in records(editor.pack).items():
                name=SLOT_NAMES.get(slot,value['displayName'])
                label=name+(' · '+value['displayName'] if slot in SLOT_NAMES else ' · source-derived' if value.get('derived') else ' · recorded')
                self.sound.addItem(label+(' · unavailable' if value['status']!='available' else ''),value['soundIdentity'])
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

