// Package offcall provides error tracking SDK for OffCall AI.
//
// Usage:
//
//	import "github.com/offcall-ai/offcall-go/offcall"
//
//	func main() {
//	    err := offcall.Init(offcall.Options{
//	        APIKey:      "ofc_your_api_key",
//	        Environment: "production",
//	        Release:     "1.0.0",
//	    })
//	    if err != nil {
//	        log.Fatal(err)
//	    }
//	    defer offcall.Flush(time.Second * 2)
//
//	    // Capture errors
//	    if err := doSomething(); err != nil {
//	        offcall.CaptureException(err)
//	    }
//
//	    // With recover middleware
//	    defer offcall.Recover()
//	    panic("something went wrong")
//	}
package offcall

import (
	"bytes"
	"encoding/json"
	"fmt"
	"net/http"
	"os"
	"runtime"
	"sync"
	"time"
)

const (
	SDKName    = "offcall-go"
	SDKVersion = "1.0.0"
	DefaultEndpoint = "http://localhost:8000/api/v1/errors/ingest"
)

// Options configures the SDK.
type Options struct {
	// APIKey is required for authentication
	APIKey string

	// Environment (e.g., "production", "staging")
	Environment string

	// Release version string
	Release string

	// Service name (defaults to executable name)
	Service string

	// Custom API endpoint
	Endpoint string

	// Debug enables debug logging
	Debug bool

	// Enabled enables/disables error reporting
	Enabled bool

	// SampleRate controls sampling (0.0 to 1.0)
	SampleRate float64

	// BeforeSend callback to modify events
	BeforeSend func(*Event) *Event

	// Transport for custom HTTP client
	Transport http.RoundTripper
}

// Event represents an error event.
type Event struct {
	EventID     string                 `json:"event_id,omitempty"`
	Timestamp   string                 `json:"timestamp"`
	Level       string                 `json:"level"`
	Service     string                 `json:"service_name"`
	Environment string                 `json:"environment"`
	Release     string                 `json:"release,omitempty"`
	ErrorType   string                 `json:"error_type"`
	Message     string                 `json:"message"`
	StackTrace  string                 `json:"stack_trace,omitempty"`
	StackFrames []StackFrame           `json:"stack_frames,omitempty"`
	User        *User                  `json:"user,omitempty"`
	Tags        map[string]string      `json:"tags,omitempty"`
	Extra       map[string]interface{} `json:"extra,omitempty"`
	Contexts    map[string]interface{} `json:"contexts,omitempty"`
	Breadcrumbs []Breadcrumb           `json:"breadcrumbs,omitempty"`
	SDK         SDKInfo                `json:"sdk"`
	Runtime     string                 `json:"runtime"`
	RuntimeVersion string              `json:"runtime_version"`
	OS          string                 `json:"os"`
	OSVersion   string                 `json:"os_version"`
}

// StackFrame represents a single stack frame.
type StackFrame struct {
	Filename    string                 `json:"filename"`
	Function    string                 `json:"function"`
	Lineno      int                    `json:"lineno"`
	AbsPath     string                 `json:"abs_path,omitempty"`
	ContextLine string                 `json:"context_line,omitempty"`
	InApp       bool                   `json:"in_app"`
	Module      string                 `json:"module,omitempty"`
	Vars        map[string]interface{} `json:"vars,omitempty"`
}

// User represents user context.
type User struct {
	ID       string `json:"id,omitempty"`
	Email    string `json:"email,omitempty"`
	Username string `json:"username,omitempty"`
	Name     string `json:"name,omitempty"`
	IPAddr   string `json:"ip_address,omitempty"`
}

// Breadcrumb represents a breadcrumb.
type Breadcrumb struct {
	Timestamp string                 `json:"timestamp"`
	Type      string                 `json:"type"`
	Category  string                 `json:"category"`
	Message   string                 `json:"message"`
	Level     string                 `json:"level"`
	Data      map[string]interface{} `json:"data,omitempty"`
}

