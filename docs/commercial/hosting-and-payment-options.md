# Hosting and recurring-payment options

Reviewed 8 October 2026 against official provider documentation. Prices and account eligibility can change; recheck provider pages before committing spend. These are architectural comparisons, not purchases or production validation.

## Hosting shortlist

| Option | Indicative current public price evidence | PostgreSQL/storage and operations | Fit and limitations |
|---|---|---|---|
| Render managed application platform | Public pricing lists a small always-on web/worker compute tier at $7/month each; PostgreSQL is $6/month for 256 MB and $40/month for 2 GB/1 CPU; Key Value is $10/month for 256 MB. A minimal example totals about $30/month before workspace plan, storage/bandwidth, taxes, and email. | Managed services, private networking, custom domain/TLS, paid Postgres logical backups and PITR depending tier; filesystem is ephemeral unless using paid persistent disks. Must use private object storage or paid durable disk for evidence. | Lowest-friction prototype/pilot if region latency and backup/restore behavior meet customer needs. The 256 MB database tier is development-sized; choose capacity based on measured load. See [Render pricing](https://render.com/pricing), [Render Postgres](https://render.com/docs/postgresql), and [web service docs](https://render.com/docs/web-services). |
| DigitalOcean managed PostgreSQL plus container/VM services | Managed PostgreSQL public pricing lists Standard single-node 1 GiB from about $15.15/month; 2 GiB from about $30.45/month. Basic Droplet starts at $4/month for 512 MiB; a 2 GiB/1-vCPU Droplet is $12/month. Object storage, application compute, backups, bandwidth, and any Redis-compatible managed cache add cost. | Database is managed with backup/PITR capabilities depending plan. App can run in App Platform or containers on Droplets; a VM reduces platform abstraction but increases patching, monitoring, TLS, worker, and recovery responsibilities. Use Spaces/private object storage for durable customer artifacts. | More control and a clear managed database option; modest entry database capacity costs more than hobby tiers. One VM is still a single failure domain. Check region availability/latency from Nigerian customer sites. See [PostgreSQL pricing/docs](https://docs.digitalocean.com/products/databases/postgresql/details/pricing/), [managed database pricing](https://www.digitalocean.com/pricing/managed-databases), and [Droplet pricing](https://www.digitalocean.com/pricing/droplets). |

### Recommendation

For a controlled pilot, use a managed application platform and managed PostgreSQL, with private object storage, provider-managed TLS, off-host backups, and explicit web/worker/one-Beat roles. Render is a reasonable first evaluation because its docs describe the Django web service, workers, managed Postgres, TLS/custom domain, and private service networking in one platform. Do not select it without measuring API latency from intended Nigerian customer networks, checking data location and contractual processing terms, setting storage backup policy, and running restore drills. DigitalOcean is the alternative where the team wants more infrastructure control and is prepared to operate more of the stack. Neither option is confirmed as deployed or contracted.

Costs above are component examples, not complete monthly estimates or quotes. They exclude tax, email, private object storage, bandwidth, logs/monitoring, backups beyond included allowance, HA, Redis, and staff operations. Free plans are not appropriate for customer records without checking persistence/expiry and recovery limits; Render's official documentation states free web instances have ephemeral filesystem and free Postgres expires after 30 days.

## Payment-provider shortlist

| Provider | Officially documented capability | Integration consequence |
|---|---|---|
| Paystack | Subscriptions docs describe recurring billing; subscription payment methods include card and Nigerian direct debit. Docs say failed subscription charges are not retried by Paystack. Webhooks document subscription/invoice/charge events and retry behavior. | Strong initial NGN candidate. Application must implement its own failed-payment/grace/reconciliation workflow and verify each event/signature and current merchant eligibility. See [Subscriptions](https://paystack.com/docs/payments/subscriptions/), [webhooks](https://paystack.com/docs/payments/webhooks/), and [recurring charges](https://paystack.com/docs/payments/recurring-charges/). |
| Flutterwave | Payment plan docs describe NGN default currency, card-based recurring subscriptions, provider-managed retries (three retries at 30-minute intervals in the published docs), cancellation/webhooks. Webhook docs describe signature verification; transaction verification docs require checking reference, status, currency and amount. | Plausible alternative and worthy sandbox evaluation. Subscription identity is tied to email; email changes may require cancelling/recreating a provider subscription. Confirm current account eligibility, NGN recurring rails, terms and sandbox/live differences. See [payment plans](https://developer.flutterwave.com/docs/payment-plans-1), [webhooks](https://developer.flutterwave.com/docs/webhooks), and [transaction verification](https://developer.flutterwave.com/docs/transaction-verification). |

### Payment decision

Implement an adapter interface before provider-specific business logic. Paystack is the recommended first sandbox candidate because of its documented NGN direct debit/card support and webhook surface, but its no-retry behavior makes local dunning and subscription state reconciliation mandatory. Do not enable live payment until business registration/merchant approval, sandbox replay tests, refunds/disputes handling, provider webhook secrets, legal text, and reconciliation operations are complete. Never store raw card data or trust checkout redirects.

## Deployment decision gates

1. Obtain current provider quote and check region/data-processing terms.
2. Deploy a staging stack with separate secrets and sandbox credentials.
3. Validate HTTPS, mail delivery, Postgres restore, private file restore, worker failure alerting, and cross-tenant smoke tests.
4. Confirm Nigerian latency from representative networks and customer requirements.
5. Record costs and recovery measures before selecting a paid production plan.
