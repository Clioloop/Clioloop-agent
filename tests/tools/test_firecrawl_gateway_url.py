"""Regression test: Firecrawl gateway requests must preserve the gateway sub-path.

The managed tool gateway base is a SUB-PATH ({portal}/api/gateway/firecrawl).
The Firecrawl v2 SDK builds request URLs with ``urljoin(api_url, "/v2/search")``,
and a leading-slash (root-relative) endpoint DISCARDS the base path — so without
the fix a subscriber's search/extract would hit ``{portal}/v2/search`` (a 404)
instead of the gateway proxy. ``_route_firecrawl_client_through_gateway`` rewrites
the SDK's URL builder to concatenate, preserving the sub-path.

These exercise the REAL Firecrawl SDK (no network — only URL construction), so a
future SDK shape change that breaks the override fails here loudly.
"""

from __future__ import annotations

import pytest

firecrawl = pytest.importorskip("firecrawl")

import tools.web_tools as wt
from tools.managed_tool_gateway import ManagedToolGatewayConfig

GATEWAY_ORIGIN = "https://portal.clioloop.com/api/gateway/firecrawl"


def _v2_http_client(client):
    """The HttpClient the v2 search/scrape/extract/map methods route through."""
    return client._v2_client.http_client


@pytest.fixture(autouse=True)
def _reset_client():
    wt._firecrawl_client = None
    wt._firecrawl_client_config = None
    yield
    wt._firecrawl_client = None
    wt._firecrawl_client_config = None


def test_gateway_client_preserves_subpath(monkeypatch):
    """Gateway-mode endpoints land on {gateway}/v2/... not the portal root."""
    import plugins.web.firecrawl.provider as prov

    gw = ManagedToolGatewayConfig(
        vendor="firecrawl",
        gateway_origin=GATEWAY_ORIGIN,
        managed_user_token="tok-123",
        managed_mode=True,
    )
    monkeypatch.setattr(wt, "prefers_gateway", lambda section: True)
    monkeypatch.setattr(wt, "resolve_managed_tool_gateway", lambda vendor, token_reader=None: gw)
    monkeypatch.setattr(wt, "_read_managed_access_token", lambda: "tok-123")
    monkeypatch.setattr(prov, "_get_direct_firecrawl_config", lambda: None)

    client = prov._get_firecrawl_client()
    build = _v2_http_client(client)._build_url

    assert build("/v2/search") == f"{GATEWAY_ORIGIN}/v2/search"
    assert build("/v2/scrape") == f"{GATEWAY_ORIGIN}/v2/scrape"
    assert build("/v2/extract") == f"{GATEWAY_ORIGIN}/v2/extract"
    assert build("/v2/map") == f"{GATEWAY_ORIGIN}/v2/map"
    # Relative endpoints (no leading slash) must also stay under the sub-path.
    assert build("v2/search") == f"{GATEWAY_ORIGIN}/v2/search"


def test_direct_client_is_not_rewritten(monkeypatch):
    """Direct (bring-your-own-key) mode keeps the SDK's default URL building."""
    import plugins.web.firecrawl.provider as prov

    monkeypatch.setattr(wt, "prefers_gateway", lambda section: False)
    monkeypatch.setattr(
        prov,
        "_get_direct_firecrawl_config",
        lambda: (
            {"api_key": "k", "api_url": "https://api.firecrawl.dev"},
            ("direct", "https://api.firecrawl.dev", "k"),
        ),
    )

    client = prov._get_firecrawl_client()
    assert _v2_http_client(client)._build_url("/v2/search") == "https://api.firecrawl.dev/v2/search"


def test_helper_is_noop_on_mock_client():
    """The override must skip test doubles so mocked-Firecrawl tests are unaffected."""
    from unittest.mock import MagicMock

    import plugins.web.firecrawl.provider as prov

    mock_client = MagicMock()
    # Must not raise and must not install a real builder on the mock.
    prov._route_firecrawl_client_through_gateway(mock_client)
    assert "_build_url" not in vars(mock_client._v2_client.http_client)
