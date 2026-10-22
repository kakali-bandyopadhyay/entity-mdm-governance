-- Synthetic wealth DQ failing-row query; illustrative rule.
SELECT record_id FROM rule_scope WHERE booking_country IS NULL OR TRIM(booking_country) = '';