// SDKInfo contains SDK metadata.
type SDKInfo struct {
	Name    string `json:"name"`
	Version string `json:"version"`
}

// Scope holds context for events.
type Scope struct {
	mu          sync.RWMutex
	user        *User
	tags        map[string]string
	extra       map[string]interface{}
	breadcrumbs []Breadcrumb
	maxBreadcrumbs int
}

// Client is the OffCall error tracking client.
type Client struct {
	options    Options
	httpClient *http.Client
	scope      *Scope
}

var (
	currentClient *Client
	clientMu      sync.RWMutex
)

// Init initializes the SDK with the given options.
func Init(options Options) error {
	if options.APIKey == "" {
		return fmt.Errorf("offcall: API key is required")
	}

	// Set defaults
	if options.Environment == "" {
		options.Environment = "production"
	}
	if options.Service == "" {
		options.Service = detectServiceName()
	}
	if options.Endpoint == "" {
		options.Endpoint = DefaultEndpoint
	}
	if options.SampleRate == 0 {
		options.SampleRate = 1.0
	}
	if !options.Enabled {
		options.Enabled = true
	}

	transport := options.Transport
	if transport == nil {
		transport = http.DefaultTransport
	}

	client := &Client{
		options: options,
		httpClient: &http.Client{
			Transport: transport,
			Timeout:   10 * time.Second,
		},
		scope: &Scope{
			tags:           make(map[string]string),
			extra:          make(map[string]interface{}),
			breadcrumbs:    make([]Breadcrumb, 0, 100),
			maxBreadcrumbs: 100,
		},
	}

	clientMu.Lock()
	currentClient = client
	clientMu.Unlock()

	if options.Debug {
		fmt.Printf("[OffCall] SDK initialized: environment=%s, service=%s\n",
			options.Environment, options.Service)
	}

	// Add init breadcrumb
	AddBreadcrumb(Breadcrumb{
		Category: "sdk",
		Message:  "OffCall SDK initialized",
		Level:    "info",
		Data: map[string]interface{}{
			"version":     SDKVersion,
			"environment": options.Environment,
		},
	})

	return nil
}

// detectServiceName tries to detect the service name.
func detectServiceName() string {
	if name := os.Getenv("SERVICE_NAME"); name != "" {
		return name
	}
	if name := os.Getenv("APP_NAME"); name != "" {
		return name
	}
	if len(os.Args) > 0 {
		return os.Args[0]
	}
	return "go-app"
}

// getClient returns the current client.
func getClient() *Client {
	clientMu.RLock()
	defer clientMu.RUnlock()
	return currentClient
}

// CaptureException captures an error.
func CaptureException(err error) string {
	client := getClient()
	if client == nil {
		return ""
	}
	return client.CaptureException(err)
}

// CaptureMessage captures a message.
func CaptureMessage(message string, level string) string {
	client := getClient()
	if client == nil {
		return ""
	}
	return client.CaptureMessage(message, level)
}

// SetUser sets the user context.
func SetUser(user *User) {
	client := getClient()
	if client == nil {
		return
	}
	client.scope.mu.Lock()
	defer client.scope.mu.Unlock()
	client.scope.user = user
}

// ClearUser clears the user context.
func ClearUser() {
	client := getClient()
	if client == nil {
		return
	}
	client.scope.mu.Lock()
	defer client.scope.mu.Unlock()
	client.scope.user = nil
}

// SetTag sets a tag.
func SetTag(key, value string) {
	client := getClient()
	if client == nil {
		return
	}
	client.scope.mu.Lock()
	defer client.scope.mu.Unlock()
	client.scope.tags[key] = value
}

// SetTags sets multiple tags.
func SetTags(tags map[string]string) {
	client := getClient()
	if client == nil {
		return
	}
	client.scope.mu.Lock()
	defer client.scope.mu.Unlock()
	for k, v := range tags {
		client.scope.tags[k] = v
	}
}

// SetExtra sets extra context.
func SetExtra(key string, value interface{}) {
	client := getClient()
	if client == nil {
		return
	}
	client.scope.mu.Lock()
	defer client.scope.mu.Unlock()
	client.scope.extra[key] = value
}

