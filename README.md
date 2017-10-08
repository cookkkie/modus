# Modus

A simple modeling python lib with validation and serialization.

# Examples

```py
from modus import Model
from modus.fields import Integer, String, Boolean, ModelField

class User(Model):
    id = Snowflake(required=True)
    username = String(required=True)
		password = String(required=True)
		bio = String()

class Tweet(Model):
    id = Snowflake(required=True)
		content = String()
		author = ModelField(User)
		likes = List(ModelField(User))

# Instantiating a user
user1 = User(id=1, username="cookkkie", password=1337, bio="hey!")

# Validating a user (throws a ValidationError if not validated)
user1.validate()
```

