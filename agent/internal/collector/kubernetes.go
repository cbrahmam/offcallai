// Package collector - Kubernetes cluster data collector
package collector

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"
	"os"
	"strconv"
	"strings"
	"sync"
	"time"

	appsv1 "k8s.io/api/apps/v1"
	corev1 "k8s.io/api/core/v1"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"k8s.io/client-go/kubernetes"
	"k8s.io/client-go/rest"
	metricsv1beta1 "k8s.io/metrics/pkg/apis/metrics/v1beta1"
	metricsclient "k8s.io/metrics/pkg/client/clientset/versioned"
)

// KubernetesConfig holds K8s collector configuration
type KubernetesConfig struct {
	Enabled      bool
	ClusterID    string
	ClusterName  string
	SyncInterval time.Duration
	Namespaces   []string // empty = all namespaces
}

// KubernetesCollector collects K8s cluster state and syncs to the backend
type KubernetesCollector struct {
	config        KubernetesConfig
	apiBase       string
	apiKey        string
	agentID       string
	clientset     kubernetes.Interface
	metricsClient metricsclient.Interface
	httpClient    *http.Client
	stopChan      chan struct{}
	wg            sync.WaitGroup
}

// NewKubernetesCollector creates a new K8s collector
func NewKubernetesCollector(cfg KubernetesConfig, apiBase, apiKey, agentID string) *KubernetesCollector {
	return &KubernetesCollector{
		config:   cfg,
		apiBase:  apiBase,
		apiKey:   apiKey,
		agentID:  agentID,
		stopChan: make(chan struct{}),
		httpClient: &http.Client{
			Timeout: 30 * time.Second,
		},
	}
}

// Start begins the background K8s sync loop
func (k *KubernetesCollector) Start() error {
	// Try in-cluster config first
	cfg, err := rest.InClusterConfig()
	if err != nil {
		log.Printf("[k8s] Not running in cluster: %v", err)
		return fmt.Errorf("kubernetes collector requires in-cluster config: %w", err)
	}

	clientset, err := kubernetes.NewForConfig(cfg)
	if err != nil {
		return fmt.Errorf("failed to create kubernetes client: %w", err)
	}
	k.clientset = clientset

	// Try to create metrics client (optional - metrics-server may not be installed)
	metricsClient, err := metricsclient.NewForConfig(cfg)
	if err != nil {
		log.Printf("[k8s] Metrics client not available (metrics-server may not be installed): %v", err)
	} else {
		k.metricsClient = metricsClient
	}

	// Verify connectivity
	_, err = clientset.Discovery().ServerVersion()
	if err != nil {
		return fmt.Errorf("failed to connect to kubernetes API: %w", err)
	}

	log.Printf("[k8s] Connected to cluster, starting sync loop (interval: %s)", k.config.SyncInterval)

	k.wg.Add(1)
	go k.syncLoop()

	return nil
}

// Stop stops the K8s collector
func (k *KubernetesCollector) Stop() {
	close(k.stopChan)
	k.wg.Wait()
	log.Printf("[k8s] Collector stopped")
}

func (k *KubernetesCollector) syncLoop() {
	defer k.wg.Done()

	// Initial sync immediately
	k.doSync()

	ticker := time.NewTicker(k.config.SyncInterval)
	defer ticker.Stop()

	for {
		select {
		case <-k.stopChan:
			return
		case <-ticker.C:
			k.doSync()
		}
	}
}

func (k *KubernetesCollector) doSync() {
	ctx, cancel := context.WithTimeout(context.Background(), 60*time.Second)
	defer cancel()

	log.Printf("[k8s] Starting cluster sync...")

	syncData, err := k.collectClusterData(ctx)
	if err != nil {
		log.Printf("[k8s] Error collecting cluster data: %v", err)
		return
	}

	if err := k.sendSyncData(syncData); err != nil {
		log.Printf("[k8s] Error sending sync data: %v", err)
		return
	}

	log.Printf("[k8s] Sync complete: %d nodes, %d pods, %d deployments, %d services, %d events, %d namespaces",
		len(syncData.Nodes), len(syncData.Pods), len(syncData.Deployments),
		len(syncData.Services), len(syncData.Events), len(syncData.Namespaces))
}

