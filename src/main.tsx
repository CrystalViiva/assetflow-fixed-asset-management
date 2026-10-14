import {StrictMode} from 'react';
import {createRoot} from 'react-dom/client';
import './index.css';

const root = createRoot(document.getElementById('root')!);
void import('./auth/ApplicationRoot').then(({ ApplicationRoot }) => {
  root.render(<StrictMode><ApplicationRoot /></StrictMode>);
}).catch(() => {
  root.render(<main role="alert" className="route-not-found"><div>
    <p>ASSETFLOW - STARTUP RECOVERY</p>
    <h1>AssetFlow could not start.</h1>
    <p>Check the application configuration and loaded files, then reload. You can also return to the public homepage.</p>
    <div className="mt-5 flex flex-wrap gap-3"><a href="#/" className="rounded bg-[#315ee7] px-4 py-2 text-sm font-semibold text-white">Return home</a><button type="button" onClick={() => window.location.reload()} className="rounded border border-slate-300 px-4 py-2 text-sm font-semibold text-slate-800">Reload application</button></div>
  </div></main>);
});
