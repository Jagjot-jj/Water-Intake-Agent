// import express from 'express';
// import path from 'path';

// const app = express();
// const PORT = Number(process.env.PORT) || 3000;
// const DIST_DIR = path.resolve(process.cwd(), 'dist');

// app.use(express.json());

// // API health endpoint
// app.get('/api/health', (req, res) => {
//   res.json({ status: 'ok', project: 'Water Intake Coach (T16 - Health)' });
// });

// // Serve static assets from dist
// app.use(express.static(DIST_DIR));

// // Fallback to index.html for SPA routing
// app.get('*', (req, res) => {
//   res.sendFile(path.join(DIST_DIR, 'index.html'));
// });

// app.listen(PORT, '0.0.0.0', () => {
//   console.log(`Water Intake Coach Server running on http://0.0.0.0:${PORT}`);
// });

import express from 'express';
import path from 'path';

const app = express();

const PORT = Number(process.env.PORT) || 3000;
const DIST_DIR = path.resolve(process.cwd(), 'dist');

app.use(express.json());

// API health endpoint
app.get('/api/health', (_req, res) => {
  res.json({
    status: 'ok',
    project: 'Water Intake Coach (T16 - Health)',
  });
});

// Serve static files from dist
app.use(express.static(DIST_DIR));

// SPA fallback
app.get('/{*splat}', (_req, res) => {
  res.sendFile(path.join(DIST_DIR, 'index.html'));
});

// Start server
app.listen(PORT, '0.0.0.0', () => {
  console.log(
    `Water Intake Coach Server running on http://localhost:${PORT}`
  );
});
