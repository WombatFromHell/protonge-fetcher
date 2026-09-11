"""Common types, protocols, and constants for ProtonFetcher."""

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Iterator, Protocol


class ForkName(StrEnum):
    GE_PROTON = "GE-Proton"
    PROTON_EM = "Proton-EM"
    CACHYOS = "CachyOS"
    DW_PROTON = "DW-Proton"


# Type aliases for better readability
Headers = dict[str, str]
VersionTuple = tuple[str, int, int, int]  # (prefix, major, minor, patch)
ReleaseTagsList = list[str]
VersionCandidateList = list[tuple[VersionTuple, Path]]
VersionGroups = dict[VersionTuple, list[Path]]


class PlatformAdapter(Protocol):
    """Protocol for platform-specific URL and header construction."""

    @property
    def api_base(self) -> str:
        """Base URL for API calls."""
        ...

    @property
    def host_base(self) -> str:
        """Base URL for host pages (release pages, etc.)."""
        ...

    def build_api_url(self, repo: str, *parts: str) -> str:
        """Build an API URL for the given repo and path parts."""
        ...

    def build_download_url(self, repo: str, tag: str, asset_name: str) -> str:
        """Build a download URL for a release asset."""
        ...

    def build_host_url(self, repo: str, *parts: str) -> str:
        """Build a host page URL (e.g., release tag page)."""
        ...

    @property
    def default_headers(self) -> Headers:
        """Default headers to include in API requests."""
        ...


@dataclass(frozen=True)
class ForkConfig:
    repo: str
    archive_format: str
    # Version parsing
    version_pattern: str = ""
    version_prefix: str = ""
    is_ge_proton: bool = False
    # Link naming suffixes
    link_names: tuple[str, str, str] = ("", "", "")
    # Tag prefixes to skip during discovery
    skip_prefixes: frozenset[str] = frozenset()
    # Asset filename template
    asset_template: str = "{tag}.tar.gz"
    # Directory name templates to try when extracting (in priority order)
    dir_name_templates: tuple[str, ...] = ("{tag}",)
    # Directory-name validation patterns (a directory must match one to be a candidate)
    dir_name_patterns: tuple[str, ...] = ()
    # Platform type: "github" or "forgejo"
    platform: str = "github"


@dataclass
class SymlinkSpec:
    link_path: Path
    target_path: Path


# Now that SymlinkSpec is defined, we can define the list type alias
LinkSpecList = list[SymlinkSpec]


@dataclass
class HttpResponse:
    """Result of an HTTP request.

    Attributes:
        status: HTTP status code
        headers: Response headers with lowercase keys
        body: Decoded response body (empty for HEAD requests)
        final_url: URL after following redirects
    """

    status: int
    headers: dict[str, str] = field(default_factory=dict)
    body: str = ""
    final_url: str = ""


class NetworkClientProtocol(Protocol):
    """HTTP GET/HEAD with timeout. 4xx/5xx returned, not raised; NetworkError on connection failure."""

    timeout: int

    def get(self, url: str, headers: Headers | None = None) -> HttpResponse: ...

    def head(self, url: str, headers: Headers | None = None) -> HttpResponse: ...


class FileSystemClientProtocol(Protocol):
    """Filesystem operations; failing ops raise LinkManagementError."""

    def exists(self, path: Path) -> bool: ...

    def is_dir(self, path: Path) -> bool: ...

    def is_symlink(self, path: Path) -> bool: ...

    def mkdir(
        self, path: Path, parents: bool = False, exist_ok: bool = False
    ) -> None: ...

    def write(self, path: Path, data: bytes) -> None: ...

    def read(self, path: Path) -> bytes: ...

    def size(self, path: Path) -> int: ...

    def mtime(self, path: Path) -> float: ...

    def symlink_to(
        self, link_path: Path, target_path: Path, target_is_directory: bool = True
    ) -> None: ...

    def resolve(self, path: Path) -> Path: ...

    def unlink(self, path: Path) -> None: ...

    def rmtree(self, path: Path) -> None: ...

    def iterdir(self, path: Path) -> Iterator[Path]: ...


