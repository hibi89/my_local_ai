"""PyInstaller specification for the Windows MLA workbench executable."""
from pathlib import Path


project = Path(SPECPATH).resolve().parent
source = project / "src"
ui = source / "my_local_ai" / "ui"
assets = [
    "dashboard.css", "workbench.css", "workbench.js", "workbench-music.js",
    "music-pixel-start.ogg", "music-bubble-square.ogg", "music-sunset-hill.ogg",
]
metadata = [
    "WORK_PHASE_GATES.json", "INSTANT_TASK_QUEUE.json", "P1_SWU_TASK_QUEUE.json",
    "P1_V1_3_SWU_REBASELINE.json", "VERIFICATION_TASK_QUEUE.json",
    "docs/OPTIONAL_CODESHIELD_TASK_QUEUE.json", "docs/WINDOWS_LOCAL_OPERATOR_SWU_QUEUE.json",
]
analysis = Analysis(
    [str(project / "scripts" / "mla_workbench_windows.py")],
    pathex=[str(source)],
    datas=[(str(ui / asset), "my_local_ai/ui") for asset in assets]
    + [(str(project / file), str(Path(file).parent)) for file in metadata],
)
archive = PYZ(analysis.pure)
exe = EXE(
    archive, analysis.scripts, analysis.binaries, analysis.datas, [],
    name="MLA", upx=False, console=True,
)
