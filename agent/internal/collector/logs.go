// Package collector - Log collection from files
package collector

import (
	"bufio"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"os"
	"path/filepath"
	"regexp"
	"strings"
	"sync"
	"time"
)

// LogCollectorConfig holds log collection configuration
type LogCollectorConfig struct {
	Enabled       bool
	Sources       []LogSource
	BatchSize     int
	FlushInterval time.Duration
	BufferSize    int
}

// LogSource represents a log source to collect from
type LogSource struct {
	Name      string            // Friendly name for this source
	Path      string            // File path or glob pattern (e.g., /var/log/*.log)
	Service   string            // Service name to tag logs with
	Format    string            // auto, json, syslog, plain
	MultiLine bool              // Enable multi-line log parsing
	Include   []string          // Patterns to include (regex)
	Exclude   []string          // Patterns to exclude (regex)
	Tags      map[string]string // Additional tags for logs from this source
}

// LogCollector collects logs from configured sources
type LogCollector struct {
	config     LogCollectorConfig
	agentID    string
	hostname   string
	globalTags map[string]string

	// Channel for collected logs
	logChan chan LogEntry

	// File tracking
	filePositions map[string]int64
	fileMu        sync.RWMutex

	// Compiled regex patterns per source
	includePatterns map[string][]*regexp.Regexp
	excludePatterns map[string][]*regexp.Regexp

	// State
	running  bool
	stopChan chan struct{}
	wg       sync.WaitGroup
}

// NewLogCollector creates a new log collector
func NewLogCollector(config LogCollectorConfig, agentID, hostname string, globalTags map[string]string) *LogCollector {
	lc := &LogCollector{
		config:          config,
		agentID:         agentID,
		hostname:        hostname,
		globalTags:      globalTags,
		logChan:         make(chan LogEntry, config.BufferSize),
		filePositions:   make(map[string]int64),
		includePatterns: make(map[string][]*regexp.Regexp),
		excludePatterns: make(map[string][]*regexp.Regexp),
		stopChan:        make(chan struct{}),
	}

	// Compile regex patterns
	for _, source := range config.Sources {
		for _, pattern := range source.Include {
			if re, err := regexp.Compile(pattern); err == nil {
				lc.includePatterns[source.Name] = append(lc.includePatterns[source.Name], re)
			}
		}
		for _, pattern := range source.Exclude {
			if re, err := regexp.Compile(pattern); err == nil {
				lc.excludePatterns[source.Name] = append(lc.excludePatterns[source.Name], re)
			}
		}
	}

	return lc
}

// Start begins log collection
func (lc *LogCollector) Start() {
	if !lc.config.Enabled || len(lc.config.Sources) == 0 {
		return
	}

	lc.running = true

	for _, source := range lc.config.Sources {
		lc.wg.Add(1)
		go lc.tailSource(source)
	}

	log.Printf("Log collector started with %d sources", len(lc.config.Sources))
}

// Stop stops log collection
func (lc *LogCollector) Stop() {
	if !lc.running {
		return
	}

	close(lc.stopChan)
	lc.wg.Wait()
	lc.running = false
	log.Printf("Log collector stopped")
}

// GetLogs returns collected logs (up to batchSize)
func (lc *LogCollector) GetLogs(batchSize int) []LogEntry {
	var logs []LogEntry

	for i := 0; i < batchSize; i++ {
		select {
		case entry := <-lc.logChan:
			logs = append(logs, entry)
		default:
			return logs
		}
	}

	return logs
}

// tailSource tails a single log source
func (lc *LogCollector) tailSource(source LogSource) {
	defer lc.wg.Done()

	// Expand glob patterns
	files, err := filepath.Glob(source.Path)
	if err != nil {
		log.Printf("Log collector: invalid path pattern %s: %v", source.Path, err)
		return
	}

	if len(files) == 0 {
		log.Printf("Log collector: no files match pattern %s", source.Path)
		return
	}

	// Tail each file
	for _, file := range files {
		lc.wg.Add(1)
		go lc.tailFile(file, source)
	}
}

// tailFile tails a single file
func (lc *LogCollector) tailFile(filePath string, source LogSource) {
	defer lc.wg.Done()

	log.Printf("Log collector: tailing %s", filePath)

	// Get initial file position (start from end for new files)
	lc.fileMu.Lock()
	pos, exists := lc.filePositions[filePath]
	if !exists {
		// Start from end of file
		if info, err := os.Stat(filePath); err == nil {
			pos = info.Size()
		}
		lc.filePositions[filePath] = pos
	}
	lc.fileMu.Unlock()

	ticker := time.NewTicker(1 * time.Second)
	defer ticker.Stop()

	for {
		select {
		case <-lc.stopChan:
			return
		case <-ticker.C:
			lc.readNewLines(filePath, source)
		}
	}
}

