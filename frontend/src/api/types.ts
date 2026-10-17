/**
 * RealityCheck Shared TypeScript Types.
 */

export type TaskStatus = 'todo' | 'in_progress' | 'blocked' | 'done' | 'deferred';

export interface Task {
  id: string;
  title: string;
  description?: string | null;
  category: string;
  priority: number; // 1 (highest) to 5 (lowest)
  deadline: string; // ISO 8601 UTC
  estimated_hours: number;
  actual_hours: number;
  remaining_hours: number;
  status: TaskStatus;
  depends_on: string[];
  splittable: boolean;
  earliest_start?: string | null;
  fixed_start?: string | null;
  fixed_end?: string | null;
  confidence: number;
  created_at: string;
  updated_at: string;
}

export interface TaskCreate {
  title: string;
  deadline: string;
  estimated_hours: number;
  description?: string;
  category?: string;
  priority?: number;
  depends_on?: string[];
  splittable?: boolean;
  earliest_start?: string;
  confidence?: number;
}

export interface TaskUpdate {
  title?: string;
  description?: string;
  category?: string;
  priority?: number;
  deadline?: string;
  estimated_hours?: number;
  actual_hours?: number;
  remaining_hours?: number;
  status?: TaskStatus;
  depends_on?: string[];
  splittable?: boolean;
  earliest_start?: string;
  confidence?: number;
}

export interface UserSettings {
  id: number;
  daily_hours: Record<string, number>;
  work_start: string;
  work_end: string;
  break_duration_minutes: number;
  break_after_hours: number;
  buffer_fraction: number;
  timezone: string;
  updated_at: string;
}

export interface FeasibilityResult {
  task_id: string;
  task_title: string;
  deadline: string;
  remaining_hours: number;
  usable_hours_before_deadline: number;
  calendar_hours_before_deadline: number;
  buffer_hours_deducted: number;
  break_hours_deducted: number;
  lost_hours_deducted: number;
  required_hours_per_day: number;
  recommended_session_hours: number;
  feasible: boolean;
  shortfall_hours?: number | null;
  slack_hours?: number | null;
  explanation: string;
  intermediate_values: Record<string, any>;
}

export interface ScheduledSession {
  task_id: string;
  task_title: string;
  priority: number;
  category: string;
  start_time: string;
  end_time: string;
  duration_hours: number;
  is_fixed: boolean;
}

export interface DailySchedule {
  date: string;
  usable_hours: number;
  scheduled_hours: number;
  sessions: ScheduledSession[];
}

export interface SchedulerResult {
  plan: DailySchedule[];
  unscheduled_work: Array<{
    task_id: string;
    task_title: string;
    remaining_hours: number;
    reason: string;
  }>;
  feasible: boolean;
  validation_passed: boolean;
  validation_errors: string[];
}

export interface RecoveryOption {
  type: 'move_lower_priority' | 'extend_hours' | 'negotiate_deadline';
  description: string;
  trade_offs: string;
  affected_task_ids: string[];
  additional_hours_needed: number;
  new_deadline?: string | null;
  proposed_actions: string[];
}

export interface RecoveryProposal {
  proposal_id: string;
  trigger_task_id?: string | null;
  trigger_task_title?: string | null;
  trigger_reason: string;
  feasibility_summary: string;
  options: RecoveryOption[];
  requires_approval: boolean;
  created_at: string;
  resolved_at?: string | null;
  status: 'pending' | 'accepted' | 'rejected';
  selected_option_index?: number | null;
}

export interface RecoveryResolutionResult {
  proposal_id: string;
  action: 'accept' | 'reject';
  selected_option_index?: number | null;
  tasks_modified: string[];
  message: string;
}

// ── MCP Protocol Types ────────────────────────────────────────────────────────

export interface MCPTool {
  name: string;
  description: string;
  inputSchema?: Record<string, any>;
}

export interface MCPMessage {
  id: string;
  sender: 'user' | 'assistant' | 'system';
  text: string;
  timestamp: string;
  mcpCall?: {
    tool: string;
    arguments: Record<string, any>;
    status: 'calling' | 'success' | 'error';
    rawResponse?: any;
    explanation?: string;
  };
  recoveryProposal?: RecoveryProposal;
}
