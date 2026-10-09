import { useState, type FormEvent } from "react";
import { apiClient } from "../services/authRuntime";
import { errorMessage } from "../services/apiError";
import { dataSource } from "../services/config";

export const marketingRoutes = new Set([
  "features",
  "how-it-works",
  "solutions",
  "security",
  "pricing",
  "about",
  "contact-sales",
  "request-demo",
  "get-started",
  "demo",
  "help",
]);
const pages: Record<
  string,
  { title: string; intro: string; sections: [string, string][] }
> = {
  features: {
    title: "One register. A controlled asset lifecycle.",
    intro:
      "Connect financial records with the people, places, and work that keep your assets useful.",
    sections: [
      [
        "Register & acquisition",
        "Capture asset details, categories, locations, custodians and directly attributable acquisition costs. Capitalize through an explicit controlled workflow.",
      ],
      [
        "Depreciation & disposal",
        "Post straight-line depreciation within accounting periods, preserve residual value floors, and record approved disposal proceeds, carrying value and gain or loss.",
      ],
      [
        "Custody, transfers & maintenance",
        "Keep custody distinct from physical placement. Manage transfers, maintenance plans, work orders and costs without silently changing accounting records.",
      ],
      [
        "Verification, assurance & reports",
        "Record physical observations and private evidence. Review deterministic assurance findings, durable report snapshots, exports and application audit events.",
      ],
    ],
  },
  "how-it-works": {
    title: "From discovery to a working asset register.",
    intro:
      "Managed onboarding and self-service trials use the same organization-scoped application.",
    sections: [
      [
        "1. Agree your scope",
        "For managed onboarding, request a demonstration and discuss locations, asset classes, users, accounting conventions and data preparation.",
      ],
      [
        "2. Activate your workspace",
        "Your invited administrator verifies access and sets their own password. Self-service applicants verify their email before a company workspace is created.",
      ],
      [
        "3. Configure and operate",
        "Set up departments, locations and categories. Invite colleagues, register assets, then capitalize and run period-controlled accounting workflows.",
      ],
      [
        "4. Review and improve",
        "Use verification, assurance, reporting and audit history to investigate gaps. Confirm acceptance against your own accounting policies before relying on results.",
      ],
    ],
  },
  solutions: {
    title: "For teams accountable for physical assets.",
    intro:
      "A shared operating record for finance, facilities and multi-location organizations.",
    sections: [
      [
        "Finance & asset accounting",
        "Manage capitalization, straight-line depreciation, disposals and supporting reports with exact server-side financial arithmetic.",
      ],
      [
        "Construction & engineering",
        "Track equipment, vehicles and custody across offices and project locations. Preserve maintenance and movement history.",
      ],
      [
        "Facilities & operations",
        "Maintain an equipment register, plan work, record costs and follow up physical verification exceptions.",
      ],
      [
        "IT & multi-location businesses",
        "Organize assets by department and location, assign custody and control transfers. Verify what is present without silently rewriting the register.",
      ],
    ],
  },
  security: {
    title: "Security controls you can evaluate.",
    intro:
      "AssetFlow uses scoped access, controlled workflows and private evidence. Deployment and operating practices must be validated for each hosted environment.",
    sections: [
      [
        "Tenant and role boundaries",
        "Django derives tenant scope from authenticated membership. Tenant administrators cannot grant platform operator capabilities or browse another organization.",
      ],
      [
        "Account protection",
        "Expiring single-use invitation and recovery links, password policy checks, rotating refresh tokens, request throttling, and session invalidation support account security. MFA is not currently available.",
      ],
      [
        "Customer data",
        "Verification evidence and report artifacts use private storage. Backup encryption and disposable restoration tools support recovery drills; production retention and off-host storage require operator configuration.",
      ],
      [
        "Claims and responsibilities",
        "These controls are not an independent security certification. Review the deployment, access policies, data location, retention and incident contacts before placing customer information in a hosted instance.",
      ],
    ],
  },
  pricing: {
    title: "Choose a service that fits your organization.",
    intro:
      "Commercial pricing is agreed after discovery. Sandbox test amounts shown inside trial workspaces are not published prices.",
    sections: [
      [
        "Managed onboarding",
        "Demonstration, implementation scope, company provisioning, administrator activation and guided acceptance. Request pricing based on users, assets, locations and support needs.",
      ],
      [
        "Self-service trial",
        "When enabled, verify your email and select an available trial. Plan limits and trial expiry are enforced by the server. No card is required to activate the seeded trial.",
      ],
      [
        "Hosting & support",
        "Agree hosting responsibilities, backup retention, support hours, service objectives and data export requirements before a paid engagement.",
      ],
      [
        "Billing status",
        "This release supports local sandbox checkout and a Paystack test adapter. Live payment collection is disabled.",
      ],
    ],
  },
  about: {
    title: "AssetFlow — Fixed Asset Management Software",
    intro:
      "Built to connect operational asset control with dependable accounting records.",
    sections: [
      [
        "The product",
        "AssetFlow brings acquisition, capitalization, depreciation, custody, maintenance, verification, disposal and reporting into one controlled workspace.",
      ],
      [
        "Accounting approach",
        "IAS 16-aligned workflows include directly attributable costs and straight-line depreciation. Revaluation, impairment, independent component depreciation and full IFRS compliance are not represented as supported.",
      ],
      [
        "A practical implementation",
        "Start with clear responsibilities, clean source records and agreed accounting conventions. Use a controlled pilot and customer acceptance checklist before expanding use.",
      ],
    ],
  },
  help: {
    title: "Getting started & support",
    intro:
      "Your company administrator is the first point of contact for access and operating structure.",
    sections: [
      [
        "Activate your account",
        "Open the one-time link in your invitation and set a strong password. Invitations expire after 48 hours; your administrator can send a replacement. Use Forgot password on the sign-in page for recovery.",
      ],
      [
        "Prepare the register",
        "Create departments, locations and asset categories. Confirm accounting currency, useful lives and residual value conventions before entering and capitalizing assets.",
      ],
      [
        "Export your data",
        "Open Reports, generate a supported snapshot, then create a CSV or JSON export. Exports remain private and require your normal permissions.",
      ],
      [
        "Request support",
        "Use Contact Sales for initial enquiries. Existing customers should use their agreed support channel and provide the action, time and request ID. Never include passwords, reset links or unnecessary personal data.",
      ],
      [
        "Service limitations",
        "Straight-line depreciation is currently supported. Trial expiry restricts writes while preserving reading and supported exports. Managed service responsibilities and retention must be agreed before customer launch.",
      ],
    ],
  },
};

