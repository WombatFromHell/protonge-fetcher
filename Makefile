PY = python3
SRC_DIR = src
BUILD_DIR = dist
ENTRY_MODULE = entry
ENTRY_FUNC = main
ARTIFACT = protonfetcher.pyz
OUT = $(BUILD_DIR)/$(ARTIFACT)
CHECKSUM = $(BUILD_DIR)/$(ARTIFACT).sha256sum

# Fixed epoch for reproducible builds: 2015-10-21 00:00:00 UTC
# Can be overridden via environment or use git commit timestamp:
# SOURCE_DATE_EPOCH ?= $(shell git log -1 --pretty=%ct 2>/dev/null || echo 1445385600)
SOURCE_DATE_EPOCH ?= 1445385600
export SOURCE_DATE_EPOCH

# Extract version from pyproject.toml
VERSION = $(shell $(PY) -c "import tomllib; print(tomllib.load(open('pyproject.toml', 'rb'))['project']['version'])")

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +; \
	rm -rf \
	$(BUILD_DIR) \
	.pytest_cache \
	.ruff_cache \
	.coverage

build: clean
	@echo "Building deterministic zipapp..."

	# Clean previous build artifacts
	rm -rf $(BUILD_DIR)/staging $(BUILD_DIR)/archive.zip
	mkdir -p $(BUILD_DIR)/staging

	# Copy source to staging, excluding __pycache__ and other non-source files
	rsync -a --exclude='__pycache__' --exclude='*.pyc' --exclude='*.pyo' \
		$(SRC_DIR)/ $(BUILD_DIR)/staging/

	# Update version in staging
	sed -i 's/__version__ = "DEV"/__version__ = "$(VERSION)"/' $(BUILD_DIR)/staging/protonfetcher/__version__.py

	# Create __main__.py for zipapp entry point (replaces -m flag)
	echo "from $(ENTRY_MODULE) import $(ENTRY_FUNC); $(ENTRY_FUNC)()" > $(BUILD_DIR)/staging/__main__.py

	# Normalize timestamps on ALL files in staging
	find $(BUILD_DIR)/staging -print0 | xargs -0r touch --no-dereference --date="@$(SOURCE_DATE_EPOCH)"

	# Create zip archive deterministically:
	# -X: strip extra file attributes (uid/gid/extended attrs)
	# -r: recursive
	# -q: quiet mode
	# Files are piped in sorted order for deterministic file ordering
	cd $(BUILD_DIR)/staging && \
		find . -type f | LC_ALL=C sort | \
		zip -X -r -q -@ ../archive.zip

	# Prepend shebang to create executable .pyz
	printf '#!/usr/bin/env python3\n' > $(OUT)
	cat $(BUILD_DIR)/archive.zip >> $(OUT)
	chmod +x $(OUT)

	# Generate SHA256 checksum file for verification
	cd $(BUILD_DIR) && sha256sum $(ARTIFACT) > $(ARTIFACT).sha256sum

	# Cleanup intermediate files
	rm -rf $(BUILD_DIR)/staging $(BUILD_DIR)/archive.zip

	@echo "Built: $(OUT)"
	@echo "Checksum: $$(cat $(BUILD_DIR)/$(ARTIFACT).sha256sum)"

install: $(OUT)
	@cd $(BUILD_DIR) && sha256sum -c $(ARTIFACT).sha256sum
	@if [ -d "$$HOME/.local/bin/scripts/" ]; then \
		INSTALL_DIR="$$HOME/.local/bin/scripts"; \
	else \
		mkdir -p "$$HOME/.local/bin"; \
		INSTALL_DIR="$$HOME/.local/bin"; \
	fi; \
	cp -f $(OUT) $(OUT).sha256sum "$$INSTALL_DIR/"; \
	chmod +x "$$INSTALL_DIR/$(ARTIFACT)"; \
	ln -sf "$$INSTALL_DIR/$(ARTIFACT)" "$$HOME/.local/bin/protonfetcher"; \
	echo "Installed to $$INSTALL_DIR/$(ARTIFACT)"

test:
	uv run pytest --tb=short --cov=src --cov-report=term-missing --cov-branch

lint:
	uv run ty check ./src ./tests; \
		uv run ruff check ./src ./tests --fix

prettier:
	uv run prettier -c -w *.md

format: prettier
	uv run ruff check --select I ./src ./tests --fix; \
	uv run ruff format ./src ./tests

radon:
	uv run radon cc ./src -a

quality: lint format

all: clean build install

.PHONY: build install test lint prettier format radon quality clean all
.SILENT: build install test lint prettier format radon quality clean all
