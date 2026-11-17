# Update and rollback procedure for 0.18.1 (prepared, not executed)

Do this only on the owner's decision, never on a working production install
without a backup. Nothing in this repository runs it.

## Update

1. Stop the MCP client. Back up the install directory, `.env`, the audit DB and
   its `<db>.pending.key` (without the key, pending actions cannot be decrypted).
2. `git fetch && git checkout <release tag or merged commit>` in a **new** venv:
   `python -m venv .venv && . .venv/bin/activate && make install-certified`.
3. `python scripts/validate_local.py` must print `LOCAL VALIDATION GREEN`.
4. Add `GOOGLE_ADS_MCP_ALLOWED_MERCHANT_IDS` if Merchant is used while an Ads
   allowlist is set (see `docs/MERCHANT_V1_ONBOARDING.md`).
5. Start the client; run read-only checks first.

## Updating dependencies later

Re-resolve in a clean venv (`pip install -e '.[dev,auth]'`), run `make check`,
then regenerate `constraints-certified.txt` from `pip freeze` minus the editable
package. Never downgrade `google-ads` below 35.1.0 to keep v26.2 support.

## Rollback

Reinstall the previous tag in a fresh venv and restore the backed-up `.env`, DB
and `.pending.key`. 0.18.1 changes no DB schema and no tool names, so the same
database works with 0.18.0. Merchant on 0.18.0 would use `v1beta` Products/
DataSources, which Google is retiring.
