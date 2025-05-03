## v1.0.0 - 2024-??-?? - ???

Noteworthy Changes:

* Complete removal of SPF record support, records should be transitioned to TXT
  values before updating to this version.

Changes:

* Address pending octoDNS 2.x deprecations, require minimum of 1.5.x

## v0.0.3 - 2024-03-11 - Format the types

* Fix handling of SRV target trailing dot
* Ensure account id is an int

## v0.0.2 - 2023-10-06 - Know your zones

* Suppoort for list_zones/dynamic zone config
* Meaningful user-agent added to all requests

## v0.0.1 - 2021-12-31 - Moving

* Initial extraction of DnsimpleProvider from octoDNS core
