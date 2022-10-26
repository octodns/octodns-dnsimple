## DNSimple provider for octoDNS

An [octoDNS](https://github.com/octodns/octodns/) provider that targets [DnsimpleProvider](https://developer.dnsimple.com/v2/).

### Installation

#### Command line

```
pip install octodns-dnsimple
```

#### requirements.txt/setup.py

Pinning specific versions or SHAs is recommended to avoid unplanned upgrades.

##### Versions

```
# Start with the latest versions and don't just copy what's here
octodns==0.9.14
octodns-dnsimple==0.0.1
```

##### SHAs

```
# Start with the latest/specific versions and don't just copy what's here
-e git+https://git@github.com/octodns/octodns.git@9da19749e28f68407a1c246dfdf65663cdc1c422#egg=octodns
-e git+https://git@github.com/octodns/octodns-dnsimple.git@ec9661f8b335241ae4746eea467a8509205e6a30#egg=octodns_dnsimple
```

### Configuration

```yaml
providers:
  dnsimple:
    class: octodns_dnsimple.DnsimpleProvider
    # API v2 account access token (required)
    token: letmein
    # Your account number (required)
    account: 42
    # Use sandbox (optional)
    sandbox: false
```

### Support Information

#### Records

All octoDNS record types are supported, there are some restrictions on CAA tags.

#### Dynamic

DnsimpleProvider does not support dynamic records.

### Development

See the [/script/](/script/) directory for some tools to help with the development process. They generally follow the [Script to rule them all](https://github.com/github/scripts-to-rule-them-all) pattern. Most useful is `./script/bootstrap` which will create a venv and install both the runtime and development related requirements. It will also hook up a pre-commit hook that covers most of what's run by CI.
