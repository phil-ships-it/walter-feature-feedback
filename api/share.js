import { put } from '@vercel/blob';

export default async function handler(req, res) {
  if (req.method !== 'POST') {
    return res.status(405).json({ error: 'Method not allowed' });
  }

  if (!process.env.BLOB_READ_WRITE_TOKEN) {
    return res.status(503).json({ error: 'Image sharing not configured' });
  }

  const { image } = req.body;
  if (!image) return res.status(400).json({ error: 'Missing image data' });

  const buf = Buffer.from(image, 'base64');
  const name = `walter-${Date.now()}-${Math.random().toString(36).slice(2, 8)}.png`;
  const blob = await put(name, buf, { access: 'public', contentType: 'image/png' });

  return res.json({ url: blob.url });
}
