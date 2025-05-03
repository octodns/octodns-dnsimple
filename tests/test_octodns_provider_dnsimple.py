#
#
#

from os.path import dirname, join
from unittest import TestCase
from unittest.mock import Mock, call

from requests import HTTPError
from requests_mock import ANY
from requests_mock import mock as requests_mock

from octodns import __VERSION__ as octodns_version
from octodns.provider.yaml import YamlProvider
from octodns.record import Record
from octodns.zone import Zone

from octodns_dnsimple import __VERSION__ as dnsimple_version
from octodns_dnsimple import (
    DnsimpleClient,
    DnsimpleClientNotFound,
    DnsimpleProvider,
)


class TestDnsimpleProvider(TestCase):
    expected = Zone('unit.tests.', [])
    source = YamlProvider('test', join(dirname(__file__), 'config'))
    source.populate(expected)

    # Our test suite differs a bit, add our NS and remove the simple one
    expected.add_record(
        Record.new(
            expected,
            'under',
            {
                'ttl': 3600,
                'type': 'NS',
                'values': ['ns1.unit.tests.', 'ns2.unit.tests.'],
            },
        )
    )
    for record in list(expected.records):
        if record.name == 'sub' and record._type == 'NS':
            expected.remove_record(record)
            break

    def test_list_zones(self):
        # Sandbox
        provider = DnsimpleProvider('test', 'token', 42, 'true')
        self.assertTrue('sandbox' in provider._client.base)

        provider = DnsimpleProvider('test', 'token', 42)
        self.assertFalse('sandbox' in provider._client.base)

        with requests_mock() as mock:
            base = 'https://api.dnsimple.com/v2/42/zones?page='
            mock.get(
                f'{base}1',
                json={
                    'data': [{'name': 'first.com'}, {'name': 'second.com'}],
                    'pagination': {
                        'current_page': 1,
                        'per_page': 2,
                        'total_entries': 4,
                        'total_pages': 2,
                    },
                },
            )
            mock.get(
                f'{base}2',
                json={
                    'data': [{'name': 'third.com'}, {'name': 'fourth.com'}],
                    'pagination': {
                        'current_page': 2,
                        'per_page': 2,
                        'total_entries': 4,
                        'total_pages': 2,
                    },
                },
            )

            self.assertEqual(
                ['first.com.', 'second.com.', 'third.com.', 'fourth.com.'],
                provider.list_zones(),
            )

    def test_populate(self):
        # Sandbox
        provider = DnsimpleProvider('test', 'token', 42, 'true')
        self.assertTrue('sandbox' in provider._client.base)

        provider = DnsimpleProvider('test', 'token', 42)
        self.assertFalse('sandbox' in provider._client.base)

        # Bad auth
        with requests_mock() as mock:
            mock.get(
                ANY,
                status_code=401,
                text='{"message": "Authentication failed"}',
            )

            with self.assertRaises(Exception) as ctx:
                zone = Zone('unit.tests.', [])
                provider.populate(zone)
            self.assertEqual('Unauthorized', str(ctx.exception))

        # General error
        with requests_mock() as mock:
            mock.get(ANY, status_code=502, text='Things caught fire')

            with self.assertRaises(HTTPError) as ctx:
                zone = Zone('unit.tests.', [])
                provider.populate(zone)
            self.assertEqual(502, ctx.exception.response.status_code)

        # Non-existent zone doesn't populate anything
        with requests_mock() as mock:
            mock.get(
                ANY,
                status_code=404,
                text='{"message": "Domain `foo.bar` not found"}',
            )

            zone = Zone('unit.tests.', [])
            provider.populate(zone)
            self.assertEqual(set(), zone.records)

        # No diffs == no changes
        with requests_mock() as mock:
            base = (
                'https://api.dnsimple.com/v2/42/zones/unit.tests/'
                'records?page='
            )
            with open('tests/fixtures/dnsimple-page-1.json') as fh:
                mock.get(f'{base}1', text=fh.read())
            with open('tests/fixtures/dnsimple-page-2.json') as fh:
                mock.get(f'{base}2', text=fh.read())

            zone = Zone('unit.tests.', [])
            provider.populate(zone)
            self.assertEqual(15, len(zone.records))
            changes = self.expected.changes(zone, provider)
            self.assertEqual(0, len(changes))

        # 2nd populate makes no network calls/all from cache
        again = Zone('unit.tests.', [])
        provider.populate(again)
        self.assertEqual(15, len(again.records))

        # bust the cache
        del provider._zone_records[zone.name]

        # test handling of invalid content
        with requests_mock() as mock:
            with open('tests/fixtures/dnsimple-invalid-content.json') as fh:
                mock.get(ANY, text=fh.read())

            zone = Zone('unit.tests.', [])
            provider.populate(zone, lenient=True)
            self.assertEqual(
                set(
                    [
                        Record.new(
                            zone,
                            '',
                            {'ttl': 3600, 'type': 'SSHFP', 'values': []},
                            lenient=True,
                        ),
                        Record.new(
                            zone,
                            '_srv._tcp',
                            {'ttl': 600, 'type': 'SRV', 'values': []},
                            lenient=True,
                        ),
                        Record.new(
                            zone,
                            'naptr',
                            {'ttl': 600, 'type': 'NAPTR', 'values': []},
                            lenient=True,
                        ),
                    ]
                ),
                zone.records,
            )

    def test_apply(self):
        provider = DnsimpleProvider('test', 'token', 42, strict_supports=False)

        resp = Mock()
        resp.json = Mock()
        provider._client._request = Mock(return_value=resp)

        # non-existent domain, create everything
        resp.json.side_effect = [
            DnsimpleClientNotFound,  # no zone in populate
            DnsimpleClientNotFound,  # no domain during apply
        ]
        plan = provider.plan(self.expected)

        # No root NS, no ignored, no excluded
        n = len(self.expected.records) - 8
        self.assertEqual(n, len(plan.changes))
        self.assertEqual(n, provider.apply(plan))
        self.assertFalse(plan.exists)

        provider._client._request.assert_has_calls(
            [
                # created the domain
                call('POST', '/domains', data={'name': 'unit.tests'}),
                # created at least some of the record with expected data
                call(
                    'POST',
                    '/zones/unit.tests/records',
                    data={
                        'content': '1.2.3.4',
                        'type': 'A',
                        'name': '',
                        'ttl': 300,
                    },
                ),
                call(
                    'POST',
                    '/zones/unit.tests/records',
                    data={
                        'content': '1.2.3.5',
                        'type': 'A',
                        'name': '',
                        'ttl': 300,
                    },
                ),
                call(
                    'POST',
                    '/zones/unit.tests/records',
                    data={
                        'content': '0 issue "ca.unit.tests"',
                        'type': 'CAA',
                        'name': '',
                        'ttl': 3600,
                    },
                ),
                call(
                    'POST',
                    '/zones/unit.tests/records',
                    data={
                        'content': '1 1 7491973e5f8b39d5327cd4e08bc81b05f7710b49',
                        'type': 'SSHFP',
                        'name': '',
                        'ttl': 3600,
                    },
                ),
                call(
                    'POST',
                    '/zones/unit.tests/records',
                    data={
                        'content': '1 1 bf6b6825d2977c511a475bbefb88aad54a92ac73',
                        'type': 'SSHFP',
                        'name': '',
                        'ttl': 3600,
                    },
                ),
                call(
                    'POST',
                    '/zones/unit.tests/records',
                    data={
                        'content': '20 30 foo-1.unit.tests.',
                        'priority': 10,
                        'type': 'SRV',
                        'name': '_srv._tcp',
                        'ttl': 600,
                    },
                ),
            ]
        )
        # expected number of total calls
        self.assertEqual(27, provider._client._request.call_count)

        provider._client._request.reset_mock()

        # delete 1 and update 1
        provider._client.records = Mock(
            return_value=[
                {
                    'id': 11189897,
                    'name': 'www',
                    'content': '1.2.3.4',
                    'ttl': 300,
                    'type': 'A',
                },
                {
                    'id': 11189898,
                    'name': 'www',
                    'content': '2.2.3.4',
                    'ttl': 300,
                    'type': 'A',
                },
                {
                    'id': 11189899,
                    'name': 'ttl',
                    'content': '3.2.3.4',
                    'ttl': 600,
                    'type': 'A',
                },
            ]
        )
        # Domain exists, we don't care about return
        resp.json.side_effect = ['{}']

        wanted = Zone('unit.tests.', [])
        wanted.add_record(
            Record.new(
                wanted, 'ttl', {'ttl': 300, 'type': 'A', 'value': '3.2.3.4'}
            )
        )

        plan = provider.plan(wanted)
        self.assertTrue(plan.exists)
        self.assertEqual(2, len(plan.changes))
        self.assertEqual(2, provider.apply(plan))
        # recreate for update, and deletes for the 2 parts of the other
        provider._client._request.assert_has_calls(
            [
                call(
                    'POST',
                    '/zones/unit.tests/records',
                    data={
                        'content': '3.2.3.4',
                        'type': 'A',
                        'name': 'ttl',
                        'ttl': 300,
                    },
                ),
                call('DELETE', '/zones/unit.tests/records/11189899'),
                call('DELETE', '/zones/unit.tests/records/11189897'),
                call('DELETE', '/zones/unit.tests/records/11189898'),
            ],
            any_order=True,
        )


class TestDnsimpleClient(TestCase):
    def test_request(self):
        client = DnsimpleClient('token', 32, False)

        # Request correctness
        with requests_mock() as mock:
            mock.get(
                'https://api.dnsimple.com/v2/32/zones/unit.tests',
                status_code=404,
                text='Zone not found',
            )

            with self.assertRaises(Exception):
                client.zone('unit.tests')

            assert mock.last_request.headers['Authorization'] == 'Bearer token'
            assert (
                mock.last_request.headers['User-Agent']
                == f'octodns/{octodns_version} octodns-dnsimple/{dnsimple_version}'
            )
