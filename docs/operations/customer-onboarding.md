# Managed customer onboarding

Use the deployed Django application and its identified database. Never run customer provisioning against an environment whose owner is unknown. Local validation uses disposable PostgreSQL only.

## Operator bootstrap

On the trusted operator host, run `python manage.py createsuperuser` interactively. Keep the operator outside every organization; enter its password at the prompt, not on the command line. Run `python manage.py enable_platform_operator operator@example.com` for that account. This local command requires an active, unscoped superuser and records an operator event. Tenant administrators cannot enable this capability.

Restrict operator access at the hosting edge to authorized staff and an MFA-protected access gateway/VPN. Application MFA and impersonation are not implemented. Django site administration is an exceptional recovery surface, not the customer administration interface; do not expose it through the public reverse proxy.

## Provision and activate

1. Confirm commercial approval, company name, unique company code, administrator email, currency and IANA timezone.
2. Sign in to the operator console. Submit **Provision a company**. The browser retains an idempotency key for retries. An inactive organization, provisioning record and activation delivery are created atomically. No account password is generated.
3. The worker sends activation mail. For a local captured-email exercise, run `python manage.py deliver_identity_mail`. In production one Beat instance schedules this every 30 seconds.
4. The administrator opens the 48-hour activation link and chooses their own password. Acceptance creates the user and managed subscription and activates the company atomically. Replays are rejected.
5. If the pending link expires, use **Resend pending activation** in the operator console. Previous links are revoked. A suspended company's revoked invitation requires an explicit support review; resending does not bypass suspension.
6. The administrator signs in, opens Settings / Getting started, configures departments and locations, and invites colleagues from Users & Roles.
7. Complete the customer acceptance checklist in the sales kit: representative asset lifecycle, accounting reconciliation, role checks and supported exports.

The equivalent repeatable command is:

```text
python manage.py provision_organization --operator operator@example.com --key <UUID> --name "Customer Company" --code CUSTOMER01 --email admin@customer.example --currency NGN --timezone Africa/Lagos
```

Persist the request UUID in the implementation record. Reusing it with the same details returns the same provisioning record; different details are rejected. The command never prints activation links or passwords.

## Mail and recovery

Configure SMTP host, port, TLS, credentials, verified sender and HTTPS `FRONTEND_BASE_URL`. Staging must use console, file capture or the test backend; no customer mail is sent by staging. Delivery uses a database outbox with up to eight delayed retries. SMTP can duplicate a message after a crash, but its activation/reset link remains single-use. Inspect delivery counts in platform health; only exception types are stored. Never copy mail bodies or tokens into support tickets.

Password recovery returns the same public response for known and unknown addresses. Reset links expire in one hour; a successful reset or password change invalidates existing access and refresh tokens. Sign out also revokes the user's other sessions when the API is reachable. Local credentials are cleared even if the network is unavailable.

## Support, suspension and retention

The operator console exposes tenant status, subscription status, lead status and health metadata. It does not provide tenant asset browsing or impersonation. Suspension requires a reason, records it in the tenant audit, rejects existing JWT sessions on their next request, revokes open invitations, and retains records. Resuming does not grant a new subscription or reactivate a revoked invitation.

Before offboarding, arrange authorized CSV/JSON report exports while the customer can access the workspace. Full evidence/database export requires the agreed operator process. Record retention, legal holds, backup expiry and customer authorization. There is no destructive tenant-deletion command.

Closed lead retention review is separate from customer data:

```text
python manage.py review_lead_retention --operator operator@example.com --days 90
```

This is a dry run. Only after policy/hold review, adding `--anonymize --confirm ANONYMIZE_CLOSED_ENQUIRIES` removes contact information from eligible closed enquiries and records the operation. Backup retention still applies. Do not automate this before the retention policy is approved.
