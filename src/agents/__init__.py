from .naive import NaiveAgent
from .retry import RetryAgent
from .validate_then_act import ValidateThenActAgent
from .monitor_gated import MonitorGatedAgent
from .conservative import ConservativeAbstentionAgent
from .offline_llm_fixture import OfflineLLMFixtureAgent

AGENTS = {
    "naive": NaiveAgent,
    "retry": RetryAgent,
    "validate_then_act": ValidateThenActAgent,
    "monitor_gated": MonitorGatedAgent,
    "conservative": ConservativeAbstentionAgent,
    "offline_llm_fixture": OfflineLLMFixtureAgent,
}
