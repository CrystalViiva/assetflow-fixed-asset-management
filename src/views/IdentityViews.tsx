import { useState, type FormEvent, type ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import { apiClient } from "../services/authRuntime";
import { errorMessage, isRecord } from "../services/apiError";
import { useAuth } from "../auth/AuthProvider";
import { organizationRoles } from "../services/organizationAdminRepository";
import { useReferences } from "../services/referenceQueries";

const input = "mt-1 block w-full rounded-lg border border-slate-300 p-3";
const button =
  "rounded-lg bg-blue-900 px-4 py-3 font-semibold text-white disabled:opacity-50";
export function AccountShell({
  title,
  children,
}: {
  title: string;
  children: ReactNode;
}) {
  return (
    <main className="min-h-screen bg-slate-50 p-6">
      <section className="mx-auto max-w-2xl rounded-2xl border bg-white p-6 md:p-10">
        <a href="#/" className="text-xl font-bold text-blue-900">
          AssetFlow
        </a>
        <h1 className="my-6 text-2xl font-bold">{title}</h1>
        {children}
        <nav className="mt-8 flex flex-wrap gap-5 text-sm text-blue-900">
          <a href="#login">Sign in</a>
          <a href="#/">Product home</a>
        </nav>
      </section>
    </main>
  );
}

export function IdentityView({ route }: { route: string }) {
  const resetRequest = route === "forgot-password";
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
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
    if (!resetRequest && password !== confirmation) {
      setError("The passwords must match.");
      return;
    }
    setBusy(true);
    try {
      const result = await apiClient.request(
        resetRequest
          ? "/auth/password-reset/"
          : route === "accept-invitation"
            ? "/auth/invitations/accept/"
            : "/auth/password-reset/complete/",
        {
          method: "POST",
          authenticated: false,
          body: resetRequest ? { email } : { token, password },
        },
      );
      setMessage(
        isRecord(result) && typeof result.detail === "string"
          ? result.detail
          : "Completed.",
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
        resetRequest
          ? "Recover your account"
          : route === "accept-invitation"
            ? "Accept your invitation"
            : "Set a new password"
      }
    >
      <p className="mb-6 text-slate-600">
        {resetRequest
          ? "Enter your business email. Eligible accounts receive a one-time reset link."
          : "Choose a strong password of at least 8 characters. This link can be used once."}
      </p>
      {message ? (
        <p role="status">{message}</p>
      ) : (
        <form className="space-y-5" onSubmit={submit} aria-busy={busy}>
          {resetRequest ? (
            <label className="block">
              Business email
              <input
                className={input}
                type="email"
                autoComplete="email"
                required
                maxLength={254}
                value={email}
                onChange={(e) => setEmail(e.target.value)}
              />
            </label>
          ) : (
            <>
              <label className="block">
                New password
                <input
                  className={input}
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
                  className={input}
                  type="password"
                  autoComplete="new-password"
                  required
                  value={confirmation}
                  onChange={(e) => setConfirmation(e.target.value)}
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
            disabled={busy || (!resetRequest && !token)}
          >
            {busy
              ? "Submitting…"
              : resetRequest
                ? "Send recovery link"
                : "Set password"}
          </button>
          {!resetRequest && !token && (
            <p role="alert">Open the complete link from your email.</p>
          )}
        </form>
      )}
    </AccountShell>
  );
}

interface Invitation {
  id: string;
  email: string;
  role: string;
  expires_at: string;
  consumed_at: string | null;
  revoked_at: string | null;
}
function invitations(value: unknown): Invitation[] {
  if (!Array.isArray(value)) throw new Error("Invalid invitation response.");
  return value.map((row) => {
    if (
      !isRecord(row) ||
      typeof row.id !== "string" ||
      typeof row.email !== "string" ||
      typeof row.role !== "string" ||
      typeof row.expires_at !== "string" ||
      !(row.consumed_at === null || typeof row.consumed_at === "string") ||
      !(row.revoked_at === null || typeof row.revoked_at === "string")
    )
      throw new Error("Invalid invitation response.");
    return {
      id: row.id,
      email: row.email,
      role: row.role,
      expires_at: row.expires_at,
      consumed_at: row.consumed_at,
      revoked_at: row.revoked_at,
    };
  });
}
export function InvitationsPanel() {
  const { generation } = useAuth();
  const query = useQuery({
    queryKey: ["invitations", generation],
    queryFn: async () =>
      invitations(await apiClient.request("/admin/invitations/")),
  });
  const departments = useReferences("departments", true);
  const [email, setEmail] = useState("");
  const [role, setRole] = useState("EMPLOYEE");
  const [department, setDepartment] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  async function run(path: string, body: unknown) {
    if (busy) return;
    setBusy(true);
    setError("");
    setMessage("");
    try {
      await apiClient.request(path, { method: "POST", body });
      await query.refetch();
      setMessage(
        path.endsWith("revoke/")
          ? "Invitation revoked."
          : "Invitation requested. Eligible recipients will receive an email.",
      );
    } catch (cause) {
      setError(errorMessage(cause));
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="space-y-4 rounded-xl border border-slate-200 bg-white p-5">
      <h2 className="text-lg font-semibold">Invite a colleague</h2>
      <p className="text-sm text-slate-600">
        Invitations expire after 48 hours. Sending another invitation to the
        same address replaces the previous link.
      </p>
      <form
        className="grid gap-4 sm:grid-cols-2"
        onSubmit={(e) => {
          e.preventDefault();
          void run("/admin/invitations/", {
            email,
            role,
            department_id: department || null,
          });
        }}
      >
        <label>
          Invitation email
          <input
            className={input}
            type="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
        </label>
        <label>
          Invitation role
          <select
            className={input}
            value={role}
            onChange={(e) => setRole(e.target.value)}
          >
            {organizationRoles.map((item) => (
              <option key={item}>{item}</option>
            ))}
          </select>
        </label>
        <label>
          Invitation department
          <select
            className={input}
            value={department}
            onChange={(e) => setDepartment(e.target.value)}
          >
            <option value="">No department</option>
            {(departments.data ?? []).map((item) => (
              <option key={item.id} value={item.id}>
                {item.name}
              </option>
            ))}
          </select>
        </label>
        <button className={button} disabled={busy}>
          Send invitation
        </button>
      </form>
      {message && <p role="status">{message}</p>}
      {(error || query.error) && (
        <p role="alert" className="text-rose-700">
          {error || errorMessage(query.error)}
        </p>
      )}
      {query.isPending ? (
        <p role="status">Loading invitations…</p>
      ) : (
        <ul className="divide-y">
          {query.data?.map((row) => (
            <li
              key={row.id}
              className="flex flex-wrap items-center justify-between gap-3 py-3"
            >
              <span>
                {row.email} · {row.role}
                <small className="block text-slate-500">
                  {row.consumed_at
                    ? "Accepted"
                    : row.revoked_at
                      ? "Revoked"
                      : new Date(row.expires_at) <= new Date()
                        ? "Expired"
                        : `Expires ${new Date(row.expires_at).toLocaleString()}`}
                </small>
              </span>
              {!row.consumed_at && !row.revoked_at && (
                <button
                  disabled={busy}
                  className="rounded border border-slate-300 px-3 py-2"
                  onClick={() =>
                    void run(`/admin/invitations/${row.id}/revoke/`, {})
                  }
                >
                  Revoke
                </button>
              )}
            </li>
          ))}
          {query.data?.length === 0 && <li>No invitations yet.</li>}
        </ul>
      )}
    </section>
  );
}

export function AccountSettings() {
  const { user, role, logout, generation } = useAuth();
  const profile = useQuery({
    queryKey: ["account-profile", generation],
    queryFn: () => apiClient.request("/auth/profile/"),
  });
  const [current, setCurrent] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const org =
    isRecord(profile.data) && isRecord(profile.data.organization)
      ? profile.data.organization
      : null;
  async function submit(event: FormEvent) {
    event.preventDefault();
    if (busy) return;
    setBusy(true);
    setError("");
    try {
      await apiClient.request("/auth/password-change/", {
        method: "POST",
        body: { current_password: current, password },
      });
      logout();
      window.location.hash = "#login";
    } catch (cause) {
      setError(errorMessage(cause));
    } finally {
      setBusy(false);
      setCurrent("");
      setPassword("");
    }
  }
  return (
    <main className="mx-auto max-w-3xl space-y-6 p-6">
      <h1 className="text-2xl font-bold">Account & organization</h1>
      <nav className="flex gap-5 text-blue-900">
        <a href="#onboarding">Getting started</a>
        {role === "ADMIN" && <a href="#billing">Plan & billing</a>}
        <a href="#help">Customer guide</a>
      </nav>
      <section className="rounded-xl border border-slate-200 bg-white p-5">
        <p>{user?.email}</p>
        <p>{role}</p>
        {profile.isPending && <p>Loading profile…</p>}
        {profile.error && <p role="alert">{errorMessage(profile.error)}</p>}
        {org && (
          <>
            <h2 className="mt-4 font-bold">{String(org.name)}</h2>
            <p>
              {String(org.currency)} · {String(org.timezone)}
            </p>
            {role === "ADMIN" && (
              <form
                className="mt-4 space-y-3"
                onSubmit={async (e) => {
                  e.preventDefault();
                  if (busy) return;
                  const values = new FormData(e.currentTarget);
                  setBusy(true);
                  setError("");
                  try {
                    await apiClient.request("/admin/organization/", {
                      method: "PATCH",
                      body: {
                        name: values.get("name"),
                        legal_name: values.get("legal_name"),
                      },
                    });
                    await profile.refetch();
                    setMessage("Organization profile saved.");
                  } catch (cause) {
                    setError(errorMessage(cause));
                  } finally {
                    setBusy(false);
                  }
                }}
              >
                <label className="block">
                  Company name
                  <input
                    name="name"
                    required
                    maxLength={160}
                    className={input}
                    defaultValue={String(org.name)}
                  />
                </label>
                <label className="block">
                  Legal name
                  <input
                    name="legal_name"
                    maxLength={240}
                    className={input}
                    defaultValue={String(org.legal_name)}
                  />
                </label>
                <button className={button} disabled={busy}>
                  Save company profile
                </button>
              </form>
            )}
          </>
        )}
      </section>
      <form
        onSubmit={submit}
        className="space-y-4 rounded-xl border border-slate-200 bg-white p-5"
      >
        <h2 className="font-bold">Change password</h2>
        <p className="text-sm text-slate-600">
          Changing your password signs out all devices.
        </p>
        <label className="block">
          Current password
          <input
            className={input}
            type="password"
            required
            autoComplete="current-password"
            value={current}
            onChange={(e) => setCurrent(e.target.value)}
          />
        </label>
        <label className="block">
          New password
          <input
            className={input}
            type="password"
            required
            minLength={8}
            maxLength={256}
            autoComplete="new-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </label>
        <button className={button} disabled={busy}>
          Change password
        </button>
      </form>
      {error && (
        <p role="alert" className="text-rose-700">
          {error}
        </p>
      )}
      {message && <p role="status">{message}</p>}
    </main>
  );
}
