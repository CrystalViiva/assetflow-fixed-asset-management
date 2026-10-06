import { useState } from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { useModalAccessibility } from './useModalAccessibility';
import { Sidebar } from '../layout/Sidebar';
import { InitiateTransferModal } from '../modals/InitiateTransferModal';

function DialogFixture() {
  const [open, setOpen] = useState(false);
  const ref = useModalAccessibility(open, () => setOpen(false));
  return <><button onClick={() => setOpen(true)}>Open dialog</button>{open && <div ref={ref} role="dialog" aria-modal="true" aria-label="Example" tabIndex={-1}><button>First</button><button>Last</button></div>}</>;
}

describe('F15 keyboard accessibility', () => {
  it('traps focus in dialogs, closes with Escape, and restores the opener', () => {
    render(<DialogFixture />);
    const opener = screen.getByRole('button', { name: 'Open dialog' });
    opener.focus();
    fireEvent.click(opener);
    const first = screen.getByRole('button', { name: 'First' });
    const last = screen.getByRole('button', { name: 'Last' });
    expect(document.activeElement).toBe(first);
    last.focus();
    fireEvent.keyDown(document, { key: 'Tab' });
    expect(document.activeElement).toBe(first);
    fireEvent.keyDown(document, { key: 'Escape' });
    expect(screen.queryByRole('dialog')).toBeNull();
    expect(document.activeElement).toBe(opener);
  });

  it('offers a named mobile navigation landmark and Escape restores the menu trigger', () => {
    const close = vi.fn();
    render(<Sidebar currentRoute="dashboard" onNavigate={() => undefined} isCollapsed={false} onToggleCollapse={() => undefined} isMobileOpen onCloseMobile={close} />);
    expect(screen.getByRole('dialog', { name: 'Primary navigation menu' })).toBeTruthy();
    expect(screen.getByRole('navigation', { name: 'Workspace destinations' })).toBeTruthy();
    expect(document.activeElement).toBe(screen.getByRole('button', { name: 'Close navigation' }));
    fireEvent.keyDown(document, { key: 'Escape' });
    expect(close).toHaveBeenCalledOnce();
  });

  it('exposes an action panel as a named dialog with an accessible close control', () => {
    render(<InitiateTransferModal isOpen onClose={() => undefined} selectedAsset={null} assets={[]} departments={[]} locations={[]} onSubmitTransfer={async () => undefined} />);
    expect(screen.getByRole('dialog', { name: 'Initiate Asset Transfer' })).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Close transfer dialog' })).toBeTruthy();
  });
});
