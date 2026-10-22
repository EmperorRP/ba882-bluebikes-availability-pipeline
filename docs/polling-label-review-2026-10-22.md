# Collection and label regression review

The existing 15-minute post-target label policy is retained. The label unit-test fixture now covers a station polled every half hour whose source reports precede each collection by 30 seconds. A target at 13:00 has reports at 12:59:30 and 13:29:30: neither qualifies. A separate five-minute collection produces a report at 13:04:30 and a real positive label.

These synthetic rows are dbt unit-test inputs, not additions to shared source tables or training data. The production polling change is proposed separately in PR #17. Faster collection creates more opportunities for usable labels, but report freshness, station usability, collection gaps and distinct periods/classes still determine training readiness.

The `dbt parse` workflow validates project configuration, models and test definitions using the pinned Python 3.12 development dependencies. It uses a credential-free parse-only profile and does not run warehouse SQL tests. A separate authenticated build/unit-test check is still required before merge or deployment.
