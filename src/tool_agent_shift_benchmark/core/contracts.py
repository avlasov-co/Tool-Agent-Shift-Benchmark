"""Public, versioned plugin contracts for the benchmark platform.

Contract v2 makes the complete runner-used surface and implementation identity
explicit. Descriptors are data: discovering or validating them must not import
plugin implementation code.
"""

from __future__ import annotations

import inspect
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, ClassVar, Mapping, Protocol, runtime_checkable

from tool_agent_shift_benchmark.core.context import ObservationContext
from tool_agent_shift_benchmark.core.immutability import deep_freeze, freeze_mapping
from tool_agent_shift_benchmark.core.serialization import (
    canonicalize,
    register_dataclass,
    register_enum,
    stable_hash,
)
from tool_agent_shift_benchmark.core.shift_context import ShiftContext
from tool_agent_shift_benchmark.core.types import (
    AgentAction,
    AgentDecision,
    ExecutionResult,
    MonitorDecision,
    Observation,
    ToolResponse,
)

CONTRACT_VERSION = "2"
PLUGIN_DESCRIPTOR_SCHEMA_VERSION = "plugin-descriptor-v2"
PLUGIN_CONFIGURATION_SCHEMA_VERSION = "plugin-configuration-schema-v1"
BOUNDED_SUBPROCESS_ISOLATION_MODE = "bounded_subprocess_v1"

PLUGIN_KINDS = frozenset({"agent", "environment", "shift", "monitor", "evaluator", "reporter"})
_IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._+:/<>-]*$")


class TrustLevel(str, Enum):
    BUILTIN_TRUSTED = "builtin_trusted"
    LOCAL_TRUSTED = "local_trusted"
    EXTERNAL_RESTRICTED = "external_restricted"
    UNTRUSTED_ISOLATED = "untrusted_isolated"


IN_PROCESS_TRUST_LEVELS = frozenset({TrustLevel.BUILTIN_TRUSTED, TrustLevel.LOCAL_TRUSTED})
ISOLATED_TRUST_LEVELS = frozenset({TrustLevel.EXTERNAL_RESTRICTED, TrustLevel.UNTRUSTED_ISOLATED})


def empty_configuration_schema() -> dict[str, Any]:
    return {
        "schema_version": PLUGIN_CONFIGURATION_SCHEMA_VERSION,
        "type": "object",
        "properties": {},
        "required": [],
        "additional_properties": False,
    }


def validate_configuration_schema(value: Mapping[str, Any]) -> dict[str, Any]:
    normalized = canonicalize(value, path="$.configuration_schema")
    if not isinstance(normalized, dict):
        raise ValueError("plugin configuration schema must be a mapping")
    allowed = {"schema_version", "type", "properties", "required", "additional_properties"}
    unknown = sorted(set(normalized) - allowed)
    if unknown:
        raise ValueError(f"plugin configuration schema has unknown key {unknown[0]!r}")
    if normalized.get("schema_version") != PLUGIN_CONFIGURATION_SCHEMA_VERSION:
        raise ValueError(f"plugin configuration schema_version must equal {PLUGIN_CONFIGURATION_SCHEMA_VERSION!r}")
    if normalized.get("type") != "object":
        raise ValueError("plugin configuration schema type must be 'object'")
    properties = normalized.get("properties")
    if not isinstance(properties, dict) or any(not isinstance(key, str) or not key for key in properties):
        raise ValueError("plugin configuration schema properties must be a string-keyed mapping")
    required = normalized.get("required")
    if not isinstance(required, list) or any(not isinstance(item, str) or not item for item in required):
        raise ValueError("plugin configuration schema required must be a list of non-empty strings")
    if len(required) != len(set(required)):
        raise ValueError("plugin configuration schema required entries must be unique")
    missing = sorted(set(required) - set(properties))
    if missing:
        raise ValueError(f"required plugin configuration property {missing[0]!r} is not declared")
    if not isinstance(normalized.get("additional_properties"), bool):
        raise ValueError("plugin configuration schema additional_properties must be boolean")
    return normalized


