import React from 'react';
import ReactDOM from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import 'leaflet/dist/leaflet.css';
import './styles.css';
import App from './App.jsx';
import { LanguageProvider } from './lib/language.jsx';
import { AuthProvider } from './lib/auth.jsx';

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <BrowserRouter>
      <LanguageProvider><AuthProvider>
        <App />
      </AuthProvider></LanguageProvider>
    </BrowserRouter>
  </React.StrictMode>
);
