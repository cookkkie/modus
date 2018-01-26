from modus.exceptions import FieldValidationError, ModelValidationError
from modus.field import Field
from copy import deepcopy


class MetaModel(type):
    def __new__(mcl, name, bases, attrs):
        fields = {}
        validators = []

        for base in bases:
            if hasattr(base, '_fields'):
                fields.update(deepcopy(base._fields))
            if hasattr(base, '_validators'):
                validators += deepcopy(base._validators)

        for name, value in attrs.items():
            if isinstance(value, Field):
                field_name = name
                field = deepcopy(value)
                field.name = field_name
                fields[field.name] = field

            if getattr(value, 'is_validator', False):
                validators.append(value)

        attrs['_fields'] = fields
        attrs['_validators'] = validators

        cls = type.__new__(mcl, name, bases, attrs)
        cls.__name__ = attrs['__qualname__']

        return cls


class Model(metaclass=MetaModel):
    def __init__(self, **kwargs):
        self.__class__.deserialize(kwargs, self)

    @classmethod
    def validator(cls, f):
        f.is_validator = True
        return f

    @classmethod
    def deserialize(cls, data, instance=None):
        instance = instance or cls()
        for field_name, field in cls._fields.items():
            value = data.get(field.name)
            if value is None and hasattr(field, 'default'):
                if callable(field.default):
                    value = field.default()
                else:
                    value = field.default
            if value is not None:
                value = field.deserialize(value)
            setattr(instance, field_name, value)
        return instance

    def update(self, **kwargs):
        cls = self.__class__
        for field_name, field in cls._fields.items():
            if field_name not in kwargs:
                continue
            value = kwargs.get(field_name)
            if value is not None:
                value = field.deserialize(value)
            setattr(self, field_name, value)
        return self

    def serialize(self):
        dct = {}
        fields = self.__class__._fields
        for field_name, field in fields.items():
            value = getattr(self, field.name, None)
            if value is not None:
                value = field.serialize(value)
            dct[field_name] = value
        return dct

    def sanitize(self):
        for field in self._fields.values():
            value = getattr(self, field.name)
            value = field.sanitize(value)
            setattr(self, field.name, value)
        return self

    def validate(self):
        validation_errors = {}
        for field in self._fields.values():
            try:
                value = getattr(self, field.name)
                field.validate(value)
            except (FieldValidationError, ModelValidationError) as e:
                validation_errors[field.name] = e.errors

        if validation_errors:
            raise ModelValidationError(**validation_errors)

        for validator in self._validators:
            validator(self)

    def fields(self):
        return self.__class__._fields.values()

    def keys(self):
        return (field.name for field in self.fields())

    def items(self):
        return ((field.name, getattr(self, field.name, None)) for field in self.__class__._fields.values())

    def values(self):
        return (getattr(self, field.name, None) for field in self.__class__._fields.values())

    def __str__(self):
        return self.__repr__()

    def __repr__(self):
        return '<%s object at 0x%s>' % (self.__class__.__name__, id(self))

