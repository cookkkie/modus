import re
import functools

from modus.field import Field
from modus.exceptions import FieldValidationError, StopValidation, SerializationError


class BaseField(Field):

    ERRORS = {'required': 'This field is required',
              'choices': 'Should be one of {0}'}

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

        if value > self.min:
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

    ERRORS = {'not_string': 'This is not a string',
              'length': '{0} should be {1} characters long',
              'min_length': '{0} length should be higher than {1}',
              'max_length': '{0} length should be lower than {1}',
              'no_match': '{0} doesn\'t match {1}'}

    def __init__(self, min_length=-1, max_length=-1, length=-1, regex=None, **kwargs):
        self.regex = regex
        self.min_length = min_length
        self.max_length = max_length
        self.length = length
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
        if not isinstance(value, str):
            msg = self.ERRORS['not_string']
            raise SerializationError(msg) from None

        return value

    @Field.validator
    def is_string(self, value):
        if not isinstance(value, str):
            msg = self.ERRORS['not_string']
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


class List(BaseField):
    def __init__(self, field, **kwargs):
        self.field = field
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
    def validate_elements(self, elems):
        for elem in elems:
            self.field.validate(elem)

    @Field.sanitizer
    def sanitize_elements(self, elems):
        return [self.field.sanitize(e) for e in elems]


class Dict(BaseField):
    def __init__(self, field, key=None, **kwargs):
        self.field = field
        self.key = key if callable(key) else lambda e: getattr(e, key)
        self.to_dict = kwargs.get('to_dict', True)
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
            value = value.values()

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

