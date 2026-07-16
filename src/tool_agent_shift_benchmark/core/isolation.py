"""Parent-side bounded subprocess execution for restricted plugins."""

from __future__ import annotations

import atexit
import importlib.util
import json
import os
import selectors
import signal
import subprocess
import sys
import tempfile
import time
import weakref
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from tool_agent_shift_benchmark.core.context import ObservationContext
from tool_agent_shift_benchmark.core.contracts import BOUNDED_SUBPROCESS_ISOLATION_MODE, PluginDescriptor
from tool_agent_shift_benchmark.core.isolation_protocol import (
    PLUGIN_RPC_CONTRACT,
    ProtocolValueError,
    decode_value,
    encode_value,
)
from tool_agent_shift_benchmark.core.policy_adapter import BasePolicyAdapter

ISOLATION_MANIFEST_CONTRACT = "plugin-isolation-manifest-v1"

__all__ = [
    "BOUNDED_SUBPROCESS_ISOLATION_MODE",
    "ISOLATION_MANIFEST_CONTRACT",
    "IsolatedPluginFactory",
    "PluginIsolationError",
]


class PluginIsolationError(RuntimeError):
    """Base structured failure for a bounded plugin subprocess."""

    def __init__(self, message: str, *, phase: str, details: Mapping[str, Any] | None = None):
        self.phase = phase
        self.details = dict(details or {})
        super().__init__(message)

    def to_dict(self) -> dict[str, Any]:
        return {
            "error_type": type(self).__name__,
            "phase": self.phase,
            "message": str(self),
            "details": self.details,
        }


class PluginStartupTimeout(PluginIsolationError):
    pass


class PluginCallTimeout(PluginIsolationError):
    pass


class PluginOutputLimitError(PluginIsolationError):
    pass


class PluginProcessCrash(PluginIsolationError):
    pass


class PluginProtocolViolation(PluginIsolationError):
    pass


class PluginRemoteError(PluginIsolationError):
    pass


@dataclass(frozen=True)
class IsolationSettings:
    startup_timeout_seconds: float = 5.0
    call_timeout_seconds: float = 2.0
    output_limit_bytes: int = 1_000_000
    memory_limit_mb: int = 512
    cpu_limit_seconds: int = 10
    file_size_limit_bytes: int = 1_000_000
    open_files_limit: int = 64
    process_limit: int = 16

    @classmethod
    def from_descriptor(cls, descriptor: PluginDescriptor) -> "IsolationSettings":
        raw = descriptor.metadata.get("isolation", {})
        if not isinstance(raw, Mapping):
            raise ValueError("plugin descriptor isolation metadata must be a mapping")
        allowed = {
            "startup_timeout_seconds",
            "call_timeout_seconds",
            "output_limit_bytes",
            "memory_limit_mb",
            "cpu_limit_seconds",
            "file_size_limit_bytes",
            "open_files_limit",
            "process_limit",
        }
        unknown = sorted(set(raw) - allowed)
        if unknown:
            raise ValueError(f"unknown plugin isolation setting: {unknown[0]!r}")
        values = {field: raw.get(field, getattr(cls(), field)) for field in allowed}
        for field in ("startup_timeout_seconds", "call_timeout_seconds"):
            number = float(values[field])
            if not 0.05 <= number <= 60.0:
                raise ValueError(f"plugin isolation {field} must be in [0.05, 60]")
            values[field] = number
        bounds = {
            "output_limit_bytes": (1024, 16_000_000),
            "memory_limit_mb": (64, 4096),
            "cpu_limit_seconds": (1, 300),
            "file_size_limit_bytes": (1024, 16_000_000),
            "open_files_limit": (16, 1024),
            "process_limit": (1, 256),
        }
        for field, (minimum, maximum) in bounds.items():
            number = int(values[field])
            if isinstance(values[field], bool) or not minimum <= number <= maximum:
                raise ValueError(f"plugin isolation {field} must be in [{minimum}, {maximum}]")
            values[field] = number
        return cls(**values)

    def to_dict(self) -> dict[str, Any]:
        return {
            "startup_timeout_seconds": self.startup_timeout_seconds,
            "call_timeout_seconds": self.call_timeout_seconds,
            "output_limit_bytes": self.output_limit_bytes,
            "memory_limit_mb": self.memory_limit_mb,
            "cpu_limit_seconds": self.cpu_limit_seconds,
            "file_size_limit_bytes": self.file_size_limit_bytes,
            "open_files_limit": self.open_files_limit,
            "process_limit": self.process_limit,
        }


