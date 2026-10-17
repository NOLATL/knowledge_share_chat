-- Task 0.2 — follow-up FK (Appendix A note). Now that clusters exists, link
-- respondents.cluster_id -> clusters(id). Kept separate from 0001 to avoid the
-- circular create-time dependency.

ALTER TABLE respondents
  ADD CONSTRAINT respondents_cluster_id_fkey
  FOREIGN KEY (cluster_id) REFERENCES clusters(id);
