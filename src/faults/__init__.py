from .base import NoFault
from .compound import CompoundShiftFault
from .conflicting_output import ConflictingOutputFault
from .constraint_shift import ConstraintShiftFault
from .corrupted_memory import CorruptedMemoryFault
from .latency_spike import LatencySpikeFault
from .missing_field import MissingFieldFault
from .schema_drift import SchemaDriftFault
from .stale_observation import StaleObservationFault

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
