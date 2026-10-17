"""
Tests for FeasibilityService and SchedulerService covering all 10 required scenarios.

Time reference: all tests that use a fixed 'now' also pass it to make_task so that
deadlines are computed relative to the same reference point, not real wall-clock time.

Capacity arithmetic (default_settings, buffer=10%, Mon-Fri 8h, 15min break per 2h):
  - gross/day = 8h
  - breaks/day = floor(8/2) × 0.25h = 4 × 0.25 = 1h
  - net/day    = 7h
  - buffered   = 7 × 0.9 = 6.3h
  Mon-Fri (5d) = 31.5h   Sat = 4×0.9-breaks ≈ 3.15h   Sun = 0h
"""
from __future__ import annotations

import pytest
from datetime import datetime, timedelta, timezone

from sqlmodel import Session, select

from app.models.task import Task, TaskStatus, UserSettings
from app.services.feasibility import FeasibilityService
from app.services.scheduler import SchedulerService
from app.services.recovery import RecoveryService
from app.services.estimator import EstimatorService
from app.schemas.task import TaskCreate, TaskUpdate
from app.services.task_service import TaskService
from tests.conftest import make_task

# Pinned Monday reference (2026-10-19 is a Monday, verified in test_availability.py)
_NOW = datetime(2026, 10, 19, 9, 0, tzinfo=timezone.utc)


# ──────────────────────────────────────────────────────────────────────────────
# Scenario 1: Everything fits
# ──────────────────────────────────────────────────────────────────────────────

def test_scenario_1_everything_fits(session, default_settings):
    """P1 task with 8 h remaining — 14-day window has >60 h usable. Feasible."""
    task = make_task(session, title="Exam Prep", priority=1,
                     estimated_hours=8, days_until_deadline=14, now=_NOW)

    svc = FeasibilityService(session)
    result = svc.analyse_p1_feasibility(task, default_settings, now=_NOW)
    assert result.feasible is True
    assert result.shortfall_hours is None
    assert "FEASIBLE" in result.explanation


# ──────────────────────────────────────────────────────────────────────────────
# Scenario 2: P1 feasible only if other tasks move
# ──────────────────────────────────────────────────────────────────────────────

def test_scenario_2_p1_feasible_if_others_move(session, default_settings):
    """
    7-day window (Mon-Sun): 5×6.3 + Sat3.15 = 34.65 h usable.
    P1 needs 22 h. Two P3 tasks need 8 h each = 16 h.
    Total needed = 38 h > 34.65 h → some lower-priority work cannot fit.
    P1 gets scheduled first (priority ordering); at least one P3 is displaced.
    """
    now = _NOW  # Monday 09:00 UTC
    p1 = make_task(session, title="Report", priority=1,
                   estimated_hours=22, days_until_deadline=7, now=now)
    p3a = make_task(session, title="Email", priority=3, estimated_hours=8,
                    days_until_deadline=7, now=now)
    p3b = make_task(session, title="Reading", priority=3, estimated_hours=8,
                    days_until_deadline=7, now=now)

    sched = SchedulerService(session, default_settings, [p1, p3a, p3b],
                             now=now, days_ahead=7)
    result = sched.generate()

    # P1 must be fully scheduled (has highest priority)
    assert p1.id in result.scheduled_task_ids, \
        f"P1 not scheduled. Unscheduled: {result.unscheduled_tasks}"
    # At least one lower-priority task is unscheduled
    assert len(result.unscheduled_tasks) >= 1, \
        "Expected at least one P3 to be unscheduled"


# ──────────────────────────────────────────────────────────────────────────────
# Scenario 3: P1 is impossible
# ──────────────────────────────────────────────────────────────────────────────

def test_scenario_3_p1_impossible(session, default_settings):
    """P1 needs 200 h in 2 days (~12.6 h usable) — mathematically impossible."""
    task = make_task(session, title="Giant Project", priority=1,
                     estimated_hours=200, days_until_deadline=2, now=_NOW)

    svc = FeasibilityService(session)
    result = svc.analyse_p1_feasibility(task, default_settings, now=_NOW)
    assert result.feasible is False
    assert result.shortfall_hours is not None
    assert result.shortfall_hours > 0
    assert "INFEASIBLE" in result.explanation


