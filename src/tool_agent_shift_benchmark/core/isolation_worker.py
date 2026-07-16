"""Private worker for :mod:`tool_agent_shift_benchmark.core.isolation`.

This module is launched with ``python -I`` and communicates only through the
versioned JSON-lines protocol on its original stdin/stdout streams.
"""

from __future__ import annotations

import contextlib
import importlib
import json
import os
import socket
import sys
import traceback
from collections.abc import Mapping
from pathlib import Path
from typing import Any

try:
    import resource
except ImportError:  # pragma: no cover - exercised on non-POSIX platforms
    resource = None  # type: ignore[assignment]

from tool_agent_shift_benchmark.core.contracts import (
    BOUNDED_SUBPROCESS_ISOLATION_MODE,
    PluginDescriptor,
    validate_plugin_factory,
)
from tool_agent_shift_benchmark.core.isolation import (
    ISOLATION_MANIFEST_CONTRACT,
)
from tool_agent_shift_benchmark.core.isolation_protocol import (
    PLUGIN_RPC_CONTRACT,
    TYPE_KEY,
    decode_value,
    encode_value,
)
from tool_agent_shift_benchmark.core.policy_adapter import BasePolicyAdapter


class PluginWorkerOutputLimit(RuntimeError):
    pass


class RemoteCallableAttribute(AttributeError):
    pass


class BoundedCapture:
    def __init__(self, limit: int):
        self.limit = limit
        self.count = 0
        self.exceeded = False

    def write(self, value: str) -> int:
        encoded = value.encode("utf-8", "replace")
        self.count += len(encoded)
        if self.count > self.limit:
            self.exceeded = True
            raise PluginWorkerOutputLimit(f"plugin captured output exceeded {self.limit} bytes")
        return len(value)

    def flush(self) -> None:
        return None


