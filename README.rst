====
pilo
====

Yet another form parser.

test
----

Run ``tox`` to run tests in Python 2 & 3.

release
-------

Using our internal invoke release tool: https://github.com/eventbrite/invoke-release#using-invoke-release-on-existing-projects
When prompted to enter a version, use +eventbrite at the end like so:
    Enter a new version (or "exit"): 2.2.0+eventbrite

usage
-----

Validation
~~~~~~~~~~

Here we validate that a message has acceptable headers and body.

.. code:: python

    from pilo import Form
    from pilo.fields import Dict, String


    class Message(Form):
        headers = Dict(String(choices=['to', 'from', 'content-type']), String())
        body = String(max_length=20)


    >>> print Message(headers={'to': 'William III'}, body='ha'*10)
    {'body': 'hahahahahahahahahaha', 'headers': {'to': 'William III'}}

    >>> print Message(headers={'send-to': 'William III'}, body='ha'*10)
    Invalid: headers - "send-to" is not one of "to", "from", "content-type"

    >>> print Message(headers={'to': 'William III'}, body='ha'*11)
    Invalid: body - "hahahahahahahahahahaha" must have length <= 20


Hooks
~~~~~

Override-able mechanism allowing users to inject functions to customize these
behaviors:

- compute
- resolve
- parse
- default
- munge
- filter
- validate

e.g.:

.. code:: python

    import pilo


    class ExtraCurricular(pilo.Form):

       category = pilo.fields.String(
           choices=['athletics', 'academics', 'social', 'service']
       )

       name = pilo.fields.String(max_length=40)

       description = pilo.fields.String(max_length=140)

       role = pilo.fields.String(choices=['member', 'leader'])


    class CollegeApplication(pilo.Form):

        high_school_name = pilo.fields.String()

        sat_score = pilo.fields.Integer()

        gpa = pilo.fields.Float()

        extra_curriculars = pilo.fields.List(pilo.fields.SubForm(ExtraCurricular))

        score = pilo.fields.Float(default=pilo.NONE)

        accepted = pilo.fields.Bool(default=False)

        @score.compute
        def score(self):
            leadership_roles = [
                ec for ec in self.extra_curriculars if ec.role == 'leader'
            ]
            relevant_extra_curriculars =[
                ec for ec in self.extra_curriculars
                if ec.category in ['academics', 'service']
            ]
            score = (
                10 * (self.sat_score / 1600.0) +
                10 * (self.gpa / 4.0) +
                 5 * len(leadership_roles) +
                 5 * len(relevant_extra_curriculars)
            )
            return score

        @accepted.compute
        def accepted(self):
            if self.score > 30:
                return True
            return False

        @high_school_name.munge
        def high_school_name(self, value):
            return value.upper()


    application = CollegeApplication(
        high_school_name='Bodega High',
        sat_score=1400,
        gpa=4.0,
        extra_curriculars=[
            dict(category='athletics', role='leader', name='hockey', description=''),
            dict(category='academics', role='member', name='chess club', description=''),
        ]
    )


    >>> print application.high_school_name
    BODEGA HIGH

    >>> print application.score
    28.75

    >>> print application.accepted
    False


Form polymorphism and type downcasting
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

In the following example, a user has an address, but the address schema is
polymorphic on the country abbreviation.

.. code:: python

    import pilo
    import uuid


    class Address(pilo.Form):

        guid = pilo.fields.UUID(default=uuid.uuid4)
        country = pilo.fields.Type.abstract()


    class UnitedKingdomAddress(Address):

        country = pilo.fields.Type.constant('UK')
        name = pilo.fields.String()
        street = pilo.fields.String()
        locality = pilo.fields.String()
        post_town = pilo.fields.String()
        postcode = pilo.fields.String()


    class UnitedStatesAddress(Address):

        country = pilo.fields.Type.constant('USA')
        name = pilo.fields.String()
        street = pilo.fields.String()
        unit = pilo.fields.String(default=None)
        city = pilo.fields.String()
        state = pilo.fields.String()
        zip = pilo.fields.String(length=5)


    class User(pilo.Form):

         guid = pilo.fields.UUID(default=uuid.uuid4)
         name = pilo.fields.String()
         address = pilo.fields.PolymorphicSubForm(Address.country)


    mikey_representation = dict(
        name='Michael Pikey',
        address=dict(
            country='UK',
            name='Mikey Pikey',
            street='351 Meagre Lane',
            locality='Hedge End',
            post_town='Southampton',
            postcode='SO31 4NG',
        )
    )


    bart_representation = dict(
        name='Bartholomew Simpson',
        address=dict(
            country='USA',
            name='Bite Me',
            street='742 Evergreen Terrace',
            city='Springfield',
            state='???',
            zip='12345',
        )
    )


    mikey = User(**mikey_representation)


    bart = User(**bart_representation)


    >>> print dict(mikey)
    {
        'address': {
            'country': 'UK',
            'guid': UUID('8c73752c-69a2-4832-99f8-c5354cbeec59'),
            'locality': 'Hedge End',
            'name': 'Mikey Pikey',
            'post_town': 'Southampton',
            'postcode': 'SO31 4NG',
            'street': '351 Meagre Lane'
        },
        'guid': UUID('eee0953c-1b5a-4bd0-893d-f513b1cf24f4'),
        'name': 'Michael Pikey'
    }

    >>> print dict(bart)
    {
        'address': {
            'city': 'Springfield',
            'country': 'USA',
            'guid': UUID('a321bedd-8b94-46b8-830e-ea137b08a608'),
            'name': 'Bite Me',
            'state': '???',
            'street': '742 Evergreen Terrace',
            'unit': None,
            'zip': '12345'
        },
        'guid': UUID('3155a3dd-4b5a-4990-aaea-439359bb36a9'),
        'name': 'Bartholomew Simpson'
    }

    >>> print mikey.address.postcode
    SO31 4NG

    >>> print bart.address.zip
    12345

    >>> print type(mikey.address).__name__
    UnitedKingdomAddress

    >>> print type(bart.address).__name__
    UnitedStatesAddress
