from __future__ import annotations

from tool_agent_shift_benchmark.core.memory import MEMORY_CORRUPTION_TYPES, POLICY_MEMORY_CONTRACT

from .base import BaseFault


class CorruptedMemoryFault(BaseFault):
    name = "corrupted_memory"
    version = "4.0.0"
    capabilities = (*BaseFault.capabilities, POLICY_MEMORY_CONTRACT)
    channel = "policy_memory"
    mechanism = "stateful_memory_read_corruption"
    severity_semantics = "monotonic number of memory corruption families applied to one read"
    schedule_behavior = "corrupts only stateful policy-memory reads on active scheduled calls"
    detection_path = "validate memory source, confidence, timestamp, shape, and expected presence"
    adaptation_path = "overwrite, ignore, reobserve, or abstain without mutating the pristine reference"

    def apply(self, response, context):
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
