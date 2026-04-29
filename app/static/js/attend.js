/* ===================================================================
   Smart Attendance — Student Portal JS (2-step wizard)
   =================================================================== */
(function () {
  "use strict";

  const $ = (id) => document.getElementById(id);

  // ---- DOM refs ----
  const startWizardBtn = $("start-wizard");
  const wizardDiv = $("wizard");
  const markSection = $("mark-section");

  const scannedQr = $("att-scanned-qr");
  const startScanBtn = $("start-scan-btn");
  const qrScanInfo = $("qr-scan-info");
  const qrSessionName = $("qr-session-name");
  const step1Next = $("step-1-next");
  const step1Back = $("step-1-back");
  const qrMessage = $("qr-message");

  const attCamera = $("att-camera");
  const attCanvas = $("att-canvas");
  const attCamDot = $("att-cam-dot");
  const attCamLabel = $("att-cam-label");
  const attChallenge = $("att-challenge");
  const attMarkBtn = $("att-mark-btn");
  const step2Back = $("step-2-back");
  const attMessage = $("att-message");

  const resultContent = $("result-content");

  const step1 = $("step-1");
  const step2 = $("step-2");
  const stepResult = $("step-result");
  const stepInd1 = $("step-ind-1");
  const stepInd2 = $("step-ind-2");

  if (!startWizardBtn || !wizardDiv) return;

  let qrScanner = null;
  let scanning = false;
  let cameraStream = null;
  let parsedQr = null;

  // ---- Helpers ----
  function showMsg(el, text, ok) {
    if (!el) return;
    el.textContent = text;
    el.className = `msg show ${ok ? "ok" : "err"}`;
  }

  function hideMsg(el) { if (el) el.className = "msg"; }

  async function api(url, method, body) {
    const res = await fetch(url, {
      method,
      headers: { "Content-Type": "application/json" },
      body: body ? JSON.stringify(body) : undefined,
    });
    const data = await res.json();
    if (!res.ok || !data.ok) throw new Error(data.message || "Request failed.");
    return data;
  }

  function delay(ms) { return new Promise((r) => setTimeout(r, ms)); }

  function goToStep(n) {
    [step1, step2, stepResult].forEach((s) => s && s.classList.add("hidden"));
    [stepInd1, stepInd2].forEach((ind, i) => {
      ind.classList.remove("active", "done");
      if (i < n) ind.classList.add("done");
      else if (i === n) ind.classList.add("active");
    });
    if (n === 0 && step1) step1.classList.remove("hidden");
    if (n === 1 && step2) step2.classList.remove("hidden");
    if (n === 2 && stepResult) stepResult.classList.remove("hidden");
  }

  function stopScanner() {
    if (qrScanner && scanning) {
      try { qrScanner.stop(); qrScanner.clear(); } catch (_) {}
      scanning = false;
    }
  }

  // ---- Start wizard ----
  startWizardBtn.addEventListener("click", () => {
    wizardDiv.classList.remove("hidden");
    markSection.classList.add("hidden");
    goToStep(0);
  });

  // ---- Step 1: QR Scan ----
  step1Back.addEventListener("click", () => {
    stopScanner();
    wizardDiv.classList.add("hidden");
    markSection.classList.remove("hidden");
  });

  startScanBtn.addEventListener("click", async () => {
    if (typeof Html5Qrcode === "undefined") {
      showMsg(qrMessage, "QR scanner library not loaded.", false);
      return;
    }
    if (scanning) {
      stopScanner();
      startScanBtn.textContent = "Start QR Scanner";
      return;
    }
    try {
      qrScanner = new Html5Qrcode("qr-reader");
      await qrScanner.start(
        { facingMode: "environment" },
        { fps: 10, qrbox: { width: 220, height: 220 } },
        (decoded) => {
          scannedQr.value = decoded;
          stopScanner();
          startScanBtn.textContent = "Start QR Scanner";
          handleQrContent(decoded);
        }
      );
      scanning = true;
      startScanBtn.textContent = "Stop Scanner";
    } catch (err) {
      showMsg(qrMessage, "Could not start scanner. Check camera permissions.", false);
    }
  });

  scannedQr.addEventListener("input", () => {
    const val = scannedQr.value.trim();
    if (val) handleQrContent(val);
  });

  function handleQrContent(text) {
    hideMsg(qrMessage);
    try {
      parsedQr = JSON.parse(text);
      if (!parsedQr.session_id || !parsedQr.token) throw new Error("Missing data.");
      if (parsedQr.challenge) attChallenge.textContent = parsedQr.challenge;
      qrScanInfo.classList.remove("hidden");
      qrSessionName.textContent = `Session #${parsedQr.session_id}`;
      step1Next.disabled = false;
    } catch (e) {
      parsedQr = null;
      qrScanInfo.classList.add("hidden");
      step1Next.disabled = true;
      showMsg(qrMessage, "Invalid QR content.", false);
    }
  }

  step1Next.addEventListener("click", async () => {
    goToStep(1);
    try {
      if (cameraStream) cameraStream.getTracks().forEach((t) => t.stop());
      cameraStream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: "user", width: { ideal: 640 }, height: { ideal: 480 } },
        audio: false,
      });
      attCamera.srcObject = cameraStream;
      await attCamera.play();
      attCamDot.classList.add("live");
      attCamLabel.textContent = "Live";
    } catch (err) {
      showMsg(attMessage, "Cannot access camera: " + err.message, false);
    }
  });

  // ---- Step 2: Face Verification ----
  step2Back.addEventListener("click", () => {
    if (cameraStream) {
      cameraStream.getTracks().forEach((t) => t.stop());
      cameraStream = null;
      attCamDot.classList.remove("live");
      attCamLabel.textContent = "Camera off";
    }
    goToStep(0);
  });

  function captureFrame() {
    if (!attCamera.videoWidth) throw new Error("Camera not ready.");
    attCanvas.width = attCamera.videoWidth;
    attCanvas.height = attCamera.videoHeight;
    attCanvas.getContext("2d").drawImage(attCamera, 0, 0);
    return attCanvas.toDataURL("image/jpeg", 0.9);
  }

  attMarkBtn.addEventListener("click", async () => {
    try {
      if (!parsedQr) throw new Error("No QR data.");
      if (!cameraStream) throw new Error("Camera not active.");

      attMarkBtn.disabled = true;
      attMarkBtn.textContent = "Capturing…";
      showMsg(attMessage, "Taking two photos for liveness. Follow the challenge!", true);

      const frameA = captureFrame();
      await delay(1200);
      const frameB = captureFrame();

      attMarkBtn.textContent = "Verifying…";

      const res = await api("/api/attendance/mark", "POST", {
        qr_text: scannedQr.value.trim(),
        frame_a: frameA,
        frame_b: frameB,
      });

      if (cameraStream) { cameraStream.getTracks().forEach((t) => t.stop()); cameraStream = null; }

      const rec = res.record;
      resultContent.innerHTML = `
        <div class="result-icon success">✓</div>
        <h3 style="font-size:1.2rem;font-weight:700;margin-bottom:0.5rem;">Attendance Marked!</h3>
        <p class="text-sm text-muted" style="margin-bottom:1rem;">
          ${rec.student_name} (${rec.student})<br>Session: ${rec.session}
        </p>
        <div style="display:inline-flex;gap:1.5rem;font-size:0.82rem;">
          <div><strong>Liveness</strong><br>${Number(rec.liveness_score).toFixed(2)}</div>
          <div><strong>Face Match</strong><br>${Number(rec.face_match_score).toFixed(2)}</div>
        </div>
        <div class="mt-lg">
          <button onclick="window.location.reload()" class="btn btn-primary">Back to Dashboard</button>
        </div>
      `;
      goToStep(2);
    } catch (err) {
      showMsg(attMessage, err.message, false);
    } finally {
      attMarkBtn.disabled = false;
      attMarkBtn.textContent = "📸 Capture & Mark Attendance";
    }
  });
})();
