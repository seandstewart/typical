from __future__ import annotations

import dataclasses
import re
from types import MappingProxyType
from typing import ClassVar, Dict, List, Mapping, Match, Optional, Pattern, Set
from urllib.parse import ParseResult, parse_qs, quote, urlencode, urlparse

from typical.classes import slotted
from typical.types import url
from typical.types.secret import SecretStr

__all__ = ("DSN", "DSNInfo", "DSNValueError")


class DSNValueError(url.NetworkAddressValueError):
    """A generic error indicating the given value is not a valid DSN.

    Inherits from :py:class:`~typic.types.NetworkAddressValueError`.
    """

    pass


@slotted(dict=False, weakref=True)
@dataclasses.dataclass(frozen=True)
class DSNInfo:
    """Detailed information about a D(ata)S(ource)N(ame).

    Can be called directly, generated by casting a :py:class:`str` as :py:class:`DSN`,
    or created with :py:meth:`DSNInfo.from_str`

    Notes:
        DSNs are *technically* a type of network address, but are more strict.
        There's also a semi-standard API for interacting with them,
        thanks to SQLAlchemy, etc. So we have our own `-Info` object which conforms more
        closely with the expected API.

    See Also:
        :py:class:`typical.types.url.NetAddrInfo`
    """

    driver: str
    """The database driver, e.g., `mysql`."""
    username: str
    """The username used for authentication."""
    password: SecretStr
    """The password used for authentication."""
    host: str
    """The host address where the server is located."""
    port: int | str
    """The exposed port to connect to."""
    name: str
    """The database name."""
    qs: str
    """The query-string to pass on to the database."""
    is_ip: bool = False
    """Whether the hostname is a raw IP Address."""
    base: str = dataclasses.field(init=False)
    """The driver, user, password, host, and port, formatted as a fully-qualified DSN."""
    relative: str = dataclasses.field(init=False)
    """The database/schema name and query-string (url-encoded)."""
    address: str = dataclasses.field(init=False)
    """The fully-qualified DSN."""
    address_encoded: str = dataclasses.field(init=False)
    """The fully-qualifed DSN, url-encoded."""
    query: MappingProxyType = dataclasses.field(init=False, hash=False)
    """The query-string parsed into a mapping of field->list[value]."""
    is_default_port: bool = dataclasses.field(init=False)
    """Whether the port for this DSN is the default port for the identified driver."""
    is_private: bool = dataclasses.field(init=False)
    """Whether the DSN points to a private host IP."""
    is_internal: bool = dataclasses.field(init=False)
    """Whether the DSN points to an interal host IP."""

    PATTERN: ClassVar[Pattern] = url.NET_ADDR_PATTERN
    DEFAULT_PORTS: ClassVar[Dict] = url.DEFAULT_PORTS
    PRIVATE_HOSTS: ClassVar[Set[str]] = url.PRIVATE_HOSTS
    INTERNAL_HOSTS: ClassVar[Set[str]] = url.INTERNAL_HOSTS
    INTERNAL_IP_PATTERN: ClassVar[re.Pattern] = url.INTERNAL_IP_PATTERN

    def __post_init__(self):
        object.__setattr__(self, "query", self._get_query())
        object.__setattr__(self, "base", self._get_base())
        object.__setattr__(self, "relative", self._get_relative())
        object.__setattr__(self, "address", self._get_address())
        object.__setattr__(self, "is_default_port", self._get_is_default_port())
        object.__setattr__(self, "is_private", self._get_is_private())
        object.__setattr__(self, "is_internal", self._get_is_internal())

    @classmethod
    def from_str(cls, value: str) -> DSNInfo:
        """Parse & validate a string and generate an instance of :py:class:`DSNInfo`."""
        match: Optional[Match] = cls.PATTERN.match(value)
        if not match or not value:
            raise DSNValueError(f"{value!r} is not a valid DSN.")
        scheme, host = match["scheme"] or "", match["host"] or ""
        if not scheme or (scheme != "sqlite" and not host):
            raise DSNValueError(f"{value!r} is not a valid DSN, missing driver|host.")

        port: int | str = int(match["port"] or 0)
        parsed: ParseResult = urlparse(match["relative"] or "")
        name = parsed.path
        if scheme == "sqlite":
            port = ""
            name = host or name
            host = ""
        if port == 0 and cls.DEFAULT_PORTS[scheme]:
            port = cls.DEFAULT_PORTS[scheme].copy().pop()
        if port == 0:
            raise DSNValueError(
                f"{value!r} is not a valid DSN, couldn't determine port."
            )
        return cls(
            driver=scheme,
            host=host,
            username=match["username"] or "",
            password=SecretStr(match["password"] or ""),
            qs=parsed.query,
            port=port,
            name=name,
            is_ip=bool(match["ipv4"] or match["ipv6"]),
        )

    def _get_base(self) -> str:
        """The 'base' of this DSN.

        Includes driver, user/pass, host, & port"""
        url = f"{self.driver}://"
        if self.username or self.password:
            url += f"{self.username}:{self.password.secret}@"
        url += self.host
        if self.port:
            url += f":{self.port}"
        return url

    def _get_relative(self):
        """The 'relative' portion of this DSN.

        Includes the database/schema name and query-string.
        """
        return f"{self.name}{urlencode(self.query)}"

    def _get_address(self) -> str:
        """The fully-qualified address.

        If this instance was generated from a string, it will match the string exactly,
        EXCEPT if a port wasn't provided in the original string. In those cases, we try
        to determine the appropriate port based upon the driver name provided.
        """
        return f"{self.base}{self.relative}"

    def _get_address_encoded(self) -> str:
        """The fully-qualified address, encoded."""
        return quote(self.address)

    def _get_query(self) -> Mapping[str, List[str]]:
        """The query-string, parsed into a mapping of key -> [values, ...]."""
        return MappingProxyType(parse_qs(self.qs) if self.qs else {})

    def _get_is_default_port(self) -> bool:
        """Whether or not the port is the default for the SQL dialect."""
        defaults = self.DEFAULT_PORTS[self.driver.split("+")[0]] | {0}
        return self.port in defaults

    def _get_is_private(self) -> bool:
        """Whether the host is a private host, i.e., 'localhost'."""
        return self.host in self.PRIVATE_HOSTS

    def _get_is_internal(self) -> bool:
        """Whether the host provided is an internal IP/DNS.

        Internal IP/DNS addresses aren't necessarily private, hence the distinction.
        """
        return bool(
            self.host in self.INTERNAL_HOSTS
            or (self.is_ip and self.INTERNAL_IP_PATTERN.match(self.host))
        )


class DSN(url.NetworkAddress):
    """A Data Source Name string.

    Detailed information about the DSN string can be looked up via :py:attr:`DSN.info`.

    See Also:
        :py:class:`~typical.types.url.NetworkAddress`

    Examples:
        >>> from typical import types
        >>> dsn = types.DSN("postgresql://user:secret@localhost:5432/mydb")
        >>> dsn
        'postgresql://user:secret@localhost:5432/mydb'
        >>> dsn.info.host
        'localhost'
        >>> dsn.info.is_private
        True
        >>> dsn.info.is_default_port
        True
        >>> dsn.info.username
        'user'
        >>> dsn.info.password  # This has been converted to a secret :)
        ******
        >>> dsn.info.name
        '/mydb'
        >>> dsn.info.driver
        'postgresql'
        >>> import json
        >>> json.dumps([dsn])
        '["postgresql://user:secret@localhost:5432/mydb"]'

    Notes:
        This object inherits from :py:class:`str` and, so is natively JSON-serializable.
    """

    def _getinfo(self) -> DSNInfo:  # type: ignore
        """Get detailed information about your DSN string.

        See Also
        --------
        :py:class:`DSNInfo`
        """
        return DSNInfo.from_str(self)
