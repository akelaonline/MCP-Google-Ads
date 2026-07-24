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
    campaign_types,
    campaigns,
    conversions,
    keywords,
    performance_max,
    reporting,
    targeting,
)

ALL_MODULES = [
    accounts,
    reporting,
    campaigns,
    campaign_types,
    budgets,
    bidding,
    targeting,
    ad_groups,
    ads,
    assets,
    keywords,
    bulk,
    audiences,
    conversions,
    performance_max,
]
