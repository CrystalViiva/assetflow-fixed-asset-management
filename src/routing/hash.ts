/** Public and workspace routing share one contract: #route and #/route are aliases. */
export function readHashPath(hash = window.location.hash): string {
  return hash.replace(/^#/, '').trim().replace(/^\/+/, '');
}
