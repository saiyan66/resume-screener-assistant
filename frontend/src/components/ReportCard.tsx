import React, { useState } from 'react';
import type { MatchReport } from '../api/types';
import { ScoreBadge } from './ScoreBadge';

interface ReportCardProps {
  report: MatchReport;
  candidateName: string;
  jobTitle?: string | null;
  inputTruncated?: boolean;
  createdAt?: string;
}

export const ReportCard: React.FC<ReportCardProps> = ({
  report,
  candidateName,
  jobTitle,
  inputTruncated,
  createdAt,
}) => {
  const [copiedIndex, setCopiedIndex] = useState<number | null>(null);
  const [allCopied, setAllCopied] = useState<boolean>(false);

  const copyQuestion = (text: string, index: number) => {
    navigator.clipboard.writeText(text);
    setCopiedIndex(index);
    setTimeout(() => setCopiedIndex(null), 2000);
  };

  const copyAllQuestions = () => {
    const formatted = report.interview_questions
      .map((q, idx) => `${idx + 1}. ${q}`)
      .join('\n\n');
    navigator.clipboard.writeText(formatted);
    setAllCopied(true);
    setTimeout(() => setAllCopied(false), 2000);
  };

  const formattedDate = createdAt
    ? new Date(createdAt).toLocaleDateString(undefined, {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
      })
    : null;

  return (
    <div className="card" style={{ padding: '28px', border: '1px solid var(--border-light)', boxShadow: 'var(--shadow-md)' }}>
      {/* Truncation warning if document exceeded token budget */}
      {inputTruncated && (
        <div className="alert alert-warning" role="alert" style={{ marginBottom: '20px' }}>
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z" />
            <line x1="12" y1="9" x2="12" y2="13" />
            <line x1="12" y1="17" x2="12.01" y2="17" />
          </svg>
          <div>
            <strong>Document Truncated:</strong> The Job Description or Resume exceeded the 8,000-character safety limit and was truncated prior to analysis.
          </div>
        </div>
      )}

      {/* Header with Candidate Name, Job Title, and Match Score */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid var(--border-light)', paddingBottom: '16px', marginBottom: '20px', flexWrap: 'wrap', gap: '14px' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <h2 style={{ fontSize: '20px', fontWeight: 600, color: '#1e293b', margin: 0 }}>
              {candidateName || report.candidate_name || 'Candidate'}
            </h2>
            <ScoreBadge score={report.match_score} />
          </div>
          {jobTitle && (
            <div style={{ fontSize: '13px', color: '#64748b', marginTop: '3px', fontWeight: 400 }}>
              Role: <span style={{ color: '#334155', fontWeight: 500 }}>{jobTitle}</span>
            </div>
          )}
          {formattedDate && (
            <div style={{ fontSize: '11px', color: '#94a3b8', marginTop: '2px' }}>
              Screened on {formattedDate}
            </div>
          )}
        </div>

        {/* Compact & Subtle Score Widget (Expanded Box Dimensions, Unchanged Font Sizes) */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '18px',
            backgroundColor: '#f8fafc',
            border: '1px solid #e2e8f0',
            padding: '10px 22px',
            borderRadius: '10px',
            boxShadow: '0 1px 2px rgba(0, 0, 0, 0.03)',
          }}
        >
          <div style={{ display: 'flex', flexDirection: 'column' }}>
            <span
              style={{
                fontSize: '10px',
                fontWeight: 500,
                color: '#64748b',
                textTransform: 'uppercase',
                letterSpacing: '0.4px',
                lineHeight: 1,
              }}
            >
              Match Score
            </span>
            <div style={{ display: 'flex', alignItems: 'baseline', gap: '2px', marginTop: '4px' }}>
              <span style={{ fontSize: '16px', fontWeight: 600, color: '#1e293b', lineHeight: 1 }}>
                {report.match_score}
              </span>
              <span style={{ fontSize: '11px', fontWeight: 400, color: '#94a3b8', lineHeight: 1 }}>
                /100
              </span>
            </div>
          </div>

          <div
            style={{
              width: '64px',
              height: '6px',
              backgroundColor: '#e2e8f0',
              borderRadius: '9999px',
              overflow: 'hidden',
            }}
          >
            <div
              style={{
                width: `${report.match_score}%`,
                height: '100%',
                backgroundColor:
                  report.match_score >= 90
                    ? '#059669'
                    : report.match_score >= 70
                    ? '#2563eb'
                    : report.match_score >= 50
                    ? '#d97706'
                    : '#dc2626',
                transition: 'width 0.4s ease',
              }}
            />
          </div>
        </div>
      </div>

      {/* Two Column Grid: Matching Skills & Identified Gaps */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '20px', marginBottom: '28px' }}>
        {/* Matching Skills */}
        <div style={{ background: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: 'var(--radius-md)', padding: '18px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '14px' }}>
            <div style={{ width: '22px', height: '22px', borderRadius: '50%', backgroundColor: '#ecfdf5', color: '#059669', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              ✓
            </div>
            <h4 style={{ fontSize: '14px', fontWeight: 700, color: '#065f46', margin: 0 }}>
              Top Matching Skills ({report.matching_skills.length})
            </h4>
          </div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
            {report.matching_skills.map((skill, index) => (
              <span
                key={index}
                style={{
                  backgroundColor: '#ffffff',
                  color: '#0f172a',
                  border: '1px solid #cbd5e1',
                  borderRadius: '6px',
                  padding: '6px 12px',
                  fontSize: '13px',
                  fontWeight: 500,
                  boxShadow: '0 1px 2px rgba(0,0,0,0.03)',
                }}
              >
                {skill}
              </span>
            ))}
          </div>
        </div>

        {/* Identified Gaps */}
        <div style={{ background: '#fffbeb', border: '1px solid #fef3c7', borderRadius: 'var(--radius-md)', padding: '18px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '14px' }}>
            <div style={{ width: '22px', height: '22px', borderRadius: '50%', backgroundColor: '#fef3c7', color: '#b45309', display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 'bold' }}>
              !
            </div>
            <h4 style={{ fontSize: '14px', fontWeight: 700, color: '#92400e', margin: 0 }}>
              Identified Candidate Gaps ({report.gaps.length})
            </h4>
          </div>
          <ul style={{ listStyle: 'none', padding: 0, margin: 0, display: 'flex', flexDirection: 'column', gap: '8px' }}>
            {report.gaps.map((gap, index) => (
              <li
                key={index}
                style={{
                  fontSize: '13px',
                  lineHeight: '1.5',
                  color: '#78350f',
                  backgroundColor: '#ffffff',
                  padding: '8px 12px',
                  borderRadius: '6px',
                  border: '1px solid #fde68a',
                  display: 'flex',
                  alignItems: 'flex-start',
                  gap: '8px',
                }}
              >
                <span style={{ color: '#d97706', fontWeight: 700 }}>•</span>
                <span>{gap}</span>
              </li>
            ))}
          </ul>
        </div>
      </div>

      {/* Suggested Interview Questions */}
      <div>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px' }}>
          <h3 style={{ fontSize: '14px', fontWeight: 700, color: 'var(--text-main)', textTransform: 'uppercase', letterSpacing: '0.5px', margin: 0 }}>
            Targeted Interview Questions ({report.interview_questions.length})
          </h3>
          <button
            type="button"
            className="btn btn-secondary"
            style={{ fontSize: '12px', padding: '6px 12px' }}
            onClick={copyAllQuestions}
          >
            {allCopied ? '✓ Copied All' : 'Copy All Questions'}
          </button>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
          {report.interview_questions.map((question, index) => (
            <div
              key={index}
              style={{
                display: 'flex',
                alignItems: 'flex-start',
                justifyContent: 'space-between',
                gap: '12px',
                backgroundColor: 'var(--bg-subtle)',
                padding: '14px 16px',
                borderRadius: 'var(--radius-md)',
                border: '1px solid var(--border-light)',
              }}
            >
              <div style={{ display: 'flex', gap: '12px', alignItems: 'flex-start' }}>
                <span
                  style={{
                    width: '24px',
                    height: '24px',
                    borderRadius: '50%',
                    backgroundColor: 'var(--primary-light)',
                    color: 'var(--primary)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    fontSize: '12px',
                    fontWeight: 700,
                    flexShrink: 0,
                  }}
                >
                  {index + 1}
                </span>
                <p style={{ margin: 0, fontSize: '14px', color: 'var(--text-main)', lineHeight: '1.5' }}>
                  {question}
                </p>
              </div>
              <button
                type="button"
                className="btn btn-secondary"
                style={{ fontSize: '11px', padding: '4px 8px', flexShrink: 0 }}
                onClick={() => copyQuestion(question, index)}
              >
                {copiedIndex === index ? '✓ Copied' : 'Copy'}
              </button>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
