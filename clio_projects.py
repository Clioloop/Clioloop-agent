"""Per-profile projects SQLite store with explicit session membership."""
from __future__ import annotations

import os
import secrets
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from clio_constants import get_clio_home
from clio_state import apply_wal_with_fallback

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS projects (
 id TEXT PRIMARY KEY, name TEXT NOT NULL, description TEXT,
 created_at REAL NOT NULL, archived INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS project_workspaces (
 id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
 path TEXT NOT NULL, repo_root TEXT, worktree_path TEXT, branch TEXT,
 is_primary INTEGER NOT NULL DEFAULT 0, metadata_json TEXT,
 UNIQUE(project_id, path)
);
CREATE TABLE IF NOT EXISTS project_sessions (
 session_id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
 moved_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_project_workspaces_project ON project_workspaces(project_id);
CREATE INDEX IF NOT EXISTS idx_project_sessions_project ON project_sessions(project_id);
"""


def projects_db_path() -> Path:
    return get_clio_home() / "projects.db"


class ProjectsDB:
    def __init__(self, db_path: Optional[Path] = None):
        self.path = Path(db_path or projects_db_path())
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.path))
        self.conn.row_factory = sqlite3.Row
        apply_wal_with_fallback(self.conn, db_label="projects.db")
        self.conn.execute("PRAGMA foreign_keys=ON")
        self.conn.executescript(SCHEMA_SQL)

    def close(self) -> None:
        self.conn.close()

    def create_project(self, name: str, *, description: Optional[str] = None) -> str:
        name = str(name).strip()
        if not name:
            raise ValueError("project name is required")
        pid = "p_" + secrets.token_hex(6)
        self.conn.execute("INSERT INTO projects VALUES (?, ?, ?, ?, 0)", (pid, name, description, time.time()))
        self.conn.commit()
        return pid

    def add_workspace(self, project_id: str, path: str, *, repo_root: Optional[str] = None,
                      worktree_path: Optional[str] = None, branch: Optional[str] = None,
                      primary: bool = False, metadata_json: Optional[str] = None) -> str:
        normalized = os.path.abspath(os.path.expanduser(path))
        wid = "w_" + secrets.token_hex(6)
        with self.conn:
            if primary:
                self.conn.execute("UPDATE project_workspaces SET is_primary=0 WHERE project_id=?", (project_id,))
            self.conn.execute(
                "INSERT INTO project_workspaces VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (wid, project_id, normalized, repo_root, worktree_path, branch, int(primary), metadata_json),
            )
        return wid

    def move_session(self, session_id: str, project_id: Optional[str]) -> None:
        """Move membership only; the session transcript/state DB is untouched."""
        with self.conn:
            if project_id is None:
                self.conn.execute("DELETE FROM project_sessions WHERE session_id=?", (session_id,))
            else:
                self.conn.execute(
                    "INSERT INTO project_sessions VALUES (?, ?, ?) ON CONFLICT(session_id) DO UPDATE SET project_id=excluded.project_id,moved_at=excluded.moved_at",
                    (session_id, project_id, time.time()),
                )

    def project_for_session(self, session_id: str, *, cwd: Optional[str] = None) -> Optional[str]:
        row = self.conn.execute("SELECT project_id FROM project_sessions WHERE session_id=?", (session_id,)).fetchone()
        if row:
            return row[0]
        if not cwd:
            return None
        needle = os.path.abspath(os.path.expanduser(cwd))
        best = None
        for row in self.conn.execute("SELECT project_id,path FROM project_workspaces"):
            try:
                if os.path.commonpath((needle, row["path"])) == row["path"] and (best is None or len(row["path"]) > best[0]):
                    best = (len(row["path"]), row["project_id"])
            except ValueError:
                pass
        return best[1] if best else None

    def list_projects(self, *, include_archived: bool = False) -> List[Dict[str, Any]]:
        where = "" if include_archived else " WHERE archived=0"
        projects = [dict(r) for r in self.conn.execute("SELECT * FROM projects" + where + " ORDER BY created_at")]
        for project in projects:
            project["workspaces"] = [dict(r) for r in self.conn.execute("SELECT * FROM project_workspaces WHERE project_id=? ORDER BY is_primary DESC,path", (project["id"],))]
            project["session_ids"] = [r[0] for r in self.conn.execute("SELECT session_id FROM project_sessions WHERE project_id=?", (project["id"],))]
        return projects