// ClusterSyncData matches the backend schema
type ClusterSyncData struct {
	ClusterName string           `json:"cluster_name"`
	Version     string           `json:"version,omitempty"`
	Nodes       []NodeData       `json:"nodes"`
	Pods        []PodData        `json:"pods"`
	Deployments []DeploymentData `json:"deployments"`
	Services    []ServiceData    `json:"services"`
	Events      []EventData      `json:"events"`
	Namespaces  []string         `json:"namespaces"`
}

type NodeData struct {
	Name              string                   `json:"name"`
	UID               string                   `json:"uid"`
	KubernetesVersion string                   `json:"kubernetes_version,omitempty"`
	OSImage           string                   `json:"os_image,omitempty"`
	ContainerRuntime  string                   `json:"container_runtime,omitempty"`
	Architecture      string                   `json:"architecture,omitempty"`
	InstanceType      string                   `json:"instance_type,omitempty"`
	InstanceID        string                   `json:"instance_id,omitempty"`
	Zone              string                   `json:"zone,omitempty"`
	CPUCapacity       *float64                 `json:"cpu_capacity,omitempty"`
	MemoryCapacity    *float64                 `json:"memory_capacity,omitempty"`
	PodCapacity       *int                     `json:"pod_capacity,omitempty"`
	CPUAllocatable    *float64                 `json:"cpu_allocatable,omitempty"`
	MemoryAllocatable *float64                 `json:"memory_allocatable,omitempty"`
	PodAllocatable    *int                     `json:"pod_allocatable,omitempty"`
	CPUUsage          *float64                 `json:"cpu_usage,omitempty"`
	MemoryUsage       *float64                 `json:"memory_usage,omitempty"`
	Status            string                   `json:"status"`
	Conditions        []map[string]interface{} `json:"conditions"`
	Taints            []map[string]interface{} `json:"taints"`
	Labels            map[string]string        `json:"labels"`
	Roles             []string                 `json:"roles"`
}

type PodData struct {
	Namespace     string                   `json:"namespace"`
	Name          string                   `json:"name"`
	UID           string                   `json:"uid"`
	OwnerKind     string                   `json:"owner_kind,omitempty"`
	OwnerName     string                   `json:"owner_name,omitempty"`
	NodeName      string                   `json:"node_name,omitempty"`
	Phase         string                   `json:"phase"`
	Conditions    []map[string]interface{} `json:"conditions"`
	Reason        string                   `json:"reason,omitempty"`
	Message       string                   `json:"message,omitempty"`
	Containers    []map[string]interface{} `json:"containers"`
	PodIP         string                   `json:"pod_ip,omitempty"`
	HostIP        string                   `json:"host_ip,omitempty"`
	CPURequest    *float64                 `json:"cpu_request,omitempty"`
	CPULimit      *float64                 `json:"cpu_limit,omitempty"`
	MemoryRequest *float64                 `json:"memory_request,omitempty"`
	MemoryLimit   *float64                 `json:"memory_limit,omitempty"`
	CPUUsage      *float64                 `json:"cpu_usage,omitempty"`
	MemoryUsage   *float64                 `json:"memory_usage,omitempty"`
	RestartCount  int                      `json:"restart_count"`
	QOSClass      string                   `json:"qos_class,omitempty"`
	Labels        map[string]string        `json:"labels"`
	StartedAt     *time.Time               `json:"started_at,omitempty"`
}

