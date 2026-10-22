-- Synthetic investment-entity DQ failing-row query; illustrative rule.
SELECT e.record_id FROM entities e LEFT JOIN allowed_jurisdictions a ON e.jurisdiction = a.code WHERE a.code IS NULL;
