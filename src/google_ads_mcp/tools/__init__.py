"""All tool modules, in the order they get registered on the MCP server."""

from . import (
    accounts,
    ad_groups,
    ads,
    assets,
    audiences,
    bidding,
    budgets,
    bulk,
    campaigns,
    conversions,
    keywords,
    performance_max,
    reporting,
)

ALL_MODULES = [
    accounts,
    reporting,
    campaigns,
    budgets,
    bidding,
    ad_groups,
    ads,
    assets,
    keywords,
    bulk,
    audiences,
    conversions,
    performance_max,
]
