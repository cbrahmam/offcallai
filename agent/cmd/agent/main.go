// OffCall AI Agent - Lightweight monitoring agent for metrics collection
package main

import (
	"flag"
	"fmt"
	"log"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/offcallai/agent/internal/buffer"
	"github.com/offcallai/agent/internal/collector"
	"github.com/offcallai/agent/internal/config"
	"github.com/offcallai/agent/internal/sender"
)

// Version is set at build time
var Version = "0.1.0"

func main() {
	// Parse command line flags
	configPath := flag.String("config", "/etc/offcall-agent/agent.yaml", "Path to config file")
	showVersion := flag.Bool("version", false, "Show version and exit")
	flag.Parse()

	if *showVersion {
		fmt.Printf("offcall-agent version %s\n", Version)
		os.Exit(0)
	}

	// Load configuration
	cfg, err := config.Load(*configPath)
	if err != nil {
		log.Fatalf("Failed to load config: %v", err)
	}

	// Generate agent ID
	agentID := collector.GenerateAgentID()
	log.Printf("Starting OffCall AI Agent v%s (agent_id: %s)", Version, agentID)

	// Get system info
	sysInfo, err := collector.GetSystemInfo()
	if err != nil {
		log.Printf("Warning: Failed to get system info: %v", err)
	}

	// Create sender
	httpSender := sender.NewHTTPSender(cfg, agentID, Version)

	// Create buffer
	metricBuffer := buffer.NewBuffer(cfg)
	if err := metricBuffer.Load(); err != nil {
		log.Printf("Warning: Failed to load buffer: %v", err)
	}

	// Register agent
	registration := collector.HostRegistration{
		Hostname:         sysInfo.Hostname,
		AgentID:          agentID,
		OS:               sysInfo.OS,
		OSVersion:        sysInfo.OSVersion,
		Kernel:           sysInfo.Kernel,
		Arch:             sysInfo.Arch,
		CPUCores:         sysInfo.CPUCores,
		CPUModel:         sysInfo.CPUModel,
		MemoryTotalBytes: sysInfo.MemoryTotalBytes,
		AgentVersion:     Version,
		IPAddress:        collector.GetPrimaryIP(),
		Tags:             cfg.Tags,
	}

	if err := httpSender.RegisterAgent(registration); err != nil {
		log.Printf("Warning: Failed to register agent: %v", err)
	} else {
		log.Printf("Agent registered successfully")
	}

	// Initialize collectors
	var collectors []collector.Collector

	if cfg.Collectors.CPU {
		collectors = append(collectors, collector.NewCPUCollector())
	}
	if cfg.Collectors.Memory {
		collectors = append(collectors, collector.NewMemoryCollector())
	}
	if cfg.Collectors.Disk {
		collectors = append(collectors, collector.NewDiskCollector())
	}
	if cfg.Collectors.Network {
		collectors = append(collectors, collector.NewNetworkCollector())
	}
	if cfg.Collectors.Processes {
		collectors = append(collectors, collector.NewProcessCollector())
	}
	if cfg.Collectors.Docker {
		dockerCollector := collector.NewDockerCollector()
		if dockerCollector.IsAvailable() {
			collectors = append(collectors, dockerCollector)
			log.Printf("Docker collector enabled")
		}
	}

	log.Printf("Enabled collectors: %d", len(collectors))
	for _, c := range collectors {
		log.Printf("Collector %s: available=%v", c.Name(), c.IsAvailable())
	}

	// Initialize log collector if enabled
	var logCollector *collector.LogCollector
	if cfg.Logs.Enabled && len(cfg.Logs.Sources) > 0 {
		var logSources []collector.LogSource
		for _, src := range cfg.Logs.Sources {
			logSources = append(logSources, collector.LogSource{
				Name:      src.Name,
				Path:      src.Path,
				Service:   src.Service,
				Format:    src.Format,
				MultiLine: src.MultiLine,
				Include:   src.Include,
				Exclude:   src.Exclude,
				Tags:      src.Tags,
			})
		}

		logConfig := collector.LogCollectorConfig{
			Enabled:       true,
			Sources:       logSources,
			BatchSize:     cfg.Logs.BatchSize,
			FlushInterval: cfg.GetLogFlushInterval(),
			BufferSize:    cfg.Logs.BufferSize,
		}

		logCollector = collector.NewLogCollector(logConfig, agentID, sysInfo.Hostname, cfg.Tags)
		logCollector.Start()
		log.Printf("Log collector enabled with %d sources", len(logSources))
	}

	// Initialize Kubernetes collector if enabled
	var k8sCollector *collector.KubernetesCollector
	if cfg.Collectors.Kubernetes && cfg.Kubernetes.Enabled {
		clusterName := cfg.Kubernetes.ClusterName
		if clusterName == "" {
			clusterName = collector.GetClusterNameFromEnv()
		}

		k8sConfig := collector.KubernetesConfig{
			Enabled:      true,
			ClusterID:    cfg.Kubernetes.ClusterID,
			ClusterName:  clusterName,
			SyncInterval: cfg.GetK8sSyncInterval(),
			Namespaces:   cfg.Kubernetes.Namespaces,
		}

		// Extract base API URL
		apiBase := cfg.API.Endpoint
		if idx := len(apiBase) - len("/metrics/ingest"); idx > 0 && apiBase[idx:] == "/metrics/ingest" {
			apiBase = apiBase[:idx]
		}

		k8sCollector = collector.NewKubernetesCollector(k8sConfig, apiBase, cfg.API.APIKey, agentID)
		if err := k8sCollector.Start(); err != nil {
			log.Printf("Warning: Failed to start Kubernetes collector: %v", err)
			k8sCollector = nil
		} else {
			log.Printf("Kubernetes collector enabled (cluster: %s, id: %s)", clusterName, cfg.Kubernetes.ClusterID)
		}
	} else if collector.IsRunningInKubernetes() {
		log.Printf("Running in Kubernetes but K8s collector not enabled. Set OFFCALL_K8S_CLUSTER_ID to enable.")
	}

	// Initialize profile collector if enabled
	var profileCollector *collector.ProfileCollector
	if cfg.Profiling.Enabled && len(cfg.Profiling.Targets) > 0 {
		// Convert config targets to collector targets
		var targets []collector.ProfileTarget
		for _, t := range cfg.Profiling.Targets {
			var profileTypes []collector.ProfileType
			for _, pt := range t.ProfileTypes {
				profileTypes = append(profileTypes, collector.ProfileType(pt))
			}
			if len(profileTypes) == 0 {
				profileTypes = []collector.ProfileType{collector.ProfileTypeCPU, collector.ProfileTypeHeap}
			}

			cpuDuration := 30 * time.Second
			if t.CPUDuration != "" {
				if d, err := time.ParseDuration(t.CPUDuration); err == nil {
					cpuDuration = d
				}
			}

			targets = append(targets, collector.ProfileTarget{
				Name:         t.Name,
				URL:          t.URL,
				Service:      t.Service,
				Environment:  t.Environment,
				ProfileTypes: profileTypes,
				CPUDuration:  cpuDuration,
				Labels:       t.Labels,
			})
		}

		profileConfig := collector.ProfileConfig{
			Enabled:        true,
			Targets:        targets,
			Interval:       cfg.GetProfilingInterval(),
			UploadEndpoint: cfg.Profiling.UploadEndpoint,
		}

		// Extract base API URL (remove /metrics/ingest path)
		apiBase := cfg.API.Endpoint
		if idx := len(apiBase) - len("/metrics/ingest"); idx > 0 && apiBase[idx:] == "/metrics/ingest" {
			apiBase = apiBase[:idx]
		}

		profileCollector = collector.NewProfileCollector(profileConfig, apiBase, cfg.API.APIKey, agentID)
		profileCollector.Start()
		log.Printf("Profile collector enabled with %d targets", len(targets))
	}

	// Set up signal handling
	sigChan := make(chan os.Signal, 1)
	signal.Notify(sigChan, syscall.SIGINT, syscall.SIGTERM)

	// Collection ticker
	collectionInterval := cfg.GetCollectionInterval()
	collectionTicker := time.NewTicker(collectionInterval)
	defer collectionTicker.Stop()

	// Heartbeat ticker (every 60 seconds)
	heartbeatTicker := time.NewTicker(60 * time.Second)
	defer heartbeatTicker.Stop()

	// Buffer flush ticker
	flushTicker := time.NewTicker(cfg.GetFlushInterval())
	defer flushTicker.Stop()

	// Log flush ticker (if enabled)
	var logFlushTicker *time.Ticker
	if logCollector != nil {
		logFlushTicker = time.NewTicker(cfg.GetLogFlushInterval())
		defer logFlushTicker.Stop()
	}

	log.Printf("Collection interval: %s", collectionInterval)
	log.Printf("Agent started. Press Ctrl+C to stop.")

	// Main loop
	startTime := time.Now()
	for {
		select {
		case <-sigChan:
			log.Printf("Received shutdown signal, stopping...")
			if k8sCollector != nil {
				k8sCollector.Stop()
			}
			if logCollector != nil {
				logCollector.Stop()
			}
			if profileCollector != nil {
				profileCollector.Stop()
			}
			return

		case <-collectionTicker.C:
			// Collect metrics from all collectors
			var allMetrics []collector.Metric

			for _, c := range collectors {
				if !c.IsAvailable() {
					log.Printf("Collector %s not available", c.Name())
					continue
				}

				metrics, err := c.Collect()
				if err != nil {
					log.Printf("Error collecting %s metrics: %v", c.Name(), err)
					continue
				}
				log.Printf("Collected %d metrics from %s", len(metrics), c.Name())

				// Apply global tags
				for i := range metrics {
					if metrics[i].Tags == nil {
						metrics[i].Tags = make(map[string]string)
					}
					for k, v := range cfg.Tags {
						metrics[i].Tags[k] = v
					}
				}

				allMetrics = append(allMetrics, metrics...)
			}

			if len(allMetrics) == 0 {
				continue
			}

			// Try to send metrics
			resp, err := httpSender.SendMetrics(allMetrics)
			if err != nil {
				log.Printf("Failed to send metrics: %v (buffering %d metrics)", err, len(allMetrics))
				if err := metricBuffer.Add(allMetrics); err != nil {
					log.Printf("Failed to buffer metrics: %v", err)
				}
			} else {
				log.Printf("Sent %d/%d metrics", resp.PointsStored, resp.PointsReceived)
			}

		case <-heartbeatTicker.C:
			// Send heartbeat
			heartbeat := collector.Heartbeat{
				AgentID:       agentID,
				AgentVersion:  Version,
				IPAddress:     collector.GetPrimaryIP(),
				UptimeSeconds: int64(time.Since(startTime).Seconds()),
			}

			if err := httpSender.SendHeartbeat(heartbeat); err != nil {
				log.Printf("Failed to send heartbeat: %v", err)
			}

		case <-flushTicker.C:
			// Try to flush buffered metrics
			bufferedMetrics := metricBuffer.Get()
			if len(bufferedMetrics) == 0 {
				continue
			}

			log.Printf("Attempting to flush %d buffered metrics", len(bufferedMetrics))

			// Send in batches
			batchSize := cfg.Collection.BatchSize
			sent := 0

			for i := 0; i < len(bufferedMetrics); i += batchSize {
				end := i + batchSize
				if end > len(bufferedMetrics) {
					end = len(bufferedMetrics)
				}

				batch := bufferedMetrics[i:end]
				_, err := httpSender.SendMetrics(batch)
				if err != nil {
					log.Printf("Failed to flush buffer batch: %v", err)
					break
				}
				sent += len(batch)
			}

			if sent > 0 {
				if err := metricBuffer.Remove(sent); err != nil {
					log.Printf("Failed to update buffer after flush: %v", err)
				}
				log.Printf("Flushed %d buffered metrics", sent)
			}

		default:
			// Check for logs to send (if log collector is enabled)
			if logCollector != nil && logFlushTicker != nil {
				select {
				case <-logFlushTicker.C:
					logs := logCollector.GetLogs(cfg.Logs.BatchSize)
					if len(logs) > 0 {
						resp, err := httpSender.SendLogs(logs)
						if err != nil {
							log.Printf("Failed to send logs: %v", err)
						} else {
							log.Printf("Sent %d/%d logs", resp.LogsStored, resp.LogsReceived)
						}
					}
				default:
					// No logs to send, continue
				}
			}
			// Small sleep to prevent busy loop
			time.Sleep(100 * time.Millisecond)
		}
	}
}
