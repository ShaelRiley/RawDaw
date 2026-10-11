"""Offline core commands and a lazy native desktop entry point."""
from __future__ import annotations

import argparse
import json
import subprocess
import tempfile
from pathlib import Path

from .contracts import ContractError, ROOT, atomic_json, canonical_bytes
from .governor import rank_progressions, resolve
from .pack import Pack
from .project import load_project, save_project


def main(argv=None):
    parser=argparse.ArgumentParser(prog="prde1",description="PRDE1 offline prepared-sample core (development checkpoint)")
    commands=parser.add_subparsers(dest="command",required=True)
    desktop=commands.add_parser("gui",help="Open the native desktop editor (requires the desktop extra)")
    desktop.add_argument('--project',type=Path);desktop.add_argument('--pack',type=Path)
    inspect=commands.add_parser("validate-pack",help="Validate archive, musical mappings and prepared audio")
    inspect.add_argument("pack",type=Path)
    ranking=commands.add_parser("rank",help="Show initial six-template coverage ranking, not a finished catalog")
    ranking.add_argument("pack",type=Path); ranking.add_argument("--tonic",type=int,default=0); ranking.add_argument("--mode",default="major")
    for name in ("resolve","render"):
        command=commands.add_parser(name)
        command.add_argument("pack",type=Path); command.add_argument("project",type=Path); command.add_argument("output",type=Path)
        command.add_argument("--approve-altered-render",action="store_true",help="Explicitly approve silent unsupported VST instrument tracks")
        if name=="render":
            command.add_argument("--seek-frame",type=int,default=0)
    roundtrip=commands.add_parser("save-project",help="Validate and transactionally write the native project envelope")
    roundtrip.add_argument("input",type=Path); roundtrip.add_argument("output",type=Path)
    options=parser.parse_args(argv)
    try:
        if options.command=='gui':
            try:from .gui import main as desktop_main
            except ImportError as error:
                raise ContractError('Desktop libraries are unavailable. Run ./run-prde1.sh to install them') from error
            args=[]
            if options.project:args.extend(['--project',str(options.project)])
            if options.pack:args.extend(['--pack',str(options.pack)])
            return desktop_main(args)
        if options.command=="save-project":
            save_project(options.output,load_project(options.input))
            print(json.dumps({"saved":str(options.output)})); return 0
        with Pack(options.pack) as pack:
            if options.command=="validate-pack":
                print(json.dumps({"packId":pack.manifest["packId"],"manifestSha256":pack.manifest_hash,
                                  "sourceKind":pack.manifest["source"]["kind"],"sampleCount":len(pack.samples),
                                  "schemaValid":True,"coverageStatus":"complete-hybrid","sourceCoverageStatus":pack.manifest["validation"]["status"],"warnings":pack.warnings},indent=2)); return 0
            if options.command=="rank":
                print(json.dumps(rank_progressions(pack,options.tonic,options.mode),indent=2,ensure_ascii=False)); return 0
            project=load_project(options.project)
            plan=resolve(project,pack,approve_altered=options.approve_altered_render)
            if options.command=="resolve":
                atomic_json(options.output,plan)
                print(json.dumps({"events":len(plan["events"]),"conflicts":plan["conflicts"],"warnings":plan["warnings"]},indent=2)); return 0
            # Incompatible placed pitches/hits are withheld as approved, but
            # missing media or coverage must not silently alter an export.
            missing=[item for item in plan["conflicts"] if item["code"].startswith("missing_")]
            if missing and not options.approve_altered_render:
                raise ContractError("Unresolved prepared-media requests; inspect resolve output and explicitly approve an altered render")
            executable=ROOT/"build"/"prde1-render"
            if not executable.exists():
                raise ContractError("Native engine is not built. Run make all")
            with tempfile.TemporaryDirectory(prefix="prde1-plan-") as folder:
                path=Path(folder)/"resolved.json"
                path.write_bytes(canonical_bytes(plan))
                result=subprocess.run([str(executable),str(path),str(pack.root),str(options.output),str(options.seek_frame)],capture_output=True,text=True)
                if result.returncode:
                    raise ContractError(result.stderr.strip())
                report=json.loads(result.stdout)
                report.update({"sourceKind":pack.manifest["source"]["kind"],"conflicts":plan["conflicts"],"warnings":plan["warnings"]})
                atomic_json(options.output.with_suffix(".report.json"),report)
                print(json.dumps(report,indent=2))
            return 0
    except (ContractError,OSError,ValueError,KeyError) as error:
        print(f"PRDE1: {error}",file=__import__("sys").stderr)
        return 1


if __name__=="__main__":
    raise SystemExit(main())

