import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AppLayout } from './components/layout/AppLayout';
import { BatchesPage } from './pages/BatchesPage';
import { ImportPage } from './pages/ImportPage';
import { ExplorerPage } from './pages/ExplorerPage';
import { AutopsyPage } from './pages/AutopsyPage';

export const App: React.FC = () => {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<AppLayout />}>
          <Route index element={<BatchesPage />} />
          <Route path="import" element={<ImportPage />} />
          <Route path="experiments" element={<ExplorerPage />} />
          <Route path="autopsy" element={<AutopsyPage />} />
          <Route path="autopsy/:batchId" element={<AutopsyPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
};

export default App;
