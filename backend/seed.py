"""
RealityCheck — Synthetic Seed Data Generator.

Populates realistic portfolio tasks to demonstrate:
1. High-priority deadline approaching ("CS5001 Final Exam Prep" - P1).
2. Tight schedule where lost hours trigger recovery.
3. Conflicting lower-priority tasks that must move ("Q3 Architecture Review" - P3).
4. Dependency chain ("Literature Review" -> "Draft Thesis Chapter").
5. Completed historical tasks for duration estimator demonstration (category "coding" has 3 completions).
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlmodel import Session, select

from app.database import get_engine, init_db
from app.models.task import CompletionLog, Task, TaskStatus, UserSettings
from app.services.task_service import TaskService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("seed")


def seed_database():
    engine = get_engine()
    init_db(engine)

    with Session(engine) as session:
        # 1. Ensure user settings exist
        settings = session.get(UserSettings, 1)
        if not settings:
            settings = UserSettings(
                daily_hours={
                    "monday": 7.0,
                    "tuesday": 7.0,
                    "wednesday": 7.0,
                    "thursday": 7.0,
                    "friday": 6.0,
                    "saturday": 4.0,
                    "sunday": 0.0,
                },
                working_window_start="09:00",
                working_window_end="18:00",
                buffer_fraction=0.10,
                timezone="UTC",
            )
            session.add(settings)
            session.commit()
            logger.info("Initialized default UserSettings.")

        # Clear existing tasks to ensure clean seed
        existing_tasks = list(session.exec(select(Task)).all())
        if existing_tasks:
            for t in existing_tasks:
                session.delete(t)
            session.commit()
            logger.info("Cleared %d existing tasks.", len(existing_tasks))

        existing_logs = list(session.exec(select(CompletionLog)).all())
        for l in existing_logs:
            session.delete(l)
        session.commit()

        now = datetime.now(timezone.utc)

        # 2. Add realistic active tasks
        # Dependency prerequisite
        dep_task = Task(
            id="task-lit-review",
            title="Literature Review & Citation Mapping",
            description="Collect and summarize key papers on scheduling algorithms.",
            category="research",
            priority=2,
            deadline=(now + timedelta(days=4)).isoformat(),
            estimated_hours=6.0,
            actual_hours=0.0,
            remaining_hours=6.0,
            status=TaskStatus.TODO,
            splittable=True,
            confidence=0.9,
        )
        session.add(dep_task)

        # Dependent task
        thesis_task = Task(
            id="task-thesis-draft",
            title="Draft Research Methodology Section",
            description="Write draft section 3 based on literature findings.",
            category="writing",
            priority=2,
            deadline=(now + timedelta(days=8)).isoformat(),
            estimated_hours=10.0,
            actual_hours=0.0,
            remaining_hours=10.0,
            status=TaskStatus.TODO,
            depends_on=["task-lit-review"],
            splittable=True,
            confidence=0.85,
        )
        session.add(thesis_task)

        # Priority 1 centerpiece
        p1_task = Task(
            id="task-exam-prep",
            title="CS5001 Final Exam Preparation",
            description="Comprehensive review of distributed systems and consensus proofs.",
            category="study",
            priority=1,
            deadline=(now + timedelta(days=5)).isoformat(),
            estimated_hours=18.0,
            actual_hours=2.0,
            remaining_hours=16.0,
            status=TaskStatus.IN_PROGRESS,
            splittable=True,
            confidence=0.95,
        )
        session.add(p1_task)

        # Lower priority work (candidates to move during recovery)
        p3_review = Task(
            id="task-arch-review",
            title="Q3 Architecture Review & Tech Debt Audit",
            description="Review microservice boundaries and document deprecations.",
            category="coding",
            priority=3,
            deadline=(now + timedelta(days=6)).isoformat(),
            estimated_hours=8.0,
            actual_hours=0.0,
            remaining_hours=8.0,
            status=TaskStatus.TODO,
            splittable=True,
            confidence=0.8,
        )
        session.add(p3_review)

        p4_backlog = Task(
            id="task-ui-polish",
            title="Update Icon Theme & Dark Mode Polish",
            description="Minor aesthetic tweaks for non-critical views.",
            category="design",
            priority=4,
            deadline=(now + timedelta(days=10)).isoformat(),
            estimated_hours=4.0,
            actual_hours=0.0,
            remaining_hours=4.0,
            status=TaskStatus.TODO,
            splittable=True,
            confidence=0.9,
        )
        session.add(p4_backlog)

        # 3. Add historical completion logs for category "coding" (>= 3 samples for estimator demo)
        hist_1 = CompletionLog(
            task_id="hist-code-1",
            category="coding",
            estimated_hours=4.0,
            actual_hours=5.5,
            completed_at=(now - timedelta(days=12)).isoformat(),
        )
        hist_2 = CompletionLog(
            task_id="hist-code-2",
            category="coding",
            estimated_hours=6.0,
            actual_hours=7.5,
            completed_at=(now - timedelta(days=7)).isoformat(),
        )
        hist_3 = CompletionLog(
            task_id="hist-code-3",
            category="coding",
            estimated_hours=2.0,
            actual_hours=3.0,
            completed_at=(now - timedelta(days=2)).isoformat(),
        )
        session.add_all([hist_1, hist_2, hist_3])

        session.commit()
        logger.info("Successfully seeded RealityCheck with 5 active tasks and 3 historical completion logs.")


if __name__ == "__main__":
    seed_database()
