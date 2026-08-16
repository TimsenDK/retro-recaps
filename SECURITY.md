# Security Policy

This project publishes a dataset and a static site generator. It has no server,
no accounts and no user data, so the attack surface is small — but not empty.

## Reporting a vulnerability

Report privately through GitHub's
[security advisory](../../security/advisories/new) form rather than in a public
issue. You can expect an acknowledgement within a week.

## What is in scope

- Code execution or path traversal in the build tooling under `tools/`, for
  instance through a crafted YAML file in a pull request.
- Cross-site scripting in the generated site, for instance through unescaped
  data or an unsafe link in a board note.
- Vulnerabilities in the GitHub Actions workflows, such as script injection
  through pull request metadata, or an over-privileged token.
- Malicious or hijacked links planted in `sources` or `suppliers.yaml`.

## What is not in scope

- Incorrect capacitor data. That is a data bug — open a normal issue, with a
  source. It matters, and it is not a security report.
- Vulnerabilities in third-party sites this project links to.
- Anything requiring an already-merged malicious commit.

## Supported versions

The `main` branch is the only supported version. Fixes land there and are
deployed on push.
