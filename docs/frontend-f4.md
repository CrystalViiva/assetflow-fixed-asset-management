# F4 — Assignments, Custody and Transfers

F4 connects Django mode to the existing assignment and transfer domain APIs. The Django backend remains authoritative for both workflows. Mock mode continues to use the demo repositories and legacy screens.

## Domain boundary

An assignment is a custody episode: an asset, optional tenant user, assigned timestamp, optional return timestamp and actor, notes, and department/location snapshots recorded when assigned. Only one active assignment may exist per asset. A return closes the episode; it does not delete history or alter asset department/location. The assignment endpoint accepts an integer `assigned_to_id`; department and location are omitted by the F4 client so the service snapshots current asset placement.

A transfer is a separate placement workflow. Django derives and stores the source department/location while locking the asset. The client submits an asset UUID, required destination department and location UUIDs, reason and optional notes. The current state machine is `REQUESTED → APPROVED → COMPLETED`, with `REQUESTED → REJECTED` and `REQUESTED → CANCELLED` terminal paths. Approval does not change placement. Completion atomically changes the Asset's department/location and records the completion actor and audit event. It does not change assignment/custody. A partial unique constraint permits one open (`REQUESTED` or `APPROVED`) transfer per asset.

## API and access

- Assignments: `GET/POST /api/v1/assets/assignments/`, detail reads, and `POST /api/v1/assets/assignments/{id}/return/`. List filters include `asset`, `assigned_to`, `department`, `location`, and `active`; records use standard pagination.
- Transfers: `GET/POST /api/v1/assets/transfers/`, detail reads, and the `approve`, `reject`, `cancel`, and `complete` POST actions. Filters include asset, status, source and destination departments/locations, with search and ordering.
- Custodians: `GET /api/v1/custodians/` is a new paginated, read-only, organization-scoped reference for active users. Only ADMIN and ASSET_MANAGER (or a superuser) can discover the list. Its allowlisted fields are integer ID, email, role and nullable department ID/name. A malformed cross-organization user/department relation is represented with null department fields. No password, security or unrelated profile fields are exposed.
- Existing tenant-scoped `/departments/` and `/locations/` endpoints provide transfer destinations.

Assignment/transfer reads require authentication and organization membership. ADMIN and ASSET_MANAGER can mutate workflows. All user roles can read within endpoint-defined scope; department managers see their department's assignment/transfer scope, and employees see their own custody and currently assigned assets' transfers. The API enforces these rules and tenant ownership independently of UI controls. Service calls lock asset/workflow rows, validate organization-owned references and legal state, and write audit events transactionally.

## Frontend behavior

Explicit DTO parsers reject malformed UUIDs, timestamps, null relation mismatches and unknown transfer states. Queries and mutations use the F1 session/user-generation query-key scope. API pagination is fully collected with duplicate and count checks. Django mode never falls back to mock workflow data.

The Assignments screen separates active custody and returned history, displays the assignment's placement snapshot, lets asset managers assign or return, and refreshes the backend state after writes. The Transfers screen reads actual statuses/history, collects destination references, displays the backend-derived source, and only offers actions valid for the observed status and manager role. Its request form is inline: it keeps the asset and destination context visible while validating the current placement and required references, with fewer modal focus and state transitions. Asset Detail exposes active custodian on Overview plus real Assignments and Transfers history tabs. Asset Register does not fan out detail calls to invent a custodian column; placement is refreshed through its existing asset queries after workflow changes.

Mutations have no automatic retry and buttons are disabled while a mutation is active. An unclear response triggers authoritative assignment/transfer and, after completion, asset reads before the UI describes whether the mutation happened. If those reads fail, the UI says the result is uncertain and does not present a confirmed success. A session change suppresses both reconciliation reads and UI/cache updates from the stale view. Session-generation checks prevent late results from invalidating a later user's cache; assignment changes invalidate assignment queries, transfer changes invalidate transfer queries, and completion also invalidates the current user's asset queries.

## Smoke and validation

Run `python scripts/f1-smoke.py --f4` from the repository root to create a randomly named disposable PostgreSQL database, migrate and seed it, start Django, exercise the TypeScript API workflow, verify database state and audit events, and drop only that generated database. The smoke capitalizes a real test asset, assigns an employee custodian and refetches active custody, requests/approves/completes a transfer while custody remains active, confirms placement is unchanged through assignment/request/approval, confirms only completion moves both destination relations, then returns custody and verifies history and destination placement remain intact. It also refetches the completed transfer and rejects repeated completion.

No assignment/transfer placement rules were moved to the frontend. F4 does not add assignment-level approvals, scheduled transfer dates, waybills, acknowledgements, transfer-level pagination controls, or register custodian aggregation because the backend contract does not expose those concepts. The transfer API supports search, but the operational page currently presents the complete paginated result set for its selected status without a separate text-search control.
