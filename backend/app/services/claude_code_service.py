# backend/app/services/claude_code_service.py
import asyncio
import json
import subprocess
import tempfile
import os
from typing import Dict, List, Optional, Any
from datetime import datetime
import aiohttp
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.incident import Incident
from app.schemas.ai import AutoResolutionPlan, ResolutionStep, RiskLevel, CommandType


class ClaudeCodeService:
    """Integration service for Claude Code automated incident resolution"""
    
    def __init__(self, db: AsyncSession, api_key: Optional[str] = None):
        self.db = db
        self.api_key = api_key or settings.CLAUDE_CODE_API_KEY
        self.base_url = "https://api.anthropic.com/v1/claude-code"  # Placeholder URL
        
    async def generate_resolution_plan(
        self, 
        incident: Incident, 
        context: Dict[str, Any] = None
    ) -> AutoResolutionPlan:
        """Generate automated resolution plan using Claude Code"""
        
        if not self.api_key:
            raise ValueError("Claude Code API key not configured")
        
        # Prepare incident context for Claude Code
        incident_context = {
            "title": incident.title,
            "description": incident.description,
            "severity": incident.severity.value,
            "created_at": incident.created_at.isoformat(),
            "tags": incident.tags or [],
            "affected_systems": self._extract_systems_from_incident(incident),
            "infrastructure_context": context or {}
        }
        
        try:
            # Call Claude Code API for resolution planning
            resolution_plan = await self._call_claude_code_api(
                "generate_resolution",
                incident_context
            )
            
            # Convert Claude Code response to our format
            return self._convert_claude_response_to_plan(resolution_plan, incident)
            
        except Exception as e:
            # Fallback to template-based resolution if API fails
            return await self._generate_fallback_resolution(incident)
    
    async def execute_resolution_step(
        self, 
        step: ResolutionStep, 
        dry_run: bool = True,
        workspace_path: str = "/tmp"
    ) -> Dict[str, Any]:
        """Execute a single resolution step via Claude Code"""
        
        if step.command_type == CommandType.CLI_COMMAND:
            return await self._execute_cli_command(step, dry_run, workspace_path)
        elif step.command_type == CommandType.API_CALL:
            return await self._execute_api_call(step, dry_run)
        elif step.command_type == CommandType.KUBERNETES:
            return await self._execute_kubernetes_command(step, dry_run)
        elif step.command_type == CommandType.TERRAFORM:
            return await self._execute_terraform_command(step, dry_run, workspace_path)
        else:
            return {
                "status": "error",
                "message": f"Unsupported command type: {step.command_type}",
                "output": ""
            }
    
    async def validate_resolution_plan(
        self, 
        plan: AutoResolutionPlan,
        infrastructure_context: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Validate resolution plan before execution"""
        
        validation_results = {
            "valid": True,
            "warnings": [],
            "errors": [],
            "risk_assessment": plan.risk_level,
            "estimated_impact": "low"
        }
        
        # Check for dangerous commands
        dangerous_patterns = [
            "rm -rf", "dd if=", "mkfs", "fdisk", 
            "shutdown", "reboot", "killall",
            "DROP TABLE", "DELETE FROM", "TRUNCATE",
            "format", "del /f", "rmdir /s"
        ]
        
        for step in plan.steps:
            command = step.command.lower()
            
            # Check for dangerous patterns
            for pattern in dangerous_patterns:
                if pattern in command:
                    validation_results["errors"].append(
                        f"Step {step.order}: Dangerous command detected - {pattern}"
                    )
                    validation_results["valid"] = False
            
            # Check for missing rollback commands on critical steps
            if step.critical and not step.rollback_command:
                validation_results["warnings"].append(
                    f"Step {step.order}: Critical step without rollback command"
                )
            
            # Validate command syntax
            syntax_check = await self._validate_command_syntax(step)
            if not syntax_check["valid"]:
                validation_results["errors"].append(
                    f"Step {step.order}: Invalid syntax - {syntax_check['error']}"
                )
                validation_results["valid"] = False
        
        # Assess overall risk
        if len(validation_results["errors"]) > 0:
            validation_results["risk_assessment"] = RiskLevel.CRITICAL
        elif len(validation_results["warnings"]) > 2:
            validation_results["risk_assessment"] = RiskLevel.HIGH
        
        return validation_results
    
    async def _call_claude_code_api(
        self, 
        endpoint: str, 
        payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Make API call to Claude Code service"""
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "X-API-Version": "2024-01-01"
        }
        
        # Note: This is a placeholder implementation
        # The actual Claude Code API may have different endpoints and formats
        
        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(
                    f"{self.base_url}/{endpoint}",
                    headers=headers,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=60)
                ) as response:
                    
                    if response.status == 200:
                        return await response.json()
                    elif response.status == 401:
                        raise ValueError("Invalid Claude Code API key")
                    elif response.status == 429:
                        raise ValueError("Claude Code API rate limit exceeded")
                    else:
                        error_text = await response.text()
                        raise ValueError(f"Claude Code API error: {error_text}")
                        
            except aiohttp.ClientError as e:
                raise ValueError(f"Claude Code API connection failed: {str(e)}")
    
    def _convert_claude_response_to_plan(
        self, 
        claude_response: Dict[str, Any], 
        incident: Incident
    ) -> AutoResolutionPlan:
        """Convert Claude Code API response to our AutoResolutionPlan format"""
        
        # Parse Claude Code response structure
        steps = []
        for i, claude_step in enumerate(claude_response.get("steps", [])):
            step = ResolutionStep(
                order=i + 1,
                description=claude_step.get("description", ""),
                command=claude_step.get("command", ""),
                command_type=CommandType(claude_step.get("type", "cli_command")),
                expected_result=claude_step.get("expected_output", ""),
                rollback_command=claude_step.get("rollback", None),
                timeout_seconds=claude_step.get("timeout", 300),
                critical=claude_step.get("critical", False)
            )
            steps.append(step)
        
        return AutoResolutionPlan(
            provider="claude_code",
            executable=claude_response.get("executable", True),
            confidence_score=claude_response.get("confidence", 0.8),
            estimated_time_minutes=claude_response.get("estimated_time", 15),
            risk_level=RiskLevel(claude_response.get("risk_level", "medium")),
            steps=steps,
            human_verification_required=claude_response.get("requires_approval", True),
            audit_trail=f"Generated by Claude Code for incident {incident.id}",
            prerequisites=claude_response.get("prerequisites", []),
            success_criteria=claude_response.get("success_criteria", [])
        )
    
    async def _generate_fallback_resolution(self, incident: Incident) -> AutoResolutionPlan:
        """Generate basic resolution plan when Claude Code is unavailable"""
        
        # Template-based resolution based on incident type
        incident_text = (incident.title + " " + (incident.description or "")).lower()
        
        if "database" in incident_text or "db" in incident_text:
            steps = self._get_database_troubleshooting_steps()
        elif "api" in incident_text or "service" in incident_text:
            steps = self._get_service_troubleshooting_steps()
        elif "memory" in incident_text or "cpu" in incident_text:
            steps = self._get_resource_troubleshooting_steps()
        else:
            steps = self._get_generic_troubleshooting_steps()
        
        return AutoResolutionPlan(
            provider="claude_code",
            executable=True,
            confidence_score=0.6,
            estimated_time_minutes=20,
            risk_level=RiskLevel.MEDIUM,
            steps=steps,
            human_verification_required=True,
            audit_trail=f"Fallback template resolution for incident {incident.id}",
            prerequisites=["kubectl access", "SSH access"],
            success_criteria=["Service health restored", "Metrics return to normal"]
        )
    
    def _get_database_troubleshooting_steps(self) -> List[ResolutionStep]:
        """Database-specific troubleshooting steps"""
        return [
            ResolutionStep(
                order=1,
                description="Check database connection",
                command="pg_isready -h localhost -p 5432",
                command_type=CommandType.CLI_COMMAND,
                expected_result="localhost:5432 - accepting connections",
                rollback_command=None,
                timeout_seconds=30
            ),
            ResolutionStep(
                order=2,
                description="Check database disk space",
                command="df -h /var/lib/postgresql",
                command_type=CommandType.CLI_COMMAND,
                expected_result="Disk usage information",
                rollback_command=None,
                timeout_seconds=30
            ),
            ResolutionStep(
                order=3,
                description="Restart database if needed",
                command="sudo systemctl restart postgresql",
                command_type=CommandType.CLI_COMMAND,
                expected_result="Service restarted successfully",
                rollback_command="sudo systemctl stop postgresql",
                timeout_seconds=60,
                critical=True
            )
        ]
    
    def _get_service_troubleshooting_steps(self) -> List[ResolutionStep]:
        """Service-specific troubleshooting steps"""
        return [
            ResolutionStep(
                order=1,
                description="Check service health",
                command="curl -f http://localhost:8080/health",
                command_type=CommandType.API_CALL,
                expected_result="HTTP 200 OK",
                rollback_command=None,
                timeout_seconds=30
            ),
            ResolutionStep(
                order=2,
                description="Check service logs",
                command="tail -n 50 /var/log/service.log",
                command_type=CommandType.CLI_COMMAND,
                expected_result="Recent log entries",
                rollback_command=None,
                timeout_seconds=30
            ),
            ResolutionStep(
                order=3,
                description="Restart service",
                command="sudo systemctl restart myservice",
                command_type=CommandType.CLI_COMMAND,
                expected_result="Service restarted",
                rollback_command="sudo systemctl stop myservice",
                timeout_seconds=60,
                critical=True
            )
        ]
    
    def _get_resource_troubleshooting_steps(self) -> List[ResolutionStep]:
        """Resource usage troubleshooting steps"""
        return [
            ResolutionStep(
                order=1,
                description="Check system resources",
                command="free -h && top -bn1 | head -20",
                command_type=CommandType.CLI_COMMAND,
                expected_result="Resource usage information",
                rollback_command=None,
                timeout_seconds=30
            ),
            ResolutionStep(
                order=2,
                description="Identify resource-heavy processes",
                command="ps aux --sort=-%cpu | head -10",
                command_type=CommandType.CLI_COMMAND,
                expected_result="Top CPU-consuming processes",
                rollback_command=None,
                timeout_seconds=30
            ),
            ResolutionStep(
                order=3,
                description="Scale application if containerized",
                command="kubectl scale deployment myapp --replicas=3",
                command_type=CommandType.KUBERNETES,
                expected_result="Deployment scaled",
                rollback_command="kubectl scale deployment myapp --replicas=1",
                timeout_seconds=120,
                critical=True
            )
        ]
    
    def _get_generic_troubleshooting_steps(self) -> List[ResolutionStep]:
        """Generic troubleshooting steps"""
        return [
            ResolutionStep(
                order=1,
                description="Check system status",
                command="systemctl status",
                command_type=CommandType.CLI_COMMAND,
                expected_result="System status information",
                rollback_command=None,
                timeout_seconds=30
            ),
            ResolutionStep(
                order=2,
                description="Check recent logs",
                command="journalctl -n 50 --no-pager",
                command_type=CommandType.CLI_COMMAND,
                expected_result="Recent system logs",
                rollback_command=None,
                timeout_seconds=30
            ),
            ResolutionStep(
                order=3,
                description="Verify network connectivity",
                command="ping -c 3 8.8.8.8",
                command_type=CommandType.CLI_COMMAND,
                expected_result="Network connectivity confirmed",
                rollback_command=None,
                timeout_seconds=30
            )
        ]
    
    async def _execute_cli_command(
        self, 
        step: ResolutionStep, 
        dry_run: bool,
        workspace_path: str
    ) -> Dict[str, Any]:
        """Execute CLI command with safety checks"""
        
        if dry_run:
            return {
                "status": "success",
                "message": f"Command simulated: {step.command}",
                "output": f"[DRY RUN] Would execute: {step.command}",
                "execution_time": 0.1
            }
        
        try:
            # Security: Use subprocess with shell=False when possible
            start_time = asyncio.get_event_loop().time()
            
            process = await asyncio.create_subprocess_shell(
                step.command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=workspace_path
            )
            
            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(), 
                    timeout=step.timeout_seconds
                )
                
                execution_time = asyncio.get_event_loop().time() - start_time
                
                if process.returncode == 0:
                    return {
                        "status": "success",
                        "message": "Command executed successfully",
                        "output": stdout.decode('utf-8'),
                        "execution_time": execution_time
                    }
                else:
                    return {
                        "status": "error",
                        "message": f"Command failed with exit code {process.returncode}",
                        "output": stderr.decode('utf-8'),
                        "execution_time": execution_time
                    }
                    
            except asyncio.TimeoutError:
                process.kill()
                return {
                    "status": "timeout",
                    "message": f"Command timed out after {step.timeout_seconds} seconds",
                    "output": "",
                    "execution_time": step.timeout_seconds
                }
                
        except Exception as e:
            return {
                "status": "error",
                "message": f"Command execution failed: {str(e)}",
                "output": "",
                "execution_time": 0
            }
    
    async def _execute_api_call(self, step: ResolutionStep, dry_run: bool) -> Dict[str, Any]:
        """Execute API call"""
        
        if dry_run:
            return {
                "status": "success",
                "message": f"API call simulated: {step.command}",
                "output": "[DRY RUN] API call would be made",
                "execution_time": 0.1
            }
        
        try:
            # Parse command as HTTP request
            parts = step.command.split()
            if not parts:
                raise ValueError("Invalid API command format")
            
            method = parts[0].upper() if parts[0].upper() in ['GET', 'POST', 'PUT', 'DELETE'] else 'GET'
            url = parts[1] if len(parts) > 1 else parts[0]
            
            start_time = asyncio.get_event_loop().time()
            
            async with aiohttp.ClientSession() as session:
                async with session.request(
                    method, 
                    url, 
                    timeout=aiohttp.ClientTimeout(total=step.timeout_seconds)
                ) as response:
                    
                    execution_time = asyncio.get_event_loop().time() - start_time
                    response_text = await response.text()
                    
                    if response.status < 400:
                        return {
                            "status": "success",
                            "message": f"API call successful: {response.status}",
                            "output": response_text[:1000],  # Limit output
                            "execution_time": execution_time
                        }
                    else:
                        return {
                            "status": "error",
                            "message": f"API call failed: {response.status}",
                            "output": response_text[:1000],
                            "execution_time": execution_time
                        }
                        
        except Exception as e:
            return {
                "status": "error",
                "message": f"API call failed: {str(e)}",
                "output": "",
                "execution_time": 0
            }
    
    async def _execute_kubernetes_command(
        self, 
        step: ResolutionStep, 
        dry_run: bool
    ) -> Dict[str, Any]:
        """Execute Kubernetes command"""
        
        if dry_run:
            return {
                "status": "success",
                "message": f"Kubernetes command simulated: {step.command}",
                "output": "[DRY RUN] kubectl command would be executed",
                "execution_time": 0.1
            }
        
        # Prepend kubectl if not present
        command = step.command
        if not command.startswith('kubectl'):
            command = f"kubectl {command}"
        
        # Use the CLI execution method for kubectl commands
        kubectl_step = ResolutionStep(
            order=step.order,
            description=step.description,
            command=command,
            command_type=CommandType.CLI_COMMAND,
            expected_result=step.expected_result,
            rollback_command=step.rollback_command,
            timeout_seconds=step.timeout_seconds,
            critical=step.critical
        )
        
        return await self._execute_cli_command(kubectl_step, dry_run, "/tmp")
    
    async def _execute_terraform_command(
        self, 
        step: ResolutionStep, 
        dry_run: bool,
        workspace_path: str
    ) -> Dict[str, Any]:
        """Execute Terraform command"""
        
        if dry_run:
            return {
                "status": "success",
                "message": f"Terraform command simulated: {step.command}",
                "output": "[DRY RUN] terraform command would be executed",
                "execution_time": 0.1
            }
        
        # Ensure we're in a terraform workspace
        if not os.path.exists(os.path.join(workspace_path, "*.tf")):
            return {
                "status": "error",
                "message": "No terraform files found in workspace",
                "output": "",
                "execution_time": 0
            }
        
        # Execute terraform command
        terraform_step = ResolutionStep(
            order=step.order,
            description=step.description,
            command=f"terraform {step.command}",
            command_type=CommandType.CLI_COMMAND,
            expected_result=step.expected_result,
            rollback_command=step.rollback_command,
            timeout_seconds=step.timeout_seconds,
            critical=step.critical
        )
        
        return await self._execute_cli_command(terraform_step, dry_run, workspace_path)
    
    async def _validate_command_syntax(self, step: ResolutionStep) -> Dict[str, Any]:
        """Validate command syntax without execution"""
        
        try:
            if step.command_type == CommandType.CLI_COMMAND:
                # Basic shell command validation
                if not step.command.strip():
                    return {"valid": False, "error": "Empty command"}
                
                # Check for basic shell injection patterns
                dangerous_chars = [';', '&&', '||', '|', '>', '>>', '<']
                if any(char in step.command for char in dangerous_chars):
                    return {"valid": False, "error": "Potentially unsafe command structure"}
                
            elif step.command_type == CommandType.API_CALL:
                # Basic URL validation
                if not any(step.command.startswith(proto) for proto in ['http://', 'https://', 'curl']):
                    return {"valid": False, "error": "Invalid API call format"}
            
            elif step.command_type == CommandType.KUBERNETES:
                # Validate kubectl command structure
                if not step.command.strip():
                    return {"valid": False, "error": "Empty kubectl command"}
            
            return {"valid": True, "error": None}
            
        except Exception as e:
            return {"valid": False, "error": f"Validation error: {str(e)}"}
    
    def _extract_systems_from_incident(self, incident: Incident) -> List[str]:
        """Extract affected systems from incident data"""
        
        systems = []
        text = (incident.title + " " + (incident.description or "")).lower()
        
        # System keywords mapping
        system_keywords = {
            'database': ['postgres', 'mysql', 'mongodb', 'redis', 'db'],
            'api': ['api', 'service', 'endpoint', 'rest'],
            'web': ['nginx', 'apache', 'web', 'frontend'],
            'queue': ['kafka', 'rabbitmq', 'sqs', 'queue'],
            'cache': ['redis', 'memcached', 'cache'],
            'auth': ['auth', 'login', 'oauth', 'jwt'],
            'payment': ['payment', 'billing', 'stripe', 'paypal']
        }
        
        for system, keywords in system_keywords.items():
            if any(keyword in text for keyword in keywords):
                systems.append(system)
        
        return systems if systems else ['general']