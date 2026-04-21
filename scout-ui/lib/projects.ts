/**
 * Family projects — API wrappers + hooks.
 */

import { useCallback, useEffect, useState } from "react";

import { API_BASE_URL } from "./config";
import { authHeaders } from "./api";

export type ProjectCategory =
  | "birthday" | "holiday" | "trip" | "school_event"
  | "home_project" | "weekend_reset" | "custom";

export type ProjectStatus = "draft" | "active" | "paused" | "complete" | "cancelled";
export type ProjectTaskStatus = "todo" | "in_progress" | "blocked" | "done" | "skipped";

export interface Project {
  id: string;
  family_id: string;
  project_template_id: string | null;
  name: string;
  description: string | null;
  category: ProjectCategory;
  status: ProjectStatus;
  start_date: string;
  target_end_date: string | null;
  actual_end_date: string | null;
  budget_cents: number | null;
  actual_spent_cents: number | null;
  primary_owner_family_member_id: string | null;
  created_by_family_member_id: string;
  created_at: string;
}

export interface ProjectTask {
  id: string;
  project_id: string;
  title: string;
  description: string | null;
  status: ProjectTaskStatus;
  owner_family_member_id: string | null;
  due_date: string | null;
  estimated_duration_minutes: number | null;
  actual_duration_minutes: number | null;
  budget_cents: number | null;
  spent_cents: number | null;
  depends_on_project_task_id: string | null;
  notes: string | null;
  created_at: string;
}

export interface ProjectMilestone {
  id: string;
  project_id: string;
  name: string;
  target_date: string;
  is_complete: boolean;
  completed_at: string | null;
  order_index: number;
  notes: string | null;
}

export interface ProjectBudgetEntry {
  id: string;
  project_id: string;
  project_task_id: string | null;
  amount_cents: number;
  kind: "estimate" | "expense" | "refund";
  vendor: string | null;
  notes: string | null;
  recorded_at: string;
  recorded_by_family_member_id: string;
}

export interface ProjectDetail {
  project: Project;
  tasks: ProjectTask[];
  milestones: ProjectMilestone[];
  budget_entries: ProjectBudgetEntry[];
}

export interface ProjectHealth {
  project_id: string;
  tasks_total: number;
  tasks_done: number;
  tasks_overdue: number;
  tasks_blocked: number;
  completion_percent: number;
  milestones_total: number;
  milestones_complete: number;
}

export interface ProjectTemplate {
  id: string;
  family_id: string | null;
  name: string;
  description: string | null;
  category: ProjectCategory;
  estimated_duration_days: number | null;
  default_lead_time_days: number;
  default_budget_cents: number | null;
  is_active: boolean;
  is_builtin: boolean;
  created_at: string;
}

// ---------------------------------------------------------------------------
// Low-level fetch helpers
// ---------------------------------------------------------------------------

async function jsonOr<T>(r: Response): Promise<T> {
  if (!r.ok) {
    const text = await r.text().catch(() => "");
    throw new Error(`${r.status} ${text}`.trim());
  }
  return (await r.json()) as T;
}

export async function fetchProjects(projectStatus = "active"): Promise<Project[]> {
  return jsonOr<Project[]>(
    await fetch(`${API_BASE_URL}/api/projects?project_status=${projectStatus}`, {
      headers: authHeaders(),
    }),
  );
}

export async function fetchProject(id: string): Promise<ProjectDetail> {
  return jsonOr<ProjectDetail>(
    await fetch(`${API_BASE_URL}/api/projects/${id}`, { headers: authHeaders() }),
  );
}

export async function fetchProjectHealth(id: string): Promise<ProjectHealth> {
  return jsonOr<ProjectHealth>(
    await fetch(`${API_BASE_URL}/api/projects/${id}/health`, { headers: authHeaders() }),
  );
}

export async function fetchMyProjectTasksToday(): Promise<ProjectTask[]> {
  return jsonOr<ProjectTask[]>(
    await fetch(`${API_BASE_URL}/api/projects/today/me`, { headers: authHeaders() }),
  );
}

export async function createProject(input: {
  name: string;
  category: ProjectCategory;
  start_date: string;
  description?: string | null;
  target_end_date?: string | null;
  budget_cents?: number | null;
  primary_owner_family_member_id?: string | null;
  project_template_id?: string | null;
  name_override?: string | null;
  status?: ProjectStatus;
}): Promise<Project> {
  return jsonOr<Project>(
    await fetch(`${API_BASE_URL}/api/projects`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...authHeaders() },
      body: JSON.stringify(input),
    }),
  );
}

