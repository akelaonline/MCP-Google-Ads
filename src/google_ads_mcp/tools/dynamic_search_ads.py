"""Dynamic Search Ads (DSA) campaign creation and webpage targeting.

DSA campaigns use ``advertising_channel_sub_type = SEARCH_DYNAMIC_ADS`` plus a
``dynamic_search_ads_setting`` (domain + language). Webpage criteria then
select which pages of the domain can trigger ads; conditions combine an
operand (URL/CATEGORY/PAGE_TITLE/PAGE_CONTENT/CUSTOM_LABEL) with an operator
(EQUALS/CONTAINS) and an argument.
"""

from __future__ import annotations

from ..campaign_compat import (
    DEFAULT_EU_POLITICAL_ADVERTISING,
    apply_campaign_dates,
    apply_required_campaign_fields,
)
from ..client import micros
from ..context import AppContext

_WEBPAGE_OPERANDS = {
    "URL", "CATEGORY", "PAGE_TITLE", "PAGE_CONTENT", "CUSTOM_LABEL"
}
_WEBPAGE_OPERATORS = {"EQUALS", "CONTAINS"}


def _validate_conditions(conditions) -> list[tuple[str, str, str]]:
    if not conditions:
        raise ValueError("Provide at least one webpage condition.")
    normalized: list[tuple[str, str, str]] = []
    for item in conditions:
        operand = str(item.get("operand", "")).strip().upper()
        operator = str(item.get("operator", "")).strip().upper()
        argument = str(item.get("argument", ""))
        if operand not in _WEBPAGE_OPERANDS:
            raise ValueError(
                f"operand must be one of {sorted(_WEBPAGE_OPERANDS)}, got {operand!r}."
            )
        if operator not in _WEBPAGE_OPERATORS:
            raise ValueError(
                f"operator must be one of {sorted(_WEBPAGE_OPERATORS)}, got {operator!r}."
            )
        if not argument:
            raise ValueError("Every webpage condition needs a non-empty argument.")
        normalized.append((operand, operator, argument))
    return normalized


