# backend/app/schemas/ai.py - Complete AI Integration Schemas
from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any, Union
from datetime import datetime
from enum import Enum

class AIProvider(str, Enum):
    """Supported AI providers for incident resolution"""
    CLAUDE_CODE = "claude_code"
    GEMINI_CLI = "gemini_cli" 
    GROK = "grok"
    FALLBACK = "fallback"

class CommandType(str, Enum):
    """Types of commands that can be executed"""
    API_CALL = "api_call"
    CLI_COMMAND = "cli_command"
    DATABASE_QUERY = "database_query"
    KUBERNETES = "kubernetes"
    TERRAFORM = "terraform"
    ANSIBLE = "ansible"
    DOCKER = "docker"

class RiskLevel(str, Enum):
    """Risk levels for automated actions"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class IncidentSeverity(str, Enum):
    """Incident severity levels"""
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"

# Core AI Analysis Models
class AIAnalysisRequest(BaseModel):
    """Request for incident AI analysis"""
    incident_id: str = Field(..., description="Incident ID to analyze")
    include_historical: bool = Field(True, description="Include historical incident analysis")
    include_recommendations: bool = Field(True, description="Include action recommendations")
    force_provider: Optional[AIProvider] = Field(None, description="Force specific AI provider")

class IncidentInsights(BaseModel):
    """AI-generated insights about an incident"""
    pattern_analysis: str = Field(..., description="Analysis of incident patterns")
    root_cause_hypothesis: str = Field(..., description="Potential root cause")
    affected_systems: List[str] = Field(default=[], description="List of affected systems")
    business_impact: str = Field(..., description="Assessment of business impact")
    prevention_suggestions: List[str] = Field(default=[], description="Suggestions to prevent similar incidents")
    correlation_score: float = Field(0.0, ge=0.0, le=1.0, description="Correlation with known patterns")

class AIAnalysisResponse(BaseModel):
    """Response from incident AI analysis"""
    incident_id: str
    severity_prediction: Optional[IncidentSeverity] = Field(None, description="AI-predicted severity")
    confidence_score: float = Field(..., ge=0.0, le=1.0, description="Confidence in analysis")
    insights: IncidentInsights
    similar_incidents_count: int = Field(0, description="Number of similar historical incidents")
    estimated_resolution_time: int = Field(..., description="Estimated resolution time in minutes")
    impact_assessment: str = Field(..., description="High/Medium/Low impact assessment")
    recommended_actions: List[str] = Field(default=[], description="List of recommended actions")
    auto_resolution_available: bool = Field(False, description="Whether auto-resolution is possible")
    processing_time: float = Field(0.0, description="AI processing time in seconds")
    cache_hit: bool = Field(False, description="Whether result was cached")
    ai_provider: AIProvider = Field(AIProvider.FALLBACK, description="AI provider used")
    kubernetes_efficiency: bool = Field(False, description="Whether response time meets Kubernetes efficiency")

# Auto-Resolution Models
class ResolutionStep(BaseModel):
    """Individual step in resolution plan"""
    order: int = Field(..., description="Execution order")
    description: str = Field(..., description="Human-readable description")
    command: str = Field(..., description="Command to execute")
    command_type: CommandType = Field(..., description="Type of command")
    expected_result: str = Field(..., description="Expected command output")
    rollback_command: Optional[str] = Field(None, description="Command to rollback if needed")
    timeout_seconds: int = Field(300, description="Command timeout")
    critical: bool = Field(False, description="Whether step is critical")
    requires_approval: bool = Field(False, description="Whether step needs human approval")

class AutoResolutionPlan(BaseModel):
    """Complete automated resolution plan"""
    provider: AIProvider = Field(..., description="AI provider that generated plan")
    executable: bool = Field(..., description="Whether plan can be auto-executed")
    confidence_score: float = Field(..., ge=0.0, le=1.0, description="Confidence in resolution plan")
    estimated_time_minutes: int = Field(..., description="Estimated execution time")
    risk_level: RiskLevel = Field(..., description="Risk level of execution")
    steps: List[ResolutionStep] = Field(..., description="Resolution steps")
    human_verification_required: bool = Field(True, description="Whether human verification is required")
    audit_trail: str = Field(..., description="Audit information")
    prerequisites: List[str] = Field(default=[], description="Prerequisites for execution")
    success_criteria: List[str] = Field(default=[], description="Criteria for successful resolution")
    generation_time: float = Field(0.0, description="Time to generate plan")
    kubernetes_efficiency: bool = Field(False, description="Whether generation meets efficiency targets")

class AutoResolutionRequest(BaseModel):
    """Request for automated resolution plan"""
    incident_id: str = Field(..., description="Incident ID to resolve")
    ai_providers: List[AIProvider] = Field(default=[AIProvider.CLAUDE_CODE], description="AI providers to use")
    user_api_keys: Optional[Dict[str, str]] = Field(None, description="User-provided API keys")
    force_provider: Optional[AIProvider] = Field(None, description="Force specific AI provider")
    approval_token: Optional[str] = Field(None, description="Human approval token for high-risk operations")

# Performance Models
class BenchmarkRequest(BaseModel):
    """Request for AI performance benchmarking"""
    num_scenarios: int = Field(10, ge=1, le=50, description="Number of scenarios to test")
    target_response_time: float = Field(2.0, description="Target response time in seconds")

class BenchmarkResult(BaseModel):
    """Result of single benchmark test"""
    scenario_id: str
    success: bool
    response_time: float
    meets_target: bool
    efficiency_rating: str
    analysis_quality: float
    error_message: Optional[str] = None

class BenchmarkResponse(BaseModel):
    """Complete benchmark results"""
    benchmark_summary: Dict[str, Any]
    kubernetes_efficiency: Dict[str, Any]
    detailed_results: List[BenchmarkResult]
    recommendations: List[str]

# Demo Models
class DemoScenarioRequest(BaseModel):
    """Request for live demo scenario"""
    scenario_type: str = Field("kubernetes_pod_failure", description="Type of demo scenario")
    ai_providers: List[AIProvider] = Field(default=[AIProvider.CLAUDE_CODE, AIProvider.GEMINI_CLI])
    demonstrate_resolution: bool = Field(True, description="Whether to show resolution execution")

class DemoResponse(BaseModel):
    """Response from live demo execution"""
    demo_status: str
    demo_metrics: Optional[Dict[str, Any]] = None
    executive_summary: Dict[str, Any]
    investor_metrics: Dict[str, Any]
    error: Optional[str] = None

# Multi-AI Models
class MultiAIRequest(BaseModel):
    """Request for multi-AI provider comparison"""
    incident_id: str

class MultiAIResponse(BaseModel):
    """Response from multi-AI comparison"""
    incident_id: str
    total_processing_time: float
    provider_results: Dict[str, Any]
    consensus: Dict[str, Any]
    fastest_provider: Optional[Dict[str, Any]] = None
    accuracy_score: float
    kubernetes_efficiency: bool

# Integration Status Models
class IntegrationStatusResponse(BaseModel):
    """Response for AI integration status"""
    organization_id: str
    overall_health_score: float
    total_providers: int
    healthy_providers: int
    provider_status: Dict[str, Any]
    ai_capabilities: Dict[str, bool]
    recommendations: List[str]
