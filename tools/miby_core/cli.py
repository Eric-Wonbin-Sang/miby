import argparse
import sys
from pathlib import Path
from typing import List

from . import adb, context, dropbear, firmware, overlay, status
from . import overlay_registry as overlays_registry
from .status import StepResult


"""Command-line interface for the MIBY firmware build system."""


def _clean_artifacts(ctx, dry_run: bool = False) -> List[StepResult]:
    """Remove all working directories and build artifacts."""
    import shutil
    results: List[StepResult] = []
    
    dirs_to_remove = [
        ctx.work_dir,
        ctx.output_dir,
        ctx.overlays_dir / "dropbear",
        ctx.overlays_dir / "adb",
        ctx.tools_dir / "dropbear",
        ctx.root_dir / "scripts",
    ]
    
    for path in dirs_to_remove:
        if path.exists():
            if dry_run:
                print(f"(DRY) Would remove: {path}")
                results.append(StepResult.done(f"would_remove_{path.name}", f"Would remove {path}"))
            else:
                try:
                    if path.is_dir():
                        shutil.rmtree(path)
                    else:
                        path.unlink()
                    results.append(StepResult.done(f"remove_{path.name}", f"Removed {path}", paths=[path]))
                except Exception as e:
                    results.append(StepResult.fail(f"remove_{path.name}", str(e)))
        else:
            results.append(StepResult.skip(f"remove_{path.name}", f"Path does not exist: {path}"))
    
    return results


def _print_step_results(results: List[StepResult]) -> None:
    for result in results:
        state = "SKIPPED" if result.skipped else "OK" if result.ok else "FAIL"
        print(f"[{state}] {result.name}: {result.message}")
        for path in result.paths:
            print(f"    {path}")


def _any_failure(results: List[StepResult]) -> bool:
    return any(not result.ok for result in results)


