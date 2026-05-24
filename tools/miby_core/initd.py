from dataclasses import dataclass
from pathlib import Path
import re


@dataclass(frozen=True)
class InitScriptSpec:
    priority: int
    name: str
    content: str
    executable: bool = True


def normalize_init_name(name: str) -> str:
    # keep alnum, underscore, dash
    return re.sub(r"[^A-Za-z0-9_\-]", "_", name)


def make_init_script_filename(priority: int, name: str) -> str:
    if not (0 <= priority <= 99):
        raise ValueError("priority must be between 0 and 99")
    n = normalize_init_name(name)
    return f"S{priority:02d}miby_{n}"


def write_init_script(root: Path, spec: InitScriptSpec) -> Path:
    if "/" in spec.name:
        raise ValueError("init script name must not contain '/'")
    filename = make_init_script_filename(spec.priority, spec.name)
    initd_dir = root / "etc" / "init.d"
    initd_dir.mkdir(parents=True, exist_ok=True)
    path = initd_dir / filename
    path.write_text(spec.content, encoding="utf-8")
    if spec.executable:
        path.chmod(0o755)
    return path
