"""
executor.py — Sandboxed code execution and packaging pipeline.
Runs as unprivileged 'levesia' user inside isolated workspace dirs.
"""

import asyncio, os, shutil, uuid, zipfile, logging
from pathlib import Path
from datetime import datetime
import yaml

with open(Path(__file__).parent.parent / "config" / "config.yaml") as f:
    CONFIG = yaml.safe_load(f)

PATHS       = CONFIG["paths"]
LANGUAGES   = CONFIG["languages"]
TIMEOUT     = CONFIG["execution"]["timeout_seconds"]
MAX_SIZE_MB = CONFIG["execution"]["max_output_size_mb"]
log         = logging.getLogger("levesia.executor")


class TaskResult:
    def __init__(self, task_id: str):
        self.task_id  = task_id
        self.success  = False
        self.zip_path = None
        self.log_text = ""
        self.error    = ""
        self.files    = []


def _detect_language(files: dict) -> str:
    ext_map = {}
    for lang, cfg in LANGUAGES.items():
        for ext in cfg["extensions"]:
            ext_map[ext] = lang
    for filename in files:
        ext = Path(filename).suffix.lower()
        if ext in ext_map:
            return ext_map[ext]
    return "python"


def _zip_directory(task_dir: Path, output_path: Path) -> bool:
    skip = {"__pycache__", "node_modules", "target", ".git"}
    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for file in task_dir.rglob("*"):
            if file.is_file():
                rel   = file.relative_to(task_dir)
                parts = rel.parts
                if any(p in skip or p.endswith(".class") for p in parts):
                    continue
                zf.write(file, rel)
    size_mb = output_path.stat().st_size / (1024 * 1024)
    return size_mb <= MAX_SIZE_MB


async def _run(cmd: str, cwd: Path, timeout: int) -> tuple[int, str]:
    proc = await asyncio.create_subprocess_shell(
        cmd, cwd=str(cwd),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
        env={**os.environ, "HOME": str(cwd), "TMPDIR": str(cwd)},
    )
    try:
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        return proc.returncode, stdout.decode(errors="replace")
    except asyncio.TimeoutError:
        proc.kill()
        return -1, f"[TIMEOUT] Exceeded {timeout}s limit."


async def generate_and_run(files: dict, language: str = None) -> TaskResult:
    task_id  = datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + uuid.uuid4().hex[:6]
    task_dir = Path(PATHS["workspace"]) / task_id
    task_dir.mkdir(parents=True, exist_ok=True)
    result     = TaskResult(task_id)
    result.files = list(files.keys())
    lines      = [f"=== Levesia Task {task_id} ===\n"]

    try:
        # Write files
        for fname, content in files.items():
            fp = task_dir / fname
            fp.parent.mkdir(parents=True, exist_ok=True)
            fp.write_text(content, encoding="utf-8")

        lang = language or _detect_language(files)
        if lang not in LANGUAGES:
            result.error = f"Unsupported language: {lang}"
            return result

        cfg        = LANGUAGES[lang]
        entrypoint = cfg["entrypoint"]
        lines.append(f"Language: {lang} | Entrypoint: {entrypoint}\n")

        # Install deps
        install = cfg.get("install", "")
        if install:
            dep_files = {
                "python":     "requirements.txt",
                "javascript": "package.json",
                "typescript": "package.json",
                "ruby":       "Gemfile",
            }
            dep_file = dep_files.get(lang)
            if dep_file and (task_dir / dep_file).exists():
                lines.append(f"\n--- Install: {install} ---\n")
                rc, out = await _run(install, task_dir, TIMEOUT)
                lines.append(out)
                if rc != 0:
                    result.error = f"Dep install failed (rc={rc})"
                    result.log_text = "".join(lines)
                    return result

        # Run
        run_cmd = cfg["run"].replace("{entrypoint}", entrypoint)
        lines.append(f"\n--- Run: {run_cmd} ---\n")
        rc, out = await _run(run_cmd, task_dir, TIMEOUT)
        lines.append(out)

        if rc == -1:
            result.error = f"Timed out after {TIMEOUT}s."
            result.log_text = "".join(lines)
            return result
        if rc != 0:
            result.error = f"Execution failed (rc={rc}). See run.log."
            result.log_text = "".join(lines)
            return result

        lines.append("\n--- SUCCESS (rc=0) ---\n")

        # Write run.log + README
        (task_dir / "run.log").write_text("".join(lines), encoding="utf-8")
        if not (task_dir / "README.md").exists():
            (task_dir / "README.md").write_text(
                f"# Task {task_id}\n\n**Language:** {lang}\n"
                f"**Files:** {', '.join(files.keys())}\n\n"
                f"## Run\n```\n{run_cmd}\n```\n", encoding="utf-8"
            )

        # Zip
        Path(PATHS["output"]).mkdir(parents=True, exist_ok=True)
        zip_path = Path(PATHS["output"]) / f"{task_id}.zip"
        ok = _zip_directory(task_dir, zip_path)
        if not ok:
            result.error = f"Zip exceeds {MAX_SIZE_MB}MB Discord limit."
            result.log_text = "".join(lines)
            return result

        result.success  = True
        result.zip_path = str(zip_path)
        result.log_text = "".join(lines)

        Path(PATHS["logs"]).mkdir(parents=True, exist_ok=True)
        (Path(PATHS["logs"]) / f"{task_id}.log").write_text("".join(lines), encoding="utf-8")
        return result

    except Exception as e:
        log.exception(f"[{task_id}] Executor error")
        result.error    = f"Internal error: {e}"
        result.log_text = "".join(lines)
        return result
    finally:
        shutil.rmtree(task_dir, ignore_errors=True)
