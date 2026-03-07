PRAGMA foreign_keys = ON;

BEGIN TRANSACTION;

CREATE TABLE customer_org (
    customer_org_id INTEGER PRIMARY KEY,
    org_name TEXT NOT NULL,
    org_type TEXT NOT NULL,
    country_code TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'ACTIVE',
    created_at TEXT NOT NULL
);

CREATE TABLE customer_user (
    customer_user_id INTEGER PRIMARY KEY,
    customer_org_id INTEGER NOT NULL,
    user_name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    phone TEXT,
    role_code TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (customer_org_id) REFERENCES customer_org(customer_org_id)
);

CREATE TABLE service_policy (
    service_policy_id INTEGER PRIMARY KEY,
    policy_name TEXT NOT NULL,
    priority_tier TEXT NOT NULL,
    min_order_area_km2 REAL NOT NULL,
    order_cutoff_hours INTEGER NOT NULL,
    max_attempts INTEGER,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE feasibility_request (
    request_id INTEGER PRIMARY KEY,
    customer_org_id INTEGER NOT NULL,
    customer_user_id INTEGER NOT NULL,
    service_policy_id INTEGER NOT NULL,
    request_code TEXT NOT NULL UNIQUE,
    request_title TEXT NOT NULL,
    request_description TEXT NOT NULL,
    request_status TEXT NOT NULL,
    request_channel TEXT NOT NULL,
    priority_tier TEXT NOT NULL,
    requested_start_at TEXT NOT NULL,
    requested_end_at TEXT NOT NULL,
    emergency_flag INTEGER NOT NULL DEFAULT 0 CHECK (emergency_flag IN (0, 1)),
    repeat_acquisition_flag INTEGER NOT NULL DEFAULT 0 CHECK (repeat_acquisition_flag IN (0, 1)),
    monitoring_count INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    FOREIGN KEY (customer_org_id) REFERENCES customer_org(customer_org_id),
    FOREIGN KEY (customer_user_id) REFERENCES customer_user(customer_user_id),
    FOREIGN KEY (service_policy_id) REFERENCES service_policy(service_policy_id)
);

CREATE TABLE request_external_ref (
    request_external_ref_id INTEGER PRIMARY KEY,
    request_id INTEGER NOT NULL,
    source_system_code TEXT NOT NULL,
    external_request_code TEXT NOT NULL,
    external_request_title TEXT,
    external_customer_org_name TEXT,
    external_requester_name TEXT,
    is_primary INTEGER NOT NULL DEFAULT 1 CHECK (is_primary IN (0, 1)),
    received_at TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (request_id) REFERENCES feasibility_request(request_id),
    UNIQUE (source_system_code, external_request_code)
);

CREATE TABLE request_aoi (
    request_aoi_id INTEGER PRIMARY KEY,
    request_id INTEGER NOT NULL UNIQUE,
    geometry_type TEXT NOT NULL,
    geometry_wkt TEXT NOT NULL,
    srid INTEGER NOT NULL DEFAULT 4326,
    area_km2 REAL NOT NULL,
    bbox_min_lon REAL NOT NULL,
    bbox_min_lat REAL NOT NULL,
    bbox_max_lon REAL NOT NULL,
    bbox_max_lat REAL NOT NULL,
    centroid_lon REAL NOT NULL,
    centroid_lat REAL NOT NULL,
    dominant_axis_deg REAL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (request_id) REFERENCES feasibility_request(request_id)
);

CREATE TABLE request_constraint (
    request_constraint_id INTEGER PRIMARY KEY,
    request_id INTEGER NOT NULL UNIQUE,
    max_cloud_pct REAL,
    max_off_nadir_deg REAL,
    min_incidence_deg REAL,
    max_incidence_deg REAL,
    preferred_local_time_start TEXT,
    preferred_local_time_end TEXT,
    min_sun_elevation_deg REAL,
    max_haze_index REAL,
    deadline_at TEXT,
    coverage_ratio_required REAL NOT NULL DEFAULT 1.0,
    created_at TEXT NOT NULL,
    FOREIGN KEY (request_id) REFERENCES feasibility_request(request_id)
);

CREATE TABLE satellite (
    satellite_id INTEGER PRIMARY KEY,
    satellite_code TEXT NOT NULL UNIQUE,
    satellite_name TEXT NOT NULL,
    orbit_type TEXT NOT NULL,
    nominal_altitude_km REAL NOT NULL,
    owner_org TEXT NOT NULL,
    operational_status TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE sensor (
    sensor_id INTEGER PRIMARY KEY,
    satellite_id INTEGER NOT NULL,
    sensor_name TEXT NOT NULL,
    sensor_type TEXT NOT NULL,
    swath_km REAL NOT NULL,
    max_off_nadir_deg REAL,
    min_incidence_deg REAL,
    max_incidence_deg REAL,
    raw_data_rate_mbps REAL NOT NULL,
    compression_ratio_nominal REAL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (satellite_id) REFERENCES satellite(satellite_id)
);

CREATE TABLE sensor_mode (
    sensor_mode_id INTEGER PRIMARY KEY,
    sensor_id INTEGER NOT NULL,
    mode_code TEXT NOT NULL,
    mode_name TEXT NOT NULL,
    ground_resolution_m REAL NOT NULL,
    swath_km REAL NOT NULL,
    max_duration_sec INTEGER NOT NULL,
    duty_cycle_limit_pct REAL NOT NULL,
    supported_polarizations TEXT,
    warmup_sec INTEGER NOT NULL DEFAULT 0,
    cooldown_sec INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    UNIQUE (sensor_id, mode_code),
    FOREIGN KEY (sensor_id) REFERENCES sensor(sensor_id)
);

CREATE TABLE request_sensor_option (
    request_sensor_option_id INTEGER PRIMARY KEY,
    request_id INTEGER NOT NULL,
    satellite_id INTEGER NOT NULL,
    sensor_id INTEGER NOT NULL,
    sensor_mode_id INTEGER NOT NULL,
    preference_rank INTEGER NOT NULL,
    is_mandatory INTEGER NOT NULL DEFAULT 0 CHECK (is_mandatory IN (0, 1)),
    polarization_code TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (request_id) REFERENCES feasibility_request(request_id),
    FOREIGN KEY (satellite_id) REFERENCES satellite(satellite_id),
    FOREIGN KEY (sensor_id) REFERENCES sensor(sensor_id),
    FOREIGN KEY (sensor_mode_id) REFERENCES sensor_mode(sensor_mode_id)
);

CREATE TABLE request_product_option (
    request_product_option_id INTEGER PRIMARY KEY,
    request_id INTEGER NOT NULL,
    product_level_code TEXT NOT NULL,
    product_type_code TEXT NOT NULL,
    file_format_code TEXT NOT NULL,
    delivery_mode_code TEXT NOT NULL,
    ancillary_required_flag INTEGER NOT NULL DEFAULT 0 CHECK (ancillary_required_flag IN (0, 1)),
    created_at TEXT NOT NULL,
    FOREIGN KEY (request_id) REFERENCES feasibility_request(request_id)
);

CREATE TABLE request_candidate (
    request_candidate_id INTEGER PRIMARY KEY,
    request_id INTEGER NOT NULL,
    candidate_code TEXT NOT NULL,
    candidate_title TEXT NOT NULL,
    candidate_description TEXT NOT NULL,
    candidate_status TEXT NOT NULL,
    candidate_rank INTEGER NOT NULL,
    is_baseline INTEGER NOT NULL DEFAULT 0 CHECK (is_baseline IN (0, 1)),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (request_id) REFERENCES feasibility_request(request_id),
    UNIQUE (request_id, candidate_code)
);

CREATE TABLE request_candidate_input (
    request_candidate_input_id INTEGER PRIMARY KEY,
    request_candidate_id INTEGER NOT NULL UNIQUE,
    sensor_type TEXT NOT NULL,
    priority_tier TEXT NOT NULL,
    area_km2 REAL NOT NULL,
    window_hours REAL NOT NULL,
    opportunity_start_at TEXT,
    opportunity_end_at TEXT,
    cloud_pct REAL,
    max_cloud_pct REAL,
    required_off_nadir_deg REAL,
    max_off_nadir_deg REAL,
    predicted_incidence_deg REAL,
    min_incidence_deg REAL,
    max_incidence_deg REAL,
    sun_elevation_deg REAL,
    min_sun_elevation_deg REAL,
    coverage_ratio_predicted REAL NOT NULL,
    coverage_ratio_required REAL NOT NULL,
    expected_data_volume_gbit REAL NOT NULL,
    recorder_free_gbit REAL NOT NULL,
    recorder_backlog_gbit REAL NOT NULL,
    available_downlink_gbit REAL NOT NULL,
    power_margin_pct REAL NOT NULL,
    thermal_margin_pct REAL NOT NULL,
    input_version_no INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (request_candidate_id) REFERENCES request_candidate(request_candidate_id)
);

CREATE TABLE request_candidate_run (
    request_candidate_run_id INTEGER PRIMARY KEY,
    request_candidate_id INTEGER NOT NULL,
    run_sequence_no INTEGER NOT NULL,
    input_version_no INTEGER,
    simulated_at TEXT NOT NULL,
    run_trigger_type TEXT,
    run_trigger_source_code TEXT,
    run_trigger_parameter_name TEXT,
    run_trigger_note TEXT,
    candidate_status TEXT NOT NULL,
    final_verdict TEXT NOT NULL,
    summary_message TEXT NOT NULL,
    dominant_risk_code TEXT,
    p_geo REAL NOT NULL,
    p_env REAL NOT NULL,
    p_resource REAL NOT NULL,
    p_downlink REAL NOT NULL,
    p_conflict_adjusted REAL NOT NULL,
    p_total_candidate REAL NOT NULL,
    resource_feasible_flag INTEGER NOT NULL CHECK (resource_feasible_flag IN (0, 1)),
    downlink_feasible_flag INTEGER NOT NULL CHECK (downlink_feasible_flag IN (0, 1)),
    storage_headroom_gbit REAL NOT NULL,
    backlog_after_capture_gbit REAL NOT NULL,
    downlink_margin_gbit REAL NOT NULL,
    FOREIGN KEY (request_candidate_id) REFERENCES request_candidate(request_candidate_id),
    UNIQUE (request_candidate_id, run_sequence_no)
);

CREATE TABLE request_candidate_run_reason (
    request_candidate_run_reason_id INTEGER PRIMARY KEY,
    request_candidate_run_id INTEGER NOT NULL,
    reason_code TEXT NOT NULL,
    reason_stage TEXT NOT NULL,
    reason_severity TEXT NOT NULL,
    reason_message TEXT NOT NULL,
    FOREIGN KEY (request_candidate_run_id) REFERENCES request_candidate_run(request_candidate_run_id)
);

CREATE TABLE request_candidate_run_recommendation (
    request_candidate_run_recommendation_id INTEGER PRIMARY KEY,
    request_candidate_run_id INTEGER NOT NULL,
    parameter_name TEXT NOT NULL,
    current_value TEXT NOT NULL,
    recommended_value TEXT NOT NULL,
    expected_effect_message TEXT NOT NULL,
    FOREIGN KEY (request_candidate_run_id) REFERENCES request_candidate_run(request_candidate_run_id)
);

CREATE TABLE ground_station (
    ground_station_id INTEGER PRIMARY KEY,
    station_code TEXT NOT NULL UNIQUE,
    station_name TEXT NOT NULL,
    country_code TEXT NOT NULL,
    latitude_deg REAL NOT NULL,
    longitude_deg REAL NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE orbit_snapshot (
    orbit_snapshot_id INTEGER PRIMARY KEY,
    source_system TEXT NOT NULL,
    source_version TEXT NOT NULL,
    generated_at TEXT NOT NULL,
    valid_from TEXT NOT NULL,
    valid_to TEXT NOT NULL,
    propagation_model TEXT NOT NULL
);

CREATE TABLE satellite_pass (
    satellite_pass_id INTEGER PRIMARY KEY,
    orbit_snapshot_id INTEGER NOT NULL,
    satellite_id INTEGER NOT NULL,
    pass_start_at TEXT NOT NULL,
    pass_end_at TEXT NOT NULL,
    ascending_descending_code TEXT NOT NULL,
    subsat_track_wkt TEXT,
    FOREIGN KEY (orbit_snapshot_id) REFERENCES orbit_snapshot(orbit_snapshot_id),
    FOREIGN KEY (satellite_id) REFERENCES satellite(satellite_id)
);

CREATE TABLE access_opportunity (
    access_opportunity_id INTEGER PRIMARY KEY,
    satellite_pass_id INTEGER NOT NULL,
    request_aoi_id INTEGER NOT NULL,
    sensor_id INTEGER NOT NULL,
    sensor_mode_id INTEGER NOT NULL,
    access_start_at TEXT NOT NULL,
    access_end_at TEXT NOT NULL,
    required_off_nadir_deg REAL,
    predicted_incidence_deg REAL,
    coverage_ratio_predicted REAL NOT NULL,
    geometric_feasible_flag INTEGER NOT NULL CHECK (geometric_feasible_flag IN (0, 1)),
    created_at TEXT NOT NULL,
    FOREIGN KEY (satellite_pass_id) REFERENCES satellite_pass(satellite_pass_id),
    FOREIGN KEY (request_aoi_id) REFERENCES request_aoi(request_aoi_id),
    FOREIGN KEY (sensor_id) REFERENCES sensor(sensor_id),
    FOREIGN KEY (sensor_mode_id) REFERENCES sensor_mode(sensor_mode_id)
);

CREATE TABLE weather_snapshot (
    weather_snapshot_id INTEGER PRIMARY KEY,
    provider_code TEXT NOT NULL,
    forecast_base_at TEXT NOT NULL,
    valid_from TEXT NOT NULL,
    valid_to TEXT NOT NULL,
    spatial_resolution_km REAL NOT NULL
);

CREATE TABLE weather_cell_forecast (
    weather_cell_forecast_id INTEGER PRIMARY KEY,
    weather_snapshot_id INTEGER NOT NULL,
    target_area_code TEXT NOT NULL,
    forecast_at TEXT NOT NULL,
    cloud_pct REAL NOT NULL,
    haze_index REAL,
    confidence_score REAL NOT NULL,
    FOREIGN KEY (weather_snapshot_id) REFERENCES weather_snapshot(weather_snapshot_id)
);

CREATE TABLE solar_condition_snapshot (
    solar_condition_snapshot_id INTEGER PRIMARY KEY,
    generated_at TEXT NOT NULL,
    algorithm_version TEXT NOT NULL,
    target_area_code TEXT NOT NULL,
    target_time TEXT NOT NULL,
    sun_elevation_deg REAL NOT NULL,
    sun_azimuth_deg REAL NOT NULL,
    daylight_flag INTEGER NOT NULL CHECK (daylight_flag IN (0, 1))
);

CREATE TABLE terrain_risk_snapshot (
    terrain_risk_snapshot_id INTEGER PRIMARY KEY,
    dem_source TEXT NOT NULL,
    generated_at TEXT NOT NULL,
    target_area_code TEXT NOT NULL,
    risk_type TEXT NOT NULL,
    risk_score REAL NOT NULL
);

CREATE TABLE spacecraft_resource_snapshot (
    resource_snapshot_id INTEGER PRIMARY KEY,
    satellite_id INTEGER NOT NULL,
    snapshot_at TEXT NOT NULL,
    recorder_free_gbit REAL NOT NULL,
    recorder_backlog_gbit REAL NOT NULL,
    power_margin_pct REAL NOT NULL,
    battery_soc_pct REAL NOT NULL,
    thermal_margin_pct REAL NOT NULL,
    instrument_duty_used_pct REAL NOT NULL,
    FOREIGN KEY (satellite_id) REFERENCES satellite(satellite_id)
);

CREATE TABLE station_contact_window (
    contact_window_id INTEGER PRIMARY KEY,
    ground_station_id INTEGER NOT NULL,
    satellite_id INTEGER NOT NULL,
    contact_start_at TEXT NOT NULL,
    contact_end_at TEXT NOT NULL,
    downlink_rate_mbps REAL NOT NULL,
    link_efficiency_pct REAL NOT NULL,
    availability_status TEXT NOT NULL,
    FOREIGN KEY (ground_station_id) REFERENCES ground_station(ground_station_id),
    FOREIGN KEY (satellite_id) REFERENCES satellite(satellite_id)
);

CREATE TABLE existing_task (
    existing_task_id INTEGER PRIMARY KEY,
    satellite_id INTEGER NOT NULL,
    task_start_at TEXT NOT NULL,
    task_end_at TEXT NOT NULL,
    priority_tier TEXT NOT NULL,
    reserved_volume_gbit REAL NOT NULL,
    task_status TEXT NOT NULL,
    FOREIGN KEY (satellite_id) REFERENCES satellite(satellite_id)
);

CREATE TABLE existing_downlink_booking (
    existing_downlink_booking_id INTEGER PRIMARY KEY,
    ground_station_id INTEGER NOT NULL,
    satellite_id INTEGER NOT NULL,
    booking_start_at TEXT NOT NULL,
    booking_end_at TEXT NOT NULL,
    reserved_volume_gbit REAL NOT NULL,
    booking_status TEXT NOT NULL,
    FOREIGN KEY (ground_station_id) REFERENCES ground_station(ground_station_id),
    FOREIGN KEY (satellite_id) REFERENCES satellite(satellite_id)
);

CREATE TABLE feasibility_run (
    run_id INTEGER PRIMARY KEY,
    request_id INTEGER NOT NULL,
    run_status TEXT NOT NULL,
    algorithm_version TEXT NOT NULL,
    trigger_type TEXT NOT NULL,
    started_at TEXT NOT NULL,
    completed_at TEXT,
    FOREIGN KEY (request_id) REFERENCES feasibility_request(request_id)
);

CREATE TABLE run_input_bundle (
    run_input_bundle_id INTEGER PRIMARY KEY,
    run_id INTEGER NOT NULL UNIQUE,
    orbit_snapshot_id INTEGER NOT NULL,
    weather_snapshot_id INTEGER,
    solar_condition_snapshot_id INTEGER,
    terrain_risk_snapshot_id INTEGER,
    resource_snapshot_id INTEGER NOT NULL,
    policy_version TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (run_id) REFERENCES feasibility_run(run_id),
    FOREIGN KEY (orbit_snapshot_id) REFERENCES orbit_snapshot(orbit_snapshot_id),
    FOREIGN KEY (weather_snapshot_id) REFERENCES weather_snapshot(weather_snapshot_id),
    FOREIGN KEY (solar_condition_snapshot_id) REFERENCES solar_condition_snapshot(solar_condition_snapshot_id),
    FOREIGN KEY (terrain_risk_snapshot_id) REFERENCES terrain_risk_snapshot(terrain_risk_snapshot_id),
    FOREIGN KEY (resource_snapshot_id) REFERENCES spacecraft_resource_snapshot(resource_snapshot_id)
);

CREATE TABLE run_input_contact_window (
    run_input_contact_window_id INTEGER PRIMARY KEY,
    run_input_bundle_id INTEGER NOT NULL,
    contact_window_id INTEGER NOT NULL,
    FOREIGN KEY (run_input_bundle_id) REFERENCES run_input_bundle(run_input_bundle_id),
    FOREIGN KEY (contact_window_id) REFERENCES station_contact_window(contact_window_id),
    UNIQUE (run_input_bundle_id, contact_window_id)
);

CREATE TABLE run_input_existing_task (
    run_input_existing_task_id INTEGER PRIMARY KEY,
    run_input_bundle_id INTEGER NOT NULL,
    existing_task_id INTEGER NOT NULL,
    FOREIGN KEY (run_input_bundle_id) REFERENCES run_input_bundle(run_input_bundle_id),
    FOREIGN KEY (existing_task_id) REFERENCES existing_task(existing_task_id),
    UNIQUE (run_input_bundle_id, existing_task_id)
);

CREATE TABLE run_input_downlink_booking (
    run_input_downlink_booking_id INTEGER PRIMARY KEY,
    run_input_bundle_id INTEGER NOT NULL,
    existing_downlink_booking_id INTEGER NOT NULL,
    FOREIGN KEY (run_input_bundle_id) REFERENCES run_input_bundle(run_input_bundle_id),
    FOREIGN KEY (existing_downlink_booking_id) REFERENCES existing_downlink_booking(existing_downlink_booking_id),
    UNIQUE (run_input_bundle_id, existing_downlink_booking_id)
);

CREATE TABLE run_candidate (
    run_candidate_id INTEGER PRIMARY KEY,
    run_id INTEGER NOT NULL,
    access_opportunity_id INTEGER NOT NULL,
    selected_contact_window_id INTEGER,
    selected_ground_station_id INTEGER,
    candidate_rank INTEGER NOT NULL,
    candidate_status TEXT NOT NULL,
    planned_capture_start_at TEXT NOT NULL,
    planned_capture_end_at TEXT NOT NULL,
    expected_data_volume_gbit REAL NOT NULL,
    FOREIGN KEY (run_id) REFERENCES feasibility_run(run_id),
    FOREIGN KEY (access_opportunity_id) REFERENCES access_opportunity(access_opportunity_id),
    FOREIGN KEY (selected_contact_window_id) REFERENCES station_contact_window(contact_window_id),
    FOREIGN KEY (selected_ground_station_id) REFERENCES ground_station(ground_station_id)
);

CREATE TABLE candidate_rejection_reason (
    rejection_reason_id INTEGER PRIMARY KEY,
    run_candidate_id INTEGER NOT NULL,
    reason_code TEXT NOT NULL,
    reason_stage TEXT NOT NULL,
    reason_severity TEXT NOT NULL,
    reason_message TEXT NOT NULL,
    FOREIGN KEY (run_candidate_id) REFERENCES run_candidate(run_candidate_id)
);

CREATE TABLE candidate_resource_check (
    candidate_resource_check_id INTEGER PRIMARY KEY,
    run_candidate_id INTEGER NOT NULL UNIQUE,
    required_volume_gbit REAL NOT NULL,
    available_volume_gbit REAL NOT NULL,
    power_margin_pct REAL NOT NULL,
    thermal_margin_pct REAL NOT NULL,
    resource_feasible_flag INTEGER NOT NULL CHECK (resource_feasible_flag IN (0, 1)),
    FOREIGN KEY (run_candidate_id) REFERENCES run_candidate(run_candidate_id)
);

CREATE TABLE candidate_downlink_check (
    candidate_downlink_check_id INTEGER PRIMARY KEY,
    run_candidate_id INTEGER NOT NULL UNIQUE,
    contact_window_id INTEGER,
    required_downlink_gbit REAL NOT NULL,
    available_downlink_gbit REAL NOT NULL,
    backlog_after_capture_gbit REAL NOT NULL,
    downlink_feasible_flag INTEGER NOT NULL CHECK (downlink_feasible_flag IN (0, 1)),
    FOREIGN KEY (run_candidate_id) REFERENCES run_candidate(run_candidate_id),
    FOREIGN KEY (contact_window_id) REFERENCES station_contact_window(contact_window_id)
);

CREATE TABLE candidate_probability (
    candidate_probability_id INTEGER PRIMARY KEY,
    run_candidate_id INTEGER NOT NULL UNIQUE,
    p_geo REAL NOT NULL,
    p_env REAL NOT NULL,
    p_resource REAL NOT NULL,
    p_downlink REAL NOT NULL,
    p_conflict_adjusted REAL NOT NULL,
    p_total_candidate REAL NOT NULL,
    probability_model_version TEXT NOT NULL,
    FOREIGN KEY (run_candidate_id) REFERENCES run_candidate(run_candidate_id)
);

CREATE TABLE feasibility_result (
    result_id INTEGER PRIMARY KEY,
    run_id INTEGER NOT NULL UNIQUE,
    final_verdict TEXT NOT NULL,
    overall_probability REAL NOT NULL,
    first_feasible_attempt_at TEXT,
    candidate_count_total INTEGER NOT NULL,
    candidate_count_feasible INTEGER NOT NULL,
    dominant_risk_code TEXT,
    summary_message TEXT NOT NULL,
    FOREIGN KEY (run_id) REFERENCES feasibility_run(run_id)
);

CREATE TABLE feasibility_recommendation (
    recommendation_id INTEGER PRIMARY KEY,
    run_id INTEGER NOT NULL,
    recommendation_type TEXT NOT NULL,
    recommendation_rank INTEGER NOT NULL,
    parameter_name TEXT NOT NULL,
    current_value TEXT NOT NULL,
    recommended_value TEXT NOT NULL,
    expected_probability_gain REAL,
    expected_effect_message TEXT NOT NULL,
    FOREIGN KEY (run_id) REFERENCES feasibility_run(run_id)
);

CREATE TABLE audit_event (
    audit_event_id INTEGER PRIMARY KEY,
    run_id INTEGER NOT NULL,
    event_type TEXT NOT NULL,
    actor_type TEXT NOT NULL,
    actor_id TEXT NOT NULL,
    event_at TEXT NOT NULL,
    event_payload_json TEXT,
    FOREIGN KEY (run_id) REFERENCES feasibility_run(run_id)
);

CREATE INDEX idx_feasibility_request_org_created
    ON feasibility_request(customer_org_id, created_at);

CREATE INDEX idx_request_external_ref_request_id
    ON request_external_ref(request_id, is_primary);

CREATE INDEX idx_request_candidate_request_rank
    ON request_candidate(request_id, candidate_rank);

CREATE INDEX idx_request_candidate_run_candidate_simulated
    ON request_candidate_run(request_candidate_id, simulated_at DESC);

CREATE INDEX idx_satellite_pass_satellite_time
    ON satellite_pass(satellite_id, pass_start_at, pass_end_at);

CREATE INDEX idx_access_opportunity_aoi_time
    ON access_opportunity(request_aoi_id, access_start_at, access_end_at);

CREATE INDEX idx_weather_cell_forecast_snapshot_time
    ON weather_cell_forecast(weather_snapshot_id, forecast_at);

CREATE INDEX idx_resource_snapshot_satellite_time
    ON spacecraft_resource_snapshot(satellite_id, snapshot_at);

CREATE INDEX idx_station_contact_window_satellite_time
    ON station_contact_window(satellite_id, contact_start_at, contact_end_at);

CREATE INDEX idx_existing_task_satellite_time
    ON existing_task(satellite_id, task_start_at, task_end_at);

CREATE INDEX idx_feasibility_run_request_started
    ON feasibility_run(request_id, started_at);

CREATE INDEX idx_run_candidate_run_status_rank
    ON run_candidate(run_id, candidate_status, candidate_rank);

CREATE INDEX idx_candidate_rejection_reason_candidate_code
    ON candidate_rejection_reason(run_candidate_id, reason_code);

COMMIT;