def implementation_identifier(factory: object) -> str:
    module = str(getattr(factory, "__module__", ""))
    qualname = str(getattr(factory, "__qualname__", getattr(factory, "__name__", "")))
    if not module or not qualname:
        raise ValueError("plugin factory must have an importable implementation identity")
    return f"{module}:{qualname}"


@dataclass(frozen=True)
class PluginDescriptor:
    schema_version: str
    kind: str
    name: str
    version: str
    contract_version: str
    implementation_identifier: str
    configuration_schema: Mapping[str, Any]
    configuration_hash: str
    trust_level: TrustLevel
    capabilities: tuple[str, ...] = ()
    isolation_mode: str = "in_process"
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.schema_version != PLUGIN_DESCRIPTOR_SCHEMA_VERSION:
            raise ValueError(f"unsupported plugin descriptor schema: {self.schema_version!r}")
        if self.kind not in PLUGIN_KINDS:
            raise ValueError(f"invalid plugin kind: {self.kind}")
        for label, value in (
            ("name", self.name),
            ("version", self.version),
            ("implementation_identifier", self.implementation_identifier),
            ("isolation_mode", self.isolation_mode),
        ):
            if not isinstance(value, str) or not _IDENTIFIER_RE.match(value):
                raise ValueError(f"plugin {label} must be a non-empty stable identifier")
        if self.contract_version != CONTRACT_VERSION:
            raise ValueError(
                f"unsupported plugin contract version {self.contract_version!r}; expected {CONTRACT_VERSION!r}"
            )
        schema = validate_configuration_schema(self.configuration_schema)
        expected_hash = stable_hash(schema, prefix="plugin_config")
        if self.configuration_hash != expected_hash:
            raise ValueError(
                "plugin configuration_hash does not match its canonical configuration schema: "
                f"expected {expected_hash!r}"
            )
        capabilities = tuple(str(item) for item in self.capabilities)
        if any(not item or not _IDENTIFIER_RE.match(item) for item in capabilities):
            raise ValueError("plugin capabilities must be stable non-empty identifiers")
        if len(capabilities) != len(set(capabilities)):
            raise ValueError("plugin capabilities must not contain duplicates")
        if self.trust_level in IN_PROCESS_TRUST_LEVELS and self.isolation_mode != "in_process":
            raise ValueError("trusted plugins must declare in_process isolation mode")
        if self.trust_level in ISOLATED_TRUST_LEVELS and self.isolation_mode != BOUNDED_SUBPROCESS_ISOLATION_MODE:
            raise ValueError("restricted and untrusted plugins must declare bounded_subprocess_v1 isolation mode")
        metadata = canonicalize(self.metadata, path="$.metadata")
        if not isinstance(metadata, dict):
            raise ValueError("plugin descriptor metadata must be a mapping")
        object.__setattr__(
            self,
            "configuration_schema",
            freeze_mapping(schema, path="$.plugin_descriptor.configuration_schema"),
        )
        object.__setattr__(self, "capabilities", capabilities)
        object.__setattr__(
            self,
            "metadata",
            freeze_mapping(metadata, path="$.plugin_descriptor.metadata"),
        )

    @classmethod
    def for_factory(
        cls,
        kind: str,
        name: str,
        factory: object,
        *,
        version: str | None = None,
        trust_level: TrustLevel = TrustLevel.LOCAL_TRUSTED,
        configuration_schema: Mapping[str, Any] | None = None,
        capabilities: tuple[str, ...] | None = None,
        isolation_mode: str | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> "PluginDescriptor":
        schema = validate_configuration_schema(
            configuration_schema or getattr(factory, "configuration_schema", None) or empty_configuration_schema()
        )
        selected_capabilities = tuple(
            str(value) for value in (capabilities if capabilities is not None else getattr(factory, "capabilities", ()))
        )
        mode = isolation_mode or (
            "in_process" if trust_level in IN_PROCESS_TRUST_LEVELS else BOUNDED_SUBPROCESS_ISOLATION_MODE
        )
        return cls(
            PLUGIN_DESCRIPTOR_SCHEMA_VERSION,
            kind,
            name,
            str(version if version is not None else getattr(factory, "version", "1.0.0")),
            CONTRACT_VERSION,
            implementation_identifier(factory),
            schema,
            stable_hash(schema, prefix="plugin_config"),
            trust_level,
            selected_capabilities,
            mode,
            metadata or {},
        )

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "PluginDescriptor":
        try:
            trust = TrustLevel(str(value["trust_level"]))
        except (KeyError, ValueError) as exc:
            raise ValueError("plugin descriptor trust_level is missing or invalid") from exc
        return cls(
            schema_version=str(value.get("schema_version", "")),
            kind=str(value.get("kind", "")),
            name=str(value.get("name", "")),
            version=str(value.get("version", "")),
            contract_version=str(value.get("contract_version", "")),
            implementation_identifier=str(value.get("implementation_identifier", "")),
            configuration_schema=value.get("configuration_schema", {}),
            configuration_hash=str(value.get("configuration_hash", "")),
            trust_level=trust,
            capabilities=tuple(str(item) for item in value.get("capabilities", ())),
            isolation_mode=str(value.get("isolation_mode", "")),
            metadata=value.get("metadata", {}),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "kind": self.kind,
            "name": self.name,
            "version": self.version,
            "contract_version": self.contract_version,
            "implementation_identifier": self.implementation_identifier,
            "configuration_schema": canonicalize(self.configuration_schema),
            "configuration_hash": self.configuration_hash,
            "trust_level": self.trust_level.value,
            "capabilities": list(self.capabilities),
            "isolation_mode": self.isolation_mode,
            "metadata": canonicalize(self.metadata),
        }


@dataclass(frozen=True)
class VisibleObservation:
    response: ToolResponse
    context: ObservationContext


@dataclass(frozen=True)
class AgentPolicyContext:
    observation: VisibleObservation


@dataclass(frozen=True)
class ShiftResult:
    response: ToolResponse
    provenance: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "provenance", freeze_mapping(self.provenance, path="$.shift_result.provenance"))


