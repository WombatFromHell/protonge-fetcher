SRC_DIR = src
BUILD_DIR = dist
ENTRY_MODULE = entry
ENTRY_FUNC = main
ARTIFACT = protonfetcher.pyz
OUT = $(BUILD_DIR)/$(ARTIFACT)
VERSION_FILE = $(SRC_DIR)/protonfetcher/__version__.py

CONTAINER_IMAGE = protonfetcher-nix
CONTAINER_FILE = Containerfile.dev
NIX_STORE_VOLUME = protonfetcher-nix-store
UV_CACHE_VOLUME = protonfetcher-uv-cache

ifeq ($(origin CONTAINER_RUNTIME),undefined)
CONTAINER_RUNTIME := $(shell command -v nerdctl 2>/dev/null || command -v podman 2>/dev/null || command -v docker 2>/dev/null)
endif

HOST_UID := $(shell id -u)
HOST_GID := $(shell id -g)
RECLAIM_OWNERSHIP = chown -R $(HOST_UID):$(HOST_GID) $(CURDIR) 2>/dev/null || true

CONTAINER_FLAGS = --security-opt label=disable --userns=keep-id:uid=0,gid=0
# Mounts:
# 1. Host project at /work
# 2. Persistent Nix store root at /nix (store + database + profiles)
# 3. Persistent uv cache at /root/.cache/uv
CONTAINER_MOUNTS = \
	-v "$(CURDIR)":/work \
	-v "$(NIX_STORE_VOLUME)":/nix \
	-v "$(UV_CACHE_VOLUME)":/root/.cache/uv \
	-e HOME=/root \
	-e DIRENV_DIR="" \
	-e UV_CACHE_DIR=/root/.cache/uv \
	-e UV_LINK_MODE=copy \
	-w /work

CONTAINER_RUN = $(CONTAINER_RUNTIME) run --rm $(CONTAINER_FLAGS) $(CONTAINER_MOUNTS) $(CONTAINER_IMAGE)
CONTAINER_RUN_IT = $(CONTAINER_RUNTIME) run --rm -it $(CONTAINER_FLAGS) $(CONTAINER_MOUNTS) $(CONTAINER_IMAGE)

define run_in_container
$(CONTAINER_RUN) /bin/sh -c ' \
	git config --global --add safe.directory /work 2>/dev/null || true; \
	mkdir -p /nix/var/nix/daemon-socket; \
	nix-daemon & \
	sleep 2; \
	NIX_REMOTE=daemon nix develop -c bash -ec "$(1)"; \
	STATUS=$$?; \
	exit $$STATUS \
'; \
STATUS=$$?; \
$(RECLAIM_OWNERSHIP); \
exit $$STATUS
endef

define run_in_container_it
$(CONTAINER_RUN_IT) /bin/sh -c ' \
	git config --global --add safe.directory /work 2>/dev/null || true; \
	mkdir -p /nix/var/nix/daemon-socket; \
	nix-daemon & \
	sleep 2; \
	NIX_REMOTE=daemon nix develop -c bash -ec "$(1)"; \
	STATUS=$$?; \
	exit $$STATUS \
'; \
STATUS=$$?; \
$(RECLAIM_OWNERSHIP); \
exit $$STATUS
endef

export SOURCE_DATE_EPOCH ?= 315532800
VERSION := $(shell grep '^version = ' pyproject.toml | cut -d'"' -f2)
TIMESTAMP = $(shell date -d "@$(SOURCE_DATE_EPOCH)" -u +%Y-%m-%dT%H:%M:%SZ)

REPORT_BUILT = echo "Built: $(OUT)"; echo "SHA256: $$(cat $(OUT).sha256sum | cut -d' ' -f1)"

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +; \
	rm -rf $(BUILD_DIR) .pytest_cache .ruff_cache .direnv .pi result* .coverage

configure:
	uv venv --clear
	uv sync --frozen

check-host-tools:
	@command -v sha256sum >/dev/null 2>&1 || { echo "ERROR: sha256sum not found."; exit 1; }
	@sed --version >/dev/null 2>&1 || { echo "ERROR: GNU sed required."; exit 1; }
	@date --version >/dev/null 2>&1 || { echo "ERROR: GNU date required."; exit 1; }