// AddBreadcrumb adds a breadcrumb.
func AddBreadcrumb(breadcrumb Breadcrumb) {
	client := getClient()
	if client == nil {
		return
	}

	if breadcrumb.Timestamp == "" {
		breadcrumb.Timestamp = time.Now().UTC().Format(time.RFC3339)
	}
	if breadcrumb.Type == "" {
		breadcrumb.Type = "default"
	}
	if breadcrumb.Level == "" {
		breadcrumb.Level = "info"
	}

	client.scope.mu.Lock()
	defer client.scope.mu.Unlock()

	client.scope.breadcrumbs = append(client.scope.breadcrumbs, breadcrumb)
	if len(client.scope.breadcrumbs) > client.scope.maxBreadcrumbs {
		client.scope.breadcrumbs = client.scope.breadcrumbs[1:]
	}
}

// Recover recovers from panic and reports it.
func Recover() {
	if r := recover(); r != nil {
		var err error
		switch v := r.(type) {
		case error:
			err = v
		case string:
			err = fmt.Errorf("%s", v)
		default:
			err = fmt.Errorf("%v", v)
		}
		CaptureException(err)
	}
}

// RecoverWithContext recovers and reports with additional context.
func RecoverWithContext(tags map[string]string, extra map[string]interface{}) {
	if r := recover(); r != nil {
		var err error
		switch v := r.(type) {
		case error:
			err = v
		case string:
			err = fmt.Errorf("%s", v)
		default:
			err = fmt.Errorf("%v", v)
		}

		client := getClient()
		if client != nil {
			event := client.buildEvent(err)
			for k, v := range tags {
				event.Tags[k] = v
			}
			for k, v := range extra {
				event.Extra[k] = v
			}
			client.sendEvent(event)
		}
	}
}

// Flush waits for events to be sent.
func Flush(timeout time.Duration) bool {
	// In a real implementation, this would wait for queued events
	return true
}

// CaptureException captures an error.
func (c *Client) CaptureException(err error) string {
	if err == nil {
		return ""
	}

	// Add error breadcrumb
	AddBreadcrumb(Breadcrumb{
		Category: "exception",
		Message:  err.Error(),
		Level:    "error",
		Type:     "error",
	})

	event := c.buildEvent(err)
	return c.sendEvent(event)
}

// CaptureMessage captures a message.
func (c *Client) CaptureMessage(message string, level string) string {
	if level == "" {
		level = "info"
	}

	// Add message breadcrumb
	AddBreadcrumb(Breadcrumb{
		Category: "message",
		Message:  message,
		Level:    level,
		Type:     "info",
	})

	event := &Event{
		Timestamp:      time.Now().UTC().Format(time.RFC3339),
		Level:          level,
		Service:        c.options.Service,
		Environment:    c.options.Environment,
		Release:        c.options.Release,
		ErrorType:      "Message",
		Message:        message,
		Runtime:        "go",
		RuntimeVersion: runtime.Version(),
		OS:             runtime.GOOS,
		OSVersion:      "",
		SDK: SDKInfo{
			Name:    SDKName,
			Version: SDKVersion,
		},
	}

	c.applyScope(event)
	return c.sendEvent(event)
}

// buildEvent builds an event from an error.
func (c *Client) buildEvent(err error) *Event {
	event := &Event{
		Timestamp:      time.Now().UTC().Format(time.RFC3339),
		Level:          "error",
		Service:        c.options.Service,
		Environment:    c.options.Environment,
		Release:        c.options.Release,
		ErrorType:      fmt.Sprintf("%T", err),
		Message:        err.Error(),
		Runtime:        "go",
		RuntimeVersion: runtime.Version(),
		OS:             runtime.GOOS,
		OSVersion:      "",
		SDK: SDKInfo{
			Name:    SDKName,
			Version: SDKVersion,
		},
	}

	// Capture stack trace
	event.StackFrames = captureStackFrames()
	event.StackTrace = formatStackTrace(event.StackFrames)

	c.applyScope(event)
	return event
}