@dataclass(frozen=True)
class PolicyTraceVisible:
    """Serializable trace containing only data available to policy code."""

    episode_id: str
    steps: tuple[Mapping[str, Any], ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "steps", tuple(deep_freeze(step) for step in self.steps))


@dataclass(frozen=True)
class EvaluatorTrace:
    """Serializable diagnostic trace kept outside the policy trace."""

    episode_id: str
    steps: tuple[Mapping[str, Any], ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "steps", tuple(deep_freeze(step) for step in self.steps))

    def to_dict(self) -> dict[str, Any]:
        return {"episode_id": self.episode_id, "steps": [canonicalize(step) for step in self.steps]}


@runtime_checkable
class PluginFactory(Protocol):
    name: ClassVar[str]
    version: ClassVar[str]
    capabilities: ClassVar[tuple[str, ...]]
    configuration_schema: ClassVar[Mapping[str, Any]]


@runtime_checkable
class EnvironmentPlugin(PluginFactory, Protocol):
    seed: int
    scenario_index: int
    scenario_id: str
    current_time: int

    def reset(self, seed: int, scenario_index: int = 0) -> None: ...
    def tool_response(self) -> ToolResponse: ...
    def execute(self, action: AgentAction, observed_timestamp: int | None = None) -> ExecutionResult: ...
    def pure_action_outcome(self, action: AgentAction, observed_timestamp: int | None = None) -> ExecutionResult: ...
    def hidden_ground_truth(self) -> Mapping[str, Any]: ...
    def visible_constraints(self) -> Mapping[str, Any]: ...
    def advance_time_ms(self, duration_ms: int) -> None: ...
    def lifecycle_snapshot(self) -> Mapping[str, Any]: ...
    def lifecycle_status(self) -> Mapping[str, Any]: ...
    def counterfactual_state(self) -> Mapping[str, Any]: ...
    def mark_budget_exhausted(self) -> None: ...
    def public_task_description(self) -> Mapping[str, Any]: ...
    def policy_adapter(self, observation: Observation) -> EnvironmentPolicyAdapter: ...
    def transition_parameters(self) -> Mapping[str, Any]: ...
    def scenario_family_descriptor(self) -> object: ...
    def generator_metadata(self) -> Mapping[str, Any]: ...


