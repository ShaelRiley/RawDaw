"""Build the versioned shared contracts. No audio or source analysis occurs here."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VERSION = "1.0.0-dev.1"


def obj(properties, required=None):
    return {"type": "object", "properties": properties, "required": list(properties) if required is None else required,
            "additionalProperties": False}


def array(items, maximum=100000, minimum=0):
    return {"type": "array", "items": items, "maxItems": maximum, "minItems": minimum}


def ref(name):
    return {"$ref": "#/$defs/" + name}


def number(low, high):
    return {"type": "number", "minimum": low, "maximum": high}


def integer(low, high):
    return {"type": "integer", "minimum": low, "maximum": high}


TEXT = {"type": "string", "maxLength": 4096}
ID = {"type": "string", "pattern": "^[a-zA-Z0-9_-]{1,100}$"}
HASH = {"type": "string", "pattern": "^[0-9a-f]{64}$"}
BEAT = {"type": "string", "pattern": "^[0-9]+(?:/[1-9][0-9]*)?$", "maxLength": 30}
BOOLEAN = {"type": "boolean"}
PATH = {"type": "string", "minLength": 1, "maxLength": 255}
MIDI = integer(0, 127)
ROLES = ["lead", "rhythm", "bass", "drums"]
SLOTS = ["kick", "snare", "hatClosed", "hatOpen", "tom1", "tom2", "extra1", "extra2"]

quality = {"type": "string", "enum": ["major", "minor", "diminished", "augmented", "power", "sus2", "sus4",
           "major7", "minor7", "dominant7", "halfDiminished7", "diminished7", "minorMajor7"]}
chord = obj({"degree": integer(1, 7), "alteration": integer(-1, 1), "quality": quality, "inversion": integer(0, 3)})

status = obj({"status": {"type": "string", "enum": ["available", "unavailable", "empty"]},
              "reason": TEXT, "sampleId": {"type": ["string", "null"], "maxLength": 100},
              "displayName": TEXT, "soundIdentity": TEXT, "midiAddress": {"type": ["integer", "null"], "minimum": 0, "maximum": 127},
              "pitchClass": {"type": "string", "enum": ["pitched", "unpitched", "uncertain"]},
              "pitches": array(MIDI, 16)})

sample = obj({"id": ID, "role": {"type": "string", "enum": ROLES}, "articulation": TEXT,
              "path": PATH, "sha256": HASH, "sampleRate": {"const": 48000}, "bitsPerSample": {"const": 24},
              "channels": integer(1, 2), "frames": integer(1, 1440000), "onsetFrame": integer(0, 1440000),
              "gainDb": number(-24, 12), "pitches": array(MIDI, 16),
              "chord": {"type": ["object", "null"], "additionalProperties": True},
              "loop": {"type": ["object", "null"], "properties": {"startFrame": integer(0,1440000),
                    "endFrame": integer(1,1440000),"validated": {"const": True}}, "required": ["startFrame", "endFrame", "validated"],
                    "additionalProperties": False},
              "source": obj({"seconds": number(0, 86400), "quarterBeat": BEAT, "durationSeconds": number(0, 30)}),
              "lineage": obj({"kind": {"type": "string", "enum": ["native", "pre-rendered", "synthetic"]},
                              "sourceAsset": TEXT, "recipe": TEXT, "transformationCost": number(0, 100)}),
              "quality": obj({"accepted": {"const": True}, "confidence": number(0, 1), "notes": TEXT})})

mapping = obj({"role": {"type": "string", "enum": ["lead", "rhythm", "bass"]},
               "note": {"type": ["integer", "null"], "minimum": 0, "maximum": 127},
               "root": {"type": ["integer", "null"], "minimum": 0, "maximum": 11},
               "quality": {"type": ["string", "null"]}, "inversion": integer(0,3), "sampleId": ID})

pack = obj({"schemaVersion": {"const": VERSION}, "packId": ID,
            "builder": obj({"version": TEXT, "profileVersion": TEXT, "modelVersion": TEXT}),
            "source": obj({"title": TEXT, "sha256": HASH, "kind": {"type": "string", "enum": ["authorized_recording", "synthetic_fixture"]},
                           "rightsDeclaration": TEXT, "license": TEXT, "attribution": TEXT}),
            "audio": obj({"sampleRate": {"const": 48000}, "bitsPerSample": {"const": 24}, "tuningHz": {"const": 440}, "tuning": {"const": "12-TET"}}),
            "maps": obj({"harmony": PATH, "coverage": PATH}),
            "instruments": obj({"lead": ref("status"), "rhythm": ref("status"), "bass": ref("status"),
                                "drums": obj({slot: ref("status") for slot in SLOTS})}),
            "samples": array(ref("sample"), 1024), "mappings": array(ref("mapping"), 8192),
            "files": {"type": "object", "additionalProperties": HASH},
            "clips": obj({"index": PATH, "libraryVersion": TEXT}),
            "channelPresets": PATH, "provenance": PATH, "qa": PATH, "preview": PATH,
            "validation": obj({"status": {"type": "string", "enum": ["complete", "coverage-limited"]}, "notes": TEXT})})
pack["$defs"] = {"status": status, "sample": sample, "mapping": mapping}

expression = obj({"velocity": number(0,1), "attackMs": number(0,100), "playPercent": number(0,100),
                  "changePercent": number(0,100), "variation": {"type":"string","enum":["none","nearby_note","double","gate"]},
                  "locked": BOOLEAN, "lockExactPitch": BOOLEAN})
event = obj({"id": ID, "beat": BEAT, "duration": BEAT, "kind": {"type":"string","enum":["note","chord","drum"]},
             "enabled": BOOLEAN, "choice": obj({"tone": integer(0,6), "registerMidi": MIDI, "exactMidi": {"type":["integer","null"],"minimum":0,"maximum":127},
                                               "soundIdentity": TEXT}), "expression": expression})
pattern = obj({"id": ID, "role": {"type":"string","enum":ROLES}, "length":BEAT, "events":array(ref("event"),4096),
               "provenance":obj({"sourceClip":TEXT,"license":TEXT,"changes":TEXT})})

insert = obj({"pluginId": TEXT, "version":TEXT, "statePath":{ "type":["string","null"]},
              "bypassed":BOOLEAN, "missing":BOOLEAN})
channel = obj({"gainDb":number(-96,12),"pan":number(-1,1),"muted":BOOLEAN,
               "eqPreset":TEXT,"reverbOn":BOOLEAN,"delayOn":BOOLEAN,"inserts":array(ref("insert"),3)})
eq = obj({"on":BOOLEAN,"highpassHz":number(20,2000),"bellHz":number(30,16000),"bellDb":number(-12,12),
          "bellQ":number(.3,4),"shelfHz":number(1000,18000),"shelfDb":number(-12,12)})
channel['properties']['eq']=eq  # Optional extension: old saved mixes remain dry.
compressor = obj({"on":BOOLEAN,"thresholdDb":number(-48,0),"ratio":number(1,20),
                  "attackMs":number(.1,100),"releaseMs":number(10,2000)})
compressor['properties']['makeupDb']=number(-12,12)
drum_compressor = obj(dict(compressor['properties']))
sidechain = obj({"on":BOOLEAN,"thresholdDb":number(-60,0),"ratio":number(1,20),
                 "attackMs":number(.1,100),"releaseMs":number(10,2000),"maxDuckDb":number(0,18)})

project = obj({"formatVersion":{"const":VERSION}, "projectId":ID, "title":TEXT,
               "packReference":obj({"packId":ID,"manifestSha256":HASH}),
               "musicalRegistryVersion":{"const":"core-v1-dev.1"},
               "tempoMap":array(obj({"beat":BEAT,"quarterBpm":number(20,300)}),4096,1),
               "meterMap":array(obj({"beat":BEAT,"numerator":integer(1,16),"denominator":{"type":"integer","enum":[2,4,8,16]},
                                     "governorSegments":{"type":"integer","enum":[3,4,6,8]}}),4096,1),
               "tonalityMap":array(obj({"beat":BEAT,"tonic":integer(0,11),"mode":TEXT}),4096,1),
               "harmony":array(obj({"beat":BEAT,"chord":ref("chord")}),16384,1),
               "length":BEAT,"patterns":array(ref("pattern"),4096),
               "instances":array(obj({"id":ID,"patternId":ID,"beat":BEAT,"linked":BOOLEAN}),4096),
               "variation":obj({"seed":TEXT,"revision":integer(0,2147483647)}),
               "mix":obj({"channels":{ "type":"object","additionalProperties":ref("channel")},
                           "master":ref("channel"),"compressor":compressor}),
               "pluginTracks":array(obj({"id":ID,"pluginId":TEXT,"version":TEXT,"statePath":{ "type":["string","null"]},
                   "missing":BOOLEAN,"mode":{"type":"string","enum":["chord","monophonic","percussion"]},
                   "patterns":array(ref("pattern"),4096),"percussionMap":{"type":"object","additionalProperties":MIDI},"channel":ref("channel")}),3),
               "vocals":array(obj({"id":ID,"visible":BOOLEAN,"takes":array(obj({"id":ID,"path":PATH,"sha256":HASH,
                   "startSeconds":number(0,7200),"complete":BOOLEAN}),10000),"selectedTakeId":{"type":["string","null"]},
                   "comp":array(obj({"takeId":ID,"startSeconds":number(0,7200),"endSeconds":number(0,7200),"sourceOffsetSeconds":number(0,7200)}),10000),
                   "correction":obj({"on":BOOLEAN,"target":{"type":"string","enum":["key-mode","chord-tones"]}}),"channel":ref("channel")}),4,1),
               "editorContext":obj({"selection":TEXT,"zoom":number(0.1,10),"scrollBeat":BEAT,"lastAction":TEXT}),
               "credits":array(obj({"source":TEXT,"license":TEXT,"attribution":TEXT,"changes":TEXT}),4096)})
project["$defs"]={"chord":chord,"event":event,"pattern":pattern,"insert":insert,"channel":channel}
project['properties']['mix']['properties'].update(drumBusCompressor=drum_compressor,bassSidechain=sidechain)

resolved = obj({"formatVersion":{"const":VERSION},"sampleRate":{"const":48000},"endFrame":integer(1,86400000),
                "assets":array(obj({"id":ID,"path":PATH,"channels":integer(1,2),"frames":integer(1,1440000),
                      "onsetFrame":integer(0,1440000),"loopStart":integer(0,1440000),"loopEnd":integer(0,1440000)}),1024),
                "events":array(obj({"id":TEXT,"assetIndex":integer(0,1023),"startFrame":integer(0,86400000),
                      "endFrame":integer(1,86400240),"releaseFrames":integer(1,4800),"attackFrames":integer(0,4800),
                      "gain":number(0,8),"pan":number(-1,1),"notePitches":array(MIDI,16),"role":TEXT,
                      "endReason":TEXT}),100000),
                "conflicts":array(obj({"eventId":TEXT,"code":TEXT,"message":TEXT}),100000),
                "warnings":array(TEXT,100000),"compressor":project["properties"]["mix"]["properties"]["compressor"],
                "masterGain":number(0,4),"peakCeilingDb":number(-1,0)})
resolved['properties']['processing']=obj({"version":{"const":"drum-mix-v1"},
    "drumEq":obj({slot:eq for slot in SLOTS}),"drumBusCompressor":drum_compressor,"bassSidechain":sidechain,
    "drumBusGain":number(0,4),"drumBusPan":number(-1,1)})

if __name__ == "__main__":
    (ROOT / "schemas").mkdir(exist_ok=True)
    for name, schema in [("pack",pack),("project",project),("events",resolved)]:
        schema.update({"$schema":"https://json-schema.org/draft/2020-12/schema", "$id":f"urn:prde1:{name}:{VERSION}",
                       "title":f"PRDE1 experimental v1 {name} contract"})
        (ROOT/"schemas"/f"prde1-{name}-v1.schema.json").write_text(json.dumps(schema,indent=2)+"\n")
