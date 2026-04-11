export interface FamilyMember {
  id: string;
  family_id: string;
  first_name: string;
  last_name: string | null;
  role: "adult" | "child";
  birthdate: string | null;
  is_active: boolean;
}

export interface TaskInstance {
  id: string;
  family_id: string;
  family_member_id: string;
  routine_id: string | null;
  chore_template_id: string | null;
  instance_date: string;
  due_at: string;
  is_completed: boolean;
  completed_at: string | null;
  override_completed: boolean | null;
  override_by: string | null;
  override_note: string | null;
}

export interface StepCompletion {
  id: string;
  task_instance_id: string;
  routine_step_id: string;
  is_completed: boolean;
  completed_at: string | null;
}

export interface Routine {
  id: string;
  family_id: string;
  family_member_id: string;
  name: string;
  block: "morning" | "after_school" | "evening";
  recurrence: string;
}

export interface ChoreTemplate {
  id: string;
  family_id: string;
  name: string;
  description: string | null;
  recurrence: string;
  assignment_type: string;
}

export interface DailyWin {
  id: string;
  family_id: string;
  family_member_id: string;
  win_date: string;
  is_win: boolean;
  task_count: number;
  completed_count: number;
}

export interface Event {
  id: string;
  family_id: string;
  created_by: string | null;
  title: string;
  description: string | null;
  location: string | null;
  starts_at: string;
  ends_at: string;
  all_day: boolean;
  recurrence_rule: string | null;
  recurrence_parent_id: string | null;
  recurrence_instance_date: string | null;
  source: string;
  is_hearth_visible: boolean;
  task_instance_id: string | null;
  is_cancelled: boolean;
}

export interface PersonalTask {
  id: string;
  family_id: string;
  assigned_to: string;
  created_by: string | null;
  title: string;
  description: string | null;
  notes: string | null;
  status: string;
  priority: string;
  due_at: string | null;
  completed_at: string | null;
  event_id: string | null;
}

export interface Bill {
  id: string;
  family_id: string;
  created_by: string | null;
  title: string;
  description: string | null;
  notes: string | null;
  amount_cents: number;
  due_date: string;
  status: string;
  paid_at: string | null;
  source: string;
}

export interface Meal {
  id: string;
  family_id: string;
  meal_plan_id: string | null;
  created_by: string | null;
  meal_date: string;
  meal_type: string;
  title: string;
  description: string | null;
  notes: string | null;
}

export interface Note {
  id: string;
  family_id: string;
  family_member_id: string;
  title: string;
  body: string;
  category: string | null;
  is_archived: boolean;
  created_at: string;
  updated_at: string;
}

export interface GroceryItem {
  id: string;
  family_id: string;
  added_by_member_id: string;
  title: string;
  quantity: number | null;
  unit: string | null;
  category: string | null;
  preferred_store: string | null;
  notes: string | null;
  source: string;
  approval_status: string;
  purchase_request_id: string | null;
  is_purchased: boolean;
  purchased_at: string | null;
  purchased_by: string | null;
}

export interface PurchaseRequest {
  id: string;
  family_id: string;
  requested_by_member_id: string;
  type: string;
  title: string;
  details: string | null;
  quantity: number | null;
  unit: string | null;
  preferred_brand: string | null;
  preferred_store: string | null;
  urgency: string | null;
  status: string;
  linked_grocery_item_id: string | null;
  reviewed_by_member_id: string | null;
  reviewed_at: string | null;
  review_note: string | null;
}
