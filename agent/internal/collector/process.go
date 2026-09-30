package collector

import (
	"sort"
	"time"

	"github.com/shirou/gopsutil/v3/process"
)

// ProcessCollector collects process metrics
type ProcessCollector struct {
	topN int // Number of top processes to report
}

// NewProcessCollector creates a new process collector
func NewProcessCollector() *ProcessCollector {
	return &ProcessCollector{
		topN: 10, // Report top 10 processes by CPU/memory
	}
}

// Name returns the collector name
func (c *ProcessCollector) Name() string {
	return "process"
}

// IsAvailable checks if process metrics can be collected
func (c *ProcessCollector) IsAvailable() bool {
	_, err := process.Processes()
	return err == nil
}

// ProcessInfo holds info about a process for sorting
type ProcessInfo struct {
	PID        int32
	Name       string
	CPUPercent float64
	MemPercent float32
	MemRSS     uint64
}

// Collect gathers process metrics
func (c *ProcessCollector) Collect() ([]Metric, error) {
	now := time.Now()
	var metrics []Metric

	procs, err := process.Processes()
	if err != nil {
		return nil, err
	}

	// Count process states
	total := len(procs)
	running := 0
	sleeping := 0
	zombie := 0

	var procInfos []ProcessInfo

	for _, p := range procs {
		status, err := p.Status()
		if err == nil {
			for _, s := range status {
				switch s {
				case "R", "running":
					running++
				case "S", "sleeping", "idle":
					sleeping++
				case "Z", "zombie":
					zombie++
				}
			}
		}

		// Get CPU and memory usage
		cpuPct, _ := p.CPUPercent()
		memPct, _ := p.MemoryPercent()
		memInfo, _ := p.MemoryInfo()
		name, _ := p.Name()

		var memRSS uint64
		if memInfo != nil {
			memRSS = memInfo.RSS
		}

		procInfos = append(procInfos, ProcessInfo{
			PID:        p.Pid,
			Name:       name,
			CPUPercent: cpuPct,
			MemPercent: memPct,
			MemRSS:     memRSS,
		})
	}

	// Process count metrics
	metrics = append(metrics,
		Metric{
			Name:      "system.process.count",
			Value:     float64(total),
			Timestamp: now,
		},
		Metric{
			Name:      "system.process.running",
			Value:     float64(running),
			Timestamp: now,
		},
		Metric{
			Name:      "system.process.sleeping",
			Value:     float64(sleeping),
			Timestamp: now,
		},
		Metric{
			Name:      "system.process.zombie",
			Value:     float64(zombie),
			Timestamp: now,
		},
	)

	// Top processes by CPU
	sort.Slice(procInfos, func(i, j int) bool {
		return procInfos[i].CPUPercent > procInfos[j].CPUPercent
	})

	for i := 0; i < c.topN && i < len(procInfos); i++ {
		p := procInfos[i]
		if p.CPUPercent > 0 {
			metrics = append(metrics, Metric{
				Name:      "system.process.top_cpu",
				Value:     p.CPUPercent,
				Timestamp: now,
				Unit:      "percent",
				Tags: map[string]string{
					"process": p.Name,
					"pid":     string(rune(p.PID)),
					"rank":    string(rune('0' + i + 1)),
				},
			})
		}
	}

	// Top processes by memory
	sort.Slice(procInfos, func(i, j int) bool {
		return procInfos[i].MemRSS > procInfos[j].MemRSS
	})

	for i := 0; i < c.topN && i < len(procInfos); i++ {
		p := procInfos[i]
		if p.MemRSS > 0 {
			metrics = append(metrics, Metric{
				Name:      "system.process.top_memory",
				Value:     float64(p.MemRSS),
				Timestamp: now,
				Unit:      "bytes",
				Tags: map[string]string{
					"process": p.Name,
					"pid":     string(rune(p.PID)),
					"rank":    string(rune('0' + i + 1)),
				},
			})
		}
	}

	return metrics, nil
}
