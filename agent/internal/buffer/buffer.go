// Package buffer provides local metric buffering when API is unavailable
package buffer

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"sync"

	"github.com/offcallai/agent/internal/collector"
	"github.com/offcallai/agent/internal/config"
)

// Buffer stores metrics locally when the API is unavailable
type Buffer struct {
	config   *config.Config
	metrics  []collector.Metric
	mu       sync.Mutex
	maxSize  int
	filePath string
}

// NewBuffer creates a new metric buffer
func NewBuffer(cfg *config.Config) *Buffer {
	return &Buffer{
		config:   cfg,
		metrics:  make([]collector.Metric, 0),
		maxSize:  cfg.Buffer.MaxSize,
		filePath: cfg.Buffer.FilePath,
	}
}

// Add adds metrics to the buffer
func (b *Buffer) Add(metrics []collector.Metric) error {
	if !b.config.Buffer.Enabled {
		return nil
	}

	b.mu.Lock()
	defer b.mu.Unlock()

	// Add metrics, respecting max size
	space := b.maxSize - len(b.metrics)
	if space <= 0 {
		// Buffer full, drop oldest metrics
		drop := len(metrics)
		if drop > len(b.metrics) {
			drop = len(b.metrics)
		}
		b.metrics = b.metrics[drop:]
	}

	// Add new metrics
	if len(metrics) > b.maxSize {
		// Too many metrics, only keep the latest
		metrics = metrics[len(metrics)-b.maxSize:]
	}

	b.metrics = append(b.metrics, metrics...)

	// Persist to disk
	return b.persist()
}

// Get returns all buffered metrics and clears the buffer
func (b *Buffer) Get() []collector.Metric {
	b.mu.Lock()
	defer b.mu.Unlock()

	metrics := make([]collector.Metric, len(b.metrics))
	copy(metrics, b.metrics)
	return metrics
}

// Clear empties the buffer
func (b *Buffer) Clear() error {
	b.mu.Lock()
	defer b.mu.Unlock()

	b.metrics = make([]collector.Metric, 0)
	return b.persist()
}

// Size returns the number of buffered metrics
func (b *Buffer) Size() int {
	b.mu.Lock()
	defer b.mu.Unlock()
	return len(b.metrics)
}

// Load reads buffered metrics from disk
func (b *Buffer) Load() error {
	if !b.config.Buffer.Enabled {
		return nil
	}

	b.mu.Lock()
	defer b.mu.Unlock()

	data, err := os.ReadFile(b.filePath)
	if err != nil {
		if os.IsNotExist(err) {
			return nil // No buffer file, that's fine
		}
		return fmt.Errorf("failed to read buffer file: %w", err)
	}

	if len(data) == 0 {
		return nil
	}

	var metrics []collector.Metric
	if err := json.Unmarshal(data, &metrics); err != nil {
		// Corrupted file, ignore it
		return nil
	}

	b.metrics = metrics
	return nil
}

// persist writes buffered metrics to disk
func (b *Buffer) persist() error {
	if !b.config.Buffer.Enabled || b.filePath == "" {
		return nil
	}

	// Ensure directory exists
	dir := filepath.Dir(b.filePath)
	if err := os.MkdirAll(dir, 0755); err != nil {
		return fmt.Errorf("failed to create buffer directory: %w", err)
	}

	data, err := json.Marshal(b.metrics)
	if err != nil {
		return fmt.Errorf("failed to marshal buffer: %w", err)
	}

	if err := os.WriteFile(b.filePath, data, 0644); err != nil {
		return fmt.Errorf("failed to write buffer file: %w", err)
	}

	return nil
}

// Remove removes a specific number of metrics from the front of the buffer
func (b *Buffer) Remove(count int) error {
	b.mu.Lock()
	defer b.mu.Unlock()

	if count >= len(b.metrics) {
		b.metrics = make([]collector.Metric, 0)
	} else {
		b.metrics = b.metrics[count:]
	}

	return b.persist()
}
