import React, { useState } from 'react';
import type { Task } from '../api/types';
import { restClient } from '../api/restClient';
import {
  Check,
  CheckCircle2,
  Clock,
  Filter,
  Plus,
  Trash2,
} from 'lucide-react';

interface AllTasksProps {
  tasks: Task[];
  onRefresh: () => void;
  onOpenCreate: () => void;
}

export const AllTasks: React.FC<AllTasksProps> = ({
  tasks,
  onRefresh,
  onOpenCreate,
}) => {
  const [filterPriority, setFilterPriority] = useState<number>(0);
  const [filterStatus, setFilterStatus] = useState<string>('all');
  const [completingTaskId, setCompletingTaskId] = useState<string | null>(null);
  const [actualHoursInput, setActualHoursInput] = useState<number>(4);
  const [completionResult, setCompletionResult] = useState<any | null>(null);

  const filteredTasks = tasks.filter((t) => {
    if (filterPriority > 0 && t.priority !== filterPriority) return false;
    if (filterStatus !== 'all' && t.status !== filterStatus) return false;
    return true;
  });

  const handleDelete = async (id: string) => {
    if (confirm('Are you sure you want to delete this task?')) {
      await restClient.deleteTask(id);
      onRefresh();
    }
  };

  const handleComplete = async (task: Task) => {
    try {
      const res = await restClient.recordCompletion(task.id, actualHoursInput);
      setCompletionResult(res);
      setCompletingTaskId(null);
      onRefresh();
    } catch (err: any) {
      alert(`Error recording completion: ${err.message}`);
    }
  };

  return (
    <div>
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
            All Portfolio Tasks
          </h1>
          <p style={{ color: '#94a3b8', fontSize: '0.9rem' }}>
            Full portfolio inventory with priority levels, deadline countdowns, and duration tracking.
          </p>
        </div>

        <button className="btn btn-primary" onClick={onOpenCreate}>
          <Plus size={16} />
          Create Task
        </button>
      </div>

      {/* Completion announcement banner if duration adjustment updated */}
      {completionResult && (
        <div
          style={{
            padding: '1rem',
            borderRadius: '8px',
            backgroundColor: 'rgba(16, 185, 129, 0.15)',
            border: '1px solid rgba(16, 185, 129, 0.4)',
            color: '#34d399',
            marginBottom: '1.5rem',
          }}
        >
          <strong>Completion Recorded:</strong> {completionResult.task_title} finished in{' '}
          {completionResult.actual_hours}h (estimated: {completionResult.estimated_hours}h).
          <div style={{ fontSize: '0.85rem', color: '#cbd5e1', marginTop: '0.35rem' }}>
            {completionResult.explanation}
          </div>
        </div>
      )}

      {/* Filters */}
      <div
        className="card"
        style={{
          padding: '1rem',
          display: 'flex',
          gap: '1rem',
          alignItems: 'center',
          flexWrap: 'wrap',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: '#94a3b8' }}>
          <Filter size={16} />
          <span style={{ fontSize: '0.85rem', fontWeight: 600 }}>Filters:</span>
        </div>

        <select
          value={filterPriority}
          onChange={(e) => setFilterPriority(parseInt(e.target.value, 10))}
          style={{
            padding: '0.4rem 0.75rem',
            borderRadius: '6px',
            border: '1px solid #334155',
            background: '#0f172a',
            color: '#fff',
            fontSize: '0.85rem',
          }}
        >
          <option value={0}>All Priorities</option>
          <option value={1}>Priority 1 Only</option>
          <option value={2}>Priority 2 Only</option>
          <option value={3}>Priority 3 Only</option>
          <option value={4}>Priority 4 Only</option>
          <option value={5}>Priority 5 Only</option>
        </select>

        <select
          value={filterStatus}
          onChange={(e) => setFilterStatus(e.target.value)}
          style={{
            padding: '0.4rem 0.75rem',
            borderRadius: '6px',
            border: '1px solid #334155',
            background: '#0f172a',
            color: '#fff',
            fontSize: '0.85rem',
          }}
        >
          <option value="all">All Statuses</option>
          <option value="todo">To Do</option>
          <option value="in_progress">In Progress</option>
          <option value="done">Completed (Done)</option>
        </select>
      </div>

      {/* Tasks Table */}
      <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left' }}>
          <thead>
            <tr style={{ background: '#0f172a', borderBottom: '1px solid #334155' }}>
              <th style={{ padding: '0.85rem 1rem', fontSize: '0.8rem', color: '#94a3b8' }}>PRIORITY</th>
              <th style={{ padding: '0.85rem 1rem', fontSize: '0.8rem', color: '#94a3b8' }}>TITLE & CATEGORY</th>
              <th style={{ padding: '0.85rem 1rem', fontSize: '0.8rem', color: '#94a3b8' }}>DEADLINE (UTC)</th>
              <th style={{ padding: '0.85rem 1rem', fontSize: '0.8rem', color: '#94a3b8' }}>REMAINING / EST</th>
              <th style={{ padding: '0.85rem 1rem', fontSize: '0.8rem', color: '#94a3b8' }}>STATUS</th>
              <th style={{ padding: '0.85rem 1rem', fontSize: '0.8rem', color: '#94a3b8', textAlign: 'right' }}>
                ACTIONS
              </th>
            </tr>
          </thead>
          <tbody>
            {filteredTasks.map((t) => {
              const deadlineDate = new Date(t.deadline).toLocaleDateString(undefined, {
                month: 'short',
                day: 'numeric',
                hour: '2-digit',
                minute: '2-digit',
              });

              return (
                <tr key={t.id} style={{ borderBottom: '1px solid #1e293b' }}>
                  <td style={{ padding: '1rem' }}>
                    <span className={`badge-p${t.priority}`}>P{t.priority}</span>
                  </td>

                  <td style={{ padding: '1rem' }}>
                    <div style={{ fontWeight: 600, color: '#fff' }}>{t.title}</div>
                    <div style={{ fontSize: '0.75rem', color: '#64748b', marginTop: '0.2rem' }}>
                      Category: {t.category} {t.depends_on.length > 0 && `• Depends on: ${t.depends_on.join(', ')}`}
                    </div>
                  </td>

                  <td style={{ padding: '1rem', color: '#cbd5e1', fontSize: '0.85rem' }}>
                    {deadlineDate}
                  </td>

                  <td style={{ padding: '1rem', fontSize: '0.85rem' }}>
                    <span style={{ color: '#fff', fontWeight: 600 }}>{t.remaining_hours}h</span>
                    <span style={{ color: '#64748b' }}> / {t.estimated_hours}h</span>
                  </td>

                  <td style={{ padding: '1rem' }}>
                    <span
                      style={{
                        padding: '0.2rem 0.5rem',
                        borderRadius: '4px',
                        fontSize: '0.75rem',
                        fontWeight: 600,
                        backgroundColor:
                          t.status === 'done'
                            ? 'rgba(16, 185, 129, 0.2)'
                            : t.status === 'in_progress'
                            ? 'rgba(99, 102, 241, 0.2)'
                            : 'rgba(148, 163, 184, 0.2)',
                        color:
                          t.status === 'done'
                            ? '#34d399'
                            : t.status === 'in_progress'
                            ? '#818cf8'
                            : '#94a3b8',
                      }}
                    >
                      {t.status.toUpperCase()}
                    </span>
                  </td>

                  <td style={{ padding: '1rem', textAlign: 'right' }}>
                    {completingTaskId === t.id ? (
                      <div style={{ display: 'inline-flex', alignItems: 'center', gap: '0.5rem' }}>
                        <input
                          type="number"
                          step="0.5"
                          min="0.5"
                          value={actualHoursInput}
                          onChange={(e) => setActualHoursInput(parseFloat(e.target.value) || 1)}
                          style={{
                            width: '60px',
                            padding: '0.25rem 0.4rem',
                            borderRadius: '4px',
                            background: '#0f172a',
                            border: '1px solid #334155',
                            color: '#fff',
                            fontSize: '0.8rem',
                          }}
                        />
                        <button
                          className="btn btn-success"
                          style={{ padding: '0.25rem 0.6rem', fontSize: '0.75rem' }}
                          onClick={() => handleComplete(t)}
                        >
                          Confirm
                        </button>
                        <button
                          className="btn btn-outline"
                          style={{ padding: '0.25rem 0.5rem', fontSize: '0.75rem' }}
                          onClick={() => setCompletingTaskId(null)}
                        >
                          Cancel
                        </button>
                      </div>
                    ) : (
                      <div style={{ display: 'inline-flex', gap: '0.5rem' }}>
                        {t.status !== 'done' && (
                          <button
                            className="btn btn-outline"
                            style={{ padding: '0.35rem 0.65rem', fontSize: '0.75rem' }}
                            title="Record completion with actual hours"
                            onClick={() => {
                              setCompletingTaskId(t.id);
                              setActualHoursInput(t.estimated_hours);
                            }}
                          >
                            <Check size={14} color="#10b981" />
                            Complete
                          </button>
                        )}
                        <button
                          className="btn btn-outline"
                          style={{ padding: '0.35rem 0.5rem', color: '#f87171' }}
                          title="Delete task"
                          onClick={() => handleDelete(t.id)}
                        >
                          <Trash2 size={14} />
                        </button>
                      </div>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
};
