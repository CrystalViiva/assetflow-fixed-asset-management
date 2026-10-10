import { useState, type FormEvent } from "react";
import { useQuery } from "@tanstack/react-query";
import { AccountShell } from "./IdentityViews";
import { apiClient } from "../services/authRuntime";
import {
  getBilling,
  getPublicConfig,
  readCheckout,
  formatMinorAmount,
} from "../services/commercial";
import { errorMessage } from "../services/apiError";
import { useAuth } from "../auth/AuthProvider";

const field = "mt-1 block w-full rounded-lg border border-slate-300 p-3";
const button =
  "rounded-lg bg-blue-900 px-4 py-3 font-semibold text-white disabled:opacity-50";
export function SignupView({ verify = false }: { verify?: boolean }) {
  const config = useQuery({
    queryKey: ["public-config"],
    queryFn: getPublicConfig,
  });
  const [email, setEmail] = useState("");
  const [company, setCompany] = useState("");
  const [currency, setCurrency] = useState("NGN");
  const [zone, setZone] = useState("Africa/Lagos");
  const [password, setPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [plan, setPlan] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const token =
    new URLSearchParams(window.location.hash.split("?")[1] ?? "").get(
      "token",
    ) ?? "";
  async function submit(event: FormEvent) {
    event.preventDefault();
    if (busy) return;
    setError("");
    if (verify && password !== confirmation) {
      setError("The passwords must match.");
      return;
    }
    setBusy(true);
    try {
      await apiClient.request(
        verify ? "/auth/signup/verify/" : "/auth/signup/",
        {
          method: "POST",
          authenticated: false,
          body: verify
            ? { token, password, plan_id: plan || config.data?.plans[0]?.id }
            : { email, company_name: company, currency, timezone_name: zone },
        },
      );
      setMessage(
        verify
          ? "Your company is ready. Sign in to begin your trial."
          : "If this address is eligible, a verification email will arrive shortly. Submit again to request a replacement link.",
      );
      setPassword("");
      setConfirmation("");
    } catch (cause) {
      setError(errorMessage(cause));
    } finally {
      setBusy(false);
    }
  }
  return (
    <AccountShell
      title={
        verify
          ? "Verify email & start your trial"
          : "Create your company workspace"
      }
    >
      {config.isPending ? (
        <p role="status">Loading onboarding options…</p>
      ) : config.error ? (
        <p role="alert">{errorMessage(config.error)}</p>
      ) : !config.data?.self_service_enabled ? (
        <p>
          Managed onboarding is available.{" "}
          <a className="underline" href="#contact-sales">
            Contact sales
          </a>{" "}
          to arrange your workspace.
        </p>
      ) : (
        <>
          <p className="mb-5 text-slate-600">
            {verify
              ? "Confirm ownership of your email, choose a trial, and set your password. No card or live charge is required."
              : "We will verify your email before creating an organization or giving access to business records."}
          </p>
          {message && (
            <p role="status" className="mb-4 rounded bg-blue-50 p-3">
              {message}
            </p>
          )}
          {(!message || !verify) && (
            <form onSubmit={submit} className="space-y-4" aria-busy={busy}>
              {verify ? (
                <>
                  <label className="block">
                    Trial plan
                    <select
                      className={field}
                      value={plan || config.data.plans[0]?.id || ""}
                      onChange={(e) => setPlan(e.target.value)}
                    >
                      {config.data.plans.map((p) => (
                        <option key={p.id} value={p.id}>
                          {p.name} · {p.trial_days} days ·{" "}
                          {p.active_users ?? "Unlimited"} users ·{" "}
                          {p.registered_assets ?? "Unlimited"} assets
                        </option>
                      ))}
                    </select>
                  </label>
                  <label className="block">
                    Password
                    <input
                      className={field}
                      type="password"
                      autoComplete="new-password"
                      required
                      minLength={8}
                      maxLength={256}
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                    />
                  </label>
                  <label className="block">
                    Confirm password
                    <input
                      className={field}
                      type="password"
                      autoComplete="new-password"
                      required
                      value={confirmation}
                      onChange={(e) => setConfirmation(e.target.value)}
                    />
                  </label>
                </>
              ) : (
                <>
                  <label className="block">
                    Business email
                    <input
                      className={field}
                      type="email"
                      autoComplete="email"
                      required
                      maxLength={254}
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                    />
                  </label>
                  <label className="block">
                    Company name
                    <input
                      className={field}
                      required
                      maxLength={160}
                      value={company}
                      onChange={(e) => setCompany(e.target.value)}
                    />
                  </label>
                  <label className="block">
                    Accounting currency
                    <select
                      className={field}
                      value={currency}
                      onChange={(e) => setCurrency(e.target.value)}
                    >
                      {["NGN", "USD", "GBP", "EUR", "GHS", "KES", "ZAR"].map(
                        (c) => (
                          <option key={c}>{c}</option>
                        ),
                      )}
                    </select>
                  </label>
                  <label className="block">
                    Timezone
                    <input
                      className={field}
                      required
                      maxLength={64}
                      value={zone}
                      onChange={(e) => setZone(e.target.value)}
                    />
                  </label>
                </>
              )}
              {error && (
                <p role="alert" className="text-rose-700">
                  {error}
                </p>
              )}
              <button
                className={button}
                disabled={
                  busy || (verify && (!token || config.data.plans.length === 0))
                }
              >
                {busy
                  ? "Submitting…"
                  : verify
                    ? "Verify & create workspace"
                    : message
                      ? "Resend verification"
                      : "Send verification email"}
              </button>
            </form>
          )}
        </>
      )}
    </AccountShell>
  );
}

export function BillingView() {
  const { role, generation } = useAuth();
  const billing = useQuery({
    queryKey: ["billing", generation],
    queryFn: getBilling,
    enabled: role === "ADMIN",
  });
  const config = useQuery({
    queryKey: ["public-config"],
    queryFn: getPublicConfig,
    enabled: role === "ADMIN",
  });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [key, setKey] = useState(() => crypto.randomUUID());
  async function action(path: string, body: unknown) {
    if (busy) return;
    setBusy(true);
    setError("");
    setMessage("");
    try {
      await apiClient.request(path, { method: "POST", body });
      await billing.refetch();
      setMessage("Billing status refreshed from the server.");
    } catch (cause) {
      setError(errorMessage(cause));
    } finally {
      setBusy(false);
    }
  }
  async function checkout(planId: string) {
    if (busy) return;
    setBusy(true);
    setError("");
    try {
      const value = readCheckout(
        await apiClient.request("/billing/checkout/", {
          method: "POST",
          body: { plan_id: planId, request_key: key },
        }),
      );
      await billing.refetch();
      setKey(crypto.randomUUID());
      if (
        value.provider === "paystack_test" &&
        value.url.startsWith("https://checkout.paystack.com/")
      )
        window.location.assign(value.url);
      else
        setMessage(
          "Sandbox checkout created. Choose a simulated outcome below. No money will move.",
        );
    } catch (cause) {
      setError(errorMessage(cause));
    } finally {
      setBusy(false);
    }
  }
  const sub = billing.data?.subscription;
  return (
    <main className="mx-auto max-w-5xl space-y-6 p-6">
      <h1 className="text-2xl font-bold">Plan & billing</h1>
      {role !== "ADMIN" ? (
        <p>Billing is available to organization administrators.</p>
      ) : (
        <>
          <p className="rounded border border-slate-300 border-amber-200 bg-amber-50 p-4">
            Payments in this release are sandbox only. Test amounts are not a
            commercial price offer. No live charges are enabled.
          </p>
          {billing.isPending ? (
            <p role="status">Loading subscription…</p>
          ) : billing.error ? (
            <p role="alert">{errorMessage(billing.error)}</p>
          ) : (
            <>
              <section className="rounded-xl border border-slate-200 bg-white p-5">
                <h2 className="font-bold">
                  {sub?.plan.name ?? "Managed service"}
                </h2>
                <p>
                  {sub?.state ?? "Commercial terms managed by your operator"}
                  {sub && !sub.writable && " · Read-only access"}
                </p>
                <p className="mt-2">
                  {billing.data?.usage.active_users} active users ·{" "}
                  {billing.data?.usage.registered_assets} registered assets
                </p>
                {sub && (
                  <>
                    <p>
                      Trial ends:{" "}
                      {sub.trial_ends_at
                        ? new Date(sub.trial_ends_at).toLocaleString()
                        : "—"}
                    </p>
                    <p>
                      Paid period ends:{" "}
                      {sub.period_ends_at
                        ? new Date(sub.period_ends_at).toLocaleString()
                        : "—"}
                    </p>
                    <p>
                      Grace ends:{" "}
                      {sub.grace_ends_at
                        ? new Date(sub.grace_ends_at).toLocaleString()
                        : "—"}
                    </p>
                    <p>Billing contact: {sub.billing_email}</p>
                    {sub.recurring_status && (
                      <p>Recurring test subscription: {sub.recurring_status}</p>
                    )}
                    {sub.provider_setup_pending && (
                      <p role="status">
                        Your payment is recorded. Recurring subscription setup
                        is awaiting provider confirmation. Refresh shortly or
                        contact your operator if this persists.
                      </p>
                    )}
                    <form
                      className="mt-3 flex flex-wrap items-end gap-3"
                      onSubmit={async (e) => {
                        e.preventDefault();
                        const data = new FormData(e.currentTarget);
                        if (busy) return;
                        setBusy(true);
                        try {
                          await apiClient.request("/billing/", {
                            method: "PATCH",
                            body: { email: data.get("email") },
                          });
                          await billing.refetch();
                          setMessage("Billing contact saved.");
                        } catch (cause) {
                          setError(errorMessage(cause));
                        } finally {
                          setBusy(false);
                        }
                      }}
                    >
                      <label>
                        Billing email
                        <input
                          className={field}
                          name="email"
                          type="email"
                          required
                          defaultValue={sub.billing_email}
                        />
                      </label>
                      <button className={button} disabled={busy}>
                        Update contact
                      </button>
                    </form>
                    <button
                      className="mt-5 rounded border border-rose-300 px-4 py-2"
                      disabled={busy || sub.cancel_at_period_end}
                      onClick={() => void action("/billing/cancel/", {})}
                    >
                      {sub.cancel_at_period_end
                        ? "Cancellation recorded"
                        : "Cancel at period end"}
                    </button>
                    <p className="mt-2 text-sm text-slate-500">
                      Trial cancellation is immediate. Cancellation preserves
                      your records for reading and export.
                    </p>
                  </>
                )}
              </section>
              {sub && billing.data?.provider !== "disabled" && (
                <section className="grid gap-4 sm:grid-cols-2">
                  {config.data?.plans.map((plan) => (
                    <article
                      className="rounded-xl border border-slate-200 bg-white p-5"
                      key={plan.id}
                    >
                      <h2 className="font-bold">
                        {plan.name} · v{plan.version}
                      </h2>
                      <p>
                        {plan.active_users ?? "Unlimited"} users /{" "}
                        {plan.registered_assets ?? "Unlimited"} assets
                      </p>
                      <p className="my-3">
                        Sandbox amount: {plan.currency} {plan.monthly_amount}
                      </p>
                      <button
                        className={button}
                        disabled={busy}
                        onClick={() => void checkout(plan.id)}
                      >
                        Start sandbox checkout
                      </button>
                    </article>
                  ))}
                </section>
              )}
              <section className="rounded-xl border border-slate-200 bg-white p-5">
                <h2 className="font-bold">Billing history</h2>
                {billing.data?.history.length === 0 && (
                  <p>No checkout attempts yet.</p>
                )}
                <ul className="divide-y">
                  {billing.data?.history.map((row) => (
                    <li key={row.id} className="space-y-2 py-4">
                      <p>
                        {new Date(row.created_at).toLocaleString()} ·{" "}
                        {row.status} · {row.currency}{" "}
                        {formatMinorAmount(row.amount_minor)}
                      </p>
                      <p className="break-all text-xs text-slate-500">
                        Reference {row.id}
                      </p>
                      {row.provider === "local_sandbox" && (
                        <div className="flex flex-wrap gap-2">
                          {(
                            [
                              "SUCCEEDED",
                              "FAILED",
                              "REFUNDED",
                              "CHARGEBACK",
                            ] as const
                          ).map((outcome) => (
                            <button
                              className="rounded border border-slate-300 px-3 py-2 text-sm"
                              disabled={busy}
                              key={outcome}
                              onClick={() =>
                                void action(
                                  `/billing/checkout/${row.id}/simulate/`,
                                  { outcome },
                                )
                              }
                            >
                              Simulate {outcome.toLowerCase()}
                            </button>
                          ))}
                        </div>
                      )}
                    </li>
                  ))}
                </ul>
              </section>
            </>
          )}
          {(error || config.error) && (
            <p role="alert" className="text-rose-700">
              {error || errorMessage(config.error)}
            </p>
          )}
          {message && <p role="status">{message}</p>}
        </>
      )}
    </main>
  );
}

export function OnboardingView() {
  return (
    <main className="mx-auto max-w-3xl space-y-5 p-6">
      <h1 className="text-2xl font-bold">Set up your workspace</h1>
      <p>
        Start with your operating structure, then bring your colleagues and
        assets into the register.
      </p>
      <ol className="list-inside list-decimal space-y-4 rounded-xl border border-slate-200 bg-white p-6">
        {[
          ["settings", "Confirm company profile"],
          ["departments", "Create departments"],
          ["locations", "Create locations"],
          ["users-and-roles", "Invite colleagues"],
          ["asset-categories", "Define asset categories"],
          ["asset-create", "Register your first asset"],
          ["dashboard", "Review the dashboard"],
          ["billing", "Review your plan and trial"],
        ].map(([route, label]) => (
          <li key={route}>
            <a className="text-blue-900 underline" href={`#${route}`}>
              {label}
            </a>
          </li>
        ))}
      </ol>
      <p className="text-sm text-slate-600">
        Your accounting policy determines useful lives, residual values,
        capitalization dates, and period controls. AssetFlow currently supports
        straight-line depreciation.
      </p>
    </main>
  );
}
