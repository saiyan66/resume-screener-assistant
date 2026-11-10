import React, { useState, useRef } from 'react';
import { createAnalysis, uploadResumeFile } from '../api/client';
import type { AnalysisDetail } from '../api/types';
import { ReportCard } from '../components/ReportCard';

interface AnalyzePageProps {
  onAnalysisSuccess?: (analysis: AnalysisDetail) => void;
  onNavigateToHistory?: () => void;
}

const MAX_CHARS = 4000;

const SAMPLE_JD = `Role: Senior Backend Engineer (Python / FastAPI)
Requirements:
- 4+ years experience with Python, FastAPI, and asynchronous APIs.
- Production experience with PostgreSQL, SQLite, and SQLAlchemy ORM.
- Hands-on integration with LLM APIs (Groq, OpenAI) using structured outputs.
- Familiarity with Docker and basic CI/CD automation.
Nice to have: React, Celery, or Redis.`;

const SAMPLE_RESUME = `Alex Rivera — Senior Backend Engineer
Email: alex.rivera@example.com | Location: Remote

Summary:
Backend engineer with 5 years building scalable Python services and LLM integrations.

Core Skills:
Python, FastAPI, PostgreSQL, SQLite, SQLAlchemy, Groq SDK, Docker, Git.

Experience:
Senior Software Engineer (2021-Present)
- Developed asynchronous FastAPI REST APIs handling LLM document processing pipelines.
- Implemented structured Pydantic JSON schemas with Groq and OpenAI.
- Optimized database queries and indexed SQLite/PostgreSQL schemas.

Education:
B.S. in Computer Science (2020)`;

