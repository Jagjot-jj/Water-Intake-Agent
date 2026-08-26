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

import 'dotenv/config';
import { GoogleGenAI } from '@google/genai';
import express from 'express';
import path from 'path';

const app = express();

const PORT = Number(process.env.PORT) || 3000;
const DIST_DIR = path.resolve(process.cwd(), 'dist');
const gemini = process.env.GEMINI_API_KEY
  ? new GoogleGenAI({ apiKey: process.env.GEMINI_API_KEY })
  : null;

app.use(express.json());

// API health endpoint
app.get('/api/health', (_req, res) => {
  res.json({
    status: 'ok',
    project: 'Water Intake Coach (T16 - Health)',
    gemini_configured: Boolean(gemini),
  });
});

app.post('/api/chat', async (req, res) => {
  const { message, state, local_response } = req.body ?? {};

  if (typeof message !== 'string' || !message.trim()) {
    res.status(400).json({ error: 'A non-empty message is required.' });
    return;
  }

  if (!gemini) {
    res.status(503).json({ error: 'Gemini is not configured on the server.' });
    return;
  }

  try {
    const response = await gemini.models.generateContent({
      model: process.env.GEMINI_MODEL || 'gemini-3.6-flash',
      contents: `User message: ${message}\n\nCurrent hydration state: ${JSON.stringify(state)}\n\nLocal verified response: ${local_response}`,
      config: {
        systemInstruction:
          'You are a professional hydration tracking assistant. Return a concise, warm response grounded only in the supplied hydration state and verified local response. Do not give medical advice or encourage excessive water consumption.',
        temperature: 0.2,
      },
    });

    res.json({ response: response.text || local_response });
  } catch (error) {
    console.error('[Gemini] Request failed:', error);
    res.status(502).json({ error: 'Gemini request failed.' });
  }
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
