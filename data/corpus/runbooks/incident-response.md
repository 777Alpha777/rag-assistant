# Incident response runbook

## Severity levels

We distinguish four severity levels. Severity 1 means a full outage or data loss
affecting customers: checkout is down, orders are not being created, payments are
failing. Severity 2 is a degraded core flow — for example, order creation works
but catalogue search returns stale data. Severity 3 is a partial degradation with
a workaround. Severity 4 is a cosmetic or single-user issue.

Severity 1 incidents page the on-call engineer immediately, day or night.
Severity 2 is handled during business hours unless the impact grows.
Severity 3 and 4 go to the regular backlog with no paging.

## On-call rotation

The rotation is weekly and starts on Monday at 10:00 local time. The primary
on-call engineer is responsible for acknowledging pages within 15 minutes.
The secondary is the backup and takes over if the primary does not acknowledge
within 15 minutes; the manager is escalated after 30 minutes.

Handover happens every Monday: open incidents, recent changes, noisy alerts and
known risks are reviewed together. A handover without a written summary is not
considered complete.

## Escalation

First escalation goes to the secondary on-call engineer, then to the engineering
manager, then to the incident commander from the platform team. For Severity 1 we
open a dedicated incident channel and assign an incident commander explicitly —
the commander coordinates and communicates, and does not debug.

Customer communication for Severity 1 starts within 30 minutes, even if the cause
is still unknown. An update without a root cause is better than silence.

## Postmortems

Every Severity 1 and Severity 2 incident gets a blameless postmortem within five
working days. The document describes the timeline, the impact, the contributing
factors and the action items with owners and deadlines. Action items are tracked
in the backlog like regular work, not as a separate wish list.

A postmortem that ends with "be more careful" is considered incomplete: the goal
is a change in systems or process, not a promise to concentrate harder.
