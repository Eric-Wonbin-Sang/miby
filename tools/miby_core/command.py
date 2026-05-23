import os
import shlex
import shutil
import subprocess
from pathlib import Path
from typing import List, Optional, Union


class CommandRunner:
    """Small wrapper for running shell commands in a safe, dry-run-aware way."""

    def __init__(self, dry_run: bool = False, verbose: bool = True):
        self.dry_run = dry_run
        self.verbose = verbose

    def run(
        self,
        cmd: List[str],
        cwd: Optional[Path] = None,
        sudo: bool = False,
        env: Optional[dict] = None,
    ) -> Optional[subprocess.CompletedProcess]:
        """Run a command and capture output.

        The command is printed before execution. In dry-run mode, the command is
        only displayed and not executed.
        """
        if sudo:
            cmd = ["sudo"] + cmd
        command_text = " ".join(shlex.quote(str(part)) for part in cmd)
        cwd_text = f" cwd={cwd}" if cwd else ""
        print(("(DRY) " if self.dry_run else "") + f"Running: {command_text}{cwd_text}")

        if self.dry_run:
            return None

        complete_env = os.environ.copy()
        if env:
            complete_env.update(env)

        proc = subprocess.run(
            [str(part) for part in cmd],
            cwd=str(cwd) if cwd else None,
            env=complete_env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )

        if proc.stdout:
            print(proc.stdout.strip())

        if proc.returncode != 0:
            raise subprocess.CalledProcessError(proc.returncode, cmd, output=proc.stdout)

        return proc


def ensure_dir(path: Path) -> None:
    """Create a directory if it does not already exist."""
    if not path.exists():
        path.mkdir(parents=True, exist_ok=True)


def remove_path(path: Path, runner: CommandRunner, sudo: bool = False) -> None:
    """Remove a file or directory, respecting dry-run mode."""
    if not path.exists():
        return
    if runner.dry_run:
        print(f"(DRY) Removing path: {path}")
        return
    if path.is_dir():
        runner.run(["rm", "-rf", str(path)], sudo=sudo)
    else:
        runner.run(["rm", "-f", str(path)], sudo=sudo)


def require_file(path: Path, label: str) -> None:
    if not path.exists() or not path.is_file():
        raise FileNotFoundError(f"Missing {label}: {path}")


def require_dir(path: Path, label: str) -> None:
    """Assert that a required directory exists."""
    if not path.exists() or not path.is_dir():
        raise FileNotFoundError(f"Missing {label}: {path}")


def require_tool(name: str) -> None:
    """Assert that a required CLI tool exists on PATH."""
    if shutil.which(name) is None:
        raise FileNotFoundError(f"Required tool not found: {name}")
