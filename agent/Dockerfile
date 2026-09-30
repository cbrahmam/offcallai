# OffCall AI Agent Dockerfile
# Build: docker build -t offcall-agent .
# Run: docker run -d --name offcall-agent -e OFFCALL_API_KEY=xxx offcall-agent

# Build stage
FROM golang:1.21-alpine AS builder

RUN apk add --no-cache git make

WORKDIR /app

# Copy go mod files
COPY go.mod go.sum ./
RUN go mod download

# Copy source
COPY . .

# Build
ARG VERSION=dev
RUN CGO_ENABLED=0 GOOS=linux go build \
    -ldflags "-X main.Version=${VERSION} -s -w" \
    -o offcall-agent \
    ./cmd/agent

# Runtime stage
FROM alpine:3.19

RUN apk add --no-cache ca-certificates tzdata

# Create non-root user
RUN addgroup -S offcall && adduser -S offcall -G offcall

# Create directories
RUN mkdir -p /etc/offcall-agent /var/lib/offcall-agent && \
    chown -R offcall:offcall /var/lib/offcall-agent

# Copy binary
COPY --from=builder /app/offcall-agent /usr/local/bin/offcall-agent

# Copy default config
COPY configs/agent.yaml /etc/offcall-agent/agent.yaml

# Set permissions
RUN chmod +x /usr/local/bin/offcall-agent

USER offcall

ENTRYPOINT ["/usr/local/bin/offcall-agent"]
CMD ["--config", "/etc/offcall-agent/agent.yaml"]
