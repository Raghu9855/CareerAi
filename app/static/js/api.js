/**
 * CareerAI — Clean API Client Layer
 * Handles authentication, data retrieval, and resilient backend communication.
 */

const API = (() => {
  const TOKEN_KEY = 'careerai_token';

  function getToken() {
    return localStorage.getItem(TOKEN_KEY);
  }

  function setToken(token) {
    if (token) {
      localStorage.setItem(TOKEN_KEY, token);
    } else {
      localStorage.removeItem(TOKEN_KEY);
    }
  }

  function clearToken() {
    localStorage.removeItem(TOKEN_KEY);
  }

  function getHeaders(customHeaders = {}, includeAuth = true) {
    const headers = { ...customHeaders };
    const token = getToken();
    if (includeAuth && token) {
      headers['Authorization'] = `Bearer ${token}`;
    }
    return headers;
  }

  async function request(url, options = {}) {
    const opts = { ...options };
    opts.headers = getHeaders(opts.headers || {});
    
    const response = await fetch(url, opts);
    
    // Automatically parse JSON or fallback
    let data = null;
    const contentType = response.headers.get('content-type') || '';
    if (contentType.includes('application/json')) {
      data = await response.json();
    } else {
      data = await response.text();
    }

    if (!response.ok) {
      const errMessage = (data && data.error && data.error.message) || data.message || `Request failed with status ${response.status}`;
      const error = new Error(errMessage);
      error.status = response.status;
      error.data = data;
      throw error;
    }

    return data;
  }

  return {
    getToken,
    setToken,
    clearToken,

    // Authentication & Users
    auth: {
      async register(fullName, email, password) {
        return request('/api/v1/auth/register', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ full_name: fullName, email, password })
        });
      },
      async login(email, password) {
        return request('/api/v1/auth/login', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ email, password })
        });
      },
      async getMe() {
        return request('/api/v1/users/me');
      }
    },

    // Profiles
    profiles: {
      async get(userId) {
        return request(`/api/v1/profiles/${userId}`);
      },
      async update(userId, payload) {
        return request(`/api/v1/profiles/${userId}`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
      }
    },

    // Skills Taxonomy
    skills: {
      async getCanonical() {
        return request('/api/v1/skills?per_page=100');
      },
      async getUserSkills(userId) {
        return request(`/api/v1/skills/users/${userId}`);
      },
      async createSkill(name, category = 'Technical') {
        return request('/api/v1/skills', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ name, category })
        });
      },
      async addUserSkill(userId, skillId, proficiency, yearsOfExp) {
        return request(`/api/v1/skills/users/${userId}`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            skill_id: skillId,
            proficiency,
            years_of_experience: yearsOfExp
          })
        });
      },
      async deleteUserSkill(userId, skillId) {
        return request(`/api/v1/skills/users/${userId}/${skillId}`, {
          method: 'DELETE'
        });
      }
    },

    // Documents
    documents: {
      async upload(file) {
        const formData = new FormData();
        formData.append('file', file);
        return request('/api/v1/documents/upload', {
          method: 'POST',
          body: formData
        });
      },
      async list() {
        return request('/api/v1/documents?per_page=50');
      },
      async delete(docId) {
        return request(`/api/v1/documents/${docId}`, {
          method: 'DELETE'
        });
      }
    },

    // Deterministic ML
    ml: {
      async analyze(payload) {
        return request('/api/v1/ml/analyze', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
      },
      async listAnalyses() {
        return request('/api/v1/ml/analyses?page_size=30');
      },
      async getAnalysis(id) {
        return request(`/api/v1/ml/analyses/${id}`);
      }
    },

    // LLM Guidance & Interview Prep
    ai: {
      async getStatus() {
        return request('/api/v1/ai/status');
      },
      async explain(analysisId) {
        return request(`/api/v1/ai/explain/${analysisId}`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' }
        });
      },
      async interviewPrep(analysisId) {
        return request(`/api/v1/ai/interview-prep/${analysisId}`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' }
        });
      }
    },

    // RAG Knowledge Search
    rag: {
      async index(docId) {
        return request(`/api/v1/rag/index/${docId}`, {
          method: 'POST'
        });
      },
      async query(queryString, topK = 3) {
        return request('/api/v1/rag/query', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ query: queryString, top_k: topK })
        });
      }
    },

    // Applications & Jobs Kanban
    applications: {
      async list() {
        return request('/api/v1/applications?per_page=100');
      },
      async create(jobId, notes = '') {
        return request('/api/v1/applications', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ job_id: jobId, notes })
        });
      },
      async updateStatus(appId, status) {
        return request(`/api/v1/applications/${appId}`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ status })
        });
      },
      async delete(appId) {
        return request(`/api/v1/applications/${appId}`, {
          method: 'DELETE'
        });
      }
    },

    jobs: {
      async create(title, company, location, description, jobType = 'full_time') {
        return request('/api/v1/jobs', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            title,
            company,
            location: location || 'Remote',
            description,
            job_type: jobType
          })
        });
      }
    },

    // System Diagnostics
    system: {
      async getMetrics() {
        return request('/metrics');
      },
      async getReadiness() {
        return request('/ready');
      }
    }
  };
})();
