-- Company firmographics captured by the pre-chat intake form, so analytics can
-- be company-centric (peer benchmarking keys off industry + size). Additive and
-- nullable; name/industry/size_bucket already exist on companies.

ALTER TABLE companies
  ADD COLUMN headcount_band    text,   -- '1-50','51-200','201-1000','1000+'
  ADD COLUMN revenue_band      text,   -- '<$10M','$10-50M','$50-250M','$250M-1B','>$1B'
  ADD COLUMN years_in_business int,
  ADD COLUMN updated_at        timestamptz NOT NULL DEFAULT now();
