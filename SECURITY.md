# Security Policy

## Reporting a Vulnerability

The Love Journal project takes security seriously. We appreciate the efforts of
security researchers and users who responsibly disclose vulnerabilities.

**Please DO NOT open public GitHub Issues for security vulnerabilities.**

### How to Report

Send an email to **ad001@hmcsz.top** to report a vulnerability privately:

1. Email `ad001@hmcsz.top` with a description, reproduction steps, and impact
   assessment.
2. The maintainers will be notified privately and respond as soon as possible.

This ensures the report is visible only to repository maintainers and the
reporter until a fix is coordinated and published.

### Response Timeline

| Stage | Target |
| --- | --- |
| Initial acknowledgement | Within 72 hours |
| Preliminary assessment | Within 7 days |
| Fix or mitigation | Within 90 days (severity dependent) |

### Scope

Security issues in the **server**, **web**, **Android**, and **netease-api**
components of this repository are in scope, including but not limited to:

- Authentication / authorization bypass (JWT, session, cookie handling)
- SQL injection, XSS, CSRF, SSRF
- Cryptographic weaknesses (E2EE chat, vault encryption, cookie vault)
- Sensitive data exposure (PII, credentials, location data)
- Path traversal / arbitrary file access
- Denial of service through crafted inputs

The following are **out of scope**:

- Vulnerabilities in third-party dependencies — report to the upstream project
- Self-hosted deployments using default/weak credentials after explicit warnings
- Issues requiring physical access to a user's device
- The upstream NeteaseCloudMusicApiEnhanced service (report to its maintainers)

### Disclosure

We follow **coordinated disclosure**. Once a fix is released we will publish a
security advisory with credit to the reporter (unless they prefer to
remain anonymous).
