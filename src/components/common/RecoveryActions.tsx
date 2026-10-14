/** A document reload clears rejected module promises and failed React boundaries. */
export function RecoveryActions() {
  return <div className="recovery-actions">
    <a href="#/" onClick={event => { event.preventDefault(); window.location.hash = '/'; window.location.reload(); }}>Return home</a>
    <button type="button" onClick={() => window.location.reload()}>Reload application</button>
  </div>;
}
