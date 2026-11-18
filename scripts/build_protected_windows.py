"""Build independent MLA Windows protected binaries without installing/provisioning them.

Requires Windows x64, Python 3.11 and pre-installed PyInstaller 6.22.3.
Never configures users, SCM, TPM/CNG keys, HKLM, ACLs or Defender.
Artifacts are untrusted until independently verified and pinned by the owner.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import tempfile

PYINSTALLER_VERSION = "6.22.3"
IMAGES = (
    ("owner", "MyLocalAI.owner.v1", "service"),
    ("reviewer", "MyLocalAI.reviewer.v1", "service"),
    ("scanner", "MyLocalAI.scanner.v1", "service"),
    ("owner-ui", "MyLocalAI.OwnerUI", "interactive"),
)
MAX_IMAGE_BYTES = 128 * 1024 * 1024
MAX_INTERNAL_BYTES = 512 * 1024 * 1024
MAX_INTERNAL_FILES = 2048


def entrypoint_source(role: str) -> str:
    """Fixed audited entrypoints; no caller-selected runtime role."""
    if role == "owner-ui":
        return ("from my_local_ai.state.consent import owner_session_main\n"
                "if __name__ == '__main__':\n"
                "    raise SystemExit(owner_session_main())\n")
    if role not in {"owner", "reviewer", "scanner"}:
        raise ValueError("unknown frozen image role")
    return ("from my_local_ai.state.consent import protected_service_main\n"
            "if __name__ == '__main__':\n"
            f"    raise SystemExit(protected_service_main({role!r}))\n")


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for data in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(data)
    return digest.hexdigest()


def inspect_image(folder: Path, image_name: str) -> dict:
    """Read-only bounded inventory; reject link-backed frozen images."""
    expected = folder / (image_name + ".exe")
    internal = folder / "_internal"
    if (folder.is_symlink() or not folder.is_dir() or expected.is_symlink()
            or not expected.is_file() or internal.is_symlink() or not internal.is_dir()):
        raise ValueError("missing or non-regular one-folder frozen image")
    if any(p.name not in {expected.name, "_internal"} for p in folder.iterdir()):
        raise ValueError("unexpected top-level frozen image contents")
    image_size = expected.stat().st_size
    if not 1 <= image_size <= MAX_IMAGE_BYTES:
        raise ValueError("frozen image exceeds size limit")
    hashes = {}
    total = count = 0
    for root, dirs, files in os.walk(internal, followlinks=False):
        for name in (*dirs, *files):
            p = Path(root) / name
            if p.is_symlink():
                raise ValueError("symlink in frozen image")
            if not p.is_file() and not p.is_dir():
                raise ValueError("unsupported file type in frozen image")
        for name in files:
            p = Path(root) / name
            count += 1
            total += p.stat().st_size
            if count > MAX_INTERNAL_FILES or total > MAX_INTERNAL_BYTES:
                raise ValueError("frozen bundle exceeds runtime bounds")
            hashes[p.relative_to(folder).as_posix()] = _hash_file(p)
    if count == 0:
        raise ValueError("empty frozen bundle")
    return {"image_sha256": _hash_file(expected), "internal_file_count": count,
            "internal_bytes": total, "internal_sha256": dict(sorted(hashes.items()))}


def build_all(output: Path) -> Path:
    if os.name != "nt" or platform.machine().lower() not in {"amd64", "x86_64"}:
        raise RuntimeError("Windows x64 required; no cross-build or emulation")
    if sys.version_info[:2] != (3, 11):
        raise RuntimeError("Python 3.11 required")
    try:
        installed = importlib.metadata.version("pyinstaller")
    except importlib.metadata.PackageNotFoundError as exc:
        raise RuntimeError("PyInstaller must be installed separately; no auto-install") from exc
    if installed != PYINSTALLER_VERSION:
        raise RuntimeError("PyInstaller version mismatch; build refused")
    project = Path(__file__).resolve().parent.parent
    source = project / "src"
    if source.is_symlink() or not (source / "my_local_ai" / "state" / "consent.py").is_file():
        raise RuntimeError("trusted MLA source tree unavailable")
    output = output.absolute()
    if output.exists() or output.is_symlink():
        raise FileExistsError("refusing to overwrite any previous build")
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="mla-protected-stage-", dir=output.parent) as tmp:
        stage = Path(tmp)
        dist = stage / "dist"
        entry = stage / "entry"
        entry.mkdir()
        env = os.environ.copy()
        env["PYTHONNOUSERSITE"] = "1"
        env["PYINSTALLER_CONFIG_DIR"] = str(stage / "cache")
        env.pop("PYTHONPATH", None)
        for role, name, kind in IMAGES:
            wrapper = entry / (role.replace("-", "_") + ".py")
            wrapper.write_text(entrypoint_source(role), encoding="utf-8")
            cmd = [sys.executable, "-I", "-m", "PyInstaller", "--onedir",
                   "--contents-directory", "_internal", "--noupx", "--clean",
                   "--noconfirm", "--log-level", "ERROR", "--name", name,
                   "--distpath", str(dist), "--workpath", str(stage / "work"),
                   "--specpath", str(stage / "spec"), "--paths", str(source),
                   "--windowed" if kind == "interactive" else "--console",
                   str(wrapper)]
            subprocess.run(cmd, check=True, cwd=project, env=env)
        manifest = {
            "schema": "mla-protected-bundle-inventory/v1",
            "trusted_or_installed": False,
            "os_accounts_keys_acl_service_changes": "NOT_PERFORMED",
            "windows_native_acceptance": "NOT_RUN",
            "python": f"{sys.version_info.major}.{sys.version_info.minor}",
            "pyinstaller": PYINSTALLER_VERSION,
            "images": {},
        }
        if {p.name for p in dist.iterdir()} != {name for _, name, _ in IMAGES}:
            raise RuntimeError("incomplete or unexpected frozen output")
        for role, name, kind in IMAGES:
            manifest["images"][role] = {
                "directory": name, "executable": name + ".exe",
                "scm_service": "MyLocalAI." + role + ".v1" if kind == "service" else None,
                **inspect_image(dist / name, name),
            }
        (dist / "UNTRUSTED_BUILD_MANIFEST.json").write_text(
            json.dumps(manifest, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        # Same-volume rename: never publish an incomplete build directory.
        dist.rename(output)
    return output


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("dist/mla-protected-v1"),
                        help="New directory only; never overwrites or installs")
    args = parser.parse_args(argv)
    try:
        result = build_all(args.output)
    except (ValueError, RuntimeError, OSError, subprocess.CalledProcessError) as exc:
        print("BUILD_HOLD:", type(exc).__name__, str(exc), file=sys.stderr)
        return 1
    print("BUILT_UNTRUSTED:", result)
    print("NO_INSTALL_NO_TRUST: independent Owner/Windows provisioning approval required")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
