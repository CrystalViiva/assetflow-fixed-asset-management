// Runs only inside the disposable F16 runner. No customer messages or payment network.
import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { randomUUID } from "node:crypto";
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";

type Data = Record<string, any>;
const base = process.env.F1_SMOKE_URL!;
const password = process.env.F1_SMOKE_PASSWORD!;
let operator = "",
  administrator = "",
  foreign = "",
  organization = "";

async function call(
  path: string,
  body?: Data,
  token = "",
  expected = 200,
): Promise<any> {
  const response = await fetch(base + path, {
    method: body ? "POST" : "GET",
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: body ? JSON.stringify(body) : undefined,
  });
  assert.equal(response.status, expected, `${path}: unexpected HTTP status`);
  return response.status === 204 ? null : response.json();
}
async function login(email: string, value = password) {
  return (await call("/auth/token/", { email, password: value }))
    .access as string;
}
function capture(email: string, route: string): string {
  execFileSync(
    process.env.SMOKE_PYTHON!,
    ["backend/manage.py", "deliver_identity_mail"],
    { env: process.env, stdio: "pipe" },
  );
  const root = process.env.EMAIL_FILE_PATH!;
  const bodies = readdirSync(root)
    .sort(
      (a, b) =>
        statSync(join(root, b)).mtimeMs - statSync(join(root, a)).mtimeMs,
    )
    .map((name) => readFileSync(join(root, name), "utf8"));
  const body = bodies.find(
    (value) =>
      value.includes(`To: ${email}`) && value.includes(`#${route}?token=`),
  );
  const match = body?.match(new RegExp(`#${route}\\?token=([^\\s]+)`));
  assert.ok(match, "Expected transactional email was not captured");
  return match[1];
}

export async function prepareCommercialLifecycle() {
  assert.equal(process.env.F16_COMMERCIAL_MODE, "1");
  assert.ok(process.env.F1_SMOKE_DATABASE?.startsWith("assetflow_f16_"));
  operator = await login("f16-operator@example.test");
  await call("/assets/", undefined, operator, 403);
  const managed = await call(
    "/platform/provision/",
    {
      key: randomUUID(),
      name: "Commercial lifecycle",
      code: "ASSETFLOW_F16SMOKE",
      email: process.env.F1_SMOKE_APPROVER_EMAIL,
    },
    operator,
    201,
  );
  organization = managed.organization_id;
  await call("/auth/invitations/accept/", {
    token: capture(process.env.F1_SMOKE_APPROVER_EMAIL!, "accept-invitation"),
    password,
  });
  administrator = await login(process.env.F1_SMOKE_APPROVER_EMAIL!);
  await call("/platform/tenants/", undefined, administrator, 403);
  for (const [email, role] of [
    [process.env.F1_SMOKE_EMAIL!, "ASSET_MANAGER"],
    ["f16-custodian@example.test", "EMPLOYEE"],
  ]) {
    await call("/admin/invitations/", { email, role }, administrator, 202);
    await call("/auth/invitations/accept/", {
      token: capture(email, "accept-invitation"),
      password,
    });
  }
  const employee = await login("f16-custodian@example.test");
  assert.equal((await call("/auth/me/", undefined, employee)).role, "EMPLOYEE");
  await call(
    "/auth/password-reset/",
    { email: "f16-custodian@example.test" },
    "",
    202,
  );
  await call("/auth/password-reset/complete/", {
    token: capture("f16-custodian@example.test", "reset-password"),
    password: password + "-recovered",
  });
  await call("/auth/me/", undefined, employee, 401);
  assert.equal(
    (
      await call(
        "/auth/me/",
        undefined,
        await login("f16-custodian@example.test", password + "-recovered"),
      )
    ).role,
    "EMPLOYEE",
  );
  for (const [name, code] of [
    ["Operations", "OPS"],
    ["Destination Operations", "OPS-DST"],
  ]) {
    await call("/admin/departments/", { name, code }, administrator, 201);
  }
  for (const [name, code] of [
    ["Main Plant", "PLANT"],
    ["Destination Plant", "PLANT-DST"],
  ]) {
    await call("/admin/locations/", { name, code }, administrator, 201);
  }
  await call(
    "/assets/categories/",
    { name: "Equipment", code: "EQ", default_useful_life_months: 36 },
    administrator,
    201,
  );
  for (const kind of ["DEMO", "SALES"]) {
    const request_key = randomUUID();
    await call(
      "/public/leads/",
      {
        request_key,
        kind,
        name: "Synthetic Buyer",
        email: "buyer@example.test",
        company: "Synthetic",
        requirements: "Controlled pilot evaluation",
        consent: true,
      },
      "",
      202,
    );
  }
  assert.equal((await call("/platform/leads/", undefined, operator)).length, 2);
  const config = await call("/public/config/");
  await call(
    "/auth/signup/",
    { email: "foreign@example.test", company_name: "Second company" },
    "",
    202,
  );
  await call("/auth/signup/verify/", {
    token: capture("foreign@example.test", "verify-email"),
    password,
    plan_id: config.plans[0].id,
  });
  foreign = await login("foreign@example.test");
  assert.equal(
    (await call("/billing/", undefined, foreign)).subscription.state,
    "TRIAL",
  );
  console.log(
    "PASS: operator authorization, managed activation, invitations, employee login/recovery, durable demo/sales leads and verified second-tenant signup.",
  );
}

