import { put } from '@vercel/blob';

const GOOGLE_WEBHOOK_URL = 'https://script.google.com/macros/s/AKfycbyfo92yZDs2QDVrkF3Pj6CJfgreQYVTMbKRp4RZfexMX9sUTOtgCcKgoqWE0lTAKmSQ/exec';

async function logToGoogle(productUrl, feature, response, imageUrl) {
  try {
    await fetch(GOOGLE_WEBHOOK_URL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ productUrl, feature, response, imageUrl }),
      signal: AbortSignal.timeout(3000),
    });
  } catch (_) { /* non-critical, ignore */ }
}

export default async function handler(req, res) {
  if (req.method !== 'POST') {
    return res.status(405).json({ error: 'Method not allowed' });
  }

  if (!process.env.BLOB_READ_WRITE_TOKEN) {
    return res.status(503).json({ error: 'Image sharing not configured' });
  }

  const { image, productUrl = '', feature = '', response = '' } = req.body;
  if (!image) return res.status(400).json({ error: 'Missing image data' });

  const buf = Buffer.from(image, 'base64');
  const name = `walter-${Date.now()}-${Math.random().toString(36).slice(2, 8)}.png`;
  const blob = await put(name, buf, { access: 'public', contentType: 'image/png' });

  await logToGoogle(productUrl, feature, response, blob.url);

  return res.json({ url: blob.url });
}
