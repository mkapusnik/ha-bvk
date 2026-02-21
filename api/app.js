const express = require('express');
const fs = require('fs/promises');
const path = require('path');

function createApp(options = {}) {
  const dataDir = options.dataDir || process.env.DATA_DIR || '/app/data';
  const app = express();

  app.get('/', (req, res) => {
    res.json({ status: 'ok', service: 'bvk-scraper-api' });
  });

  app.get('/latest', async (req, res) => {
    const filePath = path.join(dataDir, 'latest.json');

    try {
      const content = await fs.readFile(filePath, 'utf-8');
      const data = JSON.parse(content);
      res.json(data);
    } catch (error) {
      if (error && error.code === 'ENOENT') {
        res.status(404).json({ detail: 'latest.json not found' });
        return;
      }

      if (error instanceof SyntaxError) {
        res.status(500).json({ detail: 'Error decoding latest.json' });
        return;
      }

      res.status(500).json({ detail: 'Error decoding latest.json' });
    }
  });

  app.get('/history', async (req, res) => {
    const filePath = path.join(dataDir, 'history.json');

    try {
      const content = await fs.readFile(filePath, 'utf-8');
      const data = JSON.parse(content);
      res.json(data);
    } catch (error) {
      if (error && error.code === 'ENOENT') {
        res.json([]);
        return;
      }

      if (error instanceof SyntaxError) {
        res.status(500).json({ detail: 'Error decoding history.json' });
        return;
      }

      res.status(500).json({ detail: 'Error decoding history.json' });
    }
  });

  return app;
}

module.exports = {
  createApp,
};
