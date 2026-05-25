from __future__ import annotations
from src.core.types import Observation, ToolResponse
from .base import SyntheticTool


class FileListingTool(SyntheticTool):
    name = "file_listing"

    def __init__(self, env: object):
        self.env = env

    def call(self) -> ToolResponse:
        obs = Observation(
            env_name="file_ops",
            scenario_id=self.env.scenario_id,
            timestamp=self.env.current_time,
            data={"files": [dict(f) for f in self.env.visible_files()]},
            constraints=dict(self.env.visible_constraints()),
        )
        return ToolResponse(tool_name=self.name, ok=True, observation=obs, metadata={"tool_call": "list_files"})
