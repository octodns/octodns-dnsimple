# Developer Agent Guide for octoDNS DNSimple Provider

This repository contains the DNSimple provider for octoDNS. It enables planning, syncing, and applying DNS record states to the DNSimple DNS platform.

> [!IMPORTANT]
> **Core Workflow and Guidelines**
>
> All agents working on this repository must read and follow the general instructions and workflow guidelines defined in the core octoDNS `AGENTS.md` file.
> - **Local check**: Look for the file at `../octodns/AGENTS.md`.
> - **Remote check**: If the local file is not available, fetch it from GitHub: [octoDNS Core AGENTS.md](https://github.com/octodns/octodns/raw/refs/heads/main/AGENTS.md).
>
> You must align your code structure, style, pull request guidelines, and overall development workflows with the instructions specified there.

## Repository & Module Information

### Key Components

- **Provider Class**: [DnsimpleProvider](file:///home/ross/octodns/octodns-dnsimple/octodns_dnsimple/__init__.py#L106-L472) (defined in [octodns_dnsimple/__init__.py](file:///home/ross/octodns/octodns-dnsimple/octodns_dnsimple/__init__.py)). Handles mapping between DNSimple API models and octoDNS zones/records.
- **Client Class**: [DnsimpleClient](file:///home/ross/octodns/octodns-dnsimple/octodns_dnsimple/__init__.py#L34-L104) communicates with DNSimple v2 API, handling authentication, sandbox settings, pagination (iterates through pages to build full lists), and status errors (401 Unauthorized, 404 NotFound).

### Key Workflows & Features

1. **Supported Record Types**: `A`, `AAAA`, `ALIAS`, `CAA`, `CNAME`, `MX`, `NAPTR`, `NS`, `PTR`, `SRV`, `SSHFP`, `TXT`.
2. **Sandbox Environment**: Supports setting `sandbox=True` during initialization to route API requests to `https://api.sandbox.dnsimple.com/v2/` instead of production `https://api.dnsimple.com/v2/`.
3. **Authentication**: Uses Bearer Token authentication via the `token` argument alongside a target `account` ID.
4. **Dynamic Routing**: Not supported (`SUPPORTS_DYNAMIC=False`, `SUPPORTS_GEO=False`).
5. **Dynamic Subnets**: Not supported (`SUPPORTS_DYNAMIC_SUBNETS=False`).
6. **Pool Value Status**: Not supported (`SUPPORTS_POOL_VALUE_STATUS=False`).

## Development & Testing

- **Setup Script**: Run `./script/bootstrap` to create a virtual environment, install runtime and development dependencies (including `black`, `isort`, `pyflakes`, and `pytest`), and configure pre-commit hooks.
- **Test Suite**: Run unit tests using `pytest` via `./script/test` (or `pytest tests/`). Test files are located in [tests/](file:///home/ross/octodns/octodns-dnsimple/tests).
- **Code Coverage**: Verify code coverage using `./script/coverage`.

## Key Constraints & Behaviors

- **Python Version**: Targets Python `>=3.9`.
- **Formatting**: Code formatting is enforced via `black` (version `>=26.0.0,<27.0.0`) and `isort`.
