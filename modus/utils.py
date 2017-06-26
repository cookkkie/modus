def get(obj, attr, default=None):
    try:
        return getattr(obj, attr)
    except AttributeError:
        return default
