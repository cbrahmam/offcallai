package collector

import (
	"testing"
)

func TestCPUCollector(t *testing.T) {
	c := NewCPUCollector()

	if c.Name() != "cpu" {
		t.Errorf("Expected name 'cpu', got '%s'", c.Name())
	}

	if !c.IsAvailable() {
		t.Error("CPU collector should be available")
	}

	metrics, err := c.Collect()
	if err != nil {
		t.Fatalf("Failed to collect CPU metrics: %v", err)
	}

	if len(metrics) == 0 {
		t.Error("Expected at least one CPU metric")
	}

	// Check for expected metrics
	metricNames := make(map[string]bool)
	for _, m := range metrics {
		metricNames[m.Name] = true
	}

	expectedMetrics := []string{
		"system.cpu.usage",
		"system.load.1",
		"system.load.5",
		"system.load.15",
	}

	for _, name := range expectedMetrics {
		if !metricNames[name] {
			t.Errorf("Expected metric '%s' not found", name)
		}
	}
}

func TestMemoryCollector(t *testing.T) {
	c := NewMemoryCollector()

	if c.Name() != "memory" {
		t.Errorf("Expected name 'memory', got '%s'", c.Name())
	}

	if !c.IsAvailable() {
		t.Error("Memory collector should be available")
	}

	metrics, err := c.Collect()
	if err != nil {
		t.Fatalf("Failed to collect memory metrics: %v", err)
	}

	if len(metrics) == 0 {
		t.Error("Expected at least one memory metric")
	}

	// Check for expected metrics
	metricNames := make(map[string]bool)
	for _, m := range metrics {
		metricNames[m.Name] = true
	}

	expectedMetrics := []string{
		"system.memory.total",
		"system.memory.used",
		"system.memory.free",
		"system.memory.usage_percent",
	}

	for _, name := range expectedMetrics {
		if !metricNames[name] {
			t.Errorf("Expected metric '%s' not found", name)
		}
	}
}

func TestDiskCollector(t *testing.T) {
	c := NewDiskCollector()

	if c.Name() != "disk" {
		t.Errorf("Expected name 'disk', got '%s'", c.Name())
	}

	if !c.IsAvailable() {
		t.Error("Disk collector should be available")
	}

	metrics, err := c.Collect()
	if err != nil {
		t.Fatalf("Failed to collect disk metrics: %v", err)
	}

	if len(metrics) == 0 {
		t.Error("Expected at least one disk metric")
	}
}

func TestNetworkCollector(t *testing.T) {
	c := NewNetworkCollector()

	if c.Name() != "network" {
		t.Errorf("Expected name 'network', got '%s'", c.Name())
	}

	if !c.IsAvailable() {
		t.Error("Network collector should be available")
	}

	metrics, err := c.Collect()
	if err != nil {
		t.Fatalf("Failed to collect network metrics: %v", err)
	}

	if len(metrics) == 0 {
		t.Error("Expected at least one network metric")
	}
}

func TestProcessCollector(t *testing.T) {
	c := NewProcessCollector()

	if c.Name() != "process" {
		t.Errorf("Expected name 'process', got '%s'", c.Name())
	}

	if !c.IsAvailable() {
		t.Error("Process collector should be available")
	}

	metrics, err := c.Collect()
	if err != nil {
		t.Fatalf("Failed to collect process metrics: %v", err)
	}

	if len(metrics) == 0 {
		t.Error("Expected at least one process metric")
	}

	// Check for expected metrics
	metricNames := make(map[string]bool)
	for _, m := range metrics {
		metricNames[m.Name] = true
	}

	if !metricNames["system.process.count"] {
		t.Error("Expected metric 'system.process.count' not found")
	}
}

func TestGetSystemInfo(t *testing.T) {
	info, err := GetSystemInfo()
	if err != nil {
		t.Fatalf("Failed to get system info: %v", err)
	}

	if info.Hostname == "" {
		t.Error("Expected hostname to be set")
	}

	if info.OS == "" {
		t.Error("Expected OS to be set")
	}

	if info.Arch == "" {
		t.Error("Expected arch to be set")
	}

	if info.CPUCores == 0 {
		t.Error("Expected CPU cores > 0")
	}

	if info.MemoryTotalBytes == 0 {
		t.Error("Expected memory total > 0")
	}
}

func TestGenerateAgentID(t *testing.T) {
	id := GenerateAgentID()

	if id == "" {
		t.Error("Expected non-empty agent ID")
	}

	// Agent ID should be consistent across calls
	id2 := GenerateAgentID()
	if id != id2 {
		t.Error("Agent ID should be consistent")
	}
}

func TestGetPrimaryIP(t *testing.T) {
	ip := GetPrimaryIP()

	if ip == "" {
		t.Error("Expected non-empty IP address")
	}
}
