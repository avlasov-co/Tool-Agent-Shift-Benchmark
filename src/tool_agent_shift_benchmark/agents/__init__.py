from .conservative import ConservativeAbstentionAgent
from .monitor_gated import MonitorGatedAgent
from .naive import NaiveAgent
from .offline_llm_fixture import OfflineLLMFixtureAgent
from .retry import RetryAgent
from .validate_then_act import ValidateThenActAgent

AGENTS = {
    "naive": NaiveAgent,
    "retry": RetryAgent,
    "validate_then_act": ValidateThenActAgent,
    "monitor_gated": MonitorGatedAgent,
    "conservative": ConservativeAbstentionAgent,
    "offline_llm_fixture": OfflineLLMFixtureAgent,
}
