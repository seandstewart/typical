# typical Types

`typical` provides a whole host of useful types for interacting with every-day
web-oriented programming: secrets, emails, DSNs, URLs...

## Secrets

Secrets are important aspects of day-to-day application development. However, most of
the time these are poorly handled and not hidden from simple logging, etc. `typical`
secret types allow you to have your verbose logging without fear of a security risk,
while also making it easy to pass on your secrets (e.g. for authenticating via an
external service).

::: typic.types.secret


## FrozenDict

A hashable, immutable mapping is great for storing run-time configuration without fear
of an irresponsible developer coming along and mutating your global state. (Yes, global
state is evil, but it's often a bit necessary as well.)

::: typic.types.frozendict


## URLs

Oh hey, *another* URL implementation. Yup, I re-invented the wheel. However, these
types are super-powered: they're natively JSON-serializable, immutable, and
initialization is *fast*.

::: typic.types.url


## DSNs

DSNs are network addresses, but they have a slightly different standardized API.

::: typic.types.dsn


## Email

Probably the best implementation of an Email-type there is :snake:.

::: typic.types.email


## Path

This just provides a couple more strict Path objects, which inherit
directly from `pathlib.Path`.

::: typic.types.path

