const state = {
  requestCatalog: [],
  requestPayloadCache: new Map(),
  activeRequestCode: null,
  activeCandidateCode: null,
  activeRequestPayload: null,
  candidateDraftMode: false,
  currentEvalTimer: null,
  currentEvalRequestSeq: 0,
  runHistoryMode: "all",
  formSyncLock: false,
};

function detachedElement(tagName = "div") {
  return document.createElement(tagName);
}

const storageKeys = {
  activeRequestCode: "feasibility.activeRequestCode",
  activeCandidateCode: "feasibility.activeCandidateCode",
};

const elements = {
  apiBase: document.getElementById("api-base"),
  healthStatus: document.getElementById("health-status"),
  requestCount: document.getElementById("request-count"),
  requestList: document.getElementById("request-list"),
  caseTitle: document.getElementById("case-title"),
  caseDescription: document.getElementById("case-description"),
  caseRequestCode: document.getElementById("case-request-code"),
  caseSensorType: document.getElementById("case-sensor-type"),
  summaryVerdict: document.getElementById("summary-verdict"),
  summaryMessage: document.getElementById("summary-message"),
  summaryProbability: document.getElementById("summary-probability"),
  summaryRisk: document.getElementById("summary-risk"),
  summaryCandidate: document.getElementById("summary-candidate"),
  summaryCandidateCaption: document.getElementById("summary-candidate-caption"),
  candidateEvaluationTitle: document.getElementById("candidate-evaluation-title"),
  proposalOverview: document.getElementById("proposal-overview"),
  requestOverview: document.getElementById("request-overview"),
  constraintOverview: document.getElementById("constraint-overview"),
  policyOverview: document.getElementById("policy-overview"),
  requestInfoPanel: document.getElementById("request-info-panel"),
  requestInfoPanelBody: document.getElementById("request-info-panel-body"),
  requestInfoToggle: document.getElementById("request-info-toggle"),
  externalRefList: document.getElementById("external-ref-list"),
  externalRefPanel: document.getElementById("external-ref-panel"),
  externalRefPanelBody: document.getElementById("external-ref-panel-body"),
  externalRefToggle: document.getElementById("external-ref-toggle"),
  externalRefForm: document.getElementById("external-ref-form"),
  externalRefSourceSystemCode: document.getElementById("external-ref-source-system-code"),
  externalRefCode: document.getElementById("external-ref-code"),
  externalRefTitle: document.getElementById("external-ref-title"),
  externalRefOrgName: document.getElementById("external-ref-org-name"),
  externalRefRequesterName: document.getElementById("external-ref-requester-name"),
  externalRefReceivedAt: document.getElementById("external-ref-received-at"),
  externalRefIsPrimary: document.getElementById("external-ref-is-primary"),
  externalRefStatus: document.getElementById("external-ref-status"),
  requestCreateForm: document.getElementById("request-create-form"),
  requestCreateTitle: document.getElementById("request-create-title"),
  requestCreateDescription: document.getElementById("request-create-description"),
  requestCreatePolicy: document.getElementById("request-create-policy"),
  requestCreatePriority: document.getElementById("request-create-priority"),
  requestCreateOrgName: document.getElementById("request-create-org-name"),
  requestCreateRequesterName: document.getElementById("request-create-requester-name"),
  requestCreateStartAt: document.getElementById("request-create-start-at"),
  requestCreateEndAt: document.getElementById("request-create-end-at"),
  requestCreateDeadlineAt: document.getElementById("request-create-deadline-at"),
  requestCreateMonitoringCount: document.getElementById("request-create-monitoring-count"),
  requestCreateAreaKm2: document.getElementById("request-create-area-km2"),
  requestCreateCentroidLon: document.getElementById("request-create-centroid-lon"),
  requestCreateCentroidLat: document.getElementById("request-create-centroid-lat"),
  requestCreateDominantAxisDeg: document.getElementById("request-create-dominant-axis-deg"),
  requestCreateExternalSource: document.getElementById("request-create-external-source"),
  requestCreateExternalCode: document.getElementById("request-create-external-code"),
  candidateTableBody: document.querySelector("#candidate-table tbody"),
  reasonList: document.getElementById("reason-list"),
  checkList: document.getElementById("check-list"),
  probabilityList: document.getElementById("probability-list"),
  recommendationList: document.getElementById("recommendation-list"),
  requestCandidateList: document.getElementById("request-candidate-list"),
  candidateCreateNew: document.getElementById("candidate-create-new"),
  candidateDelete: document.getElementById("candidate-delete"),
  simulateForm: document.getElementById("simulate-form"),
  reloadSelectedCandidate: document.getElementById("reload-selected-candidate"),
  saveCandidate: document.getElementById("save-candidate"),
  candidateCode: document.getElementById("candidate-code"),
  candidateTitle: document.getElementById("candidate-title"),
  candidateDescription: document.getElementById("candidate-description"),
  candidateStatus: document.getElementById("candidate-status"),
  candidateRank: document.getElementById("candidate-rank"),
  candidateIsBaseline: document.getElementById("candidate-is-baseline"),
  simSensorType: document.getElementById("sim-sensor-type"),
  currentVerdict: document.getElementById("current-verdict"),
  currentSummaryMessage: document.getElementById("current-summary-message"),
  currentProbability: document.getElementById("current-probability"),
  currentDominantRisk: document.getElementById("current-dominant-risk"),
  currentReasonList: document.getElementById("current-reason-list"),
  currentCheckList: document.getElementById("current-check-list"),
  simVerdict: document.getElementById("sim-verdict") || detachedElement("strong"),
  simSummaryMessage: document.getElementById("sim-summary-message") || detachedElement("p"),
  simProbability: document.getElementById("sim-probability") || detachedElement("strong"),
  simDominantRisk: document.getElementById("sim-dominant-risk") || detachedElement("p"),
  simulateReasonList: document.getElementById("simulate-reason-list") || detachedElement(),
  simulateCheckList: document.getElementById("simulate-check-list") || detachedElement(),
  simulateRecommendationList: document.getElementById("simulate-recommendation-list") || detachedElement(),
  runHistoryList: document.getElementById("run-history-list"),
  runHistoryAll: document.getElementById("run-history-all"),
  runHistoryActions: document.getElementById("run-history-actions"),
};

const formFields = [
  "sensor_type",
  "priority_tier",
  "area_km2",
  "window_hours",
  "opportunity_start_at",
  "opportunity_end_at",
  "cloud_pct",
  "max_cloud_pct",
  "required_off_nadir_deg",
  "max_off_nadir_deg",
  "predicted_incidence_deg",
  "min_incidence_deg",
  "max_incidence_deg",
  "sun_elevation_deg",
  "min_sun_elevation_deg",
  "coverage_ratio_predicted",
  "coverage_ratio_required",
  "expected_data_volume_gbit",
  "recorder_free_gbit",
  "recorder_backlog_gbit",
  "available_downlink_gbit",
  "power_margin_pct",
  "thermal_margin_pct",
];

function formatProbability(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return "-";
  }
  return `${(Number(value) * 100).toFixed(1)}%`;
}

function formatMaybe(value) {
  if (value === null || value === undefined || value === "") {
    return "-";
  }
  return String(value);
}

function parseLocalDateTimeValue(value) {
  if (!value) {
    return null;
  }
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? null : date;
}

function toUtcIsoString(value) {
  const date = value instanceof Date ? value : parseLocalDateTimeValue(value);
  if (!date) {
    return null;
  }
  return date.toISOString().replace(".000Z", "Z");
}

