import providers
from providers.base import ProviderProfile

DISPLAY_MODELS = [
    "auto-kiro",
    "auto",
    "claude-sonnet-4.6",
    "claude-sonnet-4.5",
    "claude-opus-4.6",
    "claude-opus-4.5",
    "claude-haiku-4.5",
    "claude-sonnet-5",
    "claude-opus-5",
    "gpt-5.6-sol",
    "gpt-5.6-terra",
    "gpt-5.6-luna",
    "minimax-m2.5",
    "minimax-m2.1",
    "qwen3-coder-next",
]

class KiroProfile(ProviderProfile):
    def fetch_models(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout: float = 8.0,
        **kwargs
    ) -> list[str] | None:
        return DISPLAY_MODELS

kiro = KiroProfile(
    name="kiro",
    aliases=("q", "amazon-q", "codewhisperer"),
    display_name="AWS Kiro (Q Developer)",
    description="Query Claude Sonnet, Opus, and coding models directly using your AWS Kiro subscription",
    signup_url="https://kiro.dev",
    env_vars=("KIRO_API_KEY", "KIRO_BASE_URL"),
    base_url="http://127.0.0.1:8997/v1",
    auth_type="api_key",
    default_aux_model="claude-sonnet-4.6",
    fallback_models=tuple(DISPLAY_MODELS),
)

providers.register_provider(kiro)
