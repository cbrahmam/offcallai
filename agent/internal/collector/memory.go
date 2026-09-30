package collector

import (
	"time"

	"github.com/shirou/gopsutil/v3/mem"
)

// MemoryCollector collects memory metrics
type MemoryCollector struct{}

// NewMemoryCollector creates a new memory collector
func NewMemoryCollector() *MemoryCollector {
	return &MemoryCollector{}
}

// Name returns the collector name
func (c *MemoryCollector) Name() string {
	return "memory"
}

// IsAvailable checks if memory metrics can be collected
func (c *MemoryCollector) IsAvailable() bool {
	_, err := mem.VirtualMemory()
	return err == nil
}

// Collect gathers memory metrics
func (c *MemoryCollector) Collect() ([]Metric, error) {
	now := time.Now()
	var metrics []Metric

	// Virtual memory
	vmem, err := mem.VirtualMemory()
	if err == nil {
		metrics = append(metrics,
			Metric{
				Name:      "system.memory.total",
				Value:     float64(vmem.Total),
				Timestamp: now,
				Unit:      "bytes",
			},
			Metric{
				Name:      "system.memory.used",
				Value:     float64(vmem.Used),
				Timestamp: now,
				Unit:      "bytes",
			},
			Metric{
				Name:      "system.memory.free",
				Value:     float64(vmem.Free),
				Timestamp: now,
				Unit:      "bytes",
			},
			Metric{
				Name:      "system.memory.available",
				Value:     float64(vmem.Available),
				Timestamp: now,
				Unit:      "bytes",
			},
			Metric{
				Name:      "system.memory.cached",
				Value:     float64(vmem.Cached),
				Timestamp: now,
				Unit:      "bytes",
			},
			Metric{
				Name:      "system.memory.buffers",
				Value:     float64(vmem.Buffers),
				Timestamp: now,
				Unit:      "bytes",
			},
			Metric{
				Name:      "system.memory.usage_percent",
				Value:     vmem.UsedPercent,
				Timestamp: now,
				Unit:      "percent",
			},
		)
	}

	// Swap memory
	swap, err := mem.SwapMemory()
	if err == nil {
		metrics = append(metrics,
			Metric{
				Name:      "system.swap.total",
				Value:     float64(swap.Total),
				Timestamp: now,
				Unit:      "bytes",
			},
			Metric{
				Name:      "system.swap.used",
				Value:     float64(swap.Used),
				Timestamp: now,
				Unit:      "bytes",
			},
			Metric{
				Name:      "system.swap.free",
				Value:     float64(swap.Free),
				Timestamp: now,
				Unit:      "bytes",
			},
			Metric{
				Name:      "system.swap.usage_percent",
				Value:     swap.UsedPercent,
				Timestamp: now,
				Unit:      "percent",
			},
		)
	}

	return metrics, nil
}