export async function verifyCommercialLifecycle(
  assetId: string,
  snapshotId: string,
  postingId: string,
) {
  await call(`/assets/${assetId}/`, undefined, foreign, 404);
  const before = await call(`/assets/${assetId}/`, undefined, administrator);
  const config = await call("/public/config/");
  const checkout = await call(
    "/billing/checkout/",
    { plan_id: config.plans[0].id, request_key: randomUUID() },
    administrator,
    201,
  );
  await call(
    `/billing/checkout/${checkout.id}/simulate/`,
    { outcome: "SUCCEEDED" },
    foreign,
    400,
  );
  await call(
    `/billing/checkout/${checkout.id}/simulate/`,
    { outcome: "SUCCEEDED" },
    administrator,
  );
  assert.equal(
    (await call("/billing/", undefined, administrator)).subscription.state,
    "ACTIVE",
  );
  await call("/billing/cancel/", {}, administrator);
  // Advance only this disposable tenant's paid-period fixture to test real expiry enforcement.
  execFileSync(
    process.env.SMOKE_PYTHON!,
    [
      "backend/manage.py",
      "shell",
      "-c",
      "import os; from datetime import timedelta; from django.conf import settings; from django.utils import timezone; from commercial.models import Subscription; assert settings.DATABASES['default']['NAME'] == os.environ['F1_SMOKE_DATABASE']; assert os.environ['F1_SMOKE_DATABASE'].startswith('assetflow_f16_'); assert Subscription.objects.filter(organization__code='ASSETFLOW_F16SMOKE', cancel_at_period_end=True).update(period_ends_at=timezone.now()-timedelta(seconds=1)) == 1",
    ],
    { env: process.env, stdio: "pipe" },
  );
  assert.equal(
    (await call("/billing/", undefined, administrator)).subscription.writable,
    false,
  );
  await call(
    "/admin/departments/",
    { name: "Denied expired write", code: "DENIED" },
    administrator,
    403,
  );
  assert.deepEqual(
    await call(`/assets/${assetId}/`, undefined, administrator),
    before,
  );
  const rows = await call(
    `/report-snapshots/${snapshotId}/rows/`,
    undefined,
    administrator,
  );
  assert.equal(rows.results.length, 1);
  const entries = await call(
    "/depreciation/entries/",
    undefined,
    administrator,
  );
  assert.ok(
    (entries.results ?? entries).some((row: Data) => row.id === postingId),
  );
  await call(
    `/platform/tenants/${organization}/state/`,
    { is_active: false, reason: "Synthetic suspension validation" },
    operator,
  );
  await call("/assets/", undefined, administrator, 401);
  await call(
    `/platform/tenants/${organization}/state/`,
    { is_active: true, reason: "Synthetic resume validation" },
    operator,
  );
  administrator = await login(process.env.F1_SMOKE_APPROVER_EMAIL!);
  assert.deepEqual(
    await call(`/assets/${assetId}/`, undefined, administrator),
    before,
  );
  console.log(
    "PASS: second-tenant denial, server-authoritative simulated payment, cancellation/expired write denial, retained asset/ledger/snapshot and suspended-session denial; all 20 commercial journey checkpoints exercised.",
  );
}
