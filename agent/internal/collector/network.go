package collector

import (
	"strings"
	"time"

	"github.com/shirou/gopsutil/v3/net"
)

// NetworkCollector collects network metrics
type NetworkCollector struct {
	lastCounters  map[string]net.IOCountersStat
	lastCollectAt time.Time
}

// NewNetworkCollector creates a new network collector
func NewNetworkCollector() *NetworkCollector {
	return &NetworkCollector{
		lastCounters: make(map[string]net.IOCountersStat),
	}
}

// Name returns the collector name
func (c *NetworkCollector) Name() string {
	return "network"
}

// IsAvailable checks if network metrics can be collected
func (c *NetworkCollector) IsAvailable() bool {
	_, err := net.IOCounters(false)
	return err == nil
}

// Collect gathers network metrics
func (c *NetworkCollector) Collect() ([]Metric, error) {
	now := time.Now()
	var metrics []Metric

	// Get per-interface counters
	counters, err := net.IOCounters(true)
	if err != nil {
		return nil, err
	}

	// Track totals
	var totalBytesRecv, totalBytesSent uint64
	var totalPacketsRecv, totalPacketsSent uint64
	var totalErrsIn, totalErrsOut uint64

	for _, counter := range counters {
		// Skip loopback and virtual interfaces
		if isVirtualInterface(counter.Name) {
			continue
		}

		totalBytesRecv += counter.BytesRecv
		totalBytesSent += counter.BytesSent
		totalPacketsRecv += counter.PacketsRecv
		totalPacketsSent += counter.PacketsSent
		totalErrsIn += counter.Errin
		totalErrsOut += counter.Errout

		// Calculate rates if we have previous data
		if !c.lastCollectAt.IsZero() {
			elapsed := now.Sub(c.lastCollectAt).Seconds()
			if elapsed > 0 {
				if last, ok := c.lastCounters[counter.Name]; ok {
					bytesInRate := float64(counter.BytesRecv-last.BytesRecv) / elapsed
					bytesOutRate := float64(counter.BytesSent-last.BytesSent) / elapsed
					packetsInRate := float64(counter.PacketsRecv-last.PacketsRecv) / elapsed
					packetsOutRate := float64(counter.PacketsSent-last.PacketsSent) / elapsed

					// Per-interface metrics
					metrics = append(metrics,
						Metric{
							Name:      "system.network.bytes_in",
							Value:     bytesInRate,
							Timestamp: now,
							Unit:      "bytes/s",
							Tags:      map[string]string{"interface": counter.Name},
						},
						Metric{
							Name:      "system.network.bytes_out",
							Value:     bytesOutRate,
							Timestamp: now,
							Unit:      "bytes/s",
							Tags:      map[string]string{"interface": counter.Name},
						},
						Metric{
							Name:      "system.network.packets_in",
							Value:     packetsInRate,
							Timestamp: now,
							Unit:      "packets/s",
							Tags:      map[string]string{"interface": counter.Name},
						},
						Metric{
							Name:      "system.network.packets_out",
							Value:     packetsOutRate,
							Timestamp: now,
							Unit:      "packets/s",
							Tags:      map[string]string{"interface": counter.Name},
						},
					)
				}
			}
		}

		// Error counters (cumulative)
		metrics = append(metrics,
			Metric{
				Name:      "system.network.errors_in",
				Value:     float64(counter.Errin),
				Timestamp: now,
				Tags:      map[string]string{"interface": counter.Name},
			},
			Metric{
				Name:      "system.network.errors_out",
				Value:     float64(counter.Errout),
				Timestamp: now,
				Tags:      map[string]string{"interface": counter.Name},
			},
			Metric{
				Name:      "system.network.drops_in",
				Value:     float64(counter.Dropin),
				Timestamp: now,
				Tags:      map[string]string{"interface": counter.Name},
			},
			Metric{
				Name:      "system.network.drops_out",
				Value:     float64(counter.Dropout),
				Timestamp: now,
				Tags:      map[string]string{"interface": counter.Name},
			},
		)
	}

	// Calculate total rates
	if !c.lastCollectAt.IsZero() {
		elapsed := now.Sub(c.lastCollectAt).Seconds()
		if elapsed > 0 {
			// Sum up last totals
			var lastTotalRecv, lastTotalSent uint64
			for _, counter := range counters {
				if isVirtualInterface(counter.Name) {
					continue
				}
				if last, ok := c.lastCounters[counter.Name]; ok {
					lastTotalRecv += last.BytesRecv
					lastTotalSent += last.BytesSent
				}
			}

			if lastTotalRecv > 0 || lastTotalSent > 0 {
				metrics = append(metrics,
					Metric{
						Name:      "system.network.bytes_in",
						Value:     float64(totalBytesRecv-lastTotalRecv) / elapsed,
						Timestamp: now,
						Unit:      "bytes/s",
						Tags:      map[string]string{"interface": "all"},
					},
					Metric{
						Name:      "system.network.bytes_out",
						Value:     float64(totalBytesSent-lastTotalSent) / elapsed,
						Timestamp: now,
						Unit:      "bytes/s",
						Tags:      map[string]string{"interface": "all"},
					},
				)
			}
		}
	}

	// Store counters for next collection
	c.lastCounters = make(map[string]net.IOCountersStat)
	for _, counter := range counters {
		c.lastCounters[counter.Name] = counter
	}
	c.lastCollectAt = now

	// Connection counts
	conns, err := net.Connections("tcp")
	if err == nil {
		established := 0
		listening := 0
		timeWait := 0

		for _, conn := range conns {
			switch conn.Status {
			case "ESTABLISHED":
				established++
			case "LISTEN":
				listening++
			case "TIME_WAIT":
				timeWait++
			}
		}

		metrics = append(metrics,
			Metric{
				Name:      "system.network.connections.established",
				Value:     float64(established),
				Timestamp: now,
			},
			Metric{
				Name:      "system.network.connections.listening",
				Value:     float64(listening),
				Timestamp: now,
			},
			Metric{
				Name:      "system.network.connections.time_wait",
				Value:     float64(timeWait),
				Timestamp: now,
			},
		)
	}

	return metrics, nil
}

// isVirtualInterface checks if an interface is virtual/loopback
func isVirtualInterface(name string) bool {
	virtual := []string{"lo", "docker", "br-", "veth", "virbr", "vnet"}
	for _, v := range virtual {
		if strings.HasPrefix(name, v) {
			return true
		}
	}
	return name == "lo0" // macOS loopback
}
