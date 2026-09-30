// Package config handles agent configuration loading and validation
package config

import (
	"fmt"
	"os"
	"time"

	"gopkg.in/yaml.v3"
)

// Config represents the agent configuration
type Config struct {
	API        APIConfig         `yaml:"api"`
	Collection CollectionConfig  `yaml:"collection"`
	Collectors CollectorsConfig  `yaml:"collectors"`
	Logs       LogsConfig        `yaml:"logs"`
	Profiling  ProfilingConfig   `yaml:"profiling"`
	Kubernetes KubernetesConfig  `yaml:"kubernetes"`
	Tags       map[string]string `yaml:"tags"`
	Buffer     BufferConfig      `yaml:"buffer"`
	Logging    LoggingConfig     `yaml:"logging"`
}

// APIConfig contains API connection settings
type APIConfig struct {
	Endpoint string `yaml:"endpoint"`
	APIKey   string `yaml:"api_key"`
	Timeout  string `yaml:"timeout"`
}

// CollectionConfig contains collection interval settings
type CollectionConfig struct {
	Interval  string `yaml:"interval"`
	BatchSize int    `yaml:"batch_size"`
}

// CollectorsConfig enables/disables specific collectors
type CollectorsConfig struct {
	CPU        bool `yaml:"cpu"`
	Memory     bool `yaml:"memory"`
	Disk       bool `yaml:"disk"`
	Network    bool `yaml:"network"`
	Processes  bool `yaml:"processes"`
	Docker     bool `yaml:"docker"`
	Kubernetes bool `yaml:"kubernetes"`
}

// KubernetesConfig contains Kubernetes collector settings
type KubernetesConfig struct {
	Enabled      bool     `yaml:"enabled"`
	ClusterID    string   `yaml:"cluster_id"`
	ClusterName  string   `yaml:"cluster_name"`
	SyncInterval string   `yaml:"sync_interval"` // e.g., "30s"
	Namespaces   []string `yaml:"namespaces"`    // empty = all
}

// LogsConfig contains log collection settings
type LogsConfig struct {
	Enabled       bool              `yaml:"enabled"`
	Sources       []LogSourceConfig `yaml:"sources"`
	BatchSize     int               `yaml:"batch_size"`     // Max logs per batch (default 100)
	FlushInterval string            `yaml:"flush_interval"` // How often to send logs (default 5s)
	BufferSize    int               `yaml:"buffer_size"`    // Internal buffer size (default 10000)
}

// LogSourceConfig represents a log source to collect from
type LogSourceConfig struct {
	Name      string            `yaml:"name"`      // Friendly name
	Path      string            `yaml:"path"`      // File path or glob (e.g., /var/log/*.log)
	Service   string            `yaml:"service"`   // Service name tag
	Format    string            `yaml:"format"`    // auto, json, syslog, plain
	MultiLine bool              `yaml:"multiline"` // Enable multi-line parsing
	Include   []string          `yaml:"include"`   // Include patterns (regex)
	Exclude   []string          `yaml:"exclude"`   // Exclude patterns (regex)
	Tags      map[string]string `yaml:"tags"`      // Additional tags
}

// ProfilingConfig contains continuous profiling settings
type ProfilingConfig struct {
	Enabled        bool            `yaml:"enabled"`
	Interval       string          `yaml:"interval"`        // How often to collect profiles (e.g., "60s")
	UploadEndpoint string          `yaml:"upload_endpoint"` // Backend endpoint
	Targets        []ProfileTarget `yaml:"targets"`         // Targets to scrape
}

// ProfileTarget represents a pprof endpoint to scrape
type ProfileTarget struct {
	Name         string            `yaml:"name"`
	URL          string            `yaml:"url"`
	Service      string            `yaml:"service"`
	Environment  string            `yaml:"environment"`
	ProfileTypes []string          `yaml:"profile_types"` // cpu, heap, goroutine, block, mutex
	CPUDuration  string            `yaml:"cpu_duration"`  // Duration for CPU profiles (e.g., "30s")
	Labels       map[string]string `yaml:"labels"`
}

// BufferConfig contains local buffer settings
type BufferConfig struct {
	Enabled       bool   `yaml:"enabled"`
	MaxSize       int    `yaml:"max_size"`
	FlushInterval string `yaml:"flush_interval"`
	FilePath      string `yaml:"file_path"`
}

// LoggingConfig contains logging settings
type LoggingConfig struct {
	Level  string `yaml:"level"`
	Format string `yaml:"format"`
}

