import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';

const mocks = vi.hoisted(() => ({
  downloadEvidence: vi.fn(), uploadEvidence: vi.fn(), evidence: vi.fn(), invalidate: vi.fn(),
  data: { results: [] as Array<Record<string, unknown>> },
}));
vi.mock('../auth/AuthProvider', () => ({ useAuth: () => ({ user: { id: 7 }, generation: 3, isCurrent: () => true }) }));
vi.mock('../services/runtime', () => ({ verificationRepository: { downloadEvidence: mocks.downloadEvidence, uploadEvidence: mocks.uploadEvidence, evidence: mocks.evidence } }));
vi.mock('../services/verificationQueries', () => ({
  useVerificationEvidence: () => ({ data: mocks.data, isPending: false, isError: false, refetch: vi.fn(async () => ({ data: mocks.data })) }),
  invalidateVerification: mocks.invalidate,
}));
import { VerificationBinaryEvidence } from './VerificationBinaryEvidence';

describe('private verification binary evidence', () => {
  beforeEach(() => { vi.clearAllMocks(); mocks.data = { results: [] }; mocks.evidence.mockResolvedValue({ results: [] }); });
  it('keeps file bytes local and confirms only the server verified upload state', async () => {
    const file = new File(['private bytes'], 'proof.pdf', { type: 'application/pdf' });
    mocks.uploadEvidence.mockResolvedValue({ id: 'evidence-id', verificationId: 'verification-id', fileName: 'proof.pdf', byteSize: file.size, sha256: 'a'.repeat(64), integrity: 'VERIFIED' });
    render(<VerificationBinaryEvidence verificationId="verification-id" writable />);
    fireEvent.change(screen.getByLabelText('Choose evidence file'), { target: { files: [file] } });
    fireEvent.click(screen.getByRole('button', { name: 'Upload privately' }));
    await screen.findByText(/stored and integrity verified by Django/);
    expect(mocks.uploadEvidence).toHaveBeenCalledTimes(1);
    expect(mocks.uploadEvidence).toHaveBeenCalledWith('verification-id', file);
    expect(mocks.invalidate).toHaveBeenCalledWith(7, 3);
  });

  it('offers authenticated content access only for Django VERIFIED rows', async () => {
    mocks.data = { results: [
      { id: 'ready', verificationId: 'verification-id', fileName: 'verified.pdf', contentType: 'application/pdf', byteSize: 12, integrity: 'VERIFIED', uploadedAt: null, capturedByEmail: 'admin@example.test', sha256: 'b'.repeat(64) },
      { id: 'pending', verificationId: 'verification-id', fileName: 'pending.pdf', contentType: '', byteSize: null, integrity: 'PENDING', uploadedAt: null, capturedByEmail: 'admin@example.test', sha256: '' },
    ] };
    mocks.downloadEvidence.mockResolvedValue({ blob: new Blob(['private']), contentDisposition: 'attachment; filename="verified.pdf"', contentType: 'application/pdf' });
    const create = vi.spyOn(URL, 'createObjectURL').mockReturnValue('blob:private');
    const revoke = vi.spyOn(URL, 'revokeObjectURL').mockImplementation(() => {});
    const click = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {});
    render(<VerificationBinaryEvidence verificationId="verification-id" writable={false} />);
    expect(screen.getByRole('button', { name: 'Download privately' })).toBeTruthy();
    expect(screen.queryByRole('button', { name: /pending\.pdf/ })).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: 'Download privately' }));
    await waitFor(() => expect(click).toHaveBeenCalledTimes(1));
    expect(mocks.downloadEvidence).toHaveBeenCalledWith('ready');
    expect(create).toHaveBeenCalledTimes(1);
    await waitFor(() => expect(revoke).toHaveBeenCalledWith('blob:private'));
    create.mockRestore(); revoke.mockRestore(); click.mockRestore();
  });
});