# ──────────────────────────────────────────────────────────────────────────────
# Scenario 4: Two conflicting P1 deadlines
# ──────────────────────────────────────────────────────────────────────────────

def test_scenario_4_two_conflicting_p1(session, default_settings):
    """
    3-day window (Mon-Wed): 3×6.3 = 18.9 h.
    Two P1 tasks each needing 15 h = 30 h total. At least one must fail.
    """
    now = _NOW
    p1a = make_task(session, title="Thesis", priority=1,
                    estimated_hours=15, days_until_deadline=3, now=now)
    p1b = make_task(session, title="Client Work", priority=1,
                    estimated_hours=15, days_until_deadline=3, now=now)

    sched = SchedulerService(session, default_settings, [p1a, p1b],
                             now=now, days_ahead=3)
    result = sched.generate()

    # At least one P1 unscheduled, or schedule is infeasible
    assert len(result.unscheduled_tasks) >= 1 or not result.feasible


# ──────────────────────────────────────────────────────────────────────────────
# Scenario 5: Task overruns its estimate
# ──────────────────────────────────────────────────────────────────────────────

def test_scenario_5_task_overruns(session, default_settings):
    """Record 3 completions at 1.5× estimate. Ratio adjusts after MIN_SAMPLES."""
    svc = EstimatorService(session)

    for i in range(3):
        t = make_task(session, title=f"Writing {i}", category="writing",
                      estimated_hours=4.0, days_until_deadline=60, now=_NOW)
        svc.record_completion(t.id, actual_hours=6.0)   # 1.5× overrun

    ratio_info = svc.category_ratio("writing")
    assert ratio_info["adjustment_active"] is True
    assert ratio_info["ratio"] == pytest.approx(1.5)
    assert ratio_info["samples"] == 3


# ──────────────────────────────────────────────────────────────────────────────
# Scenario 6: Lost working hours
# ──────────────────────────────────────────────────────────────────────────────

def test_scenario_6_lost_hours(session, default_settings):
    """
    1-day window (Monday 09:00–17:00 UTC):
      net available after breaks = 7h, after 10% buffer = 6.3h.
    Task needs 6.0 h → feasible without loss.
    After losing 4 h today: 6.3 - 4 = 2.3 h → infeasible.
    """
    now = _NOW  # Monday 09:00 UTC
    task = make_task(session, title="Tight Task", priority=1,
                     estimated_hours=6.0, days_until_deadline=1, now=now)

    svc = FeasibilityService(session)
    r_no_loss = svc.analyse_p1_feasibility(task, default_settings, now=now,
                                           lost_hours_today=0)
    r_with_loss = svc.analyse_p1_feasibility(task, default_settings, now=now,
                                             lost_hours_today=4.0)

    assert r_no_loss.feasible is True, \
        f"Expected feasible without loss. Got: {r_no_loss.explanation}"
    assert r_with_loss.feasible is False, \
        f"Expected infeasible with 4h loss. Got: {r_with_loss.explanation}"


# ──────────────────────────────────────────────────────────────────────────────
# Scenario 7: Unfinished dependency
# ──────────────────────────────────────────────────────────────────────────────

def test_scenario_7_unfinished_dependency(session, default_settings):
    """P1 depends on a task whose deadline is AFTER P1's deadline → blocked."""
    # Dep deadline: 10 days out; P1 deadline: 5 days out
    dep = make_task(session, title="Prereq", priority=2,
                    estimated_hours=5, days_until_deadline=10, now=_NOW)

    p1_deadline = (_NOW + timedelta(days=5)).isoformat()
    tsvc = TaskService(session)
    p1 = tsvc.create_task(TaskCreate(
        title="Main Work",
        priority=1,
        deadline=p1_deadline,
        estimated_hours=4,
        depends_on=[dep.id],
    ))

    svc = FeasibilityService(session)
    result = svc.analyse_p1_feasibility(p1, default_settings, now=_NOW)
    assert result.feasible is False
    assert "Prereq" in result.blocking_tasks


