/**
 * End-to-end test of the core journey across all three roles, in a real browser.
 *
 *   1. Admin: bad sign-in shows an error, form validation, creates a manager,
 *      an employee and a project
 *   2. Manager: adds a milestone and assigns the employee
 *   3. Employee: logs today's hours; can't open admin pages; sees no budget
 *   4. Manager: sees the logged hours and cost on the project
 *
 * Needs the app running (./bin/start-dev.sh, or dev_server.py + npm run dev).
 *   npx playwright install chromium   # first time only
 *   npm run test:e2e
 * Env: E2E_BASE_URL (default http://localhost:3000), E2E_ADMIN_USER, E2E_ADMIN_PASSWORD
 */
import assert from 'node:assert/strict';
import { chromium } from 'playwright';

const BASE = process.env.E2E_BASE_URL || 'http://localhost:3000';
const ADMIN_USER = process.env.E2E_ADMIN_USER || 'admin';
const ADMIN_PASSWORD = process.env.E2E_ADMIN_PASSWORD || 'Admin@123';
const RUN = Date.now().toString(36);

function isoDay(offset) {
  const d = new Date();
  d.setDate(d.getDate() + offset);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}

async function step(name, fn) {
  const started = Date.now();
  try {
    await fn();
    console.log(`  ok  ${name} (${Date.now() - started} ms)`);
  } catch (error) {
    console.error(`  FAIL ${name}`);
    throw error;
  }
}

async function signIn(page, username, password) {
  await page.goto(BASE);
  await page.getByLabel('Username or email').fill(username);
  await page.getByLabel('Password').fill(password);
  await page.getByRole('button', { name: 'Sign in' }).click();
  await page.locator('main h1').waitFor();
}

async function signOut(page) {
  await page.getByRole('button', { name: 'Sign out' }).click();
  await page.getByRole('button', { name: 'Sign in' }).waitFor();
}

async function addPerson(page, {
  name, handle, role, salary, managerName,
}) {
  await page.goto(`${BASE}/people`);
  await page.getByRole('button', { name: 'Add person' }).click();
  const dialog = page.getByRole('dialog');
  await dialog.getByLabel('Full name').fill(name);
  await dialog.getByLabel('Email').fill(`${handle}@e2e.example`);
  await dialog.getByLabel('Role').selectOption(role);
  if (role === 'employee') await dialog.getByLabel('Annual salary (USD)').fill(String(salary));
  if (managerName) {
    const option = dialog.locator('select[name="manager_id"] option', { hasText: managerName });
    await dialog.getByLabel('Manager').selectOption(await option.getAttribute('value'));
  }
  await dialog.getByRole('button', { name: 'Add person' }).click();
  const password = await page.getByTestId('temporary-password').textContent();
  const username = await page.getByTestId('new-username').textContent();
  assert.equal(password.length, 6, 'temporary password should be 6 characters');
  assert.match(username, /^[a-z2-9]{6}$/, 'username should be 6 generated characters');
  await page.getByRole('button', { name: 'Done' }).click();
  return { password, username };
}

const browser = await chromium.launch();
const page = await (await browser.newContext({ viewport: { width: 1366, height: 900 } })).newPage();
const manager = { name: `Mia Manager ${RUN}`, handle: `mia.${RUN}` };
const employee = { name: `Eli Employee ${RUN}`, handle: `eli.${RUN}` };
const projectName = `E2E rollout ${RUN}`;