def register(mcp, ctx: AppContext) -> None:
    @mcp.tool()
    def create_dsa_campaign(
        customer_id: str,
        name: str,
        campaign_budget_resource_name: str,
        domain_name: str,
        language_code: str,
        use_supplied_urls_only: bool = False,
        target_cpa: float | None = None,
        campaign_group_id: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        contains_eu_political_advertising: str = DEFAULT_EU_POLITICAL_ADVERTISING,
    ) -> dict:
        """Propose creating a Dynamic Search Ads campaign. Created PAUSED.

        ``domain_name`` is the root domain to crawl (for example
        ``example.com``), ``language_code`` the site language (for example
        ``en`` or ``es``). ``use_supplied_urls_only=True`` restricts delivery
        to URLs supplied through page feeds / webpage targets. Bidding is
        Manual CPC unless ``target_cpa`` is provided.

        v25 identifies DSA campaigns by channel SEARCH + ``dynamic_search_ads_setting``;
        the SEARCH_DYNAMIC_ADS marker lives on the ad group type instead
        (see ``create_dsa_ad_group``).
        """
        if not name.strip():
            raise ValueError("name must not be empty.")
        domain = domain_name.strip().lower()
        if not domain or "." not in domain or " " in domain:
            raise ValueError(
                "domain_name must be a valid root domain, for example example.com."
            )
        if not language_code or len(language_code) != 2:
            raise ValueError("language_code must be a two-letter language code.")
        if target_cpa is not None and target_cpa <= 0:
            raise ValueError("target_cpa must be greater than 0.")

        client = ctx.client.raw
        operation = client.get_type("CampaignOperation")
        campaign = operation.create
        campaign.name = name
        campaign.campaign_budget = campaign_budget_resource_name
        campaign.advertising_channel_type = (
            client.enums.AdvertisingChannelTypeEnum.SEARCH
        )
        campaign.status = client.enums.CampaignStatusEnum.PAUSED
        campaign.dynamic_search_ads_setting.domain_name = domain
        campaign.dynamic_search_ads_setting.language_code = language_code
        campaign.dynamic_search_ads_setting.use_supplied_urls_only = (
            use_supplied_urls_only
        )
        campaign.network_settings.target_google_search = True
        campaign.network_settings.target_search_network = True
        if target_cpa is not None:
            campaign.target_cpa.target_cpa_micros = micros(target_cpa)
        else:
            client.copy_from(campaign.manual_cpc, client.get_type("ManualCpc"))
        if campaign_group_id is not None:
            campaign.campaign_group = client.get_service(
                "CampaignGroupService"
            ).campaign_group_path(
                customer_id.replace("-", ""), str(campaign_group_id)
            )
        apply_campaign_dates(campaign, start_date=start_date, end_date=end_date)
        apply_required_campaign_fields(
            client,
            campaign,
            contains_eu_political_advertising=contains_eu_political_advertising,
        )

        description = (
            f"Create DSA campaign '{name}' for {domain} ({language_code}), "
            "created PAUSED"
        )

        def execute():
            return ctx.client.mutate("CampaignService", customer_id, [operation])

        return ctx.safety.propose(
            tool_name="create_dsa_campaign",
            customer_id=customer_id,
            description=description,
            payload={
                "name": name,
                "domain_name": domain,
                "language_code": language_code,
                "use_supplied_urls_only": use_supplied_urls_only,
                "target_cpa": target_cpa,
                "campaign_group_id": campaign_group_id,
                "start_date": start_date,
                "end_date": end_date,
                "contains_eu_political_advertising": contains_eu_political_advertising,
            },
            execute=execute,
        )

    @mcp.tool()
    def create_dsa_ad_group(
        customer_id: str,
        campaign_id: str,
        name: str,
        status: str = "PAUSED",
    ) -> dict:
        """Propose creating a Dynamic Search Ads ad group. Created PAUSED.

        DSA ad groups use ``AdGroupType.SEARCH_DYNAMIC_ADS``. They cannot
        contain positive keywords; delivery is driven by the campaign's
        ``dynamic_search_ads_setting`` plus webpage targets added with
        ``add_webpage_target``.
        """
        if not name.strip():
            raise ValueError("name must not be empty.")
        if status not in {"ENABLED", "PAUSED"}:
            raise ValueError("status must be ENABLED or PAUSED when creating an ad group.")

        client = ctx.client.raw
        operation = client.get_type("AdGroupOperation")
        ad_group = operation.create
        ad_group.name = name
        ad_group.campaign = client.get_service("CampaignService").campaign_path(
            customer_id.replace("-", ""), campaign_id
        )
        ad_group.status = client.enums.AdGroupStatusEnum[status].value
        ad_group.type_ = client.enums.AdGroupTypeEnum.SEARCH_DYNAMIC_ADS

        description = (
            f"Create DSA ad group '{name}' in campaign {campaign_id} "
            f"(type SEARCH_DYNAMIC_ADS, status={status})"
        )

        def execute():
            return ctx.client.mutate("AdGroupService", customer_id, [operation])

        return ctx.safety.propose(
            tool_name="create_dsa_ad_group",
            customer_id=customer_id,
            description=description,
            payload={
                "campaign_id": campaign_id,
                "name": name,
                "status": status,
            },
            execute=execute,
        )

    @mcp.tool()
    def add_webpage_target(
        customer_id: str,
        campaign_id: str,
        conditions: list[dict],
        criterion_name: str | None = None,
        negative: bool = False,
        bid_modifier: float | None = None,
    ) -> dict:
        """Propose adding a webpage (DSA) targeting criterion to a campaign.

        Each condition is a dict with ``operand`` (URL, CATEGORY, PAGE_TITLE,
        PAGE_CONTENT, CUSTOM_LABEL), ``operator`` (EQUALS, CONTAINS) and
        ``argument``. All conditions within one criterion are AND-ed together.
        """
        normalized = _validate_conditions(conditions)
        if bid_modifier is not None and not (0.0 <= bid_modifier <= 10.0):
            raise ValueError("bid_modifier must be between 0 and 10.")

        client = ctx.client.raw
        operation = client.get_type("CampaignCriterionOperation")
        criterion = operation.create
        criterion.campaign = client.get_service("CampaignService").campaign_path(
            customer_id.replace("-", ""), campaign_id
        )
        criterion.negative = negative
        if criterion_name is not None:
            criterion.webpage.criterion_name = criterion_name
        for operand, operator, argument in normalized:
            criterion.webpage.conditions.append(
                {
                    "operand": client.enums.WebpageConditionOperandEnum[
                        operand
                    ].value,
                    "operator": client.enums.WebpageConditionOperatorEnum[
                        operator
                    ].value,
                    "argument": argument,
                }
            )
        if bid_modifier is not None:
            criterion.bid_modifier = bid_modifier

        verb = "Exclude" if negative else "Target"
        description = (
            f"{verb} webpages on campaign {campaign_id} with "
            f"{len(normalized)} condition(s)"
            + (f" [{criterion_name}]" if criterion_name else "")
        )

        def execute():
            return ctx.client.mutate(
                "CampaignCriterionService", customer_id, [operation]
            )

        return ctx.safety.propose(
            tool_name="add_webpage_target",
            customer_id=customer_id,
            description=description,
            payload={
                "campaign_id": campaign_id,
                "conditions": normalized,
                "criterion_name": criterion_name,
                "negative": negative,
                "bid_modifier": bid_modifier,
            },
            execute=execute,
        )

    @mcp.tool()
    def list_webpage_targets(customer_id: str, campaign_id: str) -> dict:
        """List webpage (DSA) targeting criteria on a campaign."""
        query = f"""
            SELECT campaign_criterion.criterion_id,
                   campaign_criterion.negative,
                   campaign_criterion.bid_modifier,
                   campaign_criterion.webpage.criterion_name,
                   campaign_criterion.webpage.conditions
            FROM campaign_criterion
            WHERE campaign.id = {int(campaign_id)}
              AND campaign_criterion.type = WEBPAGE
        """
        rows = ctx.client.search(customer_id, query)
        return {"campaign_id": campaign_id, "webpage_targets": rows, "count": len(rows)}
