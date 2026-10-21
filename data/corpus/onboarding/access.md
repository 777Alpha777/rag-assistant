# Access and onboarding

## Accounts

A new engineer receives a corporate account on the first day. Access to internal
systems is requested through the access portal, not through chat messages. Each
request requires a justification and an approver: the team lead for development
systems, the platform team for infrastructure.

Access is granted for a named role, not for a person, and is reviewed every
quarter. Accounts of people who changed teams are adjusted within five working
days; accounts of people who left are disabled on the last working day.

## VPN and network

The corporate VPN is required to reach internal services from outside the office.
The VPN profile is issued per device; sharing credentials is forbidden. A lost
device is reported to the security team immediately so the certificate can be
revoked.

Production network access is separated from the corporate network. Reaching a
production database requires an additional jump host and a ticket that names the
time window.

## Production access

Read-only production access can be granted for up to seven days through the
access portal. Write access to production requires the approval of two people:
the service owner and a member of the platform team. Every write session is
recorded and reviewed.

Break-glass access exists for incidents: it is time-limited, it pages the
security channel, and it must be justified in the incident report afterwards.

## Development environment

Local development uses docker compose and seeded anonymised data. Connecting a
developer machine to a production database is prohibited, including read-only
connections. If a bug cannot be reproduced without production data, the data is
exported, anonymised and attached to the task.
