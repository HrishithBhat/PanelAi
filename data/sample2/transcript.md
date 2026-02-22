Interviewer: Walk me through a system you designed.
Candidate: I led the checkout service redesign. The main issue was duplicate submissions causing double charges. We made the API idempotent using an idempotency key stored with a TTL, and we treated retries as the default behavior.

Interviewer: What tradeoffs did you consider?
Candidate: The main tradeoff was storage + write amplification versus correctness. We also had to pick TTL carefully: too short and retries break; too long and the table grows. We added periodic cleanup and metrics on key reuse.

Interviewer: How did you handle failures and backpressure?
Candidate: For the Kafka pipeline, we used consumer lag as a signal. If lag spiked, we scaled consumers and also reduced upstream publishing rate with rate limits. We used bounded retries with exponential backoff and a DLQ for poison messages.

Interviewer: How do you approach performance problems?
Candidate: Start with profiling and query plans. For Postgres, I check EXPLAIN, add indexes where it matters, and validate with p95/p99 latency dashboards. For caching, we were careful about cache stampedes and used request coalescing.

Interviewer: Testing and edge cases?
Candidate: I write unit tests for idempotency and retry logic, plus integration tests around Kafka reprocessing. I like to enumerate edge cases first. Complexity-wise, I keep hot paths O(1) where possible.

Interviewer: Incident experience?
Candidate: During incidents, we follow a runbook: mitigate first, then deep dive. RCAs focus on contributing factors and action items. I’ve been the incident commander a few times.
