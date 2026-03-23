#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import mimetypes
import os
import shlex
import subprocess
import threading
import time
import uuid
from dataclasses import dataclass, field
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse


ROOT_DIR = Path(__file__).resolve().parent.parent
CLIENTS_DIR = ROOT_DIR / "clients"
STATIC_DIR = ROOT_DIR / "ui" / "static"
CLIENT_SCRIPT = ROOT_DIR / "client"
APPS_DIR = ROOT_DIR / "apps"


def read_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def read_client_apps(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []

    apps: list[dict[str, str]] = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        apps.append(
            {
                "name": parts[0],
                "repo": parts[1] if len(parts) > 1 else "",
                "branch": parts[2] if len(parts) > 2 else "",
            }
        )
    return apps


def run_command(cmd: list[str], *, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)
    return subprocess.run(
        cmd,
        cwd=ROOT_DIR,
        env=merged_env,
        check=False,
        capture_output=True,
        text=True,
    )


def parse_compose_json_output(raw_output: str) -> list[dict[str, Any]]:
    raw_output = raw_output.strip()
    if not raw_output:
        return []

    try:
        decoded = json.loads(raw_output)
        if isinstance(decoded, list):
            return [item for item in decoded if isinstance(item, dict)]
        if isinstance(decoded, dict):
            return [decoded]
    except json.JSONDecodeError:
        pass

    parsed: list[dict[str, Any]] = []
    for line in raw_output.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(item, dict):
            parsed.append(item)
    return parsed


def compose_states(client_name: str, env: dict[str, str]) -> dict[str, Any]:
    compose_file = CLIENTS_DIR / client_name / "docker-compose.yml"
    env_file = CLIENTS_DIR / client_name / ".env"
    project = env.get("PROJECT", f"erpnext-{client_name}")
    cmd = [
        "docker",
        "compose",
        "-f",
        str(compose_file),
        "--env-file",
        str(env_file),
        "-p",
        project,
        "ps",
        "--format",
        "json",
    ]

    try:
        result = run_command(cmd)
    except FileNotFoundError:
        return {"status": "docker-missing", "services": []}

    if result.returncode != 0:
        error = result.stderr.strip()
        status = "docker-error"
        if "permission denied" in error.lower():
            status = "docker-permission"
        return {"status": status, "services": [], "error": error}

    services = [
        {
            "service": item.get("Service", ""),
            "state": item.get("State", "unknown"),
            "health": item.get("Health", ""),
        }
        for item in parse_compose_json_output(result.stdout)
    ]

    if not services:
        return {"status": "stopped", "services": []}

    states = {service["state"].lower() for service in services}
    if "running" in states and len(states) == 1:
        status = "running"
    elif "running" in states:
        status = "degraded"
    else:
        status = next(iter(states))

    return {"status": status, "services": services}


def get_repo_origin(repo_dir: Path) -> str:
    result = run_command(["git", "-C", str(repo_dir), "remote", "get-url", "origin"])
    return result.stdout.strip() if result.returncode == 0 else ""


def get_repo_branch(repo_dir: Path) -> str:
    result = run_command(["git", "-C", str(repo_dir), "rev-parse", "--abbrev-ref", "HEAD"])
    return result.stdout.strip() if result.returncode == 0 else ""


def list_modules() -> list[dict[str, str]]:
    modules: list[dict[str, str]] = []
    if not APPS_DIR.exists():
        return modules

    for module_dir in sorted(APPS_DIR.iterdir()):
        if not (module_dir / ".git").exists():
            continue
        modules.append(
            {
                "name": module_dir.name,
                "repo": get_repo_origin(module_dir),
                "branch": get_repo_branch(module_dir),
                "path": str(module_dir.relative_to(ROOT_DIR)),
            }
        )
    return modules


def list_clients() -> list[dict[str, Any]]:
    clients: list[dict[str, Any]] = []
    for env_file in sorted(CLIENTS_DIR.glob("*/.env")):
        client_dir = env_file.parent
        client_name = client_dir.name
        env = read_env_file(env_file)
        compose_info = compose_states(client_name, env)
        configured_apps = read_client_apps(client_dir / "apps")
        port = env.get("HTTP_PORT", "")
        site_name = env.get("SITE_NAME", "")
        clients.append(
            {
                "name": client_name,
                "branch": env.get("FRAPPE_BRANCH", ""),
                "port": port,
                "site_name": site_name,
                "project": env.get("PROJECT", ""),
                "admin_password": env.get("ADMIN_PASSWORD", ""),
                "db_root_password": env.get("DB_ROOT_PASSWORD", ""),
                "url": f"http://localhost:{port}" if port else "",
                "status": compose_info["status"],
                "services": compose_info["services"],
                "service_count": len(compose_info["services"]),
                "configured_apps": configured_apps,
                "configured_app_names": [app["name"] for app in configured_apps] or ["frappe", "erpnext"],
                "paths": {
                    "root": str(client_dir),
                    "apps": str(client_dir / "data" / "apps"),
                    "sites": str(client_dir / "data" / "sites"),
                },
            }
        )
    return clients


def dashboard_payload() -> dict[str, Any]:
    clients = list_clients()
    modules = list_modules()
    return {
        "clients": clients,
        "modules": modules,
        "stats": {
            "clients": len(clients),
            "running_clients": sum(1 for client in clients if client["status"] == "running"),
            "modules": len(modules),
        },
    }


def require(value: str, message: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        raise ValueError(message)
    return cleaned


def optional(value: Any) -> str:
    return str(value).strip()


def build_operation(payload: dict[str, Any]) -> tuple[list[str], dict[str, str]]:
    operation = optional(payload.get("operation"))
    env: dict[str, str] = {}

    if operation == "create_client":
        client_name = require(optional(payload.get("name")), "Client name is required.")
        branch = optional(payload.get("branch")) or "version-15"
        port = optional(payload.get("port"))
        site_name = optional(payload.get("site_name"))
        command = [str(CLIENT_SCRIPT), "create", client_name, branch]
        if port:
            command.append(port)
        if site_name:
            if not port:
                command.append("")
            command.append(site_name)
        return command, env

    if operation == "client_action":
        client_name = require(optional(payload.get("client")), "Client is required.")
        action = require(optional(payload.get("action")), "Action is required.")
        allowed = {"up", "down", "restart", "site-create", "host-map", "fix-perms", "app-list"}
        if action not in allowed:
            raise ValueError("Unsupported client action.")
        return [str(CLIENT_SCRIPT), action, client_name], env

    if operation == "delete_client":
        client_name = require(optional(payload.get("client")), "Client is required.")
        env["CLIENT_NON_INTERACTIVE"] = "1"
        return [str(CLIENT_SCRIPT), "delete", client_name], env

    if operation == "restore_client":
        client_name = require(optional(payload.get("client")), "Client is required.")
        backup_path = require(optional(payload.get("backup_path")), "Backup path is required.")
        site_name = optional(payload.get("site_name"))
        command = [str(CLIENT_SCRIPT), "restore", client_name, backup_path]
        if site_name:
            command.append(site_name)
        return command, env

    if operation == "bench_update":
        client_name = require(optional(payload.get("client")), "Client is required.")
        extra_args = shlex.split(optional(payload.get("args")))
        return [str(CLIENT_SCRIPT), "bench-update", client_name, *extra_args], env

    if operation == "bench_update_all":
        extra_args = shlex.split(optional(payload.get("args")))
        return [str(CLIENT_SCRIPT), "bench-update-all", *extra_args], env

    if operation == "app_set":
        client_name = require(optional(payload.get("client")), "Client is required.")
        app_name = require(optional(payload.get("app_name")), "App name is required.")
        repo_url = require(optional(payload.get("repo_url")), "Repo URL is required.")
        branch = optional(payload.get("branch"))
        command = [str(CLIENT_SCRIPT), "app-set", client_name, app_name, repo_url]
        if branch:
            command.append(branch)
        return command, env

    if operation == "app_rm":
        client_name = require(optional(payload.get("client")), "Client is required.")
        app_name = require(optional(payload.get("app_name")), "App name is required.")
        return [str(CLIENT_SCRIPT), "app-rm", client_name, app_name], env

    if operation == "app_get":
        client_name = require(optional(payload.get("client")), "Client is required.")
        repo_url = require(optional(payload.get("repo_url")), "Repo URL is required.")
        branch = optional(payload.get("branch"))
        command = [str(CLIENT_SCRIPT), "app-get", client_name, repo_url]
        if branch:
            command.append(branch)
        return command, env

    if operation == "app_install":
        client_name = require(optional(payload.get("client")), "Client is required.")
        app_name = require(optional(payload.get("app_name")), "App name is required.")
        return [str(CLIENT_SCRIPT), "app-install", client_name, app_name], env

    if operation == "app_get_install":
        client_name = require(optional(payload.get("client")), "Client is required.")
        repo_url = require(optional(payload.get("repo_url")), "Repo URL is required.")
        branch = optional(payload.get("branch"))
        app_name = optional(payload.get("app_name"))
        command = [str(CLIENT_SCRIPT), "app-get-install", client_name, repo_url]
        if branch:
            command.append(branch)
        elif app_name:
            command.append("")
        if app_name:
            command.append(app_name)
        return command, env

    if operation == "module_add":
        repo_url = require(optional(payload.get("repo_url")), "Repo URL is required.")
        module_name = optional(payload.get("module_name"))
        branch = optional(payload.get("branch"))
        command = [str(CLIENT_SCRIPT), "module-add", repo_url]
        if module_name:
            command.append(module_name)
        if branch:
            if not module_name:
                command.append("")
            command.append(branch)
        return command, env

    if operation == "module_sync":
        return [str(CLIENT_SCRIPT), "module-sync"], env

    if operation == "module_list":
        return [str(CLIENT_SCRIPT), "module-list"], env

    raise ValueError("Unsupported operation.")


def read_client_logs(client_name: str, service: str = "", tail: int = 200) -> dict[str, Any]:
    env = read_env_file(CLIENTS_DIR / client_name / ".env")
    compose_file = CLIENTS_DIR / client_name / "docker-compose.yml"
    env_file = CLIENTS_DIR / client_name / ".env"
    project = env.get("PROJECT", f"erpnext-{client_name}")
    cmd = [
        "docker",
        "compose",
        "-f",
        str(compose_file),
        "--env-file",
        str(env_file),
        "-p",
        project,
        "logs",
        "--tail",
        str(tail),
    ]
    if service:
        cmd.append(service)

    try:
        result = run_command(cmd)
    except FileNotFoundError:
        return {"status": "docker-missing", "output": ""}

    status = "ok" if result.returncode == 0 else "error"
    return {
        "status": status,
        "output": (result.stdout or result.stderr).strip(),
        "service": service,
        "tail": tail,
    }


@dataclass
class Job:
    id: str
    command: list[str]
    env: dict[str, str]
    created_at: float
    status: str = "queued"
    output: str = ""
    returncode: int | None = None
    finished_at: float | None = None
    lock: threading.Lock = field(default_factory=threading.Lock)

    def append(self, chunk: str) -> None:
        if not chunk:
            return
        with self.lock:
            self.output += chunk
            if len(self.output) > 80000:
                self.output = self.output[-80000:]

    def snapshot(self) -> dict[str, Any]:
        with self.lock:
            return {
                "id": self.id,
                "command": " ".join(shlex.quote(part) for part in self.command),
                "created_at": self.created_at,
                "status": self.status,
                "output": self.output,
                "returncode": self.returncode,
                "finished_at": self.finished_at,
            }


class JobStore:
    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()

    def create(self, command: list[str], env: dict[str, str] | None = None) -> Job:
        job = Job(
            id=uuid.uuid4().hex[:10],
            command=command,
            env=env or {},
            created_at=time.time(),
        )
        with self._lock:
            self._jobs[job.id] = job
        thread = threading.Thread(target=self._run, args=(job,), daemon=True)
        thread.start()
        return job

    def get(self, job_id: str) -> Job | None:
        with self._lock:
            return self._jobs.get(job_id)

    def _run(self, job: Job) -> None:
        with job.lock:
            job.status = "running"

        process_env = os.environ.copy()
        process_env.update(job.env)

        try:
            process = subprocess.Popen(
                job.command,
                cwd=ROOT_DIR,
                env=process_env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
        except OSError as exc:
            with job.lock:
                job.output = str(exc)
                job.returncode = 1
                job.finished_at = time.time()
                job.status = "failed"
            return

        assert process.stdout is not None
        for line in process.stdout:
            job.append(line)

        process.wait()
        with job.lock:
            job.returncode = process.returncode
            job.finished_at = time.time()
            job.status = "succeeded" if process.returncode == 0 else "failed"


JOB_STORE = JobStore()


class DashboardHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, directory=str(STATIC_DIR), **kwargs)

    def log_message(self, fmt: str, *args: Any) -> None:
        return

    def do_GET(self) -> None:
        parsed = urlparse(self.path)

        if parsed.path in {"/api/dashboard", "/api/clients"}:
            self._send_json(dashboard_payload())
            return

        if parsed.path.startswith("/api/jobs/"):
            job_id = parsed.path.split("/")[-1]
            job = JOB_STORE.get(job_id)
            if job is None:
                self.send_error(HTTPStatus.NOT_FOUND, "Job not found")
                return
            self._send_json({"job": job.snapshot()})
            return

        if parsed.path.startswith("/api/clients/") and parsed.path.endswith("/logs"):
            parts = parsed.path.strip("/").split("/")
            if len(parts) != 4:
                self.send_error(HTTPStatus.NOT_FOUND, "Route not found")
                return
            client_name = parts[2]
            query = parse_qs(parsed.query)
            service = query.get("service", [""])[0]
            tail_raw = query.get("tail", ["200"])[0]
            try:
                tail = max(20, min(1000, int(tail_raw)))
            except ValueError:
                tail = 200
            self._send_json({"logs": read_client_logs(client_name, service, tail)})
            return

        if parsed.path in {"/", "/index.html"}:
            self.path = "/index.html"
        return super().do_GET()

    def do_POST(self) -> None:
        parsed = urlparse(self.path)

        if parsed.path == "/api/jobs":
            payload = self._read_json()
            try:
                command, env = build_operation(payload)
            except ValueError as exc:
                self._send_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
                return

            job = JOB_STORE.create(command, env)
            self._send_json({"job": job.snapshot()}, status=HTTPStatus.ACCEPTED)
            return

        self.send_error(HTTPStatus.NOT_FOUND, "Route not found")

    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def guess_type(self, path: str) -> str:
        if path.endswith(".js"):
            return "application/javascript"
        return mimetypes.guess_type(path)[0] or "application/octet-stream"

    def _read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length) if length else b"{}"
        try:
            return json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError:
            return {}

    def _send_json(self, payload: dict[str, Any], status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main() -> None:
    parser = argparse.ArgumentParser(description="ERPNext Docker dashboard")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=int(os.environ.get("ERP_UI_PORT", "8099")), type=int)
    args = parser.parse_args()

    server = ThreadingHTTPServer((args.host, args.port), DashboardHandler)
    print(f"Dashboard available on http://{args.host}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