function toLocalDateTimeInputValue(value) {
  if (!value) {
    return "";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "";
  }
  const pad = (number) => String(number).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`;
}

function formatHoursForInput(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return "";
  }
  const rounded = Math.round(Number(value) * 100) / 100;
  return Number.isInteger(rounded) ? String(rounded) : rounded.toFixed(2).replace(/0+$/, "").replace(/\.$/, "");
}

function computeSquareBounds(areaKm2, centroidLon, centroidLat) {
  const sideKm = Math.sqrt(Math.max(Number(areaKm2) || 1, 1));
  const halfLatDeg = sideKm / 2 / 111.32;
  const cosLat = Math.cos((Number(centroidLat) || 0) * Math.PI / 180);
  const lonScale = Math.max(111.32 * Math.max(cosLat, 0.2), 1);
  const halfLonDeg = sideKm / 2 / lonScale;
  return {
    bbox_min_lon: Number((Number(centroidLon) - halfLonDeg).toFixed(6)),
    bbox_min_lat: Number((Number(centroidLat) - halfLatDeg).toFixed(6)),
    bbox_max_lon: Number((Number(centroidLon) + halfLonDeg).toFixed(6)),
    bbox_max_lat: Number((Number(centroidLat) + halfLatDeg).toFixed(6)),
  };
}

function buildSquareWkt(bounds) {
  return `POLYGON((${bounds.bbox_min_lon} ${bounds.bbox_min_lat},${bounds.bbox_max_lon} ${bounds.bbox_min_lat},${bounds.bbox_max_lon} ${bounds.bbox_max_lat},${bounds.bbox_min_lon} ${bounds.bbox_max_lat},${bounds.bbox_min_lon} ${bounds.bbox_min_lat}))`;
}

function buildRequestCreatePayload() {
  const policyId = Number(elements.requestCreatePolicy.value);
  const priorityTier = elements.requestCreatePriority.value;
  const sensorType = policyId === 2 ? "SAR" : "OPTICAL";
  const areaKm2 = Number(elements.requestCreateAreaKm2.value);
  const centroidLon = Number(elements.requestCreateCentroidLon.value);
  const centroidLat = Number(elements.requestCreateCentroidLat.value);
  const dominantAxisDeg = Number(elements.requestCreateDominantAxisDeg.value);
  const bounds = computeSquareBounds(areaKm2, centroidLon, centroidLat);
  const requestedStartAt = toUtcIsoString(elements.requestCreateStartAt.value);
  const requestedEndAt = toUtcIsoString(elements.requestCreateEndAt.value);
  const deadlineAt = toUtcIsoString(elements.requestCreateDeadlineAt.value);
  const requestedStartDate = requestedStartAt ? new Date(requestedStartAt) : null;
  const requestedEndDate = requestedEndAt ? new Date(requestedEndAt) : null;
  const deadlineDate = deadlineAt ? new Date(deadlineAt) : null;

  if (!elements.requestCreateTitle.value.trim()) {
    throw new Error("요청 제목은 필수입니다.");
  }
  if (!requestedStartAt || !requestedEndAt || !deadlineAt) {
    throw new Error("요청 시작, 종료, 마감시각은 필수입니다.");
  }
  if (
    !requestedStartDate || !requestedEndDate || !deadlineDate ||
    Number.isNaN(requestedStartDate.getTime()) || Number.isNaN(requestedEndDate.getTime()) || Number.isNaN(deadlineDate.getTime()) ||
    requestedEndDate <= requestedStartDate || deadlineDate < requestedStartDate
  ) {
    throw new Error("요청 시간 범위를 확인하세요.");
  }

  return {
    customer_org_id: 1,
    customer_user_id: 1,
    service_policy_id: policyId,
    request_title: elements.requestCreateTitle.value.trim(),
    request_description: elements.requestCreateDescription.value.trim() || `${elements.requestCreateTitle.value.trim()}에 대한 신규 feasibility 분석 요청입니다.`,
    request_status: "SUBMITTED",
    request_channel: "WEB_PORTAL",
    priority_tier: priorityTier,
    requested_start_at: requestedStartAt,
    requested_end_at: requestedEndAt,
    emergency_flag: priorityTier !== "STANDARD",
    repeat_acquisition_flag: Number(elements.requestCreateMonitoringCount.value) > 1,
    monitoring_count: Number(elements.requestCreateMonitoringCount.value) || 1,
    aoi: {
      geometry_type: "POLYGON",
      geometry_wkt: buildSquareWkt(bounds),
      srid: 4326,
      area_km2: areaKm2,
      ...bounds,
      centroid_lon: centroidLon,
      centroid_lat: centroidLat,
      dominant_axis_deg: Number.isFinite(dominantAxisDeg) ? dominantAxisDeg : null,
    },
    constraint: {
      max_cloud_pct: sensorType === "OPTICAL" ? 20 : null,
      max_off_nadir_deg: sensorType === "OPTICAL" ? 25 : null,
      min_incidence_deg: sensorType === "SAR" ? 25 : null,
      max_incidence_deg: sensorType === "SAR" ? 40 : null,
      preferred_local_time_start: sensorType === "OPTICAL" ? "10:00" : null,
      preferred_local_time_end: sensorType === "OPTICAL" ? "14:00" : null,
      min_sun_elevation_deg: sensorType === "OPTICAL" ? 30 : null,
      max_haze_index: sensorType === "OPTICAL" ? 0.4 : null,
      deadline_at: deadlineAt,
      coverage_ratio_required: sensorType === "OPTICAL" ? 0.95 : 0.9,
    },
    sensor_options: [
      sensorType === "SAR"
        ? {
            satellite_id: 2,
            sensor_id: 2,
            sensor_mode_id: 2,
            preference_rank: 1,
            is_mandatory: true,
            polarization_code: "HH",
          }
        : {
            satellite_id: 1,
            sensor_id: 1,
            sensor_mode_id: 1,
            preference_rank: 1,
            is_mandatory: true,
            polarization_code: null,
          },
    ],
    product_options: [
      sensorType === "SAR"
        ? {
            product_level_code: "L1C",
            product_type_code: "SIGMA0",
            file_format_code: "HDF5",
            delivery_mode_code: "FTP",
            ancillary_required_flag: true,
          }
        : {
            product_level_code: "L1R",
            product_type_code: "ORTHO_READY",
            file_format_code: "GEOTIFF",
            delivery_mode_code: "FTP",
            ancillary_required_flag: true,
          },
    ],
    external_ref: elements.requestCreateExternalCode.value.trim()
      ? {
          source_system_code: elements.requestCreateExternalSource.value.trim() || "CUSTOMER_PORTAL",
          external_request_code: elements.requestCreateExternalCode.value.trim(),
          external_request_title: elements.requestCreateTitle.value.trim(),
          external_customer_org_name: elements.requestCreateOrgName.value.trim() || null,
          external_requester_name: elements.requestCreateRequesterName.value.trim() || null,
          is_primary: true,
          received_at: requestedStartAt,
        }
      : null,
  };
}

function applyRequestCreateDefaultsFromPayload(payload) {
  if (!payload?.request || !payload?.aoi || !payload?.constraint) {
    return;
  }
  elements.requestCreatePolicy.value = String(payload.request.service_policy_id || (payload.request.policy_name?.includes("SAR") ? 2 : 1));
  elements.requestCreatePriority.value = payload.request.priority_tier || "STANDARD";
  elements.requestCreateOrgName.value = payload.request.org_name || "";
  elements.requestCreateRequesterName.value = payload.request.user_name || "";
  elements.requestCreateStartAt.value = toLocalDateTimeInputValue(payload.request.requested_start_at);
  elements.requestCreateEndAt.value = toLocalDateTimeInputValue(payload.request.requested_end_at);
  elements.requestCreateDeadlineAt.value = toLocalDateTimeInputValue(payload.constraint.deadline_at || payload.request.requested_end_at);
  elements.requestCreateAreaKm2.value = String(payload.aoi.area_km2 || "");
  elements.requestCreateCentroidLon.value = String(payload.aoi.centroid_lon || "");
  elements.requestCreateCentroidLat.value = String(payload.aoi.centroid_lat || "");
  elements.requestCreateDominantAxisDeg.value = payload.aoi.dominant_axis_deg === null || payload.aoi.dominant_axis_deg === undefined
    ? ""
    : String(payload.aoi.dominant_axis_deg);
  elements.requestCreateExternalSource.value = payload.request.external_source_system_code || "CUSTOMER_PORTAL";
}

function syncOpportunityFields(source) {
  if (state.formSyncLock) {
    return;
  }
  const startInput = document.getElementById("sim-opportunity-start-at");
  const endInput = document.getElementById("sim-opportunity-end-at");
  const windowInput = document.getElementById("sim-window-hours");
  const startDate = parseLocalDateTimeValue(startInput?.value);
  const endDate = parseLocalDateTimeValue(endInput?.value);
  const windowHours = Number(windowInput?.value);

  state.formSyncLock = true;
  try {
    startInput?.setCustomValidity("");
    endInput?.setCustomValidity("");
    if (source === "start" || source === "end") {
      if (startDate && endDate) {
        if (endDate > startDate) {
          const derivedWindowHours = (endDate.getTime() - startDate.getTime()) / (1000 * 60 * 60);
          windowInput.value = formatHoursForInput(derivedWindowHours);
        } else {
          windowInput.value = "";
          endInput?.setCustomValidity("촬영기회 종료시각은 시작시각보다 뒤여야 합니다.");
          endInput?.reportValidity();
        }
      }
      return;
    }

    if (source === "window" && startDate && Number.isFinite(windowHours) && windowHours > 0) {
      const derivedEnd = new Date(startDate.getTime() + windowHours * 60 * 60 * 1000);
      endInput.value = toLocalDateTimeInputValue(derivedEnd);
      return;
    }
  } finally {
    state.formSyncLock = false;
  }
}

function localizeStatus(status) {
  const mapping = {
    FEASIBLE: "가능",
    CONDITIONAL: "조건부",
    REJECTED: "불가",
    READY: "준비",
    DRAFT: "초안",
    ARCHIVED: "보관",
  };
  return mapping[String(status || "").toUpperCase()] ?? formatMaybe(status);
}

function localizeVerdict(verdict) {
  const mapping = {
    FEASIBLE: "가능",
    CONDITIONALLY_FEASIBLE: "조건부 가능",
    NOT_FEASIBLE: "불가",
  };
  return mapping[String(verdict || "").toUpperCase()] ?? formatMaybe(verdict);
}

function localizeSensorType(sensorType) {
  const mapping = {
    OPTICAL: "광학",
    SAR: "SAR",
  };
  return mapping[String(sensorType || "").toUpperCase()] ?? formatMaybe(sensorType);
}

function localizeTriggerType(triggerType) {
  const mapping = {
    MANUAL_SAVE_AND_RUN: "수동 저장 후 실행",
    RECOMMENDATION_APPLY: "추천안 반영 실행",
    RECOMMENDATION_SPLIT: "분리 후보 생성 실행",
  };
  return mapping[String(triggerType || "").toUpperCase()] ?? formatMaybe(triggerType);
}

function isRecommendationTriggeredRun(run) {
  const triggerType = String(run?.run_trigger_type || "").toUpperCase();
  return triggerType === "RECOMMENDATION_APPLY" || triggerType === "RECOMMENDATION_SPLIT";
}

function syncRunHistoryFilterButtons() {
  elements.runHistoryAll.classList.toggle("is-active", state.runHistoryMode === "all");
  elements.runHistoryActions.classList.toggle("is-active", state.runHistoryMode === "actions");
}

function syncExternalRefPanel() {
  const expanded = !elements.externalRefPanel.classList.contains("is-collapsed");
  elements.externalRefPanelBody.hidden = !expanded;
  elements.externalRefToggle.setAttribute("aria-expanded", expanded ? "true" : "false");
  elements.externalRefToggle.textContent = expanded ? "−" : "+";
}

function syncRequestInfoPanel() {
  const expanded = !elements.requestInfoPanel.classList.contains("is-collapsed");
  elements.requestInfoPanelBody.hidden = !expanded;
  elements.requestInfoToggle.setAttribute("aria-expanded", expanded ? "true" : "false");
  elements.requestInfoToggle.textContent = expanded ? "−" : "+";
}

function statusClass(status) {
  const normalized = String(status || "").toLowerCase();
  if (normalized === "feasible" || normalized === "ready") return "status-feasible";
  if (normalized === "conditional" || normalized === "draft") return "status-conditional";
  return "status-rejected";
}

function renderDefinitionGrid(target, entries) {
  target.innerHTML = "";
  for (const [label, value] of entries) {
    const dt = document.createElement("dt");
    dt.textContent = label;
    const dd = document.createElement("dd");
    dd.textContent = formatMaybe(value);
    target.append(dt, dd);
  }
}

function renderExternalRefs(payload) {
  elements.externalRefList.innerHTML = "";
  const refs = payload.external_refs || [];
  if (!refs.length) {
    elements.externalRefList.appendChild(
      createStackCard("외부 요청번호 없음", "아직 연결된 외부 요청번호가 없습니다."),
    );
  } else {
    for (const ref of refs) {
      const actions = [];
      if (!ref.is_primary) {
        actions.push({
          label: "기본 지정",
          className: "action-secondary",
          onClick: async () => {
            try {
              await setPrimaryExternalRef(ref.request_external_ref_id);
              elements.currentSummaryMessage.textContent = "기본 외부 요청번호가 변경되었습니다.";
            } catch (error) {
              elements.currentSummaryMessage.textContent = String(error);
            }
          },
        });
      }
      actions.push({
        label: "삭제",
        className: "action-secondary",
        onClick: async () => {
          try {
            await deleteExternalRef(ref.request_external_ref_id);
            elements.currentSummaryMessage.textContent = "외부 요청번호 매핑이 삭제되었습니다.";
          } catch (error) {
            elements.currentSummaryMessage.textContent = String(error);
          }
        },
      });
      elements.externalRefList.appendChild(
        createActionStackCard(
          `${ref.external_request_code}`,
          [
            ref.external_request_title || null,
            ref.external_customer_org_name || null,
            ref.external_requester_name || null,
          ].filter(Boolean).join(" | ") || "부가 설명 없음",
          [
            ref.source_system_code,
            ref.is_primary ? "primary" : null,
            ref.received_at || null,
          ].filter(Boolean),
          actions,
        ),
      );
    }
  }

  elements.externalRefSourceSystemCode.value = refs[0]?.source_system_code || "CUSTOMER_PORTAL";
  elements.externalRefCode.value = "";
  elements.externalRefTitle.value = "";
  elements.externalRefOrgName.value = payload.request.external_customer_org_name || payload.request.org_name || "";
  elements.externalRefRequesterName.value = payload.request.external_requester_name || payload.request.user_name || "";
  elements.externalRefReceivedAt.value = "";
  elements.externalRefIsPrimary.checked = true;
}

function renderSummaryTable(target, entries) {
  target.innerHTML = "";
  for (const [label, value] of entries) {
    const row = document.createElement("tr");
    const th = document.createElement("th");
    th.scope = "row";
    if (typeof label === "object" && label !== null) {
      const wrapper = document.createElement("div");
      wrapper.className = "table-label-with-tooltip";
      const text = document.createElement("span");
      text.textContent = String(label.text ?? "");
      wrapper.appendChild(text);
      if (label.tooltip) {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "info-tooltip hardcoded-copy";
        button.setAttribute("aria-label", `${label.text} 안내`);
        button.setAttribute("data-tooltip", String(label.tooltip));
        button.textContent = "?";
        wrapper.appendChild(button);
      }
      th.appendChild(wrapper);
    } else {
      th.textContent = String(label);
    }
    const td = document.createElement("td");
    td.textContent = formatMaybe(value);
    row.append(th, td);
    target.appendChild(row);
  }
}

function summaryLabel(text, tooltip) {
  return { text, tooltip };
}

function createStackCard(title, body, meta = []) {
  const card = document.createElement("article");
  card.className = "stack-card";
  const heading = document.createElement("h3");
  heading.textContent = title;
  const paragraph = document.createElement("p");
  paragraph.textContent = body;
  card.append(heading, paragraph);
  if (meta.length) {
    const metaRow = document.createElement("div");
    metaRow.className = "stack-meta";
    for (const item of meta) {
      const span = document.createElement("span");
      span.className = "meta-pill";
      span.textContent = item;
      metaRow.appendChild(span);
    }
    card.appendChild(metaRow);
  }
  return card;
}

function createActionStackCard(title, body, meta = [], actions = []) {
  const card = createStackCard(title, body, meta);
  const normalizedActions = Array.isArray(actions) ? actions : (actions ? [actions] : []);
  if (normalizedActions.length) {
    const actionRow = document.createElement("div");
    actionRow.className = "action-row";
    for (const action of normalizedActions) {
      const button = document.createElement("button");
      button.type = "button";
      button.className = `action-button ${action.className || "action-secondary"}`;
      button.textContent = action.label;
      button.addEventListener("click", action.onClick);
      actionRow.appendChild(button);
    }
    card.appendChild(actionRow);
  }
  return card;
}

function renderEvaluationBlock(config, evaluation, reasons = [], recommendations = [], options = {}) {
  const {
    verdict,
    summaryMessage,
    probability,
    dominantRisk,
    candidateStatus,
    checkCaption,
    reasonList,
    checkList,
    recommendationList,
  } = config;

  if (!evaluation) {
    verdict.textContent = options.emptyVerdict ?? "-";
    summaryMessage.textContent = options.emptySummary ?? "-";
    probability.textContent = "-";
    dominantRisk.textContent = "주요 위험 없음";
    if (candidateStatus) candidateStatus.textContent = options.emptyStatus ?? "-";
    if (checkCaption) checkCaption.textContent = options.emptyCheckCaption ?? "-";
    reasonList.innerHTML = "";
    checkList.innerHTML = "";
    recommendationList.innerHTML = "";
    reasonList.appendChild(createStackCard(options.emptyReasonTitle ?? "실행 이력 없음", options.emptyReasonBody ?? "평가 데이터가 없습니다."));
    checkList.appendChild(createStackCard(options.emptyCheckTitle ?? "점검 결과 없음", options.emptyCheckBody ?? "아직 계산된 확률 및 마진 정보가 없습니다."));
    recommendationList.appendChild(createStackCard(options.emptyRecommendationTitle ?? "권고 사항 없음", options.emptyRecommendationBody ?? "현재 표시할 권고가 없습니다."));
    return;
  }

  verdict.textContent = localizeVerdict(evaluation.final_verdict);
  summaryMessage.textContent = evaluation.summary_message;
  probability.textContent = formatProbability(evaluation.probabilities?.p_total_candidate ?? evaluation.p_total_candidate);
  dominantRisk.textContent = evaluation.dominant_risk_code
    ? `주요 위험: ${evaluation.dominant_risk_code}`
    : "주요 위험 없음";
  if (candidateStatus) {
    candidateStatus.textContent = localizeStatus(evaluation.candidate_status);
  }

  const resourceFlag = evaluation.checks?.resource_feasible_flag ?? evaluation.resource_feasible_flag;
  const downlinkFlag = evaluation.checks?.downlink_feasible_flag ?? evaluation.downlink_feasible_flag;
  const policyFlag = evaluation.checks?.policy_feasible_flag ?? evaluation.policy_feasible_flag;
  const policyText = policyFlag === undefined ? null : `정책 ${policyFlag ? "정상" : "실패"}`;
  if (checkCaption) {
    checkCaption.textContent = [policyText, `자원 ${resourceFlag ? "정상" : "실패"}`, `다운링크 ${downlinkFlag ? "정상" : "실패"}`]
      .filter(Boolean)
      .join(" | ");
  }

  reasonList.innerHTML = "";
  if (!reasons.length) {
    reasonList.appendChild(
      createStackCard(options.noReasonTitle ?? "차단 사유 없음", options.noReasonBody ?? "별도 차단 사유가 기록되지 않았습니다."),
    );
  } else {
    for (const reason of reasons) {
      reasonList.appendChild(
        createStackCard(reason.reason_code, reason.reason_message, [reason.reason_stage, reason.reason_severity]),
      );
    }
  }

  const pGeo = evaluation.probabilities?.p_geo ?? evaluation.p_geo;
  const pEnv = evaluation.probabilities?.p_env ?? evaluation.p_env;
  const pResource = evaluation.probabilities?.p_resource ?? evaluation.p_resource;
  const pDownlink = evaluation.probabilities?.p_downlink ?? evaluation.p_downlink;
  const pPolicy = evaluation.probabilities?.p_policy ?? evaluation.p_policy;
  const pConflict = evaluation.probabilities?.p_conflict_adjusted ?? evaluation.p_conflict_adjusted;
  const storageHeadroom = evaluation.checks?.storage_headroom_gbit ?? evaluation.storage_headroom_gbit;
  const backlogAfterCapture = evaluation.checks?.backlog_after_capture_gbit ?? evaluation.backlog_after_capture_gbit;
  const downlinkMargin = evaluation.checks?.downlink_margin_gbit ?? evaluation.downlink_margin_gbit;
  const policySummary = evaluation.checks?.policy_summary ?? evaluation.policy_summary;
  const policyAlertCount = evaluation.checks?.policy_alert_count ?? evaluation.policy_alert_count;
  const geometrySource = evaluation.checks?.geometry_source ?? evaluation.geometry_source;
  const accessOpportunityId = evaluation.checks?.access_opportunity_id ?? evaluation.access_opportunity_id;
  const accessStartAt = evaluation.checks?.access_start_at ?? evaluation.access_start_at;
  const accessEndAt = evaluation.checks?.access_end_at ?? evaluation.access_end_at;
  const geometricFeasibleFlag = evaluation.checks?.geometric_feasible_flag ?? evaluation.geometric_feasible_flag;
  const selectedGroundStationCode = evaluation.checks?.selected_ground_station_code ?? evaluation.selected_ground_station_code;
  const contactStartAt = evaluation.checks?.contact_start_at ?? evaluation.contact_start_at;
  const contactEndAt = evaluation.checks?.contact_end_at ?? evaluation.contact_end_at;
  const contactCapacityGbit = evaluation.checks?.contact_capacity_gbit ?? evaluation.contact_capacity_gbit;
  const bookingReservedGbit = evaluation.checks?.booking_reserved_gbit ?? evaluation.booking_reserved_gbit;
  const netContactCapacityGbit = evaluation.checks?.net_contact_capacity_gbit ?? evaluation.net_contact_capacity_gbit;
  const taskConflictCount = evaluation.checks?.task_conflict_count ?? evaluation.task_conflict_count;
  const bookingConflictCount = evaluation.checks?.booking_conflict_count ?? evaluation.booking_conflict_count;
  const forecastCloudPct = evaluation.checks?.forecast_cloud_pct ?? evaluation.forecast_cloud_pct;
  const forecastHazeIndex = evaluation.checks?.forecast_haze_index ?? evaluation.forecast_haze_index;
  const forecastConfidenceScore = evaluation.checks?.forecast_confidence_score ?? evaluation.forecast_confidence_score;
  const forecastSunElevationDeg = evaluation.checks?.forecast_sun_elevation_deg ?? evaluation.forecast_sun_elevation_deg;
  const forecastSunAzimuthDeg = evaluation.checks?.forecast_sun_azimuth_deg ?? evaluation.forecast_sun_azimuth_deg;
  const shadowRiskScore = evaluation.checks?.shadow_risk_score ?? evaluation.shadow_risk_score;
  const localCaptureTime = evaluation.checks?.local_capture_time_hhmm ?? evaluation.local_capture_time_hhmm;
  const preferredLocalStart = evaluation.checks?.preferred_local_time_start ?? evaluation.preferred_local_time_start;
  const preferredLocalEnd = evaluation.checks?.preferred_local_time_end ?? evaluation.preferred_local_time_end;
  const localTimeWindowDistanceMin = evaluation.checks?.local_time_window_distance_min ?? evaluation.local_time_window_distance_min;
  const daylightFlag = evaluation.checks?.daylight_flag ?? evaluation.daylight_flag;
  const terrainRiskType = evaluation.checks?.terrain_risk_type ?? evaluation.terrain_risk_type;
  const terrainRiskScore = evaluation.checks?.terrain_risk_score ?? evaluation.terrain_risk_score;

  checkList.innerHTML = "";
  checkList.appendChild(
    createStackCard(
      "확률 항목",
      [
        `P(geo) ${formatProbability(pGeo)}`,
        `P(env) ${formatProbability(pEnv)}`,
        `P(resource) ${formatProbability(pResource)}`,
        `P(downlink) ${formatProbability(pDownlink)}`,
        pPolicy !== undefined ? `P(policy) ${formatProbability(pPolicy)}` : null,
        `P(conflict-adjusted) ${formatProbability(pConflict)}`,
      ].filter(Boolean).join(" | "),
    ),
  );
  if (policySummary || policyAlertCount !== undefined) {
    checkList.appendChild(
      createStackCard(
        "정책 검증",
        [
          policySummary || "정책 요약 없음",
          policyAlertCount !== undefined ? `정책 항목 ${policyAlertCount}건` : null,
        ].filter(Boolean).join(" | "),
      ),
    );
  }
  if (geometrySource || accessOpportunityId) {
    checkList.appendChild(
      createStackCard(
        "기하 후보",
        [
          geometrySource ? `기준 ${geometrySource}` : null,
          accessOpportunityId !== undefined ? `access #${accessOpportunityId}` : null,
          accessStartAt && accessEndAt ? `${accessStartAt} ~ ${accessEndAt}` : null,
          geometricFeasibleFlag !== undefined ? `사전 기하 ${geometricFeasibleFlag ? "통과" : "탈락"}` : null,
        ].filter(Boolean).join(" | "),
      ),
    );
  }
  if (selectedGroundStationCode || taskConflictCount !== undefined || bookingConflictCount !== undefined) {
    checkList.appendChild(
      createStackCard(
        "운영 충돌 및 다운링크 창",
        [
          selectedGroundStationCode ? `지상국 ${selectedGroundStationCode}` : null,
          contactStartAt && contactEndAt ? `${contactStartAt} ~ ${contactEndAt}` : null,
          contactCapacityGbit !== undefined ? `contact 용량 ${contactCapacityGbit} Gbit` : null,
          bookingReservedGbit !== undefined ? `예약 ${bookingReservedGbit} Gbit` : null,
          netContactCapacityGbit !== undefined ? `순가용 ${netContactCapacityGbit} Gbit` : null,
          taskConflictCount !== undefined ? `task 충돌 ${taskConflictCount}건` : null,
          bookingConflictCount !== undefined ? `booking 충돌 ${bookingConflictCount}건` : null,
        ].filter(Boolean).join(" | "),
      ),
    );
  }
  if (
    forecastCloudPct !== undefined || forecastHazeIndex !== undefined || forecastSunElevationDeg !== undefined ||
    terrainRiskType !== undefined || terrainRiskScore !== undefined
  ) {
    checkList.appendChild(
      createStackCard(
        "환경 스냅샷",
        [
          forecastCloudPct !== undefined ? `예보 구름 ${forecastCloudPct}%` : null,
          forecastHazeIndex !== undefined ? `haze ${forecastHazeIndex}` : null,
          forecastConfidenceScore !== undefined ? `예보 신뢰도 ${forecastConfidenceScore}` : null,
          forecastSunElevationDeg !== undefined ? `태양고도 ${forecastSunElevationDeg}` : null,
          forecastSunAzimuthDeg !== undefined ? `태양방위각 ${forecastSunAzimuthDeg}` : null,
          shadowRiskScore !== undefined ? `그림자위험 ${shadowRiskScore}` : null,
          localCaptureTime ? `현지시각 ${localCaptureTime}` : null,
          preferredLocalStart && preferredLocalEnd ? `선호창 ${preferredLocalStart}~${preferredLocalEnd}` : null,
          localTimeWindowDistanceMin !== undefined ? `선호창 편차 ${localTimeWindowDistanceMin}분` : null,
          daylightFlag !== undefined ? `주간 ${daylightFlag ? "예" : "아니오"}` : null,
          terrainRiskType !== undefined ? `지형위험 ${terrainRiskType}` : null,
          terrainRiskScore !== undefined ? `위험도 ${terrainRiskScore}` : null,
        ].filter(Boolean).join(" | "),
      ),
    );
  }
  checkList.appendChild(
    createStackCard(
      "마진 점검",
      [
        `저장 여유 ${storageHeadroom} Gbit`,
        `촬영 후 백로그 ${backlogAfterCapture} Gbit`,
        `다운링크 마진 ${downlinkMargin} Gbit`,
      ].join(" | "),
    ),
  );

  recommendationList.innerHTML = "";
  if (!recommendations.length) {
    recommendationList.appendChild(
      createStackCard(options.noRecommendationTitle ?? "권고 사항 없음", options.noRecommendationBody ?? "추가 권고가 없습니다."),
    );
  } else {
    for (const recommendation of recommendations) {
      recommendationList.appendChild(
        createStackCard(
          recommendation.parameter_name,
          recommendation.expected_effect_message,
          [
            `current ${recommendation.current_value}`,
            `recommended ${recommendation.recommended_value}`,
            recommendation.expected_probability_gain !== undefined && recommendation.expected_probability_gain !== null
              ? `gain ${formatProbability(recommendation.expected_probability_gain)}`
              : null,
          ].filter(Boolean),
        ),
      );
    }
  }
}