type DeploymentData struct {
	Namespace         string                   `json:"namespace"`
	Name              string                   `json:"name"`
	UID               string                   `json:"uid"`
	StrategyType      string                   `json:"strategy_type"`
	Replicas          int                      `json:"replicas"`
	ReadyReplicas     int                      `json:"ready_replicas"`
	AvailableReplicas int                      `json:"available_replicas"`
	UpdatedReplicas   int                      `json:"updated_replicas"`
	Conditions        []map[string]interface{} `json:"conditions"`
	Containers        []map[string]interface{} `json:"containers"`
	CPURequest        *float64                 `json:"cpu_request,omitempty"`
	CPULimit          *float64                 `json:"cpu_limit,omitempty"`
	MemoryRequest     *float64                 `json:"memory_request,omitempty"`
	MemoryLimit       *float64                 `json:"memory_limit,omitempty"`
	Selector          map[string]string        `json:"selector"`
	Labels            map[string]string        `json:"labels"`
}

type ServiceData struct {
	Namespace   string                   `json:"namespace"`
	Name        string                   `json:"name"`
	UID         string                   `json:"uid"`
	ServiceType string                   `json:"service_type"`
	ClusterIP   string                   `json:"cluster_ip,omitempty"`
	ExternalIPs []string                 `json:"external_ips"`
	Ports       []map[string]interface{} `json:"ports"`
	Selector    map[string]string        `json:"selector"`
	Endpoints   []map[string]interface{} `json:"endpoints"`
	Labels      map[string]string        `json:"labels"`
}

type EventData struct {
	Namespace       string     `json:"namespace,omitempty"`
	Name            string     `json:"name"`
	UID             string     `json:"uid"`
	InvolvedKind    string     `json:"involved_kind"`
	InvolvedName    string     `json:"involved_name"`
	InvolvedUID     string     `json:"involved_uid,omitempty"`
	EventType       string     `json:"event_type"`
	Reason          string     `json:"reason"`
	Message         string     `json:"message,omitempty"`
	SourceComponent string     `json:"source_component,omitempty"`
	SourceHost      string     `json:"source_host,omitempty"`
	FirstTimestamp  *time.Time `json:"first_timestamp,omitempty"`
	LastTimestamp   *time.Time `json:"last_timestamp,omitempty"`
	Count           int        `json:"count"`
}

func (k *KubernetesCollector) collectClusterData(ctx context.Context) (*ClusterSyncData, error) {
	syncData := &ClusterSyncData{
		ClusterName: k.config.ClusterName,
		Nodes:       make([]NodeData, 0),
		Pods:        make([]PodData, 0),
		Deployments: make([]DeploymentData, 0),
		Services:    make([]ServiceData, 0),
		Events:      make([]EventData, 0),
		Namespaces:  make([]string, 0),
	}

	// Get cluster version
	version, err := k.clientset.Discovery().ServerVersion()
	if err == nil {
		syncData.Version = version.GitVersion
	}

	// Determine namespace filter
	namespace := "" // all namespaces
	if len(k.config.Namespaces) == 1 {
		namespace = k.config.Namespaces[0]
	}

	// Get node metrics map (optional)
	nodeMetrics := k.getNodeMetrics(ctx)
	podMetrics := k.getPodMetrics(ctx, namespace)

	// Collect nodes
	nodes, err := k.clientset.CoreV1().Nodes().List(ctx, metav1.ListOptions{})
	if err != nil {
		log.Printf("[k8s] Error listing nodes: %v", err)
	} else {
		for _, node := range nodes.Items {
			syncData.Nodes = append(syncData.Nodes, k.nodeToNodeData(node, nodeMetrics))
		}
	}

	// Collect namespaces
	namespaces, err := k.clientset.CoreV1().Namespaces().List(ctx, metav1.ListOptions{})
	if err != nil {
		log.Printf("[k8s] Error listing namespaces: %v", err)
	} else {
		for _, ns := range namespaces.Items {
			if k.shouldIncludeNamespace(ns.Name) {
				syncData.Namespaces = append(syncData.Namespaces, ns.Name)
			}
		}
	}

	// Collect pods
	pods, err := k.clientset.CoreV1().Pods(namespace).List(ctx, metav1.ListOptions{})
	if err != nil {
		log.Printf("[k8s] Error listing pods: %v", err)
	} else {
		for _, pod := range pods.Items {
			if k.shouldIncludeNamespace(pod.Namespace) {
				syncData.Pods = append(syncData.Pods, k.podToPodData(pod, podMetrics))
			}
		}
	}

	// Collect deployments
	deployments, err := k.clientset.AppsV1().Deployments(namespace).List(ctx, metav1.ListOptions{})
	if err != nil {
		log.Printf("[k8s] Error listing deployments: %v", err)
	} else {
		for _, dep := range deployments.Items {
			if k.shouldIncludeNamespace(dep.Namespace) {
				syncData.Deployments = append(syncData.Deployments, k.deploymentToDeploymentData(dep))
			}
		}
	}

	// Collect services
	services, err := k.clientset.CoreV1().Services(namespace).List(ctx, metav1.ListOptions{})
	if err != nil {
		log.Printf("[k8s] Error listing services: %v", err)
	} else {
		for _, svc := range services.Items {
			if k.shouldIncludeNamespace(svc.Namespace) {
				syncData.Services = append(syncData.Services, k.serviceToServiceData(svc))
			}
		}
	}

	// Collect recent events (last 1 hour)
	oneHourAgo := metav1.NewTime(time.Now().Add(-1 * time.Hour))
	eventOpts := metav1.ListOptions{
		FieldSelector: fmt.Sprintf("metadata.creationTimestamp>=%s", oneHourAgo.Format(time.RFC3339)),
	}
	// Field selector on creationTimestamp may not work on all versions, fall back to listing all and filtering
	events, err := k.clientset.CoreV1().Events(namespace).List(ctx, metav1.ListOptions{})
	if err != nil {
		log.Printf("[k8s] Error listing events: %v", err)
	} else {
		_ = eventOpts // used the simpler approach
		for _, event := range events.Items {
			if k.shouldIncludeNamespace(event.Namespace) && k.isRecentEvent(event) {
				syncData.Events = append(syncData.Events, k.eventToEventData(event))
			}
		}
	}

	return syncData, nil
}

