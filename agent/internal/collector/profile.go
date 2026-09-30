// Package collector - Profile collector for continuous profiling
package collector

import (
	"bytes"
	"compress/gzip"
	"context"
	"encoding/base64"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"
	"net/url"
	"os"
	"runtime"
	"strings"
	"sync"
	"time"
)

// ProfileType represents the type of profile to collect
type ProfileType string

const (
	ProfileTypeCPU       ProfileType = "cpu"
	ProfileTypeHeap      ProfileType = "heap"
	ProfileTypeGoroutine ProfileType = "goroutine"
	ProfileTypeBlock     ProfileType = "block"
	ProfileTypeMutex     ProfileType = "mutex"
	ProfileTypeAllocs    ProfileType = "allocs"
)

// ProfileTarget represents a pprof endpoint to scrape
type ProfileTarget struct {
	// Name is a friendly name for this target
	Name string `yaml:"name" json:"name"`
	// URL is the base URL (e.g., http://localhost:6060)
	URL string `yaml:"url" json:"url"`
	// Service is the service name for tagging
	Service string `yaml:"service" json:"service"`
	// Environment (production, staging, etc.)
	Environment string `yaml:"environment" json:"environment"`
	// Labels are additional labels to attach to profiles
	Labels map[string]string `yaml:"labels" json:"labels"`
	// Enabled profile types (defaults to cpu, heap if empty)
	ProfileTypes []ProfileType `yaml:"profile_types" json:"profile_types"`
	// CPUDuration is how long to collect CPU profiles (default 30s)
	CPUDuration time.Duration `yaml:"cpu_duration" json:"cpu_duration"`
}

// ProfileConfig contains profiling configuration
type ProfileConfig struct {
	// Enabled turns profiling on/off
	Enabled bool `yaml:"enabled" json:"enabled"`
	// Targets are the pprof endpoints to scrape
	Targets []ProfileTarget `yaml:"targets" json:"targets"`
	// Interval is how often to collect profiles
	Interval time.Duration `yaml:"interval" json:"interval"`
	// UploadEndpoint is the backend endpoint for profile uploads
	UploadEndpoint string `yaml:"upload_endpoint" json:"upload_endpoint"`
	// CollectSelf enables collecting profiles from the agent itself
	CollectSelf bool `yaml:"collect_self" json:"collect_self"`
	// SelfPort is the port to expose pprof on for self-collection
	SelfPort int `yaml:"self_port" json:"self_port"`
}

// DefaultProfileConfig returns sensible defaults
func DefaultProfileConfig() ProfileConfig {
	return ProfileConfig{
		Enabled:        false,
		Interval:       60 * time.Second,
		UploadEndpoint: "/api/v1/profiles/upload",
		CollectSelf:    false,
		SelfPort:       6061,
		Targets:        []ProfileTarget{},
	}
}

// ProfileUpload represents the data sent to the backend
type ProfileUpload struct {
	ServiceName    string            `json:"service_name"`
	ProfileType    string            `json:"profile_type"`
	Format         string            `json:"format"`
	StartTime      time.Time         `json:"start_time"`
	EndTime        time.Time         `json:"end_time,omitempty"`
	DurationMs     int64             `json:"duration_ms,omitempty"`
	Environment    string            `json:"environment,omitempty"`
	Runtime        string            `json:"runtime,omitempty"`
	RuntimeVersion string            `json:"runtime_version,omitempty"`
	ProfileData    string            `json:"profile_data"` // Base64-encoded gzipped data
	Tags           map[string]string `json:"tags,omitempty"`
	Labels         map[string]string `json:"labels,omitempty"`
}

// ProfileCollector collects pprof profiles from configured targets
type ProfileCollector struct {
	config     ProfileConfig
	apiKey     string
	apiBase    string
	agentID    string
	httpClient *http.Client
	mu         sync.Mutex
	stopChan   chan struct{}
	wg         sync.WaitGroup
}

// NewProfileCollector creates a new profile collector
func NewProfileCollector(config ProfileConfig, apiBase, apiKey, agentID string) *ProfileCollector {
	return &ProfileCollector{
		config:  config,
		apiKey:  apiKey,
		apiBase: apiBase,
		agentID: agentID,
		httpClient: &http.Client{
			Timeout: 120 * time.Second, // Long timeout for CPU profiles
		},
		stopChan: make(chan struct{}),
	}
}

// Name returns the collector name
func (p *ProfileCollector) Name() string {
	return "profile"
}

// IsAvailable checks if profile collection is enabled
func (p *ProfileCollector) IsAvailable() bool {
	return p.config.Enabled && len(p.config.Targets) > 0
}

// Start begins the profile collection loop
func (p *ProfileCollector) Start() {
	if !p.IsAvailable() {
		log.Printf("[profile] Profile collector disabled or no targets configured")
		return
	}

	log.Printf("[profile] Starting profile collector with %d targets, interval: %s",
		len(p.config.Targets), p.config.Interval)

	p.wg.Add(1)
	go p.collectionLoop()
}

