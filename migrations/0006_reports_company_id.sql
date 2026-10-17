-- Company-scoped deliverables (Task 8.3): reports can now attach to a company
-- instead of a single session (type='company_external' aggregates all of a
-- company's sessions; 'internal_macro' is cohort-wide with both null).
ALTER TABLE reports ADD COLUMN company_id uuid REFERENCES companies(id);
ALTER TABLE reports ALTER COLUMN session_id DROP NOT NULL;
CREATE INDEX ON reports (company_id, type, created_at);