func (k *KubernetesCollector) shouldIncludeNamespace(ns string) bool {
	if len(k.config.Namespaces) == 0 {
		return true
	}
	for _, allowed := range k.config.Namespaces {
		if allowed == ns {
			return true
		}
	}
	return false
}

func (k *KubernetesCollector) isRecentEvent(event corev1.Event) bool {
	cutoff := time.Now().Add(-1 * time.Hour)
	if event.LastTimestamp.Time.After(cutoff) {
		return true
	}
	if event.CreationTimestamp.Time.After(cutoff) {
		return true
	}
	return false
}

// getNodeMetrics fetches node metrics from metrics-server (optional)
func (k *KubernetesCollector) getNodeMetrics(ctx context.Context) map[string]*metricsv1beta1.NodeMetrics {
	result := make(map[string]*metricsv1beta1.NodeMetrics)
	if k.metricsClient == nil {
		return result
	}

	metrics, err := k.metricsClient.MetricsV1beta1().NodeMetricses().List(ctx, metav1.ListOptions{})
	if err != nil {
		log.Printf("[k8s] Could not fetch node metrics: %v", err)
		return result
	}

	for i := range metrics.Items {
		result[metrics.Items[i].Name] = &metrics.Items[i]
	}
	return result
}

// getPodMetrics fetches pod metrics from metrics-server (optional)
func (k *KubernetesCollector) getPodMetrics(ctx context.Context, namespace string) map[string]*metricsv1beta1.PodMetrics {
	result := make(map[string]*metricsv1beta1.PodMetrics)
	if k.metricsClient == nil {
		return result
	}

	metrics, err := k.metricsClient.MetricsV1beta1().PodMetricses(namespace).List(ctx, metav1.ListOptions{})
	if err != nil {
		log.Printf("[k8s] Could not fetch pod metrics: %v", err)
		return result
	}

	for i := range metrics.Items {
		key := metrics.Items[i].Namespace + "/" + metrics.Items[i].Name
		result[key] = &metrics.Items[i]
	}
	return result
}

