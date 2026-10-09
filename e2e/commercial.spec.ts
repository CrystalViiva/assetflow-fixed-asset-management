import { test, expect } from "@playwright/test";
import { execFileSync } from "node:child_process";
import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";

test.beforeAll(() => {
  if (
    process.env.ASSETFLOW_DISPOSABLE_SMOKE !== "1" ||
    !process.env.DATABASE_URL?.includes("/af_browser_")
  )
    throw new Error("Run only through scripts/commercial-smoke.py.");
});

test.beforeEach(async ({ request }) => {
  if (process.env.E2E_NGINX === "1") {
    const response = await request.get("/");
    expect(response.headers()["content-security-policy"]).toContain(
      "script-src 'self'",
    );
    expect(response.headers()["x-content-type-options"]).toBe("nosniff");
  }
});
const password = process.env.SMOKE_PASSWORD!;
function deliver(route: string, email: string) {
  execFileSync(
    process.env.SMOKE_PYTHON!,
    ["backend/manage.py", "deliver_identity_mail"],
    { env: process.env, stdio: "pipe" },
  );
  const root = process.env.EMAIL_FILE_PATH!;
  const messages = readdirSync(root).map((name) =>
    readFileSync(join(root, name), "utf8"),
  );
  const body = messages
    .reverse()
    .find(
      (message) =>
        message.includes(`To: ${email}`) &&
        message.includes(`#${route}?token=`),
    );
  const link = body?.match(
    new RegExp(`http://127\\.0\\.0\\.1:3007/#${route}\\?token=([^\\s]+)`),
  );
  if (!link)
    throw new Error("Expected captured account email was not delivered.");
  return `/#${route}?token=${link[1]}`;
}