def _import_root(identifier: str) -> str | None:
    module_name = identifier.split(":", 1)[0]
    try:
        spec = importlib.util.find_spec(module_name)
    except (ImportError, AttributeError, ValueError):
        return None
    origin = getattr(spec, "origin", None)
    if not origin or origin in {"built-in", "frozen"}:
        return None
    path = Path(origin).resolve()
    for _ in module_name.split("."):
        path = path.parent
    return str(path)


def entry_point_import_root(entry_point: Any, identifier: str) -> str | None:
    explicit = getattr(entry_point, "import_root", None)
    if explicit:
        return str(Path(explicit).resolve())
    distribution = getattr(entry_point, "dist", None)
    locate_file = getattr(distribution, "locate_file", None)
    if callable(locate_file):
        try:
            return str(Path(locate_file("")).resolve())
        except (OSError, TypeError, ValueError):
            pass
    return _import_root(identifier)


def _sanitized_environment(workspace: str) -> dict[str, str]:
    return {
        "PATH": os.defpath,
        "HOME": workspace,
        "TMPDIR": workspace,
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "PYTHONHASHSEED": "0",
        "PYTHONIOENCODING": "utf-8",
        "PYTHONDONTWRITEBYTECODE": "1",
        "TASB_NETWORK_POLICY": "python_audit_deny_best_effort",
    }


_LIVE_CLIENTS: "weakref.WeakSet[IsolatedPluginClient]" = weakref.WeakSet()


def _close_live_clients() -> None:
    for client in tuple(_LIVE_CLIENTS):
        client.close()


atexit.register(_close_live_clients)