// Stop stops the profile collection loop
func (p *ProfileCollector) Stop() {
	close(p.stopChan)
	p.wg.Wait()
	log.Printf("[profile] Profile collector stopped")
}

// collectionLoop runs the main collection loop
func (p *ProfileCollector) collectionLoop() {
	defer p.wg.Done()

	// Initial collection after a short delay
	time.Sleep(5 * time.Second)
	p.collectAllTargets()

	ticker := time.NewTicker(p.config.Interval)
	defer ticker.Stop()

	for {
		select {
		case <-p.stopChan:
			return
		case <-ticker.C:
			p.collectAllTargets()
		}
	}
}

// collectAllTargets collects profiles from all configured targets
func (p *ProfileCollector) collectAllTargets() {
	var wg sync.WaitGroup

	for _, target := range p.config.Targets {
		wg.Add(1)
		go func(t ProfileTarget) {
			defer wg.Done()
			p.collectTarget(t)
		}(target)
	}

	wg.Wait()
}

// collectTarget collects all configured profile types from a target
func (p *ProfileCollector) collectTarget(target ProfileTarget) {
	profileTypes := target.ProfileTypes
	if len(profileTypes) == 0 {
		// Default to CPU and heap profiles
		profileTypes = []ProfileType{ProfileTypeCPU, ProfileTypeHeap}
	}

	for _, pt := range profileTypes {
		if err := p.collectProfile(target, pt); err != nil {
			log.Printf("[profile] Failed to collect %s profile from %s: %v",
				pt, target.Name, err)
		}
	}
}