export async function addProjectTask(
  projectId: string,
  input: {
    title: string;
    description?: string | null;
    due_date?: string | null;
    owner_family_member_id?: string | null;
    estimated_duration_minutes?: number | null;
    budget_cents?: number | null;
  },
): Promise<ProjectTask> {
  return jsonOr<ProjectTask>(
    await fetch(`${API_BASE_URL}/api/projects/${projectId}/tasks`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...authHeaders() },
      body: JSON.stringify(input),
    }),
  );
}

export async function updateProjectTask(
  projectId: string,
  taskId: string,
  input: Partial<{
    title: string;
    description: string;
    status: ProjectTaskStatus;
    owner_family_member_id: string | null;
    due_date: string | null;
    notes: string;
  }>,
): Promise<ProjectTask> {
  return jsonOr<ProjectTask>(
    await fetch(`${API_BASE_URL}/api/projects/${projectId}/tasks/${taskId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json", ...authHeaders() },
      body: JSON.stringify(input),
    }),
  );
}

export async function addProjectMilestone(
  projectId: string,
  input: { name: string; target_date: string; order_index?: number; notes?: string },
): Promise<ProjectMilestone> {
  return jsonOr<ProjectMilestone>(
    await fetch(`${API_BASE_URL}/api/projects/${projectId}/milestones`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...authHeaders() },
      body: JSON.stringify(input),
    }),
  );
}

export async function addProjectBudgetEntry(
  projectId: string,
  input: {
    amount_cents: number;
    kind: "estimate" | "expense" | "refund";
    project_task_id?: string | null;
    vendor?: string;
    notes?: string;
  },
): Promise<ProjectBudgetEntry> {
  return jsonOr<ProjectBudgetEntry>(
    await fetch(`${API_BASE_URL}/api/projects/${projectId}/budget`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...authHeaders() },
      body: JSON.stringify(input),
    }),
  );
}

export async function fetchProjectTemplates(): Promise<ProjectTemplate[]> {
  return jsonOr<ProjectTemplate[]>(
    await fetch(`${API_BASE_URL}/api/project_templates`, { headers: authHeaders() }),
  );
}

// ---------------------------------------------------------------------------
// Hooks
// ---------------------------------------------------------------------------

export function useProjects(opts: { status?: string } = {}) {
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(async () => {
    setLoading(true);
    try {
      setProjects(await fetchProjects(opts.status ?? "active"));
      setError(null);
    } catch (e: any) {
      setError(e?.message ?? "Failed to load projects");
    } finally {
      setLoading(false);
    }
  }, [opts.status]);

  useEffect(() => {
    reload();
  }, [reload]);

  return { projects, loading, error, reload };
}

export function useProject(id: string | null) {
  const [detail, setDetail] = useState<ProjectDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(async () => {
    if (!id) return;
    setLoading(true);
    try {
      setDetail(await fetchProject(id));
      setError(null);
    } catch (e: any) {
      setError(e?.message ?? "Failed to load project");
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    reload();
  }, [reload]);

  return { detail, loading, error, reload };
}

export function useProjectHealth(id: string | null) {
  const [health, setHealth] = useState<ProjectHealth | null>(null);
  const [loading, setLoading] = useState(true);

  const reload = useCallback(async () => {
    if (!id) return;
    setLoading(true);
    try {
      setHealth(await fetchProjectHealth(id));
    } catch {
      setHealth(null);
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    reload();
  }, [reload]);

  return { health, loading, reload };
}

export function useMyProjectTasksToday() {
  const [tasks, setTasks] = useState<ProjectTask[]>([]);
  const [loading, setLoading] = useState(true);

  const reload = useCallback(async () => {
    setLoading(true);
    try {
      setTasks(await fetchMyProjectTasksToday());
    } catch {
      setTasks([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    reload();
  }, [reload]);

  return { tasks, loading, reload };
}

export function useProjectTemplates() {
  const [templates, setTemplates] = useState<ProjectTemplate[]>([]);
  const [loading, setLoading] = useState(true);

  const reload = useCallback(async () => {
    setLoading(true);
    try {
      setTemplates(await fetchProjectTemplates());
    } catch {
      setTemplates([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    reload();
  }, [reload]);

  return { templates, loading, reload };
}
