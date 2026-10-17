-- Function-level external reports (redesign Phase 3): a report can be scoped to
-- a (company_id, function_key) pair. Company-external reports keep function_key
-- NULL; the new type 'function_external' sets it.
ALTER TABLE reports ADD COLUMN function_key text;
