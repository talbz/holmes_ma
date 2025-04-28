import React from 'react';
import { createRoot } from 'react-dom/client';
import { App } from './App';

// Get the root element
const rootElement = document.getElementById('root');
const root = createRoot(rootElement);

// Render the app without StrictMode
root.render(<App />); 