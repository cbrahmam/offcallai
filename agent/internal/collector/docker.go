package collector

import (
	"context"
	"encoding/json"
	"fmt"
	"net"
	"net/http"
	"time"
)

// DockerCollector collects Docker container metrics
type DockerCollector struct {
	client     *http.Client
	socketPath string
}

// ContainerStats represents Docker container stats
type ContainerStats struct {
	ID       string `json:"Id"`
	Name     string `json:"Name"`
	State    string `json:"State"`
	Status   string `json:"Status"`
	CPUStats struct {
		CPUUsage struct {
			TotalUsage uint64 `json:"total_usage"`
		} `json:"cpu_usage"`
		SystemCPUUsage uint64 `json:"system_cpu_usage"`
		OnlineCPUs     int    `json:"online_cpus"`
	} `json:"cpu_stats"`
	PreCPUStats struct {
		CPUUsage struct {
			TotalUsage uint64 `json:"total_usage"`
		} `json:"cpu_usage"`
		SystemCPUUsage uint64 `json:"system_cpu_usage"`
	} `json:"precpu_stats"`
	MemoryStats struct {
		Usage    uint64 `json:"usage"`
		MaxUsage uint64 `json:"max_usage"`
		Limit    uint64 `json:"limit"`
	} `json:"memory_stats"`
	Networks map[string]struct {
		RxBytes uint64 `json:"rx_bytes"`
		TxBytes uint64 `json:"tx_bytes"`
	} `json:"networks"`
	BlockIO struct {
		IoServiceBytesRecursive []struct {
			Op    string `json:"op"`
			Value uint64 `json:"value"`
		} `json:"io_service_bytes_recursive"`
	} `json:"blkio_stats"`
}

// Container represents a Docker container
type Container struct {
	ID     string   `json:"Id"`
	Names  []string `json:"Names"`
	Image  string   `json:"Image"`
	State  string   `json:"State"`
	Status string   `json:"Status"`
}

// NewDockerCollector creates a new Docker collector
func NewDockerCollector() *DockerCollector {
	socketPath := "/var/run/docker.sock"

	// Create HTTP client that connects via Unix socket
	client := &http.Client{
		Transport: &http.Transport{
			DialContext: func(ctx context.Context, network, addr string) (net.Conn, error) {
				return net.Dial("unix", socketPath)
			},
		},
		Timeout: 5 * time.Second,
	}

	return &DockerCollector{
		client:     client,
		socketPath: socketPath,
	}
}

// Name returns the collector name
func (c *DockerCollector) Name() string {
	return "docker"
}

// IsAvailable checks if Docker is available
func (c *DockerCollector) IsAvailable() bool {
	// Check if Docker socket exists
	conn, err := net.Dial("unix", c.socketPath)
	if err != nil {
		return false
	}
	conn.Close()
	return true
}

// Collect gathers Docker metrics
func (c *DockerCollector) Collect() ([]Metric, error) {
	now := time.Now()
	var metrics []Metric

	// Get list of containers
	containers, err := c.listContainers()
	if err != nil {
		return nil, fmt.Errorf("failed to list containers: %w", err)
	}

	// Count containers by state
	total := len(containers)
	running := 0
	paused := 0
	stopped := 0

	for _, container := range containers {
		switch container.State {
		case "running":
			running++
		case "paused":
			paused++
		case "exited", "dead":
			stopped++
		}
	}

	metrics = append(metrics,
		Metric{
			Name:      "container.count",
			Value:     float64(total),
			Timestamp: now,
		},
		Metric{
			Name:      "container.running",
			Value:     float64(running),
			Timestamp: now,
		},
		Metric{
			Name:      "container.paused",
			Value:     float64(paused),
			Timestamp: now,
		},
		Metric{
			Name:      "container.stopped",
			Value:     float64(stopped),
			Timestamp: now,
		},
	)

	// Get stats for running containers
	for _, container := range containers {
		if container.State != "running" {
			continue
		}

		stats, err := c.getContainerStats(container.ID)
		if err != nil {
			continue
		}

		containerName := container.ID[:12]
		if len(container.Names) > 0 {
			containerName = container.Names[0]
			if containerName[0] == '/' {
				containerName = containerName[1:]
			}
		}

		// Calculate CPU percentage
		cpuDelta := float64(stats.CPUStats.CPUUsage.TotalUsage - stats.PreCPUStats.CPUUsage.TotalUsage)
		systemDelta := float64(stats.CPUStats.SystemCPUUsage - stats.PreCPUStats.SystemCPUUsage)
		cpuPercent := 0.0
		if systemDelta > 0 && cpuDelta > 0 {
			cpuPercent = (cpuDelta / systemDelta) * float64(stats.CPUStats.OnlineCPUs) * 100.0
		}

		// Memory usage
		memUsage := float64(stats.MemoryStats.Usage)
		memLimit := float64(stats.MemoryStats.Limit)
		memPercent := 0.0
		if memLimit > 0 {
			memPercent = (memUsage / memLimit) * 100.0
		}

		tags := map[string]string{
			"container": containerName,
			"image":     container.Image,
		}

		metrics = append(metrics,
			Metric{
				Name:      "container.cpu.usage",
				Value:     cpuPercent,
				Timestamp: now,
				Unit:      "percent",
				Tags:      tags,
			},
			Metric{
				Name:      "container.memory.usage",
				Value:     memUsage,
				Timestamp: now,
				Unit:      "bytes",
				Tags:      tags,
			},
			Metric{
				Name:      "container.memory.limit",
				Value:     memLimit,
				Timestamp: now,
				Unit:      "bytes",
				Tags:      tags,
			},
			Metric{
				Name:      "container.memory.usage_percent",
				Value:     memPercent,
				Timestamp: now,
				Unit:      "percent",
				Tags:      tags,
			},
		)

		// Network I/O
		for netName, netStats := range stats.Networks {
			netTags := map[string]string{
				"container": containerName,
				"network":   netName,
			}
			metrics = append(metrics,
				Metric{
					Name:      "container.network.rx_bytes",
					Value:     float64(netStats.RxBytes),
					Timestamp: now,
					Unit:      "bytes",
					Tags:      netTags,
				},
				Metric{
					Name:      "container.network.tx_bytes",
					Value:     float64(netStats.TxBytes),
					Timestamp: now,
					Unit:      "bytes",
					Tags:      netTags,
				},
			)
		}
	}

	return metrics, nil
}

// listContainers returns a list of all containers
func (c *DockerCollector) listContainers() ([]Container, error) {
	resp, err := c.client.Get("http://localhost/containers/json?all=true")
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	var containers []Container
	if err := json.NewDecoder(resp.Body).Decode(&containers); err != nil {
		return nil, err
	}

	return containers, nil
}

// getContainerStats returns stats for a specific container
func (c *DockerCollector) getContainerStats(containerID string) (*ContainerStats, error) {
	url := fmt.Sprintf("http://localhost/containers/%s/stats?stream=false", containerID)
	resp, err := c.client.Get(url)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	var stats ContainerStats
	if err := json.NewDecoder(resp.Body).Decode(&stats); err != nil {
		return nil, err
	}

	return &stats, nil
}
