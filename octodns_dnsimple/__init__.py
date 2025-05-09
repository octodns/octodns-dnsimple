#
#
#

# TODO: remove __VERSION__ with the next major version release
__version__ = __VERSION__ = '1.0.0'


import logging
from collections import defaultdict

from requests import Session

from octodns import __VERSION__ as octodns_version
from octodns.provider import ProviderException
from octodns.provider.base import BaseProvider
from octodns.record import Record


class DnsimpleClientException(ProviderException):
    pass


class DnsimpleClientNotFound(DnsimpleClientException):
    def __init__(self):
        super().__init__('Not found')


class DnsimpleClientUnauthorized(DnsimpleClientException):
    def __init__(self):
        super().__init__('Unauthorized')


class DnsimpleClient(object):
    def __init__(self, token, account, sandbox):
        self.account = int(account)
        sess = Session()
        sess.headers.update(
            {
                'Authorization': f'Bearer {token}',
                'User-Agent': f'octodns/{octodns_version} octodns-dnsimple/{__VERSION__}',
            }
        )
        self._sess = sess
        if sandbox:
            self.base = 'https://api.sandbox.dnsimple.com/v2/'
        else:
            self.base = 'https://api.dnsimple.com/v2/'

    def _request(self, method, path, params=None, data=None):
        url = f'{self.base}{self.account:d}{path}'
        resp = self._sess.request(method, url, params=params, json=data)
        if resp.status_code == 401:
            raise DnsimpleClientUnauthorized()
        if resp.status_code == 404:
            raise DnsimpleClientNotFound()
        resp.raise_for_status()
        return resp

    def zone(self, name):
        path = f'/zones/{name}'
        return self._request('GET', path).json()

    def domain_create(self, name):
        return self._request('POST', '/domains', data={'name': name})

    def zones(self):
        ret = []

        page = 1
        while True:
            data = self._request('GET', '/zones', {'page': page}).json()
            ret += data['data']
            pagination = data['pagination']
            if page >= pagination['total_pages']:
                break
            page += 1

        return ret

    def records(self, zone_name):
        ret = []

        page = 1
        while True:
            data = self._request(
                'GET', f'/zones/{zone_name}/records', {'page': page}
            ).json()
            ret += data['data']
            pagination = data['pagination']
            if page >= pagination['total_pages']:
                break
            page += 1

        return ret

    def record_create(self, zone_name, params):
        path = f'/zones/{zone_name}/records'
        self._request('POST', path, data=params)

    def record_delete(self, zone_name, record_id):
        path = f'/zones/{zone_name}/records/{record_id}'
        self._request('DELETE', path)


