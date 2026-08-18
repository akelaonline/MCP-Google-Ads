from pathlib import Path


client = Path("src/google_ads_mcp/client.py")
text = client.read_text()
old = '''        kwargs: dict[str, Any] = {
            "customer_id": customer_id,
            operations_field: operation_list,
        }
'''
new = '''        if operations_field == "operation":
            if len(operation_list) != 1:
                raise GoogleAdsMcpError(
                    f"{service_name}.{method_name} accepts exactly one operation; "
                    f"received {len(operation_list)}."
                )
            operation_value: Any = operation_list[0]
        else:
            operation_value = operation_list

        kwargs: dict[str, Any] = {
            "customer_id": customer_id,
            operations_field: operation_value,
        }
'''
if old not in text:
    raise SystemExit("client mutate kwargs block not found")
client.write_text(text.replace(old, new, 1))


billing = Path("src/google_ads_mcp/tools/billing.py")
text = billing.read_text()
old = '''            issue_year=str(issue_year),
            issue_month=month,
            include_granular_level_invoice_details=include_granular_details,
'''
new = '''            issue_year=str(issue_year),
            issue_month=ctx.client.raw.enums.MonthOfYearEnum[month].value,
            include_granular_level_invoice_details=include_granular_details,
'''
if old not in text:
    raise SystemExit("billing month block not found")
billing.write_text(text.replace(old, new, 1))


test = Path("tests/test_agency_v25_contracts.py")
text = test.read_text()
old = '    assert kwargs["issue_month"] == "JULY"\n'
new = (
    '    assert kwargs["issue_month"] == client.raw.enums.MonthOfYearEnum.JULY.value\n'
)
if old not in text:
    raise SystemExit("invoice contract expectation not found")
test.write_text(text.replace(old, new, 1))
