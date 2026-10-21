# API guidelines

## Versioning

Public APIs are versioned in the path, for example /api/v1/orders. A new major
version is created only for breaking changes. Adding a field, adding an optional
request parameter or adding a new endpoint is not a breaking change and goes into
the current version.

Deprecated endpoints keep working for at least six months after the deprecation
notice. The notice is sent to every registered API consumer, and the endpoint
returns a Deprecation header with the sunset date.

## Idempotency

Any endpoint that creates a resource accepts an Idempotency-Key header. The client
generates the key once per logical operation and repeats it on retries. The server
stores the key together with the response for 24 hours: a repeated request returns
the stored response instead of creating a duplicate.

This matters most for payments and order creation, where a network timeout leaves
the client unsure whether the operation succeeded.

## Pagination

Collections use limit and offset pagination with a hard maximum limit of 100 items
per page. Responses include total, limit and offset so the client can render a
pager without extra requests.

For collections that change frequently, cursor pagination is preferred: an opaque
cursor points to the last seen item and is stable under inserts.

## Errors

Errors use a single shape: a detail object with a machine-readable type, a
human-readable message and, where relevant, the conflicting field. HTTP status
codes are used literally: 400 for validation, 401 for missing credentials,
403 for insufficient permissions, 404 for a missing resource, 409 for a conflict
such as insufficient stock, and 422 only when the payload is syntactically valid
but semantically rejected.