function persistSelection() {
  if (state.activeRequestCode) {
    window.localStorage.setItem(storageKeys.activeRequestCode, state.activeRequestCode);
  } else {
    window.localStorage.removeItem(storageKeys.activeRequestCode);
  }

  if (!state.candidateDraftMode && state.activeCandidateCode) {
    window.localStorage.setItem(storageKeys.activeCandidateCode, state.activeCandidateCode);
  } else {
    window.localStorage.removeItem(storageKeys.activeCandidateCode);
  }
}

function loadPersistedSelection() {
  return {
    activeRequestCode: window.localStorage.getItem(storageKeys.activeRequestCode),
    activeCandidateCode: window.localStorage.getItem(storageKeys.activeCandidateCode),
  };
}

function scrollActiveEntityIntoView(container) {
  const activeButton = container.querySelector(".entity-button.active");
  if (activeButton) {
    activeButton.scrollIntoView({ block: "nearest" });
  }
}

function setCandidateCodeReadOnly(readOnly) {
  elements.candidateCode.readOnly = true;
  elements.candidateCode.disabled = false;
}

function updateSensorFieldVisibility(sensorType) {
  for (const field of document.querySelectorAll(".sensor-optical")) {
    field.classList.toggle("is-hidden", sensorType !== "OPTICAL");
  }
  for (const field of document.querySelectorAll(".sensor-sar")) {
    field.classList.toggle("is-hidden", sensorType !== "SAR");
  }
}

