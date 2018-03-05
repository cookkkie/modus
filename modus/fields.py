import re
import functools
import datetime

from modus.field import Field
from modus.exceptions import FieldValidationError, StopValidation, SerializationError
from decimal import Decimal


class BaseField(Field):

    ERRORS = {'required': 'This field is required',
              'choices': 'Should be one of "{0}"'}

    def __init__(self, required=False, default=None, validators=[], sanitizers=[], choices=None):
        self.required = required
        self.default = default
        self.choices = choices
        self.validators = [functools.partial(v, self) for v in self._validators]
        if validators:
            self.validators += validators
        self.sanitizers = [functools.partial(s, self) for s in self._sanitizers]
        if sanitizers:
            self.sanitizers += sanitizers
        super(BaseField, self).__init__()

    @Field.validator
    def validate_required(self, value):
        if value is None:
            if self.required:
                msg = self.ERRORS['required']
                raise FieldValidationError(msg, stop_validation=True) from None
            else:
                raise StopValidation()

    @Field.validator
    def validate_choices(self, value):
        if self.choices is not None:
            if value not in self.choices:
                msg = self.ERRORS['choices'].format(self.choices)
                raise FieldValidationError(msg, stop_validation=True) from None


class Any(BaseField):
    def serialize(self, value):
        return value

    def deserialize(self, value):
        return value


class Integer(BaseField):

    ERRORS = {'not_integer': 'This is not an integer',
              'min': '{0} should be greater than {1}',
              'max': '{0} should be lower than {1}'}

    def __init__(self, min=None, max=None, **kwargs):
        self.min, self.max = min, max
        super(Integer, self).__init__(**kwargs)

    def serialize(self, value):
        return value

    def deserialize(self, value):
        try:
            return int(value)
        except (TypeError, ValueError):
            msg = self.ERRORS['not_integer']
            raise SerializationError(msg) from None

    @Field.validator
    def is_integer(self, value):
        try:
            int(value)
        except (TypeError, ValueError):
            msg = self.ERRORS['not_integer']
            raise FieldValidationError(msg, stop_validation=True) from None

    @Field.validator
    def validate_min(self, value):
        if self.min is None:
            return

        if value < self.min:
            msg = self.ERRORS['min'].format(value, self.min)
            raise FieldValidationError(msg) from None

    @Field.validator
    def validate_max(self, value):
        if self.max is None:
            return

        if value > self.max:
            msg = self.ERRORS['max'].format(value, self.max)
            raise FieldValidationError(msg) from None


class Boolean(BaseField):

    ERRORS = {'not_boolean': 'This is not a valid boolean'}

    def deserialize(self, value):
        if not isinstance(value, bool):
            msg = self.ERRORS['not_boolean']
            raise SerializationError(msg) from None
        return value

    @Field.validator
    def is_boolean(self, value):
        if not isinstance(value, bool):
            msg = self.ERRORS['not_boolean']
            raise FieldValidationError(msg) from None


class Snowflake(BaseField):

    ERRORS = {'not_snowflake': 'This is not a snowflake id'}

    def deserialize(self, value):
        try:
            value = int(value)
        except (TypeError, ValueError):
            msg = self.ERRORS['not_snowflake']
            raise SerializationError(msg) from None

        if value.bit_length() > 64:
            msg = self.ERRORS['not_snowflake']
            raise SerializationError(msg) from None

        return value

    def serialize(self, value):
        if value is not None:
            return str(value)
        else:
            return None

    @Field.validator
    def is_snowflake(self, value):
        try:
            value = int(value)
        except (TypeError, ValueError):
            msg = self.ERRORS['not_snowflake']
            raise FieldValidationError(msg) from None

        if value.bit_length() > 64:
            msg = self.ERRORS['not_snowflake']
            raise FieldValidationError(msg) from None