build: clean check-host-tools
	@echo "Building $(ARTIFACT) (version $(VERSION))"
	mkdir -p $(BUILD_DIR)
	sed -i 's/^__version__ = .*/__version__ = "$(VERSION)"/' $(VERSION_FILE)
	rm -rf $(BUILD_DIR)/staging
	mkdir -p $(BUILD_DIR)/staging
	cp -r $(SRC_DIR)/* $(BUILD_DIR)/staging/
	find $(BUILD_DIR)/staging -type f -exec chmod 644 {} +
	find $(BUILD_DIR)/staging -type d -exec chmod 755 {} +
	echo "from $(ENTRY_MODULE) import $(ENTRY_FUNC); $(ENTRY_FUNC)()" > $(BUILD_DIR)/staging/__main__.py
	find $(BUILD_DIR)/staging -exec touch -d "@$(SOURCE_DATE_EPOCH)" {} \;
	cd $(BUILD_DIR)/staging && find . \( -type d -o -type f \) -print0 | LC_ALL=C sort -z | tr '\0' '\n' | zip -X -q -n : -@ ../archive.zip
	echo '#!/usr/bin/env python3' > $(OUT)
	cat $(BUILD_DIR)/archive.zip >> $(OUT)
	chmod +x $(OUT)
	cd $(BUILD_DIR) && sha256sum $(ARTIFACT) > $(ARTIFACT).sha256sum
	rm -rf $(BUILD_DIR)/staging $(BUILD_DIR)/archive.zip
	$(REPORT_BUILT)

install: $(OUT)
	@cd $(BUILD_DIR) && sha256sum -c $(ARTIFACT).sha256sum
	@if [ -d "$$HOME/.local/bin/scripts/" ]; then INSTALL_DIR="$$HOME/.local/bin/scripts"; else mkdir -p "$$HOME/.local/bin"; INSTALL_DIR="$$HOME/.local/bin"; fi; \
	cp -f $(OUT) $(OUT).sha256sum "$$INSTALL_DIR/"; \
	chmod +x "$$INSTALL_DIR/$(ARTIFACT)"; \
	ln -sf "$$INSTALL_DIR/$(ARTIFACT)" "$$HOME/.local/bin/protonfetcher"; \
	echo "Installed to $$INSTALL_DIR/$(ARTIFACT)"

test:
	uv run pytest --tb=short --cov=src --cov-report=term-missing --cov-branch

prettier:
	prettier -c -w *.md

lint:
	uv run ty check ./src ./tests; \
	uv run pyright ./src ./tests; \
	uv run ruff check ./src ./tests

format: prettier
	uv run ruff check ./src ./tests --fix; \
	uv run ruff format ./src ./tests

radon:
	uv run radon cc ./src -a

quality: lint format

ci: configure test lint build

build-nix: clean check-host-tools
	@echo "Building $(ARTIFACT) via Nix (version $(VERSION))"
	mkdir -p $(BUILD_DIR)
	nix build . --out-link ./$(OUT)
	cd $(BUILD_DIR) && sha256sum $(ARTIFACT) > $(ARTIFACT).sha256sum
	$(REPORT_BUILT)

ci-nix: lint test build-nix

container:
	$(CONTAINER_RUNTIME) build -t $(CONTAINER_IMAGE) -f $(CONTAINER_FILE) .

clean-container:
	@echo "Cleaning container image and persistent volumes..."
	-$(CONTAINER_RUNTIME) rmi -f $(CONTAINER_IMAGE) >/dev/null 2>&1 || true
	-$(CONTAINER_RUNTIME) volume rm -f $(NIX_STORE_VOLUME) >/dev/null 2>&1 || true
	-$(CONTAINER_RUNTIME) volume rm -f $(UV_CACHE_VOLUME) >/dev/null 2>&1 || true
	@echo "Cleanup complete."

enter-container: container
	$(call run_in_container_it,nix develop)

build-container: container
	@echo "Building $(ARTIFACT) via Nix in container (version $(VERSION))"
	$(call run_in_container,make build-nix && cp -L dist/protonfetcher.pyz dist/.protonfetcher && mv -f dist/.protonfetcher dist/protonfetcher.pyz)
	$(REPORT_BUILT)

container-ci: container
	@echo "Running pre-publish checks via Nix in container (version $(VERSION))"
	$(call run_in_container,make ci-nix)

container-%: container
	$(call run_in_container,make $*)

all: build install

.PHONY: build install test lint prettier format radon quality clean all configure ci build-nix ci-nix container clean-container enter-container build-container container-ci container-%
.SILENT: build install test lint prettier format radon quality clean all configure ci build-nix ci-nix container clean-container enter-container build-container container-ci container-%