func (k *KubernetesCollector) nodeToNodeData(node corev1.Node, metrics map[string]*metricsv1beta1.NodeMetrics) NodeData {
	nd := NodeData{
		Name:              node.Name,
		UID:               string(node.UID),
		KubernetesVersion: node.Status.NodeInfo.KubeletVersion,
		OSImage:           node.Status.NodeInfo.OSImage,
		ContainerRuntime:  node.Status.NodeInfo.ContainerRuntimeVersion,
		Architecture:      node.Status.NodeInfo.Architecture,
		Labels:            node.Labels,
		Status:            "Unknown",
	}

	if nd.Labels == nil {
		nd.Labels = make(map[string]string)
	}

	// Instance type and zone from labels
	if v, ok := node.Labels["node.kubernetes.io/instance-type"]; ok {
		nd.InstanceType = v
	} else if v, ok := node.Labels["beta.kubernetes.io/instance-type"]; ok {
		nd.InstanceType = v
	}
	if v, ok := node.Labels["topology.kubernetes.io/zone"]; ok {
		nd.Zone = v
	} else if v, ok := node.Labels["failure-domain.beta.kubernetes.io/zone"]; ok {
		nd.Zone = v
	}

	// Roles
	for label := range node.Labels {
		if strings.HasPrefix(label, "node-role.kubernetes.io/") {
			role := strings.TrimPrefix(label, "node-role.kubernetes.io/")
			if role != "" {
				nd.Roles = append(nd.Roles, role)
			}
		}
	}
	if len(nd.Roles) == 0 {
		nd.Roles = []string{"worker"}
	}

	// Capacity
	if cpu := node.Status.Capacity.Cpu(); cpu != nil {
		v := float64(cpu.MilliValue()) / 1000.0
		nd.CPUCapacity = &v
	}
	if mem := node.Status.Capacity.Memory(); mem != nil {
		v := float64(mem.Value())
		nd.MemoryCapacity = &v
	}
	if pods := node.Status.Capacity.Pods(); pods != nil {
		v := int(pods.Value())
		nd.PodCapacity = &v
	}

	// Allocatable
	if cpu := node.Status.Allocatable.Cpu(); cpu != nil {
		v := float64(cpu.MilliValue()) / 1000.0
		nd.CPUAllocatable = &v
	}
	if mem := node.Status.Allocatable.Memory(); mem != nil {
		v := float64(mem.Value())
		nd.MemoryAllocatable = &v
	}
	if pods := node.Status.Allocatable.Pods(); pods != nil {
		v := int(pods.Value())
		nd.PodAllocatable = &v
	}

	// Node conditions
	nd.Conditions = make([]map[string]interface{}, 0)
	for _, cond := range node.Status.Conditions {
		nd.Conditions = append(nd.Conditions, map[string]interface{}{
			"type":    string(cond.Type),
			"status":  string(cond.Status),
			"reason":  cond.Reason,
			"message": cond.Message,
		})
		if cond.Type == corev1.NodeReady {
			if cond.Status == corev1.ConditionTrue {
				nd.Status = "Ready"
			} else {
				nd.Status = "NotReady"
			}
		}
	}

	// Taints
	nd.Taints = make([]map[string]interface{}, 0)
	for _, taint := range node.Spec.Taints {
		nd.Taints = append(nd.Taints, map[string]interface{}{
			"key":    taint.Key,
			"value":  taint.Value,
			"effect": string(taint.Effect),
		})
	}

	// Metrics from metrics-server
	if m, ok := metrics[node.Name]; ok {
		if cpu := m.Usage.Cpu(); cpu != nil {
			v := float64(cpu.MilliValue()) / 1000.0
			nd.CPUUsage = &v
		}
		if mem := m.Usage.Memory(); mem != nil {
			v := float64(mem.Value())
			nd.MemoryUsage = &v
		}
	}

	return nd
}