class String(BaseField):

    ERRORS = {'not_string': 'This ({0}) is not a string',
              'length': '{0} should be {1} characters long',
              'min_length': '{0} length should be higher than {1}',
              'max_length': '{0} length should be lower than {1}',
              'no_match': '{0} doesn\'t match {1}'}

    def __init__(self, convert=False, min_length=-1, max_length=-1, length=-1, regex=None, **kwargs):
        self.regex = regex
        self.min_length = min_length
        self.max_length = max_length
        self.length = length
        self.convert = convert
        super(String, self).__init__(**kwargs)

    @property
    def rx(self):
        if self.regex is None:
            return None

        try:
            return getattr(self, '_rx')
        except AttributeError:
            self._rx = re.compile(self.regex)
            return self._rx

    def deserialize(self, value):
        if not self.convert and not isinstance(value, str):
            msg = self.ERRORS['not_string'].format(value)
            raise SerializationError(msg) from None

        return str(value)

    @Field.validator
    def is_string(self, value):
        if not isinstance(value, str):
            msg = self.ERRORS['not_string'].format(value)
            raise FieldValidationError(msg, stop_validation=True) from None

    @Field.validator
    def validate_min_length(self, value):
        if self.min_length != -1:
            if len(value) < self.min_length:
                msg = self.ERRORS['min_length'].format(value, self.min_length)
                raise FieldValidationError(msg)

    @Field.validator
    def validate_max_length(self, value):
        if self.max_length != -1:
            if len(value) > self.max_length:
                msg = self.ERRORS['max_length'].format(value, self.max_length)
                raise FieldValidationError(msg)

    @Field.validator
    def validate_length(self, value):
        if self.length != -1:
            if len(value) != self.length:
                msg = self.ERRORS['length'].format(value, self.length)
                raise FieldValidationError(msg)

    @Field.validator
    def validate_regex(self, value):
        rx = self.rx
        if rx is not None:
            if not rx.match(value):
                msg = self.ERRORS['no_match'].format(value, rx.pattern)
                raise FieldValidationError(msg) from None


class URL(String):

    URL_RX = re.compile(
        r'http[s]?://'
        r'(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]'
        r'|(?:%[0-9a-fA-F][0-9a-fA-F]))+', re.IGNORECASE,
    )

    MESSAGES = {
        'invalid_url': '{0} is an invalid URL',
    }

    @Field.validator
    def validate_url(self, value):
        if not self.URL_RX.match(value):
            raise FieldValidationError(self.MESSAGES['invalid_url'].format(value)) from None


class List(BaseField):
    ERRORS = {
        'max_length': '{0} length should be lower than {1}',
        'min_length': '{0} length should be higher than {1}',
    }

    def __init__(self, field, max_length=-1, min_length=-1, **kwargs):
        self.field = field
        self.max_length = max_length
        self.min_length = min_length
        super(List, self).__init__(**kwargs)

    def deserialize(self, values):
        if values is None:
            return []

        return [self.field.deserialize(value) for value in values]

    def serialize(self, values):
        if values is None:
            return []

        return [self.field.serialize(value) for value in values]

    @Field.validator
    def validate_min_length(self, value):
        if value is None:
            return

        if self.min_length != -1:
            if len(value) < self.min_length:
                msg = self.ERRORS['min_length'].format(value, self.min_length)
                raise FieldValidationError(msg)

    @Field.validator
    def validate_max_length(self, value):
        if value is None:
            return

        if self.max_length != -1:
            if len(value) > self.max_length:
                msg = self.ERRORS['max_length'].format(value, self.max_length)
                raise FieldValidationError(msg)

    @Field.validator
    def validate_elements(self, elems):
        for elem in elems:
            self.field.validate(elem)

    @Field.sanitizer
    def sanitize_elements(self, elems):
        return [self.field.sanitize(e) for e in elems]


class Dict(BaseField):
    def __init__(self, field, key=None, to_dict=True, **kwargs):
        self.field = field
        self.key = key if callable(key) else lambda e: getattr(e, key)
        self.to_dict = to_dict
        super(Dict, self).__init__(**kwargs)

    def deserialize(self, elems):
        if elems is None:
            return dct

        if type(elems) is dict:
            return {k: self.field.deserialize(v) for k, v in elems.items()}

        lst = [self.field.deserialize(elem) for elem in elems]
        return {self.key(e): e for e in lst}

    def serialize(self, elems):
        if elems is None:
            value = {}
        else:
            value = {k: self.field.serialize(v) for k, v in elems.items()}

        if not self.to_dict:
            value = list(value.values())

        return value

    @Field.validator
    def validate_elements(self, elems):
        for elem in elems.values():
            self.field.validate(elem)

    @Field.sanitizer
    def sanitize_elements(self, elems):
        return {k: self.field.sanitize(v) for k, v in elems.items()}


