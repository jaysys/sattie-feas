.print '=== SAR Scenario 1: Request Header and Constraints ==='
SELECT fr.request_code,
       fr.request_title,
       fr.priority_tier,
       fr.emergency_flag,
       fr.requested_start_at,
       fr.requested_end_at,
       rc.min_incidence_deg,
       rc.max_incidence_deg,
       rc.coverage_ratio_required
FROM feasibility_request fr
JOIN request_constraint rc ON rc.request_id = fr.request_id
WHERE fr.request_code = 'REQ-20260307-WESTSEA-SAR-001';

.print ''
.print '=== SAR Scenario 2: Seeded Request Candidates and Inputs ==='
SELECT rc.candidate_code,
       rc.candidate_title,
       rc.candidate_status,
       rci.predicted_incidence_deg,
       rci.min_incidence_deg,
       rci.max_incidence_deg,
       rci.expected_data_volume_gbit,
       rci.recorder_free_gbit,
       rci.recorder_backlog_gbit,
       rci.available_downlink_gbit
FROM request_candidate rc
JOIN request_candidate_input rci ON rci.request_candidate_id = rc.request_candidate_id
WHERE rc.request_id = 2
ORDER BY rc.candidate_rank;

.print ''
.print '=== SAR Scenario 3: Seeded Candidate Runs Must Be Empty Initially ==='
SELECT rc.candidate_code,
       COUNT(rcr.request_candidate_run_id) AS run_count
FROM request_candidate rc
LEFT JOIN request_candidate_run rcr ON rcr.request_candidate_id = rc.request_candidate_id
WHERE rc.request_id = 2
GROUP BY rc.request_candidate_id, rc.candidate_code
ORDER BY rc.candidate_rank;
