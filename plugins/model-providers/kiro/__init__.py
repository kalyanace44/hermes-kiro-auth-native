import json
import urllib.request
import providers
from providers.base import ProviderProfile

DISPLAY_MODELS = [
    "claude-sonnet-4.6",
    "claude-sonnet-4.5",
    "claude-sonnet-5",
    "claude-sonnet-4",
    "claude-3.7-sonnet",
    "claude-opus-5",
    "claude-opus-4.8",
    "claude-opus-4.7",
    "claude-opus-4.6",
    "claude-opus-4.5",
    "claude-haiku-4.5",
    "gpt-5.6-sol",
    "gpt-5.6-terra",
    "gpt-5.6-luna",
    "minimax-m2.5",
    "minimax-m2.1",
    "qwen3-coder-next",
    "auto-kiro",
    "auto",
]

class KiroProfile(ProviderProfile):
    def fetch_models(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout: float = 4.0,
        **kwargs
    ) -> list[str] | None:
        target_url = (base_url or "http://127.0.0.1:8997/v1").rstrip("/") + "/models"
        try:
            req = urllib.request.Request(
                target_url,
                headers={
                    "Authorization": f"Bearer {api_key or 'mock'}",
                    "User-Agent": "Hermes-Agent/1.0"
                }
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                models = [m["id"] for m in data.get("data", []) if "id" in m]
                if models:
                    ordered = []
                    for m in DISPLAY_MODELS:
                        if m in models:
                            ordered.append(m)
                    for m in models:
                        if m not in ordered:
                            ordered.append(m)
                    return ordered
        except Exception:
            pass
        return DISPLAY_MODELS

kiro = KiroProfile(
    name="kiro",
    aliases=("q", "amazon-q", "codewhisperer", "custom:kiro-gateway-local", "kiro-gateway-local"),
    display_name="AWS Kiro (Q Developer)",
    description="Query Claude 3.7 Sonnet, Opus, GPT-5.6, and coding models directly using your AWS Kiro subscription",
    signup_url="https://kiro.dev",
    env_vars=("KIRO_API_KEY", "KIRO_BASE_URL"),
    base_url="http://127.0.0.1:8997/v1",
    auth_type="api_key",
    default_aux_model="claude-sonnet-4.6",
    fallback_models=tuple(DISPLAY_MODELS),
)

providers.register_provider(kiro)
