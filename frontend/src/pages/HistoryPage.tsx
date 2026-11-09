import React, { useState, useEffect, useCallback } from 'react';
import { getAnalyses } from '../api/client';
import type { AnalysisSummary } from '../api/types';
import { ScoreBadge } from '../components/ScoreBadge';
import { DetailModal } from '../components/DetailModal';

interface HistoryPageProps {
  onNavigateToScreen?: () => void;
}

export const HistoryPage: React.FC<HistoryPageProps> = ({ onNavigateToScreen }) => {
  const [items, setItems] = useState<AnalysisSummary[]>([]);
  const [total, setTotal] = useState<number>(0);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Filters & Pagination
  const [searchTerm, setSearchTerm] = useState<string>('');
  const [scoreFilter, setScoreFilter] = useState<'all' | 'high' | 'mid' | 'low'>('all');
  const [page, setPage] = useState<number>(1);
  const pageSize = 10;

  // Modal State
  const [selectedAnalysisId, setSelectedAnalysisId] = useState<number | null>(null);
  const [isModalOpen, setIsModalOpen] = useState<boolean>(false);

  const fetchHistory = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);

      let minScore: number | undefined;
      let maxScore: number | undefined;

      if (scoreFilter === 'high') {
        minScore = 80;
      } else if (scoreFilter === 'mid') {
        minScore = 50;
        maxScore = 79;
      } else if (scoreFilter === 'low') {
        maxScore = 49;
      }

      const res = await getAnalyses({
        offset: (page - 1) * pageSize,
        limit: pageSize,
        search: searchTerm.trim() || undefined,
        min_score: minScore,
        max_score: maxScore,
      });

      setItems(res.items);
      setTotal(res.total);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch candidate history');
    } finally {
      setLoading(false);
    }
  }, [page, searchTerm, scoreFilter]);

  useEffect(() => {
    fetchHistory();
  }, [fetchHistory]);

  const handleRowClick = (id: number) => {
    setSelectedAnalysisId(id);
    setIsModalOpen(true);
  };

  const handleAnalysisDeleted = () => {
    fetchHistory();
  };

  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  // Compute quick aggregate stats from current dataset
  const averageScore = items.length
    ? Math.round(items.reduce((acc, curr) => acc + curr.match_score, 0) / items.length)
    : 0;

  const highMatches = items.filter((i) => i.match_score >= 80).length;

  return (
    <div>
      {/* Top Header */}
      <div className="page-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '16px' }}>
        <div>
          <h1 className="page-title">Candidate Screening History</h1>
          <p className="page-subtitle">
            Review past candidate evaluations, filter by score tiers, and inspect structured match dossiers.
          </p>
        </div>

        {onNavigateToScreen && (
          <button
            type="button"
            className="btn btn-primary"
            onClick={onNavigateToScreen}
          >
            New Screening
          </button>
        )}
      </div>

      {/* Metrics Stat Cards (Compact & Minimal) */}
      <div className="stats-grid" style={{ gap: '12px', marginBottom: '20px' }}>
        <div className="stat-card" style={{ padding: '12px 16px' }}>
          <div>
            <div className="stat-label" style={{ fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
              Total Screenings
            </div>
            <div className="stat-value" style={{ fontSize: '22px', marginTop: '2px' }}>{total}</div>
          </div>
        </div>

        <div className="stat-card" style={{ padding: '12px 16px' }}>
          <div>
            <div className="stat-label" style={{ fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
              Avg. Match Score
            </div>
            <div className="stat-value" style={{ fontSize: '22px', marginTop: '2px' }}>
              {items.length ? `${averageScore}%` : '—'}
            </div>
          </div>
        </div>

        <div className="stat-card" style={{ padding: '12px 16px' }}>
          <div>
            <div className="stat-label" style={{ fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
              High Matches (≥80)
            </div>
            <div className="stat-value" style={{ fontSize: '22px', marginTop: '2px', color: 'var(--score-high-text)' }}>
              {highMatches}
            </div>
          </div>
        </div>

        <div className="stat-card" style={{ padding: '12px 16px' }}>
          <div>
            <div className="stat-label" style={{ fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
              Filter Results
            </div>
            <div className="stat-value" style={{ fontSize: '22px', marginTop: '2px' }}>
              {items.length}
            </div>
          </div>
        </div>
      </div>

      {/* Search and Filters Toolbar */}
      <div
        className="card"
        style={{
          padding: '12px 16px',
          marginBottom: '20px',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          flexWrap: 'wrap',
          gap: '14px',
        }}
      >
        {/* Search by Candidate Name */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flex: '1', minWidth: '240px' }}>
          <div style={{ position: 'relative', width: '100%', maxWidth: '360px' }}>
            <input
              type="text"
              className="form-input"
              placeholder="Search candidate name..."
              value={searchTerm}
              onChange={(e) => {
                setSearchTerm(e.target.value);
                setPage(1);
              }}
              style={{ padding: '8px 12px' }}
            />
            {searchTerm && (
              <button
                type="button"
                onClick={() => {
                  setSearchTerm('');
                  setPage(1);
                }}
                style={{
                  position: 'absolute',
                  right: '10px',
                  top: '50%',
                  transform: 'translateY(-50%)',
                  background: 'transparent',
                  border: 'none',
                  color: 'var(--text-subtle)',
                  cursor: 'pointer',
                  fontSize: '12px',
                  fontWeight: 600,
                }}
              >
                Clear
              </button>
            )}
          </div>
        </div>

        {/* Score Tier Filter Tabs (Compact & Minimal) */}
        <div style={{ display: 'flex', gap: '6px', alignItems: 'center' }}>
          <span
            style={{
              fontSize: '11px',
              color: 'var(--text-subtle)',
              fontWeight: 600,
              textTransform: 'uppercase',
              letterSpacing: '0.5px',
              marginRight: '2px',
            }}
          >
            Score Tier:
          </span>
          <button
            type="button"
            className={`btn ${scoreFilter === 'all' ? 'btn-primary' : 'btn-secondary'}`}
            style={{ fontSize: '11px', padding: '4px 9px', borderRadius: '6px' }}
            onClick={() => {
              setScoreFilter('all');
              setPage(1);
            }}
          >
            All
          </button>
          <button
            type="button"
            className={`btn ${scoreFilter === 'high' ? 'btn-primary' : 'btn-secondary'}`}
            style={{ fontSize: '11px', padding: '4px 9px', borderRadius: '6px' }}
            onClick={() => {
              setScoreFilter('high');
              setPage(1);
            }}
          >
            ≥ 80 High
          </button>
          <button
            type="button"
            className={`btn ${scoreFilter === 'mid' ? 'btn-primary' : 'btn-secondary'}`}
            style={{ fontSize: '11px', padding: '4px 9px', borderRadius: '6px' }}
            onClick={() => {
              setScoreFilter('mid');
              setPage(1);
            }}
          >
            50–79 Moderate
          </button>
          <button
            type="button"
            className={`btn ${scoreFilter === 'low' ? 'btn-primary' : 'btn-secondary'}`}
            style={{ fontSize: '11px', padding: '4px 9px', borderRadius: '6px' }}
            onClick={() => {
              setScoreFilter('low');
              setPage(1);
            }}
          >
            &lt; 50 Review
          </button>
        </div>
      </div>

      {/* Error Message */}
      {error && (
        <div className="alert alert-error" role="alert">
          <strong>Error:</strong> {error}
        </div>
      )}

      {/* Main Table Card */}
      <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
        <div className="table-container">
          <table className="data-table">
            <thead>
              <tr>
                <th style={{ width: '25%' }}>Candidate Name</th>
                <th style={{ width: '25%' }}>Target Role</th>
                <th style={{ width: '20%' }}>Match Score</th>
                <th style={{ width: '18%' }}>Screened Date</th>
                <th style={{ width: '12%', textAlign: 'right' }}>Action</th>
              </tr>
            </thead>
            <tbody>
              {loading && items.length === 0 ? (
                <tr>
                  <td colSpan={5} style={{ textAlign: 'center', padding: '40px 0', color: 'var(--text-muted)' }}>
                    Loading candidate records...
                  </td>
                </tr>
              ) : items.length === 0 ? (
                <tr>
                  <td colSpan={5} style={{ textAlign: 'center', padding: '48px 16px', color: 'var(--text-muted)' }}>
                    <div style={{ fontSize: '15px', fontWeight: 600, color: 'var(--text-main)' }}>
                      No screening records found
                    </div>
                    <div style={{ fontSize: '13px', marginTop: '4px' }}>
                      {searchTerm || scoreFilter !== 'all'
                        ? 'Try clearing your search query or adjusting your score filters.'
                        : 'Screen your first candidate to start building your talent pipeline.'}
                    </div>
                  </td>
                </tr>
              ) : (
                items.map((item) => (
                  <tr
                    key={item.id}
                    onClick={() => handleRowClick(item.id)}
                    style={{ cursor: 'pointer' }}
                  >
                    <td>
                      <div style={{ fontWeight: 600, color: 'var(--text-main)' }}>
                        {item.candidate_name}
                      </div>
                      <div style={{ fontSize: '11px', color: 'var(--text-subtle)' }}>
                        ID #{item.id}
                      </div>
                    </td>
                    <td>
                      <div style={{ color: 'var(--text-main)', fontWeight: 500 }}>
                        {item.job_title || <span style={{ color: 'var(--text-subtle)' }}>General Assessment</span>}
                      </div>
                    </td>
                    <td>
                      <ScoreBadge score={item.match_score} />
                    </td>
                    <td>
                      <span style={{ fontSize: '13px', color: 'var(--text-muted)' }}>
                        {new Date(item.created_at).toLocaleDateString(undefined, {
                          year: 'numeric',
                          month: 'short',
                          day: 'numeric',
                        })}
                      </span>
                    </td>
                    <td style={{ textAlign: 'right' }}>
                      <button
                        type="button"
                        className="btn btn-secondary"
                        style={{ fontSize: '11px', fontWeight: 400, padding: '4px 10px' }}
                        onClick={(e) => {
                          e.stopPropagation();
                          handleRowClick(item.id);
                        }}
                      >
                        Inspect Dossier
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination Footer */}
        <div
          style={{
            padding: '14px 20px',
            borderTop: '1px solid var(--border-light)',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            backgroundColor: '#ffffff',
            flexWrap: 'wrap',
            gap: '12px',
          }}
        >
          <div style={{ fontSize: '13px', color: 'var(--text-muted)' }}>
            Showing {items.length > 0 ? (page - 1) * pageSize + 1 : 0} to{' '}
            {Math.min(page * pageSize, total)} of {total} Candidate Entries
          </div>

          <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
            <button
              type="button"
              className="btn btn-secondary"
              style={{ fontSize: '12px', padding: '5px 12px' }}
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page <= 1 || loading}
            >
              Previous
            </button>
            <span style={{ fontSize: '13px', color: 'var(--text-muted)', padding: '0 6px' }}>
              Page {page} of {totalPages}
            </span>
            <button
              type="button"
              className="btn btn-secondary"
              style={{ fontSize: '12px', padding: '5px 12px' }}
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              disabled={page >= totalPages || loading}
            >
              Next
            </button>
          </div>
        </div>
      </div>

      {/* Dossier Modal */}
      <DetailModal
        isOpen={isModalOpen}
        analysisId={selectedAnalysisId}
        onClose={() => {
          setIsModalOpen(false);
          setSelectedAnalysisId(null);
        }}
        onDeleted={handleAnalysisDeleted}
      />
    </div>
  );
};
