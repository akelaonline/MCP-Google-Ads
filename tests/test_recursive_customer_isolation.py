from __future__ import annotations

import pytest
from google.protobuf import struct_pb2

from google_ads_mcp.client import _assert_mutation_targets_customer
from google_ads_mcp.errors import GoogleAdsMcpError


def _nested_message(resource_name: str):
    message = struct_pb2.Struct()
    message.update(
        {
            "create": {
                "campaign": "customers/1234567890/campaigns/1",
                "nested": {
                    "asset": resource_name,
                    "other": ["not-a-resource", "https://example.com"],
                },
            }
        }
    )
    return message


def test_recursive_guard_allows_same_customer_create_references():
    _assert_mutation_targets_customer(
        "1234567890",
        [_nested_message("customers/1234567890/assets/9")],
    )


def test_recursive_guard_blocks_cross_customer_reference_inside_create():
    with pytest.raises(GoogleAdsMcpError, match="Cross-customer mutation blocked"):
        _assert_mutation_targets_customer(
            "1234567890",
            [_nested_message("customers/9999999999/assets/9")],
        )


def test_recursive_guard_blocks_cross_customer_reference_inside_protobuf_list():
    message = struct_pb2.Struct()
    message.update(
        {
            "create": {
                "assets": [
                    "customers/1234567890/assets/1",
                    "customers/9999999999/assets/2",
                ]
            }
        }
    )
    with pytest.raises(GoogleAdsMcpError, match="Cross-customer mutation blocked"):
        _assert_mutation_targets_customer("1234567890", [message])


def test_recursive_guard_blocks_root_customer_resource_reference():
    message = struct_pb2.Struct()
    message.update({"customer": "customers/9999999999"})
    with pytest.raises(GoogleAdsMcpError):
        _assert_mutation_targets_customer("1234567890", [message])
