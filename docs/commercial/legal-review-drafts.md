# Legal and privacy review checklist — draft only

**Do not publish this checklist as legal terms.** A qualified Nigerian privacy/commercial lawyer should review product practices, contracts, and any international processing before customer launch. The list is not legal advice and does not establish compliance.

## Documents requiring preparation and counsel review

- Terms of Service: service scope, customer responsibilities, acceptable use, fees/taxes, suspension, termination, warranties/liability, dispute resolution, governing law, and export/exit.
- Privacy Notice: controller identity/contact, purposes, categories, lawful bases, recipients/processors, retention, rights request method, security, international transfers, and complaint/escalation process.
- Data Processing Agreement: processing instructions, confidentiality, security measures, subprocessors, assistance, breach notice process, audit cooperation, deletion/return, and cross-border transfers.
- Acceptable Use Policy: authorized use, account security, prohibited activity, uploads, and response to abuse.
- Cancellation/refund policy: effective date, prepaid fees, failed payments, refunds, trial conversion, and data export/retention.
- Security disclosure and incident communication process: intake contact, scope, triage, customer communication, regulator/counsel escalation, and evidence retention.

## Product-specific facts to validate

- AssetFlow stores organization records, user email addresses/roles, asset data, accounting workflow values, audit metadata, and private verification evidence/report exports.
- Customer records are organization-scoped in application APIs; application audit history is not a cryptographic ledger.
- Current identity is JWT-based; MFA, SSO, immediate token revocation, malware scanning, and production penetration testing are not claimed.
- Private file contents are accessed through authenticated endpoints; storage provider, region, backup encryption, and retention need deployment-specific confirmation.
- Supported accounting workflows and exclusions are described in [accounting](../accounting.md); product terms must not imply full IFRS compliance.
- Self-service registration, subscription billing, and live payment collection are not available in the current implementation.

## Nigerian and international review topics

Ask counsel to assess applicability of the Nigeria Data Protection Act 2023 and current NDPC requirements, controller/processor roles, lawful bases, data-subject request handling, retention, security incident duties, cross-border transfers, vendor contracts, data protection impact assessment needs, and any sector-specific customer obligations. For international customers, assess each relevant jurisdiction's privacy, transfer, tax, invoicing, consumer, accessibility, and recurring payment requirements. Re-verify statutes and regulatory guidance at publication time.

## Business decisions required before publication

Name the legal contracting entity and address; appoint privacy/security/support contacts; approve data retention and deletion schedule; select subprocessors and storage regions; define customer notice and incident timelines; establish support hours and measured service objectives; approve plan prices/taxes, refund/cancellation, and payment provider; and document customer data export and backup expiry behavior.
