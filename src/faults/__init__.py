from .base import NoFault
from .schema_drift import SchemaDriftFault
from .stale_observation import StaleObservationFault
from .latency_spike import LatencySpikeFault
from .missing_field import MissingFieldFault
from .conflicting_output import ConflictingOutputFault
from .corrupted_memory import CorruptedMemoryFault
from .constraint_shift import ConstraintShiftFault
from .compound import CompoundShiftFault

FAULTS = {
    "normal": NoFault,
    "schema_drift": SchemaDriftFault,
    "stale_observation": StaleObservationFault,
    "latency_spike": LatencySpikeFault,
    "missing_field": MissingFieldFault,
    "conflicting_tool_output": ConflictingOutputFault,
    "corrupted_memory": CorruptedMemoryFault,
    "constraint_shift": ConstraintShiftFault,
    "compound_shift": CompoundShiftFault,
}
