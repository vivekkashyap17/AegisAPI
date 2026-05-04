const API_BASE_URL = "http://127.0.0.1:8000";

const form = document.getElementById("trafficForm");
const analyzeBtn = document.getElementById("analyzeBtn");
const fillSampleBtn = document.getElementById("fillSampleBtn");
const formMessage = document.getElementById("formMessage");
const output = document.getElementById("output");

const backendStatus = document.getElementById("backendStatus");
const statusDot = document.querySelector(".status-dot");

const trustScore = document.getElementById("trustScore");
const scoreBar = document.getElementById("scoreBar");
const riskStatus = document.getElementById("riskStatus");
const policyAction = document.getElementById("policyAction");

function setMessage(message, type = "") {
  formMessage.textContent = message;
  formMessage.className = `form-message ${type}`;
}

function getTrafficPayload() {
  return {
    user_id: document.getElementById("user_id").value.trim(),
    ip_address: document.getElementById("ip").value.trim(),
    request_count: Number(document.getElementById("requests").value),
    failed_logins: Number(document.getElementById("failed").value)
  };
}

function validatePayload(data) {
  if (!data.user_id || !data.ip_address) {
    return "User ID and IP Address are required.";
  }

  if (Number.isNaN(data.request_count) || data.request_count < 0) {
    return "Request Count must be a valid positive number.";
  }

  if (Number.isNaN(data.failed_logins) || data.failed_logins < 0) {
    return "Failed Logins must be a valid positive number.";
  }

  return "";
}

function normalizeTrustScore(result) {
  const possibleScore =
    result.trust_score ??
    result.trustScore ??
    result.score ??
    result.risk_score;

  const score = Number(possibleScore);

  if (Number.isNaN(score)) {
    return null;
  }

  return Math.max(0, Math.min(1, score));
}

function getPolicyAction(result, score) {
  if (result.action) return result.action;
  if (result.policy_action) return result.policy_action;
  if (result.decision) return result.decision;

  if (score === null) return "--";
  if (score >= 0.8) return "allow";
  if (score >= 0.5) return "restrict";
  if (score >= 0.3) return "re-auth";
  return "quarantine";
}

function getRiskStatus(score, result) {
  if (result.status && result.status !== "ok") return result.status;
  if (result.risk_level) return result.risk_level;

  if (score === null) return "Analyzed";
  if (score >= 0.8) return "Low Risk";
  if (score >= 0.5) return "Medium Risk";
  if (score >= 0.3) return "High Risk";
  return "Critical";
}

function updateResultUI(result) {
  const score = normalizeTrustScore(result);
  const scorePercent = score === null ? 0 : Math.round(score * 100);

  trustScore.textContent = score === null ? "--" : score.toFixed(2);
  scoreBar.style.width = `${scorePercent}%`;

  if (score === null) {
    scoreBar.style.background = "#38bdf8";
  } else if (score >= 0.8) {
    scoreBar.style.background = "#22c55e";
  } else if (score >= 0.5) {
    scoreBar.style.background = "#f59e0b";
  } else {
    scoreBar.style.background = "#ef4444";
  }

  riskStatus.textContent = getRiskStatus(score, result);
  policyAction.textContent = getPolicyAction(result, score);
  output.textContent = JSON.stringify(result, null, 2);
}

async function checkBackendStatus() {
  try {
    const response = await fetch(`${API_BASE_URL}/`);

    if (!response.ok) {
      throw new Error("Backend responded with an error.");
    }

    backendStatus.textContent = "Online";
    statusDot.classList.add("online");
    statusDot.classList.remove("offline");
  } catch {
    backendStatus.textContent = "Offline";
    statusDot.classList.add("offline");
    statusDot.classList.remove("online");
  }
}

async function sendTrafficEvent(event) {
  event.preventDefault();

  const data = getTrafficPayload();
  const error = validatePayload(data);

  if (error) {
    setMessage(error, "error");
    return;
  }

  analyzeBtn.disabled = true;
  analyzeBtn.textContent = "Analyzing...";
  setMessage("Sending event to anomaly detection engine...");

  try {
    const response = await fetch(`${API_BASE_URL}/ingest`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify(data)
    });

    const result = await response.json();

    if (!response.ok) {
      throw new Error(result.detail || "Request failed.");
    }

    updateResultUI(result);
    setMessage("Traffic event analyzed successfully.", "success");
  } catch (error) {
    output.textContent = JSON.stringify(
      {
        error: error.message,
        hint: "Make sure FastAPI is running and CORS is enabled."
      },
      null,
      2
    );

    setMessage("Unable to analyze traffic event.", "error");
  } finally {
    analyzeBtn.disabled = false;
    analyzeBtn.textContent = "Analyze Event";
  }
}

function fillSampleData() {
  document.getElementById("user_id").value = "user_1024";
  document.getElementById("ip").value = "192.168.1.15";
  document.getElementById("requests").value = "140";
  document.getElementById("failed").value = "4";
  setMessage("Sample traffic event added.");
}

form.addEventListener("submit", sendTrafficEvent);
fillSampleBtn.addEventListener("click", fillSampleData);

checkBackendStatus();
