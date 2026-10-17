-- Human-friendly, generated company identifier (account code) that is stable
-- over time, shared by all of a company's respondents/sessions, and easy to
-- quote when pulling data (vs a UUID). DB-side default covers every insert
-- path (intake upsert, demo backfills, synthetic seeding).
CREATE SEQUENCE company_account_code_seq;

ALTER TABLE companies ADD COLUMN account_code text UNIQUE
  DEFAULT ('C-' || lpad(nextval('company_account_code_seq')::text, 5, '0'));

UPDATE companies
SET account_code = 'C-' || lpad(nextval('company_account_code_seq')::text, 5, '0')
WHERE account_code IS NULL;

ALTER TABLE companies ALTER COLUMN account_code SET NOT NULL;
