from .conservative import ConservativeAbstentionAgent
from .naive import NaiveAgent
from .offline_llm_fixture import OfflineLLMFixtureAgent
from .retry import RetryAgent
from .validate_then_act import ValidateThenActAgent

AGENTS = {
    "naive": NaiveAgent,
    "retry": RetryAgent,
    "validate_then_act": ValidateThenActAgent,
    "conservative": ConservativeAbstentionAgent,
    "offline_llm_fixture": OfflineLLMFixtureAgent,
}

DIAGNOSTIC_AGENTS = ("naive", "offline_llm_fixture")
REFERENCE_AGENTS = ("validate_then_act", "conservative", "retry")
AGENT_ROLES = {
    **{name: "diagnostic" for name in DIAGNOSTIC_AGENTS},
    **{name: "reference" for name in REFERENCE_AGENTS},
}
