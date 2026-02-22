# PanelAI — Diagrams

This document contains the **architecture diagram**, **project flowchart**, and **dataflow diagram** for the PanelAI project.

> Tip: Mermaid diagrams render in many Markdown viewers (including VS Code with Mermaid support enabled, or the "Markdown Preview Mermaid Support" extension).

---

## 1) Architecture Diagram (High-Level)

```mermaid
flowchart LR
  U[User] -->|Paste/Upload texts| FE[Frontend: React + Vite]
  FE -->|GET /health| API[Backend API: FastAPI]
  FE -->|GET /samples| API
  FE -->|POST /evaluate| API
  FE -->|POST /evaluate-files| API

  subgraph FS[Workspace Filesystem]
    DATA[(data/sample*/\njob_description.md\nresume.md\ntranscript.md)]
  end

  API -->|reads| DATA

  subgraph BE[Backend: Panel Engine]
    CTX[PanelContext\n(job_description, resume, transcript, config)]
    ORCH[Orchestrator\nrun_panel(ctx)]
    AGS[Agents\n(resume-claims, transcript-evidence,\n gap-analysis, contradiction-hunter,\n judges, hiring-manager)]
    SYN[Discrepancy synthesis\n+ cross-exam rounds]
    CONS[Consensus vote\n+ risk adjustment]
    OUT[EvaluationResult\n(verdict, reasoning, discrepancies,\n strengths, risks, questions, trace, artifacts)]
  end

  API --> CTX --> ORCH
  ORCH -->|parallel initial| AGS
  AGS --> SYN --> CONS --> OUT
  OUT -->|JSON response| FE
```

---

## 2) Flowchart (Evaluation Lifecycle)

```mermaid
flowchart TD
  A([Start]) --> B{Inputs present?\nJD + Resume + Transcript}
  B -- No --> BX[Return 400 error\n"required"] --> Z([End])
  B -- Yes --> C[Create PanelContext]
  C --> D[Run initial agents in parallel]

  D --> D1[ResumeClaimsAgent\nextract claims]
  D --> D2[TranscriptEvidenceAgent\nchunk + summarize]
  D --> D3[GapAnalysisAgent\nrequirements vs evidence]
  D --> D4[ContradictionHunterAgent\nuncertainty/contradictions]
  D --> D5[Judges + Hiring Manager\nindependent reads]

  D1 --> E[Discrepancy synthesis]
  D2 --> E
  D4 --> E

  E --> F{Cross-exam rounds > 0?}
  F -- Yes --> G[Select top discrepancies\n(high severity first)]
  G --> H[Ask judges/HM to respond\nappend to trace]
  H --> I[Consensus vote\n(weighted)]
  F -- No --> I

  I --> J[Risk adjustment\n(cap hire if many high discrepancies)]
  J --> K[Assemble EvaluationResult\nverdict + reasoning + lists + trace]
  K --> Z([End])
```

---

## 3) Dataflow Diagram (Inputs → Intermediate Artifacts → Outputs)

```mermaid
flowchart LR
  subgraph IN[Inputs]
    JD[Job Description text]
    R[Resume text]
    T[Transcript text]
  end

  subgraph P[Processing]
    RC[ResumeClaimsAgent\nclaims[]]
    TE[TranscriptEvidenceAgent\nchunks[] + evidence lookup]
    GA[GapAnalysisAgent\nstrengths/risks/questions]
    CH[ContradictionHunterAgent\ncontradiction findings]
    DS[Discrepancy Builder\n(discrepancies[])]
    CE[Cross-exam\nresponses appended to trace]
    VOTE[Consensus\nweighted votes + risk adjustment]
  end

  subgraph OUT[Outputs]
    VER[verdict]
    REAS[overall_reasoning]
    DISC[discrepancies[]\n(claim, evidence, severity, why)]
    SR[strengths[] / risks[]]
    Q[next_interview_questions[]]
    TR[trace[]\n(agent, stage, content)]
    ART[artifacts\n(votes, weak_claims, …)]
  end

  JD --> GA
  JD --> VOTE
  R --> RC
  R --> DS
  R --> VOTE
  T --> TE
  T --> GA
  T --> CH
  T --> DS
  T --> VOTE

  RC --> DS
  TE --> DS
  CH --> DS
  GA --> SR
  GA --> Q

  DS --> CE
  CE --> TR
  DS --> VOTE
  VOTE --> VER
  VOTE --> REAS
  DS --> DISC
  TR --> REAS
  VOTE --> ART
```

