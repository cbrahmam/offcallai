# OffCall AI Agent

Lightweight monitoring agent for collecting system metrics and sending them to OffCall AI.

## Features

- **CPU Metrics**: Usage, load averages, per-core stats
- **Memory Metrics**: Used, free, cached, swap
- **Disk Metrics**: Usage per mount, I/O rates
- **Network Metrics**: Bytes in/out, packets, errors, connections
- **Process Metrics**: Count, states, top CPU/memory consumers
- **Docker Metrics**: Container count, per-container CPU/memory/network
- **Continuous Profiling**: Collect pprof profiles from Go applications

## Quick Install

```bash
curl -fsSL $OFFCALL_URL/install.sh | OFFCALL_API_KEY=your_key bash
```

## Manual Installation

### Build from Source

```bash
# Clone the repository
git clone https://github.com/offcallai/agent.git
cd agent

# Build
make build

# Install
sudo make install
```

### Configure

Edit `/etc/offcall-agent/agent.yaml`:

```yaml
api:
  endpoint: http://localhost:8000/api/v1/metrics/ingest
  api_key: YOUR_API_KEY
  timeout: 10s

collection:
  interval: 10s
  batch_size: 100

collectors:
  cpu: true
  memory: true
  disk: true
  network: true
  processes: true
  docker: true

tags:
  environment: production
  service: my-service
```

### Run

```bash
# As a systemd service (recommended)
sudo systemctl enable offcall-agent
sudo systemctl start offcall-agent

# Or run directly
offcall-agent --config /etc/offcall-agent/agent.yaml
```

## Docker

```bash
docker run -d \
  --name offcall-agent \
  -e OFFCALL_API_KEY=your_key \
  -v /var/run/docker.sock:/var/run/docker.sock:ro \
  offcallai/agent:latest
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `OFFCALL_API_KEY` | API key for authentication | Required |
| `OFFCALL_API_ENDPOINT` | API endpoint URL | `http://localhost:8000/api/v1/metrics/ingest` |
| `OFFCALL_COLLECTION_INTERVAL` | Collection interval | `10s` |

## Building

```bash
# Build for current platform
make build

# Build for all platforms
make release

# Build Docker image
make docker
```

## Metrics Collected

### CPU
- `system.cpu.usage` - Total CPU usage (%)
- `system.cpu.user` - User mode CPU (%)
- `system.cpu.system` - Kernel mode CPU (%)
- `system.cpu.idle` - Idle CPU (%)
- `system.cpu.iowait` - I/O wait (%)
- `system.load.1` - 1-minute load average
- `system.load.5` - 5-minute load average
- `system.load.15` - 15-minute load average

### Memory
- `system.memory.total` - Total memory (bytes)
- `system.memory.used` - Used memory (bytes)
- `system.memory.free` - Free memory (bytes)
- `system.memory.usage_percent` - Memory usage (%)
- `system.swap.used` - Swap used (bytes)
- `system.swap.free` - Swap free (bytes)

### Disk
- `system.disk.total` - Total disk space (bytes)
- `system.disk.used` - Used disk space (bytes)
- `system.disk.free` - Free disk space (bytes)
- `system.disk.usage_percent` - Disk usage (%)
- `system.disk.read_bytes` - Disk read rate (bytes/s)
- `system.disk.write_bytes` - Disk write rate (bytes/s)

### Network
- `system.network.bytes_in` - Network receive rate (bytes/s)
- `system.network.bytes_out` - Network send rate (bytes/s)
- `system.network.packets_in` - Packets received (packets/s)
- `system.network.packets_out` - Packets sent (packets/s)
- `system.network.errors_in` - Receive errors
- `system.network.errors_out` - Send errors

### Process
- `system.process.count` - Total process count
- `system.process.running` - Running processes
- `system.process.sleeping` - Sleeping processes
- `system.process.zombie` - Zombie processes

### Docker
- `container.count` - Total containers
- `container.running` - Running containers
- `container.cpu.usage` - Container CPU (%)
- `container.memory.usage` - Container memory (bytes)

## Continuous Profiling

The agent can collect pprof profiles from Go applications and upload them to OffCall AI for flamegraph visualization and analysis.

### Enable Profiling

Add profiling configuration to your `agent.yaml`:

```yaml
profiling:
  enabled: true
  interval: 60s  # How often to collect profiles

  targets:
    - name: my-api-server
      url: http://localhost:6060  # pprof endpoint
      service: api-server
      environment: production
      profile_types:
        - cpu      # CPU profile (30s sample)
        - heap     # Memory/heap profile
        - goroutine  # Goroutine stack traces
      cpu_duration: 30s
      labels:
        team: backend
```

### Supported Profile Types

| Type | Description | Endpoint |
|------|-------------|----------|
| `cpu` | CPU time spent in functions | `/debug/pprof/profile` |
| `heap` | Memory allocations | `/debug/pprof/heap` |
| `goroutine` | Stack traces of goroutines | `/debug/pprof/goroutine` |
| `block` | Blocking operations | `/debug/pprof/block` |
| `mutex` | Lock contention | `/debug/pprof/mutex` |
| `allocs` | Memory allocations | `/debug/pprof/allocs` |

### Expose pprof in Your Go App

```go
import _ "net/http/pprof"

func main() {
    // Start pprof server on port 6060
    go func() {
        log.Println(http.ListenAndServe("localhost:6060", nil))
    }()

    // Your app code...
}
```

Or use a dedicated mux:

```go
import "net/http/pprof"

mux := http.NewServeMux()
mux.HandleFunc("/debug/pprof/", pprof.Index)
mux.HandleFunc("/debug/pprof/cmdline", pprof.Cmdline)
mux.HandleFunc("/debug/pprof/profile", pprof.Profile)
mux.HandleFunc("/debug/pprof/symbol", pprof.Symbol)
mux.HandleFunc("/debug/pprof/trace", pprof.Trace)

go http.ListenAndServe(":6060", mux)
```

## Troubleshooting

### View Logs
```bash
journalctl -u offcall-agent -f
```

### Test Connection
```bash
curl -X POST http://localhost:8000/api/v1/hosts/agent/heartbeat \
  -H "X-API-Key: your_key" \
  -H "Content-Type: application/json" \
  -d '{"agent_id": "test"}'
```

### Uninstall
```bash
curl -fsSL $OFFCALL_URL/install.sh | sudo bash -s uninstall
```

## License

MIT License - see LICENSE file for details.
