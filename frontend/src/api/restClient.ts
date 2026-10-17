/**
 * RealityCheck REST API Client for the Dashboard, All Tasks, and Recovery Views.
 */
import type {
  FeasibilityResult,
  RecoveryProposal,
  RecoveryResolutionResult,
  SchedulerResult,
  Task,
  TaskCreate,
  TaskUpdate,
  UserSettings,
} from './types';

const BASE_URL = '/api';

async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let errMsg = `Request failed with status ${res.status}`;
    try {
      const err = await res.json();
      errMsg = err.detail || err.error || errMsg;
    } catch {
      // ignore
    }
    throw new Error(errMsg);
  }
  if (res.status === 204) {
    return {} as T;
  }
  return res.json();
}

export const restClient = {
  // ── Tasks ─────────────────────────────────────────────────────────────────
  async listTasks(params?: { status?: string; priority?: number; category?: string }): Promise<Task[]> {
    const qs = new URLSearchParams();
    if (params?.status) qs.set('status', params.status);
    if (params?.priority) qs.set('priority', String(params.priority));
    if (params?.category) qs.set('category', params.category);
    const url = `${BASE_URL}/tasks${qs.toString() ? `?${qs.toString()}` : ''}`;
    const res = await fetch(url);
    const data = await handleResponse<{ tasks: Task[]; total: number }>(res);
    return data.tasks;
  },

  async getTask(taskId: string): Promise<Task> {
    const res = await fetch(`${BASE_URL}/tasks/${taskId}`);
    return handleResponse<Task>(res);
  },

  async createTask(data: TaskCreate): Promise<Task> {
    const res = await fetch(`${BASE_URL}/tasks`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    return handleResponse<Task>(res);
  },

  async updateTask(taskId: string, data: TaskUpdate): Promise<Task> {
    const res = await fetch(`${BASE_URL}/tasks/${taskId}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    return handleResponse<Task>(res);
  },

  async deleteTask(taskId: string): Promise<void> {
    const res = await fetch(`${BASE_URL}/tasks/${taskId}`, { method: 'DELETE' });
    return handleResponse<void>(res);
  },

  // ── Plans & Feasibility ───────────────────────────────────────────────────
  async getFeasibility(taskId: string, lostHoursToday: number = 0.0): Promise<FeasibilityResult> {
    const qs = lostHoursToday > 0 ? `?lost_hours_today=${lostHoursToday}` : '';
    const res = await fetch(`${BASE_URL}/plans/feasibility/${taskId}${qs}`);
    return handleResponse<FeasibilityResult>(res);
  },

  async generateDailyPlan(daysAhead: number = 14, lostHoursToday: number = 0.0): Promise<SchedulerResult> {
    const res = await fetch(`${BASE_URL}/plans/generate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ days_ahead: daysAhead, lost_hours_today: lostHoursToday }),
    });
    return handleResponse<SchedulerResult>(res);
  },

  // ── Recovery ──────────────────────────────────────────────────────────────
  async generateRecoveryPlan(taskId: string, lostHoursToday: number = 0.0): Promise<RecoveryProposal> {
    const qs = lostHoursToday > 0 ? `?lost_hours_today=${lostHoursToday}` : '';
    const res = await fetch(`${BASE_URL}/recovery/generate/${taskId}${qs}`, {
      method: 'POST',
    });
    return handleResponse<RecoveryProposal>(res);
  },

  async resolveRecoveryProposal(
    proposalId: string,
    action: 'accept' | 'reject',
    optionIndex?: number
  ): Promise<RecoveryResolutionResult> {
    const res = await fetch(`${BASE_URL}/recovery/resolve`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        proposal_id: proposalId,
        action,
        selected_option_index: optionIndex ?? -1,
      }),
    });
    return handleResponse<RecoveryResolutionResult>(res);
  },

  async recordCompletion(taskId: string, actualHours: number): Promise<any> {
    const res = await fetch(`${BASE_URL}/recovery/complete/${taskId}?actual_hours=${actualHours}`, {
      method: 'POST',
    });
    return handleResponse<any>(res);
  },

  // ── Settings ──────────────────────────────────────────────────────────────
  async getSettings(): Promise<UserSettings> {
    const res = await fetch(`${BASE_URL}/settings`);
    return handleResponse<UserSettings>(res);
  },

  async updateSettings(data: Partial<UserSettings>): Promise<UserSettings> {
    const res = await fetch(`${BASE_URL}/settings`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    return handleResponse<UserSettings>(res);
  },
};
