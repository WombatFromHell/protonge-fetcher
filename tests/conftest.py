"""
Shared pytest configuration for ProtonFetcher test suite.

Thin import layer that re-exports fixtures, factories, and test data
from modular submodules.
"""

import sys
from pathlib import Path

# Add src directory to Python path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# Re-export all fixtures, factories, and test data
from tests.data import *  # noqa: F401, F403
from tests.factories import *  # noqa: F401, F403
from tests.fixtures import *  # noqa: F401, F403
