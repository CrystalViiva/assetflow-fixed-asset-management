import { apiClient } from "./authRuntime";
import { isRecord } from "./apiError";

export interface Plan {
  id: string;
  name: string;
  version: number;
  currency: string;
  monthly_amount: string;
  active_users: number | null;
  registered_assets: number | null;
  trial_days: number;
  sandbox: boolean;
}
export interface PublicConfig {
  self_service_enabled: boolean;
  billing_provider: string;
  plans: Plan[];
}
export interface Checkout {
  id: string;
  plan_id: string;
  status: string;
  amount_minor: number;
  currency: string;
  provider: string;
  url: string;
  created_at: string;
}
export interface Billing {
  provider: string;
  managed: boolean;
  usage: { active_users: number; registered_assets: number };
  subscription: null | {
    state: string;
    writable: boolean;
    plan: Plan;
    billing_email: string;
    trial_ends_at: string | null;
    period_ends_at: string | null;
    grace_ends_at: string | null;
    cancel_at_period_end: boolean;
  };
  history: Checkout[];
}
function record(value: unknown): Record<string, unknown> {
  if (!isRecord(value)) throw new Error("Invalid commercial API response.");
  return value;
}
function string(value: unknown): string {
  if (typeof value !== "string")
    throw new Error("Invalid commercial text field.");
  return value;
}
function number(value: unknown): number {
  if (typeof value !== "number" || !Number.isFinite(value))
    throw new Error("Invalid commercial number field.");
  return value;
}
export function formatMinorAmount(value: number): string {
  if (!Number.isSafeInteger(value) || value < 0)
    throw new Error("Invalid payment amount.");
  const minor = BigInt(value);
  return `${minor / 100n}.${(minor % 100n).toString().padStart(2, "0")}`;
}
function bool(value: unknown): boolean {
  if (typeof value !== "boolean")
    throw new Error("Invalid commercial boolean field.");
  return value;
}
function nullableString(value: unknown): string | null {
  return value === null ? null : string(value);
}
function nullableNumber(value: unknown): number | null {
  return value === null ? null : number(value);
}
function array(value: unknown): unknown[] {
  if (!Array.isArray(value)) throw new Error("Invalid commercial collection.");
  return value;
}
export function readPlan(value: unknown): Plan {
  const r = record(value);
  return {
    id: string(r.id),
    name: string(r.name),
    version: number(r.version),
    currency: string(r.currency),
    monthly_amount: string(r.monthly_amount),
    active_users: nullableNumber(r.active_users),
    registered_assets: nullableNumber(r.registered_assets),
    trial_days: number(r.trial_days),
    sandbox: bool(r.sandbox),
  };
}
export function readCheckout(value: unknown): Checkout {
  const r = record(value);
  return {
    id: string(r.id),
    plan_id: string(r.plan_id),
    status: string(r.status),
    amount_minor: number(r.amount_minor),
    currency: string(r.currency),
    provider: string(r.provider),
    url: string(r.url),
    created_at: string(r.created_at),
  };
}
export async function getPublicConfig(): Promise<PublicConfig> {
  const r = record(
    await apiClient.request("/public/config/", { authenticated: false }),
  );
  return {
    self_service_enabled: bool(r.self_service_enabled),
    billing_provider: string(r.billing_provider),
    plans: array(r.plans).map(readPlan),
  };
}
export async function getBilling(): Promise<Billing> {
  const r = record(await apiClient.request("/billing/"));
  const u = record(r.usage);
  const s = r.subscription === null ? null : record(r.subscription);
  return {
    provider: string(r.provider),
    managed: bool(r.managed),
    usage: {
      active_users: number(u.active_users),
      registered_assets: number(u.registered_assets),
    },
    history: array(r.history).map(readCheckout),
    subscription: s
      ? {
          state: string(s.state),
          writable: bool(s.writable),
          plan: readPlan(s.plan),
          billing_email: string(s.billing_email),
          trial_ends_at: nullableString(s.trial_ends_at),
          period_ends_at: nullableString(s.period_ends_at),
          grace_ends_at: nullableString(s.grace_ends_at),
          cancel_at_period_end: bool(s.cancel_at_period_end),
        }
      : null,
  };
}
