from mkt_measurement_ops.gtm import GoogleTagManagerReadOnly, account_path, container_path, workspace_path


class _Request:
    def __init__(self, payload):
        self.payload = payload

    def execute(self):
        return self.payload


def test_gtm_paths() -> None:
    assert account_path("1") == "accounts/1"
    assert container_path("1", "2") == "accounts/1/containers/2"
    assert workspace_path("1", "2", "3") == "accounts/1/containers/2/workspaces/3"


def test_pagination_collects_every_page() -> None:
    calls = []

    def list_call(**kwargs):
        calls.append(kwargs)
        if "pageToken" not in kwargs:
            return _Request({"tag": [{"tagId": "1"}], "nextPageToken": "next"})
        return _Request({"tag": [{"tagId": "2"}]})

    rows = GoogleTagManagerReadOnly._paginate(list_call, "tag", parent="accounts/1/containers/2/workspaces/3")
    assert [row["tagId"] for row in rows] == ["1", "2"]
    assert calls[1]["pageToken"] == "next"
