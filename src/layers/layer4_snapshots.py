"""Layer 4: Snapshot Store - Before-State Capture for Rollback.

Captures before-state of every action:
- Files: Store file contents
- Database: Store affected rows
- Shell: Store directory listing and file hashes

Snapshots enable surgical rollback in Layer 5.
Metadata in PostgreSQL, actual content in S3/local filesystem.
"""

import hashlib
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any

from src.database import get_db_session, Snapshot
from src.schemas import ActionContext, ActionType


class SnapshotStore:
    """Capture and manage before-state snapshots for rollback."""

    def __init__(self, content_storage_path: str = "snapshots/content"):
        """Initialize snapshot store.

        Args:
            content_storage_path: Local filesystem path for storing content.
        """
        self.content_storage_path = content_storage_path
        Path(content_storage_path).mkdir(parents=True, exist_ok=True)

    def capture_file_snapshot(
        self, context: ActionContext, file_path: str
    ) -> Optional[str]:
        """Capture snapshot of a file before modification.

        Args:
            context: Action context.
            file_path: Path to file.

        Returns:
            Snapshot ID if successful, None otherwise.
        """
        try:
            # Check if file exists
            if not os.path.exists(file_path):
                return self._create_snapshot_record(
                    context,
                    "file",
                    file_path,
                    {"status": "not_found", "error": "File does not exist"},
                    None,
                )

            # Read file content
            with open(file_path, "rb") as f:
                content = f.read()

            # Store content
            content_key = self._store_content(context.action_id, content)
            content_hash = hashlib.sha256(content).hexdigest()
            size_bytes = len(content)

            # Create snapshot record
            before_state = {
                "path": file_path,
                "size": size_bytes,
                "readable": True,
                "modification_time": datetime.fromtimestamp(
                    os.path.getmtime(file_path)
                ).isoformat(),
            }

            return self._create_snapshot_record(
                context,
                "file",
                file_path,
                before_state,
                content_key,
                content_hash,
                size_bytes,
            )

        except Exception as e:
            print(f"Failed to capture file snapshot: {e}")
            return None

    def capture_database_snapshot(
        self, context: ActionContext, query: str, affected_rows: Optional[list] = None
    ) -> Optional[str]:
        """Capture snapshot of database rows before modification.

        Args:
            context: Action context.
            query: Original SQL query.
            affected_rows: Rows affected by the operation (for rollback).

        Returns:
            Snapshot ID if successful, None otherwise.
        """
        try:
            # Store affected rows as content
            content = json.dumps({
                "query": query,
                "affected_rows": affected_rows or [],
                "capture_time": datetime.utcnow().isoformat(),
            }).encode()

            content_key = self._store_content(context.action_id, content)
            content_hash = hashlib.sha256(content).hexdigest()

            before_state = {
                "database": context.target_resource,
                "query": query,
                "row_count": len(affected_rows) if affected_rows else 0,
            }

            return self._create_snapshot_record(
                context,
                "database",
                context.target_resource,
                before_state,
                content_key,
                content_hash,
                len(content),
            )

        except Exception as e:
            print(f"Failed to capture database snapshot: {e}")
            return None

    def capture_directory_snapshot(
        self, context: ActionContext, directory_path: str
    ) -> Optional[str]:
        """Capture snapshot of directory structure and file hashes.

        Args:
            context: Action context.
            directory_path: Path to directory.

        Returns:
            Snapshot ID if successful, None otherwise.
        """
        try:
            # Create directory snapshot with file listing and hashes
            dir_snapshot = {
                "path": directory_path,
                "files": {},
                "capture_time": datetime.utcnow().isoformat(),
            }

            if os.path.isdir(directory_path):
                for root, dirs, files in os.walk(directory_path):
                    for filename in files[:100]:  # Limit to first 100 files
                        file_path = os.path.join(root, filename)
                        try:
                            with open(file_path, "rb") as f:
                                file_hash = hashlib.sha256(f.read()).hexdigest()
                            dir_snapshot["files"][file_path] = {
                                "hash": file_hash,
                                "size": os.path.getsize(file_path),
                            }
                        except Exception:
                            pass

            # Store snapshot
            content = json.dumps(dir_snapshot).encode()
            content_key = self._store_content(context.action_id, content)
            content_hash = hashlib.sha256(content).hexdigest()

            before_state = {
                "directory": directory_path,
                "file_count": len(dir_snapshot["files"]),
            }

            return self._create_snapshot_record(
                context,
                "directory",
                directory_path,
                before_state,
                content_key,
                content_hash,
                len(content),
            )

        except Exception as e:
            print(f"Failed to capture directory snapshot: {e}")
            return None

    def _store_content(self, action_id: str, content: bytes) -> str:
        """Store snapshot content to filesystem.

        Args:
            action_id: Action ID.
            content: Content bytes.

        Returns:
            Content key (path).
        """
        # Create content key based on action_id
        content_key = f"{action_id}.snapshot"
        content_path = os.path.join(self.content_storage_path, content_key)

        # Write content to disk
        with open(content_path, "wb") as f:
            f.write(content)

        return content_key

    def _create_snapshot_record(
        self,
        context: ActionContext,
        snapshot_type: str,
        target_resource: str,
        before_state: Dict[str, Any],
        content_key: Optional[str] = None,
        content_hash: Optional[str] = None,
        size_bytes: Optional[int] = None,
    ) -> Optional[str]:
        """Create snapshot record in database.

        Args:
            context: Action context.
            snapshot_type: Type of snapshot (file, database, directory).
            target_resource: Resource path.
            before_state: Before-state metadata.
            content_key: S3 key or local path for content.
            content_hash: SHA256 hash of content.
            size_bytes: Size in bytes.

        Returns:
            Snapshot ID if successful, None otherwise.
        """
        try:
            session = get_db_session()

            snapshot = Snapshot(
                action_id=context.action_id,
                agent_id=context.agent_id,
                action_type=context.action_type.value,
                target_resource=target_resource,
                snapshot_type=snapshot_type,
                before_state=before_state,
                content_key=content_key,
                content_hash=content_hash,
                size_bytes=size_bytes,
            )

            session.add(snapshot)
            session.commit()
            snapshot_id = snapshot.snapshot_id
            session.close()

            return snapshot_id

        except Exception as e:
            print(f"Failed to create snapshot record: {e}")
            return None

    def get_snapshot(self, snapshot_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve snapshot metadata and content.

        Args:
            snapshot_id: Snapshot ID.

        Returns:
            Snapshot data if found, None otherwise.
        """
        try:
            session = get_db_session()
            snapshot = session.query(Snapshot).filter_by(snapshot_id=snapshot_id).first()
            session.close()

            if not snapshot:
                return None

            # Load content if available
            content = None
            if snapshot.content_key:
                content_path = os.path.join(self.content_storage_path, snapshot.content_key)
                if os.path.exists(content_path):
                    with open(content_path, "rb") as f:
                        content = f.read()

            return {
                "metadata": snapshot.to_dict(),
                "content": content,
            }

        except Exception as e:
            print(f"Failed to get snapshot: {e}")
            return None

    def get_action_snapshots(self, action_id: str) -> list[Dict[str, Any]]:
        """Get all snapshots for an action.

        Args:
            action_id: Action ID.

        Returns:
            List of snapshots.
        """
        try:
            session = get_db_session()
            snapshots = session.query(Snapshot).filter_by(action_id=action_id).all()
            session.close()

            return [s.to_dict() for s in snapshots]

        except Exception as e:
            print(f"Failed to get action snapshots: {e}")
            return []

    def verify_snapshot_integrity(self, snapshot_id: str) -> bool:
        """Verify snapshot content integrity.

        Args:
            snapshot_id: Snapshot ID.

        Returns:
            True if valid, False otherwise.
        """
        try:
            session = get_db_session()
            snapshot = session.query(Snapshot).filter_by(snapshot_id=snapshot_id).first()
            session.close()

            if not snapshot or not snapshot.content_key:
                return False

            # Load and hash content
            content_path = os.path.join(self.content_storage_path, snapshot.content_key)
            if not os.path.exists(content_path):
                return False

            with open(content_path, "rb") as f:
                actual_hash = hashlib.sha256(f.read()).hexdigest()

            return actual_hash == snapshot.content_hash

        except Exception as e:
            print(f"Failed to verify snapshot: {e}")
            return False


# Global snapshot store
_snapshot_store: Optional[SnapshotStore] = None


def get_snapshot_store() -> SnapshotStore:
    """Get global snapshot store instance."""
    global _snapshot_store
    if _snapshot_store is None:
        _snapshot_store = SnapshotStore()
    return _snapshot_store
