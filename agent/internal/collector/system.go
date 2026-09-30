package collector

import (
	"net"
	"os"
	"runtime"

	"github.com/shirou/gopsutil/v3/cpu"
	"github.com/shirou/gopsutil/v3/host"
	"github.com/shirou/gopsutil/v3/mem"
)

// GetSystemInfo gathers information about the host system
func GetSystemInfo() (*SystemInfo, error) {
	info := &SystemInfo{
		Arch: runtime.GOARCH,
	}

	// Get hostname
	hostname, err := os.Hostname()
	if err == nil {
		info.Hostname = hostname
	}

	// Get host info
	hostInfo, err := host.Info()
	if err == nil {
		info.OS = hostInfo.Platform
		info.OSVersion = hostInfo.PlatformVersion
		info.Kernel = hostInfo.KernelVersion
	}

	// Get CPU info
	cpuInfo, err := cpu.Info()
	if err == nil && len(cpuInfo) > 0 {
		info.CPUModel = cpuInfo[0].ModelName
	}

	// Get CPU cores
	cores, err := cpu.Counts(true)
	if err == nil {
		info.CPUCores = cores
	}

	// Get memory
	memInfo, err := mem.VirtualMemory()
	if err == nil {
		info.MemoryTotalBytes = memInfo.Total
	}

	return info, nil
}

// GetPrimaryIP returns the primary IP address of the host
func GetPrimaryIP() string {
	// Try to get the IP by dialing an external address
	conn, err := net.Dial("udp", "8.8.8.8:80")
	if err != nil {
		return ""
	}
	defer conn.Close()

	localAddr := conn.LocalAddr().(*net.UDPAddr)
	return localAddr.IP.String()
}

// GenerateAgentID creates a unique agent ID based on system characteristics
func GenerateAgentID() string {
	hostname, _ := os.Hostname()

	// Use hostname + first MAC address as a stable ID
	interfaces, err := net.Interfaces()
	if err == nil {
		for _, iface := range interfaces {
			// Skip loopback and virtual interfaces
			if iface.Flags&net.FlagLoopback != 0 {
				continue
			}
			if iface.HardwareAddr == nil || len(iface.HardwareAddr) == 0 {
				continue
			}
			// Found a valid MAC address
			return hostname + "-" + iface.HardwareAddr.String()
		}
	}

	// Fallback: just use hostname
	return hostname
}
