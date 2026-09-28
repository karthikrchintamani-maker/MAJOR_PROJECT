// RoadEye Telemetry Cockpit JS Handler

let telemetryData = [];
let telemetryChart = null;
let selectedFile = null;
let activeSegment = null;
let activeTimestamp = null;

document.addEventListener("DOMContentLoaded", () => {
    initUI();
    loadSegments();
});

function initUI() {
    const dropZone = document.getElementById("drop-zone");
    const fileInput = document.getElementById("file-input");
    const runBtn = document.getElementById("run-btn");
    const dummyBtn = document.getElementById("dummy-btn");
    const clearFileBtn = document.getElementById("clear-file-btn");
    const segmentSelect = document.getElementById("segment-select");
    const confSlider = document.getElementById("conf-slider");
    const confVal = document.getElementById("conf-val");

    // Slider display update
    confSlider.addEventListener("input", (e) => {
        confVal.innerText = parseFloat(e.target.value).toFixed(2);
    });

    // Segment selector selection
    segmentSelect.addEventListener("change", (e) => {
        const seg = e.target.value;
        if (seg) {
            loadTelemetry(seg);
        }
    });

    // Uploader interactions
    dropZone.addEventListener("click", () => fileInput.click());
    
    fileInput.addEventListener("change", (e) => {
        if (e.target.files.length > 0) {
            handleFileSelect(e.target.files[0]);
        }
    });

    dropZone.addEventListener("dragover", (e) => {
        e.preventDefault();
        dropZone.classList.add("dragover");
    });

    dropZone.addEventListener("dragleave", () => {
        dropZone.classList.remove("dragover");
    });

    dropZone.addEventListener("drop", (e) => {
        e.preventDefault();
        dropZone.classList.remove("dragover");
        if (e.dataTransfer.files.length > 0) {
            handleFileSelect(e.dataTransfer.files[0]);
        }
    });

    clearFileBtn.addEventListener("click", (e) => {
        e.stopPropagation();
        selectedFile = null;
        fileInput.value = "";
        document.getElementById("file-info").classList.add("hidden");
        document.getElementById("filename-display").innerText = "No file selected";
    });

    // Run buttons
    runBtn.addEventListener("click", () => runPipeline());
    dummyBtn.addEventListener("click", () => runDummy());
}

function handleFileSelect(file) {
    selectedFile = file;
    document.getElementById("filename-display").innerText = file.name;
    document.getElementById("file-info").classList.remove("hidden");
}

async function loadSegments() {
    try {
        const res = await fetch("/api/segments");
        if (!res.ok) throw new Error("Failed to load segments");
        const data = await res.json();
        
        const select = document.getElementById("segment-select");
        select.innerHTML = '<option value="">-- Choose Segment --</option>';
        data.segments.forEach(seg => {
            select.innerHTML += `<option value="${seg}">${seg}</option>`;
        });
    } catch (err) {
        console.error(err);
        document.getElementById("segment-select").innerHTML = '<option value="">Error loading segments</option>';
    }
}

async function loadTelemetry(segment) {
    try {
        activeSegment = segment;
        const res = await fetch(`/api/telemetry?segment=${segment}`);
        if (!res.ok) throw new Error("Failed to load telemetry data");
        const data = await res.json();
        
        telemetryData = data.telemetry;
        initChart(telemetryData);
        
        // Populate instruments with the first record as a baseline
        if (telemetryData.length > 0) {
            updateDashboard(telemetryData[0]);
        }
    } catch (err) {
        console.error(err);
    }
}

function initChart(records) {
    const ctx = document.getElementById("telemetry-chart").getContext("2d");
    
    // Process labels (time) and values
    const labels = records.map(r => r.timestamp.split(" ")[1].substring(0, 8));
    const speedData = records.map(r => r.SPEED);
    const rpmData = records.map(r => r.RPM);

    if (telemetryChart) {
        telemetryChart.destroy();
    }

    telemetryChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [
                {
                    label: 'Speed (km/h)',
                    data: speedData,
                    borderColor: '#06b6d4',
                    borderWidth: 2,
                    pointRadius: 1,
                    pointHoverRadius: 5,
                    fill: false,
                    yAxisID: 'y'
                },
                {
                    label: 'RPM',
                    data: rpmData,
                    borderColor: '#10b981',
                    borderWidth: 1.5,
                    pointRadius: 0,
                    pointHoverRadius: 4,
                    fill: false,
                    yAxisID: 'y1'
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: {
                mode: 'index',
                intersect: false,
            },
            plugins: {
                legend: {
                    labels: { color: '#94a3b8', font: { size: 11 } }
                }
            },
            scales: {
                x: {
                    grid: { color: 'rgba(30, 41, 59, 0.3)' },
                    ticks: { color: '#94a3b8', maxTicksLimit: 12 }
                },
                y: {
                    type: 'linear',
                    display: true,
                    position: 'left',
                    grid: { color: 'rgba(30, 41, 59, 0.3)' },
                    ticks: { color: '#06b6d4' },
                    title: { display: true, text: 'Speed (km/h)', color: '#06b6d4' }
                },
                y1: {
                    type: 'linear',
                    display: true,
                    position: 'right',
                    grid: { drawOnChartArea: false },
                    ticks: { color: '#10b981' },
                    title: { display: true, text: 'RPM', color: '#10b981' }
                }
            },
            onClick: (e) => {
                const points = telemetryChart.getElementsAtEventForMode(e, 'index', { intersect: false }, true);
                if (points.length > 0) {
                    const idx = points[0].index;
                    const record = records[idx];
                    updateDashboard(record);
                    
                    // If a file is uploaded or we are using dummy mode, run pipeline for the clicked timestamp
                    if (selectedFile || document.getElementById("output-image").src.includes("dummy")) {
                        runPipelineForTimestamp(record.timestamp);
                    }
                }
            }
        }
    });
}