class IsolatedPluginClient:
    """One stateful plugin instance in a process group with deterministic teardown."""

    def __init__(
        self,
        descriptor: PluginDescriptor,
        args: tuple[Any, ...],
        kwargs: Mapping[str, Any],
        *,
        import_root: str | None,
    ) -> None:
        self.descriptor = descriptor
        self.settings = IsolationSettings.from_descriptor(descriptor)
        self._temporary_directory = tempfile.TemporaryDirectory(prefix="tasb-plugin-")
        self.workspace = self._temporary_directory.name
        self._request_id = 0
        self._stdout_buffer = b""
        self._stderr_tail = b""
        self._closed = False
        self._process = subprocess.Popen(
            [sys.executable, "-I", "-m", "tool_agent_shift_benchmark.core.isolation_worker"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=self.workspace,
            env=_sanitized_environment(self.workspace),
            start_new_session=True,
            bufsize=0,
        )
        _LIVE_CLIENTS.add(self)
        self._selector = selectors.DefaultSelector()
        assert self._process.stdout is not None and self._process.stderr is not None
        self._selector.register(self._process.stdout, selectors.EVENT_READ, "stdout")
        self._selector.register(self._process.stderr, selectors.EVENT_READ, "stderr")
        try:
            startup = self._exchange(
                "start",
                {
                    "descriptor": descriptor.to_dict(),
                    "implementation_identifier": descriptor.implementation_identifier,
                    "import_root": import_root,
                    "args": encode_value(args),
                    "kwargs": encode_value(dict(kwargs)),
                    "workspace": self.workspace,
                    "settings": self.settings.to_dict(),
                },
                timeout=self.settings.startup_timeout_seconds,
                startup=True,
                callback_context=None,
            )
        except ProtocolValueError as exc:
            self.close()
            raise PluginProtocolViolation(
                f"plugin constructor argument is outside the typed protocol: {exc}",
                phase="plugin_protocol_violation",
            ) from exc
        except Exception:
            self.close()
            raise
        if not isinstance(startup, Mapping):
            self.close()
            raise PluginProtocolViolation(
                "plugin startup response did not contain an isolation manifest",
                phase="plugin_protocol_violation",
            )
        self.isolation_manifest = dict(startup)

    @property
    def pid(self) -> int:
        return self._process.pid

    def _terminate(self) -> None:
        if self._process.poll() is not None:
            return
        try:
            if hasattr(os, "killpg"):
                os.killpg(self._process.pid, signal.SIGTERM)
            else:
                self._process.terminate()
            self._process.wait(timeout=0.25)
        except (ProcessLookupError, subprocess.TimeoutExpired):
            try:
                if hasattr(os, "killpg"):
                    os.killpg(self._process.pid, signal.SIGKILL)
                else:
                    self._process.kill()
            except ProcessLookupError:
                pass
            try:
                self._process.wait(timeout=1.0)
            except subprocess.TimeoutExpired:
                pass

    def close(self) -> None:
        if self._closed:
            return
        if self._process.poll() is None:
            try:
                self._send(
                    {
                        "protocol": PLUGIN_RPC_CONTRACT,
                        "message_type": "request",
                        "request_id": -1,
                        "operation": "close",
                        "payload": {},
                    }
                )
            except (BrokenPipeError, OSError, PluginIsolationError):
                pass
        self._closed = True
        self._terminate()
        try:
            self._selector.close()
        except Exception:
            pass
        self._temporary_directory.cleanup()

    def _send(self, message: Mapping[str, Any]) -> None:
        if self._closed or self._process.stdin is None:
            raise PluginProcessCrash("plugin subprocess is not available", phase="plugin_process_crash")
        data = json.dumps(message, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8") + b"\n"
        try:
            self._process.stdin.write(data)
            self._process.stdin.flush()
        except (BrokenPipeError, OSError) as exc:
            raise PluginProcessCrash(
                "plugin subprocess closed its request channel",
                phase="plugin_process_crash",
                details={"returncode": self._process.poll()},
            ) from exc

    def _read_message(self, *, deadline: float, startup: bool) -> dict[str, Any]:
        seen = 0
        while True:
            newline = self._stdout_buffer.find(b"\n")
            if newline >= 0:
                raw = self._stdout_buffer[:newline]
                self._stdout_buffer = self._stdout_buffer[newline + 1 :]
                try:
                    value = json.loads(raw)
                except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                    self._terminate()
                    raise PluginProtocolViolation(
                        "plugin subprocess emitted malformed protocol output",
                        phase="plugin_protocol_violation",
                        details={"output_prefix": raw[:160].decode("utf-8", "replace")},
                    ) from exc
                if not isinstance(value, dict):
                    self._terminate()
                    raise PluginProtocolViolation(
                        "plugin subprocess protocol message must be an object",
                        phase="plugin_protocol_violation",
                    )
                return value
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                self._terminate()
                error_type = PluginStartupTimeout if startup else PluginCallTimeout
                phase = "plugin_startup_timeout" if startup else "plugin_call_timeout"
                raise error_type(
                    f"plugin subprocess exceeded the {'startup' if startup else 'call'} timeout",
                    phase=phase,
                    details={
                        "timeout_seconds": (
                            self.settings.startup_timeout_seconds if startup else self.settings.call_timeout_seconds
                        )
                    },
                )
            events = self._selector.select(remaining)
            if not events:
                continue
            for key, _ in events:
                try:
                    chunk = os.read(key.fd, 65536)
                except OSError:
                    chunk = b""
                if not chunk:
                    try:
                        self._selector.unregister(key.fileobj)
                    except KeyError:
                        pass
                    continue
                seen += len(chunk)
                if seen > self.settings.output_limit_bytes:
                    self._terminate()
                    raise PluginOutputLimitError(
                        "plugin subprocess exceeded the output limit",
                        phase="plugin_output_limit",
                        details={"output_limit_bytes": self.settings.output_limit_bytes},
                    )
                if key.data == "stdout":
                    self._stdout_buffer += chunk
                else:
                    self._stderr_tail = (self._stderr_tail + chunk)[-4096:]
            if self._process.poll() is not None and not self._stdout_buffer:
                raise PluginProcessCrash(
                    "plugin subprocess exited before producing a response",
                    phase="plugin_process_crash",
                    details={
                        "returncode": self._process.returncode,
                        "stderr_tail": self._stderr_tail.decode("utf-8", "replace"),
                    },
                )

    @staticmethod
    def _context(args: tuple[Any, ...], kwargs: Mapping[str, Any]) -> ObservationContext | None:
        for value in (*args, *kwargs.values()):
            if isinstance(value, ObservationContext):
                return value
        return None

    def _handle_callback(
        self,
        message: Mapping[str, Any],
        *,
        request_id: int,
        context: ObservationContext | None,
    ) -> None:
        if set(message) != {"protocol", "message_type", "request_id", "callback_id", "method", "args", "kwargs"}:
            raise PluginProtocolViolation("malformed plugin callback message", phase="plugin_protocol_violation")
        if message["request_id"] != request_id or context is None:
            raise PluginProtocolViolation(
                "plugin callback has no matching visible context",
                phase="plugin_protocol_violation",
            )
        allowed = {
            "visible_candidates",
            "recommended_action",
            "validate_observation_data",
            "validate_action",
            "abstain",
        }
        method = str(message["method"])
        if method not in allowed:
            raise PluginProtocolViolation(
                f"plugin requested forbidden parent callback {method!r}",
                phase="plugin_protocol_violation",
            )
        try:
            args = decode_value(message["args"])
            kwargs = decode_value(message["kwargs"])
            if not isinstance(args, tuple) or not isinstance(kwargs, dict):
                raise ProtocolValueError("callback arguments are malformed")
            result = getattr(context, method)(*args, **kwargs)
            response = {"ok": True, "result": encode_value(result)}
        except Exception as exc:
            response = {"ok": False, "error": {"error_type": type(exc).__name__, "message": str(exc)}}
        self._send(
            {
                "protocol": PLUGIN_RPC_CONTRACT,
                "message_type": "callback_response",
                "request_id": request_id,
                "callback_id": message["callback_id"],
                **response,
            }
        )

    def _exchange(
        self,
        operation: str,
        payload: Mapping[str, Any],
        *,
        timeout: float,
        startup: bool,
        callback_context: ObservationContext | None,
    ) -> Any:
        self._request_id += 1
        request_id = self._request_id
        self._send(
            {
                "protocol": PLUGIN_RPC_CONTRACT,
                "message_type": "request",
                "request_id": request_id,
                "operation": operation,
                "payload": dict(payload),
            }
        )
        deadline = time.monotonic() + timeout
        while True:
            message = self._read_message(deadline=deadline, startup=startup)
            if message.get("protocol") != PLUGIN_RPC_CONTRACT:
                self._terminate()
                raise PluginProtocolViolation(
                    "plugin response uses an unknown protocol",
                    phase="plugin_protocol_violation",
                )
            if message.get("message_type") == "callback":
                self._handle_callback(message, request_id=request_id, context=callback_context)
                continue
            expected_keys = {"protocol", "message_type", "request_id", "ok"}
            if message.get("message_type") != "response" or message.get("request_id") != request_id:
                self._terminate()
                raise PluginProtocolViolation("plugin response identity mismatch", phase="plugin_protocol_violation")
            if message.get("ok") is True:
                if set(message) != expected_keys | {"result"}:
                    raise PluginProtocolViolation(
                        "malformed successful plugin response",
                        phase="plugin_protocol_violation",
                    )
                return decode_value(message["result"], remote_handle=self._remote_handle)
            if message.get("ok") is False:
                if set(message) != expected_keys | {"error"} or not isinstance(message["error"], Mapping):
                    raise PluginProtocolViolation("malformed failed plugin response", phase="plugin_protocol_violation")
                error = dict(message["error"])
                error_type = str(error.get("error_type", "PluginRemoteError"))
                details = {
                    "remote_error_type": error_type,
                    "remote_phase": str(error.get("phase", "plugin_execution")),
                }
                if error_type == "PluginWorkerOutputLimit":
                    self._terminate()
                    raise PluginOutputLimitError(
                        str(error.get("message", "plugin exceeded its captured output limit")),
                        phase="plugin_output_limit",
                        details={**details, "output_limit_bytes": self.settings.output_limit_bytes},
                    )
                raise PluginRemoteError(
                    str(error.get("message", "plugin subprocess returned an error")),
                    phase="plugin_remote_error",
                    details=details,
                )
            raise PluginProtocolViolation("plugin response ok field must be boolean", phase="plugin_protocol_violation")

    def _remote_handle(self, payload: Mapping[str, Any]) -> Any:
        if payload.get("handle_type") == "policy_adapter":
            return RemotePolicyAdapter(self, payload)
        return RemoteObject(self, int(payload["handle_id"]), str(payload.get("handle_type", "object")))

    def call(self, method: str, args: tuple[Any, ...], kwargs: Mapping[str, Any]) -> Any:
        if self._closed:
            raise PluginProcessCrash("plugin subprocess has already been closed", phase="plugin_process_crash")
        context = self._context(args, kwargs)
        try:
            encoded_args = encode_value(args)
            encoded_kwargs = encode_value(dict(kwargs))
        except ProtocolValueError as exc:
            raise PluginProtocolViolation(
                f"plugin call argument is outside the typed protocol: {exc}",
                phase="plugin_protocol_violation",
            ) from exc
        return self._exchange(
            "call",
            {"method": method, "args": encoded_args, "kwargs": encoded_kwargs},
            timeout=self.settings.call_timeout_seconds,
            startup=False,
            callback_context=context,
        )

    def get_attribute(self, name: str, *, handle_id: int = 0) -> Any:
        return self._exchange(
            "get_attribute",
            {"handle_id": handle_id, "name": name},
            timeout=self.settings.call_timeout_seconds,
            startup=False,
            callback_context=None,
        )

    def set_attribute(self, name: str, value: Any, *, handle_id: int = 0) -> None:
        try:
            encoded_value = encode_value(value)
        except ProtocolValueError as exc:
            raise PluginProtocolViolation(
                f"plugin attribute is outside the typed protocol: {exc}",
                phase="plugin_protocol_violation",
            ) from exc
        self._exchange(
            "set_attribute",
            {"handle_id": handle_id, "name": name, "value": encoded_value},
            timeout=self.settings.call_timeout_seconds,
            startup=False,
            callback_context=None,
        )


class RemoteObject:
    def __init__(self, client: IsolatedPluginClient, handle_id: int, handle_type: str):
        self._client = client
        self._handle_id = handle_id
        self._handle_type = handle_type

    def __getattr__(self, name: str) -> Any:
        if name.startswith("_"):
            raise AttributeError(name)

        def method(*args: Any, **kwargs: Any) -> Any:
            return self._client.call(f"@{self._handle_id}:{name}", args, kwargs)

        return method


class RemotePolicyAdapter(BasePolicyAdapter):
    def __init__(self, client: IsolatedPluginClient, payload: Mapping[str, Any]):
        public = payload["public"]
        super().__init__(
            environment_name=str(public["environment_name"]),
            required_fields=tuple(str(item) for item in public["required_fields"]),
            constraints=public["constraints"],
            task_metadata=public["task_metadata"],
            action_schema=public["action_schema"],
            capabilities=tuple(str(item) for item in public["capabilities"]),
        )
        object.__setattr__(self, "_client", client)
        object.__setattr__(self, "_handle_id", int(payload["handle_id"]))

    def _call(self, method: str, *args: Any) -> Any:
        return self._client.call(f"@{self._handle_id}:{method}", args, {})

    def visible_candidates(self, observation: Any) -> tuple[Mapping[str, Any], ...]:
        return tuple(self._call("visible_candidates", observation))

    def validate_observation_data(self, data: Mapping[str, Any]) -> tuple[str, ...]:
        return tuple(self._call("validate_observation_data", data))

    def validate_action(self, action: Any, observation: Any = None) -> tuple[bool, tuple[str, ...]]:
        allowed, reasons = self._call("validate_action", action, observation)
        return bool(allowed), tuple(reasons)

    def abstain(self, reason: str) -> Any:
        return self._call("abstain", reason)

    def recommend_action(self, data: Mapping[str, Any]) -> Any:
        return self._call("recommend_action", data)


class IsolatedPluginProxy:
    """Dynamic public-contract proxy for a single isolated instance."""

    _LOCAL_NAMES = {
        "_client",
        "_descriptor",
        "_tasb_isolated_proxy",
        "runtime_descriptor",
        "isolation_manifest",
        "close",
        "__dict__",
    }

    def __init__(self, client: IsolatedPluginClient, descriptor: PluginDescriptor):
        object.__setattr__(self, "_client", client)
        object.__setattr__(self, "_descriptor", descriptor)
        object.__setattr__(self, "_tasb_isolated_proxy", True)
        object.__setattr__(self, "name", descriptor.name)
        object.__setattr__(self, "version", descriptor.version)
        object.__setattr__(self, "capabilities", descriptor.capabilities)
        object.__setattr__(self, "configuration_schema", descriptor.configuration_schema)
        weakref.finalize(self, client.close)

    @property
    def runtime_descriptor(self) -> PluginDescriptor:
        return self._descriptor

    @property
    def isolation_manifest(self) -> Mapping[str, Any]:
        return self._client.isolation_manifest

    def close(self) -> None:
        self._client.close()

    def __getattr__(self, name: str) -> Any:
        if name.startswith("_"):
            raise AttributeError(name)
        try:
            return self._client.get_attribute(name)
        except PluginRemoteError as exc:
            remote_type = exc.details.get("remote_error_type")
            if remote_type == "AttributeError":
                raise AttributeError(name) from exc
            if remote_type != "RemoteCallableAttribute":
                raise

        def method(*args: Any, **kwargs: Any) -> Any:
            return self._client.call(name, args, kwargs)

        return method

    def __setattr__(self, name: str, value: Any) -> None:
        if name in self._LOCAL_NAMES or name in {"name", "version", "capabilities", "configuration_schema"}:
            object.__setattr__(self, name, value)
        else:
            self._client.set_attribute(name, value)


class IsolatedPluginFactory:
    """Non-importing factory bound to one statically validated descriptor."""

    _tasb_isolated_factory = True

    def __init__(self, descriptor: PluginDescriptor, *, import_root: str | None = None):
        self.descriptor = descriptor
        self.name = descriptor.name
        self.version = descriptor.version
        self.capabilities = descriptor.capabilities
        self.configuration_schema = descriptor.configuration_schema
        self.import_root = import_root

    def __call__(self, *args: Any, **kwargs: Any) -> IsolatedPluginProxy:
        client = IsolatedPluginClient(self.descriptor, args, kwargs, import_root=self.import_root)
        return IsolatedPluginProxy(client, self.descriptor)

    def channel_descriptor(self) -> Any:
        instance = self(severity=0.0)
        try:
            return instance.channel_descriptor()
        finally:
            instance.close()
