"""Tests for provider-scoped OpenAI-compatible proxy configuration."""

from unittest.mock import MagicMock, patch

from nanobot.config.schema import Config, ProviderConfig
from nanobot.providers.factory import make_provider, provider_signature
from nanobot.providers.registry import find_by_name


def test_provider_config_accepts_proxy() -> None:
    config = ProviderConfig(proxy="http://user:pass@example.test:8080")

    assert config.proxy == "http://user:pass@example.test:8080"


def test_openai_compat_uses_provider_proxy_and_ignores_env_proxy() -> None:
    from nanobot.providers.openai_compat_provider import OpenAICompatProvider

    created = {}

    class FakeAsyncClient:
        def __init__(self, **kwargs):
            created.update(kwargs)

    with patch("httpx.AsyncClient", FakeAsyncClient),          patch("nanobot.providers.openai_compat_provider.AsyncOpenAI", MagicMock()):
        provider = OpenAICompatProvider(
            api_key="key",
            default_model="gemini-3.5-flash",
            spec=find_by_name("gemini"),
            proxy=" http://proxy.local:8080 ",
        )
        provider._build_client()

    assert created["proxy"] == "http://proxy.local:8080"
    assert created["trust_env"] is False


def test_factory_passes_proxy_to_openai_compat_provider() -> None:
    config = Config.model_validate({
        "providers": {
            "gemini": {
                "apiKey": "gemini-key",
                "proxy": "http://proxy.local:8080",
            },
        },
        "agents": {
            "defaults": {
                "model": "gemini-3.5-flash",
                "provider": "gemini",
            },
        },
    })

    provider = make_provider(config)

    assert provider._proxy == "http://proxy.local:8080"
    assert "http://proxy.local:8080" in provider_signature(config)