function updateDashboard(record) {
    activeTimestamp = record.timestamp;
    
    // Update Text HUD info
    document.getElementById("hud-time").innerText = record.timestamp.split(" ")[1].substring(0, 11);
    document.getElementById("hud-seg").innerText = activeSegment || "--";
    
    // Update gauges
    const speed = record.SPEED || 0.0;
    const rpm = record.RPM || 0.0;
    
    updateGauge("speed", speed, 200); // 200 km/h max
    updateGauge("rpm", rpm, 6000);   // 6000 RPM max
    
    // Update auxiliary dashboard items
    document.getElementById("gear-val").innerText = record.GEAR ? record.GEAR : "N";
    document.getElementById("throttle-val").innerText = `${(record.THROTTLE_POS || 0.0).toFixed(0)}%`;
    document.getElementById("load-val").innerText = `${(record.ENGINE_LOAD || 0.0).toFixed(0)}%`;
    document.getElementById("fuel-val").innerText = `${(record.REAL_FUEL_USAGE_ML_MIN || 0.0).toFixed(1)} ml/m`;
}

function updateGauge(gaugeId, value, maxVal) {
    const percent = Math.min((value / maxVal) * 100, 100);
    const dial = document.querySelector(`.${gaugeId}-dial`);
    const valEl = document.getElementById(`${gaugeId}-val`);
    
    dial.style.setProperty('--gauge-percent', `${percent}%`);
    valEl.innerText = gaugeId === 'speed' ? value.toFixed(1) : Math.round(value);
}

async function runPipeline() {
    if (!selectedFile) {
        alert("Please select or drop an image or video file to process.");
        return;
    }
    
    const formData = new FormData();
    formData.append("file", selectedFile);
    formData.append("conf_threshold", document.getElementById("conf-slider").value);
    
    if (activeSegment) formData.append("segment", activeSegment);
    if (activeTimestamp) formData.append("timestamp", activeTimestamp);

    showLoading(true);
    try {
        const res = await fetch("/api/process", {
            method: "POST",
            body: formData
        });
        
        if (!res.ok) {
            const err = await res.json();
            throw new Error(err.detail || "Pipeline processing error");
        }
        
        const data = await res.json();
        displayOutput(data);
    } catch (err) {
        alert(err.message);
        console.error(err);
    } finally {
        showLoading(false);
    }
}

async function runPipelineForTimestamp(timestamp) {
    const formData = new FormData();
    formData.append("conf_threshold", document.getElementById("conf-slider").value);
    formData.append("timestamp", timestamp);
    
    if (selectedFile) {
        formData.append("file", selectedFile);
    } else {
        formData.append("use_dummy", "true");
    }

    try {
        const res = await fetch("/api/process", {
            method: "POST",
            body: formData
        });
        
        if (!res.ok) return;
        const data = await res.json();
        displayOutput(data);
    } catch (err) {
        console.error("Frame update failed:", err);
    }
}

async function runDummy() {
    const formData = new FormData();
    formData.append("use_dummy", "true");
    formData.append("conf_threshold", document.getElementById("conf-slider").value);
    
    if (activeSegment) formData.append("segment", activeSegment);
    if (activeTimestamp) formData.append("timestamp", activeTimestamp);

    showLoading(true);
    try {
        const res = await fetch("/api/process", {
            method: "POST",
            body: formData
        });
        
        if (!res.ok) {
            const err = await res.json();
            throw new Error(err.detail || "Pipeline processing error");
        }
        
        const data = await res.json();
        displayOutput(data);
    } catch (err) {
        alert(err.message);
        console.error(err);
    } finally {
        showLoading(false);
    }
}

function displayOutput(data) {
    const imgEl = document.getElementById("output-image");
    const vidEl = document.getElementById("output-video");
    const placeholder = document.getElementById("media-placeholder");
    
    placeholder.classList.add("hidden");
    
    if (data.type === "video" || data.url.endsWith(".mp4") || data.url.endsWith(".avi") || data.url.endsWith(".mkv") || data.url.endsWith(".mov")) {
        imgEl.classList.add("hidden");
        vidEl.classList.remove("hidden");
        vidEl.src = data.url;
        vidEl.load();
    } else {
        vidEl.classList.add("hidden");
        imgEl.classList.remove("hidden");
        imgEl.src = data.url;
    }
    
    if (data.telemetry) {
        updateDashboard(data.telemetry);
    }
}

function showLoading(show) {
    const loader = document.getElementById("loading-overlay");
    if (show) {
        loader.classList.remove("hidden");
    } else {
        loader.classList.add("hidden");
    }
}
