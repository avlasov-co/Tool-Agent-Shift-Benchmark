from __future__ import annotations
from src.core.types import Observation, ToolResponse
from .base import SyntheticTool


class SyntheticMarketTool(SyntheticTool):
    name = "synthetic_market_state"

    def __init__(self, env: object):
        self.env = env

    def call(self) -> ToolResponse:
        obs = Observation(
            env_name="risk_ops",
            scenario_id=self.env.scenario_id,
            timestamp=self.env.current_time,
            data={"market_state": dict(self.env.visible_market_state()), "exposure": self.env.exposure},
            constraints=dict(self.env.visible_constraints()),
        )
        return ToolResponse(tool_name=self.name, ok=True, observation=obs, metadata={"tool_call": "market_state"})
