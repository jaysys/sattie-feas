SELECT
  fr.request_code,
  rc.candidate_code,
  rc.candidate_title,
  rc.candidate_status,
  rci.sensor_type,
  COALESCE(rcr.run_sequence_no, 0) AS run_sequence_no,
  rcr.final_verdict,
  ROUND(rcr.p_total_candidate, 4) AS p_total_candidate,
  rcr.dominant_risk_code
FROM request_candidate rc
JOIN feasibility_request fr ON fr.request_id = rc.request_id
JOIN request_candidate_input rci ON rci.request_candidate_id = rc.request_candidate_id
LEFT JOIN request_candidate_run rcr ON rcr.request_candidate_run_id = (
  SELECT rcr2.request_candidate_run_id
  FROM request_candidate_run rcr2
  WHERE rcr2.request_candidate_id = rc.request_candidate_id
  ORDER BY rcr2.simulated_at DESC, rcr2.request_candidate_run_id DESC
  LIMIT 1
)
ORDER BY fr.request_id, rc.candidate_rank;

SELECT
  rc.candidate_code,
  COUNT(rcr.request_candidate_run_id) AS run_count
FROM request_candidate rc
LEFT JOIN request_candidate_run rcr ON rcr.request_candidate_id = rc.request_candidate_id
GROUP BY rc.request_candidate_id, rc.candidate_code
ORDER BY rc.request_candidate_id;
