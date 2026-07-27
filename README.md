# merox

**Meraki configuration backup to Git** — for teams who use [Oxidized](https://github.com/ytti/oxidized) for CLI gear and need the same for Dashboard-managed Meraki.

Meraki configs live in the cloud API, not `show running-config`. merox polls the Dashboard API on an interval, writes deterministic JSON into a Git working tree, and commits only when something changed.

```text
~/.config/merox/config.yml  →  Meraki API  →  Git repo (commit-on-change)
```

## Install

```bash
pip install git+https://github.com/borealis-ops/merox.git
```

Or from a checkout:

```bash
pip install .
```

Requires Git on `PATH` and Python 3.10+.

## Quick start

```bash
# 1. Scaffold config + empty Git backup repo
merox init

# 2. Authenticate (preferred)
export MERAKI_DASHBOARD_API_KEY=your_key_here

# 3. One-shot backup
merox run

# 4. Or daemon (Oxidized-style loop)
merox daemon
```

Default paths:

| What | Where |
|------|--------|
| Config | `~/.config/merox/config.yml` |
| Backup Git repo | `~/merox-configs` (override with `merox init --repo …`) |

## Config

Oxidized users should feel at home — YAML, interval, Git output:

```yaml
interval: 3600
# api_key: null   # prefer MERAKI_DASHBOARD_API_KEY
organizations: []   # empty = all orgs visible to the key (id or name)
network_tags: []    # optional: only networks with these tags
output:
  git:
    repo: /var/lib/merox/configs
    user: merox
    email: merox@localhost
```

Layout written into the Git repo:

```text
orgs/
  Acme/
    organization.json
    networks.json
    snmp.json
    networks/
      HQ/
        network.json
        settings.json
        appliance_firewall_l3.json
        devices/
          MX84_Q2XX-XXXX/
            device.json
            management_interface.json
```

Endpoint coverage is a curated subset of Meraki’s official [`backup_configs`](https://github.com/meraki/automation-scripts/tree/master/backup_configs) GET list (org / network / device configure APIs).

## Docker

```bash
export MERAKI_DASHBOARD_API_KEY=your_key_here
docker compose up -d --build
```

Compose mounts `docker/config/config.yml` and stores the Git tree in the `merox-data` volume (`/data/configs` in the container).

## CLI

| Command | Purpose |
|---------|---------|
| `merox init` | Create config + initialize Git backup repo |
| `merox run` | One backup cycle |
| `merox daemon` | Loop on `interval` (or `--interval`) |
| `merox --version` | Print version |

Use `-c /path/to/config.yml` to point at a non-default config. `-v` enables debug logs.

## What merox is not (v0.1)

- Not a restore / push-to-Meraki tool
- Not a web UI
- Not multi-vendor (Cisco IOS etc. — keep using Oxidized)
- Not tied to the Borealis platform runtime

## Brand

merox is part of the **Borealis** network-ops toolkit.  
Maintained by [borealis-ops](https://github.com/borealis-ops).

## License

MIT
