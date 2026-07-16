"""Importable adversarial plugins used by subprocess-isolation tests."""

from __future__ import annotations

import os

from tool_agent_shift_benchmark.agents.base import BaseAgent
from tool_agent_shift_benchmark.core.types import AgentAction, AgentDecision


def _abstain(name: str, metadata=None) -> AgentDecision:
    return AgentDecision(
        name,
        AgentAction("abstain", abstain=True, reason="isolated_fixture"),
        1.0,
        ("isolated_fixture",),
        metadata or {},
    )


class HonestIsolatedAgent(BaseAgent):
    name = "honest_isolated"
    version = "1.0.0"

    def decide(self, context, response):
        # Exercise the whitelisted visible adapter callback in addition to
        # ordinary typed request/response serialization.
        context.validate_observation_data(response.observation.data)
        action = context.abstain("honest_isolated")
        return AgentDecision(
            self.name,
            action,
            1.0,
            ("visible_callback_succeeded",),
            {"worker_pid": os.getpid()},
        )


class InfiniteLoopAgent(BaseAgent):
    name = "infinite_isolated"

    def decide(self, context, response):
        while True:
            pass


class StartupLoopAgent(BaseAgent):
    name = "startup_loop_isolated"

    def __init__(self):
        while True:
            pass

    def decide(self, context, response):
        return _abstain(self.name)


class ExcessiveOutputAgent(BaseAgent):
    name = "excessive_output_isolated"

    def decide(self, context, response):
        print("x" * 100_000)
        return _abstain(self.name)


class CrashAgent(BaseAgent):
    name = "crash_isolated"

    def decide(self, context, response):
        os._exit(73)


class MalformedProtocolAgent(BaseAgent):
    name = "malformed_protocol_isolated"

    def decide(self, context, response):
        os.write(1, b"not-json-from-plugin\n")
        return _abstain(self.name)


class FilesystemProbeAgent(BaseAgent):
    name = "filesystem_probe_isolated"

    def decide(self, context, response):
        denied = False
        try:
            with open("/etc/passwd", encoding="utf-8") as stream:
                stream.read(1)
        except PermissionError:
            denied = True
        private_write = os.path.join(os.getcwd(), "allowed.txt")
        with open(private_write, "w", encoding="utf-8") as stream:
            stream.write("allowed")
        return _abstain(
            self.name,
            {
                "outside_read_denied": denied,
                "private_write_succeeded": os.path.exists(private_write),
                "cwd": os.getcwd(),
            },
        )


class EnvironmentProbeAgent(BaseAgent):
    name = "environment_probe_isolated"

    def decide(self, context, response):
        return _abstain(
            self.name,
            {
                "parent_secret": os.environ.get("TASB_PARENT_SECRET"),
                "aws_key": os.environ.get("AWS_SECRET_ACCESS_KEY"),
                "home": os.environ.get("HOME"),
                "environment_keys": sorted(os.environ),
            },
        )


class NetworkProbeAgent(BaseAgent):
    name = "network_probe_isolated"

    def decide(self, context, response):
        import socket

        denied = False
        try:
            socket.socket()
        except PermissionError:
            denied = True
        return _abstain(self.name, {"network_denied": denied})
