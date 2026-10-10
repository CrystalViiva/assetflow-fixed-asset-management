import { afterEach, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { IdentityView } from "./IdentityViews";
import { BillingView, SignupView } from "./SaasViews";
import * as auth from "../auth/AuthProvider";
import { responseError } from "../services/apiError";
import { MarketingPage } from "./MarketingPages";
import { apiClient } from "../services/authRuntime";
import { formatMinorAmount, readCheckout } from "../services/commercial";

afterEach(() => {
  window.location.hash = "";
  vi.restoreAllMocks();
});
function wrapper(children: React.ReactNode) {
  return render(
    <QueryClientProvider
      client={
        new QueryClient({
          defaultOptions: { queries: { retry: false, gcTime: 0 } },
        })
      }
    >
      {children}
    </QueryClientProvider>,
  );
}

it("submits generic password recovery through the public API without caching passwords", async () => {
  const request = vi
    .spyOn(apiClient, "request")
    .mockResolvedValue({ detail: "If eligible, an email will arrive." });
  wrapper(<IdentityView route="forgot-password" />);
  fireEvent.change(screen.getByLabelText("Business email"), {
    target: { value: "person@example.test" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Send recovery link" }));
  expect(await screen.findByRole("status")).toHaveProperty(
    "textContent",
    "If eligible, an email will arrive.",
  );
  expect(request).toHaveBeenCalledWith(
    "/auth/password-reset/",
    expect.objectContaining({
      authenticated: false,
      body: { email: "person@example.test" },
    }),
  );
});

it("requires an invitation link and matching passwords, then shows server acceptance", async () => {
  window.location.hash = "#accept-invitation?token=synthetic-signed-link";
  const request = vi.spyOn(apiClient, "request").mockResolvedValue({
    detail: "Your password is set. Sign in to continue.",
  });
  wrapper(<IdentityView route="accept-invitation" />);
  fireEvent.change(screen.getByLabelText("New password"), {
    target: { value: "Synthetic-password-2026!" },
  });
  fireEvent.change(screen.getByLabelText("Confirm password"), {
    target: { value: "different" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Set password" }));
  expect(await screen.findByRole("alert")).toHaveProperty(
    "textContent",
    "The passwords must match.",
  );
  expect(request).not.toHaveBeenCalled();
  fireEvent.change(screen.getByLabelText("Confirm password"), {
    target: { value: "Synthetic-password-2026!" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Set password" }));
  expect(await screen.findByRole("status")).toHaveProperty(
    "textContent",
    expect.stringContaining("password is set"),
  );
  expect(request).toHaveBeenCalledWith(
    "/auth/invitations/accept/",
    expect.objectContaining({
      body: {
        token: "synthetic-signed-link",
        password: "Synthetic-password-2026!",
      },
    }),
  );
});

it("offers managed onboarding when the server disables public signup", async () => {
  vi.spyOn(apiClient, "request").mockResolvedValue({
    self_service_enabled: false,
    billing_provider: "disabled",
    plans: [],
  });
  wrapper(<SignupView />);
  expect(
    await screen.findByRole("link", { name: "Contact sales" }),
  ).toHaveProperty("hash", "#contact-sales");
  expect(
    screen.queryByRole("button", { name: "Send verification email" }),
  ).toBeNull();
});

it("keeps demo content visibly fictional and pricing separate from test charges", () => {
  const view = wrapper(<MarketingPage route="demo" />);
  expect(screen.getByText(/fictional data, no customer records/)).toBeTruthy();
  expect(screen.getByText("DEMO-001 · Office workstation")).toBeTruthy();
  view.unmount();
  wrapper(<MarketingPage route="pricing" />);
  expect(screen.getByText(/not published prices/)).toBeTruthy();
  expect(screen.getByText(/Live payment collection is disabled/)).toBeTruthy();
});

it("rejects malformed billing responses instead of trusting browser state", () => {
  expect(() =>
    readCheckout({ id: "x", status: "SUCCEEDED", amount_minor: "100" }),
  ).toThrow();
});

it("displays provider minor amounts exactly without floating-point conversion", () => {
  expect(formatMinorAmount(10025)).toBe("100.25");
  expect(formatMinorAmount(1)).toBe("0.01");
  expect(() => formatMinorAmount(Number.MAX_SAFE_INTEGER + 1)).toThrow();
});

it("shows provider subscription status and does not claim an unconfirmed cancellation", async () => {
  vi.spyOn(auth, "useAuth").mockReturnValue({
    role: "ADMIN",
    generation: 0,
  } as ReturnType<typeof auth.useAuth>);
  const plan = {
    id: "test-plan",
    name: "Team",
    version: 1,
    currency: "NGN",
    monthly_amount: "100.25",
    active_users: 10,
    registered_assets: 250,
    trial_days: 14,
    sandbox: true,
  };
  vi.spyOn(apiClient, "request").mockImplementation(async (path) => {
    if (path === "/billing/cancel/")
      throw responseError(400, {
        error: {
          code: "VALIDATION_ERROR",
          message: "Provider cancellation was not confirmed.",
          details: {},
        },
      });
    if (path === "/public/config/")
      return {
        self_service_enabled: true,
        billing_provider: "paystack_test",
        plans: [plan],
      };
    return {
      provider: "paystack_test",
      managed: false,
      usage: { active_users: 1, registered_assets: 1 },
      history: [],
      subscription: {
        state: "ACTIVE",
        writable: true,
        plan,
        billing_email: "owner@example.test",
        trial_ends_at: null,
        period_ends_at: "2026-12-01T00:00:00Z",
        grace_ends_at: null,
        cancel_at_period_end: false,
        recurring_status: "active",
        provider_setup_pending: false,
      },
    };
  });
  wrapper(<BillingView />);
  expect(
    await screen.findByText("Recurring test subscription: active"),
  ).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "Cancel at period end" }));
  expect((await screen.findByRole("alert")).textContent).toContain(
    "not confirmed",
  );
  expect(screen.queryByText("Cancellation recorded")).toBeNull();
  expect(
    screen.queryByText("Billing status refreshed from the server."),
  ).toBeNull();
});
