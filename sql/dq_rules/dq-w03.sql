-- Synthetic wealth DQ failing-row query; illustrative rule.
SELECT w.record_id FROM rule_scope w JOIN (SELECT account_id FROM rule_scope GROUP BY account_id HAVING COUNT(*) > 1) d ON w.account_id = d.account_id;
