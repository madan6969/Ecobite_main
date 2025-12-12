// API Client connecting to Flask Backend

const API_BASE = '/api';

export function getUser() {
  // In a real app, we might fetch this from an endpoint like /api/me
  // For now, we'll rely on the sidebar hydration or return a placeholder
  // The backend handles auth via session cookies.
  const sbE = document.getElementById('sbEmail');
  const sbN = document.getElementById('sbUser');
  return {
    email: sbE ? sbE.textContent : 'user@example.com',
    name: sbN ? sbN.textContent : 'User'
  };
}

export async function listPosts(params = {}) {
  const query = new URLSearchParams(params).toString();
  const res = await fetch(`${API_BASE}/food-posts?${query}`);
  if (!res.ok) throw new Error('Failed to fetch posts');
  return await res.json();
}

/* ---------- FIXED createPost ---------- */
export async function createPost(data) {
  const isFormData = data instanceof FormData;

  const res = await fetch(`${API_BASE}/food-posts`, {
    method: 'POST',
    // For FormData: let the browser set the multipart boundary automatically
    headers: isFormData ? undefined : { 'Content-Type': 'application/json' },
    body: isFormData ? data : JSON.stringify(data)
  });

  if (!res.ok) {
    let msg = 'Failed to create post';
    try {
      const err = await res.json();
      if (err && err.error) msg = err.error;
    } catch (e) {
      // Response was not JSON (e.g. HTML traceback), fall back to raw text
      try {
        const text = await res.text();
        msg = text.slice(0, 200); // just a short preview
      } catch { /* ignore */ }
    }
    throw new Error(msg);
  }

  return await res.json();
}

export async function claimPost(postId, data = {}) {
  const res = await fetch(`${API_BASE}/food-posts/${postId}/claims`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data)
  });
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.error || 'Failed to claim post');
  }
  return await res.json();
}

export async function approveClaim(postId, claimId) {
  const res = await fetch(`${API_BASE}/claims/${claimId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ status: 'accepted' })
  });
  if (!res.ok) throw new Error('Failed to approve claim');
  return await res.json();
}

export async function rejectClaim(postId, claimId) {
  const res = await fetch(`${API_BASE}/claims/${claimId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ status: 'rejected' })
  });
  if (!res.ok) throw new Error('Failed to reject claim');
  return await res.json();
}

export async function deletePost(postId) {
  const res = await fetch(`${API_BASE}/food-posts/${postId}`, {
    method: 'DELETE'
  });

  if (!res.ok) {
    let msg = 'Failed to delete post';
    try {
      const err = await res.json();
      if (err && err.error) msg = err.error;
    } catch (e) {
      try {
        const text = await res.text();
        msg = text.slice(0, 200);
      } catch { /* ignore */ }
    }
    throw new Error(msg);
  }

  return await res.json();
}

export async function computeStats() {
  // Fetch all posts to compute stats client-side or use a stats endpoint if available.
  // For now, we'll fetch all posts to match previous behavior.
  const list = await listPosts({ status: 'available' }); // This only gets available
  // Actually, to get total stats we might need more data or a dedicated endpoint.
  // But let's try to get all posts if possible, or just use what we have.
  // The API listPosts filters by status if provided.
  // The API code: if status_filter == "available" ... elif "claimed" ...
  // It doesn't seem to have an "all" option easily without modification or multiple requests.
  // Let's make multiple requests in parallel for now.

  const [availableRes, claimedRes, expiredRes] = await Promise.all([
    fetch(`${API_BASE}/food-posts?status=available`),
    fetch(`${API_BASE}/food-posts?status=claimed`),
    fetch(`${API_BASE}/food-posts?status=expired`)
  ]);

  const availableList = await availableRes.json();
  const claimedList = await claimedRes.json();
  const expiredList = await expiredRes.json();

  const available = availableList.length;
  const shared = claimedList.length;
  const expired = expiredList.length;
  const total = available + shared + expired;
  const savedKg = (shared * 1.2).toFixed(1);

  // For the feed list, we usually return the one matching the current scope.
  // But computeStats was returning 'list' which was ALL posts in the LS version.
  // app.js filters this list client-side.
  // To minimize refactoring app.js, we can combine them.
  const allList = [...availableList, ...claimedList, ...expiredList];

  return { available, total, shared, savedKg, list: allList };
}
