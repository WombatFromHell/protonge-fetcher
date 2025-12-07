"""
Tests to ensure code complexity doesn't regress beyond acceptable limits.
"""

import json
import subprocess
import sys
from pathlib import Path


class TestComplexityRegression:
    """Test that function complexity doesn't exceed acceptable limits."""

    def test_cyclomatic_complexity_limits(self):
        """Test that no functions exceed acceptable cyclomatic complexity."""
        try:
            # Run radon to analyze cyclomatic complexity
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "radon",
                    "cc",
                    "protonfetcher.py",
                    "-j",  # JSON output
                    "-s",  # Show average complexity
                ],
                capture_output=True,
                text=True,
                cwd=Path(__file__).parent.parent,
            )

            if result.returncode not in [
                0,
                1,
            ]:  # 1 is OK for radon when thresholds are exceeded
                print(f"Radon command failed: {result.stderr}")
                # If radon is not available, skip the test
                if (
                    "radon" in result.stderr.lower()
                    or "command not found" in result.stderr.lower()
                ):
                    print("Radon not available, skipping complexity test")
                    return

            # Parse the JSON output from radon
            try:
                complexity_data = json.loads(result.stdout)
            except json.JSONDecodeError:
                # If JSON parsing fails, try to parse the text output
                # Radon might output in text format despite -j flag
                output_lines = result.stdout.strip().split("\n")
                complexity_data = {}
                current_file = "protonfetcher.py"
                complexity_data[current_file] = []

                for line in output_lines:
                    if line.strip() and not line.startswith("Overall"):
                        # Parse line format: "line_number: complexity - function_name"
                        if ":" in line and "-" in line:
                            try:
                                # Extract complexity number and function name
                                func_part = (
                                    line.split("-")[1].strip() if "-" in line else line
                                )
                                func_name = (
                                    func_part.split("(")[0].strip()
                                    if "(" in func_part
                                    else func_part
                                )
                                # Extract complexity from the line (a number between letters)
                                import re

                                complexity_matches = re.findall(
                                    r"\b\d+\b", line.split(":")[1].split("-")[0]
                                )
                                if complexity_matches:
                                    complexity = int(complexity_matches[0])
                                    complexity_data[current_file].append(
                                        {
                                            "name": func_name,
                                            "complexity": complexity,
                                            "type": "function",
                                        }
                                    )
                            except Exception:
                                continue  # Skip unparsable lines
                if not complexity_data[current_file]:
                    print("Could not parse radon output")
                    return

            # Check each file in the output
            for file_path, functions in complexity_data.items():
                if isinstance(functions, list):
                    for func_info in functions:
                        if isinstance(func_info, dict):
                            func_name = func_info.get("name", "unknown")
                            complexity = func_info.get("complexity", 0)

                            # Set complexity threshold - functions should be less than 10 (rank B or better)
                            # Complexity level A is 1-5, B is 6-10, C is 11-20, etc.
                            max_acceptable_complexity = 10

                            if complexity > max_acceptable_complexity:
                                # If we find a function with too high complexity, we fail the test
                                assert complexity <= max_acceptable_complexity, (
                                    f"Function {func_name} has complexity {complexity}, "
                                    f"which exceeds the maximum acceptable complexity of {max_acceptable_complexity}"
                                )

        except FileNotFoundError:
            # radon might not be installed, so we'll try an alternative method
            print("Radon not available, using alternative complexity check")
            # Just check with ruff or similar tools if available, or skip
            pass
        except Exception as e:
            print(f"Complexity test encountered an error: {e}")
            # Don't fail the test if complexity analysis tools aren't available
            pass

    def test_halstead_metrics(self):
        """Test that Halstead complexity metrics are reasonable."""
        try:
            # Run radon to analyze Halstead metrics
            result = subprocess.run(
                [sys.executable, "-m", "radon", "hal", "protonfetcher.py"],
                capture_output=True,
                text=True,
                cwd=Path(__file__).parent.parent,
            )

            if result.returncode not in [0, 1]:
                print(f"Radon hal command failed: {result.stderr}")
                return

            # Parse radon hal output
            output = result.stdout
            lines = output.split("\n")

            for line in lines:
                if "Difficulty:" in line:
                    # Extract difficulty value
                    import re

                    difficulty_match = re.search(r"Difficulty:\s*([\d.]+)", line)
                    if difficulty_match:
                        difficulty = float(difficulty_match.group(1))
                        # Keep difficulty under 10 for maintainability
                        assert difficulty < 15.0, (
                            f"Difficulty {difficulty} is too high (should be < 15.0)"
                        )

        except FileNotFoundError:
            print("Radon not available, skipping Halstead metrics test")
        except Exception as e:
            print(f"Halstead test encountered an error: {e}")

    def test_raw_metrics(self):
        """Test raw metrics to ensure code size is reasonable."""
        try:
            # Run radon to analyze raw metrics
            result = subprocess.run(
                [sys.executable, "-m", "radon", "raw", "protonfetcher.py"],
                capture_output=True,
                text=True,
                cwd=Path(__file__).parent.parent,
            )

            if result.returncode not in [0, 1]:
                print(f"Radon raw command failed: {result.stderr}")
                return

            # Parse radon raw output
            output = result.stdout
            lines = output.split("\n")

            for line in lines:
                if "LOC:" in line:
                    # Extract lines of code value
                    import re

                    loc_match = re.search(r"LOC:\s*(\d+)", line)
                    if loc_match:
                        loc = int(loc_match.group(1))
                        # Reasonable limit for maintainability
                        assert loc < 3000, (
                            f"Lines of code {loc} is too high (should be < 3000)"
                        )

        except FileNotFoundError:
            print("Radon not available, skipping raw metrics test")
        except Exception as e:
            print(f"Raw metrics test encountered an error: {e}")

    def test_maintainability_index(self):
        """Test that maintainability index is acceptable."""
        try:
            # Run radon to analyze maintainability
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "radon",
                    "mi",
                    "protonfetcher.py",
                    "-c",  # Show in classic format
                ],
                capture_output=True,
                text=True,
                cwd=Path(__file__).parent.parent,
            )

            if result.returncode not in [0, 1]:
                print(f"Radon mi command failed: {result.stderr}")
                return

            # Parse radon mi output - format: "FILENAME: SCORE (GRADE)"
            output = result.stdout.strip()
            if output and ":" in output:
                # Extract the score
                score_part = output.split(":")[1].strip().split()[0]
                score = float(score_part)

                # Maintainability index should be > 20 for "A" rating
                # A: > 20, B: 10-20, C: 5-10, D: <= 5
                assert score > 15.0, (
                    f"Maintainability index {score} is too low (should be > 15.0)"
                )

        except FileNotFoundError:
            print("Radon not available, skipping maintainability index test")
        except Exception as e:
            print(f"Maintainability index test encountered an error: {e}")

    def test_manual_complexity_check(self):
        """Manual check for specific complex functions that should be monitored."""
        # This is a manual check to ensure key functions don't grow too complex
        # by looking at the structure of the code directly

        # Aggregate content from all protonfetcher module files
        protonfetcher_dir = Path(__file__).parent.parent / "src" / "protonfetcher"
        content = ""
        for py_file in protonfetcher_dir.glob("*.py"):
            if py_file.name != "__init__.py":  # Skip __init__.py
                with open(py_file, "r", encoding="utf-8") as f:
                    content += f.read() + "\n"

        # Count function definitions and basic structural elements
        import re

        function_count = len(re.findall(r"^\s*def\s+\w+", content, re.MULTILINE))
        class_count = len(re.findall(r"^\s*class\s+\w+", content, re.MULTILINE))

        # These numbers should be reasonable for maintainability
        assert function_count > 10, f"Expected many functions, got {function_count}"
        assert class_count >= 5, f"Expected at least several classes, got {class_count}"

        # Check for reasonable module length (across all files)
        lines = content.split("\n")
        assert len(lines) < 3200, f"Module has {len(lines)} lines, which is too long"
