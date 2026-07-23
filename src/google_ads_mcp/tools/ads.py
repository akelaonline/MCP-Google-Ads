"""Ad creative tools — Responsive Search Ads plus status management."""

from __future__ import annotations

from google.protobuf import field_mask_pb2

from ..context import AppContext


def register(mcp, ctx: AppContext) -> None:
    @mcp.tool()
    def create_responsive_search_ad(
        customer_id: str,
        ad_group_id: str,
        headlines: list[str],
        descriptions: list[str],
        final_urls: list[str],
        path1: str | None = None,
        path2: str | None = None,
    ) -> dict:
        """Propose creating a Responsive Search Ad.

        Args:
            headlines: 3-15 strings, each <=30 characters.
            descriptions: 2-4 strings, each <=90 characters.
            final_urls: Landing page URL(s).
            path1 / path2: Optional display-URL path segments (<=15 chars each).
        """
        if not (3 <= len(headlines) <= 15):
            raise ValueError("Provide between 3 and 15 headlines.")
        if not (2 <= len(descriptions) <= 4):
            raise ValueError("Provide between 2 and 4 descriptions.")
        if any(len(h) > 30 for h in headlines):
            raise ValueError("Each headline must be 30 characters or fewer.")
        if any(len(d) > 90 for d in descriptions):
            raise ValueError("Each description must be 90 characters or fewer.")

        client = ctx.client.raw
        operation = client.get_type("AdGroupAdOperation")
        ad_group_ad = operation.create
        ad_group_ad.ad_group = client.get_service("AdGroupService").ad_group_path(
            customer_id.replace("-", ""), ad_group_id
        )
        ad_group_ad.status = client.enums.AdGroupAdStatusEnum.PAUSED

        rsa = ad_group_ad.ad.responsive_search_ad
        for text in headlines:
            asset = client.get_type("AdTextAsset")
            asset.text = text
            rsa.headlines.append(asset)
        for text in descriptions:
            asset = client.get_type("AdTextAsset")
            asset.text = text
            rsa.descriptions.append(asset)
        if path1:
            rsa.path1 = path1
        if path2:
            rsa.path2 = path2
        ad_group_ad.ad.final_urls.extend(final_urls)

        description = (
            f"Create Responsive Search Ad in ad group {ad_group_id} "
            f"({len(headlines)} headlines, {len(descriptions)} descriptions), created PAUSED"
        )

        def execute():
            return ctx.client.mutate("AdGroupAdService", customer_id, [operation])

        return ctx.safety.propose(
            tool_name="create_responsive_search_ad",
            customer_id=customer_id,
            description=description,
            payload={
                "ad_group_id": ad_group_id,
                "headlines": headlines,
                "descriptions": descriptions,
                "final_urls": final_urls,
            },
            execute=execute,
        )

    @mcp.tool()
    def update_ad_status(customer_id: str, ad_group_id: str, ad_id: str, status: str) -> dict:
        """Propose pausing, enabling, or removing an ad.

        Args:
            status: ENABLED, PAUSED, or REMOVED.
        """
        client = ctx.client.raw
        operation = client.get_type("AdGroupAdOperation")
        resource_name = client.get_service("AdGroupAdService").ad_group_ad_path(
            customer_id.replace("-", ""), ad_group_id, ad_id
        )
        operation.update.resource_name = resource_name
        operation.update.status = client.enums.AdGroupAdStatusEnum[status].value
        operation.update_mask.CopyFrom(field_mask_pb2.FieldMask(paths=["status"]))

        description = f"Set ad {ad_id} (ad group {ad_group_id}) status -> {status}"

        def execute():
            return ctx.client.mutate("AdGroupAdService", customer_id, [operation])

        return ctx.safety.propose(
            tool_name="update_ad_status",
            customer_id=customer_id,
            description=description,
            payload={"ad_group_id": ad_group_id, "ad_id": ad_id, "status": status},
            execute=execute,
        )

    @mcp.tool()
    def remove_ad(customer_id: str, ad_group_id: str, ad_id: str) -> dict:
        """Propose permanently removing an ad."""
        client = ctx.client.raw
        operation = client.get_type("AdGroupAdOperation")
        operation.remove = client.get_service("AdGroupAdService").ad_group_ad_path(
            customer_id.replace("-", ""), ad_group_id, ad_id
        )

        description = f"REMOVE ad {ad_id} from ad group {ad_group_id} (irreversible)"

        def execute():
            return ctx.client.mutate("AdGroupAdService", customer_id, [operation])

        return ctx.safety.propose(
            tool_name="remove_ad",
            customer_id=customer_id,
            description=description,
            payload={"ad_group_id": ad_group_id, "ad_id": ad_id},
            execute=execute,
        )