# Constants
DEFAULT_TIMEOUT = 30
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
)
GITHUB_URL_PATTERN = r"/releases/tag/([^/?#]+)"

# Constants for ProtonGE forks
FORKS: dict[ForkName, ForkConfig] = {
    ForkName.GE_PROTON: ForkConfig(
        repo="GloriousEggroll/proton-ge-custom",
        archive_format=".tar.gz",
        version_pattern=r"GE-Proton(\d+)-(\d+)",
        version_prefix="GE-Proton",
        is_ge_proton=True,
        link_names=("GE-Proton", "GE-Proton-Fallback", "GE-Proton-Fallback2"),
        skip_prefixes=frozenset(
            ["EM-", "proton-EM-", "cachyos-", "proton-cachyos-", "dwproton-"]
        ),
        asset_template="{tag}.tar.gz",
        dir_name_templates=("{tag}-x86_64", "{tag}"),
        dir_name_patterns=(r"^GE-Proton\d+-\d+(?:-.*)?$",),
        platform="github",
    ),
    ForkName.PROTON_EM: ForkConfig(
        repo="Etaash-mathamsetty/Proton",
        archive_format=".tar.xz",
        version_pattern=r"(?:proton-)?EM-(\d+)\.(\d+)-(\d+)",
        version_prefix="EM",
        is_ge_proton=False,
        link_names=("Proton-EM", "Proton-EM-Fallback", "Proton-EM-Fallback2"),
        skip_prefixes=frozenset(
            ["GE-Proton", "cachyos-", "proton-cachyos-", "dwproton-"]
        ),
        asset_template="proton-{tag}.tar.xz",
        dir_name_templates=("proton-{tag}", "{tag}"),
        dir_name_patterns=(
            r"^proton-EM-\d+\.\d+-\d+(?:-.*)?$",
            r"^EM-\d+\.\d+-\d+(?:-.*)?$",
        ),
        platform="github",
    ),
    ForkName.CACHYOS: ForkConfig(
        repo="CachyOS/proton-cachyos",
        archive_format=".tar.xz",
        version_pattern=r"(?:proton-)?cachyos-(\d+)\.(\d+)-(\d+)-slr(?:-x86_64)?",
        version_prefix="cachyos",
        is_ge_proton=False,
        link_names=("CachyOS", "CachyOS-Fallback", "CachyOS-Fallback2"),
        skip_prefixes=frozenset(["GE-Proton", "EM-", "proton-EM-", "dwproton-"]),
        asset_template="proton-{tag}-x86_64.tar.xz",
        dir_name_templates=("proton-{tag}-x86_64", "proton-{tag}", "{tag}"),
        dir_name_patterns=(
            r"^proton-cachyos-\d+\.\d+-\d+-slr(?:-x86_64)?(?:-.*)?$",
            r"^cachyos-\d+\.\d+-\d+-slr(?:-.*)?$",
        ),
        platform="github",
    ),
    ForkName.DW_PROTON: ForkConfig(
        repo="dawn-winery/dwproton",
        archive_format=".tar.xz",
        version_pattern=r"dwproton-(\d+)\.(\d+)-(\d+)",
        version_prefix="dwproton",
        is_ge_proton=False,
        link_names=("DW-Proton", "DW-Proton-Fallback", "DW-Proton-Fallback2"),
        skip_prefixes=frozenset(
            ["GE-Proton", "EM-", "cachyos-", "proton-cachyos-", "proton-EM-"]
        ),
        asset_template="{tag}-x86_64.tar.xz",
        dir_name_templates=("{tag}-x86_64", "{tag}"),
        dir_name_patterns=(r"^dwproton-\d+\.\d+-\d+-x86_64(?:-.*)?$",),
        platform="forgejo",
    ),
}
DEFAULT_FORK: ForkName = ForkName.GE_PROTON
