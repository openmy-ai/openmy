# Security Policy

## Supported Versions

OpenMy is currently maintained on the latest `main` branch.
Security fixes are best-effort for the most recent tagged release and the current default branch.

## Reporting a Vulnerability

Please do **not** open a public GitHub issue for security-sensitive reports.

Instead:

1. Prefer GitHub's private vulnerability reporting / security advisory flow if it is enabled for the repository.
2. If that flow is unavailable, contact a maintainer privately and include enough detail to reproduce the issue safely.

Please include:

- affected version / commit
- impact and severity estimate
- reproduction steps or proof of concept
- any mitigation ideas you already tested

## What to Expect

Maintainers will try to:

- acknowledge a new report within 7 days
- reproduce and assess the issue
- work on a fix or mitigation
- coordinate disclosure once a safe fix exists

## Scope

This policy covers vulnerabilities such as:

- secret leakage
- path traversal
- prompt injection that crosses trust boundaries
- unsafe file writes or data corruption risks
- privilege escalation or unauthorized data access

## Disclosure

Please give maintainers reasonable time to investigate and ship a fix before public disclosure.
We appreciate reports that are specific, reproducible, and narrowly scoped.
