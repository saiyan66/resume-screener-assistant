import React, { useEffect, useState } from 'react';
import { getAnalysisById, deleteAnalysis } from '../api/client';
import type { AnalysisDetail } from '../api/types';
import { ReportCard } from './ReportCard';

interface DetailModalProps {
  isOpen: boolean;
  analysisId: number | null;
  onClose: () => void;
  onDeleted?: (id: number) => void;
}

export const DetailModal: React.FC<DetailModalProps> = ({
  isOpen,
  analysisId,
  onClose,
  onDeleted,
}) => {
  const [detail, setDetail] = useState<AnalysisDetail | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [deleting, setDeleting] = useState<boolean>(false);
  const [showJd, setShowJd] = useState<boolean>(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState<boolean>(false);

  useEffect(() => {
    if (!isOpen || analysisId === null) {
      setDetail(null);
      setError(null);
      setShowJd(false);
      setShowDeleteConfirm(false);
      return;
    }

    let isMounted = true;
    setLoading(true);
    setError(null);

    getAnalysisById(analysisId)
      .then((data) => {
        if (isMounted) {
          setDetail(data);
          setLoading(false);
        }
      })
      .catch((err) => {
        if (isMounted) {
          setError(err instanceof Error ? err.message : 'Failed to load candidate screening details.');
          setLoading(false);
        }
      });

    return () => {
      isMounted = false;
    };
  }, [isOpen, analysisId]);

  // Handle ESC key press to close modal
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen) {
        onClose();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  const executeDelete = async () => {
    if (!detail) return;
    try {
      setDeleting(true);
      await deleteAnalysis(detail.id);
      if (onDeleted) {
        onDeleted(detail.id);
      }
      setShowDeleteConfirm(false);
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete candidate analysis.');
      setDeleting(false);
      setShowDeleteConfirm(false);
    }
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      style={{
        position: 'fixed',
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        backgroundColor: 'rgba(15, 23, 42, 0.65)',
        backdropFilter: 'blur(3px)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 1000,
        padding: '20px',
      }}
      onClick={(e) => {
        if (e.target === e.currentTarget && !showDeleteConfirm) {
          onClose();
        }
      }}
    >
      <div
        style={{
          backgroundColor: '#ffffff',
          borderRadius: '16px',
          width: '100%',
          maxWidth: '850px',
          maxHeight: '90vh',
          display: 'flex',
          flexDirection: 'column',
          boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.2), 0 8px 10px -6px rgba(0, 0, 0, 0.1)',
          overflow: 'hidden',
          animation: 'modalSlideIn 0.2s ease-out',
          position: 'relative',
        }}
      >
        {/* Minimal Delete Confirmation Overlay */}
        {showDeleteConfirm && detail && (
          <div
            style={{
              position: 'absolute',
              top: 0,
              left: 0,
              right: 0,
              bottom: 0,
              backgroundColor: 'rgba(15, 23, 42, 0.45)',
              backdropFilter: 'blur(2px)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              zIndex: 20,
              padding: '20px',
            }}
          >
            <div
              style={{
                backgroundColor: '#ffffff',
                borderRadius: '12px',
                border: '1px solid #e2e8f0',
                boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.15)',
                padding: '22px 24px',
                maxWidth: '420px',
                width: '100%',
              }}
            >
              <div style={{ fontSize: '16px', fontWeight: 600, color: '#1e293b', marginBottom: '8px' }}>
                Delete Screening Record?
              </div>
              <p style={{ fontSize: '13px', color: '#64748b', lineHeight: 1.5, margin: '0 0 20px 0' }}>
                Are you sure you want to permanently delete the screening record for{' '}
                <strong style={{ color: '#1e293b' }}>{detail.candidate_name}</strong>? This action cannot be undone.
              </p>
              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px' }}>
                <button
                  type="button"
                  className="btn btn-secondary"
                  style={{ fontSize: '12px', padding: '6px 14px', fontWeight: 500 }}
                  onClick={() => setShowDeleteConfirm(false)}
                  disabled={deleting}
                >
                  Cancel
                </button>
                <button
                  type="button"
                  className="btn btn-danger"
                  style={{ fontSize: '12px', padding: '6px 14px', fontWeight: 500 }}
                  onClick={executeDelete}
                  disabled={deleting}
                >
                  {deleting ? 'Deleting...' : 'Delete Record'}
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Modal Header */}
        <div
          style={{
            padding: '18px 24px',
            borderBottom: '1px solid var(--border-light)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            backgroundColor: '#ffffff',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <span
              style={{
                width: '10px',
                height: '10px',
                borderRadius: '50%',
                backgroundColor: 'var(--primary)',
                display: 'inline-block',
              }}
            />
            <h3 style={{ fontSize: '17px', fontWeight: 700, color: 'var(--text-main)', margin: 0 }}>
              Candidate Screening Dossier
            </h3>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            {detail && (
              <button
                type="button"
                className="btn btn-danger"
                style={{ fontSize: '12px', padding: '6px 12px' }}
                onClick={() => setShowDeleteConfirm(true)}
                disabled={deleting}
              >
                Delete Record
              </button>
            )}
            <button
              type="button"
              onClick={onClose}
              style={{
                background: 'transparent',
                border: 'none',
                color: 'var(--text-muted)',
                cursor: 'pointer',
                padding: '6px',
                borderRadius: '6px',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}
              aria-label="Close modal"
            >
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <line x1="18" y1="6" x2="6" y2="18" />
                <line x1="6" y1="6" x2="18" y2="18" />
              </svg>
            </button>
          </div>
        </div>

        {/* Modal Body */}
        <div style={{ padding: '24px', overflowY: 'auto', flex: 1 }}>
          {loading && (
            <div style={{ textAlign: 'center', padding: '60px 0', color: 'var(--text-muted)' }}>
              <div
                style={{
                  width: '36px',
                  height: '36px',
                  border: '3px solid var(--border-light)',
                  borderTopColor: 'var(--primary)',
                  borderRadius: '50%',
                  animation: 'spin 1s linear infinite',
                  margin: '0 auto 16px auto',
                }}
              />
              <p style={{ fontSize: '14px', fontWeight: 500 }}>Loading screening report...</p>
            </div>
          )}

          {error && (
            <div className="alert alert-error" role="alert">
              <span>{error}</span>
            </div>
          )}

          {detail && !loading && (
            <div>
              <ReportCard
                report={detail.report}
                candidateName={detail.candidate_name}
                jobTitle={detail.job_title}
                inputTruncated={detail.input_truncated}
                createdAt={detail.created_at}
              />

              {/* Collapsible JD Snapshot */}
              <div style={{ marginTop: '20px', borderTop: '1px solid var(--border-light)', paddingTop: '16px' }}>
                <button
                  type="button"
                  className="btn btn-secondary"
                  style={{ width: '100%', justifyContent: 'space-between', fontSize: '13px' }}
                  onClick={() => setShowJd((prev) => !prev)}
                >
                  <span style={{ fontWeight: 600 }}>Original Job Description Snapshot</span>
                  <span>{showJd ? '▲ Hide' : '▼ View Full JD'}</span>
                </button>

                {showJd && (
                  <div
                    style={{
                      marginTop: '12px',
                      padding: '16px',
                      backgroundColor: '#f8fafc',
                      borderRadius: 'var(--radius-md)',
                      border: '1px solid var(--border-light)',
                      fontSize: '13px',
                      lineHeight: '1.6',
                      color: 'var(--text-main)',
                      whiteSpace: 'pre-wrap',
                      maxHeight: '260px',
                      overflowY: 'auto',
                    }}
                  >
                    {detail.job_description}
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

