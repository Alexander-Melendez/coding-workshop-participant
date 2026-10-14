-- Development only: deletes every table and ALL data.
-- The backend recreates the schema on its next request.
DROP TABLE IF EXISTS "audit_log", "budget_history", "time_entries", "milestone_assignments",
  "milestone_dependencies", "milestones", "projects", "employees", "users", "app_settings",
  "project_managers", "employee_projects" CASCADE;
DROP VIEW IF EXISTS "project_summary", "project_budget_summary", "project_milestone_progress",
  "employee_project_hours", "employee_current_assignment";
DROP TYPE IF EXISTS "user_role", "milestone_status";