// collectProfile collects a single profile type from a target
func (p *ProfileCollector) collectProfile(target ProfileTarget, profileType ProfileType) error {
	// Build the pprof URL
	pprofURL, err := p.buildPprofURL(target.URL, profileType, target.CPUDuration)
	if err != nil {
		return fmt.Errorf("failed to build pprof URL: %w", err)
	}

	startTime := time.Now()

	// Fetch the profile
	ctx, cancel := context.WithTimeout(context.Background(), 90*time.Second)
	defer cancel()

	req, err := http.NewRequestWithContext(ctx, "GET", pprofURL, nil)
	if err != nil {
		return fmt.Errorf("failed to create request: %w", err)
	}

	resp, err := p.httpClient.Do(req)
	if err != nil {
		return fmt.Errorf("failed to fetch profile: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		body, _ := io.ReadAll(io.LimitReader(resp.Body, 1024))
		return fmt.Errorf("pprof endpoint returned %d: %s", resp.StatusCode, string(body))
	}

	// Read the profile data
	profileData, err := io.ReadAll(resp.Body)
	if err != nil {
		return fmt.Errorf("failed to read profile data: %w", err)
	}

	endTime := time.Now()

	if len(profileData) == 0 {
		return fmt.Errorf("empty profile data received")
	}

	// Compress the profile
	compressedData, err := compressProfile(profileData)
	if err != nil {
		return fmt.Errorf("failed to compress profile: %w", err)
	}

	// Build labels
	labels := make(map[string]string)
	for k, v := range target.Labels {
		labels[k] = v
	}
	labels["agent_id"] = p.agentID

	// Upload the profile
	upload := ProfileUpload{
		ServiceName:    target.Service,
		ProfileType:    string(profileType),
		Format:         "pprof",
		StartTime:      startTime,
		EndTime:        endTime,
		DurationMs:     endTime.Sub(startTime).Milliseconds(),
		Environment:    target.Environment,
		Runtime:        "go",
		RuntimeVersion: runtime.Version(),
		ProfileData:    base64.StdEncoding.EncodeToString(compressedData),
		Tags: map[string]string{
			"target": target.Name,
			"url":    target.URL,
		},
		Labels: labels,
	}

	if err := p.uploadProfile(upload); err != nil {
		return fmt.Errorf("failed to upload profile: %w", err)
	}

	log.Printf("[profile] Collected and uploaded %s profile from %s (%d bytes compressed)",
		profileType, target.Name, len(compressedData))

	return nil
}

// buildPprofURL builds the pprof endpoint URL for a given profile type
func (p *ProfileCollector) buildPprofURL(baseURL string, profileType ProfileType, cpuDuration time.Duration) (string, error) {
	u, err := url.Parse(baseURL)
	if err != nil {
		return "", err
	}

	// Add debug/pprof path
	var path string
	var params url.Values

	switch profileType {
	case ProfileTypeCPU:
		path = "/debug/pprof/profile"
		params = url.Values{}
		if cpuDuration > 0 {
			params.Set("seconds", fmt.Sprintf("%d", int(cpuDuration.Seconds())))
		} else {
			params.Set("seconds", "30") // Default 30 seconds
		}
	case ProfileTypeHeap:
		path = "/debug/pprof/heap"
		params = url.Values{}
	case ProfileTypeGoroutine:
		path = "/debug/pprof/goroutine"
		params = url.Values{}
	case ProfileTypeBlock:
		path = "/debug/pprof/block"
		params = url.Values{}
	case ProfileTypeMutex:
		path = "/debug/pprof/mutex"
		params = url.Values{}
	case ProfileTypeAllocs:
		path = "/debug/pprof/allocs"
		params = url.Values{}
	default:
		return "", fmt.Errorf("unknown profile type: %s", profileType)
	}

	u.Path = path
	if len(params) > 0 {
		u.RawQuery = params.Encode()
	}

	return u.String(), nil
}

// uploadProfile sends the profile to the backend
func (p *ProfileCollector) uploadProfile(upload ProfileUpload) error {
	jsonData, err := json.Marshal(upload)
	if err != nil {
		return fmt.Errorf("failed to marshal upload: %w", err)
	}

	uploadURL := strings.TrimSuffix(p.apiBase, "/") + p.config.UploadEndpoint

	req, err := http.NewRequest("POST", uploadURL, bytes.NewReader(jsonData))
	if err != nil {
		return fmt.Errorf("failed to create request: %w", err)
	}

	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("X-API-Key", p.apiKey)
	req.Header.Set("User-Agent", "offcall-agent/"+p.agentID)

	resp, err := p.httpClient.Do(req)
	if err != nil {
		return fmt.Errorf("failed to send request: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK && resp.StatusCode != http.StatusCreated {
		body, _ := io.ReadAll(io.LimitReader(resp.Body, 1024))
		return fmt.Errorf("upload failed with status %d: %s", resp.StatusCode, string(body))
	}

	return nil
}

// compressProfile compresses profile data using gzip
func compressProfile(data []byte) ([]byte, error) {
	var buf bytes.Buffer
	gz := gzip.NewWriter(&buf)

	if _, err := gz.Write(data); err != nil {
		return nil, err
	}

	if err := gz.Close(); err != nil {
		return nil, err
	}

	return buf.Bytes(), nil
}

// DiscoverPprofEndpoints attempts to discover pprof endpoints in running containers
// This is a basic implementation - can be extended for more sophisticated discovery
func DiscoverPprofEndpoints() []ProfileTarget {
	var targets []ProfileTarget

	// Check common pprof ports
	commonPorts := []int{6060, 6061, 8080, 8081, 9090}
	commonPaths := []string{"/debug/pprof/"}

	for _, port := range commonPorts {
		for _, path := range commonPaths {
			testURL := fmt.Sprintf("http://localhost:%d%s", port, path)

			client := &http.Client{Timeout: 2 * time.Second}
			resp, err := client.Get(testURL)
			if err != nil {
				continue
			}
			resp.Body.Close()

			if resp.StatusCode == http.StatusOK {
				target := ProfileTarget{
					Name:         fmt.Sprintf("localhost:%d", port),
					URL:          fmt.Sprintf("http://localhost:%d", port),
					Service:      "discovered",
					Environment:  os.Getenv("ENVIRONMENT"),
					ProfileTypes: []ProfileType{ProfileTypeCPU, ProfileTypeHeap},
					CPUDuration:  30 * time.Second,
				}
				targets = append(targets, target)
				log.Printf("[profile] Discovered pprof endpoint at %s", testURL)
			}
		}
	}

	return targets
}

// CollectLocalProfile collects a profile from the current process
// Useful for profiling the agent itself
func CollectLocalProfile(profileType ProfileType, duration time.Duration) ([]byte, error) {
	switch profileType {
	case ProfileTypeCPU:
		return collectLocalCPUProfile(duration)
	case ProfileTypeHeap:
		return collectLocalHeapProfile()
	case ProfileTypeGoroutine:
		return collectLocalGoroutineProfile()
	default:
		return nil, fmt.Errorf("unsupported local profile type: %s", profileType)
	}
}

func collectLocalCPUProfile(duration time.Duration) ([]byte, error) {
	var buf bytes.Buffer

	// Import runtime/pprof at runtime to avoid circular dependencies
	// In production, you'd use pprof.StartCPUProfile/StopCPUProfile

	// For now, return an error indicating this needs runtime/pprof
	return buf.Bytes(), fmt.Errorf("local CPU profiling requires runtime/pprof import")
}

func collectLocalHeapProfile() ([]byte, error) {
	var buf bytes.Buffer
	// Similar to CPU profile - needs runtime/pprof
	return buf.Bytes(), fmt.Errorf("local heap profiling requires runtime/pprof import")
}

func collectLocalGoroutineProfile() ([]byte, error) {
	var buf bytes.Buffer
	// Similar to CPU profile - needs runtime/pprof
	return buf.Bytes(), fmt.Errorf("local goroutine profiling requires runtime/pprof import")
}
