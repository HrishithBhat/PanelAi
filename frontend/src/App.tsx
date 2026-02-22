import React, { useEffect, useMemo, useState } from 'react';
import {
  BrainCircuit,
  Cloud,
  Code2,
  FileText,
  Handshake,
  MessageSquareQuote,
  ScanSearch,
  ShieldAlert,
  Swords,
  Target
} from 'lucide-react';
import { assist, checkHealth, evaluate, fetchSamples, type AssistResult, type EvaluationResult, type Sample } from './api';

type Mode = 'sample' | 'manual';
type EvalView = 'panel' | 'live';

export function App() {
  const [mode, setMode] = useState<Mode>('sample');
  const [evalView, setEvalView] = useState<EvalView>('panel');
  const [samples, setSamples] = useState<Sample[]>([]);
  const [sampleId, setSampleId] = useState<string>('');

  const [jobDescription, setJobDescription] = useState('');
  const [resume, setResume] = useState('');
  const [transcript, setTranscript] = useState('');

  const [jdFileName, setJdFileName] = useState<string>('');
  const [resumeFileName, setResumeFileName] = useState<string>('');
  const [transcriptFileName, setTranscriptFileName] = useState<string>('');

  const [busy, setBusy] = useState(false);
  const [assistBusy, setAssistBusy] = useState(false);
  const [error, setError] = useState<string>('');
  const [assistError, setAssistError] = useState<string>('');
  const [result, setResult] = useState<EvaluationResult | null>(null);
  const [assistResult, setAssistResult] = useState<AssistResult | null>(null);
  const [assistUpdatedAt, setAssistUpdatedAt] = useState<number>(0);
  const [backendStatus, setBackendStatus] = useState<'unknown' | 'ok' | 'down'>('unknown');
  const [resultTab, setResultTab] = useState<'overview' | 'discrepancies' | 'trace' | 'questions'>('overview');

  const [appendText, setAppendText] = useState('');
  const [micSupported, setMicSupported] = useState(false);
  const [micListening, setMicListening] = useState(false);
  const [micInterim, setMicInterim] = useState('');

  useEffect(() => {
    fetchSamples()
      .then((s) => {
        setSamples(s);
        if (s.length) {
          setSampleId(s[0].id);
        }
      })
      .catch((e) => setError(String(e)));
  }, []);

  useEffect(() => {
    checkHealth()
      .then(() => setBackendStatus('ok'))
      .catch(() => setBackendStatus('down'));
  }, []);

  useEffect(() => {
    setMicSupported(Boolean(window.SpeechRecognition || window.webkitSpeechRecognition));
  }, []);

  const selectedSample = useMemo(
    () => samples.find((s: Sample) => s.id === sampleId) || null,
    [samples, sampleId]
  );

  useEffect(() => {
    if (mode !== 'sample') return;
    if (!selectedSample) return;
    setJobDescription(selectedSample.job_description);
    setResume(selectedSample.resume);
    setTranscript(selectedSample.transcript);
  }, [mode, selectedSample]);

  async function onRun() {
    setBusy(true);
    setError('');
    setResult(null);
    try {
      if (!jobDescription.trim() || !resume.trim() || !transcript.trim()) {
        throw new Error('Please provide Job Description, Resume, and Transcript (upload or paste).');
      }
      const res = await evaluate({
        job_description: jobDescription,
        resume,
        transcript,
        config: { cross_exam_rounds: 1 }
      });
      setResult(res);
      setResultTab('overview');
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }

  async function onAssist() {
    setAssistBusy(true);
    setAssistError('');
    try {
      if (!jobDescription.trim() || !resume.trim()) {
        throw new Error('Please provide Job Description and Resume to start Live Interview assist.');
      }
      const res = await assist({
        job_description: jobDescription,
        resume,
        transcript,
        config: { mode: 'assist' }
      });
      setAssistResult(res);
      setAssistUpdatedAt(Date.now());
    } catch (e) {
      setAssistError(String(e));
    } finally {
      setAssistBusy(false);
    }
  }

  function appendToTranscript(text: string) {
    const t = (text || '').trim();
    if (!t) return;
    const stamp = new Date();
    const hh = String(stamp.getHours()).padStart(2, '0');
    const mm = String(stamp.getMinutes()).padStart(2, '0');
    const ss = String(stamp.getSeconds()).padStart(2, '0');
    const line = `[${hh}:${mm}:${ss}] ${t}`;
    setTranscript((prev) => (prev ? `${prev}\n${line}` : line));
  }

  function speechErrorMessage(err: string): string {
    const e = (err || '').toLowerCase().trim();
    if (e === 'network') {
      return (
        'Mic transcription failed: network. The browser speech-to-text service requires an active internet connection ' +
        '(and sometimes VPN/proxy/firewall blocks it). Try: check internet, disable VPN, allow mic permissions, and use Chrome/Edge.'
      );
    }
    if (e === 'not-allowed' || e === 'service-not-allowed') {
      return 'Mic permission denied. Allow microphone access in the browser address bar, then try again.';
    }
    if (e === 'audio-capture') {
      return 'No microphone found (audio-capture). Check your input device and OS mic permissions.';
    }
    if (e === 'no-speech') {
      return 'No speech detected. Try speaking louder/closer to the mic, or check the selected input device.';
    }
    if (e === 'aborted') {
      return 'Mic transcription aborted.';
    }
    return `Mic transcription error: ${err || 'unknown'}`;
  }

  function startMic() {
    const Ctor = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!Ctor) {
      setAssistError('Mic transcription is not supported in this browser.');
      return;
    }
    try {
      const rec = new Ctor();
      rec.continuous = true;
      rec.interimResults = true;
      rec.lang = 'en-US';

      rec.onresult = (event) => {
        let interim = '';
        const finals: string[] = [];
        for (let i = event.resultIndex; i < event.results.length; i++) {
          const r = event.results[i];
          // Browser implementations differ: some expose `item()`, some only array-style indexing.
          const alt = (r as unknown as { item?: (idx: number) => { transcript?: string } | undefined })
            .item?.(0) ?? (r as unknown as Array<{ transcript?: string }>)[0];
          const text = (alt?.transcript || '').trim();
          if (!text) continue;
          if (r.isFinal) finals.push(text);
          else interim += (interim ? ' ' : '') + text;
        }
        setMicInterim(interim.trim());
        if (finals.length) {
          finals.forEach((t) => appendToTranscript(t));
          setMicInterim('');
          void onAssist();
        }
      };
      rec.onerror = (event) => {
        try {
          rec.stop();
        } catch {
          // ignore
        }
        const msg = speechErrorMessage(event.error);
        setAssistError(event.message ? `${msg} (${event.message})` : msg);
        setMicListening(false);
      };
      rec.onend = () => {
        setMicListening(false);
      };

      (window as unknown as { __panelai_rec?: SpeechRecognition }).__panelai_rec = rec;
      rec.start();
      setMicListening(true);
      setAssistError('');
    } catch (e) {
      setAssistError(`Failed to start mic transcription: ${String(e)}`);
    }
  }

  function stopMic() {
    try {
      const rec = (window as unknown as { __panelai_rec?: SpeechRecognition }).__panelai_rec;
      rec?.stop();
    } catch {
      // ignore
    } finally {
      // If the browser never emitted a final result, keep what we have.
      if (micInterim.trim()) {
        appendToTranscript(micInterim.trim());
        setMicInterim('');
        void onAssist();
      }
      setMicListening(false);
    }
  }

  useEffect(() => {
    if (evalView !== 'live') return;
    if (!jobDescription.trim() || !resume.trim()) return;

    void onAssist();
    const id = window.setInterval(() => {
      void onAssist();
    }, 20000);
    return () => window.clearInterval(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [evalView, jobDescription, resume]);

  function clamp(text: string, maxChars: number): { short: string; truncated: boolean } {
    const t = (text || '').trim();
    if (t.length <= maxChars) return { short: t, truncated: false };
    return { short: t.slice(0, maxChars).trimEnd() + '…', truncated: true };
  }

  function scoreMeaning(score: number): string {
    if (score >= 4) return 'Excellent';
    if (score === 3) return 'Strong';
    if (score === 2) return 'OK';
    if (score === 1) return 'Weak';
    return 'Not shown';
  }

  function labelDimension(name: string): string {
    if (name === 'systems_design') return 'Systems Design';
    if (name === 'coding') return 'Coding';
    return name.replaceAll('_', ' ');
  }

  function severityRank(sev: 'low' | 'medium' | 'high'): number {
    return sev === 'high' ? 0 : sev === 'medium' ? 1 : 2;
  }

  async function readTextFile(file: File): Promise<string> {
    return await file.text();
  }

  async function onUpload(which: 'jd' | 'resume' | 'transcript', file: File | null) {
    if (!file) return;
    setError('');
    try {
      const text = await readTextFile(file);
      if (which === 'jd') {
        setJdFileName(file.name);
        setJobDescription(text);
      } else if (which === 'resume') {
        setResumeFileName(file.name);
        setResume(text);
      } else {
        setTranscriptFileName(file.name);
        setTranscript(text);
      }
      setMode('manual');
    } catch (e) {
      setError(`Failed to read file: ${String(e)}`);
    }
  }

  return (
    <div className="page">
      <nav className="topnav">
        <div className="brand">
          <div className="brandMark">PanelAI</div>
          <div className="brandTag">Autonomous Hiring Panels</div>
        </div>
        <div className="navlinks">
          <a href="#about">About</a>
          <a href="#services">Services</a>
          <a href="#evaluate">Evaluate</a>
          <a href="#trace">Trace</a>
          <a href="#contact">Contact</a>
        </div>
      </nav>

      <header className="hero" id="about">
        <div className="heroInner">
          <div className="heroTitle">Technical Interview Evaluator</div>
          <div className="heroSubtitle">
            Multi-agent panel that validates resume claims, transcript evidence, and role fit — then reaches a committee
            verdict with a transparent debate trace.
          </div>
          <div className="heroMeta">
            Backend status:{' '}
            <span className={backendStatus === 'ok' ? 'status ok' : backendStatus === 'down' ? 'status down' : 'status'}>
              {backendStatus === 'ok' ? 'connected' : backendStatus === 'down' ? 'not reachable' : 'checking…'}
            </span>
          </div>
        </div>
      </header>

      <section className="content">
        <div className="contentGrid">
          <div className="contentCard">
            <div className="contentTitle">Why PanelAI</div>
            <div className="contentText">
              Most interview tools behave like answer checkers. PanelAI is designed to behave like a hiring committee:
              it tests whether resume claims are supported by what the candidate demonstrated in the transcript.
            </div>
            <ul className="bullets">
              <li>Evidence-first discrepancy log (claim ↔ transcript snippet)</li>
              <li>Multiple roles with independent votes (HM + judges)</li>
              <li>Cross-exam trace to make decisions auditable</li>
            </ul>
          </div>

          <div className="contentCard">
            <div className="contentTitle">How It Works</div>
            <div className="steps">
              <div className="step">
                <div className="stepNum">1</div>
                <div>
                  <div className="stepTitle">Upload 3 documents</div>
                  <div className="stepText">Job description, resume, and interview transcript.</div>
                </div>
              </div>
              <div className="step">
                <div className="stepNum">2</div>
                <div>
                  <div className="stepTitle">Agents analyze independently</div>
                  <div className="stepText">Claims, evidence, gaps, contradictions, and overall assessment.</div>
                </div>
              </div>
              <div className="step">
                <div className="stepNum">3</div>
                <div>
                  <div className="stepTitle">Panel debates + votes</div>
                  <div className="stepText">Cross-exam discrepancies and produce consensus.</div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div className="contentWide">
          <div className="contentCard">
            <div className="contentTitle">Panel Roles</div>
            <div className="roleGrid">
              <div className="role">
                <div className="roleTop">
                  <div className="roleIcon" aria-hidden="true">
                    <ScanSearch size={18} />
                  </div>
                <div className="roleName">Resume Claims</div>
                </div>
                <div className="roleText">Extracts atomic, testable claims from the resume.</div>
              </div>
              <div className="role">
                <div className="roleTop">
                  <div className="roleIcon" aria-hidden="true">
                    <MessageSquareQuote size={18} />
                  </div>
                <div className="roleName">Transcript Evidence</div>
                </div>
                <div className="roleText">Summarizes demonstrated knowledge and retrieves supporting snippets.</div>
              </div>
              <div className="role">
                <div className="roleTop">
                  <div className="roleIcon" aria-hidden="true">
                    <Target size={18} />
                  </div>
                <div className="roleName">Gap Analysis</div>
                </div>
                <div className="roleText">Maps job requirements to evidence and proposes follow-ups.</div>
              </div>
              <div className="role">
                <div className="roleTop">
                  <div className="roleIcon" aria-hidden="true">
                    <ShieldAlert size={18} />
                  </div>
                <div className="roleName">Contradiction Hunter</div>
                </div>
                <div className="roleText">Flags uncertainty and possible conflicts with resume claims.</div>
              </div>
              <div className="role">
                <div className="roleTop">
                  <div className="roleIcon" aria-hidden="true">
                    <BrainCircuit size={18} />
                  </div>
                <div className="roleName">Judges</div>
                </div>
                <div className="roleText">Evaluates systems design + coding competence based on evidence.</div>
              </div>
              <div className="role">
                <div className="roleTop">
                  <div className="roleIcon" aria-hidden="true">
                    <Handshake size={18} />
                  </div>
                <div className="roleName">Hiring Manager</div>
                </div>
                <div className="roleText">Balances risk, ownership, and role fit; casts a weighted vote.</div>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section className="services" id="services">
        <div className="sectionHeading">Our Core Services</div>
        <div className="serviceGrid">
          <div className="serviceCard">
            <div className="serviceIcon" aria-hidden="true">
              <FileText size={20} />
            </div>
            <div className="serviceTitle">Resume Claim Audit</div>
            <div className="serviceText">Extracts testable claims and checks whether the interview demonstrated them.</div>
          </div>
          <div className="serviceCard">
            <div className="serviceIcon" aria-hidden="true">
              <Code2 size={20} />
            </div>
            <div className="serviceTitle">Transcript Evidence</div>
            <div className="serviceText">Summarizes what the candidate actually showed, not what they asserted.</div>
          </div>
          <div className="serviceCard">
            <div className="serviceIcon" aria-hidden="true">
              <Cloud size={20} />
            </div>
            <div className="serviceTitle">Role Alignment</div>
            <div className="serviceText">Maps job requirements to evidence and proposes targeted follow-up questions.</div>
          </div>
          <div className="serviceCard">
            <div className="serviceIcon" aria-hidden="true">
              <Swords size={20} />
            </div>
            <div className="serviceTitle">Panel Consensus</div>
            <div className="serviceText">Judges cross-examine discrepancies and produce a weighted committee verdict.</div>
          </div>
        </div>
      </section>

      <section className="evaluate" id="evaluate">
        <div className="sectionHeading">Run an Evaluation</div>
        <div className="evalLayout">
          <section className="card">
            <div className="row">
              <div className="segmented">
                <button className={evalView === 'panel' ? 'active' : ''} onClick={() => setEvalView('panel')}>
                  Panel Evaluation
                </button>
                <button className={evalView === 'live' ? 'active' : ''} onClick={() => setEvalView('live')}>
                  Live Interview
                </button>
              </div>
              <div className="hint">Assist mode updates every ~20s</div>
            </div>

            {evalView === 'panel' ? (
              <>
                <div className="row">
                  <div className="segmented">
                    <button className={mode === 'sample' ? 'active' : ''} onClick={() => setMode('sample')}>
                      Sample
                    </button>
                    <button className={mode === 'manual' ? 'active' : ''} onClick={() => setMode('manual')}>
                      Manual
                    </button>
                  </div>

                  {mode === 'sample' && (
                    <select
                      value={sampleId}
                      onChange={(e: React.ChangeEvent<HTMLSelectElement>) => setSampleId(e.target.value)}
                    >
                      {samples.map((s: Sample) => (
                        <option key={s.id} value={s.id}>
                          {s.id}
                        </option>
                      ))}
                    </select>
                  )}
                </div>

                <div className="uploads">
                  <div className="upload">
                    <div className="label">Upload Job Description</div>
                    <input
                      type="file"
                      accept=".txt,.md"
                      onChange={(e: React.ChangeEvent<HTMLInputElement>) => onUpload('jd', e.target.files?.[0] ?? null)}
                    />
                    {jdFileName && <div className="fileName">{jdFileName}</div>}
                  </div>
                  <div className="upload">
                    <div className="label">Upload Resume</div>
                    <input
                      type="file"
                      accept=".txt,.md"
                      onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
                        onUpload('resume', e.target.files?.[0] ?? null)
                      }
                    />
                    {resumeFileName && <div className="fileName">{resumeFileName}</div>}
                  </div>
                  <div className="upload">
                    <div className="label">Upload Transcript</div>
                    <input
                      type="file"
                      accept=".txt,.md"
                      onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
                        onUpload('transcript', e.target.files?.[0] ?? null)
                      }
                    />
                    {transcriptFileName && <div className="fileName">{transcriptFileName}</div>}
                  </div>
                </div>

                <label>
                  <div className="label">Job Description</div>
                  <textarea value={jobDescription} onChange={(e) => setJobDescription(e.target.value)} />
                </label>

                <label>
                  <div className="label">Resume</div>
                  <textarea value={resume} onChange={(e) => setResume(e.target.value)} />
                </label>

                <label>
                  <div className="label">Interview Transcript</div>
                  <textarea value={transcript} onChange={(e) => setTranscript(e.target.value)} />
                </label>

                <div className="row">
                  <button className="primary" onClick={onRun} disabled={busy}>
                    {busy ? 'Evaluating…' : 'Run Panel Evaluation'}
                  </button>
                  <div className="hint">Uploads supported: .md / .txt</div>
                </div>

                {error && <div className="error">{error}</div>}
              </>
            ) : (
              <>
              <div className="muted" style={{ marginBottom: 10 }}>
                Paste/type transcript as it happens, or use mic transcription. PanelAI will surface discrepancies and the
                best next questions to ask.
              </div>

              <label>
                <div className="label">Job Description (loaded once)</div>
                <textarea value={jobDescription} onChange={(e) => setJobDescription(e.target.value)} />
              </label>

              <label>
                <div className="label">Resume (loaded once)</div>
                <textarea value={resume} onChange={(e) => setResume(e.target.value)} />
              </label>

              <div className="liveGrid">
                <div>
                  <label>
                    <div className="label">Transcript (live buffer)</div>
                    <textarea value={transcript} onChange={(e) => setTranscript(e.target.value)} />
                  </label>

                  <div className="appendRow">
                    <div style={{ flex: 1 }}>
                      <div className="label">Append latest answer</div>
                      <textarea
                        className="appendBox"
                        value={appendText}
                        onChange={(e) => setAppendText(e.target.value)}
                        placeholder="Type/paste the latest response…"
                      />
                    </div>
                  </div>

                  <div className="row" style={{ marginTop: 8 }}>
                    <button
                      className="primary"
                      onClick={() => {
                        appendToTranscript(appendText);
                        setAppendText('');
                        void onAssist();
                      }}
                      disabled={!appendText.trim()}
                    >
                      Append + Update
                    </button>

                    <div className="micRow">
                      <button
                        className={micListening ? 'micBtn active' : 'micBtn'}
                        onClick={() => (micListening ? stopMic() : startMic())}
                        disabled={!micSupported}
                        title={micSupported ? 'Mic transcription' : 'Mic transcription not supported'}
                      >
                        {micListening ? 'Stop mic' : 'Start mic'}
                      </button>
                      {micListening && <span className="muted">Listening…</span>}
                    </div>
                  </div>

                  {micInterim && (
                    <div className="interim">
                      <div className="label">Mic (interim)</div>
                      <div className="muted">{micInterim}</div>
                    </div>
                  )}

                  <div className="row">
                    <button
                      className="primary"
                      onClick={async () => {
                        await onRun();
                        setEvalView('panel');
                      }}
                      disabled={busy}
                    >
                      {busy ? 'Evaluating…' : 'Generate final verdict'}
                    </button>
                    <button className="ghost" onClick={() => void onAssist()} disabled={assistBusy}>
                      {assistBusy ? 'Updating…' : 'Analyze latest'}
                    </button>
                  </div>

                  {assistError && <div className="error">{assistError}</div>}
                </div>
              </div>
              </>
            )}
          </section>

          <section className="card resultsCard">
          <div className="sectionTitle">{evalView === 'live' ? 'Live Assist' : 'Results'}</div>

          {evalView === 'live' && (
            <div className="results">
              {!assistResult && !assistBusy && (
                <div className="muted">Waiting for assist analysis… (needs JD + Resume)</div>
              )}
              {assistBusy && <div className="muted">Updating assist insights…</div>}

              {assistResult && (
                <>
                  <div className="assistMeta">
                    <div className="kpis">
                      <div className="kpi">
                        <div className="kpiLabel">Discrepancies (watch)</div>
                        <div className="kpiValue">{assistResult.discrepancies.length}</div>
                      </div>
                      <div className="kpi">
                        <div className="kpiLabel">Ask next</div>
                        <div className="kpiValue">{assistResult.followups.length}</div>
                      </div>
                      <div className="kpi">
                        <div className="kpiLabel">Last update</div>
                        <div className="kpiValue" style={{ fontSize: 12, fontWeight: 900 }}>
                          {assistUpdatedAt ? new Date(assistUpdatedAt).toLocaleTimeString() : '—'}
                        </div>
                      </div>
                    </div>
                  </div>

                  <div className="assistGrid">
                    <div className="assistCard">
                      <div className="subTitle">Discrepancy watch</div>
                      {assistResult.discrepancies.length === 0 ? (
                        <div className="muted">No issues flagged yet.</div>
                      ) : (
                        <div className="discList">
                          {assistResult.discrepancies.slice(0, 8).map((d, idx) => (
                            <details className="discRow" key={idx}>
                              <summary className="discSummary">
                                <span className={`sev ${d.severity}`}>{d.severity}</span>
                                <span className="discCat">{d.category}</span>
                                <span className="discClaim">{clamp(d.claim, 120).short}</span>
                              </summary>
                              <div className="discDetail">
                                <div className="discLine">
                                  <b>Evidence:</b> {clamp(d.evidence, 220).short || '—'}
                                </div>
                                <div className="discLine">
                                  <b>Why it matters:</b> {clamp(d.explanation, 220).short || '—'}
                                </div>
                              </div>
                            </details>
                          ))}
                        </div>
                      )}
                    </div>

                    <div className="assistCard">
                      <div className="subTitle">Ask next (top 5)</div>
                      {assistResult.followups.length === 0 ? (
                        <div className="muted">No follow-ups generated yet.</div>
                      ) : (
                        <div className="followList">
                          {assistResult.followups.slice(0, 5).map((f, idx) => (
                            <details className="followRow" key={idx}>
                              <summary className="followSummary">{clamp(f.question, 160).short}</summary>
                              <div className="followDetail">
                                {f.reason && (
                                  <div className="discLine">
                                    <b>Reason:</b> {f.reason}
                                  </div>
                                )}
                                {f.evidence && (
                                  <div className="discLine">
                                    <b>Evidence:</b> {clamp(f.evidence, 240).short}
                                  </div>
                                )}
                                <div className="discLine">
                                  <b>Evidence score:</b> {Number.isFinite(f.evidence_score) ? f.evidence_score.toFixed(2) : '—'}
                                </div>
                              </div>
                            </details>
                          ))}
                        </div>
                      )}
                    </div>

                    <div className="assistCard">
                      <div className="subTitle">Evidence snippets</div>
                      <ul className="list compact">
                        {(assistResult.followups || [])
                          .filter((f) => (f.evidence || '').trim())
                          .slice(0, 3)
                          .map((f, idx) => (
                            <li key={idx}>{clamp(f.evidence, 180).short}</li>
                          ))}
                        {(assistResult.discrepancies || [])
                          .filter((d) => (d.evidence || '').trim())
                          .slice(0, 2)
                          .map((d, idx) => (
                            <li key={`d-${idx}`}>{clamp(d.evidence, 180).short}</li>
                          ))}
                      </ul>
                      {assistResult.risks?.length ? (
                        <>
                          <div className="subTitle" style={{ marginTop: 10 }}>
                            Live risks
                          </div>
                          <ul className="list compact">
                            {assistResult.risks.slice(0, 4).map((r, idx) => (
                              <li key={idx}>{clamp(r, 160).short}</li>
                            ))}
                          </ul>
                        </>
                      ) : null}
                    </div>
                  </div>
                </>
              )}
            </div>
          )}

          {evalView !== 'live' && !result && <div className="muted">Run an evaluation to see output.</div>}

          {evalView !== 'live' && result && (
            <div className="results">
              <div className="resultTop">
                <div className="verdict">
                  <div className="pill">Verdict</div>
                  <div className="verdictText">{result.verdict}</div>
                </div>

                <div className="kpis">
                  <div className="kpi">
                    <div className="kpiLabel">Discrepancies</div>
                    <div className="kpiValue">{result.discrepancies.length}</div>
                  </div>
                  <div className="kpi">
                    <div className="kpiLabel">High severity</div>
                    <div className="kpiValue">
                      {result.discrepancies.filter((d) => d.severity === 'high').length}
                    </div>
                  </div>
                  <div className="kpi">
                    <div className="kpiLabel">Trace events</div>
                    <div className="kpiValue">{result.trace.length}</div>
                  </div>
                </div>
              </div>

              <div className="tabs">
                <button className={resultTab === 'overview' ? 'active' : ''} onClick={() => setResultTab('overview')}>
                  Overview
                </button>
                <button
                  className={resultTab === 'discrepancies' ? 'active' : ''}
                  onClick={() => setResultTab('discrepancies')}
                >
                  Discrepancies
                </button>
                <button className={resultTab === 'trace' ? 'active' : ''} onClick={() => setResultTab('trace')}>
                  Trace
                </button>
                <button
                  className={resultTab === 'questions' ? 'active' : ''}
                  onClick={() => setResultTab('questions')}
                >
                  Questions
                </button>
              </div>

              {resultTab === 'overview' && (
                <div className="tabPanel">
                  <div className="block">
                    <div className="blockTitle">Summary</div>
                    <div className="overviewGrid">
                      <div className="summaryCard">
                        <div className="subTitle">What this means</div>
                        <ul className="list compact">
                          <li>
                            <b>Verdict</b> is the panel’s final recommendation.
                          </li>
                          <li>
                            <b>Discrepancies</b> are claim-vs-evidence mismatches.
                          </li>
                          <li>
                            <b>Trace</b> shows how agents challenged each other.
                          </li>
                        </ul>
                      </div>

                      <div className="summaryCard">
                        <div className="subTitle">Verdict reasoning</div>
                        <div className="muted">{clamp(result.overall_reasoning, 180).short || '—'}</div>
                        {(result.overall_reasoning || '').toLowerCase().includes('heuristic') && (
                          <div className="muted" style={{ marginTop: 8, fontSize: 12 }}>
                            Heuristic summary = deterministic rules (no LLM).
                          </div>
                        )}
                        <details className="details" style={{ marginTop: 10 }}>
                          <summary className="detailsSummary">Show full verdict reasoning</summary>
                          <pre className="pre compact">{result.overall_reasoning}</pre>
                        </details>
                      </div>

                      <div className="summaryCard">
                        <div className="subTitle">Strengths</div>
                        <ul className="list compact">
                          {result.strengths.slice(0, 5).map((s, idx) => (
                            <li key={idx}>{clamp(s, 120).short}</li>
                          ))}
                        </ul>
                      </div>

                      <div className="summaryCard">
                        <div className="subTitle">Risks</div>
                        <ul className="list compact">
                          {result.risks.slice(0, 5).map((r, idx) => (
                            <li key={idx}>{clamp(r, 120).short}</li>
                          ))}
                        </ul>
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {resultTab === 'discrepancies' && (
                <div className="tabPanel">
                  {result.discrepancies.length === 0 ? (
                    <div className="muted">No discrepancies detected.</div>
                  ) : (
                    <div className="discList">
                      {result.discrepancies
                        .slice()
                        .sort((a, b) => severityRank(a.severity) - severityRank(b.severity))
                        .map((d, idx) => {
                          const claim = clamp(d.claim, 140);
                          const evidence = clamp(d.evidence, 180);
                          const why = clamp(d.explanation, 180);
                          return (
                            <details className="discRow" key={idx}>
                              <summary className="discSummary">
                                <span className={`sev ${d.severity}`}>{d.severity}</span>
                                <span className="discCat">{d.category}</span>
                                <span className="discClaim">{claim.short}</span>
                              </summary>
                              <div className="discDetail">
                                <div className="discLine">
                                  <b>Claim:</b> {d.claim}
                                </div>
                                <div className="discLine">
                                  <b>Evidence:</b> {evidence.truncated ? (
                                    <span>
                                      {evidence.short}
                                      <div className="muted">(Expand to see full snippet)</div>
                                    </span>
                                  ) : (
                                    evidence.short
                                  )}
                                </div>
                                <div className="discLine">
                                  <b>Why it matters:</b> {why.short}
                                </div>
                              </div>
                            </details>
                          );
                        })}
                    </div>
                  )}
                </div>
              )}

              {resultTab === 'trace' && (
                <div className="tabPanel" id="trace">
                  <div className="muted">Showing the most recent 80 events.</div>
                  <div className="trace compactScroll">
                    {result.trace.slice(-80).map((m, idx) => {
                      const content = clamp(m.content, 320);
                      return (
                        <div className="traceItem" key={idx}>
                          <div className="traceMeta">
                            <span className="traceAgent">{m.agent}</span>
                            <span className="traceStage">{m.stage}</span>
                          </div>
                          {content.truncated ? (
                            <details className="details">
                              <summary className="detailsSummary">{content.short}</summary>
                              <pre className="pre compact">{m.content}</pre>
                            </details>
                          ) : (
                            <div className="muted">{content.short}</div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}

              {resultTab === 'questions' && (
                <div className="tabPanel">
                  <ul className="list">
                    {result.next_interview_questions.slice(0, 10).map((q, idx) => (
                      <li key={idx}>{clamp(q, 160).short}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}
        </section>
      </div>

      </section>

      <footer className="footer">
        <div className="footerInner" id="contact">
          <span className="muted">© {new Date().getFullYear()} PanelAI</span>
          <span className="muted">Contact: hello@panelai.local</span>
        </div>
      </footer>
    </div>
  );
}
