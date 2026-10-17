import React, { useState } from 'react';
import type { RecoveryProposal, RecoveryResolutionResult, Task } from '../api/types';
import { restClient } from '../api/restClient';
import {
  AlertTriangle,
  ArrowRight,
  Check,
  CheckCircle,
  HelpCircle,
  RotateCcw,
  ShieldAlert,
  X,
} from 'lucide-react';

interface RecoveryCenterProps {
  tasks: Task[];
  onRefreshTasks: () => void;
}

export const RecoveryCenter: React.FC<RecoveryCenterProps> = ({
  tasks,
  onRefreshTasks,
}) => {
  const [selectedTaskId, setSelectedTaskId] = useState<string>(
    tasks.find((t) => t.priority === 1)?.id || tasks[0]?.id || ''
  );
  const [lostHours, setLostHours] = useState<number>(2.0);
  const [proposal, setProposal] = useState<RecoveryProposal | null>(null);
  const [resolution, setResolution] = useState<RecoveryResolutionResult | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [selectedOptionIdx, setSelectedOptionIdx] = useState<number>(0);

  const activeTasks = tasks.filter((t) => t.status !== 'done');

  const handleGenerateRecovery = async () => {
    if (!selectedTaskId) return;
    setLoading(true);
    setResolution(null);
    try {
      const prop = await restClient.generateRecoveryPlan(selectedTaskId, lostHours);
      setProposal(prop);
      setSelectedOptionIdx(0);
    } catch (err: any) {
      alert(`Error generating recovery plan: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  const handleResolve = async (action: 'accept' | 'reject') => {
    if (!proposal) return;
    setLoading(true);
    try {
      const res = await restClient.resolveRecoveryProposal(
        proposal.proposal_id,
        action,
        selectedOptionIdx
      );
      setResolution(res);
      setProposal((prev) => (prev ? { ...prev, status: action === 'accept' ? 'accepted' : 'rejected' } : null));
      onRefreshTasks();
    } catch (err: any) {
      alert(`Error resolving recovery proposal: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <div style={{ marginBottom: '1.5rem' }}>
        <h1 style={{ fontSize: '1.75rem', fontWeight: 700, color: '#fff' }}>
          Recovery Center
        </h1>
        <p style={{ color: '#94a3b8', fontSize: '0.9rem' }}>
          When schedules break or time is lost, RealityCheck generates multi-option recovery proposals
          with explicit trade-offs. Nothing changes in your database without explicit approval.
        </p>
      </div>

      {/* Generator Controls */}
      <div
        className="card"
        style={{
          padding: '1.25rem',
          display: 'flex',
          gap: '1.5rem',
          alignItems: 'center',
          flexWrap: 'wrap',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <label style={{ fontSize: '0.85rem', color: '#94a3b8', fontWeight: 600 }}>
            Target Task:
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
              minWidth: '260px',
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
            Lost Hours to Recover:
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

        <button className="btn btn-primary" onClick={handleGenerateRecovery} disabled={loading}>
          <ShieldAlert size={16} />
          {loading ? 'Evaluating...' : 'Generate Recovery Options'}
        </button>
      </div>

      {/* Resolution Feedback Alert */}
      {resolution && (
        <div
          style={{
            padding: '1rem',
            borderRadius: '8px',
            backgroundColor:
              resolution.action === 'accept'
                ? 'rgba(16, 185, 129, 0.15)'
                : 'rgba(148, 163, 184, 0.15)',
            border: `1px solid ${
              resolution.action === 'accept' ? 'rgba(16, 185, 129, 0.4)' : 'rgba(148, 163, 184, 0.4)'
            }`,
            color: resolution.action === 'accept' ? '#34d399' : '#cbd5e1',
            marginBottom: '1.5rem',
          }}
        >
          <strong>Proposal Resolved:</strong> {resolution.message}
          {resolution.tasks_modified.length > 0 && (
            <div style={{ fontSize: '0.85rem', marginTop: '0.35rem', color: '#fff' }}>
              Modified tasks: {resolution.tasks_modified.join(', ')}
            </div>
          )}
          {resolution.action === 'reject' && (
            <div style={{ fontSize: '0.85rem', marginTop: '0.35rem', color: '#94a3b8' }}>
              Confirmed: Proposal rejected. Zero database tasks were altered.
            </div>
          )}
        </div>
      )}

      {/* Proposal Cards */}
      {proposal && (
        <div>
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              marginBottom: '1rem',
            }}
          >
            <h2 style={{ fontSize: '1.25rem', fontWeight: 700, color: '#fff' }}>
              Proposal ID: <span style={{ fontFamily: 'monospace', color: '#38bdf8' }}>{proposal.proposal_id.slice(0, 8)}...</span>
            </h2>
            <span
              style={{
                fontSize: '0.8rem',
                padding: '0.25rem 0.6rem',
                borderRadius: '6px',
                backgroundColor:
                  proposal.status === 'accepted'
                    ? 'rgba(16, 185, 129, 0.2)'
                    : proposal.status === 'rejected'
                    ? 'rgba(239, 68, 68, 0.2)'
                    : 'rgba(245, 158, 11, 0.2)',
                color:
                  proposal.status === 'accepted'
                    ? '#34d399'
                    : proposal.status === 'rejected'
                    ? '#f87171'
                    : '#fbbf24',
                fontWeight: 600,
              }}
            >
              STATUS: {proposal.status.toUpperCase()}
            </span>
          </div>

          <div className="grid-3" style={{ marginBottom: '1.5rem' }}>
            {proposal.options.map((opt, idx) => (
              <div
                key={idx}
                className="card"
                onClick={() => proposal.status === 'pending' && setSelectedOptionIdx(idx)}
                style={{
                  cursor: proposal.status === 'pending' ? 'pointer' : 'default',
                  border:
                    selectedOptionIdx === idx
                      ? '2px solid #6366f1'
                      : '1px solid var(--border-subtle)',
                  background:
                    selectedOptionIdx === idx
                      ? 'rgba(99, 102, 241, 0.12)'
                      : 'var(--bg-card)',
                  display: 'flex',
                  flexDirection: 'column',
                  justifyContent: 'space-between',
                }}
              >
                <div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <span style={{ fontSize: '0.8rem', fontWeight: 700, color: '#38bdf8' }}>
                      OPTION {idx + 1}
                    </span>
                    <span
                      style={{
                        fontSize: '0.75rem',
                        padding: '0.15rem 0.45rem',
                        borderRadius: '4px',
                        background: '#0f172a',
                        color: '#94a3b8',
                      }}
                    >
                      {opt.type.replace(/_/g, ' ').toUpperCase()}
                    </span>
                  </div>

                  <div style={{ fontWeight: 700, color: '#fff', marginTop: '0.5rem', fontSize: '1rem' }}>
                    {opt.description}
                  </div>

                  <div style={{ fontSize: '0.85rem', color: '#cbd5e1', marginTop: '0.5rem' }}>
                    <strong>Trade-offs:</strong> {opt.trade_offs}
                  </div>

                  {opt.proposed_actions && opt.proposed_actions.length > 0 && (
                    <div style={{ marginTop: '0.75rem', fontSize: '0.8rem', color: '#94a3b8' }}>
                      <strong>Actions:</strong>
                      <ul style={{ paddingLeft: '1.25rem', marginTop: '0.25rem' }}>
                        {opt.proposed_actions.map((act, aIdx) => (
                          <li key={aIdx}>{act}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>

                <div style={{ marginTop: '1rem', paddingTop: '0.75rem', borderTop: '1px solid #334155' }}>
                  <div style={{ fontSize: '0.8rem', color: '#94a3b8' }}>
                    {selectedOptionIdx === idx ? '● Selected for Approval' : '○ Click to select'}
                  </div>
                </div>
              </div>
            ))}
          </div>

          {/* Action Approval Controls */}
          {proposal.status === 'pending' && (
            <div
              className="card"
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                flexWrap: 'wrap',
                gap: '1rem',
                borderLeft: '4px solid #6366f1',
              }}
            >
              <div>
                <div style={{ fontWeight: 700, color: '#fff' }}>
                  Awaiting Explicit User Approval
                </div>
                <div style={{ fontSize: '0.85rem', color: '#94a3b8' }}>
                  Option {selectedOptionIdx + 1} is currently selected. Rejecting will leave all tasks unchanged.
                </div>
              </div>

              <div style={{ display: 'flex', gap: '0.75rem' }}>
                <button
                  className="btn btn-outline"
                  onClick={() => handleResolve('reject')}
                  disabled={loading}
                  style={{ color: '#f87171' }}
                >
                  <X size={16} />
                  Reject (Change Nothing)
                </button>
                <button
                  className="btn btn-success"
                  onClick={() => handleResolve('accept')}
                  disabled={loading}
                >
                  <Check size={16} />
                  Accept Option {selectedOptionIdx + 1}
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
