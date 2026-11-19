"""Launch the packaged Windows workbench."""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

from my_local_ai.ui.local_dashboard import launch_dashboard


def main() -> int:
    parser = argparse.ArgumentParser(description="My Local AI workbench")
    parser.add_argument("--port", type=int, default=0, help="Loopback port (0 selects a free port)")
    parser.add_argument("--draft-root", type=Path, help="Folder for local drafts and progress")
    parser.add_argument("--no-open", action="store_true", help="Do not open a browser window")
    options = parser.parse_args()
    if getattr(sys, "frozen", False):
        project_root = Path(__file__).resolve().parent
        default_drafts = Path(sys.executable).resolve().parent / "mla-drafts"
    else:
        project_root = Path(__file__).resolve().parents[1]
        default_drafts = Path.cwd() / "mla-drafts"
    try:
        launch_dashboard(project_root, port=options.port, open_browser=not options.no_open,
                         draft_root=options.draft_root or default_drafts)
    except KeyboardInterrupt:
        pass
    except (OSError, ValueError) as error:
        print(f"MLA startup failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
