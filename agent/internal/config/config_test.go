package config

import (
	"os"
	"path/filepath"
	"testing"
	"time"
)

func TestDefaultConfig(t *testing.T) {
	cfg := DefaultConfig()

	if cfg.API.Endpoint == "" {
		t.Error("expected a default API endpoint")
	}
	if cfg.Collection.Interval == "" {
		t.Error("expected a default collection interval")
	}
	if cfg.Collection.BatchSize == 0 {
		t.Error("expected a non-zero batch size")
	}
	if cfg.Buffer.MaxSize == 0 {
		t.Error("expected a non-zero buffer size")
	}
	if !cfg.Collectors.CPU || !cfg.Collectors.Memory {
		t.Error("expected the CPU and memory collectors to be enabled by default")
	}
}

func TestDefaultsParseAsDurations(t *testing.T) {
	cfg := DefaultConfig()

	if got := cfg.GetCollectionInterval(); got != 10*time.Second {
		t.Errorf("collection interval = %v, want 10s", got)
	}
	if got := cfg.GetAPITimeout(); got != 10*time.Second {
		t.Errorf("API timeout = %v, want 10s", got)
	}
	if got := cfg.GetFlushInterval(); got != 30*time.Second {
		t.Errorf("buffer flush interval = %v, want 30s", got)
	}
}

func TestLoadAppliesEnvOverrides(t *testing.T) {
	t.Setenv("OFFCALL_API_ENDPOINT", "http://localhost:9999/api/v1/metrics/ingest")
	t.Setenv("OFFCALL_API_KEY", "test-key-123")
	t.Setenv("OFFCALL_COLLECTION_INTERVAL", "30s")

	// Load falls back to defaults plus env when the file is absent.
	cfg, err := Load(filepath.Join(t.TempDir(), "does-not-exist.yaml"))
	if err != nil {
		t.Fatalf("Load() error = %v", err)
	}

	if cfg.API.Endpoint != "http://localhost:9999/api/v1/metrics/ingest" {
		t.Errorf("endpoint = %q, want the env override", cfg.API.Endpoint)
	}
	if cfg.API.APIKey != "test-key-123" {
		t.Errorf("api key = %q, want the env override", cfg.API.APIKey)
	}
	if got := cfg.GetCollectionInterval(); got != 30*time.Second {
		t.Errorf("collection interval = %v, want 30s", got)
	}
}

func TestKubernetesEnvOverrideEnablesCollector(t *testing.T) {
	t.Setenv("OFFCALL_API_KEY", "k")
	t.Setenv("OFFCALL_K8S_CLUSTER_ID", "cluster-1")

	cfg, err := Load(filepath.Join(t.TempDir(), "absent.yaml"))
	if err != nil {
		t.Fatalf("Load() error = %v", err)
	}

	if !cfg.Kubernetes.Enabled || !cfg.Collectors.Kubernetes {
		t.Error("setting OFFCALL_K8S_CLUSTER_ID should enable the Kubernetes collector")
	}
	if cfg.Kubernetes.ClusterID != "cluster-1" {
		t.Errorf("cluster id = %q, want cluster-1", cfg.Kubernetes.ClusterID)
	}
}

func TestLoadFromFile(t *testing.T) {
	path := filepath.Join(t.TempDir(), "agent.yaml")
	contents := `
api:
  endpoint: http://localhost:8000/api/v1/metrics/ingest
  api_key: from-file
  timeout: 5s
collection:
  interval: 20s
  batch_size: 50
`
	if err := os.WriteFile(path, []byte(contents), 0o600); err != nil {
		t.Fatalf("WriteFile: %v", err)
	}

	cfg, err := Load(path)
	if err != nil {
		t.Fatalf("Load() error = %v", err)
	}

	if cfg.API.APIKey != "from-file" {
		t.Errorf("api key = %q, want from-file", cfg.API.APIKey)
	}
	if got := cfg.GetCollectionInterval(); got != 20*time.Second {
		t.Errorf("collection interval = %v, want 20s", got)
	}
	if cfg.Collection.BatchSize != 50 {
		t.Errorf("batch size = %d, want 50", cfg.Collection.BatchSize)
	}
	if err := cfg.Validate(); err != nil {
		t.Errorf("Validate() error = %v, want nil", err)
	}
}

func TestValidate(t *testing.T) {
	valid := func() *Config {
		c := DefaultConfig()
		c.API.APIKey = "valid-key"
		return c
	}

	tests := []struct {
		name    string
		mutate  func(*Config)
		wantErr bool
	}{
		{name: "valid", mutate: func(*Config) {}},
		{name: "missing api key", mutate: func(c *Config) { c.API.APIKey = "" }, wantErr: true},
		{name: "missing endpoint", mutate: func(c *Config) { c.API.Endpoint = "" }, wantErr: true},
		{name: "bad collection interval", mutate: func(c *Config) { c.Collection.Interval = "soon" }, wantErr: true},
		{name: "bad api timeout", mutate: func(c *Config) { c.API.Timeout = "quick" }, wantErr: true},
		{name: "bad buffer flush interval", mutate: func(c *Config) { c.Buffer.FlushInterval = "later" }, wantErr: true},
		{
			name: "bad buffer flush interval ignored when buffering is off",
			mutate: func(c *Config) {
				c.Buffer.Enabled = false
				c.Buffer.FlushInterval = "later"
			},
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			cfg := valid()
			tt.mutate(cfg)

			err := cfg.Validate()
			if tt.wantErr && err == nil {
				t.Error("Validate() = nil, want error")
			}
			if !tt.wantErr && err != nil {
				t.Errorf("Validate() = %v, want nil", err)
			}
		})
	}
}