function readSimulationFormInput() {
  const formData = new FormData(elements.simulateForm);
  const payload = {};
  for (const fieldName of formFields) {
    const value = formData.get(fieldName);
    if (fieldName === "sensor_type" || fieldName === "priority_tier") {
      payload[fieldName] = value;
    } else if (fieldName === "opportunity_start_at" || fieldName === "opportunity_end_at") {
      payload[fieldName] = toUtcIsoString(String(value || "").trim()) || null;
    } else {
      payload[fieldName] = Number(value);
    }
  }
  return payload;
}

function readCandidateForm() {
  return {
    candidate_title: elements.candidateTitle.value.trim(),
    candidate_description: elements.candidateDescription.value.trim(),
    candidate_status: elements.candidateStatus.value,
    candidate_rank: Number(elements.candidateRank.value),
    is_baseline: elements.candidateIsBaseline.checked,
    input: readSimulationFormInput(),
  };
}

async function readErrorDetail(response) {
  const contentType = response.headers.get("content-type") || "";
  if (contentType.includes("application/json")) {
    const payload = await response.json().catch(() => null);
    if (payload && typeof payload.detail === "string") {
      return payload.detail;
    }
    return JSON.stringify(payload);
  }
  return response.text();
}

function setFormValuesFromCandidate(report) {
  elements.candidateCode.value = report.candidate.candidate_code;
  elements.candidateCode.placeholder = "시스템 자동 생성";
  elements.candidateTitle.value = report.candidate.candidate_title;
  elements.candidateDescription.value = report.candidate.candidate_description;
  elements.candidateStatus.value = report.candidate.candidate_status;
  elements.candidateRank.value = String(report.candidate.candidate_rank);
  elements.candidateIsBaseline.checked = Boolean(report.candidate.is_baseline);
  const currentEvaluation = report.current_evaluation || {};
  const evaluationChecks = currentEvaluation.checks || {};
  const opportunityFallback = {
    opportunity_start_at:
      report.input?.opportunity_start_at
      ?? evaluationChecks.access_start_at
      ?? currentEvaluation.access_start_at
      ?? null,
    opportunity_end_at:
      report.input?.opportunity_end_at
      ?? evaluationChecks.access_end_at
      ?? currentEvaluation.access_end_at
      ?? null,
  };
  for (const fieldName of formFields) {
    const element = document.getElementById(`sim-${fieldName.replaceAll("_", "-")}`);
    if (!element) {
      continue;
    }
    const value = fieldName === "opportunity_start_at" || fieldName === "opportunity_end_at"
      ? opportunityFallback[fieldName]
      : report.input?.[fieldName];
    if (fieldName === "opportunity_start_at" || fieldName === "opportunity_end_at") {
      element.value = toLocalDateTimeInputValue(value);
    } else {
      element.value = value === null || value === undefined ? "" : String(value);
    }
  }
  updateSensorFieldVisibility(report.input?.sensor_type ?? "OPTICAL");
  setCandidateCodeReadOnly(true);
}

function buildDefaultCandidateDraft(requestPayload) {
  const requestCandidates = requestPayload.request_candidates || [];
  const sensorType = requestPayload.sensor_options?.[0]?.sensor_type ?? "OPTICAL";
  const requestedStart = new Date(requestPayload.request.requested_start_at);
  const defaultDeadline = requestPayload.constraint?.deadline_at || requestPayload.request.requested_end_at;
  const requestedEnd = new Date(defaultDeadline);
  const windowHours = Math.max(1, Math.round((requestedEnd - requestedStart) / (1000 * 60 * 60)));
  const defaultOpportunityStart = toLocalDateTimeInputValue(requestPayload.request.requested_start_at);
  const defaultOpportunityEnd = toLocalDateTimeInputValue(defaultDeadline);
  const nextRank = requestCandidates.length + 1;
  const draft = {
    candidate_title: `${localizeSensorType(sensorType)} 비교안 ${nextRank}`,
    candidate_description: "입력값을 조정해 가능성을 비교 검토하기 위한 임시 후보입니다.",
    candidate_status: "DRAFT",
    candidate_rank: nextRank,
    is_baseline: false,
    input: {
      sensor_type: sensorType,
      priority_tier: requestPayload.request.priority_tier,
      area_km2: Number(requestPayload.aoi?.area_km2 ?? 100),
      window_hours: windowHours,
      opportunity_start_at: defaultOpportunityStart,
      opportunity_end_at: defaultOpportunityEnd,
      cloud_pct: Number(requestPayload.constraint?.max_cloud_pct ?? 0),
      max_cloud_pct: Number(requestPayload.constraint?.max_cloud_pct ?? 20),
      required_off_nadir_deg: Number(requestPayload.constraint?.max_off_nadir_deg ?? 0),
      max_off_nadir_deg: Number(requestPayload.constraint?.max_off_nadir_deg ?? 25),
      predicted_incidence_deg: Number(requestPayload.constraint?.min_incidence_deg ?? 30),
      min_incidence_deg: Number(requestPayload.constraint?.min_incidence_deg ?? 25),
      max_incidence_deg: Number(requestPayload.constraint?.max_incidence_deg ?? 40),
      sun_elevation_deg: Number(requestPayload.constraint?.min_sun_elevation_deg ?? 20),
      min_sun_elevation_deg: Number(requestPayload.constraint?.min_sun_elevation_deg ?? 20),
      coverage_ratio_predicted: Number(requestPayload.constraint?.coverage_ratio_required ?? 0.95),
      coverage_ratio_required: Number(requestPayload.constraint?.coverage_ratio_required ?? 0.95),
      expected_data_volume_gbit: sensorType === "SAR" ? 22 : 14,
      recorder_free_gbit: sensorType === "SAR" ? 44 : 48,
      recorder_backlog_gbit: sensorType === "SAR" ? 8 : 12,
      available_downlink_gbit: sensorType === "SAR" ? 36 : 42,
      power_margin_pct: 18,
      thermal_margin_pct: 16,
    },
  };
  return draft;
}

function nextCandidateRank(requestPayload) {
  const ranks = (requestPayload.request_candidates || []).map((item) => Number(item.candidate_rank) || 0);
  return (ranks.length ? Math.max(...ranks) : 0) + 1;
}

function applyRecommendationToDraftInput(input, recommendation) {
  if (!recommendation) {
    return input;
  }
  const next = { ...input };
  if (recommendation.parameter_name === "incidence_window") {
    const [minText, maxText] = String(recommendation.recommended_value || "").split("-", 2);
    const minValue = Number(minText);
    const maxValue = Number(maxText);
    if (!Number.isNaN(minValue) && !Number.isNaN(maxValue)) {
      next.min_incidence_deg = minValue;
      next.max_incidence_deg = maxValue;
      next.predicted_incidence_deg = Number(((minValue + maxValue) / 2).toFixed(1));
    }
  }
  return next;
}

function buildSplitCandidatePresentation(sourceReport, pairedIncidenceWindow) {
  const sourceTitle = sourceReport.candidate.candidate_title;
  if (pairedIncidenceWindow && pairedIncidenceWindow.recommended_value) {
    return {
      title: `${sourceTitle} - 입사각 분리 후보`,
      description: `${sourceReport.candidate.candidate_description} | ${pairedIncidenceWindow.recommended_value} 범위로 입사각 조건을 분리한 반복 촬영 완화 후보입니다.`,
    };
  }
  return {
    title: `${sourceTitle} - 분리 후보`,
    description: `${sourceReport.candidate.candidate_description} | 반복 촬영 완화안을 별도 후보로 분리한 비교 후보입니다.`,
  };
}

