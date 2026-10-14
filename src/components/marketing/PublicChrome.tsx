import { useEffect, useRef, useState, type MouseEvent } from 'react';
import { ArrowRight, Menu, X } from 'lucide-react';
import { AssetFlowLogo } from '../common/AssetFlowLogo';
import { readHashPath } from '../../routing/hash';

type Props = { sections?: boolean; authenticated?: boolean; workspaceRoute?: string };
const productLinks = [['Features', 'features'], ['Solutions', 'solutions'], ['How it works', 'how-it-works'], ['Pricing', 'pricing']];

function revisitCurrentPage(event: MouseEvent<HTMLElement>) {
  if (event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
  const href = (event.target as Element).closest('a')?.getAttribute('href');
  if (!href?.startsWith('#') || readHashPath(href) !== readHashPath()) return;
  if (href === window.location.hash) event.preventDefault();
  const section = readHashPath(href);
  if (section.startsWith('section-')) document.getElementById(section)?.scrollIntoView();
  else window.scrollTo({ top: 0, left: 0, behavior: 'instant' });
}

export function PublicHeader({ sections = false, authenticated = false, workspaceRoute = '#dashboard' }: Props) {
  const [open, setOpen] = useState(false);
  const toggle = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    const close = () => setOpen(false);
    const escape = (event: KeyboardEvent) => {
      if (event.key === 'Escape' && open) { close(); toggle.current?.focus(); }
    };
    window.addEventListener('hashchange', close);
    window.addEventListener('resize', close);
    window.addEventListener('keydown', escape);
    return () => {
      window.removeEventListener('hashchange', close);
      window.removeEventListener('resize', close);
      window.removeEventListener('keydown', escape);
    };
  }, [open]);
  const links = (mobile = false) => <>
    {productLinks.map(([label, route]) => <a key={route} onClick={() => setOpen(false)} className={mobile ? 'landing-mobile-link' : 'landing-nav-link'} href={`#${sections ? 'section-' : ''}${route}`}>{label}</a>)}
    <a onClick={() => setOpen(false)} className={mobile ? 'landing-mobile-link' : 'landing-nav-link'} href="#request-demo">Request demo</a>
    <a onClick={() => setOpen(false)} className={mobile ? 'landing-mobile-link' : 'landing-login'} href={authenticated ? workspaceRoute : '#login'}>{authenticated ? 'Open workspace' : 'Log in'}</a>
    <a onClick={() => setOpen(false)} className={mobile ? 'landing-mobile-cta' : 'landing-cta'} href="#get-started">Get started<ArrowRight size={17} aria-hidden="true" /></a>
  </>;
  return <header className="landing-header" onClick={revisitCurrentPage}>
    <a className="public-skip-link" href="#public-main" onClick={event => { event.preventDefault(); const main = document.getElementById('public-main'); main?.focus(); main?.scrollIntoView(); }}>Skip to content</a>
    <div className="landing-header-inner">
      <a href="#/" className="landing-brand" aria-label="AssetFlow home"><AssetFlowLogo className="h-9 w-9" /><span>AssetFlow</span></a>
      <nav aria-label={sections ? 'Main navigation' : 'Product navigation'} className="landing-desktop-nav">{links()}</nav>
      <button ref={toggle} type="button" className="landing-menu-button" aria-label={open ? 'Close navigation' : 'Open navigation'} aria-expanded={open} aria-controls="public-mobile-navigation" onClick={() => setOpen(value => !value)}>{open ? <X size={22} /> : <Menu size={22} />}</button>
    </div>
    {open && <nav id="public-mobile-navigation" aria-label="Mobile navigation" className="landing-mobile-nav">{links(true)}</nav>}
  </header>;
}

export function PublicFooter({ sections = false, authenticated = false, workspaceRoute = '#dashboard' }: Props) {
  return <footer className="landing-footer" onClick={revisitCurrentPage}><div className="footer-main">
    <div className="footer-brand"><a href="#/" className="landing-brand"><AssetFlowLogo className="h-8 w-8" /><span>AssetFlow</span></a><p>Fixed asset control for finance and operations teams.</p></div>
    <div><b>Product</b>{productLinks.map(([label, route]) => <a key={route} href={`#${sections ? 'section-' : ''}${route}`}>{label}</a>)}</div>
    <div><b>Explore</b><a href="#demo">Illustrative demo</a><a href={sections ? '#section-security' : '#security'}>Security</a><a href="#help">Customer guide</a><a href="#about">About AssetFlow</a></div>
    <div><b>Account & sales</b><a href={authenticated ? workspaceRoute : '#login'}>{authenticated ? 'Open workspace' : 'Log in'}</a><a href="#get-started">Get started</a><a href="#request-demo">Request demo</a><a href="#contact-sales">Contact sales</a></div>
  </div><div className="footer-bottom"><span>© {new Date().getFullYear()} AssetFlow</span><span>Product previews use fictional data.</span><a href="https://github.com/CrystalViiva/assetflow-fixed-asset-management" target="_blank" rel="noopener noreferrer">Source repository<span className="sr-only"> (opens in a new tab)</span></a></div></footer>;
}
