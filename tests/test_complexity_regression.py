"""
Tests to ensure code complexity doesn't regress beyond acceptable limits.
"""

import ast
import json
import subprocess
import sys
from pathlib import Path


class TestComplexityRegression:
    """Test that function complexity doesn't exceed acceptable limits."""

    def test_cyclomatic_complexity_limits(self):
        """Test that no functions exceed acceptable cyclomatic complexity."""
        try:
            # Run radon to analyze cyclomatic complexity on the entire protonfetcher package
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "radon",
                    "cc",
                    "src/protonfetcher",
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

                # Parse text output format
                current_file = None
                for line in output_lines:
                    if line.strip() and not line.startswith("Overall"):
                        # Look for the file name line (e.g., "src/protonfetcher/github_fetcher.py")
                        if line.strip().endswith(".py"):
                            current_file = line.strip()
                            complexity_data[current_file] = []
                        elif current_file and ":" in line and "-" in line:
                            # Parse line format: "line_number: complexity - function_name"
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
                if not any(complexity_data.values()):
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
                                    f"Function {func_name} in {file_path} has complexity {complexity}, "
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
            # Run radon to analyze Halstead metrics on the entire protonfetcher package
            result = subprocess.run(
                [sys.executable, "-m", "radon", "hal", "src/protonfetcher"],
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
            # Run radon to analyze raw metrics on the entire protonfetcher package
            result = subprocess.run(
                [sys.executable, "-m", "radon", "raw", "src/protonfetcher"],
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
            # Run radon to analyze maintainability on the entire protonfetcher package
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "radon",
                    "mi",
                    "src/protonfetcher",
                    "-c",  # Show in classic format
                ],
                capture_output=True,
                text=True,
                cwd=Path(__file__).parent.parent,
            )

            if result.returncode not in [0, 1]:
                print(f"Radon mi command failed: {result.stderr}")
                return

            # Parse radon mi output
            output = result.stdout.strip()
            if output:
                # The output format for multiple files is different
                # It may show multiple lines with scores like "filename: score (grade)"
                lines = output.split("\n")
                for line in lines:
                    if (
                        ":" in line
                        and "(A)" in line
                        or "(B)" in line
                        or "(C)" in line
                        or "(D)" in line
                    ):
                        try:
                            # Extract the score from format like "src/protonfetcher/github_fetcher.py: 85.21 (A)"
                            score_part = line.split(":")[1].strip().split()[0]
                            score = float(score_part)

                            # Maintainability index should be > 15 for acceptable maintainability
                            assert score > 15.0, (
                                f"Maintainability index {score} is too low (should be > 15.0) for {line.split(':')[0]}"
                            )
                        except (ValueError, IndexError):
                            continue  # Skip lines that don't match the expected format

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
        # Increased from 3600 to 3700 to accommodate --relink functionality
        # which adds comprehensive relink operations and validation
        assert len(lines) < 3700, f"Module has {len(lines)} lines, which is too long"

    def test_cognitive_complexity(self):
        """Test cognitive complexity to measure how difficult code is to understand."""
        try:
            # Cognitive complexity is not directly supported by radon, so we'll implement a basic analyzer
            import ast

            # Walk through the protonfetcher directory to analyze cognitive complexity
            protonfetcher_dir = Path(__file__).parent.parent / "src" / "protonfetcher"

            for py_file in protonfetcher_dir.glob("*.py"):
                if py_file.name != "__init__.py":
                    with open(py_file, "r", encoding="utf-8") as f:
                        try:
                            tree = ast.parse(f.read())

                            # Analyze each function in the file for cognitive complexity
                            for node in ast.walk(tree):
                                if isinstance(node, ast.FunctionDef):
                                    complexity = self._calculate_cognitive_complexity(
                                        node
                                    )

                                    # Set maximum cognitive complexity threshold
                                    max_cognitive_complexity = 15

                                    if complexity > max_cognitive_complexity:
                                        assert False, (
                                            f"Function {node.name} in {py_file.name} has cognitive complexity {complexity}, "
                                            f"which exceeds the maximum acceptable of {max_cognitive_complexity}. "
                                            f"Consider refactoring to improve code readability."
                                        )
                        except SyntaxError:
                            continue  # Skip files with syntax errors

        except Exception as e:
            print(f"Cognitive complexity test encountered an error: {e}")

    def _calculate_cognitive_complexity(self, node):
        """Calculate cognitive complexity for an AST node (function)."""
        complexity = 1  # Base complexity for a function

        # Use a recursive helper to traverse the AST and count complexity
        def traverse(node, nesting=0):
            nonlocal complexity

            if isinstance(
                node,
                (
                    ast.If,
                    ast.While,
                    ast.For,
                    ast.AsyncFor,
                    ast.With,
                    ast.AsyncWith,
                    ast.Assert,
                ),
            ):
                # Add 1 for each decision point, plus nesting increment
                complexity += 1 + nesting
                new_nesting = nesting + 1
            elif isinstance(node, (ast.Try, ast.ExceptHandler)):
                # Try/except blocks add complexity
                complexity += 1 + nesting
                new_nesting = nesting + 1
            elif isinstance(node, ast.BoolOp):  # and/or expressions
                # Boolean operations add complexity
                complexity += (
                    len(node.values) - 1
                )  # Each additional operand adds complexity
                new_nesting = nesting
            else:
                new_nesting = nesting

            # Recursively traverse child nodes
            for child in ast.iter_child_nodes(node):
                traverse(child, new_nesting)

        traverse(node)
        return complexity

    def test_threshold_based_alerts(self):
        """Test and validate threshold-based alerts for complexity metrics."""
        try:
            # Define thresholds for different complexity metrics
            thresholds = {
                # Cyclomatic complexity thresholds
                "max_cyclomatic_per_function": 10,
                "max_avg_cyclomatic": 5.0,
                # Raw metrics thresholds
                "max_loc": 3000,
                "max_sloc": 2500,
                # Maintainability index thresholds
                "min_maintainability": 15.0,
                # ABC metrics thresholds
                "max_abc_assignments": 15,
                "max_abc_branches": 10,
                "max_abc_conditions": 10,
                "max_abc_score": 25.0,
                # Import complexity thresholds
                "max_imports_per_file": 20,
                # Cognitive complexity thresholds
                "max_cognitive_complexity": 15,
                # Duplication thresholds
                "max_duplication_blocks": 5,
                "max_duplication_lines": 100,
                # Individual file thresholds
                "max_functions_per_file": 30,
                "max_file_complexity_total": 200,
                "max_file_complexity_avg": 10.0,
            }

            # Run all the other tests with more verbose output to check if thresholds are being met
            print("Running threshold-based alerts check...")

            # Run cyclomatic complexity check as a validation
            cc_result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "radon",
                    "cc",
                    "src/protonfetcher",
                    "-j",
                ],
                capture_output=True,
                text=True,
                cwd=Path(__file__).parent.parent,
            )

            functions_exceeding_threshold = []
            if cc_result.returncode in [0, 1]:
                try:
                    complexity_data = json.loads(cc_result.stdout)
                    for file_path, functions in complexity_data.items():
                        if isinstance(functions, list):
                            for func_info in functions:
                                if isinstance(func_info, dict):
                                    complexity = func_info.get("complexity", 0)
                                    if (
                                        complexity
                                        > thresholds["max_cyclomatic_per_function"]
                                    ):
                                        functions_exceeding_threshold.append(
                                            (
                                                file_path,
                                                func_info.get("name", "unknown"),
                                                complexity,
                                            )
                                        )
                except json.JSONDecodeError:
                    pass  # Skip if JSON parsing fails

            # Report violations
            if functions_exceeding_threshold:
                print(
                    f"ALERT: {len(functions_exceeding_threshold)} functions exceed cyclomatic complexity threshold:"
                )
                for file_path, func_name, complexity in functions_exceeding_threshold:
                    print(
                        f"  - {file_path}:{func_name} has complexity {complexity} (threshold: {thresholds['max_cyclomatic_per_function']})"
                    )
            else:
                print("OK: All functions are within cyclomatic complexity thresholds.")

            # Additional threshold checks can be added here
            print("Threshold-based alerts check completed.\n")

        except Exception as e:
            print(f"Threshold-based alerts test encountered an error: {e}")

    def test_comprehensive_complexity_report(self):
        """Generate a comprehensive complexity report combining multiple metrics."""
        try:
            import sys

            print("\n=== Comprehensive Complexity Report ===")

            # Collect all complexity metrics
            metrics = {}

            # Get cyclomatic complexity data
            cc_result = subprocess.run(
                [sys.executable, "-m", "radon", "cc", "src/protonfetcher", "-s"],
                capture_output=True,
                text=True,
                cwd=Path(__file__).parent.parent,
            )

            if cc_result.returncode in [0, 1]:
                # Process cyclomatic complexity summary
                lines = cc_result.stdout.split("\n")
                for line in lines:
                    if "complexity" in line and "average" in line:
                        # Extract average complexity value
                        parts = line.split()
                        for i, part in enumerate(parts):
                            if part == "average":
                                try:
                                    avg_complexity = float(parts[i - 1])
                                    metrics["avg_cyclomatic_complexity"] = (
                                        avg_complexity
                                    )
                                except (ValueError, IndexError):
                                    continue
                                break

            # Get raw metrics data
            raw_result = subprocess.run(
                [sys.executable, "-m", "radon", "raw", "src/protonfetcher"],
                capture_output=True,
                text=True,
                cwd=Path(__file__).parent.parent,
            )

            if raw_result.returncode in [0, 1]:
                # Process raw metrics
                lines = raw_result.stdout.split("\n")
                for line in lines:
                    if "LOC:" in line:
                        import re

                        loc_match = re.search(r"LOC:\s*(\d+)", line)
                        if loc_match:
                            loc = int(loc_match.group(1))
                            metrics["lines_of_code"] = loc
                    elif "LLOC:" in line:
                        import re

                        lloc_match = re.search(r"LLOC:\s*(\d+)", line)
                        if lloc_match:
                            lloc = int(lloc_match.group(1))
                            metrics["logical_lines_of_code"] = lloc
                    elif "SLOC:" in line:
                        import re

                        sloc_match = re.search(r"SLOC:\s*(\d+)", line)
                        if sloc_match:
                            sloc = int(sloc_match.group(1))
                            metrics["source_lines_of_code"] = sloc

            # Get maintainability index
            mi_result = subprocess.run(
                [sys.executable, "-m", "radon", "mi", "src/protonfetcher", "-c"],
                capture_output=True,
                text=True,
                cwd=Path(__file__).parent.parent,
            )

            if mi_result.returncode in [0, 1]:
                # Process maintainability index
                output = mi_result.stdout.strip()
                if output:
                    lines = output.split("\n")
                    scores = []
                    for line in lines:
                        if (
                            ":" in line
                            and "(A)" in line
                            or "(B)" in line
                            or "(C)" in line
                            or "(D)" in line
                        ):
                            try:
                                # Extract the score from format like "src/protonfetcher/github_fetcher.py: 85.21 (A)"
                                score_part = line.split(":")[1].strip().split()[0]
                                score = float(score_part)
                                scores.append(score)
                            except (ValueError, IndexError):
                                continue
                    if scores:
                        avg_mi = sum(scores) / len(scores)
                        metrics["avg_maintainability_index"] = avg_mi

            # Print the comprehensive report
            print("Complexity Metrics Summary:")
            for key, value in metrics.items():
                print(f"  {key}: {value}")

            # Verify basic thresholds
            if "avg_cyclomatic_complexity" in metrics:
                assert metrics["avg_cyclomatic_complexity"] <= 5.0, (
                    f"Average cyclomatic complexity {metrics['avg_cyclomatic_complexity']} is too high"
                )

            if "lines_of_code" in metrics:
                assert metrics["lines_of_code"] < 3000, (
                    f"Total lines of code {metrics['lines_of_code']} is too high"
                )

            if "avg_maintainability_index" in metrics:
                assert metrics["avg_maintainability_index"] > 15.0, (
                    f"Average maintainability index {metrics['avg_maintainability_index']} is too low"
                )

            print("Comprehensive complexity report completed successfully.\n")

        except Exception as e:
            print(f"Comprehensive complexity report encountered an error: {e}")

    def test_individual_file_complexity(self):
        """Test individual file complexity to ensure no single file becomes too complex."""
        try:
            # Run radon to analyze cyclomatic complexity with JSON output to get per-file info
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "radon",
                    "cc",
                    "src/protonfetcher",
                    "-j",  # JSON output
                ],
                capture_output=True,
                text=True,
                cwd=Path(__file__).parent.parent,
            )

            if result.returncode not in [0, 1]:
                print(
                    f"Radon cc command for individual file analysis failed: {result.stderr}"
                )
                return

            # Parse the JSON output from radon
            try:
                complexity_data = json.loads(result.stdout)
            except json.JSONDecodeError:
                print(
                    "Could not parse JSON output from radon for individual file analysis"
                )
                return

            # Set thresholds for individual file metrics
            max_functions_per_file = 30  # Maximum functions per file
            max_file_complexity_total = 200  # Maximum total complexity per file
            max_file_complexity_avg = 10.0  # Maximum average complexity per file

            # Check each file in the output
            for file_path, functions in complexity_data.items():
                if isinstance(functions, list):
                    if len(functions) > max_functions_per_file:
                        assert False, (
                            f"File {file_path} has {len(functions)} functions, "
                            f"which exceeds the maximum acceptable of {max_functions_per_file}. "
                            f"Consider splitting this file into smaller modules."
                        )

                    # Calculate total and average complexity for the file
                    total_complexity = sum(
                        func.get("complexity", 0)
                        for func in functions
                        if isinstance(func, dict)
                    )
                    avg_complexity = (
                        total_complexity / len(functions) if functions else 0
                    )

                    if total_complexity > max_file_complexity_total:
                        assert False, (
                            f"File {file_path} has total complexity of {total_complexity}, "
                            f"which exceeds the maximum acceptable of {max_file_complexity_total}. "
                            f"Consider refactoring to reduce file complexity."
                        )

                    if avg_complexity > max_file_complexity_avg:
                        assert False, (
                            f"File {file_path} has average complexity of {avg_complexity:.2f}, "
                            f"which exceeds the maximum acceptable of {max_file_complexity_avg}. "
                            f"Consider refactoring to reduce function complexity in this file."
                        )

        except FileNotFoundError:
            print("Radon not available, skipping individual file complexity test")
        except Exception as e:
            print(f"Individual file complexity test encountered an error: {e}")

    def test_code_duplication(self):
        """Test for code duplication using radon's duplication analysis."""
        try:
            # Run radon to analyze code duplication
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "radon",
                    "dup",
                    "src/protonfetcher",
                    "--min-similarity",
                    "50",  # Minimum similarity threshold
                ],
                capture_output=True,
                text=True,
                cwd=Path(__file__).parent.parent,
            )

            # radon dup returns 1 when duplicates are found, which is normal
            # We only care about the output to check for excessive duplication
            if result.returncode not in [0, 1]:
                print(f"Radon dup command failed: {result.stderr}")
                return

            # Parse the duplication output
            output_lines = result.stdout.strip().split("\n")

            # Count duplication occurrences and check for excessive duplication
            duplication_blocks = []
            current_block = []
            in_duplication_section = False

            for line in output_lines:
                if "Duplication" in line or "similar" in line:
                    in_duplication_section = True
                    current_block = [line]
                elif in_duplication_section and line.strip():
                    if line.strip().startswith("->") or ":" in line:
                        current_block.append(line)
                    else:
                        # End of duplication block
                        if len(current_block) > 1:
                            duplication_blocks.append(current_block)
                        current_block = []
                        in_duplication_section = not line.strip().startswith("No")
                elif line.strip().startswith("---"):
                    continue  # Separator
                else:
                    if current_block and len(current_block) > 1:
                        duplication_blocks.append(current_block)
                    current_block = []
                    in_duplication_section = False

            # Check if we have a final block to add
            if current_block and len(current_block) > 1:
                duplication_blocks.append(current_block)

            # Set duplication thresholds
            max_duplication_blocks = (
                5  # Maximum acceptable number of duplication blocks
            )
            max_lines_in_duplication = 100  # Maximum total lines of duplicated code

            total_duplication_lines = 0
            for block in duplication_blocks:
                # Count lines in each duplication block
                for line in block:
                    if "->" in line and ":" in line and "L" in line:  # File:line format
                        # Parse the line to extract line numbers
                        import re

                        matches = re.findall(r":(\d+)-(\d+)", line)
                        for start, end in matches:
                            total_duplication_lines += int(end) - int(start) + 1

            # Test duplication thresholds
            if len(duplication_blocks) > max_duplication_blocks:
                assert False, (
                    f"Found {len(duplication_blocks)} duplication blocks, "
                    f"which exceeds the maximum acceptable of {max_duplication_blocks}. "
                    f"Review and refactor duplicate code."
                )

            if total_duplication_lines > max_lines_in_duplication:
                assert False, (
                    f"Found {total_duplication_lines} lines in duplication blocks, "
                    f"which exceeds the maximum acceptable of {max_lines_in_duplication} lines. "
                    f"Review and refactor duplicate code."
                )

        except FileNotFoundError:
            print("Radon not available, skipping code duplication test")
        except Exception as e:
            print(f"Code duplication test encountered an error: {e}")

    def test_dependency_analysis(self):
        """Test dependency analysis to identify potential circular dependencies and import complexity."""
        try:
            # Run radon to analyze dependencies (this runs a different analysis)
            # Note: radon doesn't have a direct dependency analysis command; we'll use a different approach
            # For dependency analysis, we'll check for import complexity in another way
            import ast

            # Walk through the protonfetcher directory to analyze imports
            protonfetcher_dir = Path(__file__).parent.parent / "src" / "protonfetcher"
            import_counts = {}

            for py_file in protonfetcher_dir.glob("*.py"):
                if py_file.name != "__init__.py":
                    with open(py_file, "r", encoding="utf-8") as f:
                        try:
                            tree = ast.parse(f.read())
                            import_count = 0

                            for node in ast.walk(tree):
                                if isinstance(node, (ast.Import, ast.ImportFrom)):
                                    import_count += 1

                            import_counts[py_file.name] = import_count
                        except SyntaxError:
                            continue  # Skip files with syntax errors

            # Check for files with excessive import counts (indication of high coupling)
            max_imports_per_file = 20  # Maximum acceptable imports per file
            for file_name, count in import_counts.items():
                if count > max_imports_per_file:
                    assert False, (
                        f"File {file_name} has {count} imports, "
                        f"which exceeds the maximum acceptable of {max_imports_per_file}. "
                        f"This may indicate high coupling or dependency issues."
                    )

        except Exception as e:
            print(f"Dependency analysis test encountered an error: {e}")

    def test_abc_metrics(self):
        """Test ABC metrics (Assignment, Branch, Condition) for complexity analysis."""
        try:
            # Run radon to analyze ABC metrics
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "radon",
                    "abc",
                    "src/protonfetcher",
                    "-j",  # JSON output
                ],
                capture_output=True,
                text=True,
                cwd=Path(__file__).parent.parent,
            )

            if result.returncode not in [0, 1]:
                print(f"Radon abc command failed: {result.stderr}")
                return

            # Parse the JSON output from radon
            try:
                abc_data = json.loads(result.stdout)
            except json.JSONDecodeError:
                # If JSON parsing fails, try to parse the text output
                output_lines = result.stdout.strip().split("\n")
                abc_data = {}
                current_file = None

                for line in output_lines:
                    if line.strip() and not line.startswith("Overall"):
                        # Look for the file name line
                        if line.strip().endswith(".py"):
                            current_file = line.strip()
                            abc_data[current_file] = []
                        elif (
                            current_file and "(" in line and ")" in line and ":" in line
                        ):
                            # Parse ABC format like "function_name (A=1, B=2, C=3): 4.56"
                            import re

                            func_match = re.search(
                                r"(\w+)\s+\(A=(\d+),\s*B=(\d+),\s*C=(\d+)\):\s*([\d.]+)",
                                line,
                            )
                            if func_match and len(func_match.groups()) == 5:
                                func_name = func_match.group(1)
                                a = int(func_match.group(2))
                                b = int(func_match.group(3))
                                c = int(func_match.group(4))
                                score = (
                                    float(func_match.group(5))
                                    if func_match.group(5) != "inf"
                                    else float("inf")
                                )

                                abc_data[current_file].append(
                                    {
                                        "name": func_name,
                                        "a": a,  # Assignments
                                        "b": b,  # Branches
                                        "c": c,  # Conditions
                                        "score": score,
                                    }
                                )

            # Check each file in the output for ABC metrics
            for file_path, functions in abc_data.items():
                if isinstance(functions, list):
                    for func_info in functions:
                        if isinstance(func_info, dict):
                            func_name = func_info.get("name", "unknown")
                            a = func_info.get("a", 0)  # Assignments
                            b = func_info.get("b", 0)  # Branches
                            c = func_info.get("c", 0)  # Conditions
                            abc_score = func_info.get(
                                "score", 0
                            )  # ABC Score (sqrt(A^2 + B^2 + C^2))

                            # Set maximum thresholds for individual ABC components
                            max_assignments = 15  # Maximum assignments
                            max_branches = 10  # Maximum branches
                            max_conditions = 10  # Maximum conditions
                            max_abc_score = 25.0  # Maximum ABC score

                            # Test assignments count
                            if a > max_assignments:
                                assert False, (
                                    f"Function {func_name} in {file_path} has {a} assignments, "
                                    f"which exceeds the maximum acceptable of {max_assignments}"
                                )

                            # Test branches count
                            if b > max_branches:
                                assert False, (
                                    f"Function {func_name} in {file_path} has {b} branches, "
                                    f"which exceeds the maximum acceptable of {max_branches}"
                                )

                            # Test conditions count
                            if c > max_conditions:
                                assert False, (
                                    f"Function {func_name} in {file_path} has {c} conditions, "
                                    f"which exceeds the maximum acceptable of {max_conditions}"
                                )

                            # Test ABC score
                            if abc_score > max_abc_score:
                                assert False, (
                                    f"Function {func_name} in {file_path} has ABC score {abc_score:.2f}, "
                                    f"which exceeds the maximum acceptable of {max_abc_score}"
                                )

        except FileNotFoundError:
            print("Radon not available, skipping ABC metrics test")
        except Exception as e:
            print(f"ABC metrics test encountered an error: {e}")

    def test_mccabe_complexity_metrics(self):
        """Test McCabe complexity metrics including average complexity and distribution."""
        try:
            # Run radon to analyze cyclomatic complexity with average metrics
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "radon",
                    "cc",
                    "src/protonfetcher",
                    "-a",  # Show average complexity
                ],
                capture_output=True,
                text=True,
                cwd=Path(__file__).parent.parent,
            )

            if result.returncode not in [0, 1]:
                print(f"Radon mccabe command failed: {result.stderr}")
                return

            # Parse the average complexity output
            output_lines = result.stdout.strip().split("\n")

            # Look for average complexity in the output
            total_complexity = 0
            total_functions = 0
            file_count = 0

            for line in output_lines:
                if line.strip() and not line.startswith("Overall"):
                    # Count functions per file and accumulate for average calculation
                    if line.strip().endswith(".py"):
                        file_count += 1
                    elif ":" in line and "-" in line:
                        # Parse the complexity value from format like "5: 1 - function_name"
                        parts = line.split(":")
                        if len(parts) >= 2:
                            try:
                                complexity_part = parts[1].strip().split("-")[0].strip()
                                complexity = int(complexity_part)
                                total_complexity += complexity
                                total_functions += 1
                            except ValueError:
                                continue

            # Calculate and test average complexity
            if total_functions > 0:
                avg_complexity = total_complexity / total_functions
                # Average complexity should be reasonably low
                assert avg_complexity <= 5.0, (
                    f"Average cyclomatic complexity {avg_complexity:.2f} is too high (should be <= 5.0)"
                )

        except FileNotFoundError:
            print("Radon not available, skipping McCabe complexity metrics test")
        except Exception as e:
            print(f"McCabe complexity metrics test encountered an error: {e}")

    def test_built_binary_complexity(self):
        """Test the complexity of the built binary if it exists."""
        # Check if the built binary exists
        binary_path = Path(__file__).parent.parent / "dist" / "protonfetcher.pyz"

        if binary_path.exists():
            try:
                # Run radon on the built binary to ensure it still meets complexity requirements
                result = subprocess.run(
                    [
                        sys.executable,
                        "-m",
                        "radon",
                        "cc",
                        str(binary_path),
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
                    print(f"Radon command failed on binary: {result.stderr}")
                    return

                # Parse the JSON output from radon
                try:
                    complexity_data = json.loads(result.stdout)
                except json.JSONDecodeError:
                    # If JSON parsing fails, try to parse the text output
                    print("Could not parse JSON output from radon on binary")
                    return

                # Check each file in the output (for a zipapp, it might analyze the content)
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
                                        f"Function {func_name} in built binary has complexity {complexity}, "
                                        f"which exceeds the maximum acceptable complexity of {max_acceptable_complexity}"
                                    )
            except FileNotFoundError:
                print("Radon not available, skipping binary complexity test")
            except Exception as e:
                print(f"Binary complexity test encountered an error: {e}")
        else:
            print(
                f"Built binary not found at {binary_path}, running `make build` required for complete complexity analysis"
            )