# ──────────────────────────────────────────────────────────────────────────────
# Scenario 8: New urgent task displaces lower-priority work
# ──────────────────────────────────────────────────────────────────────────────

def test_scenario_8_new_urgent_task(session, default_settings):
    """
    3-day window: ~18.9 h.
    Low-priority task: 10 h. Then a P1 urgent task arrives needing 15 h.
    P1 gets scheduled first (25 h total > 18.9 h capacity).
    """
    now = _NOW
    low = make_task(session, title="Nice to have", priority=4,
                    estimated_hours=10, days_until_deadline=3, now=now)
    urgent = make_task(session, title="Urgent P1", priority=1,
                       estimated_hours=15, days_until_deadline=3, now=now)

    sched = SchedulerService(session, default_settings, [low, urgent],
                             now=now, days_ahead=3)
    result = sched.generate()

    # P1 must be scheduled
    assert urgent.id in result.scheduled_task_ids, \
        f"Urgent P1 not scheduled. Unscheduled: {result.unscheduled_tasks}"
    # Low-priority should be displaced (total > capacity)
    assert low.id not in result.scheduled_task_ids or len(result.unscheduled_tasks) >= 1


# ──────────────────────────────────────────────────────────────────────────────
# Scenario 9: Rejected recovery plan causes NO changes
# ──────────────────────────────────────────────────────────────────────────────

def test_scenario_9_rejected_proposal_no_changes(session, default_settings):
    """
    Rejecting a recovery proposal must not modify ANY task or DB record.
    Verified by snapshotting all task states before and after.
    """
    task = make_task(session, title="Infeasible", priority=1,
                     estimated_hours=200, days_until_deadline=1, now=_NOW)

    # Snapshot before
    all_before = {t.id: (t.status, t.deadline, t.remaining_hours)
                  for t in session.exec(select(Task)).all()}

    svc_f = FeasibilityService(session)
    feasibility = svc_f.analyse_p1_feasibility(task, default_settings, now=_NOW)

    svc_r = RecoveryService(session)
    proposal = svc_r.generate_recovery_plan(feasibility, default_settings, now=_NOW)

    resp = svc_r.resolve_proposal(proposal.proposal_id, action="reject")
    assert resp.action == "reject"
    assert resp.tasks_modified == []

    # Verify snapshot unchanged
    session.expire_all()
    all_after = {t.id: (t.status, t.deadline, t.remaining_hours)
                 for t in session.exec(select(Task)).all()}
    assert all_before == all_after, "Rejected proposal must not change any task"


# ──────────────────────────────────────────────────────────────────────────────
# Scenario 10: Changed availability triggers recalculation
# ──────────────────────────────────────────────────────────────────────────────

def test_scenario_10_changed_availability(session, default_settings):
    """
    1-day window (Monday):
      Default: 6.3 h available → task needing 6.0 h is feasible.
      Reduced to 2 h/day: 2 × 0.9 - 0 breaks = 1.8 h → infeasible.
    """
    task = make_task(session, title="Sensitive Task", priority=1,
                     estimated_hours=6.0, days_until_deadline=1, now=_NOW)

    svc = FeasibilityService(session)

    # Default settings: feasible
    r_default = svc.analyse_p1_feasibility(task, default_settings, now=_NOW)
    assert r_default.feasible is True, \
        f"Expected feasible with default settings. {r_default.explanation}"

    # Reduced availability: 2 h/day, no breaks (break_after_hours=0 means no breaks)
    reduced = UserSettings(id=99, buffer_fraction=0.0,
                           break_duration_minutes=0, break_after_hours=0.0)
    reduced.daily_hours = {"0": 2, "1": 2, "2": 2, "3": 2, "4": 2, "5": 0, "6": 0}
    r_reduced = svc.analyse_p1_feasibility(task, reduced, now=_NOW)
    assert r_reduced.feasible is False, \
        f"Expected infeasible with reduced availability. {r_reduced.explanation}"


