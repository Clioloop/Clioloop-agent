"""Static, side-effect-free verification recipe detection.

The detector deliberately does not install dependencies or start applications.
It provides a serializable recipe that a later runner/UI can execute with the
runtime deadline and process-tree primitives.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Recipe:
    name: str
    kind: str
    bootstrap: tuple[str, ...] = field(default_factory=tuple)
    build: tuple[str, ...] = field(default_factory=tuple)
    test: tuple[str, ...] = field(default_factory=tuple)
    start: str | None = None
    port: int | None = None
    readiness_path: str = "/"
    evidence: tuple[str, ...] = field(default_factory=tuple)

    @property
    def verification_commands(self) -> tuple[str, ...]:
        return tuple(dict.fromkeys((*self.build, *self.test)))

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "kind": self.kind,
            "bootstrap": list(self.bootstrap),
            "build": list(self.build),
            "test": list(self.test),
            "start": self.start,
            "port": self.port,
            "readinessPath": self.readiness_path,
            "evidence": list(self.evidence),
        }

    @classmethod
    def from_dict(cls, raw: Any) -> "Recipe | None":
        if not isinstance(raw, dict):
            return None
        name = raw.get("name") or raw.get("appLabel")
        if not isinstance(name, str) or not name.strip():
            return None

        def strings(value: Any) -> tuple[str, ...]:
            if isinstance(value, str):
                return (value.strip(),) if value.strip() else ()
            if not isinstance(value, (list, tuple)):
                return ()
            return tuple(v.strip() for v in value if isinstance(v, str) and v.strip())

        port_raw = raw.get("port") or raw.get("startPort")
        try:
            port = int(port_raw) if port_raw is not None else None
        except (TypeError, ValueError):
            port = None
        if port is not None and not 0 < port < 65536:
            port = None
        readiness = raw.get("readinessPath") or raw.get("readiness_path") or "/"
        if not isinstance(readiness, str) or not readiness.startswith("/"):
            readiness = "/"
        start = raw.get("start") or raw.get("startCommand")
        if not isinstance(start, str) or not start.strip():
            start = None
        return cls(
            name=name.strip(),
            kind=str(raw.get("kind") or raw.get("appKind") or "unknown").strip(),
            bootstrap=strings(raw.get("bootstrap") or raw.get("installCommands")),
            build=strings(raw.get("build") or raw.get("buildCommands")),
            test=strings(raw.get("test") or raw.get("testCommands")),
            start=start.strip() if start else None,
            port=port,
            readiness_path=readiness,
            evidence=strings(raw.get("evidence")),
        )


def _read_text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return None


def detect_package_manager(root: Path) -> str | None:
    for filename, manager in (
        ("pnpm-lock.yaml", "pnpm"),
        ("bun.lock", "bun"),
        ("bun.lockb", "bun"),
        ("yarn.lock", "yarn"),
        ("package-lock.json", "npm"),
        ("uv.lock", "uv"),
        ("poetry.lock", "poetry"),
        ("Pipfile.lock", "pipenv"),
    ):
        if (root / filename).exists():
            return manager
    return None


def _script_command(manager: str | None, script: str) -> str:
    if manager == "pnpm":
        return f"pnpm {script}"
    if manager == "yarn":
        return f"yarn {script}"
    if manager == "bun":
        return f"bun run {script}"
    return f"npm run {script}"


def _port_from_command(command: str | None) -> int | None:
    if not command:
        return None
    match = re.search(r"(?:--port|-p)\s+(\d{2,5})|\bPORT=(\d{2,5})\b", command)
    if not match:
        return None
    port = int(match.group(1) or match.group(2))
    return port if 0 < port < 65536 else None


def _node_recipe(root: Path) -> Recipe | None:
    raw = _read_text(root / "package.json")
    if raw is None:
        return None
    try:
        package = json.loads(raw)
    except (ValueError, TypeError):
        return None
    if not isinstance(package, dict):
        return None
    scripts_raw = package.get("scripts")
    scripts: dict[str, Any] = scripts_raw if isinstance(scripts_raw, dict) else {}
    dependencies: dict[str, Any] = {}
    for key in ("dependencies", "devDependencies"):
        if isinstance(package.get(key), dict):
            dependencies.update(package[key])
    kind, name, default_port = "node", "Node.js project", None
    for dependency, values in (
        ("next", ("nextjs", "Next.js", 3000)),
        ("@sveltejs/kit", ("sveltekit", "SvelteKit", 5173)),
        ("astro", ("astro", "Astro", 4321)),
        ("vite", ("vite", "Vite", 5173)),
        ("react-scripts", ("cra", "Create React App", 3000)),
    ):
        if dependency in dependencies:
            kind, name, default_port = values
            break
    manager = detect_package_manager(root)
    install = {
        "pnpm": "pnpm install",
        "yarn": "yarn install",
        "bun": "bun install",
    }.get(manager or "npm", "npm install")
    start_name = "dev" if scripts.get("dev") else "start" if scripts.get("start") else None
    start = _script_command(manager, start_name) if start_name else None
    build = tuple(
        _script_command(manager, script)
        for script in ("build", "typecheck")
        if scripts.get(script)
    )
    tests = tuple(
        _script_command(manager, script)
        for script in ("test", "check", "lint")
        if scripts.get(script)
    )
    port = _port_from_command(scripts.get(start_name) if start_name else None)
    if port is None and start:
        port = default_port
    return Recipe(
        name=name,
        kind=kind,
        bootstrap=(install,),
        build=build,
        test=tests,
        start=start,
        port=port,
        evidence=("package.json", f"package manager: {manager or 'npm'}"),
    )


def _python_recipe(root: Path) -> Recipe | None:
    pyproject = _read_text(root / "pyproject.toml")
    requirements = _read_text(root / "requirements.txt")
    setup_exists = (root / "setup.py").exists()
    manage_exists = (root / "manage.py").exists()
    if not (pyproject is not None or requirements is not None or setup_exists or manage_exists):
        return None
    combined = f"{pyproject or ''}\n{requirements or ''}".lower()
    manager = detect_package_manager(root)
    if manager == "uv":
        install = "uv sync"
    elif manager == "poetry":
        install = "poetry install"
    elif manager == "pipenv":
        install = "pipenv install"
    elif requirements is not None:
        install = "pip install -r requirements.txt"
    else:
        install = "pip install -e ."
    has_tests = (root / "tests").exists()
    if manage_exists or "django" in combined:
        return Recipe(
            name="Django app",
            kind="django",
            bootstrap=(install,),
            test=("python manage.py test",),
            start="python manage.py runserver 0.0.0.0:8000",
            port=8000,
            evidence=("Python project", "Django"),
        )
    if "fastapi" in combined or "uvicorn" in combined:
        module = "app:app" if (root / "app.py").exists() else "main:app"
        return Recipe(
            name="FastAPI app",
            kind="fastapi",
            bootstrap=(install,),
            test=("pytest",) if has_tests else (),
            start=f"uvicorn {module} --host 0.0.0.0 --port 8000",
            port=8000,
            evidence=("Python project", "FastAPI/Uvicorn"),
        )
    if "flask" in combined:
        module = "main.py" if (root / "main.py").exists() else "app.py"
        return Recipe(
            name="Flask app",
            kind="flask",
            bootstrap=(install,),
            test=("pytest",) if has_tests else (),
            start=f"flask --app {module} run --host 0.0.0.0 --port 5000",
            port=5000,
            evidence=("Python project", "Flask"),
        )
    return Recipe(
        name="Python project",
        kind="python",
        bootstrap=(install,),
        test=("pytest",) if has_tests else ("python -m unittest discover",),
        evidence=("Python project",),
    )


_SHELL_CANDIDATES = (
    "verify.sh",
    "test.sh",
    "check.sh",
    "scripts/verify.sh",
    "scripts/test.sh",
    "scripts/check.sh",
)


def _shell_recipe(root: Path) -> Recipe | None:
    scripts = [name for name in _SHELL_CANDIDATES if (root / name).is_file()]
    if not scripts:
        return None
    commands = tuple(f"bash ./{name}" for name in scripts)
    return Recipe(
        name="Shell-verified project",
        kind="shell",
        test=commands,
        evidence=tuple(scripts),
    )


def detect_recipe(root: Path) -> Recipe | None:
    """Detect Node, Python, or conventional shell verification recipes."""
    root = Path(root)
    return _node_recipe(root) or _python_recipe(root) or _shell_recipe(root)


__all__ = ["Recipe", "detect_package_manager", "detect_recipe"]
