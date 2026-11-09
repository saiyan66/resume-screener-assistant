import { useState, useEffect, useCallback } from 'react';
import { Sidebar, type NavTab } from './components/Sidebar';
import { AnalyzePage } from './pages/AnalyzePage';
import { HistoryPage } from './pages/HistoryPage';
import { getAnalyses } from './api/client';

export function App() {
  const [activeTab, setActiveTab] = useState<NavTab>('analyze');
  const [historyCount, setHistoryCount] = useState<number>(0);

  const refreshTotalCount = useCallback(async () => {
    try {
      const data = await getAnalyses({ limit: 1 });
      setHistoryCount(data.total);
    } catch {
    }
  }, []);

  useEffect(() => {
    refreshTotalCount();
  }, [refreshTotalCount]);

  return (
    <div className="app-container">
    
      <Sidebar
        activeTab={activeTab}
        onTabChange={setActiveTab}
        historyCount={historyCount}
      />

   
      <main className="main-content">
        {activeTab === 'analyze' ? (
          <AnalyzePage
            onAnalysisSuccess={() => {
              refreshTotalCount();
            }}
            onNavigateToHistory={() => {
              setActiveTab('history');
            }}
          />
        ) : (
          <HistoryPage
            onNavigateToScreen={() => {
              setActiveTab('analyze');
            }}
          />
        )}
      </main>
    </div>
  );
}

export default App;
