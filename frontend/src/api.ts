export type Discrepancy = {
  severity: 'low' | 'medium' | 'high';
  category: string;
  claim: string;
  evidence: string;
  explanation: string;
};

export type DimensionScore = {
  dimension: string;
  score_0_to_4: number;
  rationale: string;
};

export type AgentMessage = {
  agent: string;
  stage: string;
  content: string;
  meta: Record<string, unknown>;
};

export type EvaluationResult = {
  verdict: 'hire' | 'no-hire' | 'lean-hire' | 'lean-no-hire';
  overall_reasoning: string;
  scores: DimensionScore[];
  discrepancies: Discrepancy[];
  strengths: string[];
  risks: string[];
  next_interview_questions: string[];
  trace: AgentMessage[];
  artifacts: Record<string, unknown>;
};

export type FollowUp = {
  question: string;
  reason: string;
  evidence: string;
  evidence_score: number;
};

export type AssistResult = {
  discrepancies: Discrepancy[];
  followups: FollowUp[];
  risks: string[];
  artifacts: Record<string, unknown>;
};

export type Sample = {
  id: string;
  job_description: string;
  resume: string;
  transcript: string;
};

export async function checkHealth(): Promise<{ status: string }> {
  const resp = await fetch('/health');
  if (!resp.ok) throw new Error(`Health check failed: ${resp.status}`);
  return resp.json();
}

export async function fetchSamples(): Promise<Sample[]> {
  const resp = await fetch('/samples');
  if (!resp.ok) throw new Error(`Failed to load samples: ${resp.status}`);
  return resp.json();
}

export async function evaluate(payload: {
  job_description: string;
  resume: string;
  transcript: string;
  config?: Record<string, unknown>;
}): Promise<EvaluationResult> {
  const resp = await fetch('/evaluate', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  });
  if (!resp.ok) {
    const text = await resp.text();
    throw new Error(`Evaluate failed: ${resp.status} ${text}`);
  }
  return resp.json();
}

export async function assist(payload: {
  job_description: string;
  resume: string;
  transcript: string;
  config?: Record<string, unknown>;
}): Promise<AssistResult> {
  const resp = await fetch('/assist', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  });
  if (!resp.ok) {
    const text = await resp.text();
    throw new Error(`Assist failed: ${resp.status} ${text}`);
  }
  return resp.json();
}
