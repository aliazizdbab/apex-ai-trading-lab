import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import { App } from './App';
import './index.css';
import { applyUiToDocument, useUiStore } from './stores/uiStore';

// Apply persisted theme/language/direction before the first render, then keep them in sync.
applyUiToDocument(useUiStore.getState());
useUiStore.subscribe((state) => applyUiToDocument(state));

const queryClient = new QueryClient();

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <App />
      </BrowserRouter>
    </QueryClientProvider>
  </StrictMode>,
);
