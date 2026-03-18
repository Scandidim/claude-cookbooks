# EVENT_LOG_PRODUCTION_CANON_v1

**Status:** Approved for phased implementation  
**Decision date:** March 18, 2026  
**Decision owner:** CEO

## Verdict

1. The production pack is strong enough to become the canonical implementation base.
2. The architecture direction is correct.
3. The roadmap is correct.
4. The vertical slice logic is correct.
5. Implementation can start now.

## Keep as Canon

The following assets remain canonical without changes:

1. Event_Log taxonomy
2. Zapier `event_summary` pack
3. ANDON workflow
4. Tasks table schema
5. Integration blueprint

## Add Before Production

### 1) Dedupe Rule

Add `event_dedupe_key` with recommended pattern:

`source_entity_id + event_type + normalized_timestamp_bucket`

### 2) Idempotency Rule

Before creating an `Event_Log` record:

1. Check if the same `event_dedupe_key` already exists.
2. If it exists, skip create.
3. If it does not exist, create record.

### 3) Resolution Ownership

Add the following fields to `Event_Log`:

- `resolution_owner`
- `resolution_deadline`
- `resolution_note`

## Canonical Launch Order

1. Finalize Tasks table
2. Launch `TASK_CREATED` automation
3. Launch `TASK_STATUS_CHANGED` automation
4. Launch `HEALTH_SNAPSHOT_GENERATED` automation
5. Launch ANDON `blocked_48h` rule

## Do Not Do Yet

1. Launch all CORE-15 automations at once
2. Start with overcomplex Telegram logic
3. Add too many source tables in the first phase
4. Overdesign dashboards before event quality is stable

## Week-1 Success Criteria

1. Task creation logs correctly
2. Task status changes log correctly
3. No duplicate events
4. `event_summary` is always populated
5. One Health Snapshot per day
6. One test ANDON lifecycle completed

## Final CEO Decision

Use this document as **EVENT_LOG_PRODUCTION_CANON_v1** and proceed with phased implementation immediately.
