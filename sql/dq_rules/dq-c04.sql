-- Synthetic investment-entity DQ failing-row query; illustrative rule.
SELECT e.record_id FROM entities e WHERE e.parent_key IS NOT NULL AND e.parent_key != '' AND NOT EXISTS (SELECT 1 FROM entities p WHERE p.registration_key=e.parent_key);