export function CommercialNav() {
  return (
    <nav
      aria-label="Product navigation"
      className="mx-auto flex max-w-7xl flex-wrap items-center gap-x-6 gap-y-3 px-5 py-4 text-sm"
    >
      <a href="#/" className="mr-auto text-xl font-bold text-blue-900">
        AssetFlow
      </a>
      {[
        ["features", "Features"],
        ["how-it-works", "How it works"],
        ["solutions", "Solutions"],
        ["security", "Security"],
        ["pricing", "Pricing"],
        ["about", "About"],
        ["request-demo", "Request a demo"],
        ["login", "Login"],
      ].map(([route, label]) => (
        <a className="hover:underline" key={route} href={`#${route}`}>
          {label}
        </a>
      ))}
    </nav>
  );
}

function LeadForm({ demo }: { demo: boolean }) {
  const [key] = useState(() => crypto.randomUUID());
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy) return;
    const values = new FormData(event.currentTarget);
    setBusy(true);
    setError("");
    try {
      await apiClient.request("/public/leads/", {
        method: "POST",
        authenticated: false,
        body: {
          request_key: key,
          name: values.get("name"),
          email: values.get("email"),
          company: values.get("company"),
          phone: values.get("phone"),
          requirements: values.get("requirements"),
          consent: values.get("consent") === "on",
          website: values.get("website"),
          kind: demo ? "DEMO" : "SALES",
        },
      });
      setMessage(`Request received. Your reference is ${key}.`);
    } catch (cause) {
      setError(errorMessage(cause));
    } finally {
      setBusy(false);
    }
  }
  if (dataSource !== "django")
    return (
      <p className="rounded border border-slate-300 bg-amber-50 p-5">
        This is the illustrative demo build. Contact submission is available on
        the configured customer website.
      </p>
    );
  if (message)
    return (
      <p role="status" className="rounded bg-blue-50 p-5">
        {message}
      </p>
    );
  return (
    <form
      onSubmit={submit}
      className="grid gap-5 rounded-2xl border bg-white p-6 sm:grid-cols-2"
      aria-busy={busy}
    >
      {(
        [
          ["name", "Name", true, "text", 120],
          ["email", "Business email", true, "email", 254],
          ["company", "Company", true, "text", 160],
          ["phone", "Phone (optional)", false, "tel", 40],
        ] as const
      ).map(([name, label, required, type, max]) => (
        <label key={name} className="block">
          {label}
          <input
            className="mt-2 w-full rounded-lg border p-3"
            name={name}
            type={type}
            required={required}
            maxLength={max}
          />
        </label>
      ))}
      <label className="sm:col-span-2">
        Business requirements
        <textarea
          name="requirements"
          required
          maxLength={4000}
          rows={5}
          className="mt-2 w-full rounded-lg border p-3"
          placeholder="Tell us about your assets, locations and implementation needs."
        />
      </label>
      <label className="hidden" aria-hidden="true">
        Website
        <input name="website" tabIndex={-1} autoComplete="off" />
      </label>
      <p className="text-sm text-slate-600 sm:col-span-2">
        We store your details to respond to this enquiry and manage the sales
        process. Do not include passwords or customer datasets. Enquiries are
        reviewed for retention after 90 days. This notice covers this form;
        customer service terms require a separate agreement.
      </p>
      <label className="flex items-start gap-3 text-sm sm:col-span-2">
        <input name="consent" type="checkbox" required className="mt-1" />I
        acknowledge this contact notice and agree to be contacted about my
        request.
      </label>
      {error && (
        <p role="alert" className="text-rose-700 sm:col-span-2">
          {error}
        </p>
      )}
      <button
        className="rounded-lg bg-blue-900 p-3 font-semibold text-white disabled:opacity-50"
        disabled={busy}
      >
        {busy ? "Sending…" : demo ? "Request a demonstration" : "Contact sales"}
      </button>
    </form>
  );
}

