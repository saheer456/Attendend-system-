(function () {
  const byId = (id) => document.getElementById(id);

  const studentForm = byId("student-form");
  const sessionForm = byId("session-form");
  const studentMessage = byId("student-message");
  const sessionMessage = byId("session-message");
  const attendanceMessage = byId("attendance-message");
  const qrBlock = byId("qr-block");
  const qrEmpty = byId("qr-empty");
  const qrImage = byId("qr-image");
  const qrText = byId("qr-text");
  const scannedQr = byId("scanned-qr");
  const challengeText = byId("challenge-text");
  const video = byId("camera-preview");
  const canvas = byId("capture-canvas");
  const rollNo = byId("roll-no");
  const cameraSource = byId("camera-source");
  const startCameraBtn = byId("start-camera");
  const scanQrBtn = byId("scan-qr");
  const enrollFaceBtn = byId("enroll-face");
  const markBtn = byId("mark-attendance");
  const activeSessionsList = byId("active-sessions-list");
  const studentsTable = byId("students-table");
  const reportSessionId = byId("report-session-id");
  const reportDate = byId("report-date");
  const exportReportBtn = byId("export-report");

  if (!studentForm || !sessionForm) return;

  let mediaStream = null;
  let qrScanner = null;
  let scanning = false;

  function showMessage(el, text, ok) {
    if (!el) return;
    el.textContent = text;
    el.className = ok ? "small text-success mt-2" : "small text-danger mt-2";
  }

  async function requestJson(url, method, body) {
    const response = await fetch(url, {
      method,
      headers: { "Content-Type": "application/json" },
      body: body ? JSON.stringify(body) : undefined,
    });
    const data = await response.json();
    if (!response.ok || !data.ok) {
      throw new Error(data.message || "Request failed.");
    }
    return data;
  }

  async function startCamera() {
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      throw new Error("Camera access is not supported in this browser.");
    }
    if (mediaStream) {
      mediaStream.getTracks().forEach((track) => track.stop());
      mediaStream = null;
    }
    const mode = cameraSource.value === "phone" ? "environment" : "user";
    mediaStream = await navigator.mediaDevices.getUserMedia({
      video: { facingMode: mode, width: { ideal: 640 }, height: { ideal: 480 } },
      audio: false,
    });
    video.srcObject = mediaStream;
    await video.play();
  }

  function captureFrame() {
    if (!video.videoWidth || !video.videoHeight) {
      throw new Error("Camera is not ready yet.");
    }
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    const ctx = canvas.getContext("2d");
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
    return canvas.toDataURL("image/jpeg", 0.9);
  }

  function delay(ms) {
    return new Promise((resolve) => setTimeout(resolve, ms));
  }

  function setOptionFaceState(roll, enrolled) {
    for (const opt of rollNo.options) {
      if (opt.value === roll) {
        const base = opt.textContent.split(" [Face")[0];
        opt.textContent = `${base} ${enrolled ? "[Face Enrolled]" : "[Face Not Enrolled]"}`;
      }
    }
  }

  function appendStudentRow(student) {
    if (!studentsTable) return;
    const row = document.createElement("tr");
    row.dataset.studentId = String(student.id);
    row.dataset.rollNo = student.roll_no;
    row.innerHTML = `
      <td>${student.roll_no}</td>
      <td>${student.full_name}</td>
      <td><span class="badge bg-warning-subtle text-warning-emphasis">Not Enrolled</span></td>
      <td>
        <button class="btn btn-sm btn-outline-danger delete-student-btn" data-student-id="${student.id}">
          Delete
        </button>
      </td>
    `;
    studentsTable.prepend(row);
  }

  function appendSessionCard(session) {
    if (!activeSessionsList) return;
    const card = document.createElement("div");
    card.className = "border rounded p-2 bg-light-subtle";
    card.dataset.sessionId = String(session.id);
    card.innerHTML = `
      <div class="fw-semibold small">${session.name}</div>
      <div class="tiny text-muted mb-2">Expires: ${session.expires_at}</div>
      <button class="btn btn-sm btn-outline-danger close-session-btn" data-session-id="${session.id}">
        Close Session
      </button>
    `;
    activeSessionsList.prepend(card);
  }

  function appendSessionFilterOption(session) {
    if (!reportSessionId) return;
    const option = document.createElement("option");
    option.value = session.id;
    option.textContent = `${session.name} (${session.starts_at})`;
    reportSessionId.prepend(option);
  }

  studentForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const formData = new FormData(studentForm);
    const payload = {
      roll_no: formData.get("roll_no"),
      full_name: formData.get("full_name"),
      department: formData.get("department"),
      semester: formData.get("semester"),
    };
    try {
      const result = await requestJson("/api/students", "POST", payload);
      showMessage(studentMessage, `Student added: ${result.student.roll_no}`, true);
      studentForm.reset();

      const option = document.createElement("option");
      option.value = result.student.roll_no;
      option.textContent = `${result.student.roll_no} - ${result.student.full_name} [Face Not Enrolled]`;
      rollNo.appendChild(option);
      appendStudentRow(result.student);
    } catch (error) {
      showMessage(studentMessage, error.message, false);
    }
  });

  sessionForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const formData = new FormData(sessionForm);
    const payload = {
      session_name: formData.get("session_name"),
      duration_min: formData.get("duration_min"),
    };
    try {
      const result = await requestJson("/api/sessions", "POST", payload);
      qrImage.src = result.qr_image;
      qrText.value = result.qr_text;
      scannedQr.value = result.qr_text;
      challengeText.textContent = result.session.challenge;
      qrBlock.classList.remove("d-none");
      if (qrEmpty) qrEmpty.classList.add("d-none");
      appendSessionCard(result.session);
      appendSessionFilterOption(result.session);
      showMessage(
        sessionMessage,
        `Session created (#${result.session.id}). Expires at ${result.session.expires_at}`,
        true
      );
    } catch (error) {
      showMessage(sessionMessage, error.message, false);
    }
  });

  startCameraBtn.addEventListener("click", async () => {
    try {
      await startCamera();
      showMessage(attendanceMessage, "Camera started.", true);
    } catch (error) {
      showMessage(attendanceMessage, error.message, false);
    }
  });

  if (enrollFaceBtn) {
    enrollFaceBtn.addEventListener("click", async () => {
      try {
        if (!rollNo.value) throw new Error("Select a student first.");
        if (!mediaStream) await startCamera();
        showMessage(attendanceMessage, "Capturing face profile...", true);
        const frame = captureFrame();
        await requestJson("/api/students/enroll-face", "POST", {
          roll_no: rollNo.value,
          frame,
        });
        setOptionFaceState(rollNo.value, true);
        const row = studentsTable?.querySelector(`tr[data-roll-no="${rollNo.value}"] td:nth-child(3)`);
        if (row) {
          row.innerHTML = '<span class="badge bg-success-subtle text-success-emphasis">Enrolled</span>';
        }
        showMessage(attendanceMessage, "Face enrolled successfully.", true);
      } catch (error) {
        showMessage(attendanceMessage, error.message, false);
      }
    });
  }

  scanQrBtn.addEventListener("click", async () => {
    if (typeof Html5Qrcode === "undefined") {
      showMessage(attendanceMessage, "QR scanner library failed to load.", false);
      return;
    }
    if (scanning) {
      try {
        await qrScanner.stop();
        qrScanner.clear();
      } catch (e) {
        // ignore scanner close failures
      }
      scanning = false;
      showMessage(attendanceMessage, "QR scanner stopped.", true);
      return;
    }
    try {
      qrScanner = new Html5Qrcode("qr-reader");
      const mode = cameraSource.value === "phone" ? "environment" : "user";
      await qrScanner.start(
        { facingMode: mode },
        { fps: 10, qrbox: { width: 220, height: 220 } },
        async (decodedText) => {
          scannedQr.value = decodedText;
          await qrScanner.stop();
          qrScanner.clear();
          scanning = false;
          showMessage(attendanceMessage, "QR scanned successfully.", true);
        }
      );
      scanning = true;
      showMessage(attendanceMessage, "Scanning QR. Click Scan QR again to stop.", true);
    } catch (error) {
      scanning = false;
      showMessage(attendanceMessage, "Could not start QR scanner.", false);
    }
  });

  markBtn.addEventListener("click", async () => {
    try {
      if (!rollNo.value) throw new Error("Please select a student.");
      if (!scannedQr.value.trim()) throw new Error("Please scan or paste QR content.");
      if (!mediaStream) await startCamera();

      showMessage(attendanceMessage, "Capturing two frames for liveness and face confirmation...", true);
      const frameA = captureFrame();
      await delay(900);
      const frameB = captureFrame();

      const result = await requestJson("/api/attendance/mark", "POST", {
        roll_no: rollNo.value,
        qr_text: scannedQr.value.trim(),
        frame_a: frameA,
        frame_b: frameB,
        source: cameraSource.value,
      });
      const liveScore = Number(result.record.liveness_score).toFixed(2);
      const matchScore = Number(result.record.face_match_score).toFixed(2);
      showMessage(
        attendanceMessage,
        `Attendance marked. Liveness: ${liveScore}, Face Match: ${matchScore}`,
        true
      );
      setTimeout(() => window.location.reload(), 1200);
    } catch (error) {
      showMessage(attendanceMessage, error.message, false);
    }
  });

  document.addEventListener("click", async (event) => {
    const closeBtn = event.target.closest(".close-session-btn");
    if (closeBtn) {
      const sessionId = closeBtn.dataset.sessionId;
      try {
        await requestJson(`/api/sessions/${sessionId}/close`, "POST");
        showMessage(sessionMessage, "Session closed.", true);
        const card = closeBtn.closest("[data-session-id]");
        if (card) card.remove();
      } catch (error) {
        showMessage(sessionMessage, error.message, false);
      }
      return;
    }

    const deleteBtn = event.target.closest(".delete-student-btn");
    if (deleteBtn) {
      const studentId = deleteBtn.dataset.studentId;
      if (!window.confirm("Delete this student and attendance records?")) return;
      try {
        await requestJson(`/api/students/${studentId}`, "DELETE");
        const row = deleteBtn.closest("tr");
        const deletedRoll = row?.dataset.rollNo;
        if (row) row.remove();
        if (deletedRoll) {
          for (const opt of Array.from(rollNo.options)) {
            if (opt.value === deletedRoll) opt.remove();
          }
        }
        showMessage(studentMessage, "Student deleted.", true);
      } catch (error) {
        showMessage(studentMessage, error.message, false);
      }
    }
  });

  if (exportReportBtn) {
    exportReportBtn.addEventListener("click", () => {
      const params = new URLSearchParams();
      if (reportSessionId?.value) params.set("session_id", reportSessionId.value);
      if (reportDate?.value) params.set("date", reportDate.value);
      const suffix = params.toString() ? `?${params.toString()}` : "";
      window.location.href = `/api/reports/attendance.csv${suffix}`;
    });
  }
})();
