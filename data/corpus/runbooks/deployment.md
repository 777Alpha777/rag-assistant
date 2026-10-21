# Deployment and rollback

## Deployment pipeline

Every service is deployed through the pipeline: build, unit tests, integration
tests, container image, staging deploy, smoke tests, production deploy. A deploy
to production requires a green pipeline and one approving code review. Direct
deploys from a laptop are not permitted for production.

Deployments happen on any weekday during business hours. Friday deploys are
allowed before 15:00 only. A deploy that touches the database schema is never
combined with a code deploy in the same release.

## Rollback

The rollback procedure is one command per service and must be rehearsed quarterly.
Target rollback time is under 10 minutes from the decision to the previous
version serving traffic. If a rollback takes longer, it is treated as an incident
and gets a postmortem.

Rolling back a schema change is different from rolling back code: destructive
migrations are forbidden, so a rollback only reverts application code while the
new columns stay in place until a later cleanup release.

## Feature flags

Risky changes ship behind a feature flag. The flag owner is the author of the
change, and the flag is removed within two weeks after reaching 100% of traffic.
Flags older than 30 days without an owner are deleted during the monthly cleanup.

A feature flag is not a substitute for testing, and it is not a substitute for
monitoring: every flag rollout has a metric that shows whether the change is
healthy.

## Database migrations

Migrations run automatically during the deploy step, before the new application
version starts. Each migration must be backward compatible with the previous
release for at least one deploy cycle, so that a rollback does not break the
database. Long-running migrations on large tables are executed separately with a
maintenance window announced in advance.
