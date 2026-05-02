"""
Test data fixture for the ProtonFetcher test suite.

Contains:
- Centralized test data fixture
"""

from typing import Any

import pytest

from protonfetcher.common import ForkName

# =============================================================================
# Centralized Test Data
# =============================================================================


@pytest.fixture
def test_data() -> dict[str, Any]:
    """
    Centralized test data for all test scenarios.

    Usage:
        def test_fork_configuration(test_data: dict[str, Any], fork: ForkName):
            repo = test_data["FORKS"][fork]["repo"]
    """
    return {
        "FORKS": {
            ForkName.GE_PROTON: {
                "repo": "GloriousEggroll/proton-ge-custom",
                "example_tag": "GE-Proton10-20",
                "example_asset": "GE-Proton10-20.tar.gz",
                "archive_format": ".tar.gz",
            },
            ForkName.PROTON_EM: {
                "repo": "Etaash-mathamsetty/Proton",
                "example_tag": "EM-10.0-30",
                "example_asset": "proton-EM-10.0-30.tar.xz",
                "archive_format": ".tar.xz",
            },
            ForkName.CACHYOS: {
                "repo": "CachyOS/proton-cachyos",
                "example_tag": "cachyos-10.0-20260207-slr",
                "example_asset": "proton-cachyos-10.0-20260207-slr-x86_64.tar.xz",
                "archive_format": ".tar.xz",
            },
            ForkName.DW_PROTON: {
                "repo": "dawn-winery/dwproton",
                "example_tag": "dwproton-10.0-26",
                "example_asset": "dwproton-10.0-26-x86_64.tar.xz",
                "archive_format": ".tar.xz",
            },
        },
        "CLI_OUTPUTS": {
            "success": "Success",
            "error_prefix": "Error:",
        },
        "GITHUB_API": {
            "rate_limit_message": "API rate limit exceeded",
            "not_found": "404",
        },
    }
