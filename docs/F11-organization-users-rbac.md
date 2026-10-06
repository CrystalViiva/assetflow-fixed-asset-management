# F11 organization, users and RBAC administration

## Contract

The existing `Organization`, `Department`, `Location`, and custom email-based
`User` models are unchanged. The organization code/name and legal profile do
not have a write endpoint. Tenant scope is taken from the authenticated
administrator's `User.organization`; organization IDs in write payloads are
rejected. Department and location codes remain unique per organization.

F11 adds paginated, searchable Django APIs under `/api/v1/admin/`:

- `departments/` and `departments/{uuid}/`: list/create and read/update.
- `locations/` and `locations/{uuid}/`: list/create and read/update.
- `users/` and `users/{integer}/`: list/create and read/update.

There are no delete endpoints. Departments and locations can be marked
inactive without breaking historical references. Department writes accept
name, code and active state. Location writes accept name, code, address, city,
state, country and active state. Updating location descriptive fields does
not move an asset; placement changes remain a transfer workflow.

User records expose only email, organization role, department reference/name,
active state, creation time and last-login time. There is no display-name
field in the current model. Creation requires an initial password; Django
validates and hashes it with `set_password`. No invite email is sent. Password
is write-only and is absent from responses and audit changes. Email is
normalized and immutable after creation. There are no password reset or
credential viewing features here.

## Administration policy

Only an authenticated, active, non-superuser user with role `ADMIN` and an
organization can call the administrative APIs. This is enforced in Django
for reads and writes. `ASSET_MANAGER`, `ACCOUNTANT`, `DEPARTMENT_MANAGER`, and
`EMPLOYEE` cannot use them. Platform superusers and Django staff are not
tenant role controls and are deliberately excluded from this tenant API.

An administrator can create and assign any of the five organization roles,
including another `ADMIN`. Administrators cannot edit their own role,
department or active state. The final active administrator cannot be
demoted/deactivated. A user department must be active and belong to the
authenticated user's organization. User and reference object querysets are
tenant-scoped, so foreign UUID/ID lookups return not found. Strict serializers
reject organization, `is_staff`, `is_superuser`, groups, password hash and
other unsupported fields.

Deactivating a user does not revoke already-issued JWT bytes. SimpleJWT checks
the current user record during authentication, so subsequent requests reject
an inactive account under the configured user-authentication rule; token
expiry and authentication behavior remain backend-controlled. F11 forbids
self role/department/active-state changes, so the current administrator's
cached role is not mutated through this interface.

The role list in the UI is informational, not a permission matrix. Effective
permissions also depend on object, department and workflow rules in Django.
F11 does not provision tenants, subscriptions or billing.

## Audit

Writes create immutable F10 AuditLog records in the same database transaction
as the domain write:

- `DEPARTMENT_CREATED`, `DEPARTMENT_UPDATED`
- `LOCATION_CREATED`, `LOCATION_UPDATED`
- `USER_CREATED`, `USER_ADMIN_UPDATED`

User updates capture safe role, department and active-state changes. User
creation records email, role and department only. Passwords are never placed
in audit data; the audit service also redacts credential-like keys. React
does not create audit rows. F10 Audit Log displays these backend events.

## Frontend behavior

The Django-mode Departments, Locations, and Users & Roles routes use strict
DTO parsers, a dedicated repository, TanStack Query keys scoped by user and
session generation, and server-side search/pagination. Administrative
mutations have retries disabled. After a lost response, the repository checks
the authoritative object or stable email/code identity; if state cannot be
proved, it reports uncertainty instead of replaying the write. Successful or
uncertain writes invalidate only organization-admin and reference-data
queries. Asset/accounting state is not invalidated. The mock routes remain
separate and are used only in mock mode.

Passwords use a password input and are not stored in query state, URLs or
logs or TanStack mutation variables. The request uses a short-lived action
outside the mutation cache, and the form clears after submission. The initial password must be shared
with the recipient through an external secure process; F11 does not send it.
The server never echoes it.

## Validation and smoke

The disposable smoke is:

```powershell
& .\venv\Scripts\python.exe scripts/f1-smoke.py --f11
```

It creates a randomly named PostgreSQL database, runs TypeScript through
authenticated HTTP into Django/PostgreSQL, and drops only that database.
The smoke creates a department, location and user; changes role/department
and active state; checks custodian reference visibility; inspects F10 audit
events and credential omission; rejects lower-role, self-mutation,
organization-spoofing, privileged-field and foreign-tenant requests; and
confirms a location edit neither moved an asset nor created transfer history.
No application database or persistent runtime files are used.

There are no F11 migrations. The UI does not provide organization profile
editing, arbitrary Django permission/group editing, invitations, password
resets, user deletion, or tenant provisioning. User lookup is paginated;
department choices reuse the existing reference repository's validated,
server-paginated fetch of all organization departments.
