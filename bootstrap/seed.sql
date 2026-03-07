PRAGMA foreign_keys = ON;

BEGIN TRANSACTION;

INSERT INTO customer_org (
    customer_org_id, org_name, org_type, country_code, status, created_at
) VALUES
    (1, 'Seoul Disaster Analytics Center', 'PUBLIC', 'KR', 'ACTIVE', '2026-03-07T09:00:00Z');

INSERT INTO customer_user (
    customer_user_id, customer_org_id, user_name, email, phone, role_code, created_at
) VALUES
    (1, 1, 'Kim Mina', 'mina.kim@example.kr', '+82-2-555-0101', 'REQUESTER', '2026-03-07T09:00:00Z');

INSERT INTO service_policy (
    service_policy_id, policy_name, priority_tier, min_order_area_km2, order_cutoff_hours, max_attempts, status, created_at
) VALUES
    (1, 'KOMPSAT Standard Optical', 'STANDARD', 100.0, 48, 10, 'ACTIVE', '2026-03-01T00:00:00Z'),
    (2, 'KOMPSAT SAR Standard', 'PRIORITY', 100.0, 24, 4, 'ACTIVE', '2026-03-01T00:00:00Z');

INSERT INTO feasibility_request (
    request_id, customer_org_id, customer_user_id, service_policy_id, request_code, request_title, request_description, request_status,
    request_channel, priority_tier, requested_start_at, requested_end_at, emergency_flag,
    repeat_acquisition_flag, monitoring_count, created_at
) VALUES
    (
        1, 1, 1, 1, 'REQ-20260307-SEOUL-001', '서울 AOI 광학 촬영 요청건',
        '서울 도심 재난 대응 분석을 위해 요청 기간 내 구름이 적고 판독이 가능한 최신 고해상도 광학 영상을 확보하고자 합니다.',
        'SUBMITTED',
        'WEB_PORTAL', 'STANDARD', '2026-03-10T00:00:00Z', '2026-03-17T00:00:00Z',
        0, 0, 1, '2026-03-07T10:00:00Z'
    ),
    (
        2, 1, 1, 2, 'REQ-20260307-WESTSEA-SAR-001', '서해 AOI SAR 촬영 요청건',
        '서해 해역 감시를 위해 기상 영향과 무관하게 선박 활동 및 해상 이상 징후를 식별할 수 있는 SAR 영상을 긴급 확보하고자 합니다.',
        'SUBMITTED',
        'WEB_PORTAL', 'PRIORITY', '2026-03-10T00:00:00Z', '2026-03-12T00:00:00Z',
        1, 0, 1, '2026-03-07T10:20:00Z'
    );

INSERT INTO request_external_ref (
    request_external_ref_id, request_id, source_system_code, external_request_code, external_request_title,
    external_customer_org_name, external_requester_name, is_primary, received_at, created_at
) VALUES
    (
        1, 1, 'CUSTOMER_PORTAL', 'EXT-SEOUL-20260307-0001', '서울 도심 재난 대응용 광학 촬영 요청',
        'Seoul Disaster Analytics Center', 'Kim Mina', 1, '2026-03-07T09:58:00Z', '2026-03-07T10:00:00Z'
    ),
    (
        2, 2, 'CUSTOMER_PORTAL', 'EXT-WESTSEA-20260307-0002', '서해 해역 긴급 SAR 촬영 요청',
        'Seoul Disaster Analytics Center', 'Kim Mina', 1, '2026-03-07T10:18:00Z', '2026-03-07T10:20:00Z'
    );

INSERT INTO request_aoi (
    request_aoi_id, request_id, geometry_type, geometry_wkt, srid, area_km2,
    bbox_min_lon, bbox_min_lat, bbox_max_lon, bbox_max_lat, centroid_lon, centroid_lat, dominant_axis_deg, created_at
) VALUES
    (
        1, 1, 'POLYGON',
        'POLYGON((126.88 37.46,127.12 37.46,127.12 37.64,126.88 37.64,126.88 37.46))',
        4326, 420.0,
        126.88, 37.46, 127.12, 37.64, 127.00, 37.55, 145.0, '2026-03-07T10:00:00Z'
    ),
    (
        2, 2, 'POLYGON',
        'POLYGON((124.65 36.85,124.95 36.85,124.95 37.10,124.65 37.10,124.65 36.85))',
        4326, 510.0,
        124.65, 36.85, 124.95, 37.10, 124.80, 36.975, 90.0, '2026-03-07T10:20:00Z'
    );