func (k *KubernetesCollector) podToPodData(pod corev1.Pod, metrics map[string]*metricsv1beta1.PodMetrics) PodData {
	pd := PodData{
		Namespace: pod.Namespace,
		Name:      pod.Name,
		UID:       string(pod.UID),
		NodeName:  pod.Spec.NodeName,
		Phase:     string(pod.Status.Phase),
		PodIP:     pod.Status.PodIP,
		HostIP:    pod.Status.HostIP,
		QOSClass:  string(pod.Status.QOSClass),
		Labels:    pod.Labels,
	}

	if pd.Labels == nil {
		pd.Labels = make(map[string]string)
	}

	// Owner reference
	if len(pod.OwnerReferences) > 0 {
		pd.OwnerKind = pod.OwnerReferences[0].Kind
		pd.OwnerName = pod.OwnerReferences[0].Name
	}

	// Status reason/message
	if pod.Status.Reason != "" {
		pd.Reason = pod.Status.Reason
	}
	if pod.Status.Message != "" {
		pd.Message = pod.Status.Message
	}

	// Started at
	if pod.Status.StartTime != nil {
		t := pod.Status.StartTime.Time
		pd.StartedAt = &t
	}

	// Conditions
	pd.Conditions = make([]map[string]interface{}, 0)
	for _, cond := range pod.Status.Conditions {
		pd.Conditions = append(pd.Conditions, map[string]interface{}{
			"type":   string(cond.Type),
			"status": string(cond.Status),
			"reason": cond.Reason,
		})
	}

	// Containers info
	pd.Containers = make([]map[string]interface{}, 0)
	var totalCPURequest, totalCPULimit, totalMemRequest, totalMemLimit float64
	var totalRestarts int32

	for _, c := range pod.Spec.Containers {
		containerInfo := map[string]interface{}{
			"name":  c.Name,
			"image": c.Image,
		}

		// Find container status
		for _, cs := range pod.Status.ContainerStatuses {
			if cs.Name == c.Name {
				containerInfo["ready"] = cs.Ready
				containerInfo["restart_count"] = cs.RestartCount
				totalRestarts += cs.RestartCount

				if cs.State.Running != nil {
					containerInfo["state"] = "running"
					containerInfo["started_at"] = cs.State.Running.StartedAt.Time.Format(time.RFC3339)
				} else if cs.State.Waiting != nil {
					containerInfo["state"] = "waiting"
					containerInfo["reason"] = cs.State.Waiting.Reason
					containerInfo["message"] = cs.State.Waiting.Message
				} else if cs.State.Terminated != nil {
					containerInfo["state"] = "terminated"
					containerInfo["reason"] = cs.State.Terminated.Reason
				}
				break
			}
		}

		// Resource requests/limits
		if cpu := c.Resources.Requests.Cpu(); cpu != nil {
			totalCPURequest += float64(cpu.MilliValue()) / 1000.0
		}
		if cpu := c.Resources.Limits.Cpu(); cpu != nil {
			totalCPULimit += float64(cpu.MilliValue()) / 1000.0
		}
		if mem := c.Resources.Requests.Memory(); mem != nil {
			totalMemRequest += float64(mem.Value())
		}
		if mem := c.Resources.Limits.Memory(); mem != nil {
			totalMemLimit += float64(mem.Value())
		}

		pd.Containers = append(pd.Containers, containerInfo)
	}

	pd.RestartCount = int(totalRestarts)

	if totalCPURequest > 0 {
		pd.CPURequest = &totalCPURequest
	}
	if totalCPULimit > 0 {
		pd.CPULimit = &totalCPULimit
	}
	if totalMemRequest > 0 {
		pd.MemoryRequest = &totalMemRequest
	}
	if totalMemLimit > 0 {
		pd.MemoryLimit = &totalMemLimit
	}

	// Pod metrics from metrics-server
	key := pod.Namespace + "/" + pod.Name
	if m, ok := metrics[key]; ok {
		var cpuUsage, memUsage float64
		for _, c := range m.Containers {
			if cpu := c.Usage.Cpu(); cpu != nil {
				cpuUsage += float64(cpu.MilliValue()) / 1000.0
			}
			if mem := c.Usage.Memory(); mem != nil {
				memUsage += float64(mem.Value())
			}
		}
		if cpuUsage > 0 {
			pd.CPUUsage = &cpuUsage
		}
		if memUsage > 0 {
			pd.MemoryUsage = &memUsage
		}
	}

	return pd
}

