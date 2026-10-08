import pytest

from mkt_measurement_ops.gtm import GoogleTagManagerReadOnly


class _DiscoverClient(GoogleTagManagerReadOnly):
    def __init__(self, accounts, containers):
        self._accounts_fixture = accounts
        self._containers_fixture = containers

    def list_accounts(self):
        return list(self._accounts_fixture)

    def list_containers(self, account_id):
        return list(self._containers_fixture.get(account_id, []))


def test_discovers_container_by_public_id() -> None:
    client = _DiscoverClient(
        [{"accountId": "1"}],
        {
            "1": [
                {
                    "accountId": "1",
                    "containerId": "2",
                    "publicId": "GTM-ABC",
                    "name": "Example",
                    "domainName": ["example.com"],
                }
            ]
        },
    )

    result = client.discover_container(public_id="gtm-abc")

    assert result["account_id"] == "1"
    assert result["container_id"] == "2"
    assert result["public_id"] == "GTM-ABC"


def test_discovers_container_by_normalized_domain() -> None:
    client = _DiscoverClient(
        [{"path": "accounts/1"}],
        {
            "1": [
                {
                    "accountId": "1",
                    "containerId": "2",
                    "publicId": "GTM-ABC",
                    "domainName": ["www.example.com"],
                }
            ]
        },
    )

    assert client.discover_container(domain="https://example.com")["container_id"] == "2"


def test_ambiguous_domain_discovery_fails_closed() -> None:
    client = _DiscoverClient(
        [{"accountId": "1"}, {"accountId": "2"}],
        {
            "1": [{"accountId": "1", "containerId": "10", "domainName": ["example.com"]}],
            "2": [{"accountId": "2", "containerId": "20", "domainName": ["example.com"]}],
        },
    )

    with pytest.raises(LookupError, match="multiple"):
        client.discover_container(domain="example.com")
