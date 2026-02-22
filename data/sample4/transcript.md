Interviewer: Tell me about a reliability initiative you led.
Candidate: We had frequent latency spikes and noisy alerts. I introduced SLOs per service, then rebuilt alerts around burn rate. That reduced pages a lot.

Interviewer: How do you think about retries and timeouts?
Candidate: Retries must be bounded and paired with timeouts, otherwise they amplify load. I prefer exponential backoff with jitter. For idempotent operations, retries are safer; for non-idempotent, we need idempotency keys or dedupe.

Interviewer: Kubernetes experience?
Candidate: I led a migration from VM-based deploys to Kubernetes. We used canaries, measured error rate + latency, and rolled back automatically if error budgets burned too fast.

Interviewer: Incident handling?
Candidate: During an incident I focus on clear comms, roles (IC, scribe, ops), and quick mitigation. RCAs are about system fixes, not blame.

Interviewer: Testing mindset?
Candidate: For reliability work I like chaos-style failure injection in staging. For code changes, unit tests + integration tests are required.