func (k *KubernetesCollector) deploymentToDeploymentData(dep appsv1.Deployment) DeploymentData {
	dd := DeploymentData{
		Namespace:    dep.Namespace,
		Name:         dep.Name,
		UID:          string(dep.UID),
		StrategyType: string(dep.Spec.Strategy.Type),
		Labels:       dep.Labels,
	}

	if dd.Labels == nil {
		dd.Labels = make(map[string]string)
	}

	if dep.Spec.Replicas != nil {
		dd.Replicas = int(*dep.Spec.Replicas)
	}
	dd.ReadyReplicas = int(dep.Status.ReadyReplicas)
	dd.AvailableReplicas = int(dep.Status.AvailableReplicas)
	dd.UpdatedReplicas = int(dep.Status.UpdatedReplicas)

	// Conditions
	dd.Conditions = make([]map[string]interface{}, 0)
	for _, cond := range dep.Status.Conditions {
		dd.Conditions = append(dd.Conditions, map[string]interface{}{
			"type":    string(cond.Type),
			"status":  string(cond.Status),
			"reason":  cond.Reason,
			"message": cond.Message,
		})
	}

	// Containers
	dd.Containers = make([]map[string]interface{}, 0)
	var totalCPURequest, totalCPULimit, totalMemRequest, totalMemLimit float64
	for _, c := range dep.Spec.Template.Spec.Containers {
		dd.Containers = append(dd.Containers, map[string]interface{}{
			"name":  c.Name,
			"image": c.Image,
		})
		if cpu := c.Resources.Requests.Cpu(); cpu != nil {
			totalCPURequest += float64(cpu.MilliValue()) / 1000.0
		}
		if cpu := c.Resources.Limits.Cpu(); cpu != nil {
			totalCPULimit += float64(cpu.MilliValue()) / 1000.0
		}
		if mem := c.Resources.Requests.Memory(); mem != nil {
			totalMemRequest += float64(mem.Value())
		}
		if mem := c.Resources.Limits.Memory(); mem != nil {
			totalMemLimit += float64(mem.Value())
		}
	}

	if totalCPURequest > 0 {
		dd.CPURequest = &totalCPURequest
	}
	if totalCPULimit > 0 {
		dd.CPULimit = &totalCPULimit
	}
	if totalMemRequest > 0 {
		dd.MemoryRequest = &totalMemRequest
	}
	if totalMemLimit > 0 {
		dd.MemoryLimit = &totalMemLimit
	}

	// Selector
	dd.Selector = make(map[string]string)
	if dep.Spec.Selector != nil && dep.Spec.Selector.MatchLabels != nil {
		dd.Selector = dep.Spec.Selector.MatchLabels
	}

	return dd
}

func (k *KubernetesCollector) serviceToServiceData(svc corev1.Service) ServiceData {
	sd := ServiceData{
		Namespace:   svc.Namespace,
		Name:        svc.Name,
		UID:         string(svc.UID),
		ServiceType: string(svc.Spec.Type),
		ClusterIP:   svc.Spec.ClusterIP,
		Labels:      svc.Labels,
	}

	if sd.Labels == nil {
		sd.Labels = make(map[string]string)
	}

	// External IPs
	sd.ExternalIPs = make([]string, 0)
	sd.ExternalIPs = append(sd.ExternalIPs, svc.Spec.ExternalIPs...)
	if svc.Status.LoadBalancer.Ingress != nil {
		for _, ing := range svc.Status.LoadBalancer.Ingress {
			if ing.IP != "" {
				sd.ExternalIPs = append(sd.ExternalIPs, ing.IP)
			} else if ing.Hostname != "" {
				sd.ExternalIPs = append(sd.ExternalIPs, ing.Hostname)
			}
		}
	}

	// Ports
	sd.Ports = make([]map[string]interface{}, 0)
	for _, port := range svc.Spec.Ports {
		p := map[string]interface{}{
			"name":        port.Name,
			"port":        port.Port,
			"target_port": port.TargetPort.String(),
			"protocol":    string(port.Protocol),
		}
		if port.NodePort > 0 {
			p["node_port"] = port.NodePort
		}
		sd.Ports = append(sd.Ports, p)
	}

	// Selector
	sd.Selector = make(map[string]string)
	if svc.Spec.Selector != nil {
		sd.Selector = svc.Spec.Selector
	}

	// Endpoints (simplified)
	sd.Endpoints = make([]map[string]interface{}, 0)

	return sd
}

