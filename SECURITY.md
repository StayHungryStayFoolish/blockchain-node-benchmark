# Security Policy

## Supported Versions

Security fixes are handled on the default branch. If the project starts
publishing tagged releases, this section will be updated with explicit support
windows.

## Reporting a Vulnerability

Please do not open a public issue for suspected vulnerabilities.

Use GitHub private vulnerability reporting when available, or contact the
repository maintainer through GitHub with a minimal description of the issue.

Include:

- Affected component or file path.
- Reproduction steps or proof of concept.
- Impact and required privileges.
- Whether secrets, credentials, private RPC URLs, benchmark archives, or
  machine-local paths may be exposed.

Do not include live API keys, private RPC endpoints, customer data, or private
infrastructure details in public comments.

## Scope

Security-sensitive areas include:

- RPC proxy request handling.
- fake-node fixture recording and playback.
- Generated benchmark artifacts and archives.
- Prometheus/Grafana exporter output.
- Kubernetes manifests, host mounts, and container privileges.
- Dependency, CI, and release workflows.

## Expected Response

Maintainers will acknowledge valid reports as soon as practical, investigate the
impact, and coordinate a fix before public disclosure when appropriate.
