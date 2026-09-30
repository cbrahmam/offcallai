package collector

import (
	"time"

	"github.com/shirou/gopsutil/v3/cpu"
	"github.com/shirou/gopsutil/v3/load"
)

// CPUCollector collects CPU metrics
type CPUCollector struct {
	lastTimes []cpu.TimesStat
}

// NewCPUCollector creates a new CPU collector
func NewCPUCollector() *CPUCollector {
	return &CPUCollector{}
}

// Name returns the collector name
func (c *CPUCollector) Name() string {
	return "cpu"
}

// IsAvailable checks if CPU metrics can be collected
func (c *CPUCollector) IsAvailable() bool {
	_, err := cpu.Times(false)
	return err == nil
}

// Collect gathers CPU metrics
func (c *CPUCollector) Collect() ([]Metric, error) {
	now := time.Now()
	var metrics []Metric

	// Get CPU usage percentages
	percentages, err := cpu.Percent(0, false)
	if err == nil && len(percentages) > 0 {
		metrics = append(metrics, Metric{
			Name:      "system.cpu.usage",
			Value:     percentages[0],
			Timestamp: now,
			Unit:      "percent",
		})
	}

	// Get per-CPU percentages
	perCPU, err := cpu.Percent(0, true)
	if err == nil {
		for i, pct := range perCPU {
			metrics = append(metrics, Metric{
				Name:      "system.cpu.usage.per_cpu",
				Value:     pct,
				Timestamp: now,
				Unit:      "percent",
				Tags:      map[string]string{"cpu": string(rune('0' + i))},
			})
		}
	}

	// Get CPU times breakdown
	times, err := cpu.Times(false)
	if err == nil && len(times) > 0 {
		t := times[0]
		total := t.User + t.System + t.Idle + t.Nice + t.Iowait + t.Irq + t.Softirq + t.Steal

		if total > 0 {
			metrics = append(metrics, Metric{
				Name:      "system.cpu.user",
				Value:     (t.User / total) * 100,
				Timestamp: now,
				Unit:      "percent",
			})
			metrics = append(metrics, Metric{
				Name:      "system.cpu.system",
				Value:     (t.System / total) * 100,
				Timestamp: now,
				Unit:      "percent",
			})
			metrics = append(metrics, Metric{
				Name:      "system.cpu.idle",
				Value:     (t.Idle / total) * 100,
				Timestamp: now,
				Unit:      "percent",
			})
			metrics = append(metrics, Metric{
				Name:      "system.cpu.iowait",
				Value:     (t.Iowait / total) * 100,
				Timestamp: now,
				Unit:      "percent",
			})
		}
	}

	// Get load averages
	loadAvg, err := load.Avg()
	if err == nil {
		metrics = append(metrics, Metric{
			Name:      "system.load.1",
			Value:     loadAvg.Load1,
			Timestamp: now,
		})
		metrics = append(metrics, Metric{
			Name:      "system.load.5",
			Value:     loadAvg.Load5,
			Timestamp: now,
		})
		metrics = append(metrics, Metric{
			Name:      "system.load.15",
			Value:     loadAvg.Load15,
			Timestamp: now,
		})
	}

	return metrics, nil
}
