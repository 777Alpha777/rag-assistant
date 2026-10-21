# Data retention and privacy

## Retention periods

Order and payment records are kept for five years because of accounting
requirements. Application logs are kept for 30 days. Access logs are kept for
90 days. Analytics events are aggregated after 13 months and the raw events are
deleted.

Backups follow the same schedule as the data they contain: a backup never keeps
data longer than the original system is allowed to keep it.

## Personal data

Personal data is limited to what is needed to fulfil an order: name, contact
details and delivery address. Passwords are stored only as Argon2 hashes.
Payment card data never reaches our services — the payment provider returns a
token and that token is what we store.

Data that is not needed for a stated purpose is not collected "just in case".
A new field containing personal data requires a privacy review before release.

## Deletion requests

A customer can request deletion of their personal data. The request is verified,
then processed within 30 days. Order records required by accounting law are
anonymised rather than deleted: personal fields are replaced with placeholders,
while the financial part of the record stays intact.

Every deletion request is logged with the request date, the completion date and
the legal basis for anything that was retained.

## Access control

Access to production data is granted per request with an expiry date of maximum
seven days. Standing access is limited to the platform team. Every access to
production databases is logged and reviewed monthly by the data owner.