async function createSplitCandidateFromRecommendation(recommendation) {
  if (!state.activeRequestCode || !state.activeRequestPayload) {
    throw new Error("먼저 요청건을 불러오세요.");
  }
  const sourceCode = recommendation.recommendation_type;
  const sourceReport = await fetchRequestCandidateReport(state.activeRequestCode, sourceCode);
  const pairedIncidenceWindow = (state.activeRequestPayload.proposal?.relaxation_options || []).find(
    (item) => item.recommendation_type === sourceCode && item.parameter_name === "incidence_window",
  );
  const nextRank = nextCandidateRank(state.activeRequestPayload);
  const presentation = buildSplitCandidatePresentation(sourceReport, pairedIncidenceWindow);
  const payload = {
    candidate_title: presentation.title,
    candidate_description: presentation.description,
    candidate_status: "DRAFT",
    candidate_rank: nextRank,
    is_baseline: false,
    input: applyRecommendationToDraftInput({ ...sourceReport.input }, pairedIncidenceWindow),
  };
  const response = await fetch(`/requests/${state.activeRequestCode}/request-candidates`, {
    method: "POST",
    headers: {
      "content-type": "application/json",
    },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(`분리 후보 생성 실패 (${response.status}). ${detail}`);
  }
  const created = await response.json();
  state.requestPayloadCache.delete(state.activeRequestCode);
  const refreshedPayload = await fetchRequestPayload(state.activeRequestCode, true);
  renderRequestScenario(refreshedPayload);
  await loadRequestCandidate(created.candidate.candidate_code);
  await simulateSelectedCandidate(created.candidate.candidate_code, {
    trigger_type: "RECOMMENDATION_SPLIT",
    source_code: sourceCode,
    parameter_name: recommendation.parameter_name,
    note: pairedIncidenceWindow?.recommended_value
      ? `입사각 완화안 ${pairedIncidenceWindow.recommended_value}를 적용해 분리 후보를 생성했습니다.`
      : "repeat incidence 완화안을 분리 후보로 생성했습니다.",
  });
  elements.currentSummaryMessage.textContent = `분리 후보 ${created.candidate.candidate_code}를 생성하고 즉시 검증 실행했습니다.`;
}

async function applyRecommendationToExistingCandidate(recommendation) {
  if (!state.activeRequestCode) {
    throw new Error("먼저 요청건을 선택하세요.");
  }
  const targetCandidateCode = recommendation.recommendation_type;
  if (!targetCandidateCode) {
    throw new Error("추천안 대상 후보를 찾을 수 없습니다.");
  }
  const sourceReport = await fetchRequestCandidateReport(state.activeRequestCode, targetCandidateCode);
  const payload = {
    candidate_title: sourceReport.candidate.candidate_title,
    candidate_description: sourceReport.candidate.candidate_description,
    candidate_status: sourceReport.candidate.candidate_status,
    candidate_rank: sourceReport.candidate.candidate_rank,
    is_baseline: Boolean(sourceReport.candidate.is_baseline),
    input: applyRecommendationToDraftInput({ ...sourceReport.input }, recommendation),
  };
  const response = await fetch(`/requests/${state.activeRequestCode}/request-candidates/${targetCandidateCode}`, {
    method: "PATCH",
    headers: {
      "content-type": "application/json",
    },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(`추천안 반영 실패 (${response.status}). ${detail}`);
  }
  state.requestPayloadCache.delete(state.activeRequestCode);
  const refreshedPayload = await fetchRequestPayload(state.activeRequestCode, true);
  renderRequestScenario(refreshedPayload);
  await loadRequestCandidate(targetCandidateCode);
  await simulateSelectedCandidate(targetCandidateCode, {
    trigger_type: "RECOMMENDATION_APPLY",
    source_code: targetCandidateCode,
    parameter_name: recommendation.parameter_name,
    note: `${recommendation.parameter_name} 권고안을 ${recommendation.recommended_value}로 적용했습니다.`,
  });
  elements.currentSummaryMessage.textContent = `후보 ${targetCandidateCode}에 ${recommendation.parameter_name} 추천안을 반영하고 즉시 검증 실행했습니다.`;
}

function setFormValuesFromDraft(draft) {
  elements.candidateCode.value = "";
  elements.candidateCode.placeholder = "저장 시 자동 생성";
  elements.candidateTitle.value = draft.candidate_title;
  elements.candidateDescription.value = draft.candidate_description;
  elements.candidateStatus.value = draft.candidate_status;
  elements.candidateRank.value = String(draft.candidate_rank);
  elements.candidateIsBaseline.checked = Boolean(draft.is_baseline);
  for (const fieldName of formFields) {
    const element = document.getElementById(`sim-${fieldName.replaceAll("_", "-")}`);
    if (element) {
      element.value = String(draft.input[fieldName] ?? "");
    }
  }
  updateSensorFieldVisibility(draft.input.sensor_type);
  setCandidateCodeReadOnly(true);
}

function renderRequestList() {
  elements.requestList.innerHTML = "";
  elements.requestCount.textContent = String(state.requestCatalog.length);
  for (const requestItem of state.requestCatalog) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "entity-button";
    if (requestItem.request_code === state.activeRequestCode) {
      button.classList.add("active");
      button.classList.add("request-active");
    }
    button.innerHTML = `
      <p class="entity-caption"><span class="request-inline-title">${requestItem.request_title}</span><span class="request-inline-meta"> | ${requestItem.request_code} | ${requestItem.org_name} | ${requestItem.user_name}</span></p>
    `;
    button.addEventListener("click", () => loadRequest(requestItem.request_code));
    elements.requestList.appendChild(button);
  }
}

function renderRequestCandidateList(candidates) {
  elements.requestCandidateList.innerHTML = "";
  for (const candidate of candidates) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "entity-button";
    if (!state.candidateDraftMode && candidate.candidate_code === state.activeCandidateCode) {
      button.classList.add("active");
    }
    const currentVerdict = candidate.current_final_verdict ? localizeVerdict(candidate.current_final_verdict) : "평가 없음";
    const currentProbability = candidate.current_overall_probability !== null && candidate.current_overall_probability !== undefined
      ? formatProbability(candidate.current_overall_probability)
      : "-";
    const latestVerdict = candidate.latest_final_verdict ? localizeVerdict(candidate.latest_final_verdict) : "미실행";
    const latestProbability = candidate.latest_overall_probability !== null && candidate.latest_overall_probability !== undefined
      ? formatProbability(candidate.latest_overall_probability)
      : "-";
    button.innerHTML = `
      <div class="entity-topline">
        <span class="entity-title">${candidate.candidate_title}</span>
        <span class="entity-code">${candidate.candidate_code}</span>
      </div>
      <p class="entity-caption">${candidate.candidate_description}</p>
      <div class="stack-meta">
        ${candidate.is_baseline ? '<span class="meta-pill">기준안</span>' : ""}
        <span class="meta-pill">${localizeStatus(candidate.candidate_status)}</span>
        <span class="meta-pill">현재 평가 ${currentVerdict}</span>
        <span class="meta-pill">${currentProbability}</span>
        <span class="meta-pill">저장 실행 ${latestVerdict}</span>
        <span class="meta-pill">${latestProbability}</span>
      </div>
    `;
    button.addEventListener("click", () => loadRequestCandidate(candidate.candidate_code));
    elements.requestCandidateList.appendChild(button);
  }
}

function scrollActiveCandidateIntoView() {
  const activeButton = elements.requestCandidateList.querySelector(".entity-button.active");
  if (activeButton) {
    activeButton.scrollIntoView({ block: "nearest" });
  }
}

async function fetchRequestCatalog() {
  const response = await fetch("/requests");
  if (!response.ok) {
    throw new Error("요청 목록 조회 실패");
  }
  const payload = await response.json();
  state.requestCatalog = payload.items || [];
}

async function fetchRequestPayload(requestCode, force = false) {
  if (!force && state.requestPayloadCache.has(requestCode)) {
    return state.requestPayloadCache.get(requestCode);
  }
  const response = await fetch(`/requests/${requestCode}`);
  if (!response.ok) {
    throw new Error(`요청 데이터 조회 실패: ${requestCode}`);
  }
  const payload = await response.json();
  state.requestPayloadCache.set(requestCode, payload);
  return payload;
}

async function fetchRequestCandidateReport(requestCode, candidateCode) {
  const response = await fetch(`/requests/${requestCode}/request-candidates/${candidateCode}`);
  if (!response.ok) {
    throw new Error(`후보건 조회 실패: ${candidateCode}`);
  }
  return response.json();
}

function renderCandidates(payload) {
  elements.candidateTableBody.innerHTML = "";

  for (const candidate of payload.candidates || []) {
    const opportunityLabel = candidate.opportunity_start_at && candidate.opportunity_end_at
      ? `${candidate.opportunity_start_at} ~ ${candidate.opportunity_end_at}`
      : candidate.access_start_at && candidate.access_end_at
      ? `${candidate.access_start_at} ~ ${candidate.access_end_at}`
      : "촬영기회 미계산";
    const row = document.createElement("tr");
    row.className = "candidate-row";
    row.innerHTML = `
      <td>${candidate.candidate_code}<br><small>${candidate.candidate_title}</small></td>
      <td><span class="status-pill ${statusClass(candidate.candidate_status)}">${localizeStatus(candidate.candidate_status)}</span></td>
      <td>${opportunityLabel}</td>
      <td>${formatMaybe(candidate.required_off_nadir_deg)}</td>
      <td>${formatMaybe(candidate.predicted_incidence_deg)}</td>
      <td>${formatMaybe(candidate.expected_data_volume_gbit)} Gbit</td>
      <td>${formatProbability(candidate.p_total_candidate)}</td>
    `;
    elements.candidateTableBody.appendChild(row);
  }
}

function renderReasons(payload) {
  elements.reasonList.innerHTML = "";
  const reasons = payload.candidate_rejection_reasons || [];
  if (!reasons.length) {
    elements.reasonList.appendChild(
      createStackCard("탈락 사유 없음", "현재 후보 입력값 기준 평가에는 기록된 탈락 사유가 없습니다."),
    );
    return;
  }
  for (const reason of reasons) {
    elements.reasonList.appendChild(
      createStackCard(
        `${reason.candidate_code}: ${reason.reason_code}`,
        reason.reason_message,
        [reason.candidate_title, reason.reason_stage, reason.reason_severity],
      ),
    );
  }
}

