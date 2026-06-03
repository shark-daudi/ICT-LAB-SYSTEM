async function apiFetch(url, options = {}) {
    const response = await fetch(url, {
        ...options,
        headers: { 'Content-Type': 'application/json', ...options.headers },
        credentials: 'same-origin'
    });
    if (!response.ok) {
        const error = await response.json().catch(() => ({}));
        throw new Error(error.error || 'Request failed');
    }
    return response.json();
}

async function apiGet(endpoint) { return apiFetch(endpoint); }
async function apiPost(endpoint, data) { return apiFetch(endpoint, { method: 'POST', body: JSON.stringify(data) }); }
async function apiPut(endpoint, data) { return apiFetch(endpoint, { method: 'PUT', body: JSON.stringify(data) }); }
async function apiDelete(endpoint) { return apiFetch(endpoint, { method: 'DELETE' }); }