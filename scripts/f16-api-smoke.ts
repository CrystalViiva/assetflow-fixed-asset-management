// Full lifecycle smoke: only execute through scripts/f1-smoke.py --f16.
import assert from 'node:assert/strict';
import { createHash, randomUUID } from 'node:crypto';
import { ApiClient } from '../src/services/apiClient';
import { ApiError } from '../src/services/apiError';
import { Session } from '../src/services/session';
import { AcquisitionWorkflow } from '../src/services/acquisitionWorkflow';
import { emptyAcquisitionForm } from '../src/services/acquisitionForm';
import { DjangoAssetRepository } from '../src/services/djangoApiBridge';
import { DjangoDepreciationRepository } from '../src/services/depreciationRepository';
import { DjangoMovementRepository } from '../src/services/movementRepository';
import { DjangoMaintenanceRepository } from '../src/services/maintenanceRepository';
import { DjangoVerificationRepository } from '../src/services/verificationRepository';
import { DjangoAssuranceRepository } from '../src/services/assuranceRepository';
import { DjangoReportRepository } from '../src/services/reportRepository';
import { DjangoDashboardRepository } from '../src/services/dashboardRepository';
import { DjangoAuditRepository } from '../src/services/auditRepository';
import { DjangoDisposalRepository } from '../src/services/disposalRepository';

let stage = 'session setup';
const password = process.env.F1_SMOKE_PASSWORD!;
function makeSession(api: ApiClient) {
  const storage = new Map<string, string>();
  const session = new Session(api, {
    getItem: key => storage.get(key) ?? null,
    setItem: (key, value) => storage.set(key, value),
    removeItem: key => storage.delete(key),
  }, () => {});
  return { session, storage };
}

