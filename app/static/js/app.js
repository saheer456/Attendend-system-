/* ===================================================================
   Smart Attendance — Admin Dashboard JS
   =================================================================== */
(function () {
  "use strict";

  const $ = (id) => document.getElementById(id);

  // ---- Sidebar tab switching ----
  const tabButtons = document.querySelectorAll(".sidebar-link[data-tab]");
  const panels = document.querySelectorAll(".tab-panel");

  tabButtons.forEach((btn) => {
    btn.addEventListener("click", () => {
      const tab = btn.dataset.tab;
      tabButtons.forEach((b) => b.classList.remove("active"));
      panels.forEach((p) => p.classList.remove("active"));
      btn.classList.add("active");
      const panel = $("panel-" + tab);
      if (panel) panel.classList.add("active");
      const sidebar = $("sidebar");
      if (sidebar) sidebar.classList.remove("open");
    });
  });

  // ---- Mobile menu ----
  const menuToggle = $("menu-toggle");
  const sidebar = $("sidebar");
  if (menuToggle && sidebar) {
    menuToggle.addEventListener("click", () => sidebar.classList.toggle("open"));
    document.addEventListener("click", (e) => {
      if (!sidebar.contains(e.target) && e.target !== menuToggle) sidebar.classList.remove("open");
    });
  }

  // ---- DOM refs ----
  const studentForm = $("student-form");
  const sessionForm = $("session-form");
  const teacherForm = $("teacher-form");
  const studentMessage = $("student-message");
  const enrollMessage = $("enroll-message");
  const sessionMessage = $("session-message");
  const teacherMessage = $("teacher-message");
  const qrBlock = $("qr-block");
  const qrEmpty = $("qr-empty");
  const qrImage = $("qr-image");
  const qrText = $("qr-text");
  const challengeText = $("challenge-text");
  const enrollRollNo = $("enroll-roll-no");
  const enrollCamera = $("enroll-camera");
  const enrollCanvas = $("enroll-canvas");
  const enrollCamDot = $("enroll-cam-dot");
  const enrollCamLabel = $("enroll-cam-label");
  const startEnrollCameraBtn = $("start-enroll-camera");
  const enrollFaceBtn = $("enroll-face-btn");
  const activeSessionsList = $("active-sessions-list");
  const studentsTable = $("students-table");
  const reportSessionId = $("report-session-id");
  const reportDate = $("report-date");
  const exportReportBtn = $("export-report");

  if (!studentForm || !sessionForm) return;

  let enrollStream = null;

  // ---- Helpers ----
  function showMsg(el, text, ok) {
    if (!el) return;
    el.textContent = text;
    el.className = `msg show ${ok ? "ok" : "err"}`;
  }

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

  async function openCamera(videoEl, dotEl, labelEl) {
    if (!navigator.mediaDevices?.getUserMedia) throw new Error("Camera not supported.");
    const stream = await navigator.mediaDevices.getUserMedia({
      video: { facingMode: "user", width: { ideal: 640 }, height: { ideal: 480 } },
      audio: false,
    });
    videoEl.srcObject = stream;
    await videoEl.play();
    if (dotEl) dotEl.classList.add("live");
    if (labelEl) labelEl.textContent = "Live";
    return stream;
  }

  function captureFrame(videoEl, canvasEl) {
    if (!videoEl.videoWidth) throw new Error("Camera not ready.");
    canvasEl.width = videoEl.videoWidth;
    canvasEl.height = videoEl.videoHeight;
    canvasEl.getContext("2d").drawImage(videoEl, 0, 0);
    return canvasEl.toDataURL("image/jpeg", 0.9);
  }

  // ---- Student Registration ----
  studentForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const fd = new FormData(studentForm);
    try {
      const res = await api("/api/students", "POST", {
        roll_no: fd.get("roll_no"),
        full_name: fd.get("full_name"),
        department: fd.get("department"),
        semester: fd.get("semester"),
        email: fd.get("email"),
        password: fd.get("password"),
      });
      showMsg(studentMessage, `Student added: ${res.student.roll_no}`, true);
      studentForm.reset();

      const opt = document.createElement("option");
      opt.value = res.student.roll_no;
      opt.textContent = `${res.student.roll_no} — ${res.student.full_name}`;
      enrollRollNo.appendChild(opt);

      // Reload to show updated table with percentage
      setTimeout(() => window.location.reload(), 800);
    } catch (err) {
      showMsg(studentMessage, err.message, false);
    }
  });

  // ---- Face Enrollment Camera ----
  if (startEnrollCameraBtn) {
    startEnrollCameraBtn.addEventListener("click", async () => {
      try {
        if (enrollStream) { enrollStream.getTracks().forEach((t) => t.stop()); enrollStream = null; }
        enrollStream = await openCamera(enrollCamera, enrollCamDot, enrollCamLabel);
        showMsg(enrollMessage, "Camera started. Position face and click enroll.", true);
      } catch (err) {
        showMsg(enrollMessage, err.message, false);
      }
    });
  }

  if (enrollFaceBtn) {
    enrollFaceBtn.addEventListener("click", async () => {
      try {
        if (!enrollRollNo.value) throw new Error("Select a student first.");
        if (!enrollStream) {
          enrollStream = await openCamera(enrollCamera, enrollCamDot, enrollCamLabel);
          await new Promise((r) => setTimeout(r, 500));
        }
        showMsg(enrollMessage, "Capturing face…", true);
        const frame = captureFrame(enrollCamera, enrollCanvas);
        await api("/api/students/enroll-face", "POST", { roll_no: enrollRollNo.value, frame });

        const row = studentsTable.querySelector(`tr[data-roll-no="${enrollRollNo.value}"] td:nth-child(4)`);
        if (row) row.innerHTML = '<span class="badge badge-success">✓ Enrolled</span>';
        for (const opt of enrollRollNo.options) {
          if (opt.value === enrollRollNo.value && !opt.textContent.includes("✓")) opt.textContent += " ✓";
        }
        showMsg(enrollMessage, "Face enrolled successfully!", true);
      } catch (err) {
        showMsg(enrollMessage, err.message, false);
      }
    });
  }

  // ---- Session Creation ----
  sessionForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const fd = new FormData(sessionForm);
    try {
      const res = await api("/api/sessions", "POST", {
        session_name: fd.get("session_name"),
        duration_min: fd.get("duration_min"),
      });
      qrImage.src = res.qr_image;
      qrText.value = res.qr_text;
      challengeText.textContent = res.session.challenge;
      qrBlock.classList.remove("hidden");
      if (qrEmpty) qrEmpty.classList.add("hidden");

      const item = document.createElement("div");
      item.className = "session-item";
      item.dataset.sessionId = res.session.id;
      item.innerHTML = `
        <div class="session-info"><h4>${res.session.name}</h4><span>Expires: ${res.session.expires_at}</span></div>
        <button class="btn btn-outline-danger btn-sm close-session-btn" data-session-id="${res.session.id}">Close</button>
      `;
      activeSessionsList.prepend(item);
      showMsg(sessionMessage, `Session #${res.session.id} created.`, true);
    } catch (err) {
      showMsg(sessionMessage, err.message, false);
    }
  });

  // ---- Teacher Creation (Admin) ----
  if (teacherForm) {
    teacherForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      const fd = new FormData(teacherForm);
      try {
        const res = await api("/api/teachers", "POST", {
          full_name: fd.get("full_name"),
          email: fd.get("email"),
          password: fd.get("password"),
        });
        showMsg(teacherMessage, `Teacher added: ${res.teacher.email}`, true);
        teacherForm.reset();
        setTimeout(() => window.location.reload(), 800);
      } catch (err) {
        showMsg(teacherMessage, err.message, false);
      }
    });
  }

  // ---- Delegated clicks (Close, Delete) ----
  document.addEventListener("click", async (e) => {
    const closeBtn = e.target.closest(".close-session-btn");
    if (closeBtn) {
      try {
        await api(`/api/sessions/${closeBtn.dataset.sessionId}/close`, "POST");
        const item = closeBtn.closest("[data-session-id]");
        if (item) item.remove();
        showMsg(sessionMessage, "Session closed.", true);
      } catch (err) { showMsg(sessionMessage, err.message, false); }
      return;
    }

    const deleteBtn = e.target.closest(".delete-student-btn");
    if (deleteBtn) {
      if (!confirm("Delete this student and all records?")) return;
      try {
        await api(`/api/students/${deleteBtn.dataset.studentId}`, "DELETE");
        const row = deleteBtn.closest("tr");
        const roll = row?.dataset.rollNo;
        if (row) row.remove();
        if (roll) { for (const opt of Array.from(enrollRollNo.options)) { if (opt.value === roll) opt.remove(); } }
        showMsg(studentMessage, "Student deleted.", true);
      } catch (err) { showMsg(studentMessage, err.message, false); }
      return;
    }

    const deleteTeacherBtn = e.target.closest(".delete-teacher-btn");
    if (deleteTeacherBtn) {
      if (!confirm("Delete this teacher?")) return;
      try {
        await api(`/api/teachers/${deleteTeacherBtn.dataset.userId}`, "DELETE");
        const row = deleteTeacherBtn.closest("tr");
        if (row) row.remove();
        showMsg(teacherMessage, "Teacher deleted.", true);
      } catch (err) { showMsg(teacherMessage, err.message, false); }
      return;
    }

    const manageBtn = e.target.closest(".manage-session-btn");
    if (manageBtn) {
      const sessionId = manageBtn.dataset.sessionId;
      openManageModal(sessionId);
      return;
    }

    const toggleBtn = e.target.closest(".toggle-attendance-btn");
    if (toggleBtn) {
      const sessionId = toggleBtn.dataset.sessionId;
      const studentId = toggleBtn.dataset.studentId;
      const newStatus = toggleBtn.dataset.status; // 'present' or 'absent'
      
      toggleBtn.disabled = true;
      try {
        await api(`/api/sessions/${sessionId}/attendance/manual`, "POST", {
          student_id: studentId,
          status: newStatus
        });
        // Reload the modal data
        openManageModal(sessionId);
      } catch (err) {
        showMsg($("manage-message"), err.message, false);
        toggleBtn.disabled = false;
      }
      return;
    }
  });

  // ---- Manage Session Modal ----
  const manageModal = $("manage-session-modal");
  const closeManageModalBtn = $("close-manage-modal");
  
  if (closeManageModalBtn) {
    closeManageModalBtn.addEventListener("click", () => {
      manageModal.classList.add("hidden");
    });
  }

  async function openManageModal(sessionId) {
    if (!manageModal) return;
    
    $("manage-modal-title").textContent = `Loading Session #${sessionId}...`;
    $("manage-roster-tbody").innerHTML = `<tr><td colspan="6" class="text-center text-muted">Loading...</td></tr>`;
    $("manage-message").className = "msg";
    manageModal.classList.remove("hidden");

    try {
      const data = await api(`/api/sessions/${sessionId}/attendance`, "GET");
      
      $("manage-modal-title").textContent = `Manage: ${data.session_name}`;
      $("manage-stat-total").textContent = data.total_students;
      $("manage-stat-present").textContent = data.present_count;
      $("manage-stat-absent").textContent = data.total_students - data.present_count;
      
      const tbody = $("manage-roster-tbody");
      tbody.innerHTML = "";
      
      if (data.roster.length === 0) {
        tbody.innerHTML = `<tr><td colspan="6" class="text-center text-muted">No students registered.</td></tr>`;
      } else {
        data.roster.forEach(s => {
          const statusBadge = s.is_present 
            ? `<span class="badge badge-success">Present</span>` 
            : `<span class="badge badge-danger" style="background:var(--danger-light);color:var(--danger)">Absent</span>`;
            
          const actionBtn = s.is_present
            ? `<button class="btn btn-outline-danger btn-sm toggle-attendance-btn" data-session-id="${sessionId}" data-student-id="${s.student_id}" data-status="absent">Mark Absent</button>`
            : `<button class="btn btn-success btn-sm toggle-attendance-btn" data-session-id="${sessionId}" data-student-id="${s.student_id}" data-status="present">Mark Present</button>`;
            
          const sourceText = s.is_present ? `<div class="text-xs text-muted mt-sm">${s.source || ''}</div>` : '';
          
          const tr = document.createElement("tr");
          tr.innerHTML = `
            <td>${s.roll_no}</td>
            <td>${s.full_name}</td>
            <td>${s.department}</td>
            <td>${s.semester}</td>
            <td>${statusBadge}${sourceText}</td>
            <td>${actionBtn}</td>
          `;
          tbody.appendChild(tr);
        });
      }
    } catch (err) {
      showMsg($("manage-message"), "Failed to load session data.", false);
    }
  }

  // ---- Export CSV ----
  if (exportReportBtn) {
    exportReportBtn.addEventListener("click", () => {
      const params = new URLSearchParams();
      if (reportSessionId?.value) params.set("session_id", reportSessionId.value);
      if (reportDate?.value) params.set("date", reportDate.value);
      const qs = params.toString() ? `?${params.toString()}` : "";
      window.location.href = `/api/reports/attendance.csv${qs}`;
    });
  }
})();
