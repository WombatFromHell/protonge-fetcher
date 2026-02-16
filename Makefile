PY = python3
SRC_DIR = src
BUILD_DIR = dist
ENTRY = entry:main
ARTIFACT = protonfetcher.pyz
OUT = $(BUILD_DIR)/$(ARTIFACT)

build:
	mkdir -p $(BUILD_DIR)
	$(PY) -m zipapp $(SRC_DIR) -o $(OUT) -m $(ENTRY) -p "/usr/bin/env python3"
	chmod +x $(OUT)

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
	ty check ./src ./tests; \
		ruff check ./src ./tests

prettier:
	prettier --cache -c -w *.md

format: prettier
	ruff check --select I ./src ./tests --fix; \
	ruff format ./src ./tests

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