export const AnalyzePage: React.FC<AnalyzePageProps> = ({
  onAnalysisSuccess,
  onNavigateToHistory,
}) => {
  const [jobTitle, setJobTitle] = useState('');
  const [candidateNameOverride, setCandidateNameOverride] = useState('');
  const [jobDescription, setJobDescription] = useState('');
  const [resumeText, setResumeText] = useState('');

  const [jdUploading, setJdUploading] = useState(false);
  const [resumeUploading, setResumeUploading] = useState(false);
  const [analyzing, setAnalyzing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [currentAnalysis, setCurrentAnalysis] = useState<AnalysisDetail | null>(null);

  const jdFileInputRef = useRef<HTMLInputElement>(null);
  const resumeFileInputRef = useRef<HTMLInputElement>(null);
  const resultRef = useRef<HTMLDivElement>(null);

  const handleJdFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    try {
      setJdUploading(true);
      setError(null);
      const parsed = await uploadResumeFile(file);
      setJobDescription(parsed.text);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to extract text from JD file');
    } finally {
      setJdUploading(false);
      if (jdFileInputRef.current) jdFileInputRef.current.value = '';
    }
  };

  const handleResumeFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    try {
      setResumeUploading(true);
      setError(null);
      const parsed = await uploadResumeFile(file);
      setResumeText(parsed.text);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to extract text from Resume file');
    } finally {
      setResumeUploading(false);
      if (resumeFileInputRef.current) resumeFileInputRef.current.value = '';
    }
  };

  const loadSampleData = () => {
    setJobTitle('Senior Backend Engineer');
    setJobDescription(SAMPLE_JD);
    setResumeText(SAMPLE_RESUME);
    setCandidateNameOverride('');
    setError(null);
  };

  const handleClearAll = () => {
    setJobTitle('');
    setCandidateNameOverride('');
    setJobDescription('');
    setResumeText('');
    setCurrentAnalysis(null);
    setError(null);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!jobDescription.trim()) {
      setError('Please provide a Job Description.');
      return;
    }
    if (!resumeText.trim()) {
      setError('Please provide Candidate Resume text.');
      return;
    }

    try {
      setAnalyzing(true);
      setError(null);
      setCurrentAnalysis(null);

      const analysis = await createAnalysis({
        job_description: jobDescription.trim(),
        resume_text: resumeText.trim(),
        job_title: jobTitle.trim() || undefined,
        candidate_name: candidateNameOverride.trim() || undefined,
      });

      setCurrentAnalysis(analysis);
      if (onAnalysisSuccess) {
        onAnalysisSuccess(analysis);
      }

      // Smooth scroll to the result
      setTimeout(() => {
        resultRef.current?.scrollIntoView({ behavior: 'smooth' });
      }, 100);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred during screening analysis.');
    } finally {
      setAnalyzing(false);
    }
  };

  return (
    <div>
      {/* Top Page Header */}
      <div className="page-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '16px' }}>
        <div>
          <h1 className="page-title">Screen Candidate</h1>
          <p className="page-subtitle">
            Upload or paste a Job Description and Candidate Resume to generate a structured AI match evaluation.
          </p>
        </div>

        <div style={{ display: 'flex', gap: '10px' }}>
          <button
            type="button"
            className="btn btn-secondary"
            onClick={loadSampleData}
            title="Load sample Job Description and Resume for instant testing"
          >
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2" />
              <rect x="8" y="2" width="8" height="4" rx="1" ry="1" />
            </svg>
            <span>Load Sample Data</span>
          </button>
          <button
            type="button"
            className="btn btn-secondary"
            onClick={handleClearAll}
          >
            Clear All
          </button>
        </div>
      </div>

      {/* Error Banner */}
      {error && (
        <div className="alert alert-error" role="alert">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <circle cx="12" cy="12" r="10" />
            <line x1="12" y1="8" x2="12" y2="12" />
            <line x1="12" y1="16" x2="12.01" y2="16" />
          </svg>
          <div>
            <strong>Error:</strong> {error}
          </div>
        </div>
      )}

      {/* Two-Column Input Form */}
      <form onSubmit={handleSubmit}>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(340px, 1fr))', gap: '24px', marginBottom: '24px' }}>
          {/* Column 1: Job Description */}
          <div className="card" style={{ marginBottom: 0 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <div style={{ width: '28px', height: '28px', borderRadius: '6px', backgroundColor: 'var(--primary-light)', color: 'var(--primary)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 700, fontSize: '13px' }}>
                  1
                </div>
                <h2 className="card-title" style={{ margin: 0 }}>Job Description (JD)</h2>
              </div>

              {/* Upload JD File Button */}
              <div>
                <input
                  type="file"
                  ref={jdFileInputRef}
                  style={{ display: 'none' }}
                  accept=".pdf,.docx,.txt"
                  onChange={handleJdFileUpload}
                />
                <button
                  type="button"
                  className="btn btn-secondary"
                  style={{ fontSize: '12px', padding: '5px 10px' }}
                  onClick={() => jdFileInputRef.current?.click()}
                  disabled={jdUploading}
                >
                  {jdUploading ? 'Extracting...' : '📁 Upload JD'}
                </button>
              </div>
            </div>

            <div className="form-group">
              <label className="form-label" htmlFor="job-title-input">
                Job Title <span style={{ color: 'var(--text-subtle)', fontWeight: 400 }}>(Optional)</span>
              </label>
              <input
                id="job-title-input"
                type="text"
                className="form-input"
                placeholder="e.g. Senior Backend Engineer"
                value={jobTitle}
                onChange={(e) => setJobTitle(e.target.value)}
              />
            </div>

            <div className="form-group">
              <div className="form-label">
                <span>Job Description Text *</span>
                <span style={{ fontSize: '11px', color: jobDescription.length > MAX_CHARS ? '#dc2626' : 'var(--text-subtle)', fontWeight: 500 }}>
                  {jobDescription.length.toLocaleString()} / {MAX_CHARS.toLocaleString()} chars
                  {jobDescription.length > MAX_CHARS && ' (will be truncated)'}
                </span>
              </div>
              <textarea
                className="form-textarea"
                style={{ minHeight: '260px' }}
                placeholder="Paste the target job description or requirements here..."
                value={jobDescription}
                onChange={(e) => setJobDescription(e.target.value)}
                required
              />
            </div>
          </div>

          {/* Column 2: Candidate Resume */}
          <div className="card" style={{ marginBottom: 0 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <div style={{ width: '28px', height: '28px', borderRadius: '6px', backgroundColor: 'var(--score-high-bg)', color: 'var(--score-high-text)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 700, fontSize: '13px' }}>
                  2
                </div>
                <h2 className="card-title" style={{ margin: 0 }}>Candidate Resume</h2>
              </div>

              {/* Upload Resume File Button */}
              <div>
                <input
                  type="file"
                  ref={resumeFileInputRef}
                  style={{ display: 'none' }}
                  accept=".pdf,.docx,.txt"
                  onChange={handleResumeFileUpload}
                />
                <button
                  type="button"
                  className="btn btn-secondary"
                  style={{ fontSize: '12px', padding: '5px 10px' }}
                  onClick={() => resumeFileInputRef.current?.click()}
                  disabled={resumeUploading}
                >
                  {resumeUploading ? 'Extracting...' : '📄 Upload Resume'}
                </button>
              </div>
            </div>

            <div className="form-group">
              <label className="form-label" htmlFor="candidate-name-input">
                Candidate Name Override <span style={{ color: 'var(--text-subtle)', fontWeight: 400 }}>(Optional - AI auto-extracts)</span>
              </label>
              <input
                id="candidate-name-input"
                type="text"
                className="form-input"
                placeholder="Leave blank for automatic AI extraction"
                value={candidateNameOverride}
                onChange={(e) => setCandidateNameOverride(e.target.value)}
              />
            </div>

            <div className="form-group">
              <div className="form-label">
                <span>Resume Text *</span>
                <span style={{ fontSize: '11px', color: resumeText.length > MAX_CHARS ? '#dc2626' : 'var(--text-subtle)', fontWeight: 500 }}>
                  {resumeText.length.toLocaleString()} / {MAX_CHARS.toLocaleString()} chars
                  {resumeText.length > MAX_CHARS && ' (will be truncated)'}
                </span>
              </div>
              <textarea
                className="form-textarea"
                style={{ minHeight: '260px' }}
                placeholder="Paste candidate resume, CV text, or upload PDF/DOCX/TXT file..."
                value={resumeText}
                onChange={(e) => setResumeText(e.target.value)}
                required
              />
            </div>
          </div>
        </div>

        {/* Action Button Section */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '16px 20px', backgroundColor: '#ffffff', borderRadius: 'var(--radius-lg)', border: '1px solid var(--border-light)', boxShadow: 'var(--shadow-sm)', marginBottom: '32px', flexWrap: 'wrap', gap: '12px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', fontSize: '13px', color: 'var(--text-muted)' }}>
            <span>Raw resume text processed in-memory only & never stored in SQLite database.</span>
          </div>

          <button
            type="submit"
            className="btn btn-primary"
            style={{ padding: '12px 28px', fontSize: '15px' }}
            disabled={analyzing || !jobDescription.trim() || !resumeText.trim()}
          >
            {analyzing ? (
              <>
                <span
                  style={{
                    width: '16px',
                    height: '16px',
                    border: '2px solid rgba(255,255,255,0.4)',
                    borderTopColor: '#ffffff',
                    borderRadius: '50%',
                    animation: 'spin 0.8s linear infinite',
                    display: 'inline-block',
                  }}
                />
                <span>Analyzing Candidate Fit...</span>
              </>
            ) : (
              <>
                <span> Run Screening</span>
              </>
            )}
          </button>
        </div>
      </form>

      {/* Generated Report Section */}
      <div ref={resultRef}>
        {currentAnalysis && (
          <div style={{ animation: 'fadeIn 0.3s ease-in-out' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
              <h2 style={{ fontSize: '18px', fontWeight: 700, color: 'var(--text-main)', margin: 0 }}>
                Screening Results
              </h2>
              {onNavigateToHistory && (
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={onNavigateToHistory}
                >
                  View in Screening History →
                </button>
              )}
            </div>

            <ReportCard
              report={currentAnalysis.report}
              candidateName={currentAnalysis.candidate_name}
              jobTitle={currentAnalysis.job_title}
              inputTruncated={currentAnalysis.input_truncated}
              createdAt={currentAnalysis.created_at}
            />
          </div>
        )}
      </div>
    </div>
  );
};

