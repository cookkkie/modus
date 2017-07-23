from modus.utils import get
from modus.exceptions import FieldValidationError, StopValidation
from copy import deepcopy


class MetaField(type):
    def __new__(mcl, name, bases, attrs):
        validators = []
        sanitizers = []

        for base in bases:
            if hasattr(base, '_validators'):
                validators += deepcopy(base._validators)
            if hasattr(base, '_sanitizers'):
                sanitizers += deepcopy(base._sanitizers)
            if hasattr(base, 'ERRORS'):
                if attrs.get('ERRORS'):
                    attrs['ERRORS'].update(deepcopy(base.ERRORS))
                else:
                    attrs['ERRORS'] = base.ERRORS

        for value in attrs.values():
            if get(value, 'is_validator'):
                validators.append(value)
            if get(value, 'is_sanitizer'):
                sanitizers.append(value)

        attrs['_validators'] = validators
        attrs['_sanitizers'] = sanitizers
        return type.__new__(mcl, name, bases, attrs)


class Field(metaclass=MetaField):
    @classmethod
    def validator(cls, f):
        f.is_validator = True
        return f

    @classmethod
    def sanitizer(cls, f):
        f.is_sanitizer = True
        return f

    def serialize(self, value):
        return value

    def deserialize(self, value):
        return value

    def sanitize(self, value):
        for sanitizer in self.sanitizers:
            value = sanitizer(value)
        return value

    def validate(self, value):
        errors = []

        for validator in self.validators:
            try:
                validator(value)
            except FieldValidationError as e:
                errors += e.errors
                if e.stop_validation:
                    break
            except StopValidation:
                break

        if errors:
            raise FieldValidationError(*errors)

        return True

