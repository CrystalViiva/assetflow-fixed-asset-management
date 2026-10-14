import { afterEach, describe, expect, it } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { PublicLandingPage } from './PublicLandingPage';

afterEach(() => { window.location.hash = ''; });

describe('public product experience', () => {
  it('presents the product with clearly fictional preview values and implemented claims', () => {
    render(<PublicLandingPage authenticated={false} mockMode />);
    expect(screen.getByRole('heading', { name: /know your assets.*control their value/i })).toBeTruthy();
    expect(screen.getByRole('img', { name: /illustrative assetflow workspace with fictional asset records/i })).toBeTruthy();
    expect(screen.getByText(/synthetic data.*preview/i)).toBeTruthy();
    expect(screen.getByRole('img', { name: /sample values/i })).toBeTruthy();
    expect(screen.getByText(/does not claim an independent security certification/i)).toBeTruthy();
    expect(screen.getAllByRole('link', { name: /request a demo/i }).some(link => link.getAttribute('href') === '#request-demo')).toBe(true);
    expect(screen.getAllByRole('link', { name: 'Log in' }).every(link => link.getAttribute('href') === '#login')).toBe(true);
    expect(screen.queryByText(/fully ifrs compliant|ai-powered|predictive maintenance|malware scanned/i)).toBeNull();
  });

  it('uses unambiguous section hashes and provides an operable mobile menu', () => {
    render(<PublicLandingPage authenticated={false} mockMode />);
    expect(screen.getAllByRole('link', { name: 'Features' }).every(link => link.getAttribute('href') === '#section-features')).toBe(true);
    expect(screen.getAllByRole('link', { name: 'Solutions' }).some(link => link.getAttribute('href') === '#section-solutions')).toBe(true);
    expect(screen.getAllByRole('link', { name: 'How it works' }).some(link => link.getAttribute('href') === '#section-how-it-works')).toBe(true);
    expect(screen.getAllByRole('link', { name: 'Pricing' }).some(link => link.getAttribute('href') === '#section-pricing')).toBe(true);
    expect(document.getElementById('section-features')).toBeTruthy();
    expect(document.getElementById('section-pricing')).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: 'Open navigation' }));
    expect(screen.getByRole('button', { name: 'Close navigation' }).getAttribute('aria-expanded')).toBe('true');
    fireEvent.click(screen.getByRole('navigation', { name: 'Mobile navigation' }).querySelector('a[href="#section-features"]')!);
    expect(screen.queryByRole('navigation', { name: 'Mobile navigation' })).toBeNull();
  });

  it('offers a workspace link to authenticated visitors', () => {
    render(<PublicLandingPage authenticated />);
    expect(screen.getAllByRole('link', { name: 'Open workspace' }).every(link => link.getAttribute('href') === '#dashboard')).toBe(true);
  });
});
