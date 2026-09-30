# OffCall AI Agent Makefile

VERSION ?= $(shell git describe --tags --always --dirty 2>/dev/null || echo "dev")
LDFLAGS := -X main.Version=$(VERSION) -s -w
BINARY := offcall-agent

# Go parameters
GOCMD := go
GOBUILD := $(GOCMD) build
GOCLEAN := $(GOCMD) clean
GOTEST := $(GOCMD) test
GOGET := $(GOCMD) get
GOMOD := $(GOCMD) mod

# Build directories
BUILD_DIR := build
DIST_DIR := dist

.PHONY: all build clean test deps linux darwin windows docker install release

all: clean deps test build

# Dependencies
deps:
	$(GOMOD) download
	$(GOMOD) tidy

# Build for current platform
build:
	mkdir -p $(BUILD_DIR)
	$(GOBUILD) -ldflags "$(LDFLAGS)" -o $(BUILD_DIR)/$(BINARY) ./cmd/agent

# Run tests
test:
	$(GOTEST) -v ./...

# Clean build artifacts
clean:
	$(GOCLEAN)
	rm -rf $(BUILD_DIR) $(DIST_DIR)

# Build for Linux (amd64 and arm64)
linux:
	mkdir -p $(DIST_DIR)
	GOOS=linux GOARCH=amd64 $(GOBUILD) -ldflags "$(LDFLAGS)" -o $(DIST_DIR)/$(BINARY)-linux-amd64 ./cmd/agent
	GOOS=linux GOARCH=arm64 $(GOBUILD) -ldflags "$(LDFLAGS)" -o $(DIST_DIR)/$(BINARY)-linux-arm64 ./cmd/agent

# Build for macOS (amd64 and arm64)
darwin:
	mkdir -p $(DIST_DIR)
	GOOS=darwin GOARCH=amd64 $(GOBUILD) -ldflags "$(LDFLAGS)" -o $(DIST_DIR)/$(BINARY)-darwin-amd64 ./cmd/agent
	GOOS=darwin GOARCH=arm64 $(GOBUILD) -ldflags "$(LDFLAGS)" -o $(DIST_DIR)/$(BINARY)-darwin-arm64 ./cmd/agent

# Build for Windows
windows:
	mkdir -p $(DIST_DIR)
	GOOS=windows GOARCH=amd64 $(GOBUILD) -ldflags "$(LDFLAGS)" -o $(DIST_DIR)/$(BINARY)-windows-amd64.exe ./cmd/agent

# Build all platforms
release: linux darwin windows
	@echo "Built binaries for all platforms in $(DIST_DIR)/"
	@ls -la $(DIST_DIR)/

# Build Docker image
docker:
	docker build -t offcallai/agent:$(VERSION) -t offcallai/agent:latest --build-arg VERSION=$(VERSION) .

# Install locally (Linux/macOS)
install: build
	sudo cp $(BUILD_DIR)/$(BINARY) /usr/local/bin/
	sudo mkdir -p /etc/offcall-agent /var/lib/offcall-agent
	sudo cp configs/agent.yaml /etc/offcall-agent/agent.yaml
	@echo "Installed $(BINARY) to /usr/local/bin/"
	@echo "Config at /etc/offcall-agent/agent.yaml"
	@echo ""
	@echo "To configure, edit /etc/offcall-agent/agent.yaml and set your API key"
	@echo "Or set OFFCALL_API_KEY environment variable"

# Create systemd service file
systemd:
	@echo "[Unit]" > $(BUILD_DIR)/offcall-agent.service
	@echo "Description=OffCall AI Monitoring Agent" >> $(BUILD_DIR)/offcall-agent.service
	@echo "After=network.target" >> $(BUILD_DIR)/offcall-agent.service
	@echo "" >> $(BUILD_DIR)/offcall-agent.service
	@echo "[Service]" >> $(BUILD_DIR)/offcall-agent.service
	@echo "Type=simple" >> $(BUILD_DIR)/offcall-agent.service
	@echo "User=root" >> $(BUILD_DIR)/offcall-agent.service
	@echo "ExecStart=/usr/local/bin/offcall-agent --config /etc/offcall-agent/agent.yaml" >> $(BUILD_DIR)/offcall-agent.service
	@echo "Restart=always" >> $(BUILD_DIR)/offcall-agent.service
	@echo "RestartSec=10" >> $(BUILD_DIR)/offcall-agent.service
	@echo "" >> $(BUILD_DIR)/offcall-agent.service
	@echo "[Install]" >> $(BUILD_DIR)/offcall-agent.service
	@echo "WantedBy=multi-user.target" >> $(BUILD_DIR)/offcall-agent.service
	@echo "Created systemd service file at $(BUILD_DIR)/offcall-agent.service"

# Run locally for development
run: build
	./$(BUILD_DIR)/$(BINARY) --config configs/agent.yaml

# Show version
version:
	@echo $(VERSION)

# Help
help:
	@echo "OffCall AI Agent Makefile"
	@echo ""
	@echo "Usage:"
	@echo "  make build     - Build for current platform"
	@echo "  make test      - Run tests"
	@echo "  make linux     - Build for Linux (amd64, arm64)"
	@echo "  make darwin    - Build for macOS (amd64, arm64)"
	@echo "  make windows   - Build for Windows (amd64)"
	@echo "  make release   - Build for all platforms"
	@echo "  make docker    - Build Docker image"
	@echo "  make install   - Install locally"
	@echo "  make systemd   - Generate systemd service file"
	@echo "  make run       - Run locally for development"
	@echo "  make clean     - Clean build artifacts"
