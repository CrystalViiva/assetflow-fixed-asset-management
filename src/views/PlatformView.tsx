import { useState, type FormEvent } from "react";
import { useQuery } from "@tanstack/react-query";
import { apiClient } from "../services/authRuntime";
import { errorMessage, isRecord } from "../services/apiError";
import { useAuth } from "../auth/AuthProvider";

interface Tenant {
  id: string;
  name: string;
  code: string;
  is_active: boolean;
  subscription: string;
}
interface Lead {
  id: string;
  name: string;
  email: string;
  company: string;
  requirements: string;
  status: string;
}
function tenants(value: unknown): {
  tenants: Tenant[];
  newLeads: number;
  failedWebhooks: number;
} {
  if (
    !isRecord(value) ||
    !Array.isArray(value.tenants) ||
    typeof value.new_leads !== "number" ||
    !Array.isArray(value.failed_webhooks)
  )
    throw new Error("Invalid operator response.");
  return {
    newLeads: value.new_leads,
    failedWebhooks: value.failed_webhooks.length,
    tenants: value.tenants.map((row) => {
      if (
        !isRecord(row) ||
        typeof row.id !== "string" ||
        typeof row.name !== "string" ||
        typeof row.code !== "string" ||
        typeof row.is_active !== "boolean" ||
        typeof row.subscription !== "string"
      )
        throw new Error("Invalid tenant metadata.");
      return {
        id: row.id,
        name: row.name,
        code: row.code,
        is_active: row.is_active,
        subscription: row.subscription,
      };
    }),
  };
}
function leads(value: unknown): Lead[] {
  if (!Array.isArray(value)) throw new Error("Invalid sales inbox.");
  return value.map((row) => {
    if (
      !isRecord(row) ||
      typeof row.id !== "string" ||
      typeof row.name !== "string" ||
      typeof row.email !== "string" ||
      typeof row.company !== "string" ||
      typeof row.requirements !== "string" ||
      typeof row.status !== "string"
    )
      throw new Error("Invalid enquiry.");
    return {
      id: row.id,
      name: row.name,
      email: row.email,
      company: row.company,
      requirements: row.requirements,
      status: row.status,
    };
  });
}

