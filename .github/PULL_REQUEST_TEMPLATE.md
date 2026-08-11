## Summary

<!-- Describe what this PR changes and why. Keep it concise but specific. -->

## Type of change

- [ ] Bug fix
- [ ] New tool or feature
- [ ] Documentation update
- [ ] Refactor / code quality
- [ ] Dependency update
- [ ] CI / build

## Test plan

- [ ] `make check` passes locally (`ruff check`, `pytest`, `smoke test`).
- [ ] New functionality is covered by unit tests with mocked Google Ads services.
- [ ] I manually verified the change against a real/test Google Ads account.
- [ ] README / TOOLS.md / CHANGELOG.md updated if user-facing behavior changed.

## Safety check

- [ ] Every new write tool routes through `ctx.safety.propose(...)`.
- [ ] No Google Ads credentials, `.env`, or `audit.db` files are committed.
- [ ] No raw PII is transmitted unhashed.

## Checklist before requesting review

- [ ] My branch is up to date with `main`.
- [ ] Commits are clean and focused (one logical change per commit).
- [ ] I have reviewed my own diff for accidental changes.

## Additional context

<!-- Optional: screenshots, related issues, notes for reviewers. -->
