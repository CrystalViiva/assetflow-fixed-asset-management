import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { DashboardView } from './DashboardView';
import { DepreciationView } from './DepreciationView';
import { AssetDetailView } from './AssetDetailView';
import { DisposalsView } from './DisposalsView';
import { ReportsView } from './ReportsView';
import { MockVerificationView } from './MockVerificationView';
import { MockAssuranceView } from './MockAssuranceView';
import App from '../App';

const noop = () => {};

describe('portfolio presentation claims', () => {
  it('uses implemented dashboard accounting terms without certification, auditor, revaluation, or amortization claims', async () => {
    const { container } = render(<DashboardView onNavigate={noop} onSelectAsset={noop} onOpenQuickAction={noop} />);
    expect(await screen.findByText('IAS 16-Aligned Workflow')).toBeTruthy();
    expect(container.textContent).not.toMatch(/IFRS CERTIFIED|PwC|External Audit|Revalued Method|amortiz/i);
  });

  it('labels the implemented tangible asset charge as depreciation', async () => {
    const { container } = render(<DepreciationView onNavigate={noop} onSelectAsset={noop} />);
    expect(await screen.findByRole('heading', { name: 'Depreciation' })).toBeTruthy();
    expect(container.textContent).toMatch(/Depreciable Amount = Cost/);
    expect(container.textContent).toMatch(/Monthly Depreciation = Depreciable Amount \/ Useful Life in Months/);
    expect(container.textContent).not.toMatch(/amortiz|statutory/i);
  });

  it('does not present compliance or external-audit statuses in asset detail, disposal, or reports', async () => {
    const callbacks = { onNavigate: noop, onTriggerPrintBarcode: noop, onTriggerTransfer: noop, onTriggerMaintenance: noop, onTriggerDisposal: noop };
    const detail = render(<AssetDetailView assetId="AST-000002" {...callbacks} />);
    expect(await screen.findByText('Capitalized Asset')).toBeTruthy();
    expect(detail.container.textContent).not.toMatch(/IAS 16 Capital Asset Verified|IAS 16 Bound|Amortization/i);
    detail.unmount();

    const disposals = render(<DisposalsView onNavigate={noop} onSelectAsset={noop} onOpenDisposeAsset={noop} />);
    expect(await screen.findByText(/Asset disposal, derecognition, gain\/loss accounting, and approval controls/)).toBeTruthy();
    expect(disposals.container.textContent).not.toMatch(/IFRS 5|statutory/i);
    disposals.unmount();

    const reports = render(<ReportsView onNavigate={noop} onSelectAsset={noop} />);
    expect(await screen.findByText('Live report preview')).toBeTruthy();
    expect(reports.container.textContent).not.toMatch(/PwC|Audit Compliant|statutory schedules|useful life compliance/i);
  });

  it('shows local demo verification and assurance examples without pending-integration or private-file claims', () => {
    const verification = render(<MockVerificationView />);
    expect(screen.getByRole('heading', { name: 'Physical verification' })).toBeTruthy();
    expect(verification.container.textContent).toMatch(/Matched|Location mismatch|Unregistered/);
    expect(verification.container.textContent).toMatch(/does not connect to Django or store evidence files/i);
    expect(verification.container.textContent).not.toMatch(/Integration pending|later milestones/i);
    verification.unmount();

    const assurance = render(<MockAssuranceView />);
    expect(screen.getByRole('heading', { name: 'Assurance & reconciliation' })).toBeTruthy();
    expect(assurance.container.textContent).toMatch(/Illustrative results/);
    expect(assurance.container.textContent).not.toMatch(/Integration pending|PwC Audit Compliant|IFRS 5/i);
  });

  it('routes mock verification and assurance navigation to their local demo views', async () => {
    window.location.hash = '#verification';
    const verification = render(<App />);
    expect(await screen.findByRole('heading', { name: 'Physical verification' })).toBeTruthy();
    verification.unmount();

    window.location.hash = '#assurance';
    render(<App />);
    expect(await screen.findByRole('heading', { name: 'Assurance & reconciliation' })).toBeTruthy();
  });
});
