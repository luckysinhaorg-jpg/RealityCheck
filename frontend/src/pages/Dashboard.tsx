import React, { useEffect, useState } from 'react';
import type { FeasibilityResult, SchedulerResult, Task } from '../api/types';
import { restClient } from '../api/restClient';
import {
  AlertTriangle,
  Calendar,
  CheckCircle,
  Clock,
  Flame,
  Plus,
  RefreshCw,
  TrendingDown,
} from 'lucide-react';

interface DashboardProps {
  tasks: Task[];
  onOpenCreate: () => void;
  onNavigateToRecovery: () => void;
}

export const Dashboard: React.FC<DashboardProps> = ({
  tasks,
  onOpenCreate,
  onNavigateToRecovery,
}) => {
  const [schedulerResult, setSchedulerResult] = useState<SchedulerResult | null>(null);
  const [p1Feasibility, setP1Feasibility] = useState<FeasibilityResult | null>(null);
  const [lostHours, setLostHours] = useState<number>(0);
  const [loading, setLoading] = useState<boolean>(true);

  // Highest priority active task
  const p1Task = tasks
    .filter((t) => t.status !== 'done')
    .sort((a, b) => a.priority - b.priority)[0];

  const fetchPlan = async (lost: number) => {
    setLoading(true);
    try {
      const plan = await restClient.generateDailyPlan(7, lost);
      setSchedulerResult(plan);

      if (p1Task) {
        const feas = await restClient.getFeasibility(p1Task.id, lost);
        setP1Feasibility(feas);
      }
    } catch (err) {
      console.error('Error fetching plan:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchPlan(lostHours);
  }, [tasks, lostHours]);

  const totalRemainingHours = tasks
    .filter((t) => t.status !== 'done')
    .reduce((acc, t) => acc + t.remaining_hours, 0);

  return (
    <div>
      {/* Top banner / action bar */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: '1.5rem',
          flexWrap: 'wrap',
          gap: '1rem',
        }}
      >
        <div>
          <h1 style={{ fontSize: '1.75rem', fontWeight: 700, color: '#fff' }}>
            Deadline-Recovery Dashboard
          </h1>
          <p style={{ color: '#94a3b8', fontSize: '0.9rem' }}>
            Know what matters, know how much time it really needs, and know what must change.
          </p>
        </div>

        <div style={{ display: 'flex', gap: '0.75rem' }}>
          <button className="btn btn-outline" onClick={() => fetchPlan(lostHours)}>
            <RefreshCw size={16} className={loading ? 'animate-spin' : ''} />
            Recalculate
          </button>
          <button className="btn btn-primary" onClick={onOpenCreate}>
            <Plus size={16} />
            New Task
          </button>
        </div>
      </div>

      {/* Metrics Row */}
      <div className="grid-3" style={{ marginBottom: '1.5rem' }}>
        {/* Metric 1: Priority 1 Focus */}
        <div className="card" style={{ borderLeft: '4px solid #ef4444' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ fontSize: '0.85rem', color: '#94a3b8', fontWeight: 600 }}>
              PRIORITY 1 TASK
            </span>
            <Flame size={18} color="#ef4444" />
          </div>
          {p1Task ? (
            <div style={{ marginTop: '0.75rem' }}>
              <div style={{ fontSize: '1.1rem', fontWeight: 700, color: '#fff' }}>
                {p1Task.title}
              </div>
              <div style={{ display: 'flex', gap: '0.5rem', marginTop: '0.5rem', alignItems: 'center' }}>
                <span className="badge-p1">P1</span>
                <span style={{ fontSize: '0.8rem', color: '#cbd5e1' }}>
                  {p1Task.remaining_hours}h left
                </span>
                <span style={{ fontSize: '0.8rem', color: '#94a3b8' }}>•</span>
                <span
                  style={{
                    fontSize: '0.8rem',
                    fontWeight: 600,
                    color: p1Feasibility?.feasible ? '#34d399' : '#f87171',
                  }}
                >
                  {p1Feasibility?.feasible ? '✓ Feasible' : '⚠ Infeasible!'}
                </span>
              </div>
            </div>
          ) : (
            <div style={{ marginTop: '0.75rem', color: '#94a3b8', fontSize: '0.9rem' }}>
              No active Priority 1 tasks.
            </div>
          )}
        </div>

        {/* Metric 2: Portfolio Workload */}
        <div className="card" style={{ borderLeft: '4px solid #6366f1' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ fontSize: '0.85rem', color: '#94a3b8', fontWeight: 600 }}>
              ACTIVE PORTFOLIO
            </span>
            <Clock size={18} color="#6366f1" />
          </div>
          <div style={{ marginTop: '0.75rem' }}>
            <div style={{ fontSize: '1.75rem', fontWeight: 700, color: '#fff' }}>
              {totalRemainingHours.toFixed(1)} <span style={{ fontSize: '1rem', color: '#94a3b8' }}>hrs</span>
            </div>
            <div style={{ fontSize: '0.8rem', color: '#94a3b8', marginTop: '0.25rem' }}>
              Across {tasks.filter((t) => t.status !== 'done').length} active tasks
            </div>
          </div>
        </div>

        {/* Metric 3: Lost Hours Simulator */}
        <div className="card" style={{ borderLeft: '4px solid #f59e0b' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ fontSize: '0.85rem', color: '#94a3b8', fontWeight: 600 }}>
              LOST HOURS SIMULATOR
            </span>
            <TrendingDown size={18} color="#f59e0b" />
          </div>
          <div style={{ marginTop: '0.75rem' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
              <input
                type="range"
                min="0"
                max="8"
                step="0.5"
                value={lostHours}
                onChange={(e) => setLostHours(parseFloat(e.target.value))}
                style={{ flex: 1 }}
              />
              <span
                style={{
                  fontFamily: 'monospace',
                  fontWeight: 700,
                  fontSize: '1.1rem',
                  color: lostHours > 0 ? '#f59e0b' : '#94a3b8',
                  minWidth: '40px',
                }}
              >
                {lostHours}h
              </span>
            </div>
            <div style={{ fontSize: '0.75rem', color: '#94a3b8', marginTop: '0.5rem' }}>
              {lostHours > 0
                ? 'Plan dynamically adjusts availability and tests feasibility.'
                : 'Slide to simulate losing working hours today.'}
            </div>
          </div>
        </div>
      </div>

      {/* Infeasibility alert banner */}
      {p1Feasibility && !p1Feasibility.feasible && (
        <div
          style={{
            padding: '1rem 1.25rem',
            backgroundColor: 'rgba(239, 68, 68, 0.15)',
            border: '1px solid rgba(239, 68, 68, 0.4)',
            borderRadius: '10px',
            marginBottom: '1.5rem',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            flexWrap: 'wrap',
            gap: '1rem',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
            <AlertTriangle size={24} color="#f87171" />
            <div>
              <div style={{ fontWeight: 700, color: '#f87171' }}>
                Schedule Alert: {p1Task?.title} cannot finish on time!
              </div>
              <div style={{ fontSize: '0.85rem', color: '#cbd5e1' }}>
                Shortfall of {p1Feasibility.shortfall_hours?.toFixed(1)} hours before deadline.
              </div>
            </div>
          </div>
          <button className="btn btn-danger" onClick={onNavigateToRecovery}>
            Open Recovery Center
          </button>
        </div>
      )}

      {/* Timetable View (Folded into Dashboard per Day 5 Cut Rule) */}
      <div className="card">
        <div className="card-header">
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <Calendar size={18} color="#38bdf8" />
            <h2 className="card-title">Day/Week Deterministic Timetable</h2>
          </div>
          <span style={{ fontSize: '0.8rem', color: '#94a3b8' }}>
            Deterministic pure-Python portfolio placement
          </span>
        </div>

        {schedulerResult?.unscheduled_work && schedulerResult.unscheduled_work.length > 0 && (
          <div
            style={{
              padding: '0.75rem 1rem',
              borderRadius: '8px',
              backgroundColor: 'rgba(245, 158, 11, 0.1)',
              border: '1px solid rgba(245, 158, 11, 0.3)',
              marginBottom: '1rem',
              fontSize: '0.85rem',
              color: '#fbbf24',
            }}
          >
            <strong>Unscheduled Work:</strong>
            <ul style={{ paddingLeft: '1.25rem', marginTop: '0.25rem' }}>
              {schedulerResult.unscheduled_work.map((uw, idx) => (
                <li key={idx}>
                  {uw.task_title} ({uw.remaining_hours}h) — {uw.reason}
                </li>
              ))}
            </ul>
          </div>
        )}

        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
          {schedulerResult?.plan.map((day) => {
            const dateStr = new Date(day.date).toLocaleDateString(undefined, {
              weekday: 'short',
              month: 'short',
              day: 'numeric',
            });
            return (
              <div
                key={day.date}
                style={{
                  background: '#0f172a',
                  border: '1px solid #1e293b',
                  borderRadius: '8px',
                  padding: '0.85rem 1.25rem',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '1.5rem',
                  flexWrap: 'wrap',
                }}
              >
                <div style={{ minWidth: '120px' }}>
                  <div style={{ fontWeight: 600, color: '#fff' }}>{dateStr}</div>
                  <div style={{ fontSize: '0.75rem', color: '#64748b' }}>
                    {day.scheduled_hours.toFixed(1)}h / {day.usable_hours.toFixed(1)}h max
                  </div>
                </div>

                <div style={{ flex: 1, display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
                  {day.sessions.length > 0 ? (
                    day.sessions.map((sess, idx) => (
                      <div
                        key={idx}
                        style={{
                          background:
                            sess.priority === 1
                              ? 'rgba(239, 68, 68, 0.2)'
                              : sess.priority === 2
                              ? 'rgba(245, 158, 11, 0.2)'
                              : 'rgba(99, 102, 241, 0.2)',
                          border: `1px solid ${
                            sess.priority === 1
                              ? 'rgba(239, 68, 68, 0.4)'
                              : sess.priority === 2
                              ? 'rgba(245, 158, 11, 0.4)'
                              : 'rgba(99, 102, 241, 0.4)'
                          }`,
                          padding: '0.35rem 0.65rem',
                          borderRadius: '6px',
                          fontSize: '0.8rem',
                          color: '#fff',
                          display: 'flex',
                          alignItems: 'center',
                          gap: '0.4rem',
                        }}
                      >
                        <span
                          style={{
                            fontWeight: 700,
                            color:
                              sess.priority === 1
                                ? '#f87171'
                                : sess.priority === 2
                                ? '#fbbf24'
                                : '#a5b4fc',
                          }}
                        >
                          P{sess.priority}
                        </span>
                        <span>{sess.task_title}</span>
                        <span style={{ color: '#94a3b8', fontSize: '0.75rem' }}>
                          ({sess.duration_hours.toFixed(1)}h)
                        </span>
                      </div>
                    ))
                  ) : (
                    <span style={{ fontSize: '0.8rem', color: '#64748b', fontStyle: 'italic' }}>
                      No sessions scheduled (free / off-day)
                    </span>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};