// readNewLines reads new lines from a file
func (lc *LogCollector) readNewLines(filePath string, source LogSource) {
	file, err := os.Open(filePath)
	if err != nil {
		return
	}
	defer file.Close()

	// Get current position
	lc.fileMu.RLock()
	pos := lc.filePositions[filePath]
	lc.fileMu.RUnlock()

	// Check if file was truncated/rotated
	info, err := file.Stat()
	if err != nil {
		return
	}

	if info.Size() < pos {
		// File was truncated, start from beginning
		pos = 0
	}

	// Seek to position
	if _, err := file.Seek(pos, io.SeekStart); err != nil {
		return
	}

	scanner := bufio.NewScanner(file)
	// Increase buffer size for long lines
	buf := make([]byte, 0, 64*1024)
	scanner.Buffer(buf, 1024*1024)

	linesRead := 0
	for scanner.Scan() {
		line := scanner.Text()
		if line == "" {
			continue
		}

		// Check filters
		if !lc.shouldInclude(source.Name, line) {
			continue
		}

		// Parse log entry
		entry := lc.parseLine(line, filePath, source)

		// Send to channel (non-blocking)
		select {
		case lc.logChan <- entry:
			linesRead++
		default:
			// Channel full, drop oldest logs
			select {
			case <-lc.logChan:
				lc.logChan <- entry
				linesRead++
			default:
			}
		}
	}

	// Update position
	newPos, _ := file.Seek(0, io.SeekCurrent)
	lc.fileMu.Lock()
	lc.filePositions[filePath] = newPos
	lc.fileMu.Unlock()
}

// shouldInclude checks if a line should be included based on filters
func (lc *LogCollector) shouldInclude(sourceName, line string) bool {
	// Check exclude patterns first
	for _, re := range lc.excludePatterns[sourceName] {
		if re.MatchString(line) {
			return false
		}
	}

	// If include patterns exist, line must match at least one
	includes := lc.includePatterns[sourceName]
	if len(includes) > 0 {
		for _, re := range includes {
			if re.MatchString(line) {
				return true
			}
		}
		return false
	}

	return true
}

// parseLine parses a log line into a LogEntry
func (lc *LogCollector) parseLine(line, filePath string, source LogSource) LogEntry {
	entry := LogEntry{
		Timestamp: time.Now(),
		Message:   line,
		Source:    filePath,
		Service:   source.Service,
		Host:      lc.hostname,
		Tags:      make(map[string]string),
	}

	// Copy global tags
	for k, v := range lc.globalTags {
		entry.Tags[k] = v
	}

	// Copy source-specific tags
	for k, v := range source.Tags {
		entry.Tags[k] = v
	}

	// Add source name as tag
	entry.Tags["log_source"] = source.Name

	// Parse based on format
	format := source.Format
	if format == "" || format == "auto" {
		format = lc.detectFormat(line)
	}

	switch format {
	case "json":
		lc.parseJSON(&entry, line)
	case "syslog":
		lc.parseSyslog(&entry, line)
	default:
		lc.parsePlain(&entry, line)
	}

	return entry
}

// detectFormat auto-detects the log format
func (lc *LogCollector) detectFormat(line string) string {
	line = strings.TrimSpace(line)

	// Check for JSON
	if strings.HasPrefix(line, "{") && strings.HasSuffix(line, "}") {
		return "json"
	}

	// Check for syslog format (starts with month or priority)
	syslogPattern := regexp.MustCompile(`^(<\d+>)?[A-Z][a-z]{2}\s+\d+\s+\d{2}:\d{2}:\d{2}`)
	if syslogPattern.MatchString(line) {
		return "syslog"
	}

	return "plain"
}

// parseJSON parses JSON formatted logs
func (lc *LogCollector) parseJSON(entry *LogEntry, line string) {
	var data map[string]interface{}
	if err := json.Unmarshal([]byte(line), &data); err != nil {
		// Not valid JSON, keep as plain text
		return
	}

	entry.Attributes = make(map[string]interface{})

	// Extract common fields
	for _, timeField := range []string{"timestamp", "time", "@timestamp", "ts", "datetime"} {
		if v, ok := data[timeField]; ok {
			if t, err := parseTimestamp(v); err == nil {
				entry.Timestamp = t
			}
			delete(data, timeField)
			break
		}
	}

	for _, levelField := range []string{"level", "severity", "log_level", "loglevel"} {
		if v, ok := data[levelField].(string); ok {
			entry.Level = normalizeLevel(v)
			delete(data, levelField)
			break
		}
	}

	for _, msgField := range []string{"message", "msg", "log", "text"} {
		if v, ok := data[msgField].(string); ok {
			entry.Message = v
			delete(data, msgField)
			break
		}
	}

	for _, svcField := range []string{"service", "app", "application", "service_name"} {
		if v, ok := data[svcField].(string); ok {
			if entry.Service == "" {
				entry.Service = v
			}
			delete(data, svcField)
			break
		}
	}

	// Store remaining fields as attributes
	entry.Attributes = data
}

