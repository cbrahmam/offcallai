package collector

import (
	"strings"
	"time"

	"github.com/shirou/gopsutil/v3/disk"
)

// DiskCollector collects disk metrics
type DiskCollector struct {
	lastIOCounters map[string]disk.IOCountersStat
	lastCollectAt  time.Time
}

// NewDiskCollector creates a new disk collector
func NewDiskCollector() *DiskCollector {
	return &DiskCollector{
		lastIOCounters: make(map[string]disk.IOCountersStat),
	}
}

// Name returns the collector name
func (c *DiskCollector) Name() string {
	return "disk"
}

// IsAvailable checks if disk metrics can be collected
func (c *DiskCollector) IsAvailable() bool {
	_, err := disk.Partitions(false)
	return err == nil
}

// Collect gathers disk metrics
func (c *DiskCollector) Collect() ([]Metric, error) {
	now := time.Now()
	var metrics []Metric

	// Get disk partitions
	partitions, err := disk.Partitions(false)
	if err != nil {
		return nil, err
	}

	// Track totals across all disks
	var totalSize, totalUsed, totalFree uint64

	for _, partition := range partitions {
		// Skip pseudo filesystems
		if isVirtualFS(partition.Fstype) {
			continue
		}

		usage, err := disk.Usage(partition.Mountpoint)
		if err != nil {
			continue
		}

		// Clean up device name for tag
		device := cleanDeviceName(partition.Device)

		// Per-mount metrics
		metrics = append(metrics,
			Metric{
				Name:      "system.disk.total",
				Value:     float64(usage.Total),
				Timestamp: now,
				Unit:      "bytes",
				Tags:      map[string]string{"device": device, "mount": partition.Mountpoint},
			},
			Metric{
				Name:      "system.disk.used",
				Value:     float64(usage.Used),
				Timestamp: now,
				Unit:      "bytes",
				Tags:      map[string]string{"device": device, "mount": partition.Mountpoint},
			},
			Metric{
				Name:      "system.disk.free",
				Value:     float64(usage.Free),
				Timestamp: now,
				Unit:      "bytes",
				Tags:      map[string]string{"device": device, "mount": partition.Mountpoint},
			},
			Metric{
				Name:      "system.disk.usage_percent",
				Value:     usage.UsedPercent,
				Timestamp: now,
				Unit:      "percent",
				Tags:      map[string]string{"device": device, "mount": partition.Mountpoint},
			},
		)

		totalSize += usage.Total
		totalUsed += usage.Used
		totalFree += usage.Free
	}

	// Total disk metrics (aggregate)
	if totalSize > 0 {
		metrics = append(metrics,
			Metric{
				Name:      "system.disk.total",
				Value:     float64(totalSize),
				Timestamp: now,
				Unit:      "bytes",
				Tags:      map[string]string{"device": "all"},
			},
			Metric{
				Name:      "system.disk.used",
				Value:     float64(totalUsed),
				Timestamp: now,
				Unit:      "bytes",
				Tags:      map[string]string{"device": "all"},
			},
			Metric{
				Name:      "system.disk.usage_percent",
				Value:     float64(totalUsed) / float64(totalSize) * 100,
				Timestamp: now,
				Unit:      "percent",
				Tags:      map[string]string{"device": "all"},
			},
		)
	}

	// Disk I/O counters
	ioCounters, err := disk.IOCounters()
	if err == nil && !c.lastCollectAt.IsZero() {
		elapsed := now.Sub(c.lastCollectAt).Seconds()
		if elapsed > 0 {
			for device, counter := range ioCounters {
				if last, ok := c.lastIOCounters[device]; ok {
					readBytes := float64(counter.ReadBytes-last.ReadBytes) / elapsed
					writeBytes := float64(counter.WriteBytes-last.WriteBytes) / elapsed
					readOps := float64(counter.ReadCount-last.ReadCount) / elapsed
					writeOps := float64(counter.WriteCount-last.WriteCount) / elapsed

					metrics = append(metrics,
						Metric{
							Name:      "system.disk.read_bytes",
							Value:     readBytes,
							Timestamp: now,
							Unit:      "bytes/s",
							Tags:      map[string]string{"device": device},
						},
						Metric{
							Name:      "system.disk.write_bytes",
							Value:     writeBytes,
							Timestamp: now,
							Unit:      "bytes/s",
							Tags:      map[string]string{"device": device},
						},
						Metric{
							Name:      "system.disk.read_ops",
							Value:     readOps,
							Timestamp: now,
							Unit:      "ops/s",
							Tags:      map[string]string{"device": device},
						},
						Metric{
							Name:      "system.disk.write_ops",
							Value:     writeOps,
							Timestamp: now,
							Unit:      "ops/s",
							Tags:      map[string]string{"device": device},
						},
					)
				}
			}
		}
	}

	// Store for next collection
	c.lastIOCounters = ioCounters
	c.lastCollectAt = now

	return metrics, nil
}

// isVirtualFS checks if a filesystem type is virtual/pseudo
func isVirtualFS(fstype string) bool {
	virtual := []string{"tmpfs", "devtmpfs", "devfs", "iso9660", "overlay", "aufs", "squashfs", "proc", "sysfs", "cgroup"}
	for _, v := range virtual {
		if fstype == v {
			return true
		}
	}
	return false
}

// cleanDeviceName cleans up device names for tags
func cleanDeviceName(device string) string {
	// Remove /dev/ prefix
	device = strings.TrimPrefix(device, "/dev/")
	return device
}
