const { createApp } = require('./app');

const app = createApp();
const port = Number(process.env.PORT) || 8000;
const host = process.env.HOST || '0.0.0.0';

app.listen(port, host, () => {
  console.log(`API listening on ${host}:${port}`);
});