---

## 4) “Single Models” (Agent Internals)

This section shows **what happens inside each agent** (the “single models”). These diagrams are based on the actual code in `backend/app/agents/*`.

---

### 4.1) ResumeClaimsAgent (resume-claims)

```mermaid
flowchart TD
  IN[Input: Resume text] --> LINES[Split into non-empty lines]
  LINES --> FILTER[Select candidate lines if:\n- bullet line (-/•/*)\n- contains action verbs (built/designed/led/owned/...)\n- contains N years/yrs]
  FILTER --> DEDUP[Normalize whitespace + de-dup preserving order]
  DEDUP --> CAP[Cap to 40 claims]
  CAP --> MODE{LLM provider?}
  MODE -- Heuristic --> SYN1[claims_normalized = numbered list of claims]
  MODE -- LLM --> SYN2[LLM normalizes into atomic, testable list]
  SYN1 --> OUT
  SYN2 --> OUT
  OUT[Outputs:\n- Finding: resume_claims (low)\n- Artifacts: claims[], claims_normalized (text)]
```

---

### 4.2) TranscriptEvidenceAgent (transcript-evidence)

```mermaid
flowchart TD
  IN[Input: Transcript text] --> LINES[Split into non-empty lines]
  LINES --> CHUNK[Chunk lines into ~360+ char chunks]\n
  CHUNK --> MODE{LLM provider?}
  MODE -- Heuristic --> SUM1[Evidence-oriented bullet summary\n(pulls strong-signal lines + uncertainty marker)]
  MODE -- LLM --> SUM2[LLM summary focused on demonstrated evidence\n+ concrete snippets]
  SUM1 --> OUT
  SUM2 --> OUT
  OUT[Outputs:\n- Finding: transcript_summary (low)\n- Artifacts: chunks[], summary (text)]

  %% evidence retrieval helper used by orchestrator
  CHUNK --> BEST[_best_evidence(claim, chunks)]
  BEST --> TOK[_tokenize() => set of words (stopwords removed)\nshort_ok includes: go/c/js/ts/ai/ml/db/ci/cd]
  TOK --> SCORE[Score = overlap / |claim_tokens|\nBoost if claim short (<=2 tokens)\nBoost if exact substring match]
```

---

### 4.3) GapAnalysisAgent (gap-analysis)

```mermaid
flowchart TD
  IN[Inputs: JD + Resume + Transcript] --> REQ[Extract requirements from JD lines if:\n- bullet line (-/•/*)\n- contains must/required/requirement(s)]
  REQ --> REQDEDUP[Normalize whitespace + de-dup]
  REQDEDUP --> CORPUS[Build corpus = resume + transcript]
  CORPUS --> LOOP[For each requirement: _mentions(corpus, requirement)]
  LOOP --> M1[Tokenize requirement keywords\n(remove stopwords; short_ok includes go/c/js/ts/ai/ml)]
  M1 --> M2[Compute hits of up to 8 unique keywords]
  M2 --> SPLIT{Enough hits?}
  SPLIT -- Yes --> COV[Add to covered[]]
  SPLIT -- No --> GAP[Add to gaps[]]
  COV --> MODE
  GAP --> MODE
  MODE{LLM provider?} -- Heuristic --> N1[Heuristic gap summary\nCovered + Missing sections]
  MODE -- LLM --> N2[LLM narrative: interview-relevant gaps + why]
  N1 --> OUT
  N2 --> OUT
  OUT[Outputs:\n- Finding: role_alignment (low/medium)\n- strengths[] from covered\n- risks[] from gaps\n- next_questions[] from gaps\n- Artifacts: requirements[], covered[], gaps[]]
```

---

### 4.4) ContradictionHunterAgent (contradiction-hunter)

