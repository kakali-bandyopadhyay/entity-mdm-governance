-- Synthetic wealth DQ failing-row query; illustrative rule.
SELECT record_id FROM rule_scope w WHERE parent_client_id IS NOT NULL AND parent_client_id NOT IN (SELECT client_id FROM rule_scope);