// parseSyslog parses syslog formatted logs
func (lc *LogCollector) parseSyslog(entry *LogEntry, line string) {
	// Syslog format: <priority>timestamp hostname tag: message
	// Or: timestamp hostname tag: message

	// Remove priority if present
	if strings.HasPrefix(line, "<") {
		if idx := strings.Index(line, ">"); idx != -1 {
			line = line[idx+1:]
		}
	}

	// Parse timestamp (first 15 chars typically: "Jan  1 12:00:00")
	syslogTimestamp := regexp.MustCompile(`^([A-Z][a-z]{2}\s+\d+\s+\d{2}:\d{2}:\d{2})\s+`)
	if matches := syslogTimestamp.FindStringSubmatch(line); len(matches) > 1 {
		// Parse with current year
		ts := matches[1]
		year := time.Now().Year()
		if t, err := time.Parse("Jan  2 15:04:05 2006", ts+" "+fmt.Sprintf("%d", year)); err == nil {
			entry.Timestamp = t
		}
		line = line[len(matches[0]):]
	}

	// Extract hostname and tag
	parts := strings.SplitN(line, " ", 3)
	if len(parts) >= 2 {
		// parts[0] = hostname, parts[1] = tag:, parts[2] = message
		if len(parts) >= 3 {
			entry.Tags["syslog_hostname"] = parts[0]
			tag := strings.TrimSuffix(parts[1], ":")
			entry.Tags["syslog_tag"] = tag
			entry.Message = parts[2]
		} else {
			entry.Message = line
		}
	}

	// Detect level from message
	entry.Level = detectLevelFromMessage(entry.Message)
}

// parsePlain parses plain text logs
func (lc *LogCollector) parsePlain(entry *LogEntry, line string) {
	// Try to extract timestamp from beginning
	timestampPatterns := []struct {
		pattern string
		layout  string
	}{
		{`^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}`, time.RFC3339},
		{`^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}`, "2006-01-02 15:04:05"},
		{`^\d{2}/\d{2}/\d{4} \d{2}:\d{2}:\d{2}`, "01/02/2006 15:04:05"},
		{`^\[\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\]`, "[2006-01-02 15:04:05]"},
	}

	for _, tp := range timestampPatterns {
		re := regexp.MustCompile(tp.pattern)
		if match := re.FindString(line); match != "" {
			match = strings.Trim(match, "[]")
			if t, err := time.Parse(tp.layout, match); err == nil {
				entry.Timestamp = t
				break
			}
		}
	}

	// Detect level
	entry.Level = detectLevelFromMessage(line)
}

// parseTimestamp parses various timestamp formats
func parseTimestamp(v interface{}) (time.Time, error) {
	switch t := v.(type) {
	case string:
		// Try common formats
		formats := []string{
			time.RFC3339,
			time.RFC3339Nano,
			"2006-01-02T15:04:05",
			"2006-01-02 15:04:05",
			"2006-01-02T15:04:05.000Z",
		}
		for _, f := range formats {
			if parsed, err := time.Parse(f, t); err == nil {
				return parsed, nil
			}
		}
	case float64:
		// Unix timestamp (seconds or milliseconds)
		if t > 1e12 {
			return time.UnixMilli(int64(t)), nil
		}
		return time.Unix(int64(t), 0), nil
	case int64:
		if t > 1e12 {
			return time.UnixMilli(t), nil
		}
		return time.Unix(t, 0), nil
	}
	return time.Time{}, fmt.Errorf("cannot parse timestamp")
}

// normalizeLevel normalizes log level strings
func normalizeLevel(level string) string {
	level = strings.ToLower(strings.TrimSpace(level))
	switch level {
	case "trace", "debug":
		return "debug"
	case "info", "information":
		return "info"
	case "warn", "warning":
		return "warn"
	case "error", "err":
		return "error"
	case "fatal", "critical", "panic":
		return "fatal"
	default:
		return level
	}
}

// detectLevelFromMessage tries to detect log level from message content
func detectLevelFromMessage(msg string) string {
	msg = strings.ToUpper(msg)

	patterns := []struct {
		pattern string
		level   string
	}{
		{`\b(FATAL|PANIC|CRITICAL)\b`, "fatal"},
		{`\bERROR\b`, "error"},
		{`\b(WARN|WARNING)\b`, "warn"},
		{`\bINFO\b`, "info"},
		{`\b(DEBUG|TRACE)\b`, "debug"},
	}

	for _, p := range patterns {
		if matched, _ := regexp.MatchString(p.pattern, msg); matched {
			return p.level
		}
	}

	return "info" // default
}