class ModelField(BaseField):
    def __init__(self, model, **kwargs):
        self.model = model
        super(ModelField, self).__init__(**kwargs)

    def deserialize(self, value):
        if value is None:
            return value
        if isinstance(value, self.model):
            return value

        return self.model(**value)

    def serialize(self, value):
        if value is None:
            return None

        return value.serialize()

    def validate(self, value):
        if value:
            return value.validate()

    def sanitize(self, value):
        if value:
            return value.sanitize()

ISO8601_REGEX = re.compile(
    r"""
    (?P<year>[0-9]{4})
    (
        (
            (-(?P<monthdash>[0-9]{1,2}))
            |
            (?P<month>[0-9]{2})
            (?!$)  # Don't allow YYYYMM
        )
        (
            (
                (-(?P<daydash>[0-9]{1,2}))
                |
                (?P<day>[0-9]{2})
            )
            (
                (
                    (?P<separator>[ T])
                    (?P<hour>[0-9]{2})
                    (:{0,1}(?P<minute>[0-9]{2})){0,1}
                    (
                        :{0,1}(?P<second>[0-9]{1,2})
                        ([.,](?P<second_fraction>[0-9]+)){0,1}
                    ){0,1}
                    (?P<timezone>
                        Z
                        |
                        (
                            (?P<tz_sign>[-+])
                            (?P<tz_hour>[0-9]{2})
                            :{0,1}
                            (?P<tz_minute>[0-9]{2}){0,1}
                        )
                    ){0,1}
                ){0,1}
            )
        ){0,1}  # YYYY-MM
    ){0,1}  # YYYY only
    $
    """, re.VERBOSE
)
class DateTime(BaseField):

    MESSAGES = {
        'unknown_type': 'Unknown type (supported types: str (ISO8601), int (timestamp))',
        'unknown_format': 'Unknown format (supported format: ISO8601)',
    }

    def __init__(self, *args, **kwargs):
        if 'now' in kwargs and kwargs.pop('now') == True:
            kwargs['default'] = datetime.datetime.utcnow()
        return super(DateTime, self).__init__(*args, **kwargs)

    def to_int(self, d, key, default_to_zero=False, default=None, required=True):
        value = d.get(key) or default
        if (value in ["", None]) and default_to_zero:
            return 0
        if value is None:
            if required:
                raise Exception
        else:
            return int(value)

    def parse(self, datestring):
        """
        Source: https://bitbucket.org/micktwomey/pyiso8601
        """
        m = ISO8601_REGEX.match(datestring)
        if not m:
            raise SerializationError(self.MESSAGES['unknown_format'])

        groups = m.groupdict()

        tz = datetime.timezone.utc

        groups["second_fraction"] = int(Decimal("0.%s" % (groups["second_fraction"] or 0)) * Decimal("1000000.0"))

        try:
            return datetime.datetime(
                year=self.to_int(groups, "year"),
                month=self.to_int(groups, "month", default=self.to_int(groups, "monthdash", required=False, default=1)),
                day=self.to_int(groups, "day", default=self.to_int(groups, "daydash", required=False, default=1)),
                hour=self.to_int(groups, "hour", default_to_zero=True),
                minute=self.to_int(groups, "minute", default_to_zero=True),
                second=self.to_int(groups, "second", default_to_zero=True),
                microsecond=groups["second_fraction"],
                tzinfo=tz,
            )
        except Exception as e:
            raise SerializationError(self.MESSAGES['unknown_format'])

    def serialize(self, value):
        if value:
            return value.isoformat()
        return None

    def deserialize(self, value):
        if value is None:
            return None

        if type(value) == datetime.datetime:
            return value

        if type(value) == str:
            return self.parse(value)

        if type(value) == int:
            return datetime.datetime.fromtimestamp(value)

        raise SerializationError(self.MESSAGES['unknown_format'])

