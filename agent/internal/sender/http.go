// Package sender handles sending metrics to the OffCall AI API
package sender

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"time"

	"github.com/offcallai/agent/internal/collector"
	"github.com/offcallai/agent/internal/config"
)

// HTTPSender sends metrics to the API via HTTP
type HTTPSender struct {
	config  *config.Config
	client  *http.Client
	agentID string
	version string
}

// APIResponse represents the API response
type APIResponse struct {
	Success        bool     `json:"success"`
	PointsReceived int      `json:"points_received"`
	PointsStored   int      `json:"points_stored"`
	HostID         string   `json:"host_id"`
	Errors         []string `json:"errors,omitempty"`
}

// NewHTTPSender creates a new HTTP sender
func NewHTTPSender(cfg *config.Config, agentID, version string) *HTTPSender {
	return &HTTPSender{
		config:  cfg,
		agentID: agentID,
		version: version,
		client: &http.Client{
			Timeout: cfg.GetAPITimeout(),
		},
	}
}

// SendMetrics sends a batch of metrics to the API
func (s *HTTPSender) SendMetrics(metrics []collector.Metric) (*APIResponse, error) {
	batch := collector.MetricBatch{
		AgentID:      s.agentID,
		Metrics:      metrics,
		AgentVersion: s.version,
		CollectedAt:  time.Now(),
	}

	body, err := json.Marshal(batch)
	if err != nil {
		return nil, fmt.Errorf("failed to marshal metrics: %w", err)
	}

	req, err := http.NewRequest("POST", s.config.API.Endpoint, bytes.NewReader(body))
	if err != nil {
		return nil, fmt.Errorf("failed to create request: %w", err)
	}

	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("X-API-Key", s.config.API.APIKey)
	req.Header.Set("User-Agent", fmt.Sprintf("offcall-agent/%s", s.version))

	resp, err := s.client.Do(req)
	if err != nil {
		return nil, fmt.Errorf("failed to send request: %w", err)
	}
	defer resp.Body.Close()

	respBody, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("failed to read response: %w", err)
	}

	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("API returned status %d: %s", resp.StatusCode, string(respBody))
	}

	var apiResp APIResponse
	if err := json.Unmarshal(respBody, &apiResp); err != nil {
		return nil, fmt.Errorf("failed to parse response: %w", err)
	}

	return &apiResp, nil
}

// RegisterAgent registers the agent with the API
func (s *HTTPSender) RegisterAgent(registration collector.HostRegistration) error {
	body, err := json.Marshal(registration)
	if err != nil {
		return fmt.Errorf("failed to marshal registration: %w", err)
	}

	endpoint := s.getRegisterEndpoint()
	req, err := http.NewRequest("POST", endpoint, bytes.NewReader(body))
	if err != nil {
		return fmt.Errorf("failed to create request: %w", err)
	}

	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("X-API-Key", s.config.API.APIKey)
	req.Header.Set("User-Agent", fmt.Sprintf("offcall-agent/%s", s.version))

	resp, err := s.client.Do(req)
	if err != nil {
		return fmt.Errorf("failed to send request: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		respBody, _ := io.ReadAll(resp.Body)
		return fmt.Errorf("registration failed with status %d: %s", resp.StatusCode, string(respBody))
	}

	return nil
}

// SendHeartbeat sends a heartbeat to the API
func (s *HTTPSender) SendHeartbeat(heartbeat collector.Heartbeat) error {
	body, err := json.Marshal(heartbeat)
	if err != nil {
		return fmt.Errorf("failed to marshal heartbeat: %w", err)
	}

	endpoint := s.getHeartbeatEndpoint()
	req, err := http.NewRequest("POST", endpoint, bytes.NewReader(body))
	if err != nil {
		return fmt.Errorf("failed to create request: %w", err)
	}

	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("X-API-Key", s.config.API.APIKey)
	req.Header.Set("User-Agent", fmt.Sprintf("offcall-agent/%s", s.version))

	resp, err := s.client.Do(req)
	if err != nil {
		return fmt.Errorf("failed to send request: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		respBody, _ := io.ReadAll(resp.Body)
		return fmt.Errorf("heartbeat failed with status %d: %s", resp.StatusCode, string(respBody))
	}

	return nil
}

// getRegisterEndpoint returns the agent registration endpoint
func (s *HTTPSender) getRegisterEndpoint() string {
	// Replace /metrics/ingest with /hosts/agent/register
	base := s.config.API.Endpoint
	if len(base) > len("/metrics/ingest") {
		base = base[:len(base)-len("/metrics/ingest")]
	}
	return base + "/hosts/agent/register"
}

// getHeartbeatEndpoint returns the heartbeat endpoint
func (s *HTTPSender) getHeartbeatEndpoint() string {
	base := s.config.API.Endpoint
	if len(base) > len("/metrics/ingest") {
		base = base[:len(base)-len("/metrics/ingest")]
	}
	return base + "/hosts/agent/heartbeat"
}

// LogAPIResponse represents the API response for log ingestion
type LogAPIResponse struct {
	Success      bool     `json:"success"`
	LogsReceived int      `json:"logs_received"`
	LogsStored   int      `json:"logs_stored"`
	Errors       []string `json:"errors,omitempty"`
}

// SendLogs sends a batch of logs to the API
func (s *HTTPSender) SendLogs(logs []collector.LogEntry) (*LogAPIResponse, error) {
	batch := collector.LogBatch{
		AgentID:      s.agentID,
		Logs:         logs,
		AgentVersion: s.version,
		CollectedAt:  time.Now(),
	}

	body, err := json.Marshal(batch)
	if err != nil {
		return nil, fmt.Errorf("failed to marshal logs: %w", err)
	}

	endpoint := s.getLogsEndpoint()
	req, err := http.NewRequest("POST", endpoint, bytes.NewReader(body))
	if err != nil {
		return nil, fmt.Errorf("failed to create request: %w", err)
	}

	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("X-API-Key", s.config.API.APIKey)
	req.Header.Set("User-Agent", fmt.Sprintf("offcall-agent/%s", s.version))

	resp, err := s.client.Do(req)
	if err != nil {
		return nil, fmt.Errorf("failed to send request: %w", err)
	}
	defer resp.Body.Close()

	respBody, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("failed to read response: %w", err)
	}

	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("API returned status %d: %s", resp.StatusCode, string(respBody))
	}

	var apiResp LogAPIResponse
	if err := json.Unmarshal(respBody, &apiResp); err != nil {
		return nil, fmt.Errorf("failed to parse response: %w", err)
	}

	return &apiResp, nil
}

// getLogsEndpoint returns the logs ingestion endpoint
func (s *HTTPSender) getLogsEndpoint() string {
	base := s.config.API.Endpoint
	if len(base) > len("/metrics/ingest") {
		base = base[:len(base)-len("/metrics/ingest")]
	}
	return base + "/logs/ingest"
}