test("self-service verification, real dashboard, invitations, sandbox payment and recovery", async ({
  page,
  browser,
  request,
}) => {
  await page.goto("/#signup");
  await page.getByLabel("Business email").fill("browser-owner@example.test");
  await page.getByLabel("Company name").fill("Browser Synthetic Company");
  await page.getByRole("button", { name: "Send verification email" }).click();
  await expect(page.getByRole("status")).toContainText("verification email");
  await page.goto(deliver("verify-email", "browser-owner@example.test"));
  await page.getByLabel("Password", { exact: true }).fill(password);
  await page.getByLabel("Confirm password").fill(password);
  await page.getByRole("button", { name: "Verify & create workspace" }).click();
  await expect(page.getByRole("status")).toContainText("company is ready");
  await page.getByRole("link", { name: "Sign in", exact: true }).click();
  await page
    .getByLabel("Email", { exact: true })
    .fill("browser-owner@example.test");
  await page.getByLabel("Password", { exact: true }).fill(password);
  const dashboard = page.waitForResponse(
    (response) =>
      response.url().endsWith("/dashboard/metrics/") &&
      response.status() === 200,
  );
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await dashboard;
  await page.goto("/#settings");
  await expect(
    page.getByRole("heading", { name: "Account & organization" }),
  ).toBeVisible();
  await page.goto("/#departments");
  await page.getByLabel("Name", { exact: true }).fill("Finance");
  await page.getByLabel("Code", { exact: true }).fill("FIN");
  await page.getByRole("button", { name: "Create department" }).click();
  await expect(page.getByRole("status")).toContainText("Changes saved");
  await page.goto("/#users-and-roles");
  await page
    .getByLabel("Invitation email")
    .fill("browser-colleague@example.test");
  await page.getByRole("button", { name: "Send invitation" }).click();
  await expect(
    page.getByText(
      "Invitation requested. Eligible recipients will receive an email.",
    ),
  ).toBeVisible();
  const colleagueContext = await browser.newContext();
  const colleague = await colleagueContext.newPage();
  await colleague.goto(
    "http://127.0.0.1:3007" +
      deliver("accept-invitation", "browser-colleague@example.test"),
  );
  await colleague.getByLabel("New password").fill(password);
  await colleague.getByLabel("Confirm password").fill(password);
  await colleague.getByRole("button", { name: "Set password" }).click();
  await expect(colleague.getByRole("status")).toContainText("password is set");
  await colleagueContext.close();
  await page.goto("/#billing");
  await expect(page.getByText("TRIAL", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Start sandbox checkout" }).click();
  await page
    .getByRole("button", { name: "Simulate succeeded" })
    .first()
    .click();
  await expect(page.getByText("ACTIVE", { exact: true })).toBeVisible();
  await expect(page.getByText(/SUCCEEDED · NGN 100\.00/)).toBeVisible();
  await page.evaluate(() => window.scrollTo({ top: 0, behavior: "instant" }));
  await page.screenshot({
    path: join(process.env.E2E_OUTPUT_DIR!, "billing-sandbox.png"),
    fullPage: true,
    animations: "disabled",
    timeout: 15_000,
  });
  const recoveryContext = await browser.newContext();
  const recovery = await recoveryContext.newPage();
  await recovery.goto("http://127.0.0.1:3007/#forgot-password");
  await recovery
    .getByLabel("Business email")
    .fill("browser-owner@example.test");
  await recovery.getByRole("button", { name: "Send recovery link" }).click();
  await expect(recovery.getByRole("status")).toContainText("eligible");
  await recovery.goto(
    "http://127.0.0.1:3007" +
      deliver("reset-password", "browser-owner@example.test"),
  );
  await recovery.getByLabel("New password").fill(password + "-reset");
  await recovery.getByLabel("Confirm password").fill(password + "-reset");
  await recovery.getByRole("button", { name: "Set password" }).click();
  await expect(recovery.getByRole("status")).toContainText("password is set");
  const invalidLogin = await request.post("/api/v1/auth/token/", {
    data: { email: "browser-owner@example.test", password },
  });
  expect(invalidLogin.status()).toBe(401);
  const validLogin = await request.post("/api/v1/auth/token/", {
    data: {
      email: "browser-owner@example.test",
      password: password + "-reset",
    },
  });
  expect(validLogin.status()).toBe(200);
  await recoveryContext.close();
});

test("public demo request persists and notifies the operator inbox", async ({
  page,
  request,
}) => {
  await page.goto("/#request-demo");
  await page.getByLabel("Name", { exact: true }).fill("Synthetic Prospect");
  await page.getByLabel("Business email").fill("browser-prospect@example.test");
  await page
    .getByLabel("Company", { exact: true })
    .fill("Synthetic Prospect Company");
  await page
    .getByLabel("Business requirements")
    .fill("Synthetic evaluation of a multi-location asset register.");
  await page.getByRole("checkbox").check();
  await page.getByRole("button", { name: "Request a demonstration" }).click();
  await expect(page.getByRole("status")).toContainText("Request received");
  const login = await request.post("/api/v1/auth/token/", {
    data: { email: "browser-operator@example.test", password },
  });
  const tokens = await login.json();
  const inbox = await request.get("/api/v1/platform/leads/", {
    headers: { Authorization: `Bearer ${tokens.access}` },
  });
  expect(inbox.status()).toBe(200);
  expect(
    (await inbox.json()).some(
      (row: { email: string }) => row.email === "browser-prospect@example.test",
    ),
  ).toBe(true);
});

test("managed provisioning and platform operator dashboard work in the browser", async ({
  page,
}) => {
  await page.goto("/#login");
  await page
    .getByLabel("Email", { exact: true })
    .fill("browser-operator@example.test");
  await page.getByLabel("Password", { exact: true }).fill(password);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Platform operations" }),
  ).toBeVisible();
  await page
    .getByLabel("Company name", { exact: true })
    .fill("Managed Browser Company");
  await page.getByLabel("Unique company code").fill("BROWSER-MANAGED");
  await page
    .getByLabel("Administrator email")
    .fill("browser-managed@example.test");
  await page
    .getByRole("button", { name: "Create company & queue activation" })
    .click();
  await expect(page.getByRole("status")).toContainText("Operation recorded");
  await page.getByRole("button", { name: "Sign out", exact: true }).click();
  await page.goto(deliver("accept-invitation", "browser-managed@example.test"));
  await page.getByLabel("New password").fill(password);
  await page.getByLabel("Confirm password").fill(password);
  await page.getByRole("button", { name: "Set password" }).click();
  await expect(page.getByRole("status")).toContainText("password is set");
});

test("commercial pages work at a mobile viewport and label fictional demo data", async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  for (const route of [
    "features",
    "how-it-works",
    "solutions",
    "security",
    "pricing",
    "about",
    "help",
    "demo",
  ]) {
    await page.goto(`/#${route}`);
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= window.innerWidth,
      ),
    ).toBe(true);
  }
  await expect(
    page.getByText("Illustrative demo — fictional data, no customer records"),
  ).toBeVisible();
  await page.evaluate(() => window.scrollTo({ top: 0, behavior: "instant" }));
  await page.screenshot({
    path: join(process.env.E2E_OUTPUT_DIR!, "mobile-demo.png"),
    fullPage: true,
    animations: "disabled",
    timeout: 15_000,
  });
});
