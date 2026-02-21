const fs = require('fs/promises');
const os = require('os');
const path = require('path');
const { test, beforeEach, afterEach } = require('node:test');
const assert = require('node:assert/strict');
const request = require('supertest');

const { createApp } = require('../app');

let tempDir;
let app;

async function writeJson(fileName, payload) {
  const filePath = path.join(tempDir, fileName);
  await fs.writeFile(filePath, JSON.stringify(payload), 'utf-8');
}

beforeEach(async () => {
  tempDir = await fs.mkdtemp(path.join(os.tmpdir(), 'bvk-api-'));
  app = createApp({ dataDir: tempDir });
});

afterEach(async () => {
  if (tempDir) {
    await fs.rm(tempDir, { recursive: true, force: true });
  }
});

test('root returns ok status', async () => {
  const response = await request(app).get('/');
  assert.equal(response.status, 200);
  assert.deepEqual(response.body, { status: 'ok', service: 'bvk-scraper-api' });
});

test('latest returns 404 when missing', async () => {
  const response = await request(app).get('/latest');
  assert.equal(response.status, 404);
  assert.equal(response.body.detail, 'latest.json not found');
});

test('latest returns json when present', async () => {
  await writeJson('latest.json', { timestamp: '2026-01-01T00:00:00', reading: '123.456' });
  const response = await request(app).get('/latest');
  assert.equal(response.status, 200);
  assert.equal(response.body.reading, '123.456');
});

test('latest returns 500 when invalid json', async () => {
  const filePath = path.join(tempDir, 'latest.json');
  await fs.writeFile(filePath, '{not json}', 'utf-8');
  const response = await request(app).get('/latest');
  assert.equal(response.status, 500);
  assert.equal(response.body.detail, 'Error decoding latest.json');
});

test('history returns empty list when missing', async () => {
  const response = await request(app).get('/history');
  assert.equal(response.status, 200);
  assert.deepEqual(response.body, []);
});

test('history returns json when present', async () => {
  await writeJson('history.json', [
    { timestamp: '2026-01-01T00:00:00', reading: '1.000' },
    { timestamp: '2026-01-02T00:00:00', reading: '2.000' },
  ]);
  const response = await request(app).get('/history');
  assert.equal(response.status, 200);
  assert.equal(response.body.at(-1).reading, '2.000');
});

test('history returns 500 when invalid json', async () => {
  const filePath = path.join(tempDir, 'history.json');
  await fs.writeFile(filePath, '[] trailing', 'utf-8');
  const response = await request(app).get('/history');
  assert.equal(response.status, 500);
  assert.equal(response.body.detail, 'Error decoding history.json');
});