def main(argv: List[str] = None) -> int:
    parser = argparse.ArgumentParser(description="MIBY firmware build system for Hiby R3 Pro II")
    parser.add_argument("--root", default=Path.cwd(), type=Path, help="Repository root directory")
    parser.add_argument("--dry-run", action="store_true", help="Show actions without executing")
    parser.add_argument("--status", action="store_true", help="Print current project status and exit")
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("status", help="Show project status")

    # Extraction commands operate on the standard firmware workspace layout.
    extract_parser = subparsers.add_parser("extract", help="Extract firmware and rootfs")
    extract_parser.add_argument("firmware_name")
    extract_parser.add_argument("--force", action="store_true")

    dropbear_build_parser = subparsers.add_parser("dropbear-build", help="Build dropbear for mipsel")
    dropbear_build_parser.add_argument("--force", action="store_true")
    dropbear_build_parser.add_argument("--redownload-source", action="store_true")

    dropbear_overlay_parser = subparsers.add_parser("dropbear-overlay", help="Create dropbear overlay")
    dropbear_overlay_parser.add_argument("--public-key", type=str, default=None)
    auto_group = dropbear_overlay_parser.add_mutually_exclusive_group()
    auto_group.add_argument("--auto-start", dest="auto_start", action="store_true")
    auto_group.add_argument("--manual-start", dest="auto_start", action="store_false")
    dropbear_overlay_parser.set_defaults(auto_start=True)
    indicator_group = dropbear_overlay_parser.add_mutually_exclusive_group()
    indicator_group.add_argument("--show-indicator", dest="show_indicator", action="store_true")
    indicator_group.add_argument("--no-show-indicator", dest="show_indicator", action="store_false")
    dropbear_overlay_parser.set_defaults(show_indicator=True)
    dropbear_overlay_parser.add_argument("--port", type=int, default=2222)

    inject_overlay_parser = subparsers.add_parser("inject-overlay", help="Inject an overlay into extracted rootfs")
    inject_overlay_parser.add_argument("firmware_name")
    inject_overlay_parser.add_argument("overlay")
    inject_overlay_parser.add_argument("--force", action="store_true")

    inject_dropbear_parser = subparsers.add_parser("inject-dropbear", help="Build, create, and inject dropbear overlay")
    inject_dropbear_parser.add_argument("firmware_name")
    inject_dropbear_parser.add_argument("--public-key", type=str, default=None)
    auto_group2 = inject_dropbear_parser.add_mutually_exclusive_group()
    auto_group2.add_argument("--auto-start", dest="auto_start", action="store_true")
    auto_group2.add_argument("--manual-start", dest="auto_start", action="store_false")
    inject_dropbear_parser.set_defaults(auto_start=True)
    indicator_group2 = inject_dropbear_parser.add_mutually_exclusive_group()
    indicator_group2.add_argument("--show-indicator", dest="show_indicator", action="store_true")
    indicator_group2.add_argument("--no-show-indicator", dest="show_indicator", action="store_false")
    inject_dropbear_parser.set_defaults(show_indicator=True)
    inject_dropbear_parser.add_argument("--port", type=int, default=2222)
    inject_dropbear_parser.add_argument("--force", action="store_true")

    adb_overlay_parser = subparsers.add_parser("adb-overlay", help="Create adb overlay")

    overlays_list_parser = subparsers.add_parser("overlays", help="List discovered overlay plugins")

    overlay_build_parser = subparsers.add_parser("overlay-build", help="Build overlays from tools/overlays")
    overlay_build_parser.add_argument("names", nargs="*", help="Overlay names to build")
    overlay_build_parser.add_argument("--all", action="store_true")
    overlay_build_parser.add_argument("--public-key", type=str, default=None)

    inject_overlays_parser = subparsers.add_parser("inject-overlays", help="Inject multiple overlays into firmware")
    inject_overlays_parser.add_argument("firmware_name")
    inject_overlays_parser.add_argument("names", nargs="*", help="Overlay names to inject")
    inject_overlays_parser.add_argument("--all", action="store_true")
    inject_overlays_parser.add_argument("--force", action="store_true")

    adb_inject_parser = subparsers.add_parser("adb-inject", help="Create and inject adb overlay")
    adb_inject_parser.add_argument("firmware_name")
    adb_inject_parser.add_argument("--force", action="store_true")

    pack_parser = subparsers.add_parser("pack", help="Package firmware into a new UPT")
    pack_parser.add_argument("firmware_name")
    pack_parser.add_argument("--output", type=str, default=None)
    pack_parser.add_argument("--force", action="store_true")

    full_parser = subparsers.add_parser("full", help="Run extract, optional dropbear/adb injection, and pack")
    full_parser.add_argument("firmware_name")
    full_parser.add_argument("--dropbear", action="store_true")
    full_parser.add_argument("--adb", action="store_true")
    full_parser.add_argument("--public-key", type=str, default=None)
    full_parser.add_argument("--force", action="store_true")
    full_parser.add_argument("--output", type=str, default=None)

    clean_parser = subparsers.add_parser("clean", help="Remove all working directories and build artifacts")

    args = parser.parse_args(argv)
    ctx = context.ProjectContext.from_root(args.root, dry_run=args.dry_run)

    if args.status:
        if args.command is not None:
            parser.error("--status cannot be used with a subcommand")
        status_obj = status.list_project_status(ctx)
        status.print_project_status(status_obj)
        return 0

    if args.command == "status":
        status_obj = status.list_project_status(ctx)
        status.print_project_status(status_obj)
        return 0

    if args.command == "overlays":
        names = overlays_registry.discover_overlay_names(ctx)
        print("Discovered overlays:")
        for n in names:
            print(f"  - {n}")
        return 0

    # All other commands perform build operations in the context of the selected
    # firmware source and the configured repository root.

    if args.command == "extract":
        results = firmware.extract_firmware(ctx, args.firmware_name, force=args.force)
        _print_step_results(results)
        return 1 if _any_failure(results) else 0

    if args.command == "dropbear-build":
        result = dropbear.build_dropbear(ctx, force=args.force, redownload_source=args.redownload_source)
        _print_step_results([result])
        return 1 if not result.ok else 0

    if args.command == "dropbear-overlay":
        # Build the dropbear overlay via overlay registry for compatibility
        result = overlays_registry.build_overlay(ctx, "dropbear", public_key=args.public_key, auto_start=args.auto_start, show_indicator=args.show_indicator, port=args.port)
        _print_step_results([result])
        return 1 if not result.ok else 0

    if args.command == "inject-overlay":
        result = overlay.inject_overlay(ctx, args.firmware_name, args.overlay, force=args.force)
        _print_step_results([result])
        return 1 if not result.ok else 0

    if args.command == "overlay-build":
        names = args.names or []
        if args.all:
            results = overlays_registry.build_all_overlays(ctx, public_key=args.public_key)
        else:
            results = overlays_registry.build_overlays(ctx, names, public_key=args.public_key)
        _print_step_results(results)
        return 1 if _any_failure(results) else 0

    if args.command == "inject-overlays":
        names = args.names or []
        if args.all:
            names = overlays_registry.discover_overlay_names(ctx)
        results = []
        # Ensure overlays built
        build_results = overlays_registry.build_overlays(ctx, names)
        results.extend(build_results)
        if _any_failure(build_results):
            _print_step_results(results)
            return 1
        # Inject each
        for n in names:
            r = overlay.inject_overlay(ctx, args.firmware_name, n, force=args.force)
            results.append(r)
            if not r.ok:
                _print_step_results(results)
                return 1
        _print_step_results(results)
        return 0

    if args.command == "inject-dropbear":
        results = dropbear.inject_dropbear(
            ctx,
            args.firmware_name,
            public_key=args.public_key,
            auto_start=args.auto_start,
            show_indicator=args.show_indicator,
            port=args.port,
            force=args.force,
        )
        _print_step_results(results)
        return 1 if _any_failure(results) else 0

    if args.command == "adb-overlay":
        result = overlays_registry.build_overlay(ctx, "adb")
        _print_step_results([result])
        return 1 if not result.ok else 0

    if args.command == "adb-inject":
        # build if necessary
        overlays_registry.build_overlay(ctx, "adb")
        results = adb.inject_adb(ctx, args.firmware_name, force=args.force)
        _print_step_results(results)
        return 1 if _any_failure(results) else 0

    if args.command == "pack":
        results = firmware.pack_firmware(ctx, args.firmware_name, output_name=args.output, force=args.force)
        _print_step_results(results)
        return 1 if _any_failure(results) else 0

    if args.command == "full":
        results: List[StepResult] = []
        extract_results = firmware.extract_firmware(ctx, args.firmware_name, force=args.force)
        results.extend(extract_results)
        if _any_failure(extract_results):
            _print_step_results(results)
            return 1
        # support legacy flags
        overlays_to_inject = []
        if args.dropbear:
            overlays_to_inject.append("dropbear")
        if args.adb:
            overlays_to_inject.append("adb")
        # additional overlays via env var or future flags can be added
        for ov in overlays_to_inject:
            # build then inject
            overlays_registry.build_overlay(ctx, ov, public_key=args.public_key)
            r = overlay.inject_overlay(ctx, args.firmware_name, ov, force=args.force)
            results.append(r)
            if not r.ok:
                _print_step_results(results)
                return 1

        pack_results = firmware.pack_firmware(ctx, args.firmware_name, output_name=args.output, force=args.force)
        results.extend(pack_results)
        _print_step_results(results)
        return 1 if _any_failure(results) else 0

    if args.command == "clean":
        clean_results = _clean_artifacts(ctx, dry_run=args.dry_run)
        _print_step_results(clean_results)
        return 1 if _any_failure(clean_results) else 0

    parser.print_help()
    return 1
