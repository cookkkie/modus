from modus.utils import get
from modus.exceptions import FieldValidationError, ModelValidationError
from modus.field import Field
from copy import deepcopy


class MetaModel(type):
    def __new__(mcl, name, bases, attrs):
        fields = {}
        new_attrs = {}

        for base in bases:
            if hasattr(base, '_fields'):
                fields.update(deepcopy(base._fields))

        for name, value in attrs.items():
            if isinstance(value, Field):
                field_name = name
                field = deepcopy(value)
                field.name = field_name
                fields[field.name] = field
            else:
                new_attrs[name] = value

        attrs['_fields'] = fields
        return type.__new__(mcl, name, bases, attrs)


class Model(metaclass=MetaModel):
    def __init__(self, **kwargs):
        self.__class__.deserialize(kwargs, self)

    @classmethod
    def deserialize(cls, data, instance=None):
        instance = instance or cls()
        for field_name, field in cls._fields.items():
            value = data.get(field.name)
            if value is None and hasattr(field, 'default'):
                value = field.default
            setattr(instance, field_name, value and field.deserialize(value))
        return instance

    def serialize(self):
        dct = {}
        fields = self.__class__._fields
        for field_name, field in fields.items():
            value = get(self, field.name)
            dct[field_name] = field.serialize(value)
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
