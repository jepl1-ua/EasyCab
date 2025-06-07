const express = require('express');
const path = require('path');

const app = express();
const PORT = process.env.FRONT_PORT || 3000;
const CENTRAL_HOST = process.env.CENTRAL_HOST || 'central';
const CENTRAL_PORT = process.env.CENTRAL_PORT || '8443';

app.use(express.static(path.join(__dirname, 'public')));

app.get('/api/state', async (req, res) => {
  try {
    const resp = await fetch(`http://${CENTRAL_HOST}:${CENTRAL_PORT}/state`);
    const data = await resp.json();
    res.json(data);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.get('/api/audit', async (req, res) => {
  try {
    const resp = await fetch(`http://${CENTRAL_HOST}:${CENTRAL_PORT}/audit`);
    const data = await resp.json();
    res.json(data);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.listen(PORT, () => {
  console.log(`Front listening on port ${PORT}`);
});
