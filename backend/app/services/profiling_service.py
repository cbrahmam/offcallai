# backend/app/services/profiling_service.py
"""Service for Continuous Profiling."""

import base64
import gzip
import hashlib
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Any, Tuple
from uuid import UUID
from collections import defaultdict

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_, desc
from sqlalchemy.dialects.postgresql import insert

from app.models.profile import Profile, ProfileAggregate, ProfileType, ProfileFormat
from app.schemas.profile import (
    ProfileUpload,
    ProfileUploadResponse,
    ProfileSummary,
    ProfileDetail,
    FlamegraphNode,
    FlamegraphData,
    ProfileDiff,
    FunctionDiff,
    ProfileStats,
    ServiceProfilingOverview,
)


class ProfilingService:
    """Service for continuous profiling operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def upload_profile(
        self,
        profile: ProfileUpload,
        organization_id: UUID,
    ) -> ProfileUploadResponse:
        """
        Upload and store a profile.

        Args:
            profile: Profile data to upload
            organization_id: Organization ID

        Returns:
            Upload response with profile ID
        """
        # Decode and compress profile data
        try:
            profile_bytes = base64.b64decode(profile.profile_data)
        except Exception as e:
            raise ValueError(f"Invalid base64 profile data: {e}")

        # Compress with gzip
        compressed_data = gzip.compress(profile_bytes)

        # Parse profile to extract metadata
        sample_count = None
        top_functions = None
        total_samples = None
        total_cpu_ns = None
        total_alloc_bytes = None

        if profile.format == ProfileFormat.PPROF:
            metadata = self._parse_pprof_metadata(profile_bytes, profile.profile_type)
            sample_count = metadata.get("sample_count")
            top_functions = metadata.get("top_functions")
            total_samples = metadata.get("total_samples")
            total_cpu_ns = metadata.get("total_cpu_ns")
            total_alloc_bytes = metadata.get("total_alloc_bytes")
        elif profile.format == ProfileFormat.COLLAPSED:
            metadata = self._parse_collapsed_metadata(profile_bytes)
            sample_count = metadata.get("sample_count")
            top_functions = metadata.get("top_functions")
            total_samples = metadata.get("total_samples")

        # Create profile record
        db_profile = Profile(
            organization_id=organization_id,
            host_id=UUID(profile.host_id) if profile.host_id else None,
            service_name=profile.service_name,
            profile_type=profile.profile_type.value,
            format=profile.format.value,
            start_time=profile.start_time,
            end_time=profile.end_time,
            duration_seconds=profile.duration_seconds,
            profile_data=compressed_data,
            profile_size_bytes=len(compressed_data),
            sample_count=sample_count,
            trace_id=profile.trace_id,
            span_id=profile.span_id,
            environment=profile.environment,
            runtime=profile.runtime,
            runtime_version=profile.runtime_version,
            tags=profile.tags,
            labels=profile.labels,
            total_samples=total_samples,
            total_cpu_ns=total_cpu_ns,
            total_alloc_bytes=total_alloc_bytes,
            top_functions=top_functions,
        )

        self.db.add(db_profile)
        await self.db.commit()
        await self.db.refresh(db_profile)

        # Update hourly aggregates asynchronously
        await self._update_aggregates(db_profile)

        return ProfileUploadResponse(
            id=db_profile.id,
            service_name=db_profile.service_name,
            profile_type=db_profile.profile_type,
            profile_size_bytes=db_profile.profile_size_bytes,
            sample_count=db_profile.sample_count,
            created_at=db_profile.created_at,
        )

    def _parse_pprof_metadata(self, data: bytes, profile_type: str) -> Dict[str, Any]:
        """Parse pprof data to extract metadata."""
        # In a real implementation, we'd use the pprof protobuf format
        # For now, return placeholder metadata
        return {
            "sample_count": len(data) // 100,  # Rough estimate
            "total_samples": len(data) // 100,
            "top_functions": [
                {"name": "main.main", "samples": 100, "percent": 15.0},
                {"name": "runtime.gcBgMarkWorker", "samples": 80, "percent": 12.0},
                {"name": "net/http.(*conn).serve", "samples": 60, "percent": 9.0},
            ],
        }

    def _parse_collapsed_metadata(self, data: bytes) -> Dict[str, Any]:
        """Parse collapsed stack format to extract metadata."""
        try:
            lines = data.decode("utf-8").strip().split("\n")
            total_samples = 0
            function_counts = defaultdict(int)

            for line in lines:
                if " " in line:
                    stack, count_str = line.rsplit(" ", 1)
                    try:
                        count = int(count_str)
                        total_samples += count

                        # Count leaf function
                        functions = stack.split(";")
                        if functions:
                            function_counts[functions[-1]] += count
                    except ValueError:
                        continue

            # Get top functions
            sorted_funcs = sorted(function_counts.items(), key=lambda x: x[1], reverse=True)
            top_functions = [
                {
                    "name": name,
                    "samples": count,
                    "percent": (count / total_samples * 100) if total_samples > 0 else 0,
                }
                for name, count in sorted_funcs[:10]
            ]

            return {
                "sample_count": len(lines),
                "total_samples": total_samples,
                "top_functions": top_functions,
            }
        except Exception:
            return {"sample_count": 0, "total_samples": 0, "top_functions": []}

    async def _update_aggregates(self, profile: Profile):
        """Update hourly aggregates for the profile."""
        # Determine bucket boundaries (hourly)
        bucket_start = profile.start_time.replace(minute=0, second=0, microsecond=0)
        bucket_end = bucket_start + timedelta(hours=1)

        # Upsert aggregate
        stmt = insert(ProfileAggregate).values(
            organization_id=profile.organization_id,
            service_name=profile.service_name,
            profile_type=profile.profile_type,
            environment=profile.environment,
            bucket_start=bucket_start,
            bucket_end=bucket_end,
            profile_count=1,
            total_samples=profile.total_samples or 0,
            avg_duration_seconds=profile.duration_seconds or 0,
        ).on_conflict_do_update(
            constraint="uq_profile_aggregate_bucket",
            set_={
                "profile_count": ProfileAggregate.profile_count + 1,
                "total_samples": ProfileAggregate.total_samples + (profile.total_samples or 0),
            },
        )

        await self.db.execute(stmt)
        await self.db.commit()

    async def list_profiles(
        self,
        organization_id: UUID,
        service_name: Optional[str] = None,
        profile_type: Optional[str] = None,
        environment: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[ProfileSummary], int]:
        """List profiles with filtering."""
        query = select(Profile).where(Profile.organization_id == organization_id)

        if service_name:
            query = query.where(Profile.service_name == service_name)
        if profile_type:
            query = query.where(Profile.profile_type == profile_type)
        if environment:
            query = query.where(Profile.environment == environment)
        if start_time:
            query = query.where(Profile.start_time >= start_time)
        if end_time:
            query = query.where(Profile.start_time <= end_time)

        # Count total
        count_query = select(func.count()).select_from(query.subquery())
        total = await self.db.scalar(count_query) or 0

        # Get profiles
        query = query.order_by(desc(Profile.start_time)).offset(offset).limit(limit)
        result = await self.db.execute(query)
        profiles = result.scalars().all()

        summaries = [
            ProfileSummary(
                id=p.id,
                service_name=p.service_name,
                profile_type=p.profile_type,
                format=p.format,
                start_time=p.start_time,
                end_time=p.end_time,
                duration_seconds=p.duration_seconds,
                profile_size_bytes=p.profile_size_bytes,
                sample_count=p.sample_count,
                environment=p.environment,
                runtime=p.runtime,
                trace_id=p.trace_id,
                top_functions=p.top_functions,
                created_at=p.created_at,
            )
            for p in profiles
        ]

        return summaries, total

    async def get_profile(
        self,
        profile_id: UUID,
        organization_id: UUID,
        include_data: bool = False,
    ) -> Optional[ProfileDetail]:
        """Get a single profile."""
        query = select(Profile).where(
            Profile.id == profile_id,
            Profile.organization_id == organization_id,
        )
        result = await self.db.execute(query)
        profile = result.scalar_one_or_none()

        if not profile:
            return None

        detail = ProfileDetail(
            id=profile.id,
            service_name=profile.service_name,
            profile_type=profile.profile_type,
            format=profile.format,
            start_time=profile.start_time,
            end_time=profile.end_time,
            duration_seconds=profile.duration_seconds,
            profile_size_bytes=profile.profile_size_bytes,
            sample_count=profile.sample_count,
            environment=profile.environment,
            runtime=profile.runtime,
            trace_id=profile.trace_id,
            top_functions=profile.top_functions,
            created_at=profile.created_at,
            host_id=profile.host_id,
            runtime_version=profile.runtime_version,
            span_id=profile.span_id,
            tags=profile.tags,
            labels=profile.labels,
            total_samples=profile.total_samples,
            total_cpu_ns=profile.total_cpu_ns,
            total_alloc_bytes=profile.total_alloc_bytes,
        )

        return detail

    async def get_flamegraph_data(
        self,
        profile_id: UUID,
        organization_id: UUID,
    ) -> Optional[FlamegraphData]:
        """
        Convert profile to flamegraph format.

        Args:
            profile_id: Profile ID
            organization_id: Organization ID

        Returns:
            Flamegraph data for visualization
        """
        query = select(Profile).where(
            Profile.id == profile_id,
            Profile.organization_id == organization_id,
        )
        result = await self.db.execute(query)
        profile = result.scalar_one_or_none()

        if not profile or not profile.profile_data:
            return None

        # Decompress profile data
        try:
            profile_bytes = gzip.decompress(profile.profile_data)
        except:
            profile_bytes = profile.profile_data

        # Parse to flamegraph format
        if profile.format == ProfileFormat.PPROF.value:
            root = self._pprof_to_flamegraph(profile_bytes)
        elif profile.format == ProfileFormat.COLLAPSED.value:
            root = self._collapsed_to_flamegraph(profile_bytes)
        else:
            # Return empty root for unknown formats
            root = FlamegraphNode(name="root", value=0, children=[])

        # Determine unit based on profile type
        unit = "samples"
        if profile.profile_type == ProfileType.CPU.value:
            unit = "nanoseconds"
        elif profile.profile_type in [ProfileType.HEAP.value, ProfileType.ALLOCS.value]:
            unit = "bytes"

        return FlamegraphData(
            profile_id=profile.id,
            profile_type=profile.profile_type,
            service_name=profile.service_name,
            start_time=profile.start_time,
            duration_seconds=profile.duration_seconds,
            root=root,
            total_samples=profile.total_samples or 0,
            unit=unit,
        )

    def _collapsed_to_flamegraph(self, data: bytes) -> FlamegraphNode:
        """Convert collapsed stack format to flamegraph tree."""
        root = {"name": "root", "value": 0, "children": {}}

        try:
            lines = data.decode("utf-8").strip().split("\n")
            for line in lines:
                if " " not in line:
                    continue

                stack, count_str = line.rsplit(" ", 1)
                try:
                    count = int(count_str)
                except ValueError:
                    continue

                functions = stack.split(";")
                current = root

                for func in functions:
                    current["value"] += count
                    if func not in current["children"]:
                        current["children"][func] = {
                            "name": func,
                            "value": 0,
                            "children": {},
                        }
                    current = current["children"][func]

                current["value"] += count

        except Exception:
            pass

        def convert_to_node(node_dict: dict) -> FlamegraphNode:
            children = [convert_to_node(c) for c in node_dict["children"].values()]
            return FlamegraphNode(
                name=node_dict["name"],
                value=node_dict["value"],
                children=children,
            )

        return convert_to_node(root)

    def _pprof_to_flamegraph(self, data: bytes) -> FlamegraphNode:
        """Convert pprof format to flamegraph tree."""
        # In production, we'd parse the protobuf format
        # For now, return a placeholder
        return FlamegraphNode(
            name="root",
            value=1000,
            children=[
                FlamegraphNode(
                    name="main.main",
                    value=500,
                    children=[
                        FlamegraphNode(name="http.ListenAndServe", value=300, children=[]),
                        FlamegraphNode(name="database.Query", value=200, children=[]),
                    ],
                ),
                FlamegraphNode(
                    name="runtime.gcBgMarkWorker",
                    value=300,
                    children=[],
                ),
                FlamegraphNode(
                    name="runtime.schedule",
                    value=200,
                    children=[],
                ),
            ],
        )

    async def compare_profiles(
        self,
        base_profile_id: UUID,
        compare_profile_id: UUID,
        organization_id: UUID,
    ) -> Optional[ProfileDiff]:
        """Compare two profiles and return diff."""
        # Get both profiles
        query = select(Profile).where(
            Profile.id.in_([base_profile_id, compare_profile_id]),
            Profile.organization_id == organization_id,
        )
        result = await self.db.execute(query)
        profiles = {p.id: p for p in result.scalars().all()}

        if len(profiles) != 2:
            return None

        base = profiles.get(base_profile_id)
        compare = profiles.get(compare_profile_id)

        if not base or not compare:
            return None

        # Extract function data from top_functions
        base_funcs = {f["name"]: f["samples"] for f in (base.top_functions or [])}
        compare_funcs = {f["name"]: f["samples"] for f in (compare.top_functions or [])}

        all_funcs = set(base_funcs.keys()) | set(compare_funcs.keys())

        diffs = []
        for func_name in all_funcs:
            base_val = base_funcs.get(func_name, 0)
            compare_val = compare_funcs.get(func_name, 0)
            diff_val = compare_val - base_val
            diff_pct = (diff_val / base_val * 100) if base_val > 0 else (100 if compare_val > 0 else 0)

            diffs.append(FunctionDiff(
                name=func_name,
                base_value=base_val,
                compare_value=compare_val,
                diff=diff_val,
                diff_percent=diff_pct,
                file=None,
            ))

        # Sort by absolute diff
        diffs.sort(key=lambda x: abs(x.diff), reverse=True)

        top_increases = [d for d in diffs if d.diff > 0][:10]
        top_decreases = [d for d in diffs if d.diff < 0][:10]

        base_total = base.total_samples or sum(base_funcs.values())
        compare_total = compare.total_samples or sum(compare_funcs.values())
        total_diff = compare_total - base_total
        total_diff_pct = (total_diff / base_total * 100) if base_total > 0 else 0

        return ProfileDiff(
            base_profile_id=base_profile_id,
            compare_profile_id=compare_profile_id,
            profile_type=base.profile_type,
            base_total_samples=base_total,
            compare_total_samples=compare_total,
            total_diff=total_diff,
            total_diff_percent=total_diff_pct,
            top_increases=top_increases,
            top_decreases=top_decreases,
        )

    async def get_service_overview(
        self,
        service_name: str,
        organization_id: UUID,
    ) -> Optional[ServiceProfilingOverview]:
        """Get profiling overview for a service."""
        now = datetime.utcnow()
        day_ago = now - timedelta(days=1)
        week_ago = now - timedelta(days=7)

        # Get unique environments and profile types
        query = select(
            Profile.environment,
            Profile.profile_type,
        ).where(
            Profile.organization_id == organization_id,
            Profile.service_name == service_name,
            Profile.start_time >= week_ago,
        ).distinct()

        result = await self.db.execute(query)
        rows = result.all()

        environments = list(set(r[0] for r in rows if r[0]))
        profile_types = list(set(r[1] for r in rows if r[1]))

        if not environments and not profile_types:
            return None

        # Count recent profiles
        count_24h = await self.db.scalar(
            select(func.count()).where(
                Profile.organization_id == organization_id,
                Profile.service_name == service_name,
                Profile.start_time >= day_ago,
            )
        ) or 0

        count_7d = await self.db.scalar(
            select(func.count()).where(
                Profile.organization_id == organization_id,
                Profile.service_name == service_name,
                Profile.start_time >= week_ago,
            )
        ) or 0

        # Get last profile time
        last_profile = await self.db.scalar(
            select(func.max(Profile.start_time)).where(
                Profile.organization_id == organization_id,
                Profile.service_name == service_name,
            )
        )

        return ServiceProfilingOverview(
            service_name=service_name,
            environments=environments,
            profile_types=profile_types,
            last_profile_at=last_profile,
            profiles_last_24h=count_24h,
            profiles_last_7d=count_7d,
            cpu_trend_percent=None,
            memory_trend_percent=None,
            top_cpu_functions=None,
            top_memory_functions=None,
        )

    async def cleanup_old_profiles(
        self,
        organization_id: UUID,
        retention_days: int = 7,
    ) -> int:
        """Delete profiles older than retention period."""
        cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)

        query = select(Profile).where(
            Profile.organization_id == organization_id,
            Profile.start_time < cutoff,
        )
        result = await self.db.execute(query)
        profiles = result.scalars().all()

        deleted_count = len(profiles)

        for profile in profiles:
            await self.db.delete(profile)

        await self.db.commit()

        return deleted_count
