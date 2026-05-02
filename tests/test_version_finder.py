"""Tests for version_finder submodule.

Tests version discovery, fork-specific filtering, and deduplication
as standalone functions (no LinkManager dependency).
"""

from pathlib import Path

from protonfetcher.common import ForkName
from protonfetcher.filesystem import FileSystemClient
from protonfetcher.version_finder import (
    _deduplicate_candidates,
    _get_tag_name,
    _is_valid_proton_directory,
    _should_skip_directory,
    find_version_candidates,
)


class TestGetTagName:
    """Test _get_tag_name helper."""

    def test_ge_proton_no_prefix(self, tmp_path: Path) -> None:
        """GE-Proton directories keep their name."""
        entry = tmp_path / "GE-Proton10-20"
        assert _get_tag_name(entry, ForkName.GE_PROTON) == "GE-Proton10-20"

    def test_proton_em_strips_prefix(self, tmp_path: Path) -> None:
        """Proton-EM directories with 'proton-' prefix get it stripped."""
        entry = tmp_path / "proton-EM-10.0-30"
        assert _get_tag_name(entry, ForkName.PROTON_EM) == "EM-10.0-30"

    def test_proton_em_no_prefix(self, tmp_path: Path) -> None:
        """Proton-EM directories without prefix keep their name."""
        entry = tmp_path / "EM-10.0-30"
        assert _get_tag_name(entry, ForkName.PROTON_EM) == "EM-10.0-30"

    def test_cachyos_strips_prefix_and_suffix(self, tmp_path: Path) -> None:
        """CachyOS directories with 'proton-' prefix and '-x86_64' suffix."""
        entry = tmp_path / "proton-cachyos-10.0-20260207-slr-x86_64"
        assert _get_tag_name(entry, ForkName.CACHYOS) == "cachyos-10.0-20260207-slr"

    def test_dw_proton_strips_suffix(self, tmp_path: Path) -> None:
        """DW-Proton directories with '-x86_64' suffix."""
        entry = tmp_path / "dwproton-10.0-26-x86_64"
        assert _get_tag_name(entry, ForkName.DW_PROTON) == "dwproton-10.0-26"


class TestShouldSkipDirectory:
    """Test _should_skip_directory helper."""

    def test_skips_other_fork_prefix(self) -> None:
        """Directories with other fork's prefix are skipped."""
        assert _should_skip_directory("EM-10.0-30", ForkName.GE_PROTON) is True
        assert (
            _should_skip_directory("cachyos-10.0-20260207-slr", ForkName.GE_PROTON)
            is True
        )

    def test_no_skip_for_matching_prefix(self) -> None:
        """GE-Proton directories are not skipped for GE-Proton fork."""
        assert _should_skip_directory("GE-Proton10-20", ForkName.GE_PROTON) is False


class TestIsValidProtonDirectory:
    """Test _is_valid_proton_directory helper."""

    def test_ge_proton_valid(self, tmp_path: Path) -> None:
        """Valid GE-Proton directory names."""
        assert (
            _is_valid_proton_directory(tmp_path / "GE-Proton10-20", ForkName.GE_PROTON)
            is True
        )
        assert (
            _is_valid_proton_directory(tmp_path / "GE-Proton9-15", ForkName.GE_PROTON)
            is True
        )
        assert (
            _is_valid_proton_directory(
                tmp_path / "GE-Proton10-20-RC1", ForkName.GE_PROTON
            )
            is True
        )

    def test_ge_proton_invalid(self, tmp_path: Path) -> None:
        """Invalid GE-Proton directory names."""
        assert (
            _is_valid_proton_directory(tmp_path / "LegacyRuntime", ForkName.GE_PROTON)
            is False
        )
        assert (
            _is_valid_proton_directory(tmp_path / "SomeOtherDir", ForkName.GE_PROTON)
            is False
        )
        assert (
            _is_valid_proton_directory(tmp_path / "EM-10.0-30", ForkName.GE_PROTON)
            is False
        )

    def test_proton_em_valid(self, tmp_path: Path) -> None:
        """Valid Proton-EM directory names."""
        assert (
            _is_valid_proton_directory(tmp_path / "EM-10.0-30", ForkName.PROTON_EM)
            is True
        )
        assert (
            _is_valid_proton_directory(
                tmp_path / "proton-EM-10.0-30", ForkName.PROTON_EM
            )
            is True
        )
        assert (
            _is_valid_proton_directory(
                tmp_path / "proton-EM-10.0-36-HDRTEST", ForkName.PROTON_EM
            )
            is True
        )

    def test_cachyos_valid(self, tmp_path: Path) -> None:
        """Valid CachyOS directory names."""
        assert (
            _is_valid_proton_directory(
                tmp_path / "cachyos-10.0-20260207-slr", ForkName.CACHYOS
            )
            is True
        )
        assert (
            _is_valid_proton_directory(
                tmp_path / "proton-cachyos-10.0-20260207-slr-x86_64", ForkName.CACHYOS
            )
            is True
        )

    def test_dw_proton_valid(self, tmp_path: Path) -> None:
        """Valid DW-Proton directory names."""
        assert (
            _is_valid_proton_directory(
                tmp_path / "dwproton-10.0-26-x86_64", ForkName.DW_PROTON
            )
            is True
        )


