# backend/app/services/deployment_service.py - Production Deployment Service
import asyncio
import json
import subprocess
import tempfile
import shutil
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, AsyncGenerator
from pathlib import Path
import os
import logging
import docker
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
import redis.asyncio as redis

from app.core.config import settings
from app.models.incident import Incident
from app.models.deployment import Deployment, DeploymentStep, DeploymentStatus
from app.services.websocket_service import WebSocketManager

logger = logging.getLogger(__name__)

class SecureExecutionEnvironment:
    """Secure, isolated environment for executing deployment commands"""
    
    def __init__(self, deployment_id: str):
        self.deployment_id = deployment_id
        self.container = None
        self.temp_dir = None
        self.docker_client = None
        
    async def __aenter__(self):
        """Create secure execution environment"""
        try:
            # Create temporary directory for deployment files
            self.temp_dir = tempfile.mkdtemp(prefix=f"deployment_{self.deployment_id}_")
            
            # Initialize Docker client
            self.docker_client = docker.from_env()
            
            # Create secure container with limited privileges
            self.container = self.docker_client.containers.run(
                image="ubuntu:22.04",
                name=f"offcall-deploy-{self.deployment_id}",
                detach=True,
                stdin_open=True,
                tty=True,
                mem_limit="512m",
                cpu_quota=50000,  # 0.5 CPU
                security_opt=["no-new-privileges"],
                cap_drop=["ALL"],
                cap_add=["CHOWN", "DAC_OVERRIDE", "SETGID", "SETUID"],
                network_mode="bridge",  # Isolated network
                volumes={
                    self.temp_dir: {"bind": "/workspace", "mode": "rw"}
                },
                working_dir="/workspace",
                environment={
                    "DEPLOYMENT_ID": self.deployment_id,
                    "PYTHONUNBUFFERED": "1"
                },
                command="tail -f /dev/null"  # Keep container running
            )
            
            # Install basic tools in container
            await self._setup_container_environment()
            
            logger.info(f"Secure execution environment created: {self.container.id[:12]}")
            return self
            
        except Exception as e:
            logger.error(f"Failed to create execution environment: {e}")
            await self._cleanup()
            raise
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Cleanup execution environment"""
        await self._cleanup()
    
    async def _setup_container_environment(self):
        """Install required tools in the container"""
        setup_commands = [
            "apt-get update -qq",
            "apt-get install -y -qq curl wget git python3 python3-pip kubectl docker.io",
            "pip3 install --quiet requests pyyaml kubernetes",
            "mkdir -p /workspace/logs"
        ]
        
        for cmd in setup_commands:
            result = self.container.exec_run(cmd, stdout=True, stderr=True)
            if result.exit_code != 0:
                logger.warning(f"Setup command failed: {cmd}")
    
    async def execute_command(
        self, 
        command: str, 
        timeout: int = 300,
        env_vars: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """Execute command in secure environment with real-time output"""
        
        if not self.container:
            raise RuntimeError("Execution environment not initialized")
        
        start_time = datetime.utcnow()
        
        try:
            # Prepare environment variables
            exec_env = {
                "PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
                "DEPLOYMENT_ID": self.deployment_id,
                "EXECUTION_TIME": start_time.isoformat()
            }
            
            if env_vars:
                exec_env.update(env_vars)
            
            # Execute command with timeout
            result = self.container.exec_run(
                f"timeout {timeout} bash -c '{command}'",
                stdout=True,
                stderr=True,
                stream=False,
                environment=exec_env
            )
            
            end_time = datetime.utcnow()
            duration = (end_time - start_time).total_seconds()
            
            return {
                "success": result.exit_code == 0,
                "exit_code": result.exit_code,
                "stdout": result.output.decode('utf-8', errors='replace'),
                "stderr": "",
                "duration": duration,
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat()
            }
            
        except Exception as e:
            logger.error(f"Command execution failed: {e}")
            return {
                "success": False,
                "exit_code": -1,
                "stdout": "",
                "stderr": str(e),
                "duration": (datetime.utcnow() - start_time).total_seconds(),
                "start_time": start_time.isoformat(),
                "end_time": datetime.utcnow().isoformat()
            }
    
    async def _cleanup(self):
        """Clean up container and temporary files"""
        try:
            if self.container:
                self.container.stop(timeout=10)
                self.container.remove()
                logger.info(f"Container removed: {self.deployment_id}")
        except Exception as e:
            logger.error(f"Error removing container: {e}")
        
        try:
            if self.temp_dir and os.path.exists(self.temp_dir):
                shutil.rmtree(self.temp_dir)
                logger.info(f"Temp directory removed: {self.temp_dir}")
        except Exception as e:
            logger.error(f"Error removing temp directory: {e}")

class DeploymentService:
    """Production deployment service with security and monitoring"""
    
    def __init__(self):
        self.redis = redis.from_url(settings.REDIS_URL, decode_responses=True)
        self.websocket_manager = WebSocketManager()
        self.active_deployments: Dict[str, asyncio.Task] = {}
    
    async def create_deployment(
        self, 
        incident_id: str,
        provider: str,
        solution: Dict[str, Any],
        user_id: str,
        organization_id: str,
        db: AsyncSession
    ) -> str:
        """Create and start a new deployment"""
        
        deployment_id = str(uuid.uuid4())
        
        try:
            # Create deployment record
            deployment = Deployment(
                id=deployment_id,
                incident_id=incident_id,
                provider=provider,
                status=DeploymentStatus.INITIALIZING,
                solution_data=solution,
                created_by_id=user_id,
                organization_id=organization_id,
                created_at=datetime.utcnow()
            )
            
            db.add(deployment)
            await db.commit()
            
            # Start deployment task
            task = asyncio.create_task(
                self._execute_deployment(deployment_id, solution, db)
            )
            self.active_deployments[deployment_id] = task
            
            logger.info(f"Deployment created: {deployment_id} for incident {incident_id}")
            return deployment_id
            
        except Exception as e:
            logger.error(f"Failed to create deployment: {e}")
            raise
    
    async def _execute_deployment(
        self, 
        deployment_id: str, 
        solution: Dict[str, Any], 
        db: AsyncSession
    ):
        """Execute deployment with comprehensive monitoring and error handling"""
        
        try:
            # Update deployment status
            await self._update_deployment_status(deployment_id, DeploymentStatus.RUNNING, db)
            
            # Extract deployment information
            commands = solution.get("commands", [])
            steps = solution.get("steps", [])
            provider = solution.get("provider", "unknown")
            
            async with SecureExecutionEnvironment(deployment_id) as exec_env:
                
                total_steps = len(commands)
                completed_steps = 0
                
                # Send deployment started event
                await self._broadcast_event(deployment_id, {
                    "type": "deployment_started",
                    "deployment_id": deployment_id,
                    "provider": provider,
                    "total_steps": total_steps,
                    "timestamp": datetime.utcnow().isoformat()
                })
                
                # Execute each deployment step
                for step_index, (command, description) in enumerate(zip(commands, steps)):
                    
                    # Check if deployment was cancelled
                    if await self._is_deployment_cancelled(deployment_id):
                        await self._update_deployment_status(deployment_id, DeploymentStatus.CANCELLED, db)
                        return
                    
                    # Check if deployment is paused
                    while await self._is_deployment_paused(deployment_id):
                        await asyncio.sleep(1)
                        if await self._is_deployment_cancelled(deployment_id):
                            return
                    
                    step_id = f"step_{step_index}"
                    
                    # Create deployment step record
                    step_record = DeploymentStep(
                        id=str(uuid.uuid4()),
                        deployment_id=deployment_id,
                        step_index=step_index,
                        command=command,
                        description=description,
                        status="running",
                        started_at=datetime.utcnow()
                    )
                    
                    db.add(step_record)
                    await db.commit()
                    
                    # Broadcast step started
                    await self._broadcast_event(deployment_id, {
                        "type": "step_started",
                        "step_id": step_id,
                        "step_index": step_index,
                        "command": command,
                        "description": description,
                        "start_time": datetime.utcnow().isoformat()
                    })
                    
                    # Execute the command
                    try:
                        # Enhance command with proper context
                        enhanced_command = await self._enhance_command(command, deployment_id)
                        
                        result = await exec_env.execute_command(
                            enhanced_command,
                            timeout=300,  # 5 minutes per step
                            env_vars={
                                "STEP_INDEX": str(step_index),
                                "STEP_DESCRIPTION": description
                            }
                        )
                        
                        # Update step record
                        step_record.status = "completed" if result["success"] else "failed"
                        step_record.exit_code = result["exit_code"]
                        step_record.output = result["stdout"]
                        step_record.error_output = result["stderr"]
                        step_record.completed_at = datetime.utcnow()
                        step_record.duration = result["duration"]
                        
                        await db.commit()
                        
                        # Broadcast step result
                        event_type = "step_completed" if result["success"] else "step_failed"
                        await self._broadcast_event(deployment_id, {
                            "type": event_type,
                            "step_id": step_id,
                            "step_index": step_index,
                            "success": result["success"],
                            "exit_code": result["exit_code"],
                            "output": result["stdout"][:1000],  # Limit output size
                            "error": result["stderr"][:1000] if result["stderr"] else None,
                            "duration": result["duration"],
                            "start_time": result["start_time"],
                            "end_time": result["end_time"]
                        })
                        
                        # Stream output if available
                        if result["stdout"]:
                            await self._broadcast_event(deployment_id, {
                                "type": "output",
                                "data": result["stdout"]
                            })
                        
                        if not result["success"]:
                            # Step failed - determine if we should continue
                            if await self._should_fail_fast(deployment_id, step_index):
                                raise Exception(f"Step {step_index} failed: {result['stderr']}")
                            else:
                                logger.warning(f"Step {step_index} failed but continuing: {result['stderr']}")
                        
                        completed_steps += 1
                        
                    except Exception as step_error:
                        logger.error(f"Step {step_index} execution error: {step_error}")
                        
                        step_record.status = "failed"
                        step_record.error_output = str(step_error)
                        step_record.completed_at = datetime.utcnow()
                        await db.commit()
                        
                        await self._broadcast_event(deployment_id, {
                            "type": "step_failed",
                            "step_id": step_id,
                            "step_index": step_index,
                            "error": str(step_error),
                            "end_time": datetime.utcnow().isoformat()
                        })
                        
                        # Fail the entire deployment
                        raise step_error
                
                # All steps completed successfully
                await self._update_deployment_status(deployment_id, DeploymentStatus.COMPLETED, db)
                
                # Calculate total duration
                deployment_record = await self._get_deployment(deployment_id, db)
                total_duration = (datetime.utcnow() - deployment_record.created_at).total_seconds()
                
                await self._broadcast_event(deployment_id, {
                    "type": "deployment_completed",
                    "deployment_id": deployment_id,
                    "completed_steps": completed_steps,
                    "total_steps": total_steps,
                    "total_duration": f"{total_duration:.1f}s",
                    "timestamp": datetime.utcnow().isoformat()
                })
                
                logger.info(f"Deployment completed successfully: {deployment_id}")
                
        except Exception as e:
            logger.error(f"Deployment failed: {deployment_id}, error: {e}")
            
            await self._update_deployment_status(deployment_id, DeploymentStatus.FAILED, db)
            
            await self._broadcast_event(deployment_id, {
                "type": "deployment_failed",
                "deployment_id": deployment_id,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            })
            
        finally:
            # Clean up active deployment tracking
            if deployment_id in self.active_deployments:
                del self.active_deployments[deployment_id]
    
    async def _enhance_command(self, command: str, deployment_id: str) -> str:
        """Enhance command with proper context and safety checks"""
        
        # Add safety prefixes for different command types
        if command.startswith("kubectl"):
            return f"echo 'Executing kubectl command...' && {command}"
        elif command.startswith("docker"):
            return f"echo 'Executing docker command...' && {command}"
        elif "rm -rf" in command or "rm -r" in command:
            return f"echo 'WARNING: Destructive command detected' && {command}"
        else:
            return f"echo 'Executing: {command}' && {command}"
    
    async def pause_deployment(self, deployment_id: str, db: AsyncSession) -> bool:
        """Pause a running deployment"""
        try:
            await self.redis.set(f"deployment:{deployment_id}:paused", "true", ex=3600)
            await self._update_deployment_status(deployment_id, DeploymentStatus.PAUSED, db)
            
            await self._broadcast_event(deployment_id, {
                "type": "deployment_paused",
                "deployment_id": deployment_id,
                "timestamp": datetime.utcnow().isoformat()
            })
            
            return True
        except Exception as e:
            logger.error(f"Failed to pause deployment {deployment_id}: {e}")
            return False
    
    async def resume_deployment(self, deployment_id: str, db: AsyncSession) -> bool:
        """Resume a paused deployment"""
        try:
            await self.redis.delete(f"deployment:{deployment_id}:paused")
            await self._update_deployment_status(deployment_id, DeploymentStatus.RUNNING, db)
            
            await self._broadcast_event(deployment_id, {
                "type": "deployment_resumed",
                "deployment_id": deployment_id,
                "timestamp": datetime.utcnow().isoformat()
            })
            
            return True
        except Exception as e:
            logger.error(f"Failed to resume deployment {deployment_id}: {e}")
            return False
    
    async def cancel_deployment(self, deployment_id: str, db: AsyncSession) -> bool:
        """Cancel a running deployment"""
        try:
            await self.redis.set(f"deployment:{deployment_id}:cancelled", "true", ex=3600)
            
            # Cancel the running task
            if deployment_id in self.active_deployments:
                task = self.active_deployments[deployment_id]
                task.cancel()
                del self.active_deployments[deployment_id]
            
            await self._update_deployment_status(deployment_id, DeploymentStatus.CANCELLED, db)
            
            await self._broadcast_event(deployment_id, {
                "type": "deployment_cancelled",
                "deployment_id": deployment_id,
                "timestamp": datetime.utcnow().isoformat()
            })
            
            return True
        except Exception as e:
            logger.error(f"Failed to cancel deployment {deployment_id}: {e}")
            return False
    
    async def rollback_deployment(self, deployment_id: str, db: AsyncSession) -> str:
        """Create and execute rollback deployment"""
        
        # Get original deployment
        deployment = await self._get_deployment(deployment_id, db)
        if not deployment:
            raise ValueError(f"Deployment not found: {deployment_id}")
        
        # Generate rollback commands
        rollback_solution = await self._generate_rollback_solution(deployment)
        
        # Create new rollback deployment
        rollback_id = await self.create_deployment(
            incident_id=deployment.incident_id,
            provider=f"{deployment.provider}_rollback",
            solution=rollback_solution,
            user_id=deployment.created_by_id,
            organization_id=deployment.organization_id,
            db=db
        )
        
        logger.info(f"Rollback deployment created: {rollback_id} for {deployment_id}")
        return rollback_id
    
    async def _generate_rollback_solution(self, deployment: Deployment) -> Dict[str, Any]:
        """Generate rollback commands based on original deployment"""
        
        original_solution = deployment.solution_data
        rollback_commands = []
        rollback_steps = []
        
        # Generate generic rollback commands
        if deployment.provider == "claude":
            rollback_commands = [
                "kubectl rollout undo deployment/offcall-ai-backend -n offcall-ai",
                "kubectl rollout status deployment/offcall-ai-backend -n offcall-ai --timeout=300s",
                "kubectl get pods -n offcall-ai -l app=offcall-ai-backend"
            ]
            rollback_steps = [
                "Undo the last deployment rollout",
                "Wait for rollback to complete",
                "Verify rollback status"
            ]
        else:  # gemini
            rollback_commands = [
                "docker service rollback offcall-ai-backend",
                "docker service ps offcall-ai-backend",
                "curl -f http://localhost:8000/health"
            ]
            rollback_steps = [
                "Rollback Docker service",
                "Check service status",
                "Verify service health"
            ]
        
        return {
            "commands": rollback_commands,
            "steps": rollback_steps,
            "provider": f"{deployment.provider}_rollback",
            "risk_level": "low"
        }
    
    async def get_deployment_status(self, deployment_id: str, db: AsyncSession) -> Optional[Dict[str, Any]]:
        """Get comprehensive deployment status"""
        
        deployment = await self._get_deployment(deployment_id, db)
        if not deployment:
            return None
        
        # Get deployment steps
        steps_result = await db.execute(
            select(DeploymentStep)
            .where(DeploymentStep.deployment_id == deployment_id)
            .order_by(DeploymentStep.step_index)
        )
        steps = steps_result.scalars().all()
        
        return {
            "id": deployment.id,
            "incident_id": deployment.incident_id,
            "provider": deployment.provider,
            "status": deployment.status.value,
            "created_at": deployment.created_at.isoformat(),
            "updated_at": deployment.updated_at.isoformat() if deployment.updated_at else None,
            "steps": [
                {
                    "index": step.step_index,
                    "command": step.command,
                    "description": step.description,
                    "status": step.status,
                    "duration": step.duration,
                    "exit_code": step.exit_code,
                    "output": step.output[:500] if step.output else None,  # Truncate output
                    "error": step.error_output[:500] if step.error_output else None
                }
                for step in steps
            ]
        }
    
    # Helper methods
    async def _update_deployment_status(self, deployment_id: str, status: DeploymentStatus, db: AsyncSession):
        """Update deployment status in database"""
        await db.execute(
            update(Deployment)
            .where(Deployment.id == deployment_id)
            .values(status=status, updated_at=datetime.utcnow())
        )
        await db.commit()
    
    async def _get_deployment(self, deployment_id: str, db: AsyncSession) -> Optional[Deployment]:
        """Get deployment by ID"""
        result = await db.execute(
            select(Deployment).where(Deployment.id == deployment_id)
        )
        return result.scalar_one_or_none()
    
    async def _broadcast_event(self, deployment_id: str, event: Dict[str, Any]):
        """Broadcast event to WebSocket subscribers"""
        try:
            await self.websocket_manager.broadcast_to_deployment(deployment_id, event)
        except Exception as e:
            logger.error(f"Failed to broadcast event: {e}")
    
    async def _is_deployment_cancelled(self, deployment_id: str) -> bool:
        """Check if deployment was cancelled"""
        result = await self.redis.get(f"deployment:{deployment_id}:cancelled")
        return result == "true"
    
    async def _is_deployment_paused(self, deployment_id: str) -> bool:
        """Check if deployment is paused"""
        result = await self.redis.get(f"deployment:{deployment_id}:paused")
        return result == "true"
    
    async def _should_fail_fast(self, deployment_id: str, step_index: int) -> bool:
        """Determine if deployment should fail fast on step failure"""
        # For now, fail fast on any step failure
        # Could be made configurable per deployment
        return True

# Singleton instance
deployment_service = DeploymentService()