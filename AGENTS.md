# AGENTS.md

## Overview

Actionable tool usage guidelines for agentic tools when working with the ProtonFetcher codebase.

## Development Commands

- `make test` - Run test suite
- `make radon` - Check code complexity
- `make quality` - Run code quality checks
- `make all` - Clean, build, and install locally to `~/.local/bin/protonfetcher`
- `uv run pytest -xvs` - Manually run test suite

## Current Task Tracking

The `.current_task.md` file in the project root serves as transient, per-task memory for tracking active work. Use this file as follows:

**Before starting a task:**

- Create or update `.current_task.md` with:
  - A clear, concise description of the current active task
  - Relevant code context (snippets only, not entire files)
  - The goal of the task
  - The intended deterministic, verifiable result
  - If a task will involve a particular file build a compact file-index in our `.current_task.md` first before changing anything
  - If a change impacts additional files update the scope in `.current_task.md` first

**During the task:**

- Keep the file updated with progress notes, decisions made, and any discoveries
- Store relevant code snippets encountered during exploration
- Update the goal or expected result if understanding evolves

**After task completion:**

- Attempt to verify the deterministic result has been achieved
- Clear or archive `.current_task.md` using `echo "" > .current_task.md` to prepare for the next task
- Transfer any persistent insights to `MEMORY.md` if they apply beyond the current task

## Context Window Budgeting

The context window is typically limited to ~65536 tokens. To maximize efficiency and avoid overflow:

**Reading source code:**

- Never read entire source files into context (unless absolutely necessary)
- Use targeted searches and read only relevant snippets (specific functions, classes, or line ranges)
- Prefer grep/ripgrep patterns to locate relevant code before reading

**Communication:**

- Avoid verbose pre- and post-summaries
- Skip conversational filler; be direct and concise
- Focus on actionable information only

**Memory strategy:**

- Use `.current_task.md` for transient, per-task context (see above)
- Use `MEMORY.md` for persistent, per-plan context that spans multiple tasks
- Offload context to these files regularly rather than keeping details in working memory
- Before reading new context, write current findings to memory files to free space