function renderChecks(payload) {
  elements.checkList.innerHTML = "";
  for (const check of payload.candidate_checks || []) {
    const lines = [
      check.policy_feasible_flag !== undefined
        ? `정책: ${check.policy_feasible_flag ? "정상" : "실패"}${check.policy_alert_count ? ` (${check.policy_alert_count}건)` : ""}`
        : null,
      `자원: ${check.resource_feasible_flag ? "정상" : "실패"} | 필요 ${check.required_volume_gbit} Gbit / 가용 ${check.available_volume_gbit} Gbit`,
      `다운링크: ${check.downlink_feasible_flag ? "정상" : "실패"} | 가용 ${check.available_downlink_gbit} Gbit / 촬영 후 백로그 ${check.backlog_after_capture_gbit} Gbit`,
      check.selected_ground_station_code
        ? `지상국: ${check.selected_ground_station_code} | contact ${formatMaybe(check.contact_start_at)} ~ ${formatMaybe(check.contact_end_at)}`
        : null,
      check.contact_capacity_gbit !== undefined && check.contact_capacity_gbit !== null
        ? `contact 용량 ${check.contact_capacity_gbit} Gbit | 예약 ${formatMaybe(check.booking_reserved_gbit)} Gbit | 순가용 ${formatMaybe(check.net_contact_capacity_gbit)} Gbit`
        : null,
      check.task_conflict_count !== undefined || check.booking_conflict_count !== undefined
        ? `task 충돌 ${check.task_conflict_count ?? 0}건 | booking 충돌 ${check.booking_conflict_count ?? 0}건`
        : null,
      check.forecast_cloud_pct !== undefined || check.forecast_haze_index !== undefined
        ? `광학예보 구름 ${formatMaybe(check.forecast_cloud_pct)}% | haze ${formatMaybe(check.forecast_haze_index)} | 태양고도 ${formatMaybe(check.forecast_sun_elevation_deg)} | 태양방위각 ${formatMaybe(check.forecast_sun_azimuth_deg)} | AOI 방향 ${formatMaybe(check.dominant_axis_deg)} | 정오편차 ${formatMaybe(check.local_noon_distance_min)}분 | 그림자위험 ${formatMaybe(check.shadow_risk_score)}`
        : null,
      check.terrain_risk_score !== undefined
        ? `지형위험 ${formatMaybe(check.terrain_risk_type)} ${formatMaybe(check.terrain_risk_score)}`
        : null,
    ].filter(Boolean);
    elements.checkList.appendChild(
      createStackCard(`${check.candidate_code}`, lines.join(" "), [
        check.candidate_title,
        `전력 ${check.power_margin_pct}%`,
        `열 ${check.thermal_margin_pct}%`,
      ]),
    );
  }
}

function renderProbabilities(payload) {
  elements.probabilityList.innerHTML = "";
  for (const probability of payload.candidate_probabilities || []) {
    const lines = [
      `P(geo) ${formatProbability(probability.p_geo)}`,
      `P(env) ${formatProbability(probability.p_env)}`,
      `P(resource) ${formatProbability(probability.p_resource)}`,
      `P(downlink) ${formatProbability(probability.p_downlink)}`,
      probability.p_policy !== undefined ? `P(policy) ${formatProbability(probability.p_policy)}` : null,
      `P(conflict-adjusted) ${formatProbability(probability.p_conflict_adjusted)}`,
      `P(total) ${formatProbability(probability.p_total_candidate)}`,
    ].filter(Boolean);
    elements.probabilityList.appendChild(
      createStackCard(`${probability.candidate_code}`, lines.join(" | "), [probability.candidate_title, probability.probability_model_version]),
    );
  }
}

function renderRecommendations(payload) {
  elements.recommendationList.innerHTML = "";
  if (!(payload.recommendations || []).length) {
    elements.recommendationList.appendChild(
      createStackCard("권고 사항 없음", "현재 후보 입력값 기준 평가에는 추가 권고가 없습니다."),
    );
    return;
  }
  for (const recommendation of payload.recommendations) {
    elements.recommendationList.appendChild(
      createStackCard(
        `${recommendation.recommendation_type}: ${recommendation.parameter_name}`,
        recommendation.expected_effect_message,
        [
          `current ${recommendation.current_value}`,
          `recommended ${recommendation.recommended_value}`,
          `gain ${formatProbability(recommendation.expected_probability_gain)}`,
        ],
      ),
    );
  }
}

function renderRequestScenario(payload) {
  state.activeRequestPayload = payload;
  elements.caseTitle.classList.remove("hardcoded-copy");
  elements.caseDescription.classList.remove("hardcoded-copy");
  elements.caseTitle.textContent = payload.request.request_title;
  elements.caseDescription.textContent = payload.request.request_description;
  elements.caseRequestCode.textContent = payload.request.request_code;
  elements.caseSensorType.textContent = localizeSensorType(payload.sensor_options?.[0]?.sensor_type);

  elements.summaryVerdict.textContent = localizeVerdict(payload.result?.final_verdict);
  elements.summaryMessage.textContent = payload.result?.summary_message ?? "요청 전체 실행 결과가 없습니다.";
  elements.summaryProbability.textContent = formatProbability(payload.result?.overall_probability);
  elements.summaryRisk.textContent = [
    payload.result?.dominant_risk_code ? `주요 위험: ${payload.result.dominant_risk_code}` : "주요 위험 없음",
    payload.result?.first_feasible_attempt_at ? `첫 촬영기회: ${payload.result.first_feasible_attempt_at}` : null,
  ].filter(Boolean).join(" | ");
  elements.summaryCandidate.textContent = payload.result?.best_candidate_code ?? "평가 대상 없음";
  elements.summaryCandidateCaption.textContent = payload.result?.best_candidate_title
    ? [
        payload.result?.baseline_candidate_title
          ? `기준안: ${payload.result.baseline_candidate_title}`
          : null,
        `최적안: ${payload.result.best_candidate_title}`,
        `가능 ${payload.result.feasible_count ?? 0}건`,
        `조건부 ${payload.result.conditional_count ?? 0}건`,
        `불가 ${payload.result.rejected_count ?? 0}건`,
        payload.result?.expected_attempt_count !== null && payload.result?.expected_attempt_count !== undefined
          ? `예상 촬영기회 소진 수 ${payload.result.expected_attempt_count}`
          : null,
        payload.result?.attempt_count_considered
          ? `집계 반영 ${payload.result.attempt_count_considered}/${payload.result.max_attempts_considered}`
          : null,
      ].filter(Boolean).join(" | ")
    : `후보건 ${payload.request_candidates?.length ?? 0}건 관리 중`;

  renderSummaryTable(elements.proposalOverview, [
    [summaryLabel("누적 성공확률", "단일 후보 1건의 확률이 아니라, 요청 하위 후보나 촬영기회를 정책상 집계 상한 범위 안에서 순차적으로 반영했을 때 최종적으로 한 번이라도 성사될 확률입니다."), formatProbability(payload.proposal?.cumulative_probability)],
    [summaryLabel("예상 첫 촬영기회", "위성이 자동으로 첫 촬영을 시작하는 시각을 뜻하지 않습니다. 현재 요청 하위 후보나 촬영기회를 순서대로 검토했을 때, 처음으로 성사 가능성이 있는 유효 촬영기회 시각을 의미합니다."), payload.proposal?.first_feasible_attempt_at],
    [summaryLabel("예상 촬영기회 소진 수", "위성이 같은 촬영을 자동으로 여러 번 재시도한다는 뜻이 아닙니다. 요청 하위 후보나 촬영기회를 순차 검토한다고 볼 때 평균적으로 몇 개의 촬영기회를 소진하게 되는지를 나타내는 기대값입니다."), payload.proposal?.expected_attempt_count],
    [summaryLabel("집계 반영 후보 수", "요청 전체 누적 성공확률과 예상 촬영기회 소진 수 계산에 실제로 반영한 수행계획 후보 수입니다. 후보를 더 많이 만들어도 정책상 집계 상한을 넘는 후보는 요약 계산에서 제외될 수 있습니다."), payload.proposal?.attempt_count_considered],
    [summaryLabel("요구 반복 횟수", "반복 촬영 또는 모니터링 요청일 때 최소 몇 번의 유효 촬영기회가 필요하다고 보는지를 나타냅니다. 일반 단건 요청이면 보통 1입니다."), payload.proposal?.required_attempt_count],
    [summaryLabel("반복 요구 충족", "요구 반복 횟수 기준으로 유효한 기회 수가 충분한지 여부입니다. 반복 품질, 입사각 일관성, 재방문 간격 조건까지 반영한 뒤 최종 판단합니다."), payload.proposal?.repeat_requirement_met === undefined ? null : (payload.proposal.repeat_requirement_met ? "예" : "아니오")],
    [summaryLabel("품질 반영 시도 수", "반복 품질 하한을 넘는 후보 또는 촬영기회가 몇 건인지 나타냅니다. 반복 요구 충족 판단의 첫 번째 필터입니다."), payload.proposal?.repeat_quality_attempt_count],
    [summaryLabel("입사각 일관성 충족", "SAR 반복 촬영 후보들이 기준안 대비 허용 입사각 편차 안에 들어오는지 여부입니다. 반복 분석 품질 판단의 핵심 조건입니다."), payload.proposal?.repeat_incidence_met === undefined ? null : (payload.proposal.repeat_incidence_met ? "예" : "아니오")],
    [summaryLabel("일관성 반영 시도 수", "반복 품질 하한을 넘고, 기준안 대비 입사각 편차 한도도 만족하는 후보 또는 촬영기회 수입니다."), payload.proposal?.repeat_incidence_consistent_count],
    [summaryLabel("반복 간격 충족", "반복 촬영 후보들이 최소 재방문 간격 조건까지 만족하는지 여부입니다. 반복 요구 최종 충족 여부와 직접 연결됩니다."), payload.proposal?.repeat_spacing_met === undefined ? null : (payload.proposal.repeat_spacing_met ? "예" : "아니오")],
    [summaryLabel("간격 충족 시도 수", "반복 품질과 입사각 일관성을 통과한 후보 중에서, 최소 재방문 간격 조건까지 만족한 후보 또는 촬영기회 수입니다."), payload.proposal?.repeat_spaced_attempt_count],
  ]);

  renderDefinitionGrid(elements.policyOverview, [
    ["정책", payload.proposal?.service_policy_name],
    ["정책 우선순위", payload.proposal?.request_priority_tier],
    ["정책상 집계 상한", payload.proposal?.max_attempts_considered],
    ["반복 품질 하한", payload.proposal?.repeat_quality_threshold],
    ["반복 최소 간격", payload.proposal?.repeat_spacing_hours_required !== undefined && payload.proposal?.repeat_spacing_hours_required !== null ? `${payload.proposal.repeat_spacing_hours_required}h` : null],
    ["입사각 일관성 한도", payload.proposal?.repeat_incidence_tolerance_deg !== undefined && payload.proposal?.repeat_incidence_tolerance_deg !== null ? `${payload.proposal.repeat_incidence_tolerance_deg}deg` : null],
    ["SLA 요약", payload.proposal?.sla_summary],
  ]);

  renderDefinitionGrid(elements.requestOverview, [
    ["내부 요청코드", payload.request.request_code],
    ["외부 요청번호", payload.request.external_request_code],
    ["외부 요청시스템", payload.request.external_source_system_code],
    ["기관", payload.request.org_name],
    ["요청자", payload.request.user_name],
    ["정책", payload.request.policy_name],
    ["우선순위", payload.request.priority_tier],
    ["시작", payload.request.requested_start_at],
    ["종료", payload.request.requested_end_at],
    ["AOI 면적", `${payload.aoi.area_km2} km²`],
    ["AOI 방향", payload.aoi.dominant_axis_deg !== undefined && payload.aoi.dominant_axis_deg !== null ? `${payload.aoi.dominant_axis_deg}deg` : null],
    ["센서", payload.sensor_options?.[0]?.sensor_name],
    ["모드", payload.sensor_options?.[0]?.mode_code],
  ]);

  renderDefinitionGrid(elements.constraintOverview, [
    ["최대 구름", payload.constraint.max_cloud_pct],
    ["최대 오프나디르", payload.constraint.max_off_nadir_deg],
    ["최소 입사각", payload.constraint.min_incidence_deg],
    ["최대 입사각", payload.constraint.max_incidence_deg],
    ["최소 태양 고도", payload.constraint.min_sun_elevation_deg],
    ["요구 커버리지", payload.constraint.coverage_ratio_required],
    ["마감", payload.constraint.deadline_at],
    ["모니터링 횟수", payload.request.monitoring_count],
  ]);

  renderExternalRefs(payload);
  applyRequestCreateDefaultsFromPayload(payload);

  renderCandidates(payload);
  renderReasons(payload);
  renderChecks(payload);
  renderProbabilities(payload);
  renderRecommendations(payload);
  renderRequestCandidateList(payload.request_candidates || []);
}

