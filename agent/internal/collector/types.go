// Package collector contains metric collection logic
package collector

import (
	"time"
)

// Metric represents a single metric data point
type Metric struct {
	Name      string            `json:"name"`
	Value     float64           `json:"value"`
	Timestamp time.Time         `json:"timestamp"`
	Tags      map[string]string `json:"tags,omitempty"`
	Unit      string            `json:"unit,omitempty"`
}

// MetricBatch represents a batch of metrics to send to the API
type MetricBatch struct {
	AgentID      string    `json:"agent_id"`
	Metrics      []Metric  `json:"metrics"`
	AgentVersion string    `json:"agent_version,omitempty"`
	CollectedAt  time.Time `json:"collected_at,omitempty"`
}

// SystemInfo contains information about the host system
type SystemInfo struct {
	Hostname         string `json:"hostname"`
	OS               string `json:"os"`
	OSVersion        string `json:"os_version"`
	Kernel           string `json:"kernel"`
	Arch             string `json:"arch"`
	CPUCores         int    `json:"cpu_cores"`
	CPUModel         string `json:"cpu_model"`
	MemoryTotalBytes uint64 `json:"memory_total_bytes"`
}

// HostRegistration is sent when the agent starts
type HostRegistration struct {
	Hostname         string            `json:"hostname"`
	AgentID          string            `json:"agent_id"`
	OS               string            `json:"os,omitempty"`
	OSVersion        string            `json:"os_version,omitempty"`
	Kernel           string            `json:"kernel,omitempty"`
	Arch             string            `json:"arch,omitempty"`
	CPUCores         int               `json:"cpu_cores,omitempty"`
	CPUModel         string            `json:"cpu_model,omitempty"`
	MemoryTotalBytes uint64            `json:"memory_total_bytes,omitempty"`
	AgentVersion     string            `json:"agent_version,omitempty"`
	IPAddress        string            `json:"ip_address,omitempty"`
	Tags             map[string]string `json:"tags,omitempty"`
}

// Heartbeat is sent periodically to indicate the agent is alive
type Heartbeat struct {
	AgentID       string `json:"agent_id"`
	AgentVersion  string `json:"agent_version,omitempty"`
	IPAddress     string `json:"ip_address,omitempty"`
	UptimeSeconds int64  `json:"uptime_seconds,omitempty"`
}

// Collector interface for all metric collectors
type Collector interface {
	// Name returns the collector name
	Name() string
	// Collect gathers metrics and returns them
	Collect() ([]Metric, error)
	// IsAvailable checks if the collector can run on this system
	IsAvailable() bool
}

// LogEntry represents a single log line
type LogEntry struct {
	Timestamp  time.Time              `json:"timestamp"`
	Level      string                 `json:"level,omitempty"` // debug, info, warn, error, fatal
	Message    string                 `json:"message"`
	Source     string                 `json:"source"` // file path or source name
	Service    string                 `json:"service,omitempty"`
	Host       string                 `json:"host,omitempty"`
	Tags       map[string]string      `json:"tags,omitempty"`
	Attributes map[string]interface{} `json:"attributes,omitempty"` // Parsed JSON fields
}

// LogBatch represents a batch of logs to send to the API
type LogBatch struct {
	AgentID      string     `json:"agent_id"`
	Logs         []LogEntry `json:"logs"`
	AgentVersion string     `json:"agent_version,omitempty"`
	CollectedAt  time.Time  `json:"collected_at,omitempty"`
}

// LogResponse represents the API response for log ingestion
type LogResponse struct {
	Success      bool     `json:"success"`
	LogsReceived int      `json:"logs_received"`
	LogsStored   int      `json:"logs_stored"`
	Errors       []string `json:"errors,omitempty"`
}
