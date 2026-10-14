/**
 * One function per API endpoint: the frontend's contract with the backend.
 */
import { api, request } from './api.js';

// auth
export const login = (username, password) => request('POST', '/auth/login', { body: { username, password }, auth: false });
export const logout = () => api.post('/auth/logout');
export const getMe = () => api.get('/auth/me');
export const updateMe = (body) => api.put('/auth/me', body);
export const changePassword = (body) => api.post('/auth/change-password', body);

// dashboard
export const getDashboard = () => api.get('/dashboard');

// users
export const listUsers = (query) => api.get('/users', query);
export const createUser = (body) => api.post('/users', body);
export const updateUser = (id, body) => api.put(`/users/${id}`, body);
export const archiveUser = (id) => api.del(`/users/${id}`);
export const restoreUser = (id) => api.post(`/users/${id}/restore`);
export const resetPassword = (id) => api.post(`/users/${id}/reset-password`);
export const getMyTeam = () => api.get('/users/my-team');

// projects
export const listProjects = (query) => api.get('/projects', query);
export const getProject = (id) => api.get(`/projects/${id}`);
export const createProject = (body) => api.post('/projects', body);
export const updateProject = (id, body) => api.put(`/projects/${id}`, body);
export const completeProject = (id) => api.post(`/projects/${id}/complete`);
export const archiveProject = (id) => api.del(`/projects/${id}`);
export const restoreProject = (id) => api.post(`/projects/${id}/restore`);
export const setProjectManager = (id, managerId) => api.put(`/projects/${id}/manager`, { manager_id: managerId });
export const getBudgetHistory = (id) => api.get(`/projects/${id}/budget-history`);

// milestones
export const listMilestones = (projectId) => api.get(`/projects/${projectId}/milestones`);
export const createMilestone = (projectId, body) => api.post(`/projects/${projectId}/milestones`, body);
export const updateMilestone = (id, body) => api.put(`/milestones/${id}`, body);
export const completeMilestone = (id) => api.post(`/milestones/${id}/complete`);
export const deleteMilestone = (id) => api.del(`/milestones/${id}`);

// assignments
export const listAssignments = (query) => api.get('/assignments', query);
export const createAssignment = (milestoneId, body) => api.post(`/milestones/${milestoneId}/assignments`, body);
export const deleteAssignment = (id) => api.del(`/assignments/${id}`);

// time
export const listTimeEntries = (query) => api.get('/time-entries', query);
export const createTimeEntry = (body) => api.post('/time-entries', body);
export const updateTimeEntry = (id, body) => api.put(`/time-entries/${id}`, body);
export const deleteTimeEntry = (id) => api.del(`/time-entries/${id}`);

// audit
export const listAuditLogs = (query) => api.get('/audit-logs', query);