try {
  console.log(`E2E against ${BASE}`);

  await step('wrong password shows a clear error', async () => {
    await page.goto(BASE);
    await page.getByLabel('Username or email').fill(ADMIN_USER);
    await page.getByLabel('Password').fill('definitely-wrong');
    await page.getByRole('button', { name: 'Sign in' }).click();
    await page.getByRole('alert').filter({ hasText: 'Incorrect username or password' }).waitFor();
  });

  await step('admin signs in and sees the overview', async () => {
    await signIn(page, ADMIN_USER, ADMIN_PASSWORD);
    await page.getByRole('link', { name: 'Audit log' }).first().waitFor();
  });

  await step('empty form shows field errors and is not submitted', async () => {
    await page.goto(`${BASE}/people`);
    await page.getByRole('button', { name: 'Add person' }).click();
    await page.getByRole('dialog').getByRole('button', { name: 'Add person' }).click();
    assert.ok(await page.getByText('This field is required').count() >= 2);
    await page.getByRole('button', { name: 'Cancel' }).click();
  });

  await step('admin creates a manager and an employee', async () => {
    Object.assign(manager, await addPerson(page, { ...manager, role: 'manager', salary: 130000 }));
    Object.assign(employee, await addPerson(page, {
      ...employee, role: 'employee', salary: 104000, managerName: manager.name,
    }));
    await page.getByRole('cell', { name: new RegExp(employee.name) }).waitFor();
  });

  await step('admin creates a project with that manager', async () => {
    await page.goto(`${BASE}/projects`);
    await page.getByRole('button', { name: 'New project' }).click();
    const dialog = page.getByRole('dialog');
    await dialog.getByLabel('Title').fill(projectName);
    await dialog.getByLabel('Start date').fill(isoDay(-7));
    await dialog.getByLabel('End date').fill(isoDay(60));
    await dialog.getByLabel('Budget (USD)').fill('20000');
    await dialog.getByLabel('Estimated hours').fill('400');
    const managerOption = dialog.locator('select[name="manager_id"] option', { hasText: manager.name });
    await dialog.getByLabel('Manager').selectOption(await managerOption.getAttribute('value'));
    await dialog.getByRole('button', { name: 'Create project' }).click();
    await page.getByRole('heading', { level: 1, name: projectName }).waitFor();
    await signOut(page);
  });

  await step('manager adds a milestone and assigns the employee', async () => {
    await signIn(page, manager.username, manager.password);
    await page.goto(`${BASE}/projects`);
    await page.getByRole('link', { name: projectName }).click();
    await page.getByRole('button', { name: 'Add milestone' }).click();
    let dialog = page.getByRole('dialog');
    await dialog.getByLabel('Title').fill('Pilot sites');
    await dialog.getByLabel('Completion criteria').fill('Three pilot sites live');
    await dialog.getByLabel('End date').fill(isoDay(30));
    await dialog.getByRole('button', { name: 'Add milestone' }).click();
    await page.getByRole('heading', { name: 'Pilot sites' }).waitFor();

    await page.getByRole('button', { name: 'Assign' }).click();
    dialog = page.getByRole('dialog');
    const option = dialog.locator('select[name="user_id"] option', { hasText: employee.name });
    await dialog.getByLabel('Employee').selectOption(await option.getAttribute('value'));
    await dialog.getByRole('button', { name: 'Assign' }).click();
    await page.getByText(new RegExp(`${employee.name}, `)).waitFor();
    await signOut(page);
  });

  await step('employee logs today, sees no budget or People, and sees their team', async () => {
    await signIn(page, employee.username, employee.password);
    await page.getByText('Pilot sites', { exact: false }).first().waitFor();
    await page.getByRole('button', { name: 'Log hours' }).click();
    await page.getByText('Hours logged').waitFor();
    await page.getByText('8 h', { exact: true }).first().waitFor();

    await page.getByRole('link', { name: projectName }).click();
    await page.getByRole('heading', { level: 1, name: projectName }).waitFor();
    assert.equal(await page.getByText('Budget', { exact: true }).count(), 0, 'employees must not see budget');

    await page.goto(`${BASE}/people`);
    await page.getByRole('heading', { name: 'Page not found' }).waitFor();

    await page.getByRole('link', { name: 'My team' }).click();
    await page.getByText(manager.name, { exact: true }).waitFor();
    await page.getByText(`${employee.name} (you)`).waitFor();
    assert.equal(await page.getByText('Salary').count(), 0, 'teammates must not show salaries');
    await signOut(page);
  });

  await step('manager sees the logged hours and cost', async () => {
    await signIn(page, manager.username, manager.password);
    await page.goto(`${BASE}/projects`);
    await page.getByRole('link', { name: projectName }).click();
    // 8h x (104,000 / 2,080 = $50/h) = $400
    await page.getByRole('row', { name: new RegExp(`${employee.name}.*8 h.*\\$400`) }).waitFor();
    await signOut(page);
  });

  console.log('All end-to-end checks passed');
} catch (error) {
  await page.screenshot({ path: 'e2e-failure.png', fullPage: true });
  console.error(error);
  console.error('Saved a screenshot to e2e-failure.png');
  process.exitCode = 1;
} finally {
  await browser.close();
}
