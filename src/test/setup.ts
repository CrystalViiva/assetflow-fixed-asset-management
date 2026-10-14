import { afterEach, vi } from 'vitest';
import { cleanup } from '@testing-library/react';
// jsdom has no layout/scrolling engine; real scrolling is covered in Playwright.
Element.prototype.scrollIntoView = vi.fn();
window.scrollTo = vi.fn();
afterEach(() => { cleanup(); window.sessionStorage.clear(); window.localStorage.clear(); });
