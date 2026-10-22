-- Synthetic wealth DQ failing-row query; illustrative rule.
SELECT record_id FROM rule_scope WHERE risk_rating IS NULL OR TRIM(risk_rating) = '';
