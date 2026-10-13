"""Bounded native note renders and reusable low-latency Qt audition clips."""
from __future__ import annotations

import copy
import hashlib
import shutil
import wave
from collections import OrderedDict
from pathlib import Path

from PySide6.QtCore import QObject, QProcess, QUrl, Signal
from PySide6.QtMultimedia import QSoundEffect

from .contracts import ROOT, RATE, canonical_bytes


def preview_key(plan, pack_identity):
    acoustic=copy.deepcopy(plan)
    acoustic.pop('warnings',None);acoustic.pop('conflicts',None)
    for event in acoustic['events']:event['id']='preview'
    return hashlib.sha256(canonical_bytes([pack_identity,acoustic])).hexdigest()


def preview_pcm16(source, destination):
    """Change only the PCM container depth for portable QSoundEffect playback."""
    with wave.open(str(source),'rb') as stream:
        if (stream.getnchannels(),stream.getsampwidth(),stream.getframerate())!=(2,3,RATE) or not 0<stream.getnframes()<=2*RATE:
            raise ValueError('Invalid note-preview audio format or duration')
        frames=stream.getnframes();raw=stream.readframes(frames)
    if len(raw)!=frames*6:raise ValueError('Truncated note-preview audio')
    pcm=bytearray(frames*4);pcm[0::2]=raw[1::3];pcm[1::2]=raw[2::3]
    with wave.open(str(destination),'wb') as stream:
        stream.setparams((2,2,RATE,frames,'NONE','not compressed'));stream.writeframes(pcm)


class NotePreview(QObject):
    ready=Signal(str,str,bool)  # key, WAV path, reused cache
    played=Signal(str)
    MAX_CLIPS=64
    MAX_SOUNDS=8

    def __init__(self,folder,device,notice,parent=None):
        super().__init__(parent);self.folder=Path(folder);self.folder.mkdir(parents=True,exist_ok=True)
        self.device=device;self.notice=notice;self.cache=OrderedDict();self.sounds=OrderedDict()
        self.process=QProcess(self);self.process.finished.connect(self._finished);self.process.errorOccurred.connect(self._error)
        self.generation=0;self.job=None;self.pending=None;self.play_request=None;self.closed=False

    def request(self,plan,pack_root,pack_identity):
        self.generation+=1;self.play_request=None
        for effect in self.sounds.values():effect.stop()
        if self.closed or plan is None:
            self.pending=None
            if self.job:self.job['canceled']=True
            if self.process.state()!=QProcess.ProcessState.NotRunning:self.process.kill()
            return None
        key=preview_key(plan,pack_identity);item=dict(key=key,plan=plan,root=Path(pack_root),generation=self.generation)
        if key in self.cache and self.cache[key].is_file():
            self.pending=None;self.cache.move_to_end(key);self.ready.emit(key,str(self.cache[key]),True)
            if item['generation']==self.generation and not self.closed:self._play(key,self.cache[key])
            return key
        if self.job and not self.job.get('canceled') and self.job['key']==key and self.process.state()!=QProcess.ProcessState.NotRunning:
            self.job['generation']=self.generation;self.pending=None;return key
        self.pending=item
        if self.process.state()!=QProcess.ProcessState.NotRunning:
            if self.job:self.job['canceled']=True
            self.process.kill()
        else:self._start_pending()
        return key

    def _start_pending(self):
        if self.closed or self.pending is None:return
        item=self.pending;self.pending=None
        folder=self.folder/('job-'+str(item['generation']));folder.mkdir()
        item.update(folder=folder,output=folder/'note24.wav')
        path=folder/'plan.json';path.write_bytes(canonical_bytes(item['plan']));self.job=item
        self.process.setProgram(str(ROOT/'build/prde1-render'))
        self.process.setArguments([str(path),str(item['root']),str(item['output']),'0']);self.process.start()

    def _finished(self,exit_code,exit_status):
        job=self.job;self.job=None;self.process.readAllStandardOutput()
        error=bytes(self.process.readAllStandardError()).decode('utf-8','replace')
        if job is None:return
        current=not self.closed and job['generation']==self.generation
        try:
            if current and exit_code==0 and exit_status==QProcess.ExitStatus.NormalExit:
                path=self.folder/(job['key']+'.wav');preview_pcm16(job['output'],path)
                self.cache[job['key']]=path;self.cache.move_to_end(job['key'])
                while len(self.cache)>self.MAX_CLIPS:
                    key,old=self.cache.popitem(last=False);self._drop_sound(key);old.unlink(missing_ok=True)
                self.ready.emit(job['key'],str(path),False)
                if job['generation']==self.generation and not self.closed:self._play(job['key'],path)
            elif current:self.notice('Note preview failed: '+error.strip())
        except (ValueError,OSError,wave.Error) as error:self.notice('Note preview failed: '+str(error))
        finally:shutil.rmtree(job['folder'],ignore_errors=True)
        self._start_pending()

    def _error(self,error):
        if error==QProcess.ProcessError.FailedToStart:
            job=self.job;self.job=None
            if job:shutil.rmtree(job['folder'],ignore_errors=True)
            self.notice('Note preview renderer could not start: '+self.process.errorString());self._start_pending()

    def _play(self,key,path):
        device=self.device()
        if device is None:return
        if key not in self.sounds:
            effect=QSoundEffect(device,self);effect.setLoopCount(1);effect.setVolume(1)
            effect.statusChanged.connect(lambda key=key:self._sound_ready(key))
            self.sounds[key]=effect;effect.setSource(QUrl.fromLocalFile(str(path)))
        self.sounds.move_to_end(key)
        while len(self.sounds)>self.MAX_SOUNDS:self._drop_sound(next(iter(self.sounds)))
        self.play_request=(self.generation,key);self._sound_ready(key)

    def _sound_ready(self,key):
        effect=self.sounds.get(key)
        if effect is None or self.play_request!=(self.generation,key):return
        if effect.status()==QSoundEffect.Status.Ready:
            self.play_request=None;effect.stop();effect.play();self.played.emit(key)
        elif effect.status()==QSoundEffect.Status.Error:
            self.play_request=None;self.notice('Could not play the note preview on this audio output.')

    def _drop_sound(self,key):
        effect=self.sounds.pop(key,None)
        if effect is not None:effect.stop();effect.deleteLater()

    def set_device(self):
        self.stop()
        for key in list(self.sounds):self._drop_sound(key)

    def stop(self):
        self.generation+=1;self.pending=None;self.play_request=None
        if self.job:self.job['canceled']=True
        if self.process.state()!=QProcess.ProcessState.NotRunning:self.process.kill()
        for effect in self.sounds.values():effect.stop()

    def close(self):
        self.closed=True;self.stop()
        if self.process.state()!=QProcess.ProcessState.NotRunning:self.process.waitForFinished(1000)
        for key in list(self.sounds):self._drop_sound(key)