export function MarketingPage({ route }: { route: string }) {
  const lead = route === "contact-sales" || route === "request-demo";
  const page = pages[route];
  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      <header className="border-b bg-white">
        <CommercialNav />
      </header>
      <main className="mx-auto max-w-6xl px-5 py-12 md:py-20">
        {lead ? (
          <>
            <p className="text-sm font-semibold uppercase tracking-widest text-blue-800">
              Talk to AssetFlow
            </p>
            <h1 className="mt-4 mb-8 text-4xl font-semibold">
              {route === "request-demo"
                ? "See your asset workflows in action."
                : "Plan your implementation."}
            </h1>
            <LeadForm demo={route === "request-demo"} />
          </>
        ) : route === "get-started" ? (
          <>
            <h1 className="text-4xl font-semibold">
              Get started with AssetFlow
            </h1>
            <div className="mt-8 grid gap-6 sm:grid-cols-2">
              <article className="rounded-2xl border bg-white p-8">
                <h2 className="text-xl font-semibold">Managed onboarding</h2>
                <p className="my-4">
                  Discuss your asset register, accounting policy and rollout
                  with an implementation operator.
                </p>
                <a className="text-blue-900 underline" href="#request-demo">
                  Request a demonstration
                </a>
              </article>
              <article className="rounded-2xl border bg-white p-8">
                <h2 className="text-xl font-semibold">Self-service trial</h2>
                <p className="my-4">
                  Verify your business email and create an isolated company
                  workspace when trials are enabled.
                </p>
                <a className="text-blue-900 underline" href="#signup">
                  Create a trial workspace
                </a>
              </article>
            </div>
          </>
        ) : route === "demo" ? (
          <>
            <p className="rounded bg-amber-100 p-4 font-semibold">
              Illustrative demo — fictional data, no customer records
            </p>
            <h1 className="mt-8 text-4xl font-semibold">
              A clear operating record.
            </h1>
            <p className="my-5">
              This read-only example shows how assets can be grouped by category
              and location. Request a demonstration of the authenticated
              workflows.
            </p>
            <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white">
              <table className="w-full text-left">
                <thead>
                  <tr>
                    {["Asset", "Category", "Location", "Custody"].map((h) => (
                      <th key={h} className="p-4">
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {[
                    [
                      "DEMO-001 · Office workstation",
                      "IT equipment",
                      "Fictional Lagos office",
                      "Assigned",
                    ],
                    [
                      "DEMO-002 · Delivery van",
                      "Vehicles",
                      "Fictional depot",
                      "Assigned",
                    ],
                    [
                      "DEMO-003 · Generator",
                      "Plant & equipment",
                      "Fictional site",
                      "Available",
                    ],
                  ].map((row) => (
                    <tr key={row[0]} className="border-t">
                      {row.map((cell) => (
                        <td key={cell} className="p-4">
                          {cell}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        ) : page ? (
          <>
            <p className="text-sm font-semibold uppercase tracking-widest text-blue-800">
              AssetFlow / Fixed asset management
            </p>
            <h1 className="mt-5 max-w-4xl text-4xl font-semibold leading-tight md:text-5xl">
              {page.title}
            </h1>
            <p className="mt-6 max-w-3xl text-lg leading-8 text-slate-600">
              {page.intro}
            </p>
            <div className="mt-12 grid gap-5 md:grid-cols-2">
              {page.sections.map(([title, text]) => (
                <section
                  key={title}
                  className="rounded-2xl border bg-white p-7"
                >
                  <h2 className="text-xl font-semibold">{title}</h2>
                  <p className="mt-4 leading-7 text-slate-600">{text}</p>
                </section>
              ))}
            </div>
          </>
        ) : null}
        <nav className="mt-12 flex flex-wrap gap-5 border-t pt-8 text-blue-900">
          <a href="#request-demo">Request a demo →</a>
          <a href="#get-started">Get started →</a>
          <a href="#demo">Illustrative demo</a>
          <a href="#help">Customer guide</a>
        </nav>
      </main>
      <footer className="border-t bg-white p-6 text-center text-sm text-slate-500">
        AssetFlow · IAS 16-aligned workflows, subject to documented limitations.
      </footer>
    </div>
  );
}
