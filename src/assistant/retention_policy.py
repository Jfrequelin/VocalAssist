"""
Data retention policy management module.
Handles data lifecycle, expiration, archival, and cleanup.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Optional
import logging

logger = logging.getLogger(__name__)


class RetentionLevel(Enum):
    """Data retention levels."""
    
    IMMEDIATE = "immediate"      # 1 day
    SHORT_TERM = "short_term"    # 7 days
    MEDIUM_TERM = "medium_term"  # 30 days
    LONG_TERM = "long_term"      # 365 days

    def get_days(self) -> int:
        """Get retention days for this level."""
        mapping = {
            "immediate": 1,
            "short_term": 7,
            "medium_term": 30,
            "long_term": 365,
        }
        return mapping.get(self.value, 30)


@dataclass
class RetentionPolicy:
    """Configuration for data retention."""
    
    level: RetentionLevel = RetentionLevel.MEDIUM_TERM
    archivable: bool = False
    exportable: bool = True
    description: str = ""

    def days_until_expiry(self, created_at: datetime) -> int:
        """Calculate days until data expires.
        
        Args:
            created_at: When the data was created.
            
        Returns:
            Number of days until expiry.
        """
        expiry = created_at + timedelta(days=self.level.get_days())
        days_left = (expiry - datetime.now()).days
        return max(0, days_left)

    def is_expired(self, created_at: datetime) -> bool:
        """Check if data has expired.
        
        Args:
            created_at: When the data was created.
            
        Returns:
            True if expired, False otherwise.
        """
        expiry = created_at + timedelta(days=self.level.get_days())
        return datetime.now() > expiry


@dataclass
class RetentionInfo:
    """Information about retained data."""
    
    id: str
    data_type: str
    created_at: datetime
    archived: bool = False
    archived_at: Optional[datetime] = None
    retention_policy: dict[str, Any] = field(default_factory=lambda: {})


class DataRetentionManager:
    """Manages data retention, archival, and cleanup."""
    
    def __init__(self) -> None:
        """Initialize the retention manager."""
        self.data_registry: dict[str, RetentionInfo] = {}
        self.type_policies: dict[str, RetentionPolicy] = {}
        self._init_default_policies()

    def _init_default_policies(self) -> None:
        """Initialize default retention policies for data types."""
        self.type_policies["reminders"] = RetentionPolicy(
            level=RetentionLevel.LONG_TERM,
            archivable=True
        )
        self.type_policies["notes"] = RetentionPolicy(
            level=RetentionLevel.MEDIUM_TERM,
            archivable=True
        )
        self.type_policies["calendar_events"] = RetentionPolicy(
            level=RetentionLevel.LONG_TERM,
            archivable=True
        )
        self.type_policies["logs"] = RetentionPolicy(
            level=RetentionLevel.SHORT_TERM,
            archivable=False
        )
        self.type_policies["sessions"] = RetentionPolicy(
            level=RetentionLevel.IMMEDIATE,
            archivable=False
        )

    def register_data(
        self,
        data_type: str,
        policy: Optional[RetentionPolicy] = None,
    ) -> str:
        """Register data with a retention policy.
        
        Args:
            data_type: Type of data being retained.
            policy: Retention policy (uses default if not provided).
            
        Returns:
            Data ID for tracking.
        """
        if policy is None:
            policy = self.type_policies.get(data_type, RetentionPolicy())
        
        data_id = str(uuid.uuid4())
        info = RetentionInfo(
            id=data_id,
            data_type=data_type,
            created_at=datetime.now(),
            retention_policy={
                "level": policy.level.value,
                "archivable": policy.archivable,
                "exportable": policy.exportable,
            }
        )
        
        self.data_registry[data_id] = info
        return data_id

    def get_retention_info(self, data_id: str) -> Optional[dict[str, Any]]:
        """Get retention information for data.
        
        Args:
            data_id: The data ID.
            
        Returns:
            Retention info dict or None if not found.
        """
        info = self.data_registry.get(data_id)
        if not info:
            return None
        
        return {
            "id": info.id,
            "data_type": info.data_type,
            "created_at": info.created_at,
            "archived": info.archived,
            "archived_at": info.archived_at,
            "retention_policy": info.retention_policy,
        }

    def set_policy_for_type(self, data_type: str, policy: RetentionPolicy) -> None:
        """Set retention policy for a data type.
        
        Args:
            data_type: Type of data.
            policy: Retention policy.
        """
        self.type_policies[data_type] = policy

    def get_policy_for_type(self, data_type: str) -> Optional[RetentionPolicy]:
        """Get retention policy for a data type.
        
        Args:
            data_type: Type of data.
            
        Returns:
            RetentionPolicy or None if not found.
        """
        return self.type_policies.get(data_type)

    def find_expired_data(self) -> list[dict[str, Any]]:
        """Find all expired data.
        
        Returns:
            List of expired data info dicts.
        """
        expired: list[dict[str, Any]] = []
        
        for data_id, info in self.data_registry.items():
            policy = self._get_policy_for_info(info)
            if policy.is_expired(info.created_at):
                data_info = self.get_retention_info(data_id)
                if data_info is not None:
                    expired.append(data_info)
        
        return expired

    def mark_for_archival(self, data_id: str) -> bool:
        """Mark data for archival.
        
        Args:
            data_id: The data ID.
            
        Returns:
            True if marked, False if archiving not supported.
        """
        info = self.data_registry.get(data_id)
        if not info:
            return False
        
        policy = self._get_policy_for_info(info)
        if not policy.archivable:
            return False
        
        info.archived = True
        info.archived_at = datetime.now()
        return True

    def delete_data(self, data_id: str) -> bool:
        """Delete data from registry.
        
        Args:
            data_id: The data ID.
            
        Returns:
            True if deleted, False if not found.
        """
        if data_id in self.data_registry:
            del self.data_registry[data_id]
            return True
        return False

    def cleanup_expired_data(self) -> list[dict[str, Any]]:
        """Clean up expired data by deletion.
        
        Returns:
            List of deleted data info.
        """
        expired = self.find_expired_data()
        deleted: list[dict[str, Any]] = []
        
        for data_info in expired:
            self.delete_data(data_info["id"])
            deleted.append(data_info)
        
        logger.info(f"Cleaned up {len(deleted)} expired data items")
        return deleted

    def cleanup_with_archival(self) -> dict[str, list[dict[str, Any]]]:
        """Clean up expired data, archiving what can be archived.
        
        Returns:
            Dictionary with 'archived' and 'deleted' lists.
        """
        expired = self.find_expired_data()
        archived: list[dict[str, Any]] = []
        deleted: list[dict[str, Any]] = []
        
        for data_info in expired:
            data_id = data_info["id"]
            if self.mark_for_archival(data_id):
                archived.append(data_info)
            else:
                self.delete_data(data_id)
                deleted.append(data_info)
        
        logger.info(f"Cleaned up: {len(archived)} archived, {len(deleted)} deleted")
        return {
            "archived": archived,
            "deleted": deleted,
        }

    def export_data(self, data_id: str) -> Optional[dict[str, Any]]:
        """Export data before deletion.
        
        Args:
            data_id: The data ID.
            
        Returns:
            Exported data dict or None if not exportable.
        """
        info = self.data_registry.get(data_id)
        if not info:
            return None
        
        policy = self._get_policy_for_info(info)
        if not policy.exportable:
            return None
        
        return self.get_retention_info(data_id)

    def get_retention_stats(self) -> dict[str, Any]:
        """Get retention statistics.
        
        Returns:
            Dictionary with retention stats.
        """
        total = len(self.data_registry)
        archived = sum(1 for i in self.data_registry.values() if i.archived)
        
        by_level: dict[str, int] = {}
        for info in self.data_registry.values():
            level = info.retention_policy.get("level", "unknown")
            by_level[level] = by_level.get(level, 0) + 1
        
        by_type: dict[str, int] = {}
        for info in self.data_registry.values():
            by_type[info.data_type] = by_type.get(info.data_type, 0) + 1
        
        return {
            "total_items": total,
            "archived_count": archived,
            "by_retention_level": by_level,
            "by_data_type": by_type,
        }

    def _get_policy_for_info(self, info: RetentionInfo) -> RetentionPolicy:
        """Get retention policy for info.
        
        Args:
            info: RetentionInfo object.
            
        Returns:
            RetentionPolicy.
        """
        # Always use the policy stored with the data
        return RetentionPolicy(
            level=RetentionLevel(info.retention_policy.get("level", "medium_term")),
            archivable=info.retention_policy.get("archivable", False),
            exportable=info.retention_policy.get("exportable", True),
        )