class DnsimpleProvider(BaseProvider):
    SUPPORTS_GEO = False
    SUPPORTS_DYNAMIC = False
    SUPPORTS = set(
        (
            'A',
            'AAAA',
            'ALIAS',
            'CAA',
            'CNAME',
            'MX',
            'NAPTR',
            'NS',
            'PTR',
            'SRV',
            'SSHFP',
            'TXT',
        )
    )

    def __init__(self, id, token, account, sandbox=False, *args, **kwargs):
        self.log = logging.getLogger(f'DnsimpleProvider[{id}]')
        self.log.debug('__init__: id=%s, token=***, account=%s', id, account)
        super().__init__(id, *args, **kwargs)
        self._client = DnsimpleClient(token, account, sandbox)

        self._zone_records = {}

    def _data_for_multiple(self, _type, records):
        return {
            'ttl': records[0]['ttl'],
            'type': _type,
            'values': [r['content'] for r in records],
        }

    _data_for_A = _data_for_multiple
    _data_for_AAAA = _data_for_multiple

    def _data_for_TXT(self, _type, records):
        return {
            'ttl': records[0]['ttl'],
            'type': _type,
            # escape semicolons
            'values': [r['content'].replace(';', '\\;') for r in records],
        }

    def _data_for_CAA(self, _type, records):
        values = []
        for record in records:
            flags, tag, value = record['content'].split(' ')
            values.append({'flags': flags, 'tag': tag, 'value': value[1:-1]})
        return {'ttl': records[0]['ttl'], 'type': _type, 'values': values}

    def _data_for_CNAME(self, _type, records):
        record = records[0]
        return {
            'ttl': record['ttl'],
            'type': _type,
            'value': f'{record["content"]}.',
        }

    _data_for_ALIAS = _data_for_CNAME

    def _data_for_MX(self, _type, records):
        values = []
        for record in records:
            values.append(
                {
                    'preference': record['priority'],
                    'exchange': f'{record["content"]}.',
                }
            )
        return {'ttl': records[0]['ttl'], 'type': _type, 'values': values}

    def _data_for_NAPTR(self, _type, records):
        values = []
        for record in records:
            try:
                order, preference, flags, service, regexp, replacement = record[
                    'content'
                ].split(' ', 5)
            except ValueError:
                # their api will let you create invalid records, this
                # essentially handles that by ignoring them for values
                # purposes. That will cause updates to happen to delete them if
                # they shouldn't exist or update them if they're wrong
                continue
            values.append(
                {
                    'flags': flags[1:-1],
                    'order': order,
                    'preference': preference,
                    'regexp': regexp[1:-1],
                    'replacement': replacement,
                    'service': service[1:-1],
                }
            )
        return {'type': _type, 'ttl': records[0]['ttl'], 'values': values}

    def _data_for_NS(self, _type, records):
        values = []
        for record in records:
            content = record['content']
            if content[-1] != '.':
                content = f'{content}.'
            values.append(content)
        return {'ttl': records[0]['ttl'], 'type': _type, 'values': values}

    def _data_for_PTR(self, _type, records):
        record = records[0]
        return {'ttl': record['ttl'], 'type': _type, 'value': record['content']}

    def _data_for_SRV(self, _type, records):
        values = []
        for record in records:
            try:
                weight, port, target = record['content'].split(' ', 2)
            except ValueError:
                # their api/website will let you create invalid records, this
                # essentially handles that by ignoring them for values
                # purposes. That will cause updates to happen to delete them if
                # they shouldn't exist or update them if they're wrong
                self.log.warning(
                    '_data_for_SRV: unsupported %s record (%s)',
                    _type,
                    record['content'],
                )
                continue

            target = f'{target}.' if target[-1] != '.' else target

            values.append(
                {
                    'port': port,
                    'priority': record['priority'],
                    'target': target,
                    'weight': weight,
                }
            )
        return {'type': _type, 'ttl': records[0]['ttl'], 'values': values}

    def _data_for_SSHFP(self, _type, records):
        values = []
        for record in records:
            try:
                algorithm, fingerprint_type, fingerprint = record[
                    'content'
                ].split(' ', 2)
            except ValueError:
                # see _data_for_NAPTR's continue
                continue
            values.append(
                {
                    'algorithm': algorithm,
                    'fingerprint': fingerprint,
                    'fingerprint_type': fingerprint_type,
                }
            )
        return {'type': _type, 'ttl': records[0]['ttl'], 'values': values}

    def zone_records(self, zone):
        if zone.name not in self._zone_records:
            try:
                self._zone_records[zone.name] = self._client.records(
                    zone.name[:-1]
                )
            except DnsimpleClientNotFound:
                return []

        return self._zone_records[zone.name]

    def list_zones(self):
        return [f'{z["name"]}.' for z in self._client.zones()]

    def populate(self, zone, target=False, lenient=False):
        self.log.debug(
            'populate: name=%s, target=%s, lenient=%s',
            zone.name,
            target,
            lenient,
        )

        values = defaultdict(lambda: defaultdict(list))
        for record in self.zone_records(zone):
            _type = record['type']
            if _type not in self.SUPPORTS:
                self.log.warning(
                    'populate: skipping unsupported %s record', _type
                )
                continue
            elif _type == 'TXT' and record['content'].startswith('ALIAS for'):
                # ALIAS has a "ride along" TXT record with 'ALIAS for XXXX',
                # we're ignoring it
                continue
            values[record['name']][record['type']].append(record)

        before = len(zone.records)
        for name, types in values.items():
            for _type, records in types.items():
                data_for = getattr(self, f'_data_for_{_type}')
                record = Record.new(
                    zone,
                    name,
                    data_for(_type, records),
                    source=self,
                    lenient=lenient,
                )
                zone.add_record(record, lenient=lenient)

        exists = zone.name in self._zone_records
        self.log.info(
            'populate:   found %s records, exists=%s',
            len(zone.records) - before,
            exists,
        )
        return exists

    def supports(self, record):
        # DNSimple does not support empty/NULL SRV records
        #
        # Fails silently and leaves a corrupt record
        #
        # Skip the record and continue
        if record._type == "SRV":
            if 'value' in record.data:
                targets = (record.data['value']['target'],)
            else:
                targets = [value['target'] for value in record.data['values']]

            if "." in targets:
                self.log.warning(
                    'supports: unsupported %s record with target (%s)',
                    record._type,
                    targets,
                )
                return False

        return super().supports(record)

    def _params_for_multiple(self, record):
        for value in record.values:
            yield {
                'content': value,
                'name': record.name,
                'ttl': record.ttl,
                'type': record._type,
            }

    _params_for_A = _params_for_multiple
    _params_for_AAAA = _params_for_multiple
    _params_for_NS = _params_for_multiple

    def _params_for_TXT(self, record):
        for value in record.values:
            yield {
                # un-escape semicolons
                'content': value.replace('\\', ''),
                'name': record.name,
                'ttl': record.ttl,
                'type': record._type,
            }

    def _params_for_CAA(self, record):
        for value in record.values:
            yield {
                'content': f'{value.flags} {value.tag} "{value.value}"',
                'name': record.name,
                'ttl': record.ttl,
                'type': record._type,
            }

    def _params_for_single(self, record):
        yield {
            'content': record.value,
            'name': record.name,
            'ttl': record.ttl,
            'type': record._type,
        }

    _params_for_ALIAS = _params_for_single
    _params_for_CNAME = _params_for_single
    _params_for_PTR = _params_for_single

    def _params_for_MX(self, record):
        for value in record.values:
            yield {
                'content': value.exchange,
                'name': record.name,
                'priority': value.preference,
                'ttl': record.ttl,
                'type': record._type,
            }

    def _params_for_NAPTR(self, record):
        for value in record.values:
            content = (
                f'{value.order} {value.preference} "{value.flags}" '
                f'"{value.service}" "{value.preference}" {value.flags}'
            )
            yield {
                'content': content,
                'name': record.name,
                'ttl': record.ttl,
                'type': record._type,
            }

    def _params_for_SRV(self, record):
        for value in record.values:
            yield {
                'content': f'{value.weight} {value.port} {value.target}',
                'name': record.name,
                'priority': value.priority,
                'ttl': record.ttl,
                'type': record._type,
            }

    def _params_for_SSHFP(self, record):
        for value in record.values:
            yield {
                'content': f'{value.algorithm} {value.fingerprint_type} '
                f'{value.fingerprint}',
                'name': record.name,
                'ttl': record.ttl,
                'type': record._type,
            }

    def _apply_Create(self, change):
        new = change.new
        params_for = getattr(self, f'_params_for_{new._type}')
        for params in params_for(new):
            self._client.record_create(new.zone.name[:-1], params)

    def _apply_Update(self, change):
        self._apply_Delete(change)
        self._apply_Create(change)

    def _apply_Delete(self, change):
        existing = change.existing
        zone = existing.zone
        for record in self.zone_records(zone):
            if (
                existing.name == record['name']
                and existing._type == record['type']
            ):
                self._client.record_delete(zone.name[:-1], record['id'])

    def _apply(self, plan):
        desired = plan.desired
        changes = plan.changes
        self.log.debug(
            '_apply: zone=%s, len(changes)=%d', desired.name, len(changes)
        )

        domain_name = desired.name[:-1]
        try:
            self._client.zone(domain_name)
        except DnsimpleClientNotFound:
            self.log.debug('_apply:   no matching zone, creating domain')
            self._client.domain_create(domain_name)

        for change in changes:
            class_name = change.__class__.__name__
            getattr(self, f'_apply_{class_name}')(change)

        # Clear out the cache if any
        self._zone_records.pop(desired.name, None)