function renderCandidateRun(report) {
  if (elements.candidateEvaluationTitle) {
    elements.candidateEvaluationTitle.textContent = `수행계획 후보별 현재 평가 - ${report.candidate.candidate_title}`;
  }
  renderEvaluationBlock(
    {
      verdict: elements.currentVerdict,
      summaryMessage: elements.currentSummaryMessage,
      probability: elements.currentProbability,
      dominantRisk: elements.currentDominantRisk,
      reasonList: elements.currentReasonList,
      checkList: elements.currentCheckList,
      recommendationList: document.createElement("div"),
    },
    report.current_evaluation,
    report.current_evaluation?.reasons || [],
    report.current_evaluation?.recommendations || [],
    {
      emptyVerdict: "미평가",
      emptySummary: "현재 입력 기준 평가가 없습니다.",
      emptyStatus: localizeStatus(report.candidate.candidate_status),
      emptyCheckCaption: "자원/다운링크 점검 전",
      emptyReasonTitle: "현재 평가 없음",
      emptyReasonBody: "후보 입력값이 아직 없어 현재 평가를 계산할 수 없습니다.",
      emptyCheckTitle: "현재 점검 결과 없음",
      emptyRecommendationTitle: "현재 권고 사항 없음",
    },
  );

  syncRunHistoryFilterButtons();
  elements.runHistoryList.innerHTML = "";
  const allRuns = report.runs || [];
  const filteredRuns = state.runHistoryMode === "actions"
    ? allRuns.filter((run) => isRecommendationTriggeredRun(run))
    : allRuns;
  if (!allRuns.length) {
    elements.runHistoryList.appendChild(
      createStackCard("실행 이력 없음", "아직 저장된 후보 실행 이력이 없습니다."),
    );
    return;
  }
  if (!filteredRuns.length) {
    elements.runHistoryList.appendChild(
      createStackCard("추천안 실행 이력 없음", "추천안 반영 또는 분리 후보 생성으로 저장된 실행 이력이 없습니다."),
    );
    return;
  }

  for (const run of filteredRuns) {
    const triggerSummary = run.run_trigger_type
      ? `${localizeTriggerType(run.run_trigger_type)} | ${formatMaybe(run.run_trigger_parameter_name)}`
      : "일반 실행";
    const triggerDetail = [run.run_trigger_source_code, run.run_trigger_note].filter(Boolean).join(" | ");
    elements.runHistoryList.appendChild(
      createStackCard(
        `Run #${run.run_sequence_no} · ${localizeVerdict(run.final_verdict)}`,
        triggerDetail || run.summary_message,
        [
          run.simulated_at,
          run.input_version_no !== undefined && run.input_version_no !== null ? `input v${run.input_version_no}` : null,
          triggerSummary,
          run.dominant_risk_code ? `risk ${run.dominant_risk_code}` : null,
          run.p_total_candidate !== undefined && run.p_total_candidate !== null
            ? `p ${formatProbability(run.p_total_candidate)}`
            : null,
        ].filter(Boolean),
      ),
    );
  }
}

async function simulateCurrentFormEvaluation() {
  const requestSeq = ++state.currentEvalRequestSeq;
  const payload = readSimulationFormInput();
  const url = state.activeRequestCode
    ? `/requests/${state.activeRequestCode}/simulate-candidate-input${state.activeCandidateCode && !state.candidateDraftMode ? `?candidate_code=${encodeURIComponent(state.activeCandidateCode)}` : ""}`
    : "/simulate";
  const response = await fetch(url, {
    method: "POST",
    headers: {
      "content-type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  if (requestSeq !== state.currentEvalRequestSeq) {
    return;
  }

  if (!response.ok) {
    renderEvaluationBlock(
      {
        verdict: elements.currentVerdict,
        summaryMessage: elements.currentSummaryMessage,
        probability: elements.currentProbability,
        dominantRisk: elements.currentDominantRisk,
        reasonList: elements.currentReasonList,
        checkList: elements.currentCheckList,
        recommendationList: document.createElement("div"),
      },
      null,
      [],
      [],
      {
        emptyVerdict: "입력 확인",
        emptySummary: "현재 입력값이 완전하지 않거나 유효성 조건을 만족하지 않습니다.",
        emptyStatus: state.candidateDraftMode ? "초안" : localizeStatus(elements.candidateStatus.value),
        emptyCheckCaption: "입력 보완 필요",
        emptyReasonTitle: "현재 평가 불가",
        emptyReasonBody: "필수 숫자 입력과 범위를 확인하세요.",
        emptyCheckTitle: "현재 점검 결과 없음",
        emptyRecommendationTitle: "현재 권고 사항 없음",
      },
    );
    return;
  }

  const evaluation = await response.json();
  if (requestSeq !== state.currentEvalRequestSeq) {
    return;
  }
  renderEvaluationBlock(
    {
      verdict: elements.currentVerdict,
      summaryMessage: elements.currentSummaryMessage,
      probability: elements.currentProbability,
      dominantRisk: elements.currentDominantRisk,
      reasonList: elements.currentReasonList,
      checkList: elements.currentCheckList,
      recommendationList: document.createElement("div"),
    },
    evaluation,
    evaluation.reasons || [],
    evaluation.recommendations || [],
  );
}

function scheduleCurrentFormEvaluation() {
  if (state.currentEvalTimer) {
    window.clearTimeout(state.currentEvalTimer);
  }
  state.currentEvalTimer = window.setTimeout(() => {
    state.currentEvalTimer = null;
    simulateCurrentFormEvaluation().catch(() => {
      renderEvaluationBlock(
        {
          verdict: elements.currentVerdict,
          summaryMessage: elements.currentSummaryMessage,
          probability: elements.currentProbability,
          dominantRisk: elements.currentDominantRisk,
          reasonList: elements.currentReasonList,
          checkList: elements.currentCheckList,
          recommendationList: document.createElement("div"),
        },
        null,
        [],
        [],
        {
          emptyVerdict: "오류",
          emptySummary: "현재 입력 기준 평가 계산 중 오류가 발생했습니다.",
          emptyStatus: state.candidateDraftMode ? "초안" : localizeStatus(elements.candidateStatus.value),
          emptyCheckCaption: "재시도 필요",
          emptyReasonTitle: "현재 평가 오류",
          emptyReasonBody: "입력을 다시 확인하거나 저장 후 검증 실행을 시도하세요.",
          emptyCheckTitle: "현재 점검 결과 없음",
          emptyRecommendationTitle: "현재 권고 사항 없음",
        },
      );
    });
  }, 250);
}

async function loadRequest(requestCode) {
  state.activeRequestCode = requestCode;
  state.activeCandidateCode = null;
  state.candidateDraftMode = false;
  persistSelection();
  renderRequestList();
  elements.caseTitle.textContent = "요청건 불러오는 중";
  elements.caseDescription.textContent = "요청 정보와 전체 feasibility 결과를 조회하는 중입니다.";
  try {
    const payload = await fetchRequestPayload(requestCode, true);
    renderRequestScenario(payload);
    const persisted = loadPersistedSelection();
    const firstCandidate = payload.request_candidates?.find(
      (candidate) => candidate.candidate_code === persisted.activeCandidateCode,
    ) ?? payload.request_candidates?.find(
      (candidate) => Boolean(candidate.is_baseline),
    ) ?? payload.request_candidates?.[0];
    if (firstCandidate) {
      await loadRequestCandidate(firstCandidate.candidate_code);
    } else {
      beginNewCandidateDraft();
    }
  } catch (error) {
    elements.caseTitle.textContent = "요청건 로드 실패";
    elements.caseDescription.textContent = String(error);
  }
}

async function saveExternalRef() {
  if (!state.activeRequestCode) {
    throw new Error("먼저 요청건을 선택하세요.");
  }
  const payload = {
    source_system_code: elements.externalRefSourceSystemCode.value.trim(),
    external_request_code: elements.externalRefCode.value.trim(),
    external_request_title: elements.externalRefTitle.value.trim() || null,
    external_customer_org_name: elements.externalRefOrgName.value.trim() || null,
    external_requester_name: elements.externalRefRequesterName.value.trim() || null,
    is_primary: elements.externalRefIsPrimary.checked,
    received_at: toUtcIsoString(elements.externalRefReceivedAt.value) || null,
  };
  if (!payload.source_system_code || !payload.external_request_code) {
    throw new Error("외부 시스템 코드와 외부 요청번호는 필수입니다.");
  }
  const response = await fetch(`/requests/${state.activeRequestCode}/external-refs`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    const detail = await readErrorDetail(response);
    throw new Error(`외부 요청번호 저장 실패 (${response.status}). ${detail}`);
  }
  state.requestPayloadCache.delete(state.activeRequestCode);
  const refreshedPayload = await fetchRequestPayload(state.activeRequestCode, true);
  renderRequestScenario(refreshedPayload);
  elements.externalRefCode.value = "";
  elements.externalRefTitle.value = "";
  elements.externalRefReceivedAt.value = "";
}

async function setPrimaryExternalRef(requestExternalRefId) {
  if (!state.activeRequestCode) {
    throw new Error("먼저 요청건을 선택하세요.");
  }
  const response = await fetch(`/requests/${state.activeRequestCode}/external-refs/${requestExternalRefId}`, {
    method: "PATCH",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ is_primary: true }),
  });
  if (!response.ok) {
    const detail = await readErrorDetail(response);
    throw new Error(`기본 외부 요청번호 지정 실패 (${response.status}). ${detail}`);
  }
  state.requestPayloadCache.delete(state.activeRequestCode);
  const refreshedPayload = await fetchRequestPayload(state.activeRequestCode, true);
  renderRequestScenario(refreshedPayload);
}

async function deleteExternalRef(requestExternalRefId) {
  if (!state.activeRequestCode) {
    throw new Error("먼저 요청건을 선택하세요.");
  }
  const response = await fetch(`/requests/${state.activeRequestCode}/external-refs/${requestExternalRefId}`, {
    method: "DELETE",
  });
  if (!response.ok) {
    const detail = await readErrorDetail(response);
    throw new Error(`외부 요청번호 삭제 실패 (${response.status}). ${detail}`);
  }
  state.requestPayloadCache.delete(state.activeRequestCode);
  const refreshedPayload = await fetchRequestPayload(state.activeRequestCode, true);
  renderRequestScenario(refreshedPayload);
}

async function createRequestFromForm() {
  const payload = buildRequestCreatePayload();
  const response = await fetch("/requests", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    const detail = await readErrorDetail(response);
    throw new Error(`새 요청 저장 실패 (${response.status}). ${detail}`);
  }
  const created = await response.json();
  state.requestPayloadCache.delete(created.request.request_code);
  await fetchRequestCatalog();
  renderRequestList();
  await loadRequest(created.request.request_code);
  elements.currentSummaryMessage.textContent = `새 요청 ${created.request.request_code}가 생성되었습니다.`;
}

