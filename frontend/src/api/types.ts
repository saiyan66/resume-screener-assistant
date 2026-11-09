export interface MatchReport {
  candidate_name: string
  match_score: number
  matching_skills: string[]
  gaps: string[]
  interview_questions: string[]
}

export interface AnalysisCreate {
  job_description: string
  resume_text: string
  candidate_name?: string
  job_title?: string
}

export interface AnalysisSummary {
  id: number
  candidate_name: string
  job_title: string
  match_score: number
  created_at: string
}

export interface AnalysisDetail extends AnalysisSummary {
  job_description: string
  report: MatchReport
  input_truncated: boolean
}

export interface AnalysisListResponse {
  items: AnalysisSummary[]
  total: number
}

export interface ResumeUploadResponse {
  filename: string
  text: string
  char_count: number
}

export interface AnalysisFilterParams {
  search?: string
  min_score?: number
  max_score?: number
  limit?: number
  offset?: number
}

