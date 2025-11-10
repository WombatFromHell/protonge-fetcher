# AGENTS.md

## Overview

This document establishes guidelines for agentic tools (AI assistants, code generation tools, etc.) when interacting with the ProtonFetcher codebase. These rules ensure consistency, maintainability, and proper handling of the project's specific requirements.

## General Principles

- **Preserve Architecture**: Maintain the modular design with clear separation of concerns between NetworkClient, FileSystemClient, Spinner, GitHubReleaseFetcher, and utility functions.

- **Respect Dependencies**: Only use dependencies already present in the project (standard library modules) and system tools (curl, tar). Do not introduce new third-party Python packages.

- **Follow Error Handling Patterns**: Use the custom FetchError exception for all failure cases with detailed error messages and context.

- **Maintain Link Management System**: Preserve the symbolic link management system that provides stable paths to Proton installations.

- Common project tool usage:
  - The test suite can be run with the command: `uv run pytest -v`
  - A code coverage report can be generated with the command: `uv run pytest --cov=protonfetcher --cov-branch --cov-report=term-missing --cov-fail-under=95`
  - Lint checking can be done with the command: `ruff check --select I --fix; ruff format; pyright`
  - Formatting can be done with the command: `ruff format; prettier --cache -c -w *.md`.
  - Formatting for markdown files can be done with the command: `prettier --cache -c -w *.md`
  - Measure Halstead metrics via Radon with the command: `uv run radon hal ./protonfetcher.py`
  - Measure cyclomatic code complexity via Radon using letter grades with the command: `uv run radon cc ./protonfetcher.py -a`

- When running into a test that won't pass, only attempt to fix it 3 times before stopping and prompting the user what to do next. Do not make sweeping changes to the logic of the project without express permission granted by the user to do so.

- Strictly avoid making destructive changes to the project files unless the user has specifically requested it or given permission after being prompted with a confirmation to check if it's okay.

- When significant changes are made to code our lint checking and formatting command, listed above, should be run.

## Code Modification Guidelines

### When Modifying Existing Components

- **NetworkClient**:
  - Maintain timeout handling for all requests
  - Preserve the curl-based implementation with fallbacks
  - Keep the same method signatures and return types
  - Ensure proper error handling for network operations

- **FileSystemClient**:
  - Continue using pathlib for file operations
  - Maintain the abstraction layer for testing purposes
  - Preserve all existing method signatures
  - Ensure consistent error handling across file operations

- **Spinner**:
  - Keep the FPS limiting functionality to prevent excessive terminal updates
  - Maintain clean terminal handling to avoid leftover characters
  - Preserve support for both simple spinning indicators and detailed progress bars
  - Ensure the spinner works correctly with both download and extraction operations

- **GitHubReleaseFetcher**:
  - Maintain support for multiple Proton forks with different naming conventions
  - Preserve the intelligent caching mechanism (skipping downloads if local file matches)
  - Keep the multiple extraction methods (tarfile library and system tar)
  - Ensure proper handling of different archive formats (.tar.gz, .tar.xz)

### When Adding New Features

- **Fork Support**:
  - Add new forks to the FORKS dictionary with appropriate naming conventions
  - Implement fork-specific version parsing in the utility functions
  - Update the link management system to handle new fork types
  - Ensure all existing functionality continues to work with new forks

- **Progress Indication**:
  - Use the existing Spinner class for all progress indication
  - Maintain consistent formatting and display across operations
  - Ensure proper FPS limiting to prevent excessive terminal updates
  - Preserve the ability to disable progress indication when needed

- **Error Handling**:
  - Use the custom FetchError exception for all new error cases
  - Provide detailed error messages with context
  - Implement graceful fallbacks where appropriate
  - Ensure proper logging at appropriate levels

## Link Management System Guidelines

- **Preserve Link Structure**:
  - Maintain the primary link (e.g., `GE-Proton`) pointing to the latest version
  - Keep the fallback links (e.g., `GE-Proton-Fallback`, `GE-Proton-Fallback2`)
  - Ensure links are created with absolute paths
  - Handle both manual and automatic release types

- **Link Creation Process**:
  - Always validate that the target directory exists before creating links
  - Remove existing links with the same names before creating new ones
  - Use the FileSystemClient for all link operations
  - Ensure proper error handling for link operations

- **Fork-Specific Links**:
  - For GE-Proton: Create `GE-Proton`, `GE-Proton-Fallback`, and `GE-Proton-Fallback2`
  - For Proton-EM: Create `Proton-EM`, `Proton-EM-Fallback`, and `Proton-EM-Fallback2`
  - Follow the same pattern for any new forks added to the system

## Testing Guidelines

