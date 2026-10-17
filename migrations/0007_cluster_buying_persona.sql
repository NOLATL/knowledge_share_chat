-- Buying persona per cluster (Task 8.4): LLM-generated descriptor of who buys
-- and why, used by the internal intelligence view for market-fit tailoring.
ALTER TABLE clusters ADD COLUMN buying_persona text;
