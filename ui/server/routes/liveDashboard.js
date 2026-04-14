import express from 'express';
import axios from 'axios';
import { protect } from '../middleware/auth.js';

const router = express.Router();
router.use(protect);

const pythonApiUrl = (process.env.PYTHON_API_URL || 'http://localhost:8000').replace(/\/+$/, '');

function getTargetPath(req) {
  const original = req.originalUrl || req.url || '';
  return original.replace(/^\/api\/live/, '') || '/';
}

function resolveWorkflowUserId(user) {
  if (!user?._id) return '';
  return String(user.role || '').toLowerCase() === 'admin'
    ? 'admin'
    : user._id.toString();
}

function shouldEmbedUserIdInBody(pathname) {
  return pathname.endsWith('/callback') || pathname.endsWith('/feedback');
}

async function proxyDashboardRequest(req, res) {
  const targetPath = getTargetPath(req);
  const userId = resolveWorkflowUserId(req.user);

  if (!userId) {
    return res.status(401).json({ message: 'User context missing' });
  }

  try {
    const target = new URL(targetPath, `${pythonApiUrl}/`);
    const pathname = target.pathname;
    const params = new URLSearchParams(target.search);

    Object.entries(req.query || {}).forEach(([key, value]) => {
      if (Array.isArray(value)) {
        value.forEach((item) => params.append(key, String(item)));
      } else if (value !== undefined && value !== null) {
        params.set(key, String(value));
      }
    });

    let data = req.body;
    if (shouldEmbedUserIdInBody(pathname)) {
      data = { ...(req.body || {}), user_id: userId };
    } else {
      params.set('user_id', userId);
    }

    const response = await axios({
      method: req.method,
      url: `${pythonApiUrl}${pathname}`,
      params,
      data,
      timeout: 20000,
    });

    return res.status(response.status).json(response.data);
  } catch (error) {
    const status = error.response?.status || 500;
    const payload = error.response?.data || { message: error.message || 'Live dashboard request failed' };
    return res.status(status).json(payload);
  }
}

router.use('/dashboard', proxyDashboardRequest);

export default router;
