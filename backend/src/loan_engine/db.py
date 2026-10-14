import os
import ssl

import pg8000.native

_connection: pg8000.native.Connection | None = None


def connect() -> pg8000.native.Connection:
    return pg8000.native.Connection(
        host=os.environ["DB_HOST"],
        port=int(os.environ.get("DB_PORT", "5432")),
        database=os.environ["DB_NAME"],
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
        ssl_context=ssl.create_default_context() if os.environ.get("DB_SSL") == "true" else None,
    )


def shared_connection() -> pg8000.native.Connection:
    """Reuse one connection across warm Lambda invocations."""
    global _connection
    if _connection is None:
        _connection = connect()
    else:
        try:
            _connection.run("select 1")
        except pg8000.native.InterfaceError:
            _connection = connect()
    return _connection
