"""Path helpers for Proton release directories and symlinks."""

import os
import tempfile
from pathlib import Path

from .common import FORKS, FileSystemClientProtocol, ForkName
from .exceptions import LinkManagementError
from .filesystem import FileSystemClient


def lock_path() -> Path:
    """Path of the single-instance mutex file.

    XDG_RUNTIME_DIR is a local, per-user directory: flock on a network filesystem is
    advisory and unreliable, and the download/cache dirs may well be NFS or SMB mounts.
    ssh and cron sessions have no XDG_RUNTIME_DIR, so they fall back to /run/user/<uid>
    (mode 0700, same user) and then to /tmp — world-writable, hence the uid in the name.
    """
    root = os.environ.get("XDG_RUNTIME_DIR")
    if not root:
        run_user = Path(f"/run/user/{os.getuid()}")
        root = str(run_user) if run_user.is_dir() else tempfile.gettempdir()
    return Path(root) / f"protonfetcher-{os.getuid()}.lock"


def get_link_names(
    extract_dir: Path,
    fork: ForkName,
) -> tuple[Path, Path, Path]:
    """Get the three symlink paths (main, fallback1, fallback2) for a fork."""
    main, fb1, fb2 = FORKS[fork].link_names
    return (extract_dir / main, extract_dir / fb1, extract_dir / fb2)


def resolve_directory(
    extract_dir: Path,
    tag: str,
    fork: ForkName,
    file_system: FileSystemClientProtocol | None = None,
) -> Path:
    """Resolve the extracted directory for a release tag using fork-specific templates.

    Tries each directory name template from ForkConfig in priority order.

    Raises:
        LinkManagementError: If no template matches an existing directory
    """
    file_system = file_system or FileSystemClient()
    cfg = FORKS[fork]
    for template in cfg.dir_name_templates:
        candidate = extract_dir / template.format(tag=tag)
        if file_system.exists(candidate) and file_system.is_dir(candidate):
            return candidate

    tried = ", ".join(t.format(tag=tag) for t in cfg.dir_name_templates)
    raise LinkManagementError(f"Manual release directory not found: {tried}")


def resolve_directory_candidates(
    extract_dir: Path,
    tag: str,
    fork: ForkName,
) -> list[Path]:
    """Return all candidate directory paths for a tag, in priority order.

    Does not check existence — just generates paths from templates.
    """
    cfg = FORKS[fork]
    return [extract_dir / t.format(tag=tag) for t in cfg.dir_name_templates]
