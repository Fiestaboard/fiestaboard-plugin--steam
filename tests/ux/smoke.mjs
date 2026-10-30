// Run against run_fixture_app.py only. Never use real Steam credentials.
import assert from 'node:assert/strict';
import { mkdir, writeFile } from 'node:fs/promises';
const { chromium, request } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright');
const baseURL = process.env.STEAM_UX_URL || 'http://127.0.0.1:8000';
const output = process.env.STEAM_UX_RESULTS || '/results';
await mkdir(output, { recursive: true });
const api = await request.newContext({ baseURL });
const marker = await api.get('/__steam_fixture');
assert.deepEqual(await marker.json(), { fixture: 'steam-plugin-ux', real_steam: false });
// Safe to reset only the disposable fixture's two named instances.
for (const label of ['me', 'husband']) await api.delete(`/api/plugins/steam/instances/${label}`);
for (const item of (await (await api.get('/api/pages')).json()).pages) {
  if (item.name.startsWith('Steam UX ')) await api.delete(`/api/pages/${item.id}`);
}
const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
const results = [];
const check = (description) => { results.push(description); console.log(`PASS ${description}`); };
const shot = (name) => page.screenshot({ path: `${output}/${name}.png`, fullPage: true, animations: 'disabled' });
const row = (name) => page.getByRole('row').filter({ has: page.getByRole('switch', { name: `Toggle ${name}`, exact: true }) });
async function configure(name, profile, key, mode) {
  await row(name).getByRole('button', { name: 'Configure', exact: true }).click();
  await page.getByRole('textbox', { name: 'Steam Profile', exact: false }).fill(profile);
  const keyField = page.getByRole('textbox', { name: 'Steam Web API Key', exact: true });
  await keyField.fill(key);
  assert.equal(await keyField.getAttribute('type'), 'password');
  if (mode) {
    await page.getByRole('combobox').click();
    await page.getByRole('option', { name: mode, exact: true }).click();
  }
  await shot('settings');
  await page.getByRole('button', { name: 'Save Changes', exact: true }).click();
  await page.getByRole('dialog').waitFor({ state: 'hidden' });
}
async function data(label) {
  const response = await api.get(`/api/plugins/steam:${label}/data`);
  assert.equal(response.status(), 200, await response.text());
  return (await response.json()).data;
}
try {
  await page.goto(`${baseURL}/integrations`);
  await page.waitForLoadState('networkidle');
  const skip = page.getByRole('button', { name: "Skip — I'll add a display later" });
  await skip.waitFor();
  await skip.click();
  await page.waitForURL(`${baseURL}/`);
  await page.goto(`${baseURL}/integrations`);
  await page.getByRole('heading', { name: 'Integrations', exact: true }).waitFor();
  for (const [label, id] of [['me', '76561198000000001'], ['husband', '76561198000000002']]) {
    await row('Steam').getByRole('button', { name: 'More options' }).click();
    await page.getByRole('menuitem', { name: 'Add Instance' }).click();
    await page.getByPlaceholder('e.g. sf, prod, api-2').fill(label);
    await page.getByRole('button', { name: 'Create', exact: true }).click();
    await page.getByPlaceholder('e.g. sf, prod, api-2').waitFor({ state: 'hidden' });
    await page.keyboard.press('Escape');
    await configure(`Steam (${label})`, id, 'fixture-key');
    const toggle = page.getByRole('switch', { name: `Toggle Steam (${label})`, exact: true });
    await toggle.click();
    await toggle.and(page.locator('[aria-checked="true"]')).waitFor();
  }
  assert.equal((await data('me')).current_game, 'Portal 2');
  assert.equal((await data('husband')).current_game, 'Hades');
  assert.equal((await data('me')).achievements_unlocked, 2);
  assert.equal((await data('husband')).achievements_unlocked, 1);
  check('Create, configure and enable two independent profiles; masked key and distinct stats');
  await shot('two-profiles');

  await row('Steam (me)').getByRole('button', { name: 'Configure', exact: true }).click();
  await page.getByRole('textbox', { name: 'Steam Profile', exact: false }).fill('not-a-profile');
  const validationResponse = page.waitForResponse(r => ['PUT', 'PATCH'].includes(r.request().method()) && r.url().includes('plugins/steam'));
  await page.getByRole('button', { name: 'Save Changes', exact: true }).click();
  const validation = await validationResponse;
  assert.equal(validation.status(), 400);
  assert.match(await validation.text(), /Enter a 17-digit Steam ID/);
  await page.getByText(/Failed to save configuration:.*failed validation/).first().waitFor();
  await shot('validation-error');
  await page.getByRole('textbox', { name: 'Steam Profile', exact: false }).fill('76561198000000001');
  await page.getByRole('button', { name: 'Save Changes', exact: true }).click();
  await page.getByRole('dialog').waitFor({ state: 'hidden' });
  check('Invalid profile is rejected visibly and can be corrected in settings');

  await configure('Steam (me)', '76561198000000001', 'invalid-test-key');
  const invalid = await api.get('/api/plugins/steam:me/data');
  assert.equal(invalid.status(), 503);
  assert.match(await invalid.text(), /key|auth|denied|reject/i);
  await shot('invalid-key');
  check('Rejected API key returns an actionable data-fetch error');
  await configure('Steam (me)', '76561198000000001', 'private-test-key', 'Friends');
  const privateData = await data('me');
  assert.equal(privateData.friends_available, false);
  assert.equal(privateData.friends_online, null);
  assert.equal(privateData.current_game, 'Portal 2');
  check('Private friends list stays unavailable while profile activity survives');
  await configure('Steam (me)', '76561198000000001', 'fixture-key', 'Now Playing');

  await page.goto(`${baseURL}/pages/new`);
  await page.getByRole('button', { name: 'Variables', exact: true }).click();
  await page.getByRole('button', { name: 'player_name Jeff', exact: true }).waitFor();
  await page.getByRole('button', { name: 'player_name Husband', exact: true }).waitFor();
  await shot('variables');
  await page.getByRole('button', { name: 'player_name Husband', exact: true }).click();
  assert.match(await page.getByRole('textbox', { name: 'Template editor' }).innerText(), /steam:husband.player_name/i);
  check('Variable picker exposes both people and inserts a selected variable');
  await page.getByRole('button', { name: 'Plain Text', exact: true }).click();
  await page.getByRole('textbox', { name: 'Page Name', exact: true }).fill('Steam UX Household');
  const template = ['{{steam:me.player_name}}','{{steam:me.current_game}}','{{steam:me.status}}','{{steam:husband.player_name}}','{{steam:husband.current_game}}','{{steam:husband.status}}'];
  await page.getByRole('textbox', { name: /Type your template text/ }).fill(template.join('\n'));
  const saved = page.waitForResponse(r => /\/api\/(v1\/)?pages$/.test(r.url()) && r.request().method() === 'POST');
  await page.getByRole('button', { name: 'Save Page', exact: true }).click();
  const response = await saved;
  assert.ok(response.ok(), await response.text());
  const savedBody = await response.json();
  const savedId = savedBody.id || savedBody.page?.id;
  assert.ok(savedId, JSON.stringify(savedBody));
  const previewResponse = await api.post(`/api/pages/${savedId}/preview?force_refresh=true`);
  assert.ok(previewResponse.ok(), await previewResponse.text());
  const preview = await previewResponse.json();
  assert.deepEqual(preview.lines.map(line => line.trim().toUpperCase()), ['JEFF', 'PORTAL 2', 'IN GAME', 'HUSBAND', 'HADES', 'IN GAME']);
  await page.waitForLoadState('networkidle');
  await shot('household');
  check('Save household page through the actual editor');
  for (const [size, rows, cols] of [['Note', 3, 15], ['Note Array', 3, 30]]) {
    await page.goto(`${baseURL}/pages/new`);
    await page.getByRole('combobox', { name: 'Change board size' }).click();
    await page.getByRole('option', { name: size, exact: true }).click();
    if (size === 'Note Array') {
      await page.getByRole('combobox', { name: 'Notes wide', exact: true }).click();
      await page.getByRole('option', { name: '2 wide', exact: true }).click();
    }
    await page.getByRole('button', { name: 'Plain Text', exact: true }).click();
    await page.getByRole('textbox', { name: 'Page Name', exact: true }).fill(`Steam UX ${size}`);
    await page.getByRole('textbox', { name: /Type your template text/ }).fill('{{steam:me.line_1}}\n{{steam:me.line_2}}\n{{steam:me.line_3}}');
    const saving = page.waitForResponse(r => /\/api\/(v1\/)?pages$/.test(r.url()) && r.request().method() === 'POST');
    await page.getByRole('button', { name: 'Save Page', exact: true }).click();
    const savedResponse = await saving;
    assert.ok(savedResponse.ok(), await savedResponse.text());
    const body = await savedResponse.json();
    const rendered = await api.post(`/api/pages/${body.id || body.page?.id}/preview?force_refresh=true`);
    const board = await rendered.json();
    assert.equal(board.lines.length, rows);
    assert.ok(board.lines.every(line => line.length === cols), JSON.stringify(board));
    assert.match(board.lines.join(' '), /PORTAL 2/i);
    await page.waitForLoadState('networkidle');
    await shot(size.toLowerCase().replace(' ', '-'));
    check(`${size} page saves and renders ${rows} x ${cols} with live plugin data`);
  }
  await writeFile(`${output}/report.json`, JSON.stringify({ results, savedPage: savedBody }, null, 2));
} catch (error) {
  await shot('failure');
  await writeFile(`${output}/failure.txt`, String(error));
  throw error;
} finally {
  await browser.close();
  await api.dispose();
}
