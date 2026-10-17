/**
 * RealityCheck Deterministic Natural-Language Intent Router.
 *
 * Maps user conversational requests directly to real MCP tool calls.
 * Pure deterministic pattern matching — ZERO LLM for math, scheduling,
 * or database state transitions.
 */
import type { Task } from '../api/types';

export interface RoutedIntent {
  toolName: string;
  arguments: Record<string, any>;
  explanationPrompt: string;
}

export function routeUserIntent(
  userQuery: string,
  activeTasks: Task[] = []
): RoutedIntent {
  const q = userQuery.toLowerCase().trim();

  // Helper: find task by partial name or P1
  const findTask = (queryHint?: string): Task | undefined => {
    if (queryHint) {
      const match = activeTasks.find((t) =>
        t.title.toLowerCase().includes(queryHint.toLowerCase())
      );
      if (match) return match;
    }
    // Default to highest priority active task (priority = 1)
    return activeTasks
      .filter((t) => t.status !== 'done')
      .sort((a, b) => a.priority - b.priority)[0];
  };

  // 1. "Can I finish ... ?" / "Is it feasible ... ?"
  if (
    q.includes('can i finish') ||
    q.includes('finish on time') ||
    q.includes('is it possible') ||
    q.includes('will i finish') ||
    q.includes('feasibility')
  ) {
    let taskName = '';
    const match = q.match(/(?:finish|for)\s+([^?.]+)/);
    if (match && !match[1].includes('highest') && !match[1].includes('p1')) {
      taskName = match[1].replace(/by\s+\w+/i, '').trim();
    }
    const task = findTask(taskName);
    const taskId = task ? task.id : 'task-exam-prep';

    return {
      toolName: 'calculate_deadline_feasibility',
      arguments: {
        task_id: taskId,
        lost_hours_today: 0.0,
      },
      explanationPrompt: `Analyzing deadline feasibility for task "${task ? task.title : 'Highest Priority Task'}" using verified calendar constraints and deterministic buffer deductions.`,
    };
  }

  // 2. "I lost N hours today" / "fell behind N hours"
  const lostHoursMatch = q.match(/(?:lost|missed|wasted|behind by?)\s+(\d+(?:\.\d+)?)\s*(?:hours?|hrs?)/i) ||
    q.match(/(\d+(?:\.\d+)?)\s*(?:hours?|hrs?)\s*(?:lost|missed)/i);
  if (lostHoursMatch) {
    const hours = parseFloat(lostHoursMatch[1]);
    const task = findTask();
    const taskId = task ? task.id : 'task-exam-prep';

    return {
      toolName: 'generate_recovery_plan',
      arguments: {
        task_id: taskId,
        lost_hours_today: hours,
      },
      explanationPrompt: `Registered ${hours} lost working hours today. Generating recovery options with trade-offs and awaiting explicit user approval before applying changes.`,
    };
  }

  // 3. "What must move so I can finish ... ?"
  if (q.includes('what must move') || q.includes('which tasks must move')) {
    let taskName = '';
    const match = q.match(/(?:finish|complete)\s+([^?.]+)/);
    if (match) taskName = match[1].replace(/on time/i, '').trim();
    const task = findTask(taskName);
    const taskId = task ? task.id : 'task-exam-prep';

    return {
      toolName: 'generate_recovery_plan',
      arguments: {
        task_id: taskId,
        lost_hours_today: 0.0,
      },
      explanationPrompt: `Evaluating portfolio schedule to identify lower-priority tasks that can be deferred or extended to protect "${task ? task.title : 'Priority 1 work'}".`,
    };
  }

  // 4. "Show me recovery options" / "Show me two recovery options"
  if (q.includes('recovery options') || q.includes('how do i recover') || q.includes('options and wait for my approval')) {
    const task = findTask();
    const taskId = task ? task.id : 'task-exam-prep';

    return {
      toolName: 'generate_recovery_plan',
      arguments: {
        task_id: taskId,
        lost_hours_today: 0.0,
      },
      explanationPrompt: `Generated multi-option recovery plan for "${task ? task.title : 'Primary Task'}". Review the trade-offs below and select Accept or Reject.`,
    };
  }

  // 5. "I finished [task] in N hours instead of M" / "Update future estimates"
  const finishedMatch = q.match(/(?:finished|completed)\s+([a-zA-Z0-9\s_-]+?)\s+in\s+(\d+(?:\.\d+)?)\s*(?:hours?|hrs?)/i);
  if (finishedMatch) {
    const taskHint = finishedMatch[1].trim();
    const actualHours = parseFloat(finishedMatch[2]);
    const task = findTask(taskHint);
    const taskId = task ? task.id : (activeTasks[0]?.id || 'task-lit-review');

    return {
      toolName: 'record_task_completion',
      arguments: {
        task_id: taskId,
        actual_hours: actualHours,
      },
      explanationPrompt: `Recording completion of "${task ? task.title : taskId}" with actual duration ${actualHours}h. Updating historical duration ratios.`,
    };
  }

  // 6. "Recalculate my plan" / "Generate schedule"
  if (q.includes('recalculate') || q.includes('schedule') || q.includes('daily plan') || q.includes('today\'s plan')) {
    return {
      toolName: 'generate_daily_plan',
      arguments: {
        days_ahead: 14,
        lost_hours_today: 0.0,
      },
      explanationPrompt: `Generating optimal daily schedule honoring priority protections, dependencies, working hours, and mandatory break rules.`,
    };
  }

  // 7. "List my tasks" / "What tasks do I have?"
  if (q.includes('list') || q.includes('show tasks') || q.includes('what tasks')) {
    return {
      toolName: 'list_tasks',
      arguments: {},
      explanationPrompt: `Retrieving all active tasks across priority levels.`,
    };
  }

  // 8. "Check estimates for [category]"
  const estimateMatch = q.match(/estimate[s]?\s+for\s+(\w+)/i);
  if (estimateMatch) {
    return {
      toolName: 'update_duration_estimate',
      arguments: {
        category: estimateMatch[1],
      },
      explanationPrompt: `Checking duration ratio and sample threshold (≥3 required) for category "${estimateMatch[1]}".`,
    };
  }

  // Fallback default: list tasks or schedule
  return {
    toolName: 'list_tasks',
    arguments: {},
    explanationPrompt: `Retrieving current task portfolio.`,
  };
}
