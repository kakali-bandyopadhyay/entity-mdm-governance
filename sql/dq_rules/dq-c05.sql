-- Synthetic investment-entity DQ failing-row query; illustrative rule.
SELECT record_id FROM entities WHERE legal_name IS NULL OR TRIM(legal_name) = '';