class Worker:
    def __init__(self) -> None:
        self.protocol_stdin = sys.stdin
        self.protocol_stdout = sys.stdout
        self.instance: Any = None
        self.descriptor: PluginDescriptor | None = None
        self.settings: dict[str, Any] = {}
        self.handles: dict[int, Any] = {}
        self.next_handle = 1
        self.active_request_id = 0
        self.callback_id = 0

    def send(self, value: Mapping[str, Any]) -> None:
        self.protocol_stdout.write(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n")
        self.protocol_stdout.flush()

    def response(self, request_id: int, result: Any) -> None:
        self.send(
            {
                "protocol": PLUGIN_RPC_CONTRACT,
                "message_type": "response",
                "request_id": request_id,
                "ok": True,
                "result": encode_value(result, result_handles=self.register_handle),
            }
        )

    def error(self, request_id: int, exc: BaseException, *, phase: str) -> None:
        self.send(
            {
                "protocol": PLUGIN_RPC_CONTRACT,
                "message_type": "response",
                "request_id": request_id,
                "ok": False,
                "error": {
                    "error_type": type(exc).__name__,
                    "message": str(exc),
                    "phase": phase,
                },
            }
        )

    def register_handle(self, value: object) -> Mapping[str, Any]:
        handle_id = self.next_handle
        self.next_handle += 1
        self.handles[handle_id] = value
        payload: dict[str, Any] = {
            "handle_id": handle_id,
            "handle_type": "policy_adapter" if isinstance(value, BasePolicyAdapter) else type(value).__name__,
        }
        if isinstance(value, BasePolicyAdapter):
            payload["public"] = value.to_dict()
        return {TYPE_KEY: "RemoteHandle", "value": encode_value(payload)}

    def callback(self, method: str, args: tuple[Any, ...], kwargs: dict[str, Any]) -> Any:
        self.callback_id += 1
        callback_id = self.callback_id
        self.send(
            {
                "protocol": PLUGIN_RPC_CONTRACT,
                "message_type": "callback",
                "request_id": self.active_request_id,
                "callback_id": callback_id,
                "method": method,
                "args": encode_value(args),
                "kwargs": encode_value(kwargs),
            }
        )
        line = self.protocol_stdin.readline()
        if not line:
            raise RuntimeError("parent closed the plugin callback channel")
        value = json.loads(line)
        expected = {"protocol", "message_type", "request_id", "callback_id", "ok"}
        if (
            not isinstance(value, dict)
            or value.get("protocol") != PLUGIN_RPC_CONTRACT
            or value.get("message_type") != "callback_response"
            or value.get("request_id") != self.active_request_id
            or value.get("callback_id") != callback_id
        ):
            raise RuntimeError("parent returned a malformed plugin callback response")
        if value.get("ok") is True and set(value) == expected | {"result"}:
            return decode_value(value["result"])
        if value.get("ok") is False and set(value) == expected | {"error"}:
            error = value["error"]
            raise RuntimeError(f"visible-context callback failed: {error.get('error_type')}: {error.get('message')}")
        raise RuntimeError("parent returned a malformed plugin callback result")

    @staticmethod
    def _resolve(identifier: str) -> Any:
        module_name, separator, qualname = identifier.partition(":")
        if not separator or not module_name or not qualname or "<locals>" in qualname.split("."):
            raise ImportError("plugin implementation identifier is not importable")
        value: Any = importlib.import_module(module_name)
        for component in qualname.split("."):
            value = getattr(value, component)
        return value

    @staticmethod
    def _path_within(path: str, roots: tuple[str, ...]) -> bool:
        try:
            resolved = os.path.realpath(path)
        except (OSError, TypeError, ValueError):
            return False
        return any(resolved == root or resolved.startswith(root + os.sep) for root in roots)

    @classmethod
    def _install_guards(cls, *, workspace: str, import_root: str | None) -> dict[str, Any]:
        package_root = str(Path(__file__).resolve().parents[2])
        read_roots = tuple(
            dict.fromkeys(
                os.path.realpath(path)
                for path in (sys.base_prefix, sys.prefix, package_root, import_root, workspace)
                if path
            )
        )
        write_roots = (os.path.realpath(workspace),)

        def audit(event: str, args: tuple[Any, ...]) -> None:
            if event.startswith("socket."):
                raise PermissionError("plugin network access denied by bounded subprocess policy")
            if event in {"subprocess.Popen", "os.system"} or event.startswith(("os.exec", "os.spawn", "pty.spawn")):
                raise PermissionError("plugin process creation denied by bounded subprocess policy")
            if event == "open" and args:
                path = args[0]
                if isinstance(path, int):
                    return
                mode = args[1] if len(args) > 1 else "r"
                writing = False
                if isinstance(mode, str):
                    writing = any(flag in mode for flag in "wax+")
                elif isinstance(mode, int):
                    writing = bool(mode & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND))
                roots = write_roots if writing else read_roots
                if not cls._path_within(os.fspath(path), roots):
                    raise PermissionError("plugin filesystem access denied by bounded subprocess policy")
            guarded_path_events = {
                "os.listdir",
                "os.scandir",
                "os.chdir",
                "os.remove",
                "os.rename",
                "os.mkdir",
                "os.rmdir",
            }
            if event in guarded_path_events and args:
                paths = args[:2] if event == "os.rename" else args[:1]
                for path in paths:
                    if isinstance(path, (str, bytes, os.PathLike)) and not cls._path_within(
                        os.fsdecode(path),
                        write_roots if event not in {"os.listdir", "os.scandir"} else read_roots,
                    ):
                        raise PermissionError("plugin filesystem access denied by bounded subprocess policy")

        sys.addaudithook(audit)

        def deny_network(*args: Any, **kwargs: Any) -> Any:
            raise PermissionError("plugin network access denied by bounded subprocess policy")

        socket.socket = deny_network  # type: ignore[assignment]
        socket.create_connection = deny_network  # type: ignore[assignment]
        socket.socketpair = deny_network  # type: ignore[assignment]
        return {
            "network_policy": "python_audit_deny_best_effort",
            "filesystem_policy": "distribution_and_runtime_read_workspace_write_best_effort",
            "read_roots": list(read_roots),
            "write_root": workspace,
        }

    @staticmethod
    def _set_limit(name: str, soft: int, applied: dict[str, Any], unavailable: list[str]) -> None:
        if resource is None:
            unavailable.append(name)
            return
        resource_name = getattr(resource, name, None)
        if resource_name is None:
            unavailable.append(name)
            return
        try:
            _, hard = resource.getrlimit(resource_name)
            selected = soft if hard == resource.RLIM_INFINITY else min(soft, int(hard))
            resource.setrlimit(resource_name, (selected, selected))
            applied[name] = selected
        except (OSError, ValueError):
            unavailable.append(name)

    @classmethod
    def _apply_resource_limits(cls, settings: Mapping[str, Any]) -> dict[str, Any]:
        applied: dict[str, Any] = {}
        unavailable: list[str] = []
        cls._set_limit("RLIMIT_CPU", int(settings["cpu_limit_seconds"]), applied, unavailable)
        cls._set_limit("RLIMIT_AS", int(settings["memory_limit_mb"]) * 1024 * 1024, applied, unavailable)
        cls._set_limit("RLIMIT_FSIZE", int(settings["file_size_limit_bytes"]), applied, unavailable)
        cls._set_limit("RLIMIT_NOFILE", int(settings["open_files_limit"]), applied, unavailable)
        cls._set_limit("RLIMIT_NPROC", int(settings["process_limit"]), applied, unavailable)
        return {"applied": applied, "unavailable": sorted(unavailable)}

    def start(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        expected = {
            "descriptor",
            "implementation_identifier",
            "import_root",
            "args",
            "kwargs",
            "workspace",
            "settings",
        }
        if set(payload) != expected:
            raise ValueError("plugin startup payload fields do not match the protocol")
        descriptor = PluginDescriptor.from_mapping(payload["descriptor"])
        if descriptor.isolation_mode != BOUNDED_SUBPROCESS_ISOLATION_MODE:
            raise ValueError("plugin descriptor does not select bounded_subprocess_v1")
        if payload["implementation_identifier"] != descriptor.implementation_identifier:
            raise ValueError("plugin startup implementation identifier mismatch")
        workspace = os.path.realpath(str(payload["workspace"]))
        if workspace != os.path.realpath(os.getcwd()):
            raise ValueError("plugin worker controlled cwd mismatch")
        import_root = payload["import_root"]
        if import_root:
            root = os.path.realpath(str(import_root))
            if root not in sys.path:
                sys.path.insert(0, root)
        self.settings = dict(payload["settings"])
        resources = self._apply_resource_limits(self.settings)
        guards = self._install_guards(workspace=workspace, import_root=str(import_root) if import_root else None)
        capture = BoundedCapture(int(self.settings["output_limit_bytes"]))
        with contextlib.redirect_stdout(capture), contextlib.redirect_stderr(capture):
            factory = self._resolve(descriptor.implementation_identifier)
            validate_plugin_factory(descriptor, factory)
            args = decode_value(payload["args"], callback=self.callback)
            kwargs = decode_value(payload["kwargs"], callback=self.callback)
            if not isinstance(args, tuple) or not isinstance(kwargs, dict):
                raise ValueError("plugin constructor arguments are malformed")
            self.instance = factory(*args, **kwargs)
        if capture.exceeded:
            raise PluginWorkerOutputLimit("plugin exceeded output limit during startup")
        self.descriptor = descriptor
        self.handles[0] = self.instance
        return {
            "contract": ISOLATION_MANIFEST_CONTRACT,
            "mode": BOUNDED_SUBPROCESS_ISOLATION_MODE,
            "pid": os.getpid(),
            "cwd_policy": "private_temporary_directory",
            "environment_policy": "allowlist_without_parent_credentials",
            "network_policy": guards["network_policy"],
            "filesystem_policy": guards["filesystem_policy"],
            "resource_limits": resources,
            "timeouts": {
                "startup_seconds": self.settings["startup_timeout_seconds"],
                "call_seconds": self.settings["call_timeout_seconds"],
            },
            "output_limit_bytes": self.settings["output_limit_bytes"],
        }

    def _target_method(self, method: str) -> tuple[Any, str]:
        if method.startswith("@"):
            identifier, separator, name = method[1:].partition(":")
            if not separator or not identifier.isdigit() or int(identifier) not in self.handles:
                raise AttributeError("unknown isolated object handle")
            return self.handles[int(identifier)], name
        return self.instance, method

    def call(self, payload: Mapping[str, Any]) -> Any:
        if set(payload) != {"method", "args", "kwargs"}:
            raise ValueError("plugin call payload fields do not match the protocol")
        target, method = self._target_method(str(payload["method"]))
        callable_value = getattr(target, method)
        if not callable(callable_value):
            raise TypeError(f"plugin attribute {method!r} is not callable")
        args = decode_value(payload["args"], callback=self.callback)
        kwargs = decode_value(payload["kwargs"], callback=self.callback)
        if not isinstance(args, tuple) or not isinstance(kwargs, dict):
            raise ValueError("plugin call arguments are malformed")
        capture = BoundedCapture(int(self.settings["output_limit_bytes"]))
        with contextlib.redirect_stdout(capture), contextlib.redirect_stderr(capture):
            result = callable_value(*args, **kwargs)
        if capture.exceeded:
            raise PluginWorkerOutputLimit("plugin exceeded output limit during call")
        return result

    def get_attribute(self, payload: Mapping[str, Any]) -> Any:
        if set(payload) != {"handle_id", "name"}:
            raise ValueError("plugin attribute payload fields do not match the protocol")
        target = self.handles[int(payload["handle_id"])]
        value = getattr(target, str(payload["name"]))
        if callable(value):
            raise RemoteCallableAttribute("attribute is callable")
        return value

    def set_attribute(self, payload: Mapping[str, Any]) -> None:
        if set(payload) != {"handle_id", "name", "value"}:
            raise ValueError("plugin attribute payload fields do not match the protocol")
        target = self.handles[int(payload["handle_id"])]
        setattr(target, str(payload["name"]), decode_value(payload["value"], callback=self.callback))

    def run(self) -> int:
        for line in self.protocol_stdin:
            request_id = 0
            try:
                request = json.loads(line)
                if not isinstance(request, dict):
                    raise ValueError("plugin request must be an object")
                if set(request) != {"protocol", "message_type", "request_id", "operation", "payload"}:
                    raise ValueError("plugin request fields do not match the protocol")
                if request["protocol"] != PLUGIN_RPC_CONTRACT or request["message_type"] != "request":
                    raise ValueError("unknown plugin request protocol")
                request_id = int(request["request_id"])
                self.active_request_id = request_id
                operation = request["operation"]
                payload = request["payload"]
                if operation == "close":
                    return 0
                if operation == "start":
                    result = self.start(payload)
                elif self.instance is None:
                    raise RuntimeError("plugin subprocess was not initialized")
                elif operation == "call":
                    result = self.call(payload)
                elif operation == "get_attribute":
                    result = self.get_attribute(payload)
                elif operation == "set_attribute":
                    result = self.set_attribute(payload)
                else:
                    raise ValueError(f"unknown plugin operation: {operation!r}")
                self.response(request_id, result)
            except BaseException as exc:
                # SystemExit is converted to a structured plugin failure; hard
                # exits and signals remain observable as process crashes.
                try:
                    self.error(request_id, exc, phase="plugin_startup" if self.instance is None else "plugin_execution")
                except BaseException:
                    traceback.print_exc(file=self.protocol_stdout)
                    self.protocol_stdout.flush()
                    return 2
        return 0


def main() -> int:
    return Worker().run()


if __name__ == "__main__":
    raise SystemExit(main())