INSERT INTO request_constraint (
    request_constraint_id, request_id, max_cloud_pct, max_off_nadir_deg, min_incidence_deg, max_incidence_deg,
    preferred_local_time_start, preferred_local_time_end, min_sun_elevation_deg, max_haze_index, deadline_at,
    coverage_ratio_required, created_at
) VALUES
    (
        1, 1, 20.0, 25.0, NULL, NULL,
        '10:00', '14:00', 30.0, 0.4, '2026-03-17T00:00:00Z',
        0.95, '2026-03-07T10:00:00Z'
    ),
    (
        2, 2, NULL, NULL, 25.0, 40.0,
        NULL, NULL, NULL, NULL, '2026-03-12T00:00:00Z',
        0.90, '2026-03-07T10:20:00Z'
    );

INSERT INTO satellite (
    satellite_id, satellite_code, satellite_name, orbit_type, nominal_altitude_km, owner_org, operational_status, created_at
) VALUES
    (1, 'K3', 'KOMPSAT-3', 'LEO-SSO', 685.0, 'KARI', 'ACTIVE', '2012-05-18T00:00:00Z'),
    (2, 'K5', 'KOMPSAT-5', 'LEO-SSO', 550.0, 'KARI', 'ACTIVE', '2013-08-22T00:00:00Z');

INSERT INTO sensor (
    sensor_id, satellite_id, sensor_name, sensor_type, swath_km, max_off_nadir_deg,
    min_incidence_deg, max_incidence_deg, raw_data_rate_mbps, compression_ratio_nominal, created_at
) VALUES
    (1, 1, 'AEISS-A', 'OPTICAL', 15.0, 30.0, NULL, NULL, 1600.0, 2.2, '2012-05-18T00:00:00Z'),
    (2, 2, 'X-Band SAR', 'SAR', 30.0, NULL, 20.0, 45.0, 320.0, 1.8, '2013-08-22T00:00:00Z');

INSERT INTO sensor_mode (
    sensor_mode_id, sensor_id, mode_code, mode_name, ground_resolution_m, swath_km,
    max_duration_sec, duty_cycle_limit_pct, supported_polarizations, warmup_sec, cooldown_sec, created_at
) VALUES
    (1, 1, 'SPOTLIGHT', 'Optical Spotlight', 0.7, 15.0, 70, 15.0, NULL, 20, 30, '2012-05-18T00:00:00Z'),
    (2, 2, 'STRIPMAP', 'SAR Stripmap', 1.0, 30.0, 70, 20.0, 'HH,HV,VV,VH', 10, 20, '2013-08-22T00:00:00Z');

INSERT INTO request_sensor_option (
    request_sensor_option_id, request_id, satellite_id, sensor_id, sensor_mode_id,
    preference_rank, is_mandatory, polarization_code, created_at
) VALUES
    (1, 1, 1, 1, 1, 1, 1, NULL, '2026-03-07T10:01:00Z'),
    (2, 2, 2, 2, 2, 1, 1, 'HH', '2026-03-07T10:21:00Z');

INSERT INTO request_product_option (
    request_product_option_id, request_id, product_level_code, product_type_code,
    file_format_code, delivery_mode_code, ancillary_required_flag, created_at
) VALUES
    (1, 1, 'L1R', 'ORTHO_READY', 'GEOTIFF', 'FTP', 1, '2026-03-07T10:01:00Z'),
    (2, 2, 'L1C', 'SIGMA0', 'HDF5', 'FTP', 1, '2026-03-07T10:21:00Z');

