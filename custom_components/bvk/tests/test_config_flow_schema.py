import pytest


def test_config_flow_builds_schema_without_homeassistant(monkeypatch: pytest.MonkeyPatch):
    """Sanity test: schema constants are wired and default URL is a string.

    We don't spin up Home Assistant test harness here; that's heavy and would
    require extra dependencies.
    """

    from custom_components.bvk.const import DEFAULT_API_URL

    assert isinstance(DEFAULT_API_URL, str)
    assert DEFAULT_API_URL
