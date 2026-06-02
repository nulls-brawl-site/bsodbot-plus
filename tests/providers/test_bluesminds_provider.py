"""Tests for the BluesMinds provider registration."""

from nanobot.config.schema import Config, ProvidersConfig
from nanobot.providers.factory import make_provider
from nanobot.providers.openai_compat_provider import OpenAICompatProvider
from nanobot.providers.registry import PROVIDERS, find_by_name


def test_bluesminds_config_field_exists() -> None:
    config = ProvidersConfig()

    assert hasattr(config, "bluesminds")


def test_bluesminds_provider_in_registry() -> None:
    specs = {spec.name: spec for spec in PROVIDERS}

    assert "bluesminds" in specs
    bluesminds = specs["bluesminds"]
    assert bluesminds.backend == "openai_compat"
    assert bluesminds.env_key == "BLUESMINDS_API_KEY"
    assert bluesminds.display_name == "BluesMinds"
    assert bluesminds.is_gateway is True
    assert bluesminds.is_direct is False
    assert bluesminds.detect_by_base_keyword == "bluesminds"
    assert bluesminds.default_api_base == "https://api.bluesminds.com/v1"


def test_find_by_name_bluesminds_accepts_common_typo() -> None:
    assert find_by_name("bluesminds") is not None
    assert find_by_name("blueminds").name == "bluesminds"


def test_bluesminds_forced_provider_requires_api_key() -> None:
    config = Config.model_validate({
        "providers": {
            "bluesminds": {
                "apiBase": "https://api.bluesminds.com/v1",
            },
        },
        "agents": {
            "defaults": {
                "model": "gemini-3.1-pro-preview",
                "provider": "bluesminds",
            },
        },
    })

    assert config.get_provider_name("gemini-3.1-pro-preview") == "bluesminds"
    assert config.get_api_key("gemini-3.1-pro-preview") is None
    assert config.get_api_base("gemini-3.1-pro-preview") == "https://api.bluesminds.com/v1"

    try:
        make_provider(config)
    except ValueError as exc:
        assert "No API key configured for provider 'bluesminds'" in str(exc)
    else:
        raise AssertionError("BluesMinds without api_key should not build a provider")


def test_bluesminds_forced_provider_uses_default_api_base_with_key() -> None:
    config = Config.model_validate({
        "providers": {
            "bluesminds": {
                "apiKey": "blues-key",
                "apiBase": "https://api.bluesminds.com/v1",
            },
        },
        "agents": {
            "defaults": {
                "model": "gemini-3.1-pro-preview",
                "provider": "bluesminds",
            },
        },
    })

    provider = make_provider(config)

    assert isinstance(provider, OpenAICompatProvider)
    assert provider.default_model == "gemini-3.1-pro-preview"


def test_bluesminds_provider_config_alias_is_normalized() -> None:
    config = Config.model_validate({
        "providers": {
            "blueminds": {
                "apiBase": "https://api.bluesminds.com/v1",
            },
        },
        "agents": {
            "defaults": {
                "model": "gpt-5-chat",
                "provider": "blueminds",
            },
        },
    })

    assert config.get_provider_name("gpt-5-chat") == "bluesminds"
    assert config.get_api_base("gpt-5-chat") == "https://api.bluesminds.com/v1"