INSERT INTO request_candidate (
    request_candidate_id, request_id, candidate_code, candidate_title, candidate_description,
    candidate_status, candidate_rank, is_baseline, created_at, updated_at
) VALUES
    (1, 1, 'OPT-CAND-001', '기본 조건안', '원 요청 조건을 그대로 적용한 기준 후보입니다.', 'READY', 1, 1, '2026-03-07T10:05:00Z', '2026-03-07T10:05:00Z'),
    (2, 1, 'OPT-CAND-002', '오프나디르 완화 검토안', '촬영 기회 확대를 위해 오프나디르 관련 값을 높여 본 비교 후보입니다.', 'READY', 2, 0, '2026-03-07T10:06:00Z', '2026-03-07T10:06:00Z'),
    (3, 1, 'OPT-CAND-003', '구름 완화 검토안', '구름 영향이 큰 상황에서 활용 가능성을 보기 위한 비교 후보입니다.', 'READY', 3, 0, '2026-03-07T10:07:00Z', '2026-03-07T10:07:00Z'),
    (4, 2, 'SAR-CAND-001', '기본 Stripmap 안', '기본 SAR 촬영 조건으로 가능한지 보는 기준 후보입니다.', 'READY', 1, 1, '2026-03-07T10:25:00Z', '2026-03-07T10:25:00Z'),
    (5, 2, 'SAR-CAND-002', '입사각 초과 비교안', '기하 조건 한계 확인용 비교 후보입니다.', 'READY', 2, 0, '2026-03-07T10:26:00Z', '2026-03-07T10:26:00Z'),
    (6, 2, 'SAR-CAND-003', '저장·전송 병목 비교안', '레코더와 다운링크 부족 시 실패 양상을 확인하기 위한 후보입니다.', 'READY', 3, 0, '2026-03-07T10:27:00Z', '2026-03-07T10:27:00Z');

INSERT INTO request_candidate_input (
    request_candidate_input_id, request_candidate_id, sensor_type, priority_tier, area_km2, window_hours,
    cloud_pct, max_cloud_pct, required_off_nadir_deg, max_off_nadir_deg, predicted_incidence_deg,
    min_incidence_deg, max_incidence_deg, sun_elevation_deg, min_sun_elevation_deg,
    coverage_ratio_predicted, coverage_ratio_required, expected_data_volume_gbit, recorder_free_gbit,
    recorder_backlog_gbit, available_downlink_gbit, power_margin_pct, thermal_margin_pct,
    input_version_no, created_at, updated_at
) VALUES
    (1, 1, 'OPTICAL', 'STANDARD', 400.0, 168.0, 18.0, 20.0, 18.5, 25.0, 30.0, 25.0, 40.0, 44.0, 20.0, 0.98, 0.95, 14.0, 48.0, 12.0, 42.0, 19.0, 16.0, 1, '2026-03-07T10:05:00Z', '2026-03-07T10:05:00Z'),
    (2, 2, 'OPTICAL', 'STANDARD', 400.0, 168.0, 12.0, 20.0, 27.4, 25.0, 30.0, 25.0, 40.0, 46.0, 20.0, 0.99, 0.95, 14.0, 48.0, 8.0, 40.0, 19.0, 17.0, 1, '2026-03-07T10:06:00Z', '2026-03-07T10:06:00Z'),
    (3, 3, 'OPTICAL', 'STANDARD', 400.0, 168.0, 34.0, 20.0, 20.5, 25.0, 30.0, 25.0, 40.0, 42.0, 20.0, 0.97, 0.95, 14.0, 48.0, 10.0, 40.0, 19.0, 15.0, 1, '2026-03-07T10:07:00Z', '2026-03-07T10:07:00Z'),
    (4, 4, 'SAR', 'PRIORITY', 625.0, 48.0, 0.0, 100.0, 0.0, 40.0, 28.0, 25.0, 40.0, 0.0, 0.0, 0.99, 0.95, 22.0, 44.0, 8.0, 36.0, 18.0, 16.0, 1, '2026-03-07T10:25:00Z', '2026-03-07T10:25:00Z'),
    (5, 5, 'SAR', 'PRIORITY', 625.0, 48.0, 0.0, 100.0, 0.0, 40.0, 42.0, 25.0, 40.0, 0.0, 0.0, 0.98, 0.95, 24.0, 42.0, 10.0, 40.0, 17.0, 15.0, 1, '2026-03-07T10:26:00Z', '2026-03-07T10:26:00Z'),
    (6, 6, 'SAR', 'PRIORITY', 625.0, 48.0, 0.0, 100.0, 0.0, 40.0, 33.0, 25.0, 40.0, 0.0, 0.0, 0.98, 0.95, 28.0, 22.0, 20.0, 34.0, 14.0, 12.0, 1, '2026-03-07T10:27:00Z', '2026-03-07T10:27:00Z');

