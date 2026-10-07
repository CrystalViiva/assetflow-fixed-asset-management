import { afterEach, describe, expect, it } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { PublicLandingPage } from './PublicLandingPage';

afterEach(() => { window.location.hash = ''; });

describe('public product experience', () => {
  it('describes implemented lifecycle capabilities and makes the preview explicitly illustrative', () => {
    render(<PublicLandingPage authenticated={false} />);
    expect(screen.getByRole('heading', { name: /control the complete lifecycle of every asset/i })).toBeTruthy();
    expect(screen.getByText(/illustrative interface only/i)).toBeTruthy();
    expect(screen.getByText(/straight-line depreciation workflows/i)).toBeTruthy();
    expect(screen.getByText(/impairment accounting and other depreciation methods are not represented/i)).toBeTruthy();
    expect(screen.getByText(/the browser dashboard does not read parquet marts/i)).toBeTruthy();
    expect(screen.queryByText(/fully ifrs compliant|ai-powered|predictive maintenance|malware scanned/i)).toBeNull();
    expect(screen.getAllByRole('link', { name: /sign in to assetflow/i }).length).toBeGreaterThan(0);
    const github = screen.getByRole('link', { name: /github/i });
    expect(github.getAttribute('href')).toBe('https://github.com/CrystalViiva/assetflow-fixed-asset-management');
    expect(github.getAttribute('target')).toBe('_blank');
    expect(github.getAttribute('rel')).toContain('noopener');
    expect(screen.queryByRole('link', { name: /free trial|pricing|forgot password/i })).toBeNull();
  });

  it('uses an internal dashboard CTA for an authenticated user and provides keyboard-operated mobile navigation', () => {
    render(<PublicLandingPage authenticated />);
    expect(screen.getAllByRole('link', { name: /open dashboard/i })[0].getAttribute('href')).toBe('#dashboard');
    const menu = screen.getByRole('button', { name: 'Open navigation' });
    fireEvent.click(menu);
    expect(screen.getByRole('button', { name: 'Close navigation' }).getAttribute('aria-expanded')).toBe('true');
    expect(screen.getByRole('navigation', { name: 'Mobile navigation' })).toBeTruthy();
  });

  it('exposes section navigation without requesting authenticated data', () => {
    render(<PublicLandingPage authenticated={false} />);
    expect(screen.getAllByRole('link', { name: 'Capabilities' })[0].getAttribute('href')).toBe('#capabilities');
    expect(screen.getAllByRole('link', { name: 'Controls' })[0].getAttribute('href')).toBe('#controls');
    expect(screen.getAllByRole('link', { name: 'Architecture' })[0].getAttribute('href')).toBe('#architecture');
    expect(screen.getByRole('heading', { name: /from acquisition record to accountable disposition/i })).toBeTruthy();
  });
});