// DefaultConfig returns a configuration with sensible defaults
func DefaultConfig() *Config {
	return &Config{
		API: APIConfig{
			Endpoint: "http://localhost:8000/api/v1/metrics/ingest",
			Timeout:  "10s",
		},
		Collection: CollectionConfig{
			Interval:  "10s",
			BatchSize: 100,
		},
		Collectors: CollectorsConfig{
			CPU:        true,
			Memory:     true,
			Disk:       true,
			Network:    true,
			Processes:  true,
			Docker:     true,
			Kubernetes: false,
		},
		Kubernetes: KubernetesConfig{
			Enabled:      false,
			SyncInterval: "30s",
			Namespaces:   []string{},
		},
		Logs: LogsConfig{
			Enabled:       false,
			Sources:       []LogSourceConfig{},
			BatchSize:     100,
			FlushInterval: "5s",
			BufferSize:    10000,
		},
		Profiling: ProfilingConfig{
			Enabled:        false,
			Interval:       "60s",
			UploadEndpoint: "/api/v1/profiles/upload",
			Targets:        []ProfileTarget{},
		},
		Tags: make(map[string]string),
		Buffer: BufferConfig{
			Enabled:       true,
			MaxSize:       10000,
			FlushInterval: "30s",
			FilePath:      "/var/lib/offcall-agent/buffer.json",
		},
		Logging: LoggingConfig{
			Level:  "info",
			Format: "json",
		},
	}
}

// Load reads configuration from a YAML file
func Load(path string) (*Config, error) {
	cfg := DefaultConfig()

	data, err := os.ReadFile(path)
	if err != nil && !os.IsNotExist(err) {
		return nil, fmt.Errorf("failed to read config file: %w", err)
	}

	// A missing file is fine: the agent can be configured entirely through the
	// environment, which is how the container and DaemonSet deployments work.
	if err == nil {
		if err := yaml.Unmarshal(data, cfg); err != nil {
			return nil, fmt.Errorf("failed to parse config file: %w", err)
		}
	}

	// Override with environment variables
	cfg.applyEnvOverrides()

	// Validate configuration
	if err := cfg.Validate(); err != nil {
		return nil, err
	}

	return cfg, nil
}

// applyEnvOverrides applies environment variable overrides
func (c *Config) applyEnvOverrides() {
	if endpoint := os.Getenv("OFFCALL_API_ENDPOINT"); endpoint != "" {
		c.API.Endpoint = endpoint
	}
	if apiKey := os.Getenv("OFFCALL_API_KEY"); apiKey != "" {
		c.API.APIKey = apiKey
	}
	if interval := os.Getenv("OFFCALL_COLLECTION_INTERVAL"); interval != "" {
		c.Collection.Interval = interval
	}
	// Kubernetes overrides
	if clusterID := os.Getenv("OFFCALL_K8S_CLUSTER_ID"); clusterID != "" {
		c.Kubernetes.ClusterID = clusterID
		c.Kubernetes.Enabled = true
		c.Collectors.Kubernetes = true
	}
	if clusterName := os.Getenv("OFFCALL_K8S_CLUSTER_NAME"); clusterName != "" {
		c.Kubernetes.ClusterName = clusterName
	}
	if syncInterval := os.Getenv("OFFCALL_K8S_SYNC_INTERVAL"); syncInterval != "" {
		c.Kubernetes.SyncInterval = syncInterval
	}
}

// Validate checks if the configuration is valid
func (c *Config) Validate() error {
	if c.API.APIKey == "" {
		return fmt.Errorf("API key is required (set via config or OFFCALL_API_KEY env var)")
	}
	if c.API.Endpoint == "" {
		return fmt.Errorf("API endpoint is required")
	}

	// Validate intervals
	if _, err := time.ParseDuration(c.Collection.Interval); err != nil {
		return fmt.Errorf("invalid collection interval: %w", err)
	}
	if _, err := time.ParseDuration(c.API.Timeout); err != nil {
		return fmt.Errorf("invalid API timeout: %w", err)
	}
	if c.Buffer.Enabled {
		if _, err := time.ParseDuration(c.Buffer.FlushInterval); err != nil {
			return fmt.Errorf("invalid buffer flush interval: %w", err)
		}
	}

	return nil
}

// GetCollectionInterval returns the collection interval as a duration
func (c *Config) GetCollectionInterval() time.Duration {
	d, _ := time.ParseDuration(c.Collection.Interval)
	if d == 0 {
		return 10 * time.Second
	}
	return d
}

// GetAPITimeout returns the API timeout as a duration
func (c *Config) GetAPITimeout() time.Duration {
	d, _ := time.ParseDuration(c.API.Timeout)
	if d == 0 {
		return 10 * time.Second
	}
	return d
}

// GetFlushInterval returns the buffer flush interval as a duration
func (c *Config) GetFlushInterval() time.Duration {
	d, _ := time.ParseDuration(c.Buffer.FlushInterval)
	if d == 0 {
		return 30 * time.Second
	}
	return d
}

// GetProfilingInterval returns the profiling interval as a duration
func (c *Config) GetProfilingInterval() time.Duration {
	d, _ := time.ParseDuration(c.Profiling.Interval)
	if d == 0 {
		return 60 * time.Second
	}
	return d
}

// GetLogFlushInterval returns the log flush interval as a duration
func (c *Config) GetLogFlushInterval() time.Duration {
	d, _ := time.ParseDuration(c.Logs.FlushInterval)
	if d == 0 {
		return 5 * time.Second
	}
	return d
}

// GetK8sSyncInterval returns the Kubernetes sync interval as a duration
func (c *Config) GetK8sSyncInterval() time.Duration {
	d, _ := time.ParseDuration(c.Kubernetes.SyncInterval)
	if d == 0 {
		return 30 * time.Second
	}
	return d
}