INSERT INTO ground_station (
    ground_station_id, station_code, station_name, country_code, latitude_deg, longitude_deg, status, created_at
) VALUES
    (1, 'JEJU', 'Jeju Ground Station', 'KR', 33.3940, 126.5350, 'ACTIVE', '2020-01-01T00:00:00Z'),
    (2, 'DAEJEON', 'Daejeon Ground Station', 'KR', 36.3504, 127.3845, 'ACTIVE', '2020-01-01T00:00:00Z');

INSERT INTO orbit_snapshot (
    orbit_snapshot_id, source_system, source_version, generated_at, valid_from, valid_to, propagation_model
) VALUES
    (1, 'flight-dynamics', 'v2.3.1', '2026-03-09T00:00:00Z', '2026-03-10T00:00:00Z', '2026-03-17T00:00:00Z', 'SGP4+OPS');

INSERT INTO satellite_pass (
    satellite_pass_id, orbit_snapshot_id, satellite_id, pass_start_at, pass_end_at,
    ascending_descending_code, subsat_track_wkt
) VALUES
    (1, 1, 1, '2026-03-11T02:10:00Z', '2026-03-11T02:22:00Z', 'DESC', 'LINESTRING(126.0 38.2,127.4 36.9)'),
    (2, 1, 1, '2026-03-13T02:14:00Z', '2026-03-13T02:26:00Z', 'DESC', 'LINESTRING(126.1 38.3,127.5 37.0)'),
    (3, 1, 1, '2026-03-15T02:18:00Z', '2026-03-15T02:30:00Z', 'DESC', 'LINESTRING(125.9 38.1,127.3 36.8)'),
    (4, 1, 2, '2026-03-10T18:02:00Z', '2026-03-10T18:14:00Z', 'ASC', 'LINESTRING(123.8 36.2,125.6 37.8)'),
    (5, 1, 2, '2026-03-11T18:07:00Z', '2026-03-11T18:19:00Z', 'ASC', 'LINESTRING(124.0 36.1,125.8 37.7)'),
    (6, 1, 2, '2026-03-11T21:10:00Z', '2026-03-11T21:22:00Z', 'ASC', 'LINESTRING(123.9 36.0,125.7 37.6)');

INSERT INTO access_opportunity (
    access_opportunity_id, satellite_pass_id, request_aoi_id, sensor_id, sensor_mode_id,
    access_start_at, access_end_at, required_off_nadir_deg, predicted_incidence_deg,
    coverage_ratio_predicted, geometric_feasible_flag, created_at
) VALUES
    (1, 1, 1, 1, 1, '2026-03-11T02:14:30Z', '2026-03-11T02:15:40Z', 18.2, NULL, 0.98, 1, '2026-03-09T00:05:00Z'),
    (2, 2, 1, 1, 1, '2026-03-13T02:18:20Z', '2026-03-13T02:19:30Z', 27.4, NULL, 0.94, 0, '2026-03-09T00:05:00Z'),
    (3, 3, 1, 1, 1, '2026-03-15T02:22:10Z', '2026-03-15T02:23:20Z', 21.0, NULL, 0.99, 1, '2026-03-09T00:05:00Z'),
    (4, 4, 2, 2, 2, '2026-03-10T18:06:10Z', '2026-03-10T18:07:20Z', NULL, 28.0, 0.97, 1, '2026-03-09T00:06:00Z'),
    (5, 5, 2, 2, 2, '2026-03-11T18:11:10Z', '2026-03-11T18:12:20Z', NULL, 42.0, 0.95, 0, '2026-03-09T00:06:00Z'),
    (6, 6, 2, 2, 2, '2026-03-11T21:14:10Z', '2026-03-11T21:15:20Z', NULL, 33.0, 0.96, 1, '2026-03-09T00:06:00Z');

