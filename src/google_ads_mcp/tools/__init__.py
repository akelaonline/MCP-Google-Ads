"""All tool modules, in the order they get registered on the MCP server."""

from . import (
    accounts,
    ad_groups,
    ads,
    assets,
    audiences,
    bidding,
    budgets,
    campaigns,
    conversions,
    keywords,
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
    audiences,
    conversions,
]
