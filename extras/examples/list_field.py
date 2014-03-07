from __future__ import unicode_literals

import json
from pprint import pprint

import pilo

raw = json.dumps({
    'guru_id': 'OHMb47eb95e4cbf11e39c10026ba7f8ec28',
    'request': {
        'headers': [
            ['Authorization', 'Basic !@#!@#!@#'],
            ['X-Forwarded-Proto', 'https'],
            ['Host', 'api.balancedpayments.com'],
            ['X-Real-Ip', '96.126.105.48'],
            ['Accept', '*/*'],
            ['User-Agent', 'balanced-ruby/0.7.0'],
            ['X-Forwarded-Port', '443'],
            ['X-Forwarded-For', '96.126.105.48, 50.18.213.193'],
            ['Accept-Encoding', 'gzip;q=1.0,deflate;q=0.6,identity;q=0.3']
            ],
        'method': 'GET',
    }
})


class Request(pilo.Form):

    headers = pilo.fields.List(pilo.fields.Tuple(
        fields=(pilo.fields.String(), pilo.fields.String())
    ))

    @headers.munge
    def headers(self, value):
        return dict(value)

    method = pilo.fields.String(choices=['GET', 'POST', 'PUT', 'DELETE'])


class Envelope(pilo.Form):

    guru_id = pilo.fields.String(pattern=r'OHM(\w){32}$')

    request = pilo.fields.SubForm(Request)


source = json.loads(raw)
form = Envelope()
errors = form(source)
pprint(form)
pprint(errors)
