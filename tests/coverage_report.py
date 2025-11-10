#!/usr/bin/env python3

import json
import os
import shutil
import subprocess
from pathlib import Path

from coverage import Coverage

# If auto-detection fails, set MODULE_TO_COVER to your actual module path:
# Examples: "src/protonfetcher", "proton_fetcher", or "protonfetcher.py"
MODULE_TO_COVER = "protonfetcher"  # Will be auto-detected if this doesn't exist

# Paths relative to script location
SCRIPT_DIR = os.path.dirname(__file__)
PROJECT_ROOT = os.path.abspath(SCRIPT_DIR + "/..")
COV_DIR = os.path.join(PROJECT_ROOT, "coverage_reports")
COMBINED_DIR = os.path.join(COV_DIR, "combined")
DATA_DIR = os.path.join(COV_DIR, "data")


def progress_bar(current, total, prefix="Progress"):
    """Print progress bar without overwriting (each update on new line)"""
    percent = (current / total) * 100
    filled = int(percent // 2)
    bar = "█" * filled + "-" * (50 - filled)
    line = f"{prefix}: [{bar}] {percent:6.1f}%"
    print(line, flush=True)
    if current == total:
        print()  # Final newline


def detect_module_path():
    """Auto-detect the module path using common project structures"""
    global MODULE_TO_COVER

    # If the configured path exists, use it
    direct_path = Path(PROJECT_ROOT) / MODULE_TO_COVER
    if direct_path.exists():
        print(f"✅ Using configured module path: {direct_path}")
        return direct_path

    print(f"⚠️  Configured module path not found: {direct_path}")
    print("🔍 Auto-detecting module...")

    # Common patterns to try
    patterns = [
        "src/" + MODULE_TO_COVER,  # src layout
        MODULE_TO_COVER.replace("-", "_"),  # hyphen to underscore
        MODULE_TO_COVER.replace("_", "-"),  # underscore to hyphen
        MODULE_TO_COVER + ".py",  # single file module
        "src/" + MODULE_TO_COVER.replace("-", "_"),  # src layout with underscore
    ]

    # Look for Python packages (directories with __init__.py)
    for pattern in patterns:
        path = Path(PROJECT_ROOT) / pattern
        if path.exists():
            if path.is_dir() and (path / "__init__.py").exists():
                print(f"✅ Found Python package: {path}")
                MODULE_TO_COVER = pattern
                return path
            elif path.is_file() and path.suffix == ".py":
                print(f"✅ Found Python module file: {path}")
                MODULE_TO_COVER = pattern
                return path

    # Last resort: search for any Python files in project root or src/
    search_dirs = [Path(PROJECT_ROOT), Path(PROJECT_ROOT) / "src"]
    python_files = []

    for search_dir in search_dirs:
        if search_dir.exists():
            python_files.extend(search_dir.glob("*.py"))
            python_files.extend(search_dir.glob("*/*.py"))  # One level deep

    if python_files:
        print("⚠️  No clear module found. Found Python files:")
        for f in python_files[:5]:  # Show first 5
            print(f"   - {f.relative_to(PROJECT_ROOT)}")
        if len(python_files) > 5:
            print(f"   ... and {len(python_files) - 5} more")

        # Auto-pick the most likely candidate
        most_likely = python_files[0]
        print(f"\n❓ Guessing module is: {most_likely.relative_to(PROJECT_ROOT)}")
        response = input("Use this? (y/n) [y]: ").strip().lower()
        if response in ("", "y", "yes"):
            MODULE_TO_COVER = str(most_likely.relative_to(PROJECT_ROOT))
            return most_likely

    print("❌ Could not auto-detect module. Please set MODULE_TO_COVER manually.")
    return None


def get_coverage_source_arg(module_path):
    """Get the appropriate --cov argument based on module type"""
    if module_path.is_file():
        # For single-file modules, use the filename without .py extension
        return module_path.stem
    else:
        # For package directories, use the relative path from project root
        return str(module_path.relative_to(PROJECT_ROOT))


def run_test_with_unique_datafile(test_file, cov_source):
    """Run a single test file and save coverage data to a unique file"""
    test_name = Path(test_file).stem
    data_file = os.path.join(DATA_DIR, f".coverage.{test_name}")

    if os.path.exists(data_file):
        os.remove(data_file)

    env = os.environ.copy()
    env["COVERAGE_FILE"] = data_file

    # Run from PROJECT_ROOT with adjusted test path
    test_path = os.path.join("tests", test_file)

    cmd = [
        "pytest",
        test_path,
        f"--cov={cov_source}",
        "--cov-report=",
    ]

    result = subprocess.run(
        cmd, cwd=PROJECT_ROOT, capture_output=True, text=True, env=env
    )
    success = result.returncode in (0, 5)

    if not success:
        print(f"⚠️  Failed: {test_file}")
        if result.stderr:
            print(f"  Error: {result.stderr[:200]}...")

    return success, data_file, test_name


def collect_coverage_data(cov_source):
    """Run all test files and collect individual coverage data"""
    if os.path.exists(COV_DIR):
        shutil.rmtree(COV_DIR)

    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(COMBINED_DIR, exist_ok=True)

    test_files = [
        f for f in os.listdir(SCRIPT_DIR) if f.startswith("test_") and f.endswith(".py")
    ]

    if not test_files:
        print("❌ No test files found in ./tests/")
        return None, []

    print(f"📊 Running {len(test_files)} test files and collecting coverage data...\n")

    coverage_files = []
    success_count = 0

    for i, test_file in enumerate(test_files, 1):
        progress_bar(i, len(test_files), prefix=f"Testing {test_file}")
        success, data_file, test_name = run_test_with_unique_datafile(
            test_file, cov_source
        )
        if success:
            success_count += 1
            coverage_files.append((data_file, test_name))

    print(f"\n✅ Successful: {success_count}/{len(test_files)}")
    return coverage_files, test_files


def analyze_per_test_file_coverage(coverage_files):
    """Analyze which lines each test file covers"""
    module_path = detect_module_path()

    if not module_path or not module_path.exists():
        print("   ❌ Cannot proceed: module path not found")
        return {}, []

    # Get all Python files in the module
    python_files = []

    if module_path.is_dir():
        # It's a package: collect all .py files recursively
        for py_file in module_path.rglob("*.py"):
            if py_file.is_file():
                rel_path = py_file.relative_to(PROJECT_ROOT)
                python_files.append(str(rel_path))
    else:
        # It's a single file module
        python_files = [str(module_path.relative_to(PROJECT_ROOT))]

    print(f"   Found {len(python_files)} Python files to analyze")

    test_coverage_map = {}

    for data_file, test_name in coverage_files:
        cov = Coverage(data_file=data_file)
        cov.load()

        test_coverage_map[test_name] = {}

        for py_file in python_files:
            try:
                abs_path = Path(PROJECT_ROOT) / py_file
                analysis = cov.analysis2(str(abs_path))
                executed_lines = set(analysis[1])
                if executed_lines:
                    test_coverage_map[test_name][py_file] = executed_lines
            except Exception:
                # Debug output for individual file analysis failures
                # print(f"   Debug: {test_name} - {py_file}: {str(e)[:100]}")
                pass

    return test_coverage_map, python_files


def generate_combined_report(
    test_coverage_map, python_files, original_test_files, cov_source
):
    """Generate combined HTML report with per-test-file breakdown"""

    # Step 1: Create combined coverage data by running all tests
    print("\n📈 Generating baseline combined coverage data...")
    combined_data_file = os.path.join(DATA_DIR, ".coverage.combined")

    if os.path.exists(combined_data_file):
        os.remove(combined_data_file)

    env = os.environ.copy()
    env["COVERAGE_FILE"] = combined_data_file

    # Run from PROJECT_ROOT with adjusted test paths
    test_paths = [os.path.join("tests", f) for f in original_test_files]

    cmd = [
        "pytest",
        *test_paths,
        f"--cov={cov_source}",
        "--cov-report=",
    ]

    result = subprocess.run(
        cmd, cwd=PROJECT_ROOT, capture_output=True, text=True, env=env
    )

    if result.returncode not in (0, 5):
        print("❌ Failed to generate combined coverage data")
        if result.stderr:
            print(f"Error: {result.stderr[:300]}")
        return

    # Step 2: Generate HTML report
    print("🔧 Generating HTML report...")

    cov = Coverage(data_file=combined_data_file)
    cov.load()

    # Verify we have data before generating report
    data = cov.get_data()
    measured_files = data.measured_files()

    if not measured_files:
        print("❌ No coverage data collected. This usually means:")
        print("   - The module wasn't imported during tests")
        print("   - The --cov argument doesn't match the module structure")
        print(f"   Current --cov argument: {cov_source}")
        print(f"   Module path: {MODULE_TO_COVER}")
        return

    # Configure HTML reporting options
    cov.set_option("html:directory", COMBINED_DIR)
    cov.set_option("html:show_contexts", False)

    # Generate the HTML report
    cov.html_report()

    # Step 3: Create supplemental summary page
    print("📊 Creating per-test-file summary...")

    breakdown_data = {
        "test_files": list(test_coverage_map.keys()),
        "python_files": python_files,
        "coverage_by_test": {
            test: {py_file: list(lines) for py_file, lines in coverage.items()}
            for test, coverage in test_coverage_map.items()
        },
        "file_summary": {},
    }

    # Calculate summary statistics per Python file
    for py_file in python_files:
        covering_tests = []
        total_covered_lines = set()

        for test_name, coverage in test_coverage_map.items():
            if py_file in coverage:
                covering_tests.append(test_name)
                total_covered_lines.update(coverage[py_file])

        try:
            abs_path = Path(PROJECT_ROOT) / py_file
            analysis = cov.analysis2(str(abs_path))
            all_lines = set(analysis[1]) | set(analysis[2])
            coverage_percent = (
                (len(total_covered_lines) / len(all_lines) * 100) if all_lines else 0
            )
        except Exception:
            coverage_percent = 0
            all_lines = set()

        if all_lines:
            breakdown_data["file_summary"][py_file] = {
                "covering_tests": covering_tests,
                "coverage_percent": round(coverage_percent, 1),
                "covered_lines": len(total_covered_lines),
                "total_lines": len(all_lines),
            }

    # Save breakdown data as JSON
    breakdown_file = os.path.join(COMBINED_DIR, "per_test_file_coverage.json")
    with open(breakdown_file, "w") as f:
        json.dump(breakdown_data, f, indent=2)

    # Create a custom HTML summary page
    summary_html = os.path.join(COMBINED_DIR, "test_file_summary.html")

    html_content = f"""<!DOCTYPE html>
<html>
<head>
    <title>Per-Test-File Coverage Summary</title>
    <meta charset="utf-8">
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; margin: 20px; background: #f5f5f5; }}
        .container {{ max-width: 1200px; margin: 0 auto; background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        h1 {{ color: #333; }}
        table {{ border-collapse: collapse; width: 100%; margin-top: 20px; }}
        th, td {{ border: 1px solid #ddd; padding: 12px; text-align: left; }}
        th {{ background-color: #4CAF50; color: white; font-weight: 600; }}
        tr:nth-child(even) {{ background-color: #f9f9f9; }}
        tr:hover {{ background-color: #f1f1f1; }}
        .file-name {{ font-family: monospace; font-weight: 500; }}
        .coverage-bar {{ display: inline-block; width: 100px; height: 20px; background: #e0e0e0; border-radius: 4px; overflow: hidden; vertical-align: middle; margin-right: 10px; }}
        .coverage-fill {{ height: 100%; background: linear-gradient(90deg, #4CAF50, #81C784); transition: width 0.3s; }}
        .coverage-text {{ font-weight: 600; color: #333; }}
        .test-tag {{ display: inline-block; background: #e3f2fd; color: #1976d2; padding: 4px 8px; margin: 2px; border-radius: 4px; font-size: 0.85em; font-family: monospace; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>Per-Test-File Coverage Summary</h1>
        <p>This report shows which test files contribute to the coverage of each Python file in <code>{MODULE_TO_COVER}</code>.</p>
        <p><strong>💡 Tip:</strong> View the main <a href="index.html">coverage report</a> for detailed line-by-line coverage.</p>
        
        <table>
            <tr>
                <th>Python File</th>
                <th>Coverage %</th>
                <th>Lines Covered</th>
                <th>Test Files That Cover It</th>
            </tr>
"""

    # Sort files by coverage percentage (descending)
    sorted_files = sorted(
        breakdown_data["file_summary"].items(),
        key=lambda x: x[1]["coverage_percent"],
        reverse=True,
    )

    for py_file, summary in sorted_files:
        coverage_pct = summary["coverage_percent"]
        covered = summary["covered_lines"]
        total = summary["total_lines"]
        tests = summary["covering_tests"]

        # Create visual coverage bar
        bar_width = int(coverage_pct * 0.8)
        coverage_bar = f'<div class="coverage-bar"><div class="coverage-fill" style="width: {bar_width}px;"></div></div>'

        # Create test file tags
        test_tags = (
            "".join(f'<span class="test-tag">{test}</span>' for test in tests)
            if tests
            else '<em style="color: #999;">No coverage</em>'
        )

        html_content += f"""
            <tr>
                <td class="file-name">{py_file}</td>
                <td>{coverage_bar}<span class="coverage-text">{coverage_pct:.1f}%</span></td>
                <td>{covered}/{total}</td>
                <td>{test_tags}</td>
            </tr>
        """

    html_content += """
        </table>
        <p style="margin-top: 30px; font-size: 0.9em; color: #666;">
            Generated with per-test-file coverage analysis. 
            Raw data available in <a href="per_test_file_coverage.json">JSON format</a>.
        </p>
    </div>
</body>
</html>
"""

    with open(summary_html, "w") as f:
        f.write(html_content)

    print(f"\n🎉 Combined report generated: {COMBINED_DIR}/index.html")
    print(f"📊 Per-test-file summary: {summary_html}")
    print("💡 View the main coverage report for detailed line-by-line coverage!")


def main():
    # Step 0: Auto-detect module path
    module_path = detect_module_path()
    if not module_path:
        print("❌ Cannot proceed without valid module path. Exiting.")
        return

    # Determine the correct --cov argument
    cov_source = get_coverage_source_arg(module_path)
    print(f"📍 Using coverage source: {cov_source}")

    # Step 1: Collect coverage data from each test file
    coverage_files, test_files = collect_coverage_data(cov_source)

    if not coverage_files:
        return

    # Step 2: Analyze coverage by test file
    coverage_map, python_files = analyze_per_test_file_coverage(coverage_files)

    # Step 3: Generate combined report with breakdown
    generate_combined_report(coverage_map, python_files, test_files, cov_source)


if __name__ == "__main__":
    main()
