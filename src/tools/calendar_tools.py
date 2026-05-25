from __future__ import annotations
from src.core.types import Observation, ToolResponse
from .base import SyntheticTool


class CalendarAvailabilityTool(SyntheticTool):
    name = "calendar_availability"

    def __init__(self, env: object):
        self.env = env

    def call(self) -> ToolResponse:
        obs = Observation(
            env_name="calendar_ops",
            scenario_id=self.env.scenario_id,
            timestamp=self.env.current_time,
            data={"attendees": list(self.env.attendees), "availability": [dict(s) for s in self.env.visible_availability()]},
            constraints=dict(self.env.visible_constraints()),
        )
        return ToolResponse(tool_name=self.name, ok=True, observation=obs, metadata={"tool_call": "availability"})
