Interviewer: Tell me about a project you’re proud of.
Candidate: I built a task tracker for my capstone. I designed REST endpoints for tasks and users, and used PostgreSQL for storage. For auth I used JWT.

Interviewer: Any tradeoffs you made?
Candidate: I chose a relational DB because relations were simple and I wanted constraints. For the API, I tried to keep endpoints consistent and returned clear errors.

Interviewer: Testing?
Candidate: I wrote unit tests for validation and auth helpers, and added a few integration tests. I also thought about edge cases like missing fields and invalid tokens.

Interviewer: Complexity or performance considerations?
Candidate: Mostly basic. I know Big O in general, but I didn’t do heavy optimization because the dataset was small.

Interviewer: Anything you haven’t used but listed on your resume?
Candidate: I’ve used Docker for local dev, but not Kubernetes.
