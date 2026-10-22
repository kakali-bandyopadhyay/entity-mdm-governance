-- Synthetic investment-entity DQ failing-row query; illustrative rule.
SELECT record_id FROM entities WHERE registration_key IS NULL OR TRIM(registration_key) = '';
