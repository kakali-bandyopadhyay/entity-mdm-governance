-- Synthetic wealth DQ failing-row query; illustrative rule.
SELECT record_id FROM rule_scope WHERE kyc_status NOT IN ('CURRENT','DUE','IN_PROGRESS','NOT_REQUIRED') OR kyc_status IS NULL;
