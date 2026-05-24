import importlib.util
import sys
from pathlib import Path
from typing import List
from .overlay_base import FirmwareOverlay
from .status import StepResult


def _overlays_root(ctx) -> Path:
    return ctx.root_dir / "tools" / "overlays"


def discover_overlay_names(ctx) -> List[str]:
    root = _overlays_root(ctx)
    if not root.exists():
        return []
    return sorted([p.name for p in root.iterdir() if p.is_dir() and (p / "overlay.py").is_file()])


def _load_module_from_path(path: Path):
    spec = importlib.util.spec_from_file_location(path.stem, str(path))
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_overlay_class(ctx, overlay_name: str):
    mod_path = _overlays_root(ctx) / overlay_name / "overlay.py"
    if not mod_path.exists():
        raise FileNotFoundError(f"Overlay module not found: {mod_path}")
    # Ensure project root is on sys.path so overlay modules can import package modules
    root = str(ctx.root_dir)
    removed = False
    if root not in sys.path:
        sys.path.insert(0, root)
        removed = True
    try:
        mod = _load_module_from_path(mod_path)
    finally:
        if removed:
            try:
                sys.path.remove(root)
            except ValueError:
                pass
    # module may expose class or factory
    if hasattr(mod, "Overlay"):
        return getattr(mod, "Overlay")
    if hasattr(mod, "get_overlay_class"):
        return mod.get_overlay_class()
    # fallback: find subclass of FirmwareOverlay
    for v in vars(mod).values():
        try:
            if isinstance(v, type) and issubclass(v, FirmwareOverlay) and v is not FirmwareOverlay:
                return v
        except Exception:
            continue
    raise RuntimeError("No overlay class found in module")


def create_overlay_instance(ctx, overlay_name: str):
    cls = load_overlay_class(ctx, overlay_name)
    return cls(ctx)


def build_overlay(ctx, overlay_name: str, **kwargs) -> StepResult:
    inst = create_overlay_instance(ctx, overlay_name)
    return inst.build(**kwargs)


def build_overlays(ctx, overlay_names: List[str], **kwargs) -> List[StepResult]:
    results = []
    for name in overlay_names:
        try:
            results.append(build_overlay(ctx, name, **kwargs))
        except Exception as exc:
            results.append(StepResult.fail(f"build_overlay_{name}", str(exc)))
    return results


def build_all_overlays(ctx, **kwargs) -> List[StepResult]:
    names = discover_overlay_names(ctx)
    return build_overlays(ctx, names, **kwargs)