INSERT INTO weather_snapshot (
    weather_snapshot_id, provider_code, forecast_base_at, valid_from, valid_to, spatial_resolution_km
) VALUES
    (1, 'KMA-GFS', '2026-03-09T00:00:00Z', '2026-03-10T00:00:00Z', '2026-03-17T00:00:00Z', 3.0);

INSERT INTO weather_cell_forecast (
    weather_cell_forecast_id, weather_snapshot_id, target_area_code, forecast_at, cloud_pct, haze_index, confidence_score
) VALUES
    (1, 1, 'AOI-REQ-1', '2026-03-11T02:15:00Z', 18.0, 0.20, 0.86),
    (2, 1, 'AOI-REQ-1', '2026-03-13T02:19:00Z', 42.0, 0.32, 0.79),
    (3, 1, 'AOI-REQ-1', '2026-03-15T02:23:00Z', 24.0, 0.18, 0.82);

INSERT INTO solar_condition_snapshot (
    solar_condition_snapshot_id, generated_at, algorithm_version, target_area_code,
    target_time, sun_elevation_deg, sun_azimuth_deg, daylight_flag
) VALUES
    (1, '2026-03-09T00:00:00Z', 'solar-v1.4', 'AOI-REQ-1', '2026-03-11T02:15:00Z', 41.3, 154.1, 1);

INSERT INTO terrain_risk_snapshot (
    terrain_risk_snapshot_id, dem_source, generated_at, target_area_code, risk_type, risk_score
) VALUES
    (1, 'SRTM-30M', '2026-03-09T00:00:00Z', 'AOI-REQ-1', 'SAR_LAYOVER', 0.08),
    (2, 'SRTM-30M', '2026-03-09T00:00:00Z', 'AOI-REQ-2', 'SAR_LAYOVER', 0.12);

INSERT INTO spacecraft_resource_snapshot (
    resource_snapshot_id, satellite_id, snapshot_at, recorder_free_gbit, recorder_backlog_gbit,
    power_margin_pct, battery_soc_pct, thermal_margin_pct, instrument_duty_used_pct
) VALUES
    (1, 1, '2026-03-09T00:10:00Z', 68.0, 12.5, 23.0, 77.0, 18.0, 9.0),
    (2, 2, '2026-03-09T00:10:00Z', 14.0, 36.0, 21.0, 81.0, 16.0, 11.0);

INSERT INTO station_contact_window (
    contact_window_id, ground_station_id, satellite_id, contact_start_at, contact_end_at,
    downlink_rate_mbps, link_efficiency_pct, availability_status
) VALUES
    (1, 1, 1, '2026-03-11T03:01:00Z', '2026-03-11T03:09:00Z', 310.0, 0.76, 'AVAILABLE'),
    (2, 2, 1, '2026-03-15T03:05:00Z', '2026-03-15T03:13:00Z', 310.0, 0.75, 'AVAILABLE'),
    (3, 1, 2, '2026-03-10T18:40:00Z', '2026-03-10T18:47:00Z', 310.0, 0.74, 'AVAILABLE'),
    (4, 2, 2, '2026-03-11T21:42:00Z', '2026-03-11T21:49:00Z', 310.0, 0.74, 'AVAILABLE');

INSERT INTO existing_task (
    existing_task_id, satellite_id, task_start_at, task_end_at, priority_tier, reserved_volume_gbit, task_status
) VALUES
    (1, 1, '2026-03-13T02:17:40Z', '2026-03-13T02:18:50Z', 'ASSURED', 18.0, 'SCHEDULED'),
    (2, 2, '2026-03-11T20:50:00Z', '2026-03-11T21:05:00Z', 'PRIORITY', 8.0, 'SCHEDULED');

INSERT INTO existing_downlink_booking (
    existing_downlink_booking_id, ground_station_id, satellite_id, booking_start_at, booking_end_at,
    reserved_volume_gbit, booking_status
) VALUES
    (1, 1, 1, '2026-03-11T03:01:00Z', '2026-03-11T03:04:00Z', 24.0, 'RESERVED'),
    (2, 1, 2, '2026-03-10T18:40:00Z', '2026-03-10T18:43:30Z', 21.0, 'RESERVED');

COMMIT;