@runtime_checkable
class AgentPlugin(PluginFactory, Protocol):
    def decide(self, context: ObservationContext, response: ToolResponse) -> AgentDecision: ...


@runtime_checkable
class ShiftPlugin(PluginFactory, Protocol):
    severity: float

    def apply(self, response: ToolResponse, context: ShiftContext) -> ToolResponse: ...
    @classmethod
    def channel_descriptor(cls) -> object: ...


@runtime_checkable
class MonitorPlugin(PluginFactory, Protocol):
    def check(
        self,
        context: ObservationContext,
        observation: Observation,
        action: AgentAction,
    ) -> MonitorDecision: ...


@runtime_checkable
class EvaluatorPlugin(PluginFactory, Protocol):
    def score_action(
        self,
        environment: EnvironmentPlugin,
        action: AgentAction,
        *,
        observed_timestamp: int | None,
    ) -> object: ...
    def score_intervention(self, **kwargs: Any) -> object: ...
    def score(
        self,
        environment: EnvironmentPlugin,
        action: AgentAction,
        execution: ExecutionResult,
    ) -> Mapping[str, Any]: ...


@runtime_checkable
class ReporterPlugin(PluginFactory, Protocol):
    def report(self, records: object) -> object: ...


@runtime_checkable
class EnvironmentPolicyAdapter(Protocol):
    contract_version: str
    action_schema: Mapping[str, Any]
    capabilities: tuple[str, ...]

    def visible_candidates(self, observation: Observation) -> tuple[Mapping[str, Any], ...]: ...
    def validate_observation_data(self, data: Mapping[str, Any]) -> tuple[str, ...]: ...
    def validate_action(
        self, action: AgentAction, observation: Observation | None = None
    ) -> tuple[bool, tuple[str, ...]]: ...
    def abstain(self, reason: str) -> AgentAction: ...
    def recommend_action(self, data: Mapping[str, Any]) -> AgentAction: ...
    def to_dict(self) -> Mapping[str, Any]: ...


REQUIRED_METHODS: Mapping[str, tuple[str, ...]] = {
    "environment": (
        "reset",
        "tool_response",
        "execute",
        "pure_action_outcome",
        "hidden_ground_truth",
        "visible_constraints",
        "advance_time_ms",
        "lifecycle_snapshot",
        "lifecycle_status",
        "counterfactual_state",
        "mark_budget_exhausted",
        "public_task_description",
        "policy_adapter",
        "transition_parameters",
        "scenario_family_descriptor",
        "generator_metadata",
    ),
    "agent": ("decide",),
    "shift": ("apply", "channel_descriptor"),
    "monitor": ("check",),
    "evaluator": ("score_action", "score_intervention", "score"),
    "reporter": ("report",),
}


