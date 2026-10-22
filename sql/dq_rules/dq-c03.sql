-- Synthetic investment-entity DQ failing-row query; illustrative rule.
SELECT a.registration_key FROM entities a JOIN entities b ON a.registration_key=b.registration_key AND a.record_id < b.record_id WHERE a.registration_key IS NOT NULL AND (a.entity_type != b.entity_type OR a.jurisdiction != b.jurisdiction OR name_similarity(a.legal_name,b.legal_name) < 0.85) GROUP BY a.registration_key;