```mermaid
flowchart TD
  IN[Inputs: Resume + Transcript] --> SK[_extract_skill_terms(resume)]
  SK --> SK1[Regex tokens like: A-Za-z[A-Za-z0-9+.#-]{1,}]
  SK1 --> SK2[Keep token if:\n- starts uppercase OR contains + . #\n- length <= 24]
  SK2 --> SKOUT[skills_detected[] (capped later)]

  IN --> RF[_find_red_flag_snippets(transcript)]
  RF --> RF1[Chunk transcript]\n
  RF1 --> RF2[Keep chunk if contains red flags\n("not sure", "never used", "i don't know", ...)]
  RF2 --> RF3[Cap to 8 snippets]

  RF3 --> LOOP[For each snippet: match resume skills]\n
  SKOUT --> LOOP
  LOOP --> MENTION[mentioned_skills = skills whose lowercase appears in snippet\n(limit skills scanned: first ~80)]
  MENTION --> FIND[Create Finding:\ncategory=contradiction_or_uncertainty\nseverity=high if mentioned_skills else medium\nevidence=snippet\nclaim=mentioned skills or None]
  FIND --> OUT[Outputs:\n- findings[] (0..N)\n- artifacts: skills_detected[]]
```

---

### 4.5) SystemsDesignJudgeAgent (judge-systems)

```mermaid
flowchart TD
  IN[Input: Transcript] --> DEPTH[_depth_markers(transcript)]
  DEPTH --> D1[Count presence of markers\n(tradeoff/latency/consistency/...)]
  IN --> UNC[_uncertainty_markers(transcript)]
  UNC --> U1[Count uncertainty flags\n("not sure", "never used", ...)]
  D1 --> ADJ[adjusted = max(0, depth - 2*uncertainty)]
  U1 --> ADJ
  ADJ --> BUCKET[_score_bucket(adjusted, low=2, high=10) => 1..4]
  BUCKET --> MODE{LLM provider?}
  MODE -- Heuristic --> R1[rationale_text = "Signals: depth=..., uncertainty=..." ]
  MODE -- LLM --> R2[LLM rationale citing transcript evidence\n(no reward for uncertain keyword drops)]
  R1 --> VOTE
  R2 --> VOTE
  VOTE{score >= 3?} -- Yes --> VH[Vote: lean-hire (c=0.62)]
  VOTE -- No --> VN[Vote: lean-no-hire (c=0.62)]
  VH --> OUT
  VN --> OUT
  OUT[Outputs:\n- scores: systems_design (0..4)\n- vote: lean-hire/lean-no-hire]
```

---

### 4.6) CodingJudgeAgent (judge-coding)

```mermaid
flowchart TD
  IN[Input: Transcript] --> SIG[Compute signals]\n
  SIG --> S1[+1 if mentions: "big o" or "complexity"]
  SIG --> S2[+1 if mentions: edge/corner case]
  SIG --> S3[+1 if mentions: test/unit]
  SIG --> S4[+1 if mentions: refactor]
  S1 --> SCORE[score = clamp(signals + 1, 0..4)]
  S2 --> SCORE
  S3 --> SCORE
  S4 --> SCORE
  SCORE --> MODE{LLM provider?}
  MODE -- Heuristic --> R1[rationale_text = "Signals: N (complexity/edge/tests/refactor)" ]
  MODE -- LLM --> R2[LLM rationale citing transcript evidence]
  R1 --> VOTE
  R2 --> VOTE
  VOTE[Vote = lean-hire if score>=3 else lean-no-hire\n(confidence=0.58)] --> OUT
  OUT[Outputs:\n- scores: coding (0..4)\n- vote]
```

---

### 4.7) HiringManagerAgent (hiring-manager)

```mermaid
flowchart TD
  IN[Inputs: JD + Resume + Transcript] --> MODE{LLM provider?}
  MODE -- Heuristic --> HM1[hm_summary = heuristic text]
  MODE -- LLM --> HM2[LLM summary: role fit + strengths + risks]

  IN --> OWN[ownership = 1 if transcript matches\n"i owned"|"i led"|"i was responsible"|"i drove"]
  IN --> DEPTH[depth = 1 if _depth_markers(transcript) >= 4]
  OWN --> DEC{ownership + depth >= 1?}
  DEPTH --> DEC
  DEC -- Yes --> VH[Vote: lean-hire (c=0.60)]
  DEC -- No --> VN[Vote: lean-no-hire (c=0.60)]
  HM1 --> OUT
  HM2 --> OUT
  VH --> OUT
  VN --> OUT
  OUT[Outputs:\n- vote\n- artifacts: hm_summary (text)]
```
