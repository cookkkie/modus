from collections import Iterable

class ValidationError(Exception): pass

class StopValidation(Exception): pass

class FieldValidationError(ValidationError):
    def __init__(self, *errors, stop_validation=False):
        self.errors = list(errors)
        self.stop_validation = stop_validation

        Exception.__init__(self, self.errors)

class ModelValidationError(ValidationError):
    def __init__(self, **kwargs):
        self.errors = kwargs
        Exception.__init__(self, self.errors)
