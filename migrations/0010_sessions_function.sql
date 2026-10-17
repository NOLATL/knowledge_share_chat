-- The business FUNCTION a session belongs to (Accounting, FP&A, Treasury...),
-- chosen on the intake form. A "function" is the distinct (company_id,
-- function_key) pair: multiple sessions roll up into one function, and multiple
-- functions roll up into one company. Nullable — legacy/demo sessions have none.
ALTER TABLE sessions ADD COLUMN function_key text;
