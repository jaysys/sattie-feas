.print '=== Optical Scenario 1: Request Header and Constraints ==='
SELECT fr.request_code,
       fr.request_title,
       fr.priority_tier,
       fr.requested_start_at,
       fr.requested_end_at,
       rc.max_cloud_pct,
       rc.max_off_nadir_deg,
       rc.min_sun_elevation_deg,
       rc.coverage_ratio_required
FROM feasibility_request fr
JOIN request_constraint rc ON rc.request_id = fr.request_id
WHERE fr.request_code = 'REQ-20260307-SEOUL-001';

.print ''
.print '=== Optical Scenario 2: Seeded Request Candidates and Inputs ==='
SELECT rc.candidate_code,
       rc.candidate_title,
       rc.candidate_status,
       rci.cloud_pct,
       rci.max_cloud_pct,
       rci.required_off_nadir_deg,
       rci.max_off_nadir_deg,
       rci.sun_elevation_deg,
       rci.expected_data_volume_gbit
FROM request_candidate rc
JOIN request_candidate_input rci ON rci.request_candidate_id = rc.request_candidate_id
WHERE rc.request_id = 1
ORDER BY rc.candidate_rank;

.print ''
.print '=== Optical Scenario 3: Seeded Candidate Runs Must Be Empty Initially ==='
SELECT rc.candidate_code,
       COUNT(rcr.request_candidate_run_id) AS run_count
FROM request_candidate rc
LEFT JOIN request_candidate_run rcr ON rcr.request_candidate_id = rc.request_candidate_id
WHERE rc.request_id = 1
GROUP BY rc.request_candidate_id, rc.candidate_code
ORDER BY rc.candidate_rank;
