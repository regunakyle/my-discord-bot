# Migration Notes

This project uses SQLite in strict mode by default. This means that only the following data types in SQLite are supported:

- INT
- INTEGER
- REAL
- TEXT
- BLOB
- ANY

A important implication is that, all SQLAlchemy `Unicode`, `String`, `DateTime` must use `TEXT` instead.