- **Dependency Injection**:
  - Use the dependency injection pattern for testing network and file system operations
  - Mock external dependencies (curl, tar) appropriately
  - Test error conditions and edge cases
  - Ensure all components can be tested in isolation

- **Test Coverage**:
  - Test all fork types with their specific naming conventions
  - Verify the link management system works correctly
  - Test error handling and fallback mechanisms
  - Ensure progress indication works as expected

- **Test Structure**:
  - Follow the existing test patterns in the project
  - Use pytest and pytest-mock for testing
  - Avoid the unittest module when designing tests
  - Utilize test parametrization to reduce boilerplate
  - When a test's name would shadow or be substantially similar to another existing test concisely rename it based on what it actually is testing rather than whatever function name is being tested
  - In the event two tests reside in different test category files and are substantially the same one of them should be renamed based on what category of test it is (based on its implementation) and the other should be removed to address the shadowing conflict

## Security Considerations

- **Input Validation**:
  - Validate all inputs before use
  - Sanitize file paths to prevent path traversal attacks
  - Verify file sizes and types before processing
  - Handle symbolic links safely during extraction

- **Network Security**:
  - Always use HTTPS for network requests
  - Implement proper timeout handling
  - Verify downloaded content when possible
  - Handle redirects safely

- **File System Security**:
  - Ensure proper permissions on created files and directories
  - Validate file paths before operations
  - Handle symbolic links safely
  - Clean up temporary files appropriately

## Performance Considerations

- **Network Operations**:
  - Maintain streaming downloads for large files
  - Implement appropriate timeout handling
  - Use chunked processing for large files
  - Preserve the intelligent caching mechanism

- **File Operations**:
  - Use appropriate extraction methods for different archive formats
  - Process files in chunks to minimize memory usage
  - Maintain FPS limiting for progress indication
  - Preserve efficient directory traversal

- **Progress Indication**:
  - Limit updates to prevent excessive terminal refreshes
  - Use appropriate chunk sizes for progress updates
  - Ensure clean terminal handling
  - Balance between responsiveness and performance

## Code Style Guidelines

- **Python Conventions**:
  - Follow PEP 8 style guidelines
  - Use type hints where appropriate
  - Maintain consistent naming conventions
  - Write clear, concise docstrings

- **Documentation**:
  - Update this DESIGN.md file when making significant changes
  - Document new features and their interactions
  - Maintain clear comments for complex logic
  - Ensure error messages are descriptive and helpful

- **Modularity**:
  - Maintain clear separation of concerns
  - Keep components focused on single responsibilities
  - Use dependency injection for testability
  - Preserve the existing architecture patterns

## Common Pitfalls to Avoid

- **Breaking Changes**:
  - Do not modify existing method signatures without careful consideration
  - Maintain backward compatibility where possible
  - Ensure all existing tests continue to pass
  - Consider the impact on the link management system

- **Dependency Issues**:
  - Do not introduce new third-party dependencies
  - Maintain compatibility with existing system dependencies
  - Ensure all required system tools are available
  - Handle cases where dependencies might be missing

- **Link Management**:
  - Do not modify the link structure without updating all related code
  - Ensure links are created with absolute paths
  - Handle cases where links already exist
  - Validate that link targets are valid directories

## Review Process

- **Before Submitting Changes**:
  - Ensure all existing tests pass
  - Add tests for new functionality
  - Update documentation as needed
  - Verify the link management system works correctly

- **Code Review Checklist**:
  - [ ] Architecture is preserved
  - [ ] Error handling is consistent
  - [ ] Link management system is maintained
  - [ ] No new dependencies are introduced
  - [ ] Tests are comprehensive
  - [ ] Documentation is updated

- **Post-Implementation**:
  - Monitor for any issues with new changes
  - Be prepared to fix issues quickly
  - Update documentation based on feedback
  - Consider the impact on all supported forks

By following these guidelines, agentic tools can effectively contribute to the ProtonFetcher project while maintaining its architecture, functionality, and reliability.

## Complexity Regression Prevention

- **Complexity Testing**: Use the complexity regression tests in `test/test_complexity_regression.py` to prevent code complexity from exceeding acceptable thresholds:
  - Run `uv run pytest tests/test_complexity_regression.py` to check current complexity metrics
  - These tests will fail if code complexity metrics exceed predefined thresholds
  - Use these tests as quality gates in your development workflow
  - Modify the thresholds in the test file as needed for your project requirements

- **Thresholds**: The complexity regression tests enforce the following limits:
  - Cyclomatic complexity: < 10 (functions rated A-B)
  - Halstead difficulty: < 15.0
  - Lines of code: < 3000 total
  - Maintainability index: > 15.0
  - Function and class count reasonable limits

- **Tools**: The tests use the radon static analysis tool to measure metrics (must be installed in development environment)