class TestFindVersionCandidates:
    """Test find_version_candidates function."""

    def test_find_version_candidates_all_forks(
        self,
        installed_proton_versions: list[Path],
        tmp_path: Path,
        fork: ForkName,
    ) -> None:
        """Test finding and parsing version directories for all forks."""
        extract_dir = tmp_path / "compatibilitytools.d"
        fs = FileSystemClient()

        candidates = find_version_candidates(
            extract_dir=extract_dir,
            fork=fork,
            file_system=fs,
        )

        assert len(candidates) == 3
        versions = [c[0] for c in candidates]
        assert len(versions) == 3

    def test_find_version_candidates_proton_em(
        self,
        tmp_path: Path,
    ) -> None:
        """Test finding and parsing Proton-EM version directories."""
        extract_dir = tmp_path / "compatibilitytools.d"
        extract_dir.mkdir()

        for name in ["EM-10.0-30", "EM-10.0-29", "EM-10.0-28"]:
            (extract_dir / name).mkdir()

        fs = FileSystemClient()

        candidates = find_version_candidates(
            extract_dir=extract_dir,
            fork=ForkName.PROTON_EM,
            file_system=fs,
        )

        assert len(candidates) == 3

    def test_skip_other_fork_directories(
        self,
        tmp_path: Path,
    ) -> None:
        """Test that directories from other fork are skipped."""
        extract_dir = tmp_path / "compatibilitytools.d"
        extract_dir.mkdir()

        (extract_dir / "GE-Proton10-20").mkdir()
        (extract_dir / "GE-Proton10-19").mkdir()
        (extract_dir / "EM-10.0-30").mkdir()

        fs = FileSystemClient()

        ge_candidates = find_version_candidates(
            extract_dir=extract_dir,
            fork=ForkName.GE_PROTON,
            file_system=fs,
        )

        em_candidates = find_version_candidates(
            extract_dir=extract_dir,
            fork=ForkName.PROTON_EM,
            file_system=fs,
        )

        assert len(ge_candidates) == 2
        assert len(em_candidates) == 1

    def test_skip_non_proton_directories(
        self,
        tmp_path: Path,
    ) -> None:
        """Test that non-Proton directories are skipped."""
        extract_dir = tmp_path / "compatibilitytools.d"
        extract_dir.mkdir()

        (extract_dir / "GE-Proton10-20").mkdir()
        (extract_dir / "LegacyRuntime").mkdir()
        (extract_dir / "SomeOtherDir").mkdir()

        fs = FileSystemClient()

        candidates = find_version_candidates(
            extract_dir=extract_dir,
            fork=ForkName.GE_PROTON,
            file_system=fs,
        )

        assert len(candidates) == 1
        assert candidates[0][1].name == "GE-Proton10-20"

    def test_find_version_candidates_with_special_build_suffixes(
        self,
        tmp_path: Path,
    ) -> None:
        """Test that Proton-EM directories with special build suffixes are recognized.

        Regression test for directories like proton-EM-10.0-36-HDRTEST
        not being recognized as valid Proton-EM directories.
        """
        extract_dir = tmp_path / "compatibilitytools.d"
        extract_dir.mkdir()

        for name in [
            "proton-EM-10.0-36-HDRTEST",
            "proton-EM-10.0-34",
            "proton-EM-10.0-33",
            "EM-10.0-30",
        ]:
            (extract_dir / name).mkdir()

        fs = FileSystemClient()

        candidates = find_version_candidates(
            extract_dir=extract_dir,
            fork=ForkName.PROTON_EM,
            file_system=fs,
        )

        assert len(candidates) == 4

        candidate_names = [c[1].name for c in candidates]
        assert "proton-EM-10.0-36-HDRTEST" in candidate_names

        hdrtest_candidate = next(
            c for c in candidates if c[1].name == "proton-EM-10.0-36-HDRTEST"
        )
        assert hdrtest_candidate[0][0] == "EM"
        assert hdrtest_candidate[0][1] == 10
        assert hdrtest_candidate[0][2] == 0
        assert hdrtest_candidate[0][3] == 36


class TestDeduplicateCandidates:
    """Test _deduplicate_candidates function."""

    def test_prefers_standard_naming(self, tmp_path: Path) -> None:
        """Test that duplicate versions prefer standard naming over prefixed."""
        extract_dir = tmp_path / "compatibilitytools.d"
        extract_dir.mkdir()

        standard = extract_dir / "EM-10.0-30"
        prefixed = extract_dir / "proton-EM-10.0-30"
        standard.mkdir()
        prefixed.mkdir()

        fs = FileSystemClient()

        candidates = find_version_candidates(
            extract_dir=extract_dir,
            fork=ForkName.PROTON_EM,
            file_system=fs,
        )

        deduped = _deduplicate_candidates(candidates)

        assert len(deduped) == 1
        assert deduped[0][1].name == "EM-10.0-30"

    def test_no_duplicates_unchanged(self, tmp_path: Path) -> None:
        """Test that non-duplicate candidates pass through unchanged."""
        v1 = tmp_path / "GE-Proton10-20"
        v2 = tmp_path / "GE-Proton10-19"
        v1.mkdir()
        v2.mkdir()

        fs = FileSystemClient()

        candidates = find_version_candidates(
            extract_dir=tmp_path,
            fork=ForkName.GE_PROTON,
            file_system=fs,
        )

        deduped = _deduplicate_candidates(candidates)
        assert len(deduped) == len(candidates)