// applyScope applies scope to event.
func (c *Client) applyScope(event *Event) {
	c.scope.mu.RLock()
	defer c.scope.mu.RUnlock()

	event.User = c.scope.user

	if event.Tags == nil {
		event.Tags = make(map[string]string)
	}
	for k, v := range c.scope.tags {
		event.Tags[k] = v
	}

	if event.Extra == nil {
		event.Extra = make(map[string]interface{})
	}
	for k, v := range c.scope.extra {
		event.Extra[k] = v
	}

	event.Breadcrumbs = make([]Breadcrumb, len(c.scope.breadcrumbs))
	copy(event.Breadcrumbs, c.scope.breadcrumbs)
}

// sendEvent sends an event to the API.
func (c *Client) sendEvent(event *Event) string {
	if !c.options.Enabled {
		if c.options.Debug {
			fmt.Println("[OffCall] SDK disabled")
		}
		return ""
	}

	// Apply before_send hook
	if c.options.BeforeSend != nil {
		event = c.options.BeforeSend(event)
		if event == nil {
			if c.options.Debug {
				fmt.Println("[OffCall] Event dropped by BeforeSend")
			}
			return ""
		}
	}

	data, err := json.Marshal(event)
	if err != nil {
		if c.options.Debug {
			fmt.Printf("[OffCall] Failed to marshal event: %v\n", err)
		}
		return ""
	}

	req, err := http.NewRequest("POST", c.options.Endpoint, bytes.NewReader(data))
	if err != nil {
		if c.options.Debug {
			fmt.Printf("[OffCall] Failed to create request: %v\n", err)
		}
		return ""
	}

	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("X-API-Key", c.options.APIKey)

	resp, err := c.httpClient.Do(req)
	if err != nil {
		if c.options.Debug {
			fmt.Printf("[OffCall] Failed to send event: %v\n", err)
		}
		return ""
	}
	defer resp.Body.Close()

	if c.options.Debug {
		if resp.StatusCode == http.StatusOK || resp.StatusCode == http.StatusCreated {
			fmt.Println("[OffCall] Event sent successfully")
		} else {
			fmt.Printf("[OffCall] Failed to send event: %d\n", resp.StatusCode)
		}
	}

	return ""
}

// captureStackFrames captures the current stack.
func captureStackFrames() []StackFrame {
	const maxFrames = 50
	pcs := make([]uintptr, maxFrames)
	n := runtime.Callers(4, pcs) // Skip runtime.Callers, this func, and SDK funcs
	pcs = pcs[:n]

	frames := make([]StackFrame, 0, n)
	for _, pc := range pcs {
		fn := runtime.FuncForPC(pc)
		if fn == nil {
			continue
		}

		file, line := fn.FileLine(pc)
		frame := StackFrame{
			Function: fn.Name(),
			Filename: file,
			Lineno:   line,
			AbsPath:  file,
			InApp:    isInApp(file),
		}
		frames = append(frames, frame)
	}

	return frames
}

// isInApp checks if frame is from application code.
func isInApp(file string) bool {
	// Check for common library paths
	if contains(file, "go/src/") ||
		contains(file, "go/pkg/") ||
		contains(file, "vendor/") ||
		contains(file, "pkg/mod/") {
		return false
	}
	return true
}

// contains checks if s contains substr.
func contains(s, substr string) bool {
	return len(s) >= len(substr) && (s == substr || len(s) > 0 && len(substr) > 0 && stringContains(s, substr))
}

func stringContains(s, substr string) bool {
	for i := 0; i <= len(s)-len(substr); i++ {
		if s[i:i+len(substr)] == substr {
			return true
		}
	}
	return false
}

// formatStackTrace formats frames as a string.
func formatStackTrace(frames []StackFrame) string {
	var buf bytes.Buffer
	for _, frame := range frames {
		fmt.Fprintf(&buf, "%s\n\t%s:%d\n", frame.Function, frame.Filename, frame.Lineno)
	}
	return buf.String()
}
