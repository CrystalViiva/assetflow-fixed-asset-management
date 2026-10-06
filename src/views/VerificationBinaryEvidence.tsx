import { useState } from 'react';
import { useAuth } from '../auth/AuthProvider';
import { errorMessage } from '../services/apiError';
import { verificationRepository } from '../services/runtime';
import { invalidateVerification, useVerificationEvidence } from '../services/verificationQueries';
import { VerificationEvidence } from '../services/verificationDtos';

function safeDownloadName(header: string | null, fallback: string) {
  const match = header?.match(/filename\*?=(?:UTF-8''|\")?([^;\"]+)/i);
  let value = fallback;
  if (match) {
    const encoded = match[1].replace(/^"|"$/g, '');
    try { value = decodeURIComponent(encoded); } catch { value = encoded; }
  }
  const basename = value.replace(/[\\/]/g, '_').replace(/[\u0000-\u001f\u007f]/g, '').trim();
  return basename && basename !== '.' && basename !== '..' ? basename.slice(0, 255) : 'evidence';
}

export function VerificationBinaryEvidence({ verificationId, writable }: { verificationId: string; writable: boolean }) {
  const { user, generation, isCurrent } = useAuth();
  const query = useVerificationEvidence(verificationId);
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [uncertain, setUncertain] = useState(false);
  const [message, setMessage] = useState('');

  async function upload() {
    if (!file || !user) return;
    const selected = file;
    const expectedName = selected.name.replace(/^.*[\\/]/, '').replace(/[\u0000-\u001f\u007f]/g, '').trim().slice(0, 255) || 'evidence';
    setBusy(true); setUncertain(false); setMessage('');
    let submitted = false;
    let before = new Set<string>();
    let localDigest = '';
    try {
      const prior = await verificationRepository.evidence(verificationId);
      before = new Set(prior.results.map(row => row.id));
      if (!isCurrent(generation)) return;
      submitted = true;
      const created = await verificationRepository.uploadEvidence(verificationId, selected);
      if (!isCurrent(generation)) return;
      setMessage(`Evidence stored and integrity verified by Django (${created.byteSize} bytes, SHA256 ${created.sha256}).`);
      setFile(null);
    } catch (error) {
      if (!isCurrent(generation)) return;
      if (!submitted) { setMessage(errorMessage(error)); return; }
      if (error instanceof Error && 'status' in error && typeof error.status === 'number' && error.status >= 400 && error.status < 500 && error.status !== 408) {
        setMessage(errorMessage(error));
        return;
      }
      try {
        const after = await verificationRepository.evidence(verificationId);
        if (!isCurrent(generation)) return;
        if (globalThis.crypto?.subtle) {
          const digest = await globalThis.crypto.subtle.digest('SHA-256', await selected.arrayBuffer());
          localDigest = Array.from(new Uint8Array(digest), value => value.toString(16).padStart(2, '0')).join('');
        }
        if (!isCurrent(generation)) return;
        const matches = after.results.filter(row => !before.has(row.id) && row.verificationId === verificationId && row.fileName === expectedName && row.byteSize === selected.size && row.integrity === 'VERIFIED' && localDigest !== '' && row.sha256 === localDigest);
        if (matches.length === 1) {
          setMessage(`Upload committed as ${matches[0].id}; Django confirmed its stored integrity metadata.`);
          setFile(null);
        } else {
          setUncertain(true);
          setMessage(matches.length ? 'Several new evidence records match this upload. Recheck evidence history before retrying.' : 'Upload outcome is uncertain. Recheck evidence history before retrying; the file will not be uploaded again automatically.');
        }
      } catch {
        if (!isCurrent(generation)) return;
        setUncertain(true); setMessage('Upload outcome is uncertain. Recheck evidence history before retrying; the file will not be uploaded again automatically.');
      }
    } finally {
      if (isCurrent(generation)) { await invalidateVerification(user.id, generation); setBusy(false); }
    }
  }

  async function download(item: VerificationEvidence) {
    setBusy(true); setMessage('');
    try {
      const result = await verificationRepository.downloadEvidence(item.id);
      if (!isCurrent(generation)) return;
      const url = URL.createObjectURL(result.blob);
      try {
        const anchor = document.createElement('a');
        anchor.href = url;
        anchor.download = safeDownloadName(result.contentDisposition, item.fileName);
        anchor.rel = 'noopener';
        document.body.appendChild(anchor); anchor.click(); anchor.remove();
      } finally { window.setTimeout(() => URL.revokeObjectURL(url), 0); }
    } catch (error) {
      if (isCurrent(generation)) setMessage(errorMessage(error));
    } finally { if (isCurrent(generation)) setBusy(false); }
  }

  return <section className="rounded-xl border bg-white p-5" aria-labelledby="binary-evidence-title">
    <h3 id="binary-evidence-title" className="text-base font-semibold">Private binary evidence</h3>
    <p className="mt-1 text-sm text-slate-600">PDF, JPEG, or PNG. Django enforces its configured upload limit (20 MiB by default), checks file structure and stored-byte integrity. This does not scan for malware. NOTE entries above are metadata only.</p>
    {query.isPending ? <p role="status" className="py-3 text-sm">Loading binary evidence…</p> : query.isError ? <p role="alert" className="py-3 text-sm">{errorMessage(query.error)} <button className="underline" onClick={() => void query.refetch()}>Retry</button></p> : query.data.results.filter(row => row.integrity !== 'METADATA_ONLY').length === 0 ? <p role="status" className="py-3 text-sm text-slate-600">No binary evidence is linked to this verification record.</p> : <ul className="my-3 space-y-2">{query.data.results.filter(row => row.integrity !== 'METADATA_ONLY').map(item => <li key={item.id} className="flex flex-wrap items-center justify-between gap-3 rounded border p-3 text-sm"><div><b>{item.fileName}</b><div>{item.contentType || 'Type unavailable'} · {item.byteSize ?? '—'} bytes · {item.integrity}</div><div>Uploaded {item.uploadedAt ? new Date(item.uploadedAt).toLocaleString() : 'time unavailable'} by {item.capturedByEmail || 'unknown uploader'}</div>{item.sha256 && <div className="break-all text-xs text-slate-500">SHA256 {item.sha256}</div>}</div>{item.integrity === 'VERIFIED' && <button disabled={busy} onClick={() => void download(item)} className="rounded border px-3 py-2 disabled:opacity-50">Download privately</button>}</li>)}</ul>}
    {writable && <div className="mt-3 flex flex-wrap items-end gap-3"><label className="text-sm">Choose evidence file<input aria-label="Choose evidence file" className="mt-1 block max-w-full rounded border p-2" type="file" accept=".pdf,.jpg,.jpeg,.png,application/pdf,image/jpeg,image/png" disabled={busy || uncertain} onChange={event => setFile(event.target.files?.[0] ?? null)} /></label><button disabled={!file || busy || uncertain} onClick={() => void upload()} className="rounded bg-[#00288e] px-4 py-2 text-sm font-semibold text-white disabled:opacity-50">{busy ? 'Working…' : 'Upload privately'}</button>{uncertain && <button className="rounded border px-3 py-2 text-sm" onClick={() => void query.refetch().then(() => { setUncertain(false); setMessage('Evidence history refreshed. Review it before deciding whether to retry.'); })}>Recheck evidence</button>}</div>}
    {message && <p role={uncertain ? 'alert' : 'status'} className="mt-3 text-sm">{message}</p>}
  </section>;
}
