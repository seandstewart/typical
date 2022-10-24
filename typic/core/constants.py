import inspect


class empty:
    def __bool__(self):
        return False


DEFAULT_ENCODING = "utf-8"
ORIG_SETTER_NAME = "__setattr_original__"
POSITIONAL_ONLY = inspect.Parameter.POSITIONAL_ONLY
POSITIONAL_OR_KEYWORD = inspect.Parameter.POSITIONAL_OR_KEYWORD
KEYWORD_ONLY = inspect.Parameter.KEYWORD_ONLY
RETURN_KEY = "return"
SCHEMA_NAME = "__json_schema__"
SELF_NAME = "self"
SERDE_ATTR = "__serde__"
SERDE_FLAGS_ATTR = "__serde_flags__"
TOO_MANY_POS = "too many positional arguments"
TYPIC_ANNOS_NAME = "__typic_annotations__"
VAR_POSITIONAL = inspect.Parameter.VAR_POSITIONAL
VAR_KEYWORD = inspect.Parameter.VAR_KEYWORD
KWD_KINDS = {VAR_KEYWORD, KEYWORD_ONLY}
POS_KINDS = {VAR_POSITIONAL, POSITIONAL_ONLY}
NULLABLES = (None, Ellipsis, type(None), type(Ellipsis))