func (k *KubernetesCollector) eventToEventData(event corev1.Event) EventData {
	ed := EventData{
		Namespace:       event.Namespace,
		Name:            event.Name,
		UID:             string(event.UID),
		InvolvedKind:    event.InvolvedObject.Kind,
		InvolvedName:    event.InvolvedObject.Name,
		InvolvedUID:     string(event.InvolvedObject.UID),
		EventType:       event.Type,
		Reason:          event.Reason,
		Message:         event.Message,
		SourceComponent: event.Source.Component,
		SourceHost:      event.Source.Host,
		Count:           int(event.Count),
	}

	if !event.FirstTimestamp.IsZero() {
		t := event.FirstTimestamp.Time
		ed.FirstTimestamp = &t
	}
	if !event.LastTimestamp.IsZero() {
		t := event.LastTimestamp.Time
		ed.LastTimestamp = &t
	}

	if ed.Count == 0 {
		ed.Count = 1
	}

	return ed
}

func (k *KubernetesCollector) sendSyncData(data *ClusterSyncData) error {
	body, err := json.Marshal(data)
	if err != nil {
		return fmt.Errorf("failed to marshal sync data: %w", err)
	}

	endpoint := fmt.Sprintf("%s/containers/clusters/%s/sync", k.apiBase, k.config.ClusterID)

	req, err := http.NewRequest("POST", endpoint, bytes.NewReader(body))
	if err != nil {
		return fmt.Errorf("failed to create request: %w", err)
	}

	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("X-API-Key", k.apiKey)
	req.Header.Set("User-Agent", "offcall-agent/k8s-collector")

	resp, err := k.httpClient.Do(req)
	if err != nil {
		return fmt.Errorf("failed to send request: %w", err)
	}
	defer resp.Body.Close()

	respBody, _ := io.ReadAll(resp.Body)

	if resp.StatusCode != http.StatusOK {
		return fmt.Errorf("API returned status %d: %s", resp.StatusCode, string(respBody))
	}

	log.Printf("[k8s] Sync response: %s", string(respBody))
	return nil
}

// IsRunningInKubernetes checks if the agent is running inside a K8s pod
func IsRunningInKubernetes() bool {
	// Check for service account token (mounted in all K8s pods)
	if _, err := os.Stat("/var/run/secrets/kubernetes.io/serviceaccount/token"); err == nil {
		return true
	}
	// Check for KUBERNETES_SERVICE_HOST env var
	if os.Getenv("KUBERNETES_SERVICE_HOST") != "" {
		return true
	}
	return false
}

// GetClusterNameFromEnv tries to detect the cluster name
func GetClusterNameFromEnv() string {
	if name := os.Getenv("OFFCALL_K8S_CLUSTER_NAME"); name != "" {
		return name
	}
	if name := os.Getenv("CLUSTER_NAME"); name != "" {
		return name
	}
	return "unknown-cluster"
}

// helper for parsing resource quantities to millicores/bytes
func parseMilliCPU(s string) float64 {
	if strings.HasSuffix(s, "m") {
		v, _ := strconv.ParseFloat(strings.TrimSuffix(s, "m"), 64)
		return v / 1000.0
	}
	v, _ := strconv.ParseFloat(s, 64)
	return v
}
