import React, { useEffect, useState } from 'react';
import type { FeasibilityResult, Task } from '../api/types';
import { restClient } from '../api/restClient';
import {
  AlertCircle,
  Calculator,
  CheckCircle2,
  Clock,
  Flame,
  HelpCircle,
  ShieldCheck,
  XCircle,
} from 'lucide-react';

interface PriorityAnalysisProps {
  tasks: Task[];
}

export const PriorityAnalysis: React.FC<PriorityAnalysisProps> = ({ tasks }) => {
  const [selectedTaskId, setSelectedTaskId] = useState<string>('');
  const [lostHours, setLostHours] = useState<number>(0);
  const [feasibility, setFeasibility] = useState<FeasibilityResult | null>(null);
  const [loading, setLoading] = useState<boolean>(false);

  // Active tasks sorted by priority
  const activeTasks = tasks.filter((t) => t.status !== 'done');

  useEffect(() => {
    if (!selectedTaskId && activeTasks.length > 0) {
      // Default to P1 task if present, else first active
      const p1 = activeTasks.find((t) => t.priority === 1);
      setSelectedTaskId(p1 ? p1.id : activeTasks[0].id);
    }
  }, [tasks]);

  useEffect(() => {
    if (selectedTaskId) {
      setLoading(true);
      restClient
        .getFeasibility(selectedTaskId, lostHours)
        .then((res) => setFeasibility(res))
        .catch((err) => console.error(err))
        .finally(() => setLoading(false));
    }
  }, [selectedTaskId, lostHours]);

  const currentTask = tasks.find((t) => t.id === selectedTaskId);

  return (
    <div>
      <div style={{ marginBottom: '1.5rem' }}>
        <h1 style={{ fontSize: '1.75rem', fontWeight: 700, color: '#fff' }}>
          Priority 1 & Feasibility Engine
        </h1>
        <p style={{ color: '#94a3b8', fontSize: '0.9rem' }}>
          Deterministic mathematical proof of whether your critical work can finish on time.
          Never confuses available calendar time with usable working hours.
        </p>
      </div>

      {/* Selector bar */}
      <div
        className="card"
        style={{
          padding: '1rem',
          display: 'flex',
          gap: '1.5rem',
          alignItems: 'center',
          flexWrap: 'wrap',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <label style={{ fontSize: '0.85rem', color: '#94a3b8', fontWeight: 600 }}>
            Analyze Task:
          </label>
          <select
            value={selectedTaskId}
            onChange={(e) => setSelectedTaskId(e.target.value)}
            style={{
              padding: '0.45rem 0.85rem',
              borderRadius: '6px',
              border: '1px solid #334155',
              background: '#0f172a',
              color: '#fff',
              fontSize: '0.9rem',
              minWidth: '280px',
            }}
          >
            {activeTasks.map((t) => (
              <option key={t.id} value={t.id}>
                [P{t.priority}] {t.title} ({t.remaining_hours}h left)
              </option>
            ))}
          </select>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <label style={{ fontSize: '0.85rem', color: '#94a3b8', fontWeight: 600 }}>
            Lost Hours Today:
          </label>
          <input
            type="number"
            min="0"
            max="12"
            step="0.5"
            value={lostHours}
            onChange={(e) => setLostHours(parseFloat(e.target.value) || 0)}
            style={{
              width: '70px',
              padding: '0.4rem 0.6rem',
              borderRadius: '6px',
              border: '1px solid #334155',
              background: '#0f172a',
              color: '#fff',
              fontSize: '0.9rem',
            }}
          />
        </div>
      </div>

      {feasibility && (
        <>
          {/* Main Verdict Card */}
          <div
            className="card"
            style={{
              borderLeft: `6px solid ${feasibility.feasible ? '#10b981' : '#ef4444'}`,
              background: feasibility.feasible
                ? 'linear-gradient(180deg, rgba(16, 185, 129, 0.08) 0%, #1e293b 100%)'
                : 'linear-gradient(180deg, rgba(239, 68, 68, 0.08) 0%, #1e293b 100%)',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', flexWrap: 'wrap', gap: '1rem' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
                {feasibility.feasible ? (
                  <CheckCircle2 size={36} color="#34d399" />
                ) : (
                  <XCircle size={36} color="#f87171" />
                )}
                <div>
                  <div style={{ fontSize: '1.35rem', fontWeight: 700, color: '#fff' }}>
                    {feasibility.feasible
                      ? 'FEASIBLE: Task can be completed on time'
                      : 'INFEASIBLE: Immediate plan revision required'}
                  </div>
                  <div style={{ fontSize: '0.9rem', color: '#cbd5e1', marginTop: '0.25rem' }}>
                    {feasibility.explanation}
                  </div>
                </div>
              </div>

              <div style={{ textAlign: 'right' }}>
                <div style={{ fontSize: '0.8rem', color: '#94a3b8' }}>
                  {feasibility.feasible ? 'Slack Time Before Deadline' : 'Estimated Shortfall'}
                </div>
                <div
                  style={{
                    fontSize: '1.75rem',
                    fontWeight: 800,
                    color: feasibility.feasible ? '#34d399' : '#f87171',
                  }}
                >
                  {feasibility.feasible
                    ? `+${feasibility.slack_hours?.toFixed(1)} hrs`
                    : `-${feasibility.shortfall_hours?.toFixed(1)} hrs`}
                </div>
              </div>
            </div>
          </div>

          {/* Detailed Calculations Breakdown */}
          <div className="grid-3" style={{ marginBottom: '1.5rem' }}>
            <div className="card">
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.75rem', color: '#38bdf8' }}>
                <Clock size={18} />
                <span style={{ fontWeight: 600, fontSize: '0.9rem' }}>Time Arithmetic</span>
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.6rem', fontSize: '0.875rem' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span style={{ color: '#94a3b8' }}>Work Remaining:</span>
                  <span style={{ fontWeight: 600, color: '#fff' }}>{feasibility.remaining_hours} hrs</span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span style={{ color: '#94a3b8' }}>Calendar Window:</span>
                  <span style={{ color: '#cbd5e1' }}>{feasibility.calendar_hours_before_deadline.toFixed(1)} hrs</span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span style={{ color: '#94a3b8' }}>Usable Working Time:</span>
                  <span style={{ fontWeight: 700, color: '#38bdf8' }}>{feasibility.usable_hours_before_deadline.toFixed(1)} hrs</span>
                </div>
              </div>
            </div>

            <div className="card">
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.75rem', color: '#fbbf24' }}>
                <ShieldCheck size={18} />
                <span style={{ fontWeight: 600, fontSize: '0.9rem' }}>Buffer & Deductions</span>
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.6rem', fontSize: '0.875rem' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span style={{ color: '#94a3b8' }}>Buffer Reserved:</span>
                  <span style={{ color: '#fbbf24' }}>-{feasibility.buffer_hours_deducted.toFixed(1)} hrs</span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span style={{ color: '#94a3b8' }}>Mandatory Breaks:</span>
                  <span style={{ color: '#fbbf24' }}>-{feasibility.break_hours_deducted.toFixed(1)} hrs</span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span style={{ color: '#94a3b8' }}>Lost Working Hours:</span>
                  <span style={{ color: '#f87171' }}>-{feasibility.lost_hours_deducted.toFixed(1)} hrs</span>
                </div>
              </div>
            </div>

            <div className="card">
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.75rem', color: '#a78bfa' }}>
                <Calculator size={18} />
                <span style={{ fontWeight: 600, fontSize: '0.9rem' }}>Session Target</span>
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.6rem', fontSize: '0.875rem' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span style={{ color: '#94a3b8' }}>Required Pace:</span>
                  <span style={{ fontWeight: 700, color: '#fff' }}>{feasibility.required_hours_per_day.toFixed(1)} hrs/day</span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span style={{ color: '#94a3b8' }}>Session Length:</span>
                  <span style={{ color: '#cbd5e1' }}>{feasibility.recommended_session_hours.toFixed(1)} hrs/session</span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span style={{ color: '#94a3b8' }}>Deadline Date:</span>
                  <span style={{ color: '#cbd5e1' }}>
                    {new Date(feasibility.deadline).toLocaleDateString(undefined, {
                      month: 'short',
                      day: 'numeric',
                      hour: '2-digit',
                      minute: '2-digit',
                    })}
                  </span>
                </div>
              </div>
            </div>
          </div>

          {/* Mathematical Proof & Formulas */}
          <div className="card">
            <h3 style={{ fontSize: '1rem', fontWeight: 600, color: '#fff', marginBottom: '0.75rem' }}>
              Formula & Intermediate Deterministic Proof
            </h3>
            <pre className="code-json">
              {JSON.stringify(feasibility.intermediate_values, null, 2)}
            </pre>
          </div>
        </>
      )}
    </div>
  );
};
