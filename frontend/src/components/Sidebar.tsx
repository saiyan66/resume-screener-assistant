import React from 'react';

export type NavTab = 'analyze' | 'history';

interface SidebarProps {
  activeTab: NavTab;
  onTabChange: (tab: NavTab) => void;
  historyCount?: number;
}

export const Sidebar: React.FC<SidebarProps> = ({
  activeTab,
  onTabChange,
  historyCount,
}) => {
  return (
    <aside className="sidebar">
      {/* Brand Header */}
      <div className="sidebar-brand">
        <div className="sidebar-logo" aria-hidden="true">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2" />
            <circle cx="9" cy="7" r="4" />
            <path d="M22 21v-2a4 4 0 0 0-3-3.87" />
            <path d="M16 3.13a4 4 0 0 1 0 7.75" />
          </svg>
        </div>
        <div>
          <div className="sidebar-title">Synthweb HR</div>
          <div style={{ fontSize: '11px', color: 'var(--text-subtle)', fontWeight: 500 }}>
            Resume Screener
          </div>
        </div>
      </div>

      {/* Navigation Links */}
      <nav>
        <div style={{ fontSize: '11px', fontWeight: 600, color: 'var(--text-subtle)', textTransform: 'uppercase', letterSpacing: '0.6px', padding: '0 12px 10px 12px' }}>
          Workflows
        </div>
        <ul className="sidebar-menu">
          <li>
            <button
              type="button"
              className={`sidebar-btn ${activeTab === 'analyze' ? 'active' : ''}`}
              onClick={() => onTabChange('analyze')}
            >
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                <polyline points="14 2 14 8 20 8" />
                <line x1="16" y1="13" x2="8" y2="13" />
                <line x1="16" y1="17" x2="8" y2="17" />
                <polyline points="10 9 9 9 8 9" />
              </svg>
              <span>Screen Candidate</span>
            </button>
          </li>
          <li>
            <button
              type="button"
              className={`sidebar-btn ${activeTab === 'history' ? 'active' : ''}`}
              onClick={() => onTabChange('history')}
            >
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="12" cy="12" r="10" />
                <polyline points="12 6 12 12 16 14" />
              </svg>
              <span>Screening History</span>
              {typeof historyCount === 'number' && historyCount > 0 && (
                <span
                  style={{
                    marginLeft: 'auto',
                    fontSize: '11px',
                    fontWeight: 700,
                    padding: '2px 7px',
                    borderRadius: '10px',
                    backgroundColor: activeTab === 'history' ? 'var(--primary)' : 'var(--bg-subtle)',
                    color: activeTab === 'history' ? '#ffffff' : 'var(--text-muted)',
                  }}
                >
                  {historyCount}
                </span>
              )}
            </button>
          </li>
        </ul>
      </nav>

      {/* Footer Info */}
      <div style={{ marginTop: 'auto', padding: '16px 8px 0 8px', borderTop: '1px solid var(--border-light)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '12px', color: 'var(--text-muted)' }}>
          <span style={{ width: '8px', height: '8px', borderRadius: '50%', backgroundColor: '#10b981', display: 'inline-block' }} />
          <span>Local Engine · SQLite</span>
        </div>
      </div>
    </aside>
  );
};

