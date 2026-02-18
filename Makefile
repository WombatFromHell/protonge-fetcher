PY = python3
SRC_DIR = src
BUILD_DIR = dist
ENTRY = entry:main
ARTIFACT = protonfetcher.pyz
OUT = $(BUILD_DIR)/$(ARTIFACT)

# Extract version from pyproject.toml
VERSION = $(shell $(PY) -c "import tomllib; print(tomllib.load(open('pyproject.toml', 'rb'))['project']['version'])")

build:
	mkdir -p $(BUILD_DIR)
	sed -i 's/__version__ = "DEV"/__version__ = "$(VERSION)"/' $(SRC_DIR)/protonfetcher/__version__.py
	$(PY) -m zipapp $(SRC_DIR) -o $(OUT) -m $(ENTRY) -p "/usr/bin/env python3"
	chmod +x $(OUT)
	sed -i 's/__version__ = "$(VERSION)"/__version__ = "DEV"/' $(SRC_DIR)/protonfetcher/__version__.py

install: $(OUT)
	@if [ -d "$$HOME/.local/bin/scripts/" ]; then \
		INSTALL_DIR="$$HOME/.local/bin/scripts"; \
	else \
		mkdir -p "$$HOME/.local/bin"; \
		INSTALL_DIR="$$HOME/.local/bin"; \
	fi; \
	cp $(OUT) "$$INSTALL_DIR/$(ARTIFACT)"; \
	chmod +x "$$INSTALL_DIR/$(ARTIFACT)"; \
	ln -sf "$$INSTALL_DIR/$(ARTIFACT)" "$$HOME/.local/bin/protonfetcher"; \
	echo "Installed to $$INSTALL_DIR/$(ARTIFACT)"

test:
	uv run pytest -xvs --cov=src --cov-report=term-missing --cov-branch

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

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +; \
	rm -rf \
		$(BUILD_DIR) \
		.pytest_cache \
		.ruff_cache \
		.coverage

all: clean build install

.PHONY: build install test lint prettier format radon quality clean all
.SILENT: build install test lint prettier format radon quality clean all
