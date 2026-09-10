# Vybe Rebuild Parity Matrix

This file tracks the original Open Wearables platform against the Vybe rebuild so no important subsystem is silently dropped.

| Subsystem | Open Wearables | Vybe target | Status |
|---|---|---|---|
| Canonical health evidence | Normalized provider records/timeseries | Immutable evidence with provenance, quality, lineage | BUILT |
| Provider abstraction | Strategy object coupled to repositories/Celery | Transport/normalization contracts independent of infrastructure | BUILT FOUNDATION |
| Provider priority | Global provider/device priority | Metric-aware resolution with quality/confidence | BUILT FOUNDATION |
| Ingestion modes | Pull, webhook, SDK, import | Source-neutral ingestion envelopes | BUILT |
| Idempotency | Provider-specific handling | Deterministic cross-transport idempotency | BUILT |
| Historical sync | Celery/provider-specific | Durable checkpoints + provider execution | IN PROGRESS |
| Live sync | Poll/webhook/provider-specific | Verified webhook/SDK/device event pipeline | IN PROGRESS |
| Webhook signatures | Provider-specific | Shared verification boundary + provider verifier | TODO |
| Retry/backoff | Celery/task specific | Explicit retry policy + terminal/dead-letter state | TODO |
| OAuth | Provider-specific OAuth templates | Application-scoped provider connections + token vault boundary | TODO |
| API keys | Plain key as DB identifier | Hashed application-scoped credentials + prefix + scopes + rotation | IN PROGRESS |
| Developer identity | Developer accounts | Organization -> application -> credential ownership | IN PROGRESS |
| Multi-tenancy | Single organization deployment | Explicit tenant/application isolation | TODO |
| Database | PostgreSQL/SQLAlchemy | PostgreSQL adapter behind core store contracts | TODO |
| Migrations | Alembic | Alembic, isolated Vybe schema | TODO |
| Data refinery | Provider mapping | Normalize, validate, dedup, conflict detect, preserve rejects | BUILT FOUNDATION |
| Longitudinal model | Event/timeseries records | Evidence graph/timeline | BUILT FOUNDATION |
| Baselines | Limited algorithm services | Replaceable deterministic derivation layer | BUILT FOUNDATION |
| AI assistant | Roadmap/partial | Bounded evidence retrieval + tool-driven reasoning | TODO |
| MCP | Separate server | Controlled developer/agent tools over public contracts | TODO |
| Health AI context | Mostly direct data access | Context compiler; never unrestricted DB dump | BUILT FOUNDATION |
| Mobile HealthKit | Separate iOS SDK | Commercial SDK adapter | TODO |
| Health Connect/Samsung | Separate Android SDK | Commercial SDK adapter | TODO |
| Garmin | Provider implementation | Rebuild provider adapter | TODO |
| Oura | Provider implementation | Rebuild provider adapter | TODO |
| Fitbit | Provider implementation | Rebuild provider adapter | TODO |
| Polar | Provider implementation | Rebuild provider adapter | TODO |
| Suunto | Provider implementation | Rebuild provider adapter | TODO |
| Strava | Provider implementation | Rebuild provider adapter | TODO |
| Ultrahuman | Provider implementation | Rebuild provider adapter | TODO |
| Withings/other sources | Provider-dependent | Evaluate against product value | TODO |
| FHIR/clinical | Not core | FHIR ingestion boundary | TODO |
| Audit logs | Partial operational logs | Immutable security/data-access audit events | TODO |
| Consent | Limited | Explicit grants, purpose and revocation | TODO |
| Export/deletion | Platform-specific | Tenant/user data lifecycle APIs | TODO |
| Retention | Deployment concern | Configurable retention policy | TODO |
| Encryption | Infrastructure concern | Key-management boundary; encrypted secrets/tokens | TODO |
| Rate limits | Endpoint/provider dependent | Per-app API quotas + provider rate policies | TODO |
| Observability | Structured logs/Sentry | Structured traces, metrics, sync diagnostics | TODO |
| Dead-letter handling | Task dependent | Explicit failed-ingestion queue/state | TODO |
| Developer portal | React portal | Vybe developer console | TODO |
| SDK licensing boundary | Open-source platform | Commercial public SDK, proprietary engine | BUILT FOUNDATION |
| Raw hardware/firmware | N/A | Never exposed through commercial SDK | HARD CONSTRAINT |
| VibeBand integration | N/A | Future adapter only after contract validation | DEFERRED — DO NOT TOUCH |
| CI | Existing backend/frontend CI | Isolated Vybe core CI + integration suites | BUILT FOUNDATION |
| Load/security tests | Limited | Required before production | TODO |

## Rebuild rule

A subsystem is not considered complete because a class exists. `BUILT` means its invariant is represented in code and tests. Production adapters, persistence, security review and load validation are tracked separately.