async function run() {
  const api = new ApiClient(process.env.F1_SMOKE_URL!);
  const { session, storage } = makeSession(api);
  await session.initialize();
  stage = 'asset manager login and reference data';
  await session.login(process.env.F1_SMOKE_EMAIL!, password);
  assert.equal(session.getSnapshot().user?.role, 'ASSET_MANAGER');
  const assets = new DjangoAssetRepository(api);
  const depreciation = new DjangoDepreciationRepository(api);
  const movement = new DjangoMovementRepository(api);
  const maintenance = new DjangoMaintenanceRepository(api);
  const verification = new DjangoVerificationRepository(api);
  const assurance = new DjangoAssuranceRepository(api);
  const reports = new DjangoReportRepository(api);
  const dashboard = new DjangoDashboardRepository(api);
  const audit = new DjangoAuditRepository(api);
  const disposals = new DjangoDisposalRepository(api);
  const [categories, departments, locations, custodians] = await Promise.all([
    assets.getCategories(), assets.getReferences('departments'), assets.getReferences('locations'), movement.custodians(),
  ]);
  const department = departments.find(row => row.code === 'OPS')!;
  const destinationDepartment = departments.find(row => row.code === 'OPS-DST')!;
  const location = locations.find(row => row.code === 'PLANT')!;
  const destinationLocation = locations.find(row => row.code === 'PLANT-DST')!;
  const custodian = custodians.find(row => row.email === 'f16-custodian@example.test')!;
  assert.ok(categories[0] && department && destinationDepartment && location && destinationLocation && custodian);

  stage = 'draft asset, componentized acquisition and capitalization';
  const form = {
    ...emptyAcquisitionForm, tag: 'F16-GOLDEN-001', name: 'F16 lifecycle asset',
    description: 'Single disposable release-gate asset', categoryId: categories[0].id,
    departmentId: department.id, locationId: location.id, acquisitionDate: '2026-01-01',
    capitalizationDate: '2026-01-02', usefulLifeMonths: '36', residualValue: '100.00',
    purchase: '1000.01', freight: '0.99', installation: '0.00', civil: '0.00', other: '0.00',
    vendor: 'F16 test supplier', invoice: 'F16-INV-001', reference: 'F16-GOLDEN', notes: 'Disposable fixture',
  };
  const workflow = new AcquisitionWorkflow(assets, () => session.getSnapshot().user !== null, async () => {});
  await workflow.create(form);
  await workflow.record(form);
  await workflow.capitalize();
  const assetId = workflow.getSnapshot().asset!.id;
  assert.equal(workflow.getSnapshot().asset?.status, 'ACTIVE');
  assert.equal(workflow.getSnapshot().asset?.purchaseCost, '1001.00');

  stage = 'SLM schedule and independently checked January posting';
  const period = await depreciation.createPeriod(2026, 1);
  await depreciation.createSchedule(assetId);
  const posting = await depreciation.post(assetId, period.id);
  assert.deepEqual([
    posting.openingBookValue, posting.depreciationAmount,
    posting.accumulatedDepreciation, posting.closingBookValue,
  ], ['1001.00', '25.03', '25.03', '975.97']);
  assert.equal((await assets.getAssetById(assetId)).bookValue, '975.97');

  stage = 'custody assignment and placement transfer';
  const assignment = await movement.createAssignment({ asset_id: assetId, assigned_to_id: custodian.id, notes: 'F16 custody fixture' });
  const transfer = await movement.createTransfer({ asset_id: assetId, to_department_id: destinationDepartment.id, to_location_id: destinationLocation.id, reason: 'F16 controlled relocation', notes: 'Golden lifecycle' });
  await movement.transition(transfer.id, 'approve');
  assert.equal((await assets.getAssetById(assetId)).department?.id, department.id);
  const completedTransfer = await movement.transition(transfer.id, 'complete');
  assert.equal(completedTransfer.status, 'COMPLETED');
  assert.equal((await movement.assignments({ asset: assetId, active: true })).length, 1);
  let currentAsset = await assets.getAssetById(assetId);
  assert.deepEqual([currentAsset.department?.id, currentAsset.location?.id], [destinationDepartment.id, destinationLocation.id]);

  stage = 'maintenance completion and ledger invariance';
  const beforeMaintenance = [currentAsset.purchaseCost, currentAsset.residualValue, currentAsset.usefulLifeMonths, currentAsset.depreciationMethod, currentAsset.accumulatedDepreciation, currentAsset.bookValue];
  const order = await maintenance.createWorkOrder({ asset_id: assetId, maintenance_type: 'CORRECTIVE', priority: 'HIGH', description: 'F16 release-gate service', due_date: '2026-02-01', diagnosis: 'Inspection required' });
  await maintenance.assign(order.id, session.getSnapshot().user!.id);
  await maintenance.start(order.id);
  const cost = await maintenance.createCost({ work_order_id: order.id, cost_type: 'PARTS', description: 'Replacement part', quantity: '2.500', unit_cost: '13.37', vendor_reference: 'F16-COST', incurred_at: '2026-02-03T10:00:00Z' });
  assert.equal(cost.totalCost, '33.43');
  const completedWork = await maintenance.complete(order.id, { resolution: 'Part replaced', completion_notes: 'Operational check passed', downtime_minutes: 20, maintenance_date: '2026-02-03' });
  assert.equal(completedWork.record.totalCost, '33.43');
  currentAsset = await assets.getAssetById(assetId);
  assert.deepEqual([currentAsset.purchaseCost, currentAsset.residualValue, currentAsset.usefulLifeMonths, currentAsset.depreciationMethod, currentAsset.accumulatedDepreciation, currentAsset.bookValue], beforeMaintenance);

  stage = 'physical verification, exception, NOTE and private evidence';
  const campaign = await verification.createCampaign({ name: 'F16 physical verification', description: 'Same-asset release gate', scope_type: 'ORGANIZATION', start_date: '2026-03-01' });
  await verification.transitionCampaign(campaign.id, 'start');
  const observation = await verification.createObservation({ campaign_id: campaign.id, asset_id: assetId, observed_asset_tag: 'F16-OBSERVED-MISMATCH', observed_description: 'Intentional tag discrepancy', observed_location_id: destinationLocation.id, observed_department_id: destinationDepartment.id, observed_custodian_id: custodian.id, observed_condition: 'GOOD', notes: 'Master data must not change' });
  assert.equal(observation.assetId, assetId);
  assert.ok(observation.exceptions.some(row => row.type === 'TAG_MISMATCH'));
  const note = await verification.addNote({ verification_id: observation.id, evidence_type: 'NOTE', description: 'Inspector note only; separate from binary evidence.' });
  assert.equal(note.integrity, 'METADATA_ONLY');
  const png = Buffer.from('89504e470d0a1a0a0000000d4948445200000001000000010802000000907753de0000000c49444154789c63f8cfc0000003010100c9fe92ef0000000049454e44ae426082', 'hex');
  const evidence = await verification.uploadEvidence(observation.id, new File([png], 'f16-evidence.png', { type: 'text/plain' }));
  assert.equal(evidence.integrity, 'VERIFIED');
  assert.equal(evidence.byteSize, png.byteLength);
  const downloadedEvidence = await verification.downloadEvidence(evidence.id);
  assert.deepEqual(Buffer.from(await downloadedEvidence.blob.arrayBuffer()), png);
  await verification.transitionCampaign(campaign.id, 'complete');

  stage = 'authoritative assurance run creation';
  const run = await assurance.createRun({ run_type: 'FULL', verification_campaign_id: campaign.id, stale_after_days: 365 });
  stage = 'authoritative assurance execution dispatch';
  const started = await assurance.executeRun(run.id);
  stage = 'authoritative assurance completion polling';
  let finished = started;
  for (let attempt = 0; attempt < 20 && finished.status === 'RUNNING'; attempt++) {
    await new Promise(resolve => setTimeout(resolve, 100));
    finished = await assurance.run(run.id);
  }
  assert.equal(finished.status, 'COMPLETED');
  assert.equal(finished.assetsEvaluated, 1);
  stage = 'public assurance finding publication';
  const published = await assurance.runFindings(run.id, { page: 1, pageSize: 100 });
  assert.ok(published.results.every(finding => finding.occurrences.some(item => item.assuranceRunId === run.id)));
  if (published.results[0]) {
    await assurance.findingAction(published.results[0].id, 'review');
    await assurance.findingAction(published.results[0].id, 'resolve', 'Reviewed in F16 disposable release smoke.');
  }
  const afterAssurance = await assets.getAssetById(assetId);
  assert.deepEqual([afterAssurance.tag, afterAssurance.department?.id, afterAssurance.location?.id, afterAssurance.status, afterAssurance.purchaseCost, afterAssurance.accumulatedDepreciation, afterAssurance.bookValue], ['F16-GOLDEN-001', destinationDepartment.id, destinationLocation.id, 'ACTIVE', '1001.00', '25.03', '975.97']);

  stage = 'live report, durable snapshot and CSV/JSON exports';
  const filter = { asset_tag: 'F16-GOLDEN-001' };
  const liveBefore = await reports.report('asset_register', { page: 1, pageSize: 25, ...filter });
  assert.equal(liveBefore.count, 1);
  assert.equal(liveBefore.results[0]?.purchase_cost, '1001.00');
  assert.equal(liveBefore.results[0]?.current_book_value, '975.97');
  const snapshot = await reports.createSnapshot({ report_type: 'asset_register', filters: filter, idempotency_key: randomUUID() });
  let completedSnapshot = await reports.snapshot(snapshot.id);
  for (let attempt = 0; attempt < 20 && ['QUEUED', 'RUNNING'].includes(completedSnapshot.status); attempt++) {
    await new Promise(resolve => setTimeout(resolve, 100));
    completedSnapshot = await reports.snapshot(snapshot.id);
  }
  assert.equal(completedSnapshot.status, 'COMPLETED');
  assert.equal(completedSnapshot.rowCount, 1);
  const frozenRows = await reports.snapshotRows(snapshot.id, 1, 25);
  assert.equal(frozenRows.results[0]?.payload.status, 'ACTIVE');
  const expected = { cost: '1001.00', accumulated: '25.03', book: '975.97', gain: '224.03' };
  const downloaded: Record<string, string> = {};
  for (const format of ['CSV', 'JSON'] as const) {
    const accepted = await reports.createExport({ source_snapshot_id: snapshot.id, format, idempotency_key: randomUUID() });
    let exported = await reports.export(accepted.id);
    for (let attempt = 0; attempt < 20 && ['QUEUED', 'RUNNING'].includes(exported.status); attempt++) {
      await new Promise(resolve => setTimeout(resolve, 100));
      exported = await reports.export(accepted.id);
    }
    assert.equal(exported.status, 'COMPLETED');
    assert.equal(exported.sourceSnapshotId, snapshot.id);
    const file = await reports.downloadExport(exported.id);
    const bytes = Buffer.from(await file.blob.arrayBuffer());
    assert.equal(bytes.byteLength, exported.byteSize);
    assert.equal(createHash('sha256').update(bytes).digest('hex'), exported.sha256);
    downloaded[format] = bytes.toString('utf8');
    if (format === 'CSV') assert.ok(downloaded.CSV.includes('F16-GOLDEN-001'));
    else {
      const envelope = JSON.parse(downloaded.JSON) as { schema_version: number; snapshot: { id: string }; rows: Record<string, unknown>[] };
      assert.equal(envelope.schema_version, 1);
      assert.equal(envelope.snapshot.id, snapshot.id);
      assert.equal(envelope.rows[0]?.purchase_cost, expected.cost);
      assert.equal(envelope.rows[0]?.current_book_value, expected.book);
    }
  }

  stage = 'dashboard and audit reconciliation before disposal';
  const preDisposal = await dashboard.metrics();
  assert.equal(preDisposal.portfolio.currentlyHeldAssets, 1);
  assert.equal(preDisposal.financial.capitalizedCost, expected.cost);
  assert.equal(preDisposal.financial.accumulatedDepreciation, expected.accumulated);
  assert.equal(preDisposal.financial.bookValue, expected.book);
  const auditEvents = await audit.events({ page: 1, pageSize: 100, action: '', entityType: 'ASSET', entityId: assetId, actor: '', search: '', dateFrom: '', dateTo: '', ordering: '-timestamp' });
  assert.ok(auditEvents.results.some(event => event.action === 'ASSET_CAPITALIZED'));
  const depreciationEvents = await audit.events({ page: 1, pageSize: 100, action: '', entityType: 'DEPRECIATION_ENTRY', entityId: posting.id, actor: '', search: '', dateFrom: '', dateTo: '', ordering: '-timestamp' });
  assert.ok(depreciationEvents.results.some(event => event.action === 'DEPRECIATION_POSTED'));

  stage = 'return custody and complete separate-approver disposal';
  await movement.returnAssignment(assignment.id);
  const draft = await disposals.create({ asset_id: assetId, disposal_date: '2026-03-04', disposal_method: 'SALE', reason: 'F16 controlled derecognition', proceeds: '1200.00' });
  await disposals.submit(draft.id);
  const adminApi = new ApiClient(process.env.F1_SMOKE_URL!);
  const { session: adminSession, storage: adminStorage } = makeSession(adminApi);
  await adminSession.initialize();
  await adminSession.login(process.env.F1_SMOKE_APPROVER_EMAIL!, password);
  assert.equal(adminSession.getSnapshot().user?.role, 'ADMIN');
  const approved = await new DjangoDisposalRepository(adminApi).approve(draft.id);
  assert.equal(approved.status, 'APPROVED');
  const completedDisposal = await disposals.complete(draft.id);
  assert.deepEqual([completedDisposal.status, completedDisposal.capitalizedCost, completedDisposal.accumulatedDepreciation, completedDisposal.carryingAmount, completedDisposal.gainOrLoss], ['COMPLETED', expected.cost, expected.accumulated, expected.book, expected.gain]);
  const disposed = await assets.getAssetById(assetId);
  assert.equal(disposed.status, 'DISPOSED');
  assert.deepEqual(await depreciation.getEntries({ asset: assetId }), [posting]);
  const postDisposal = await dashboard.metrics();
  assert.equal(postDisposal.portfolio.currentlyHeldAssets, 0);
  assert.equal(postDisposal.portfolio.disposedAssets, 1);
  assert.equal(postDisposal.financial.bookValue, '0.00');
  const snapshotAfterDisposal = await reports.snapshotRows(snapshot.id, 1, 25);
  assert.equal(snapshotAfterDisposal.results[0]?.payload.status, 'ACTIVE');
  assert.equal((await reports.report('asset_register', { page: 1, pageSize: 25, ...filter })).results[0]?.status, 'DISPOSED');
  const eventActions = new Set((await audit.events({ page: 1, pageSize: 100, action: '', entityType: '', entityId: '', actor: '', search: '', dateFrom: '', dateTo: '', ordering: '-timestamp' })).results.map(event => event.action));
  assert.ok(eventActions.has('ASSET_DERECOGNIZED'));

  stage = 'logout and session material cleanup';
  session.logout();
  adminSession.logout();
  assert.equal(storage.size, 0);
  assert.equal(adminStorage.size, 0);
  assert.equal(session.getSnapshot().user, null);
  console.log('PASS: one isolated F16 asset traversed draft→acquisition→capitalization→SLM posting→custody/transfer→maintenance→physical verification/private evidence→assurance→live report/snapshot/CSV+JSON→separate approval/disposal; Decimal 1001.00−25.03=975.97; disposal 1200.00−975.97=224.03; snapshot stayed ACTIVE while live report became DISPOSED; dashboard moved held asset/book value 1/975.97→0/0.00; audit and session cleanup verified.');
}

void run().catch(error => {
  const detail = error instanceof ApiError ? `${error.kind}${error.status ? ` HTTP ${error.status}` : ''}` : error instanceof Error && error.name === 'AssertionError' ? error.message.slice(0, 250) : error instanceof Error ? error.name : 'runtime failure';
  console.log(`SMOKE: failed at ${stage}; ${detail}`);
  process.exitCode = 1;
});
