# Task Board - Smart Attendance System

## Sprint 0 - Project Setup (Current)

### Done
- [x] Create no-login dashboard web app
- [x] Add database models for student/session/attendance
- [x] Implement student registration API
- [x] Implement student delete/list APIs
- [x] Implement live session + QR generation API
- [x] Implement active session close/list APIs
- [x] Implement attendance marking API using webcam/phone frames
- [x] Add anti-fake attendance checks
- [x] Add webcam-based identity confirmation (enrolled face vs live face match)
- [x] Add health endpoint (`/health`) with CV readiness flag
- [x] Implement attendance CSV export endpoint
- [x] Connect dashboard UI controls to full API flow

### In Progress
- [ ] Classroom-ready validation with real student camera samples
- [ ] Attendance report export (CSV)

### To Do
- [ ] Add session close button and auto-refresh timers
- [ ] Add attendance filter by date/session
- [ ] Add student edit/delete flow
- [ ] Add downloadable attendance report
- [ ] Add stronger liveness (blink/head-pose model)
- [ ] Add test suite for anti-fake logic

## Backlog

- [ ] Device fingerprint risk scoring
- [ ] Mobile PWA mode for student attendance
- [ ] Cloud deployment and managed DB
- [ ] Alerting for suspicious attendance attempts

## Work Breakdown (Epics -> Stories)

1. Epic: Core Platform
- Story: Student master data management
- Story: Session lifecycle and QR token management
- Story: Single-page dashboard workflow

2. Epic: Attendance Engine
- Story: Camera capture and liveness validation
- Story: QR scan and token verification
- Story: Duplicate and replay prevention

3. Epic: Insights and Operations
- Story: Attendance reports and exports
- Story: Suspicious-attempt monitoring
- Story: Session-level analytics

## Immediate Next 5 Tasks

1. Add attendance report CSV download endpoint.
2. Add automatic session expiry countdown in dashboard.
3. Add suspicious-attempt audit table and logs.
4. Improve camera guidance UI for better liveness capture.
5. Add tests for duplicate, replay, and expired QR cases.
