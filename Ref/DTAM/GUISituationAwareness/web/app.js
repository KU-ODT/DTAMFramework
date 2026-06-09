console.log("Situation Awareness Dashboard Loaded");

const consoleLog = document.getElementById("consoleLog");
const riskScore = document.getElementById("riskScore");
const riskBar = document.getElementById("riskBar");
const riskLevel = document.getElementById("riskLevel");
const objectCount = document.getElementById("objectCount");
const distance = document.getElementById("distance");
const ttc = document.getElementById("ttc");
const uncertainty = document.getElementById("uncertainty");
const advisoryText = document.getElementById("advisoryText");

const startBtn = document.getElementById("startBtn");
const connectBtn = document.getElementById("connectBtn");

function addLog(message) {
    const p = document.createElement("p");
    const time = new Date().toLocaleTimeString();
    p.textContent = `[${time}] ${message}`;
    consoleLog.appendChild(p);
    consoleLog.scrollTop = consoleLog.scrollHeight;
}

function updateDemoData() {
    const score = Math.random() * 0.75;
    const scoreText = score.toFixed(2);

    riskScore.textContent = scoreText;
    riskBar.style.width = `${score * 100}%`;

    if (score <= 0.3) {
        riskLevel.textContent = "SAFE";
        riskLevel.className = "risk-level safe";
        riskBar.style.background = "#41ff8a";
        advisoryText.textContent = "Maintain current course and continue monitoring.";
    } else if (score <= 0.6) {
        riskLevel.textContent = "CAUTION";
        riskLevel.className = "risk-level caution";
        riskBar.style.background = "#ffd166";
        advisoryText.textContent = "Reduce speed and monitor detected object trajectory.";
    } else {
        riskLevel.textContent = "EMERGENCY";
        riskLevel.className = "risk-level emergency";
        riskBar.style.background = "#ff4d4d";
        advisoryText.textContent = "Execute immediate avoidance maneuver.";
    }

    objectCount.textContent = Math.floor(Math.random() * 6);
    distance.textContent = `${(10 + Math.random() * 80).toFixed(1)} m`;
    ttc.textContent = `${(2 + Math.random() * 20).toFixed(1)} s`;
    uncertainty.textContent = Math.random().toFixed(2);
}

startBtn.addEventListener("click", () => {
    addLog("Start Monitoring button clicked");
    updateDemoData();
});

connectBtn.addEventListener("click", () => {
    addLog("Connect UAMSim button clicked");
});

const socket = new WebSocket("ws://127.0.0.1:8010/ws");

socket.onopen = () => {
    addLog("WebSocket connected");
};

socket.onmessage = (event) => {

    const data = JSON.parse(event.data);

    riskScore.textContent = data.risk_score;
    riskLevel.textContent = data.risk_level;

    objectCount.textContent = data.object_count;
    distance.textContent = data.distance;
    ttc.textContent = data.ttc;
    uncertainty.textContent = data.uncertainty;

    advisoryText.textContent = data.advisory;

    const score = parseFloat(data.risk_score);

    riskBar.style.width = `${score * 100}%`;

    if (data.risk_level === "SAFE") {
        riskLevel.className = "risk-level safe";
        riskBar.style.background = "#41ff8a";
    }
    else if (data.risk_level === "CAUTION") {
        riskLevel.className = "risk-level caution";
        riskBar.style.background = "#ffd166";
    }
    else {
        riskLevel.className = "risk-level emergency";
        riskBar.style.background = "#ff4d4d";
    }
};

socket.onerror = () => {
    addLog("WebSocket error");
};

socket.onclose = () => {
    addLog("WebSocket disconnected");
};addLog("Static dashboard ready");