async function loadRequestCandidate(candidateCode) {
  if (!state.activeRequestCode) {
    return;
  }
  state.activeCandidateCode = candidateCode;
  state.candidateDraftMode = false;
  persistSelection();
  renderRequestCandidateList(state.activeRequestPayload?.request_candidates || []);
  const report = await fetchRequestCandidateReport(state.activeRequestCode, candidateCode);
  setFormValuesFromCandidate(report);
  renderCandidateRun(report);
}

function beginNewCandidateDraft() {
  if (!state.activeRequestPayload) {
    return;
  }
  state.candidateDraftMode = true;
  state.activeCandidateCode = null;
  persistSelection();
  renderRequestCandidateList(state.activeRequestPayload.request_candidates || []);
  setFormValuesFromDraft(buildDefaultCandidateDraft(state.activeRequestPayload));
  renderEvaluationBlock(
    {
      verdict: elements.currentVerdict,
      summaryMessage: elements.currentSummaryMessage,
      probability: elements.currentProbability,
      dominantRisk: elements.currentDominantRisk,
      reasonList: elements.currentReasonList,
      checkList: elements.currentCheckList,
      recommendationList: document.createElement("div"),
    },
    null,
    [],
    [],
    {
      emptyVerdict: "초안",
      emptySummary: "새 후보 초안을 작성 중입니다. 입력값을 저장하면 현재 평가 기준이 만들어집니다.",
      emptyStatus: "초안",
      emptyCheckCaption: "아직 평가 전",
      emptyReasonTitle: "초안 상태",
      emptyReasonBody: "후보 제목과 입력값을 저장하면 현재 입력 기준 평가를 확인할 수 있습니다.",
      emptyCheckTitle: "현재 점검 결과 없음",
      emptyRecommendationTitle: "현재 권고 사항 없음",
    },
  );
  renderEvaluationBlock(
    {
      verdict: elements.simVerdict,
      summaryMessage: elements.simSummaryMessage,
      probability: elements.simProbability,
      dominantRisk: elements.simDominantRisk,
      reasonList: elements.simulateReasonList,
      checkList: elements.simulateCheckList,
      recommendationList: elements.simulateRecommendationList,
    },
    null,
    [],
    [],
    {
      emptyVerdict: "미실행",
      emptySummary: "새 후보 초안에는 아직 저장 실행 결과가 없습니다.",
      emptyStatus: "초안",
      emptyCheckCaption: "아직 검증 전",
      emptyReasonTitle: "실행 이력 없음",
      emptyReasonBody: "저장 후 검증 실행을 수행하면 최신 저장 실행 결과가 여기에 표시됩니다.",
      emptyCheckTitle: "점검 결과 없음",
      emptyRecommendationTitle: "권고 사항 없음",
    },
  );
}

async function saveCandidateForm() {
  if (!state.activeRequestCode) {
    throw new Error("먼저 요청건을 선택하세요.");
  }
  const payload = readCandidateForm();
  if (!payload.candidate_title) {
    throw new Error("후보 제목은 비워둘 수 없습니다.");
  }
  const method = state.candidateDraftMode ? "POST" : "PATCH";
  const createdNewCandidate = state.candidateDraftMode;
  const url = state.candidateDraftMode
    ? `/requests/${state.activeRequestCode}/request-candidates`
    : `/requests/${state.activeRequestCode}/request-candidates/${state.activeCandidateCode}`;
  const response = await fetch(url, {
    method,
    headers: {
      "content-type": "application/json",
    },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    const detail = await readErrorDetail(response);
    throw new Error(`후보 저장 실패 (${response.status}). ${detail}`);
  }
  const saved = await response.json();
  state.activeCandidateCode = saved.candidate.candidate_code;
  state.candidateDraftMode = false;
  persistSelection();
  state.requestPayloadCache.delete(state.activeRequestCode);
  const refreshedPayload = await fetchRequestPayload(state.activeRequestCode, true);
  renderRequestScenario(refreshedPayload);
  if (createdNewCandidate) {
    scrollActiveCandidateIntoView();
  }
  const refreshedCandidate = await fetchRequestCandidateReport(state.activeRequestCode, state.activeCandidateCode);
  setFormValuesFromCandidate(refreshedCandidate);
  renderCandidateRun(refreshedCandidate);
  return refreshedCandidate;
}

async function simulateSelectedCandidate(candidateCode = state.activeCandidateCode, trigger = null) {
  if (!state.activeRequestCode || !candidateCode) {
    throw new Error("저장된 후보를 먼저 선택하세요.");
  }
  const response = await fetch(`/requests/${state.activeRequestCode}/request-candidates/${candidateCode}/simulate`, {
    method: "POST",
    headers: {
      "content-type": "application/json",
    },
    body: JSON.stringify(trigger || { trigger_type: "MANUAL_SAVE_AND_RUN" }),
  });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(`후보 검증 실행 실패 (${response.status}). ${detail}`);
  }
  const report = await response.json();
  state.activeCandidateCode = candidateCode;
  persistSelection();
  state.requestPayloadCache.delete(state.activeRequestCode);
  const refreshedPayload = await fetchRequestPayload(state.activeRequestCode, true);
  renderRequestScenario(refreshedPayload);
  renderCandidateRun(report);
  return report;
}

async function deleteSelectedCandidate() {
  if (!state.activeRequestCode || !state.activeCandidateCode) {
    throw new Error("삭제할 후보를 먼저 선택하세요.");
  }
  const response = await fetch(`/requests/${state.activeRequestCode}/request-candidates/${state.activeCandidateCode}`, {
    method: "DELETE",
  });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(`후보 삭제 실패 (${response.status}). ${detail}`);
  }
  state.requestPayloadCache.delete(state.activeRequestCode);
  const refreshedPayload = await fetchRequestPayload(state.activeRequestCode, true);
  renderRequestScenario(refreshedPayload);
  const nextCandidate = refreshedPayload.request_candidates?.[0];
  if (nextCandidate) {
    await loadRequestCandidate(nextCandidate.candidate_code);
  } else {
    persistSelection();
    beginNewCandidateDraft();
  }
}

async function checkHealth() {
  try {
    const response = await fetch("/health");
    const payload = await response.json();
    elements.healthStatus.textContent = payload.status === "ok" ? "정상" : "성능 저하";
  } catch {
    elements.healthStatus.textContent = "오프라인";
  }
}

elements.apiBase.textContent = window.location.origin;

elements.simulateForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  try {
    await saveCandidateForm();
    await simulateSelectedCandidate();
  } catch (error) {
    elements.simVerdict.textContent = "오류";
    elements.simSummaryMessage.textContent = String(error);
  }
});

elements.simSensorType.addEventListener("change", (event) => {
  updateSensorFieldVisibility(event.target.value);
});

elements.simulateForm.addEventListener("input", (event) => {
  if (event.target?.id === "sim-opportunity-start-at") {
    syncOpportunityFields("start");
  } else if (event.target?.id === "sim-opportunity-end-at") {
    syncOpportunityFields("end");
  } else if (event.target?.id === "sim-window-hours") {
    syncOpportunityFields("window");
  }
  scheduleCurrentFormEvaluation();
});

elements.simulateForm.addEventListener("change", (event) => {
  if (event.target?.id === "sim-opportunity-start-at") {
    syncOpportunityFields("start");
  } else if (event.target?.id === "sim-opportunity-end-at") {
    syncOpportunityFields("end");
  } else if (event.target?.id === "sim-window-hours") {
    syncOpportunityFields("window");
  }
  scheduleCurrentFormEvaluation();
});

elements.reloadSelectedCandidate.addEventListener("click", async () => {
  try {
    if (state.candidateDraftMode) {
      beginNewCandidateDraft();
      return;
    }
    if (!state.activeCandidateCode) {
      throw new Error("다시 불러올 후보가 없습니다.");
    }
    await loadRequestCandidate(state.activeCandidateCode);
  } catch (error) {
    elements.simVerdict.textContent = "오류";
    elements.simSummaryMessage.textContent = String(error);
  }
});

elements.saveCandidate.addEventListener("click", async () => {
  try {
    await saveCandidateForm();
    elements.simVerdict.textContent = "저장됨";
    elements.simSummaryMessage.textContent = "후보 입력값이 저장되었습니다. 필요하면 바로 검증 실행을 수행하세요.";
  } catch (error) {
    elements.simVerdict.textContent = "오류";
    elements.simSummaryMessage.textContent = String(error);
  }
});

elements.candidateCreateNew.addEventListener("click", () => {
  beginNewCandidateDraft();
});

elements.candidateDelete.addEventListener("click", async () => {
  try {
    await deleteSelectedCandidate();
  } catch (error) {
    elements.simVerdict.textContent = "오류";
    elements.simSummaryMessage.textContent = String(error);
  }
});

elements.externalRefForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  try {
    elements.externalRefStatus.textContent = "저장 중...";
    await saveExternalRef();
    elements.currentSummaryMessage.textContent = "외부 요청번호 매핑이 저장되었습니다.";
    elements.externalRefStatus.textContent = "외부 요청번호 매핑이 저장되었습니다.";
  } catch (error) {
    elements.currentSummaryMessage.textContent = String(error);
    elements.externalRefStatus.textContent = String(error);
  }
});

elements.externalRefToggle.addEventListener("click", () => {
  elements.externalRefPanel.classList.toggle("is-collapsed");
  syncExternalRefPanel();
});

elements.requestInfoToggle.addEventListener("click", () => {
  elements.requestInfoPanel.classList.toggle("is-collapsed");
  syncRequestInfoPanel();
});

elements.requestCreateForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  try {
    await createRequestFromForm();
    elements.requestCreateTitle.value = "";
    elements.requestCreateDescription.value = "";
    elements.requestCreateExternalCode.value = "";
  } catch (error) {
    elements.caseTitle.textContent = "요청 생성 실패";
    elements.caseDescription.textContent = String(error);
  }
});

elements.requestCreatePolicy.addEventListener("change", () => {
  const isSar = Number(elements.requestCreatePolicy.value) === 2;
  elements.requestCreatePriority.value = isSar ? "PRIORITY" : "STANDARD";
});

elements.runHistoryAll.addEventListener("click", () => {
  state.runHistoryMode = "all";
  if (state.activeRequestCode && state.activeCandidateCode && !state.candidateDraftMode) {
    loadRequestCandidate(state.activeCandidateCode).catch((error) => {
      elements.simVerdict.textContent = "오류";
      elements.simSummaryMessage.textContent = String(error);
    });
  } else {
    syncRunHistoryFilterButtons();
  }
});

elements.runHistoryActions.addEventListener("click", () => {
  state.runHistoryMode = "actions";
  if (state.activeRequestCode && state.activeCandidateCode && !state.candidateDraftMode) {
    loadRequestCandidate(state.activeCandidateCode).catch((error) => {
      elements.simVerdict.textContent = "오류";
      elements.simSummaryMessage.textContent = String(error);
    });
  } else {
    syncRunHistoryFilterButtons();
  }
});

async function bootstrapPage() {
  try {
    syncRequestInfoPanel();
    syncExternalRefPanel();
    await fetchRequestCatalog();
    const persisted = loadPersistedSelection();
    const initialRequest = state.requestCatalog.find(
      (item) => item.request_code === persisted.activeRequestCode,
    ) || state.requestCatalog[0];
    renderRequestList();
    checkHealth();
    if (initialRequest) {
      await loadRequest(initialRequest.request_code);
    }
  } catch (error) {
    elements.caseTitle.textContent = "초기 로드 실패";
    elements.caseDescription.textContent = String(error);
  }
}

bootstrapPage();