def validate_plugin_factory(descriptor: PluginDescriptor, factory: object) -> None:
    """Apply identical implementation validation for every registration path."""

    if not callable(factory):
        raise ValueError(f"invalid {descriptor.kind} plugin {descriptor.name}: factory is not callable")
    actual_name = str(getattr(factory, "name", ""))
    if actual_name != descriptor.name:
        raise ValueError(f"invalid {descriptor.kind} plugin {descriptor.name}: factory name is {actual_name!r}")
    actual_identifier = implementation_identifier(factory)
    if actual_identifier != descriptor.implementation_identifier:
        raise ValueError(f"invalid {descriptor.kind} plugin {descriptor.name}: implementation identifier mismatch")
    for method in REQUIRED_METHODS[descriptor.kind]:
        if not callable(getattr(factory, method, None)):
            raise ValueError(f"invalid {descriptor.kind} plugin {descriptor.name}: missing {method} contract method")
    if descriptor.kind == "shift":
        parameters = tuple(inspect.signature(getattr(factory, "apply")).parameters.values())
        if (
            len(parameters) != 3
            or tuple(parameter.name for parameter in parameters) != ("self", "response", "context")
            or any(
                parameter.kind not in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)
                for parameter in parameters
            )
        ):
            raise ValueError(
                f"invalid shift plugin {descriptor.name}: apply signature must be (self, response, context)"
            )
    declared_schema = getattr(factory, "configuration_schema", descriptor.configuration_schema)
    normalized_schema = validate_configuration_schema(declared_schema)
    if stable_hash(normalized_schema, prefix="plugin_config") != descriptor.configuration_hash:
        raise ValueError(f"invalid {descriptor.kind} plugin {descriptor.name}: configuration schema/hash mismatch")
    declared_capabilities = tuple(str(value) for value in getattr(factory, "capabilities", descriptor.capabilities))
    if declared_capabilities != descriptor.capabilities:
        raise ValueError(f"invalid {descriptor.kind} plugin {descriptor.name}: capability declaration mismatch")
    if inspect.isabstract(factory):
        raise ValueError(f"invalid {descriptor.kind} plugin {descriptor.name}: implementation is abstract")


@dataclass(frozen=True)
class OrchestrationError:
    episode_id: str
    phase: str
    error_type: str
    message: str
    attempts: int = 1
    field: str | None = None
    expected: Any = None
    actual: Any = None
    plugin_descriptor: Mapping[str, Any] | None = None
    action_record: Mapping[str, Any] | None = None
    planned_episode: Mapping[str, Any] | None = None
    failure_details: Mapping[str, Any] | None = None

    def __post_init__(self) -> None:
        if self.plugin_descriptor is not None:
            object.__setattr__(
                self,
                "plugin_descriptor",
                freeze_mapping(self.plugin_descriptor, path="$.orchestration_error.plugin_descriptor"),
            )
        if self.action_record is not None:
            object.__setattr__(
                self,
                "action_record",
                freeze_mapping(self.action_record, path="$.orchestration_error.action_record"),
            )
        if self.planned_episode is not None:
            object.__setattr__(
                self,
                "planned_episode",
                freeze_mapping(self.planned_episode, path="$.orchestration_error.planned_episode"),
            )
        if self.failure_details is not None:
            object.__setattr__(
                self,
                "failure_details",
                freeze_mapping(self.failure_details, path="$.orchestration_error.failure_details"),
            )

    def to_dict(self) -> dict[str, Any]:
        normalized = canonicalize(self)
        if not isinstance(normalized, dict):
            raise RuntimeError("orchestration error did not serialize to a mapping")
        return normalized


class IdentityMismatchError(RuntimeError):
    """A runtime component disagreed with the planner's identity."""

    def __init__(
        self,
        *,
        field: str,
        expected: Any,
        actual: Any,
        phase: str,
        plugin_descriptor: Mapping[str, Any],
        episode_id: str,
    ):
        self.field = field
        self.expected = expected
        self.actual = actual
        self.phase = phase
        self.plugin_descriptor = dict(plugin_descriptor)
        self.episode_id = episode_id
        super().__init__(f"planned identity mismatch for {field}: expected {expected!r}, got {actual!r}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "episode_id": self.episode_id,
            "phase": self.phase,
            "error_type": type(self).__name__,
            "message": str(self),
            "field": self.field,
            "expected": self.expected,
            "actual": self.actual,
            "plugin_descriptor": self.plugin_descriptor,
        }


register_enum(TrustLevel)
for _serializable_dataclass in (
    PluginDescriptor,
    VisibleObservation,
    AgentPolicyContext,
    ShiftResult,
    PolicyTraceVisible,
    EvaluatorTrace,
    OrchestrationError,
):
    register_dataclass(_serializable_dataclass)