# ──────────────────────────────────────────────────────────────────────────────
# Additional constraint tests
# ──────────────────────────────────────────────────────────────────────────────

def test_no_overlapping_sessions(session, default_settings):
    """Scheduler must not produce overlapping sessions on the same day."""
    tasks = [
        make_task(session, title=f"T{i}", priority=2,
                  estimated_hours=1.5, days_until_deadline=5, now=_NOW)
        for i in range(5)
    ]
    sched = SchedulerService(session, default_settings, tasks,
                             now=_NOW, days_ahead=5)
    result = sched.generate()

    for day_plan in result.plan:
        sessions_sorted = sorted(day_plan.sessions, key=lambda s: s.start_time)
        for i in range(len(sessions_sorted) - 1):
            a, b = sessions_sorted[i], sessions_sorted[i + 1]
            assert a.end_time <= b.start_time, (
                f"Overlap on {day_plan.date}: '{a.task_title}' ends {a.end_time} "
                f"but '{b.task_title}' starts {b.start_time}"
            )


def test_no_scheduling_before_earliest_start(session, default_settings):
    """Task with earliest_start must not be scheduled before it."""
    earliest_dt = _NOW + timedelta(days=3)
    earliest = earliest_dt.isoformat()

    tsvc = TaskService(session)
    task = tsvc.create_task(TaskCreate(
        title="Late Start",
        priority=2,
        deadline=(_NOW + timedelta(days=7)).isoformat(),
        estimated_hours=4,
        earliest_start=earliest,
    ))

    sched = SchedulerService(session, default_settings, [task],
                             now=_NOW, days_ahead=7)
    result = sched.generate()

    earliest_date = earliest_dt.date()
    for day_plan in result.plan:
        from datetime import date
        day = date.fromisoformat(day_plan.date)
        for s in day_plan.sessions:
            if s.task_id == task.id:
                assert day >= earliest_date, \
                    f"Session for '{task.title}' placed on {day}, before earliest_start {earliest_date}"


def test_duration_adjustment_threshold(session):
    """Category ratio NOT applied until 3+ completions; applied from 3 onward."""
    svc = EstimatorService(session)

    # 2 completions — no adjustment yet
    for i in range(2):
        t = make_task(session, title=f"Design {i}", category="design",
                      estimated_hours=4.0, days_until_deadline=60, now=_NOW)
        svc.record_completion(t.id, actual_hours=8.0)

    info = svc.category_ratio("design")
    assert info["adjustment_active"] is False
    assert info["ratio"] == pytest.approx(1.0)  # returns 1.0 when inactive

    # 3rd completion — threshold crossed
    t3 = make_task(session, title="Design 2", category="design",
                   estimated_hours=4.0, days_until_deadline=60, now=_NOW)
    svc.record_completion(t3.id, actual_hours=8.0)

    info2 = svc.category_ratio("design")
    assert info2["adjustment_active"] is True
    assert info2["ratio"] == pytest.approx(2.0)
    assert "2.00x" in info2["explanation"]


def test_task_duplicate_prevention(session):
    """Creating the same title+deadline twice must raise DuplicateTaskError."""
    from app.services.task_service import DuplicateTaskError
    tsvc = TaskService(session)
    deadline = (_NOW + timedelta(days=5)).isoformat()
    tsvc.create_task(TaskCreate(title="Unique Task", deadline=deadline, estimated_hours=3))

    with pytest.raises(DuplicateTaskError):
        tsvc.create_task(TaskCreate(title="Unique Task", deadline=deadline, estimated_hours=3))


def test_invalid_dependency_raises(session):
    """Depending on a non-existent task ID must raise InvalidDependencyError."""
    from app.services.task_service import InvalidDependencyError
    tsvc = TaskService(session)
    deadline = (_NOW + timedelta(days=5)).isoformat()
    with pytest.raises(InvalidDependencyError):
        tsvc.create_task(TaskCreate(
            title="Bad Dep",
            deadline=deadline,
            estimated_hours=2,
            depends_on=["non-existent-uuid-here"],
        ))


