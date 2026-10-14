import {StrictMode} from 'react';
import {createRoot} from 'react-dom/client';
import './index.css';
import { RecoveryActions } from './components/common/RecoveryActions';

const root = createRoot(document.getElementById('root')!);
void import('./auth/ApplicationRoot').then(({ ApplicationRoot }) => {
  root.render(<StrictMode><ApplicationRoot /></StrictMode>);
}).catch(error => {
  console.error("AssetFlow startup failed", error);
  root.render(<main role="alert" className="route-not-found"><div>
    <p>ASSETFLOW - STARTUP RECOVERY</p>
    <h1>AssetFlow could not start.</h1>
    <p>Check the application configuration and loaded files, then reload. You can also return to the public homepage.</p>
    <RecoveryActions />
  </div></main>);
});