export function PlatformView() {
  const { user, generation, logout } = useAuth();
  const enabled = user?.isPlatformOperator === true;
  const [search, setSearch] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [key, setKey] = useState(() => crypto.randomUUID());
  const overview = useQuery({
    queryKey: ["platform", generation, search],
    queryFn: async () =>
      tenants(
        await apiClient.request("/platform/tenants/", { query: { search } }),
      ),
    enabled,
  });
  const inbox = useQuery({
    queryKey: ["sales-inbox", generation],
    queryFn: async () => leads(await apiClient.request("/platform/leads/")),
    enabled,
  });
  const health = useQuery({
    queryKey: ["operator-health", generation],
    queryFn: () => apiClient.request("/platform/health/"),
    enabled,
  });
  async function run(path: string, body: unknown, patch = false) {
    if (busy) return;
    setBusy(true);
    setError("");
    setMessage("");
    try {
      await apiClient.request(path, { method: patch ? "PATCH" : "POST", body });
      await Promise.all([overview.refetch(), inbox.refetch()]);
      setMessage("Operation recorded.");
      return true;
    } catch (cause) {
      setError(errorMessage(cause));
      return false;
    } finally {
      setBusy(false);
    }
  }
  async function provision(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    if (
      await run("/platform/provision/", {
        key,
        name: data.get("name"),
        code: data.get("code"),
        email: data.get("email"),
        currency: data.get("currency"),
        timezone_name: data.get("timezone"),
      })
    ) {
      setKey(crypto.randomUUID());
      form.reset();
    }
  }
  return (
    <main className="mx-auto max-w-6xl space-y-6 p-6">
      <header className="flex flex-wrap justify-between gap-3">
        <h1 className="text-2xl font-bold">Platform operations</h1>
        <button
          className="rounded border border-slate-300 px-4 py-2"
          onClick={logout}
        >
          Sign out
        </button>
      </header>
      {!enabled ? (
        <p>Platform operator access is required.</p>
      ) : (
        <>
          <p className="text-slate-600">
            Commercial and operational metadata. Customer asset records are
            accessed through the customer's authorized workspace.
          </p>
          <section className="rounded-xl border border-slate-200 bg-white p-5">
            <h2 className="font-bold">Attention</h2>
            <p>
              {overview.data?.newLeads ?? "…"} new sales enquiries ·{" "}
              {overview.data?.failedWebhooks ?? "…"} failed billing events
            </p>
            {isRecord(health.data) && (
              <ul className="mt-3 flex flex-wrap gap-4 text-sm">
                {Object.entries(health.data).map(([name, value]) => (
                  <li key={name}>
                    {name.replaceAll("_", " ")}: {String(value)}
                  </li>
                ))}
              </ul>
            )}
            {health.error && <p role="alert">{errorMessage(health.error)}</p>}
          </section>
          <form
            onSubmit={provision}
            className="grid gap-4 rounded-xl border border-slate-200 bg-white p-5 sm:grid-cols-2"
          >
            <h2 className="font-bold sm:col-span-2">Provision a company</h2>
            {[
              ["name", "Company name", ""],
              ["code", "Unique company code", ""],
              ["email", "Administrator email", ""],
              ["currency", "Currency", "NGN"],
              ["timezone", "Timezone", "Africa/Lagos"],
            ].map(([name, label, value]) => (
              <label key={name}>
                {label}
                <input
                  name={name}
                  required
                  type={name === "email" ? "email" : "text"}
                  defaultValue={value}
                  className="mt-1 w-full rounded border border-slate-300 p-3"
                />
              </label>
            ))}
            <button
              className="rounded bg-blue-900 p-3 text-white disabled:opacity-50"
              disabled={busy}
            >
              Create company & queue activation
            </button>
          </form>
          <section className="space-y-4 rounded-xl border border-slate-200 bg-white p-5">
            <h2 className="font-bold">Tenant lookup</h2>
            <label className="block">
              Company search
              <input
                className="mt-1 w-full rounded border border-slate-300 p-3"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
              />
            </label>
            {overview.isPending && <p role="status">Loading tenants…</p>}
            {overview.error && (
              <p role="alert">{errorMessage(overview.error)}</p>
            )}
            {overview.data?.tenants.map((t) => (
              <form
                key={t.id}
                className="flex flex-wrap items-center gap-3 border-t py-4"
                onSubmit={(e) => {
                  e.preventDefault();
                  const values = new FormData(e.currentTarget);
                  void run(`/platform/tenants/${t.id}/state/`, {
                    is_active: !t.is_active,
                    reason: values.get("reason"),
                  });
                }}
              >
                <p className="mr-auto">
                  {t.name} · {t.code} · {t.subscription} ·{" "}
                  {t.is_active ? "Active" : "Pending / suspended"}
                </p>
                <label className="text-sm">
                  Reason
                  <input
                    name="reason"
                    required
                    maxLength={500}
                    className="ml-2 rounded border border-slate-300 p-2"
                  />
                </label>
                <button
                  className="rounded border border-slate-300 px-3 py-2"
                  disabled={busy}
                >
                  {t.is_active ? "Suspend tenant" : "Resume tenant"}
                </button>
                {!t.is_active && (
                  <button
                    type="button"
                    className="rounded border border-slate-300 px-3 py-2"
                    disabled={busy}
                    onClick={() =>
                      void run(`/platform/tenants/${t.id}/invitation/`, {})
                    }
                  >
                    Resend pending activation
                  </button>
                )}
              </form>
            ))}
          </section>
          <section className="space-y-4 rounded-xl border border-slate-200 bg-white p-5">
            <h2 className="font-bold">Sales & demo requests</h2>
            {inbox.error && <p role="alert">{errorMessage(inbox.error)}</p>}
            {inbox.data?.length === 0 && <p>No enquiries yet.</p>}
            {inbox.data?.map((lead) => (
              <article key={lead.id} className="space-y-2 border-t py-4">
                <h3 className="font-semibold">
                  {lead.company} · {lead.name}
                </h3>
                <p>{lead.email}</p>
                <p className="whitespace-pre-wrap">{lead.requirements}</p>
                <label>
                  Request status
                  <select
                    className="ml-3 rounded border border-slate-300 p-2"
                    value={lead.status}
                    disabled={busy}
                    onChange={(e) =>
                      void run(
                        "/platform/leads/",
                        { id: lead.id, status: e.target.value },
                        true,
                      )
                    }
                  >
                    {["NEW", "CONTACTED", "QUALIFIED", "CLOSED"].map(
                      (status) => (
                        <option key={status}>{status}</option>
                      ),
                    )}
                  </select>
                </label>
              </article>
            ))}
          </section>
          {error && (
            <p role="alert" className="text-rose-700">
              {error}
            </p>
          )}
          {message && <p role="status">{message}</p>}
        </>
      )}
    </main>
  );
}
