import { afterEach, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { IdentityView } from "./IdentityViews";
import { SignupView } from "./SaasViews";
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