def test_recovery_accept_defers_tasks(session, default_settings):
    """Accepting a defer option marks affected lower-priority tasks as DEFERRED."""
    p1 = make_task(session, title="P1 Task", priority=1,
                   estimated_hours=100, days_until_deadline=2, now=_NOW)
    # Lower-priority tasks that can be freed
    for i in range(2):
        make_task(session, title=f"Low {i}", priority=4,
                  estimated_hours=8, days_until_deadline=2, now=_NOW)

    svc_f = FeasibilityService(session)
    feasibility = svc_f.analyse_p1_feasibility(p1, default_settings, now=_NOW)
    assert feasibility.feasible is False  # prerequisite

    svc_r = RecoveryService(session)
    proposal = svc_r.generate_recovery_plan(feasibility, default_settings, now=_NOW)
    assert len(proposal.options) >= 2

    # Find the defer option (option_index == 0) — only accept if it has affected tasks
    option_0 = proposal.options[0]
    if option_0.affected_tasks:
        resp = svc_r.resolve_proposal(proposal.proposal_id, action="accept", option_index=0)
        assert resp.action == "accept"
        assert len(resp.tasks_modified) >= 1

        session.expire_all()
        deferred = list(session.exec(
            select(Task).where(Task.status == TaskStatus.DEFERRED)
        ).all())
        assert len(deferred) >= 1, "Accept should have deferred at least one task"
    else:
        # Option 0 is extend-hours (no lower-prio tasks exist) — accept option 1
        resp = svc_r.resolve_proposal(proposal.proposal_id, action="accept", option_index=1)
        assert resp.action == "accept"


def test_already_resolved_proposal_no_op(session, default_settings):
    """Attempting to resolve an already-rejected proposal returns a no-op message."""
    task = make_task(session, title="Impossible", priority=1,
                     estimated_hours=999, days_until_deadline=1, now=_NOW)

    svc_f = FeasibilityService(session)
    feasibility = svc_f.analyse_p1_feasibility(task, default_settings, now=_NOW)
    svc_r = RecoveryService(session)
    proposal = svc_r.generate_recovery_plan(feasibility, default_settings, now=_NOW)

    # First resolution: reject
    svc_r.resolve_proposal(proposal.proposal_id, "reject")

    # Second resolution: should be a no-op, not raise
    resp2 = svc_r.resolve_proposal(proposal.proposal_id, "accept", 0)
    assert "already" in resp2.message.lower()
    assert resp2.tasks_modified == []


def test_fixed_breaks_reduce_availability(session):
    """Break calculation: 15 min per 2h applied correctly over 8h gross."""
    from app.services.availability import AvailabilityCalculator
    from datetime import date

    settings = UserSettings(id=1, buffer_fraction=0.0,
                            break_duration_minutes=15, break_after_hours=2.0)
    settings.daily_hours = {"0": 8, "1": 8, "2": 8, "3": 8, "4": 8, "5": 0, "6": 0}

    monday = date(2026, 10, 19)
    calc = AvailabilityCalculator(settings, monday, monday)
    days = calc.compute()

    # 8h gross, floor(8/2) = 4 breaks × 0.25h = 1h breaks, net = 7h
    assert days[0].break_hours == pytest.approx(1.0)
    assert days[0].available_hours == pytest.approx(7.0)


def test_deadline_in_past_infeasible(session, default_settings):
    """A task whose deadline has already passed must be infeasible."""
    tsvc = TaskService(session)
    past_deadline = (_NOW - timedelta(days=1)).isoformat()
    task = tsvc.create_task(TaskCreate(
        title="Late Task",
        deadline=past_deadline,
        estimated_hours=2,
    ))
    svc = FeasibilityService(session)
    result = svc.analyse_p1_feasibility(task, default_settings, now=_NOW)
    assert result.feasible is False
