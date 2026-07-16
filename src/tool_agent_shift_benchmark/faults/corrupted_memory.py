from __future__ import annotations

from random import Random

from tool_agent_shift_benchmark.core.memory import MEMORY_CORRUPTION_TYPES, POLICY_MEMORY_CONTRACT

from .base import BaseFault


class CorruptedMemoryFault(BaseFault):
    name = "corrupted_memory"
    version = "3.0.0"
    capabilities = (*BaseFault.capabilities, POLICY_MEMORY_CONTRACT)
    channel = "policy_memory"
    mechanism = "stateful_memory_read_corruption"

    def apply(self, response, env, rng: Random):
        """Record direct-call provenance without mutating a tool observation.

        Episode execution applies this fault to the policy-memory channel. The
        response API remains callable for plugin compatibility, but it can no
        longer manufacture a fake memory hint in observation metadata.
        """

        claim_count = 0 if self.severity == 0.0 else min(5, max(1, round(self.severity * 5)))
        effect = self._effect(
            "memory_corruption",
            claim_count / len(MEMORY_CORRUPTION_TYPES),
            {
                "corruption_amount": claim_count,
                "maximum_corruptions": len(MEMORY_CORRUPTION_TYPES),
                "channel": self.channel,
                "mechanism": self.mechanism,
                "policy_observation_unchanged": True,
            },
        )
        return self._record_only(response, effect)
