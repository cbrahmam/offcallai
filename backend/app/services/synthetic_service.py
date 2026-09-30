# backend/app/services/synthetic_service.py
import uuid
import httpx
import asyncio
import ssl
import socket
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_, desc
from sqlalchemy.orm import selectinload

from ..models.synthetic import (
    SyntheticCheck, SyntheticCheckResult, SyntheticCheckIncident, SyntheticLocation
)
from ..schemas.synthetic import (
    SyntheticCheckCreate, SyntheticCheckUpdate, SyntheticCheckResultCreate,
    SyntheticStats, AssertionSchema
)


class SyntheticService:
    """Service for managing synthetic monitoring checks"""

    def __init__(self, db: AsyncSession):
        self.db = db

    # ==================== Check CRUD ====================

    async def create_check(
        self,
        organization_id: uuid.UUID,
        data: SyntheticCheckCreate,
        created_by: Optional[uuid.UUID] = None
    ) -> SyntheticCheck:
        """Create a new synthetic check"""
        check = SyntheticCheck(
            id=uuid.uuid4(),
            organization_id=organization_id,
            created_by=created_by,
            assertions=[a.model_dump() for a in data.assertions] if data.assertions else [],
            **{k: v for k, v in data.model_dump().items() if k != 'assertions'}
        )
        self.db.add(check)
        await self.db.commit()
        await self.db.refresh(check)
        return check

    async def get_check(
        self,
        organization_id: uuid.UUID,
        check_id: uuid.UUID
    ) -> Optional[SyntheticCheck]:
        """Get a synthetic check by ID"""
        result = await self.db.execute(
            select(SyntheticCheck).where(
                and_(
                    SyntheticCheck.organization_id == organization_id,
                    SyntheticCheck.id == check_id
                )
            )
        )
        return result.scalar_one_or_none()

    async def list_checks(
        self,
        organization_id: uuid.UUID,
        check_type: Optional[str] = None,
        status: Optional[str] = None,
        current_status: Optional[str] = None,
        service_id: Optional[uuid.UUID] = None,
        page: int = 1,
        page_size: int = 50
    ) -> Tuple[List[SyntheticCheck], int]:
        """List synthetic checks with filters"""
        query = select(SyntheticCheck).where(
            SyntheticCheck.organization_id == organization_id
        )

        if check_type:
            query = query.where(SyntheticCheck.check_type == check_type)
        if status:
            query = query.where(SyntheticCheck.status == status)
        if current_status:
            query = query.where(SyntheticCheck.current_status == current_status)
        if service_id:
            query = query.where(SyntheticCheck.service_id == service_id)

        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        total = (await self.db.execute(count_query)).scalar()

        # Apply pagination and ordering
        query = query.order_by(SyntheticCheck.name)
        query = query.offset((page - 1) * page_size).limit(page_size)

        result = await self.db.execute(query)
        return result.scalars().all(), total

    async def update_check(
        self,
        organization_id: uuid.UUID,
        check_id: uuid.UUID,
        data: SyntheticCheckUpdate
    ) -> Optional[SyntheticCheck]:
        """Update a synthetic check"""
        check = await self.get_check(organization_id, check_id)
        if not check:
            return None

        update_data = data.model_dump(exclude_unset=True)
        if 'assertions' in update_data and update_data['assertions']:
            update_data['assertions'] = [
                a.model_dump() if hasattr(a, 'model_dump') else a
                for a in update_data['assertions']
            ]

        for key, value in update_data.items():
            setattr(check, key, value)

        check.updated_at = datetime.utcnow()
        await self.db.commit()
        await self.db.refresh(check)
        return check

    async def delete_check(
        self,
        organization_id: uuid.UUID,
        check_id: uuid.UUID
    ) -> bool:
        """Delete a synthetic check"""
        check = await self.get_check(organization_id, check_id)
        if not check:
            return False

        await self.db.delete(check)
        await self.db.commit()
        return True

    async def toggle_check(
        self,
        organization_id: uuid.UUID,
        check_id: uuid.UUID,
        status: str
    ) -> Optional[SyntheticCheck]:
        """Change check status (active/paused/disabled)"""
        check = await self.get_check(organization_id, check_id)
        if not check:
            return None

        check.status = status
        check.updated_at = datetime.utcnow()
        await self.db.commit()
        await self.db.refresh(check)
        return check

    # ==================== Check Results ====================

    async def record_result(
        self,
        organization_id: uuid.UUID,
        data: SyntheticCheckResultCreate
    ) -> SyntheticCheckResult:
        """Record a check execution result"""
        result = SyntheticCheckResult(
            id=uuid.uuid4(),
            organization_id=organization_id,
            **data.model_dump()
        )
        self.db.add(result)

        # Update check statistics
        check = await self.get_check(organization_id, data.check_id)
        if check:
            check.last_check_at = data.executed_at
            check.total_checks_24h = (check.total_checks_24h or 0) + 1

            if data.status == "success":
                check.last_success_at = data.executed_at
                check.consecutive_successes = (check.consecutive_successes or 0) + 1
                check.consecutive_failures = 0
                check.current_status = "up"
            else:
                check.last_failure_at = data.executed_at
                check.consecutive_failures = (check.consecutive_failures or 0) + 1
                check.consecutive_successes = 0
                check.failed_checks_24h = (check.failed_checks_24h or 0) + 1

                if check.consecutive_failures >= 3:
                    check.current_status = "down"
                elif check.consecutive_failures >= 1:
                    check.current_status = "degraded"

        await self.db.commit()
        await self.db.refresh(result)
        return result

    async def get_result(
        self,
        organization_id: uuid.UUID,
        result_id: uuid.UUID
    ) -> Optional[SyntheticCheckResult]:
        """Get a check result by ID"""
        result = await self.db.execute(
            select(SyntheticCheckResult).where(
                and_(
                    SyntheticCheckResult.organization_id == organization_id,
                    SyntheticCheckResult.id == result_id
                )
            )
        )
        return result.scalar_one_or_none()

    async def list_results(
        self,
        organization_id: uuid.UUID,
        check_id: Optional[uuid.UUID] = None,
        status: Optional[str] = None,
        location: Optional[str] = None,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
        page: int = 1,
        page_size: int = 100
    ) -> Tuple[List[SyntheticCheckResult], int]:
        """List check results with filters"""
        query = select(SyntheticCheckResult).where(
            SyntheticCheckResult.organization_id == organization_id
        )

        if check_id:
            query = query.where(SyntheticCheckResult.check_id == check_id)
        if status:
            query = query.where(SyntheticCheckResult.status == status)
        if location:
            query = query.where(SyntheticCheckResult.location == location)
        if since:
            query = query.where(SyntheticCheckResult.executed_at >= since)
        if until:
            query = query.where(SyntheticCheckResult.executed_at <= until)

        count_query = select(func.count()).select_from(query.subquery())
        total = (await self.db.execute(count_query)).scalar()

        query = query.order_by(desc(SyntheticCheckResult.executed_at))
        query = query.offset((page - 1) * page_size).limit(page_size)

        result = await self.db.execute(query)
        return result.scalars().all(), total

    # ==================== Execute Check ====================

    async def execute_check(
        self,
        organization_id: uuid.UUID,
        check_id: uuid.UUID,
        location: str = "default"
    ) -> SyntheticCheckResult:
        """Execute a synthetic check and record the result"""
        check = await self.get_check(organization_id, check_id)
        if not check:
            raise ValueError("Check not found")

        executed_at = datetime.utcnow()
        result_data = {
            "check_id": check_id,
            "status": "success",
            "location": location,
            "executed_at": executed_at,
            "assertions_passed": 0,
            "assertions_failed": 0,
            "assertion_results": []
        }

        try:
            if check.check_type in ["http", "api"]:
                result_data = await self._execute_http_check(check, result_data)
            elif check.check_type == "ssl":
                result_data = await self._execute_ssl_check(check, result_data)
            elif check.check_type == "tcp":
                result_data = await self._execute_tcp_check(check, result_data)
            elif check.check_type == "dns":
                result_data = await self._execute_dns_check(check, result_data)
            else:
                result_data["status"] = "error"
                result_data["error_type"] = "unsupported_check_type"
                result_data["error_message"] = f"Check type {check.check_type} is not supported"

        except Exception as e:
            result_data["status"] = "error"
            result_data["error_type"] = type(e).__name__
            result_data["error_message"] = str(e)

        # Record result
        return await self.record_result(
            organization_id,
            SyntheticCheckResultCreate(**result_data)
        )

    async def _execute_http_check(
        self,
        check: SyntheticCheck,
        result_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute HTTP/API check"""
        start_time = datetime.utcnow()

        try:
            async with httpx.AsyncClient(
                verify=check.verify_ssl,
                timeout=check.timeout_seconds
            ) as client:
                # Prepare request
                kwargs = {
                    "method": check.method or "GET",
                    "url": check.target_url,
                    "headers": check.headers or {},
                }

                if check.body:
                    if check.body_type == "json":
                        kwargs["json"] = check.body
                    else:
                        kwargs["content"] = check.body

                # Add auth
                if check.auth_type == "basic" and check.auth_config:
                    kwargs["auth"] = (
                        check.auth_config.get("username", ""),
                        check.auth_config.get("password", "")
                    )
                elif check.auth_type == "bearer" and check.auth_config:
                    kwargs["headers"]["Authorization"] = f"Bearer {check.auth_config.get('token', '')}"

                # Execute request
                response = await client.request(**kwargs)

                end_time = datetime.utcnow()
                duration_ms = (end_time - start_time).total_seconds() * 1000

                result_data["response_time_ms"] = duration_ms
                result_data["total_time_ms"] = duration_ms
                result_data["status_code"] = response.status_code
                result_data["response_size_bytes"] = len(response.content)
                result_data["response_headers"] = dict(response.headers)
                result_data["response_body_preview"] = response.text[:500] if response.text else None

                # Run assertions
                result_data = self._run_assertions(check, response, result_data)

        except httpx.TimeoutException:
            result_data["status"] = "timeout"
            result_data["error_type"] = "timeout"
            result_data["error_message"] = f"Request timed out after {check.timeout_seconds}s"

        except httpx.RequestError as e:
            result_data["status"] = "error"
            result_data["error_type"] = "request_error"
            result_data["error_message"] = str(e)

        return result_data

    async def _execute_ssl_check(
        self,
        check: SyntheticCheck,
        result_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute SSL certificate check"""
        try:
            from urllib.parse import urlparse
            parsed = urlparse(check.target_url)
            hostname = parsed.hostname
            port = parsed.port or 443

            context = ssl.create_default_context()
            with socket.create_connection((hostname, port), timeout=check.timeout_seconds) as sock:
                with context.wrap_socket(sock, server_hostname=hostname) as ssock:
                    cert = ssock.getpeercert()

                    # Parse certificate
                    not_after = datetime.strptime(cert['notAfter'], '%b %d %H:%M:%S %Y %Z')
                    days_until_expiry = (not_after - datetime.utcnow()).days

                    result_data["ssl_valid"] = True
                    result_data["ssl_expiry_date"] = not_after
                    result_data["ssl_days_until_expiry"] = days_until_expiry
                    result_data["ssl_subject"] = str(cert.get('subject', ''))
                    result_data["ssl_issuer"] = str(cert.get('issuer', ''))

                    # Check expiry threshold
                    if days_until_expiry < 0:
                        result_data["status"] = "failure"
                        result_data["error_message"] = "SSL certificate has expired"
                    elif check.ssl_check_expiry and days_until_expiry < check.ssl_expiry_warning_days:
                        result_data["status"] = "failure"
                        result_data["error_message"] = f"SSL certificate expires in {days_until_expiry} days"

        except ssl.SSLError as e:
            result_data["status"] = "failure"
            result_data["ssl_valid"] = False
            result_data["error_type"] = "ssl_error"
            result_data["error_message"] = str(e)

        except Exception as e:
            result_data["status"] = "error"
            result_data["error_type"] = type(e).__name__
            result_data["error_message"] = str(e)

        return result_data

    async def _execute_tcp_check(
        self,
        check: SyntheticCheck,
        result_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute TCP port check"""
        try:
            from urllib.parse import urlparse
            parsed = urlparse(check.target_url)
            hostname = parsed.hostname
            port = parsed.port or 80

            start_time = datetime.utcnow()

            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(check.timeout_seconds)
            result = sock.connect_ex((hostname, port))
            sock.close()

            end_time = datetime.utcnow()
            duration_ms = (end_time - start_time).total_seconds() * 1000

            result_data["response_time_ms"] = duration_ms
            result_data["total_time_ms"] = duration_ms

            if result == 0:
                result_data["status"] = "success"
            else:
                result_data["status"] = "failure"
                result_data["error_message"] = f"TCP connection failed (code: {result})"

        except socket.timeout:
            result_data["status"] = "timeout"
            result_data["error_message"] = f"TCP connection timed out after {check.timeout_seconds}s"

        except Exception as e:
            result_data["status"] = "error"
            result_data["error_type"] = type(e).__name__
            result_data["error_message"] = str(e)

        return result_data

    async def _execute_dns_check(
        self,
        check: SyntheticCheck,
        result_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute DNS resolution check"""
        try:
            from urllib.parse import urlparse
            parsed = urlparse(check.target_url)
            hostname = parsed.hostname

            start_time = datetime.utcnow()
            socket.gethostbyname(hostname)
            end_time = datetime.utcnow()

            duration_ms = (end_time - start_time).total_seconds() * 1000
            result_data["dns_time_ms"] = duration_ms
            result_data["response_time_ms"] = duration_ms
            result_data["status"] = "success"

        except socket.gaierror as e:
            result_data["status"] = "failure"
            result_data["error_type"] = "dns_error"
            result_data["error_message"] = str(e)

        except Exception as e:
            result_data["status"] = "error"
            result_data["error_type"] = type(e).__name__
            result_data["error_message"] = str(e)

        return result_data

    def _run_assertions(
        self,
        check: SyntheticCheck,
        response: httpx.Response,
        result_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Run assertions against the response"""
        if not check.assertions:
            return result_data

        assertion_results = []
        passed = 0
        failed = 0

        for assertion in check.assertions:
            assertion_result = {
                "assertion": assertion,
                "passed": False,
                "actual_value": None,
                "message": None
            }

            try:
                if assertion.get("type") == "status_code":
                    actual = response.status_code
                    assertion_result["actual_value"] = actual
                    assertion_result["passed"] = self._evaluate_assertion(
                        actual, assertion.get("operator", "equals"), assertion.get("value")
                    )

                elif assertion.get("type") == "response_time":
                    actual = result_data.get("response_time_ms", 0)
                    assertion_result["actual_value"] = actual
                    assertion_result["passed"] = self._evaluate_assertion(
                        actual, assertion.get("operator", "less_than"), assertion.get("value")
                    )

                elif assertion.get("type") == "body_contains":
                    actual = assertion.get("value") in response.text
                    assertion_result["actual_value"] = actual
                    assertion_result["passed"] = actual

                elif assertion.get("type") == "json_path":
                    import jsonpath_ng
                    expr = jsonpath_ng.parse(assertion.get("path", "$"))
                    matches = [m.value for m in expr.find(response.json())]
                    actual = matches[0] if matches else None
                    assertion_result["actual_value"] = actual
                    assertion_result["passed"] = self._evaluate_assertion(
                        actual, assertion.get("operator", "equals"), assertion.get("value")
                    )

                elif assertion.get("type") == "header":
                    header_name = assertion.get("name", "").lower()
                    actual = response.headers.get(header_name)
                    assertion_result["actual_value"] = actual
                    assertion_result["passed"] = self._evaluate_assertion(
                        actual, assertion.get("operator", "equals"), assertion.get("value")
                    )

            except Exception as e:
                assertion_result["message"] = str(e)
                assertion_result["passed"] = False

            if assertion_result["passed"]:
                passed += 1
            else:
                failed += 1

            assertion_results.append(assertion_result)

        result_data["assertions_passed"] = passed
        result_data["assertions_failed"] = failed
        result_data["assertion_results"] = assertion_results

        if failed > 0:
            result_data["status"] = "failure"

        return result_data

    def _evaluate_assertion(self, actual: Any, operator: str, expected: Any) -> bool:
        """Evaluate a single assertion"""
        if actual is None:
            return False

        if operator == "equals":
            return actual == expected
        elif operator == "not_equals":
            return actual != expected
        elif operator == "greater_than":
            return actual > expected
        elif operator == "less_than":
            return actual < expected
        elif operator == "greater_than_or_equals":
            return actual >= expected
        elif operator == "less_than_or_equals":
            return actual <= expected
        elif operator == "contains":
            return expected in str(actual)
        elif operator == "not_contains":
            return expected not in str(actual)
        elif operator == "regex":
            import re
            return bool(re.search(expected, str(actual)))

        return False

    # ==================== Locations ====================

    async def list_locations(self) -> Tuple[List[SyntheticLocation], int]:
        """List available synthetic check locations"""
        result = await self.db.execute(
            select(SyntheticLocation).where(SyntheticLocation.active == True)
            .order_by(SyntheticLocation.region, SyntheticLocation.name)
        )
        locations = result.scalars().all()
        return locations, len(locations)

    # ==================== Statistics ====================

    async def get_stats(self, organization_id: uuid.UUID) -> SyntheticStats:
        """Get synthetic monitoring statistics"""
        # Total and active checks
        total_result = await self.db.execute(
            select(func.count()).where(SyntheticCheck.organization_id == organization_id)
        )
        total_checks = total_result.scalar()

        active_result = await self.db.execute(
            select(func.count()).where(
                and_(
                    SyntheticCheck.organization_id == organization_id,
                    SyntheticCheck.status == "active"
                )
            )
        )
        active_checks = active_result.scalar()

        paused_result = await self.db.execute(
            select(func.count()).where(
                and_(
                    SyntheticCheck.organization_id == organization_id,
                    SyntheticCheck.status == "paused"
                )
            )
        )
        paused_checks = paused_result.scalar()

        # Current status counts
        up_result = await self.db.execute(
            select(func.count()).where(
                and_(
                    SyntheticCheck.organization_id == organization_id,
                    SyntheticCheck.current_status == "up"
                )
            )
        )
        checks_up = up_result.scalar()

        down_result = await self.db.execute(
            select(func.count()).where(
                and_(
                    SyntheticCheck.organization_id == organization_id,
                    SyntheticCheck.current_status == "down"
                )
            )
        )
        checks_down = down_result.scalar()

        degraded_result = await self.db.execute(
            select(func.count()).where(
                and_(
                    SyntheticCheck.organization_id == organization_id,
                    SyntheticCheck.current_status == "degraded"
                )
            )
        )
        checks_degraded = degraded_result.scalar()

        # Executions in last 24h
        day_ago = datetime.utcnow() - timedelta(days=1)

        total_exec_result = await self.db.execute(
            select(func.count()).where(
                and_(
                    SyntheticCheckResult.organization_id == organization_id,
                    SyntheticCheckResult.executed_at >= day_ago
                )
            )
        )
        total_executions_24h = total_exec_result.scalar()

        success_exec_result = await self.db.execute(
            select(func.count()).where(
                and_(
                    SyntheticCheckResult.organization_id == organization_id,
                    SyntheticCheckResult.executed_at >= day_ago,
                    SyntheticCheckResult.status == "success"
                )
            )
        )
        successful_executions_24h = success_exec_result.scalar()

        failed_executions_24h = total_executions_24h - successful_executions_24h

        # Average response time
        avg_result = await self.db.execute(
            select(func.avg(SyntheticCheckResult.response_time_ms)).where(
                and_(
                    SyntheticCheckResult.organization_id == organization_id,
                    SyntheticCheckResult.executed_at >= day_ago,
                    SyntheticCheckResult.response_time_ms.isnot(None)
                )
            )
        )
        avg_response_time = avg_result.scalar() or 0

        # Uptime calculation
        avg_uptime = (successful_executions_24h / total_executions_24h * 100) if total_executions_24h > 0 else 100

        # Open incidents
        open_incidents_result = await self.db.execute(
            select(func.count()).where(
                and_(
                    SyntheticCheckIncident.organization_id == organization_id,
                    SyntheticCheckIncident.status == "open"
                )
            )
        )
        open_incidents = open_incidents_result.scalar()

        return SyntheticStats(
            total_checks=total_checks,
            active_checks=active_checks,
            paused_checks=paused_checks,
            checks_up=checks_up,
            checks_down=checks_down,
            checks_degraded=checks_degraded,
            total_executions_24h=total_executions_24h,
            successful_executions_24h=successful_executions_24h,
            failed_executions_24h=failed_executions_24h,
            avg_uptime_24h=avg_uptime,
            avg_response_time_24h=float(avg_response_time),
            open_incidents=open_incidents,
            checks_by_type={},
            checks_by_location={}
        )
