import {StrictMode} from 'react';
import {createRoot} from 'react-dom/client';
import './index.css';

const root = createRoot(document.getElementById('root')!);
void import('./auth/ApplicationRoot').then(({ ApplicationRoot }) => {
  root.render(<StrictMode><ApplicationRoot /></StrictMode>);
}).catch(() => {
  root.render(<main role="alert" className="m-8 p-8 bg-white rounded-xl border border-rose-200">
    <h1 className="text-xl font-bold">AssetFlow could not start</h1>
    <p className="mt-3">Check VITE_DATA_SOURCE (mock or django), VITE_BACKEND_API_URL, and that the application files are available. Reload after correcting the configuration.</p>
  </main>);
});
