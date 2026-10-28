/**
 * CareerAI — Main Application Controller
 * Coordinates workflows, data binding, state management, and interaction handlers.
 */

const PRESETS = {
  cloud: {
    title: "Senior Cloud Platform Engineer",
    company: "Stripe",
    resume: `Alice Smith — Lead Cloud Architect & Backend Systems Engineer
Experienced in designing, deploying, and maintaining cloud platforms with Docker, Kubernetes, Linux, and Terraform.
Built robust microservices using Python, FastAPI, and SQLAlchemy.
Optimized high-concurrency MySQL databases and implemented Redis caching clusters.
Automated multi-region infrastructure using Terraform and configured CI/CD with Docker and GitHub Actions.
Certifications: Certified Kubernetes Administrator (CKA).`,
    job: `Senior Cloud Platform Engineer
We are seeking an experienced Senior Cloud Engineer to manage our microservices infrastructure.
Requirements:
- Strong background with Python and FastAPI backend development.
- Deep expertise in containerized cloud environments (Docker & Kubernetes).
- Hands-on experience with MySQL and Redis caching.
- Infrastructure-as-Code proficiency using Terraform.
- Familiarity with CI/CD pipelines and Docker.`,
    skills: "Python, FastAPI, Docker, Kubernetes, MySQL, Redis, Terraform"
  },
  fullstack: {
    title: "Full-Stack Python Engineer",
    company: "Vercel",
    resume: `Bob Davis — Full-Stack Python & React Developer
5 years building web applications with Python, FastAPI, and Django backends coupled with React TypeScript frontends.
Extensive experience with PostgreSQL and MySQL database schema design and optimization.
Containerized development environments with Docker. Familiar with Linux deployments and microservices.`,
    job: `Full-Stack Python Engineer
Looking for a full-stack engineer proficient in Python, FastAPI, Docker, and frontend web development.
Experience in MySQL or PostgreSQL and Redis is a major plus.`,
    skills: "Python, FastAPI, Docker, MySQL, Redis, React"
  },
  junior: {
    title: "Senior Distributed Systems Architect",
    company: "Snowflake",
    resume: `Charlie Brown — Junior Software Developer
Recent graduate with basic computer science foundation. Built academic projects in Java and basic HTML/CSS.
Passionate about software architecture and eager to learn backend development and cloud computing.`,
    job: `Senior Distributed Systems Architect
Must possess 8+ years experience architecting high-scale distributed systems in Python, Go, or C++.
Expert-level knowledge of Docker, Kubernetes, Redis caching, gRPC, and Kafka distributed streaming.`,
    skills: "Python, Docker, Kubernetes, Redis, Kafka, gRPC"
  }
};

let currentUser = null;
let currentAnalysisId = null;
let activeUploadedFile = null;

// ==========================================================================
// Initialization
// ==========================================================================

document.addEventListener('DOMContentLoaded', async () => {
  loadPreset('cloud');
  await ensureAuthSession();
  loadAIStatus();

  // Initialize Drag & Drop for Kanban
  UI.initKanbanDragAndDrop(async (appId, targetStage) => {
    await updateApplicationStage(appId, targetStage);
  });

  // Pre-load data in background
  loadKanbanBoard();
  loadUserProfile();
  loadUserSkills();
  loadDocumentsList();
  loadAnalysisHistory();
  initDragAndDropUpload();
});

// ==========================================================================
// Authentication & Session
// ==========================================================================

async function ensureAuthSession() {
  const token = API.getToken();
  if (token) {
    try {
      currentUser = await API.auth.getMe();
      updateUserPillUI();
      return token;
    } catch (e) {
      API.clearToken();
    }
  }

  // Auto-register a clean guest session if none exists
  try {
    const guestEmail = `guest_${Math.random().toString(36).substring(2, 8)}@example.com`;
    const data = await API.auth.register('Guest Candidate', guestEmail, 'DemoPassword123!');
    if (data && data.tokens) {
      API.setToken(data.tokens.access_token);
      currentUser = data.user;
      updateUserPillUI();
      return data.tokens.access_token;
    }
  } catch (err) {
    console.warn('Guest account initialization note:', err);
  }
  return null;
}

function updateUserPillUI() {
  const labelEl = document.getElementById('account-pill-label');
  const emailEl = document.getElementById('auth-current-email');
  if (currentUser) {
    const displayName = currentUser.full_name || currentUser.email.split('@')[0];
    if (labelEl) labelEl.textContent = displayName;
    if (emailEl) emailEl.textContent = `${currentUser.email} (${currentUser.role})`;
  } else {
    if (labelEl) labelEl.textContent = 'Account';
  }
}

async function loadAIStatus() {
  try {
    const data = await API.ai.getStatus();
    const dot = document.getElementById('ai-engine-dot');
    const label = document.getElementById('ai-engine-label');
    if (dot && label) {
      label.textContent = `AI: ${data.provider_label}`;
      dot.className = data.is_mock ? 'status-dot' : 'status-dot pulsing';
      dot.style.background = data.is_mock ? 'var(--text-tertiary)' : 'var(--success)';
    }
  } catch (err) {
    console.warn('AI status check note:', err);
  }
}

// ==========================================================================
// Navigation & Views
// ==========================================================================

function switchAppTab(tabId) {
  document.querySelectorAll('.app-view').forEach(v => v.classList.remove('active'));
  document.querySelectorAll('.nav-tab-btn').forEach(b => b.classList.remove('active'));

  const targetView = document.getElementById(`view-${tabId}`);
  const targetBtn = document.getElementById(`nav-btn-${tabId}`);
  if (targetView) targetView.classList.add('active');
  if (targetBtn) targetBtn.classList.add('active');

  // Refresh target data
  if (tabId === 'kanban') loadKanbanBoard();
  if (tabId === 'profile') { loadUserProfile(); loadUserSkills(); }
  if (tabId === 'documents') loadDocumentsList();
  if (tabId === 'history') loadAnalysisHistory();
}

function switchMode(mode) {
  const isText = mode === 'text';
  document.getElementById('tab-text').classList.toggle('active', isText);
  document.getElementById('tab-file').classList.toggle('active', !isText);
  document.getElementById('text-input-section').style.display = isText ? 'block' : 'none';
  document.getElementById('file-input-section').style.display = isText ? 'none' : 'block';
}

function switchDeepDiveTab(tabName) {
  document.querySelectorAll('.deepdive-tab-btn').forEach(b => b.classList.remove('active'));
  document.querySelectorAll('.deepdive-panel').forEach(p => p.classList.remove('active'));

  const btn = document.getElementById(`dd-tab-${tabName}`);
  const panel = document.getElementById(`dd-panel-${tabName}`);
  if (btn) btn.classList.add('active');
  if (panel) panel.classList.add('active');
}

function loadPreset(key) {
  const p = PRESETS[key];
  if (!p) return;
  document.getElementById('resume-text').value = p.resume;
  document.getElementById('job-desc').value = p.job;
  document.getElementById('job-skills').value = p.skills;
  document.getElementById('job-title-input').value = p.title || '';
  document.getElementById('job-company-input').value = p.company || '';
  switchMode('text');
}

function handleFileSelect(input) {
  if (input.files && input.files[0]) {
    activeUploadedFile = input.files[0];
    const sizeKb = (activeUploadedFile.size / 1024).toFixed(1);
    document.getElementById('file-label').textContent = `${activeUploadedFile.name} (${sizeKb} KB)`;
  }
}

function initDragAndDropUpload() {
  const dropZone = document.getElementById('drop-zone');
  if (!dropZone) return;

  ['dragenter', 'dragover'].forEach(eventName => {
    dropZone.addEventListener(eventName, (e) => {
      e.preventDefault();
      dropZone.classList.add('drag-active');
    }, false);
  });

  ['dragleave', 'drop'].forEach(eventName => {
    dropZone.addEventListener(eventName, (e) => {
      e.preventDefault();
      dropZone.classList.remove('drag-active');
    }, false);
  });

  dropZone.addEventListener('drop', (e) => {
    const dt = e.dataTransfer;
    const files = dt.files;
    if (files && files[0]) {
      activeUploadedFile = files[0];
      const sizeKb = (activeUploadedFile.size / 1024).toFixed(1);
      document.getElementById('file-label').textContent = `${activeUploadedFile.name} (${sizeKb} KB)`;
    }
  });
}

// ==========================================================================
// Fit Analysis & Intelligence
// ==========================================================================

async function runAnalysis() {
  const btn = document.getElementById('analyze-btn');
  const spinner = document.getElementById('btn-spinner');
  const btnText = document.getElementById('btn-text');

  btn.disabled = true;
  spinner.style.display = 'inline-block';
  btnText.textContent = 'Computing Fit...';

  try {
    await ensureAuthSession();

    let resumeText = document.getElementById('resume-text').value;
    const jobDesc = document.getElementById('job-desc').value;
    const skillsRaw = document.getElementById('job-skills').value;
    const jobSkills = skillsRaw.split(',').map(s => s.trim()).filter(Boolean);

    // File Mode
    if (document.getElementById('tab-file').classList.contains('active') && activeUploadedFile) {
      btnText.textContent = 'Extracting File...';
      const upDoc = await API.documents.upload(activeUploadedFile);
      
      // Trigger background RAG index asynchronously
      API.rag.index(upDoc.id).catch(() => {});

      btnText.textContent = 'Running ML Engine...';
      const mlData = await API.ml.analyze({
        document_id: upDoc.id,
        job_description: jobDesc,
        job_skills: jobSkills
      });

      renderResults(mlData);
      UI.showToast('Compatibility analysis generated successfully!', 'success');
      return;
    }

    // Text Mode
    if (!resumeText.trim()) {
      UI.showToast('Please enter your resume content or load a preset profile.', 'error');
      return;
    }

    const mlData = await API.ml.analyze({
      resume_text: resumeText,
      job_description: jobDesc,
      job_skills: jobSkills
    });

    renderResults(mlData);
    UI.showToast('Compatibility analysis generated successfully!', 'success');

  } catch (err) {
    console.error('Analysis error:', err);
    UI.showToast(err.message || 'Analysis could not be completed.', 'error');
  } finally {
    btn.disabled = false;
    spinner.style.display = 'none';
    btnText.textContent = 'Analyze Fit & Readiness';
  }
}

function renderResults(data) {
  const score = Math.round(data.compatibility_score || 0);
  document.getElementById('score-text').textContent = `${score}%`;

  // Animate Circular Gauge
  const circle = document.getElementById('score-circle');
  const offset = 283 - (283 * score) / 100;
  circle.style.strokeDashoffset = offset;

  const titleEl = document.getElementById('verdict-title');
  const descEl = document.getElementById('verdict-desc');
  const statusBadge = document.getElementById('result-status-badge');

  if (score >= 80) {
    circle.style.stroke = 'var(--success)';
    titleEl.textContent = 'Strong Match';
    descEl.textContent = 'Excellent candidate fit! Your technical background aligns directly with the target requirements.';
    statusBadge.className = 'badge badge-success';
    statusBadge.textContent = 'Highly Aligned';
  } else if (score >= 50) {
    circle.style.stroke = 'var(--warning)';
    titleEl.textContent = 'Moderate Alignment';
    descEl.textContent = 'Good foundational skills with actionable gaps to bridge before submission.';
    statusBadge.className = 'badge badge-warning';
    statusBadge.textContent = 'Growth Candidate';
  } else {
    circle.style.stroke = 'var(--danger)';
    titleEl.textContent = 'Significant Upskilling Needed';
    descEl.textContent = 'Several required competencies are missing from the provided profile.';
    statusBadge.className = 'badge badge-danger';
    statusBadge.textContent = 'Gaps Detected';
  }

  document.getElementById('model-badge').textContent = `Model: ${data.model_version || 'v1.0.0'}`;
  document.getElementById('latency-badge').textContent = `Latency: ${data.latency_ms || 12} ms`;

  // Render Matched Skills
  const matchedContainer = document.getElementById('matched-skills-container');
  matchedContainer.innerHTML = '';
  const matched = data.matched_skills || [];
  document.getElementById('matched-count').textContent = matched.length;

  if (matched.length > 0) {
    matched.forEach(sk => {
      const tag = document.createElement('span');
      tag.className = 'skill-tag matched';
      tag.innerHTML = `
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
          <polyline points="20 6 9 17 4 12"></polyline>
        </svg>
        ${UI.escapeHtml(sk)}
      `;
      matchedContainer.appendChild(tag);
    });
  } else {
    matchedContainer.innerHTML = '<span style="color: var(--text-tertiary); font-size: 13px;">No direct matching skills found in description.</span>';
  }

  // Render Skill Gaps
  const gapContainer = document.getElementById('missing-skills-container');
  gapContainer.innerHTML = '';
  const gaps = data.missing_skills || [];
  document.getElementById('gap-count').textContent = gaps.length;

  if (gaps.length > 0) {
    gaps.forEach(g => {
      const name = typeof g === 'string' ? g : g.skill;
      const priority = typeof g === 'object' && g.importance ? g.importance : 'medium';
      const tag = document.createElement('span');
      tag.className = 'skill-tag gap';
      tag.innerHTML = `
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
          <circle cx="12" cy="12" r="10"></circle><line x1="12" y1="8" x2="12" y2="12"></line><line x1="12" y1="16" x2="12.01" y2="16"></line>
        </svg>
        ${UI.escapeHtml(name)}
        <span class="gap-level-chip">${priority}</span>
      `;
      gapContainer.appendChild(tag);
    });
  } else {
    gapContainer.innerHTML = '<span style="color: var(--success); font-size: 13px;">Zero critical gaps! Full skill overlap identified.</span>';
  }

  // Reveal 1-click track button
  document.getElementById('track-job-btn').style.display = 'inline-flex';

  // Trigger Recruiter AI narrative
  currentAnalysisId = data.id;
  fetchAIExplanation(data.id);
}

async function fetchAIExplanation(analysisId) {
  const summaryEl = document.getElementById('guidance-summary');
  const strengthsEl = document.getElementById('guidance-strengths');
  const growthEl = document.getElementById('guidance-growth');
  const verdictEl = document.getElementById('ai-verdict-badge');

  summaryEl.innerHTML = '<span class="spinner"></span> Synthesizing AI explanation with active LLM...';
  strengthsEl.innerHTML = '<li style="color: var(--text-tertiary);">Evaluating verified competencies...</li>';
  growthEl.innerHTML = '<li style="color: var(--text-tertiary);">Analyzing high-priority skill gaps...</li>';
  verdictEl.textContent = 'Evaluating';

  try {
    const aiData = await API.ai.explain(analysisId);
    const exp = aiData.explanation;
    if (exp) {
      summaryEl.textContent = exp.summary || 'Summary generated.';
      verdictEl.textContent = exp.match_verdict || 'Evaluated';

      strengthsEl.innerHTML = '';
      (exp.strengths || []).forEach(s => {
        const li = document.createElement('li');
        li.textContent = s;
        strengthsEl.appendChild(li);
      });

      growthEl.innerHTML = '';
      (exp.areas_for_growth || []).forEach(g => {
        const li = document.createElement('li');
        li.textContent = g;
        growthEl.appendChild(li);
      });
      return;
    }
  } catch (err) {
    console.warn('AI explain notice:', err);
  }

  summaryEl.textContent = 'Analysis complete. Review matched competencies and targeted skill gaps above.';
  verdictEl.textContent = 'Complete';
}

async function generateInterviewPrep() {
  if (!currentAnalysisId) {
    UI.showToast('Please run a fit analysis first before generating interview questions.', 'warning');
    return;
  }

  const btn = document.getElementById('generate-prep-btn');
  const spinner = document.getElementById('prep-spinner');
  const btnText = document.getElementById('prep-btn-text');
  const resultsContainer = document.getElementById('interview-prep-results');

  btn.disabled = true;
  spinner.style.display = 'inline-block';
  btnText.textContent = 'Generating Tailored Questions...';

  try {
    const aiData = await API.ai.interviewPrep(currentAnalysisId);
    const prep = aiData.interview_prep;
    if (prep) {
      resultsContainer.style.display = 'block';

      // Technical questions
      const techList = document.getElementById('tech-questions-list');
      techList.innerHTML = '';
      (prep.technical_questions || []).forEach(q => {
        const card = document.createElement('div');
        card.className = 'interview-q-card';
        card.innerHTML = `
          <div class="interview-q-title">
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="var(--accent)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><line x1="16" y1="13" x2="8" y2="13"></line><line x1="16" y1="17" x2="8" y2="17"></line><polyline points="10 9 9 9 8 9"></polyline></svg>
            ${UI.escapeHtml(q.question)}
          </div>
          <div class="interview-q-concept"><strong>Core Focus:</strong> ${UI.escapeHtml(q.expected_key_concepts || 'System fundamentals')}</div>
          <div class="interview-q-tip">${UI.escapeHtml(q.tip || 'Structure response clearly with trade-offs.')}</div>
        `;
        techList.appendChild(card);
      });

      // Behavioral questions
      const behList = document.getElementById('behavioral-questions-list');
      behList.innerHTML = '';
      (prep.behavioral_questions || []).forEach(b => {
        const card = document.createElement('div');
        card.className = 'interview-q-card';
        card.innerHTML = `
          <div class="interview-q-title">
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="var(--purple)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><polygon points="12 8 8 12 12 16 16 12 12 8"></polygon></svg>
            ${UI.escapeHtml(b.question)}
          </div>
          <div class="interview-q-tip" style="border-left-color: var(--purple);"><strong>STAR Focus:</strong> ${UI.escapeHtml(b.star_focus || 'Situation, Task, Action, Result')}</div>
        `;
        behList.appendChild(card);
      });

      // Tactical tips
      const tipsList = document.getElementById('prep-tips-list');
      tipsList.innerHTML = '';
      (prep.preparation_tips || []).forEach(t => {
        const li = document.createElement('li');
        li.textContent = t;
        tipsList.appendChild(li);
      });

      btnText.textContent = '✓ Interview Questions Generated';
      UI.showToast('Interview preparation guide generated!', 'success');
      return;
    }
  } catch (err) {
    console.error('Interview prep error:', err);
    UI.showToast('Could not generate interview questions.', 'error');
  } finally {
    btn.disabled = false;
    spinner.style.display = 'none';
    if (btnText.textContent !== '✓ Interview Questions Generated') {
      btnText.textContent = 'Generate Tailored Interview Questions';
    }
  }
}

async function askRAG() {
  const query = document.getElementById('rag-query-input').value.trim();
  if (!query) return;

  const container = document.getElementById('rag-response-container');
  container.innerHTML = '<div style="color: var(--text-tertiary); font-size: 13px; padding: 10px 0;"><span class="spinner"></span> Querying multi-tenant vector intelligence...</div>';

  try {
    const data = await API.rag.query(query, 3);
    container.innerHTML = `
      <div style="background: var(--surface-inset); border: 1px solid var(--border-subtle); border-radius: var(--radius-md); padding: 14px; margin-top: 10px;">
        <h5 style="color: var(--accent); margin-bottom: 6px; font-size: 13px; font-weight: 600;">Answer:</h5>
        <p style="font-size: 13px; line-height: 1.5; color: var(--text-primary); margin-bottom: 12px;">${UI.escapeHtml(data.answer)}</p>
        
        <div>
          <div style="font-size: 11px; font-weight: 600; color: var(--text-tertiary); text-transform: uppercase; margin-bottom: 6px;">Verified Citations:</div>
          ${(data.citations || []).map(c => `
            <div class="citation-card-box">
              <div class="citation-header">
                <span>Chunk #${c.chunk_id || 1} • Similarity: ${(c.relevance_score * 100).toFixed(0)}%</span>
              </div>
              <div class="citation-snippet">"${UI.escapeHtml(c.snippet)}"</div>
            </div>
          `).join('')}
        </div>
      </div>
    `;
  } catch (err) {
    console.error('RAG query error:', err);
    container.innerHTML = '<div style="color: var(--warning-text); font-size: 13px; padding: 8px 0;">Upload and index a resume document first to search verified vector citations.</div>';
  }
}

// ==========================================================================
// Kanban Pipeline
// ==========================================================================

async function loadKanbanBoard() {
  try {
    await ensureAuthSession();
    const data = await API.applications.list();
    const apps = data.items || [];

    let cApplied = 0, cScreening = 0, cInterviewing = 0, cOffered = 0, cRejected = 0;
    const cols = {
      applied: document.getElementById('col-applied'),
      screening: document.getElementById('col-screening'),
      interviewing: document.getElementById('col-interviewing'),
      offered: document.getElementById('col-offered'),
      rejected: document.getElementById('col-rejected'),
      withdrawn: document.getElementById('col-rejected')
    };

    Object.values(cols).forEach(c => { if (c) c.innerHTML = ''; });

    apps.forEach(app => {
      const st = (app.status || 'applied').toLowerCase();
      if (st === 'applied') cApplied++;
      else if (st === 'screening') cScreening++;
      else if (st === 'interviewing') cInterviewing++;
      else if (st === 'offered') cOffered++;
      else cRejected++;

      const targetCol = cols[st] || cols.applied;
      if (!targetCol) return;

      const jobTitle = app.job ? app.job.title : 'Software Engineer';
      const company = app.job ? app.job.company : 'Company';
      const location = app.job && app.job.location ? app.job.location : 'Remote';
      const appliedDate = new Date(app.applied_at || app.created_at).toLocaleDateString(undefined, { month: 'short', day: 'numeric' });

      const card = document.createElement('div');
      card.className = 'kanban-app-card';
      card.setAttribute('data-app-id', app.id);
      UI.makeCardDraggable(card, app.id);

      card.innerHTML = `
        <div class="kanban-job-title">${UI.escapeHtml(jobTitle)}</div>
        <div class="kanban-company">@ ${UI.escapeHtml(company)}</div>
        <div class="kanban-meta-row">
          <span>📍 ${UI.escapeHtml(location)}</span>
          <span>📅 ${appliedDate}</span>
        </div>
        ${app.notes ? `<div class="kanban-notes-box">"${UI.escapeHtml(app.notes)}"</div>` : ''}
        <div class="kanban-card-actions">
          <select style="padding: 3px 20px 3px 6px; font-size: 11px; width: auto;" onchange="updateApplicationStage(${app.id}, this.value)">
            <option value="applied" ${st === 'applied' ? 'selected' : ''}>Applied</option>
            <option value="screening" ${st === 'screening' ? 'selected' : ''}>Screening</option>
            <option value="interviewing" ${st === 'interviewing' ? 'selected' : ''}>Interviewing</option>
            <option value="offered" ${st === 'offered' ? 'selected' : ''}>Offered</option>
            <option value="rejected" ${st === 'rejected' ? 'selected' : ''}>Archived</option>
          </select>
          <button class="btn btn-sm btn-ghost" style="color: var(--danger-text); padding: 2px 6px;" onclick="deleteApplication(${app.id})" title="Delete Application">
            Delete
          </button>
        </div>
      `;
      targetCol.appendChild(card);
    });

    // Update KPI stats
    const setTxt = (id, val) => { const el = document.getElementById(id); if (el) el.textContent = val; };
    setTxt('stat-total', apps.length);
    setTxt('stat-screening', cScreening);
    setTxt('stat-interviewing', cInterviewing);
    setTxt('stat-offers', cOffered);

    setTxt('count-applied', cApplied);
    setTxt('count-screening', cScreening);
    setTxt('count-interviewing', cInterviewing);
    setTxt('count-offered', cOffered);
    setTxt('count-rejected', cRejected);

  } catch (err) {
    console.warn('Kanban load notice:', err);
  }
}

async function updateApplicationStage(appId, newStage) {
  try {
    await API.applications.updateStatus(appId, newStage);
    UI.showToast(`Application moved to ${newStage.charAt(0).toUpperCase() + newStage.slice(1)}`, 'info');
    loadKanbanBoard();
  } catch (err) {
    console.error('Update stage error:', err);
    UI.showToast('Could not update application stage.', 'error');
  }
}

async function deleteApplication(appId) {
  const confirmed = await UI.showConfirm('Delete Application', 'Are you sure you want to remove this job application from your pipeline?', 'Delete', true);
  if (!confirmed) return;

  try {
    await API.applications.delete(appId);
    UI.showToast('Application removed.', 'info');
    loadKanbanBoard();
  } catch (err) {
    console.error('Delete application error:', err);
    UI.showToast('Could not delete application.', 'error');
  }
}

async function submitAddJobApplication() {
  const title = document.getElementById('add-job-title').value.trim();
  const company = document.getElementById('add-job-company').value.trim();
  const location = document.getElementById('add-job-location').value.trim() || 'Remote';
  const stage = document.getElementById('add-job-status').value;
  const notes = document.getElementById('add-job-notes').value.trim();

  if (!title || !company) {
    UI.showToast('Please enter both Job Title and Company.', 'warning');
    return;
  }

  try {
    const job = await API.jobs.create(title, company, location, `${title} role at ${company}. Tracked in CareerAI.`);
    const app = await API.applications.create(job.id, notes);

    if (stage !== 'applied') {
      await API.applications.updateStatus(app.id, stage);
    }

    UI.closeModal('modal-add-job');
    document.getElementById('form-add-job').reset();
    UI.showToast(`Tracked "${title}" at ${company}!`, 'success');
    loadKanbanBoard();
    switchAppTab('kanban');

  } catch (err) {
    console.error('Add job error:', err);
    UI.showToast('Could not save application.', 'error');
  }
}

function trackAnalyzedJobInKanban() {
  const title = document.getElementById('job-title-input').value.trim() || 'Analyzed Role';
  const company = document.getElementById('job-company-input').value.trim() || 'Target Company';
  const skills = document.getElementById('job-skills').value.trim();

  document.getElementById('add-job-title').value = title;
  document.getElementById('add-job-company').value = company;
  document.getElementById('add-job-notes').value = `Compatibility score analyzed in CareerAI. Required skills: ${skills}`;
  UI.openModal('modal-add-job');
}

// ==========================================================================
// Profile & Skills Management
// ==========================================================================

async function loadUserProfile() {
  if (!currentUser) return;
  try {
    const prof = await API.profiles.get(currentUser.id);
    document.getElementById('prof-headline').value = prof.headline || '';
    document.getElementById('prof-location').value = prof.location || '';
    document.getElementById('prof-yoe').value = prof.years_of_experience || 0;
    document.getElementById('prof-summary').value = prof.summary || '';
    document.getElementById('prof-linkedin').value = prof.linkedin_url || '';
    document.getElementById('prof-github').value = prof.github_url || '';
  } catch (e) {
    console.warn('Profile load notice:', e);
  }
}

async function saveProfile() {
  if (!currentUser) return;
  const payload = {
    headline: document.getElementById('prof-headline').value.trim(),
    location: document.getElementById('prof-location').value.trim(),
    years_of_experience: parseFloat(document.getElementById('prof-yoe').value) || 0,
    summary: document.getElementById('prof-summary').value.trim(),
    linkedin_url: document.getElementById('prof-linkedin').value.trim(),
    github_url: document.getElementById('prof-github').value.trim()
  };

  try {
    await API.profiles.update(currentUser.id, payload);
    UI.showToast('Profile updated successfully!', 'success');
  } catch (e) {
    console.error('Save profile error:', e);
    UI.showToast('Could not update profile.', 'error');
  }
}

function loadSavedProfileIntoResume() {
  const summary = document.getElementById('prof-summary').value.trim();
  const headline = document.getElementById('prof-headline').value.trim();
  if (summary || headline) {
    document.getElementById('resume-text').value = `${headline}\n\n${summary}`;
    UI.showToast('Profile headline and summary loaded into resume field!', 'info');
  } else {
    UI.showToast('Please save your headline and summary in "Profile & Skills" first.', 'warning');
  }
}

async function loadUserSkills() {
  if (!currentUser) return;
  try {
    const skills = await API.skills.getUserSkills(currentUser.id);
    document.getElementById('my-skills-count').textContent = `${skills.length} Skills`;
    const container = document.getElementById('my-skills-list');
    container.innerHTML = '';

    if (skills.length === 0) {
      container.innerHTML = '<span style="color: var(--text-tertiary); font-size: 13px;">No skills attached yet. Add your key skills above!</span>';
      return;
    }

    skills.forEach(us => {
      const skillName = us.skill ? us.skill.name : 'Skill';
      const item = document.createElement('div');
      item.className = 'skill-tag-manager-item';
      item.innerHTML = `
        <div style="display: flex; align-items: center; gap: 8px;">
          <span class="skill-tag-name">${UI.escapeHtml(skillName)}</span>
          <span class="badge badge-accent">${us.proficiency}</span>
          <span style="font-size: 11px; color: var(--text-tertiary);">${us.years_of_experience || 1} yrs</span>
        </div>
        <button class="btn btn-sm btn-ghost" style="color: var(--danger-text); padding: 4px;" onclick="deleteUserSkill(${us.skill_id})" title="Remove skill">
          &times;
        </button>
      `;
      container.appendChild(item);
    });
  } catch (e) {
    console.warn('Skills load notice:', e);
  }
}

async function addSkillToProfile() {
  const name = document.getElementById('new-skill-name').value.trim();
  const prof = document.getElementById('new-skill-prof').value;
  const yoe = parseFloat(document.getElementById('new-skill-yoe').value) || 1.0;

  if (!name) {
    UI.showToast('Please enter a skill name.', 'warning');
    return;
  }

  try {
    let skillId = null;
    try {
      const s = await API.skills.createSkill(name);
      skillId = s.id;
    } catch (e) {
      // Find existing
      const listData = await API.skills.getCanonical();
      const match = (listData.items || []).find(s => s.name.toLowerCase() === name.toLowerCase());
      if (match) skillId = match.id;
    }

    if (skillId && currentUser) {
      await API.skills.addUserSkill(currentUser.id, skillId, prof, yoe);
      document.getElementById('new-skill-name').value = '';
      loadUserSkills();
      UI.showToast(`Added ${name} to your skills!`, 'success');
    }
  } catch (e) {
    console.error('Add skill error:', e);
    UI.showToast('Could not add skill.', 'error');
  }
}

async function deleteUserSkill(skillId) {
  if (!currentUser) return;
  try {
    await API.skills.deleteUserSkill(currentUser.id, skillId);
    loadUserSkills();
    UI.showToast('Skill removed.', 'info');
  } catch (e) {
    console.error('Delete skill error:', e);
  }
}

// ==========================================================================
// Document Library & Management
// ==========================================================================

async function loadDocumentsList() {
  try {
    await ensureAuthSession();
    const data = await API.documents.list();
    const docs = data.items || [];
    const tbody = document.getElementById('documents-table-body');
    if (!tbody) return;
    tbody.innerHTML = '';

    if (docs.length === 0) {
      tbody.innerHTML = '<tr><td colspan="7" style="text-align: center; color: var(--text-tertiary); padding: 24px;">No documents uploaded yet.</td></tr>';
      return;
    }

    docs.forEach(doc => {
      const sizeKb = ((doc.file_size_bytes || 0) / 1024).toFixed(1);
      const dateStr = new Date(doc.created_at).toLocaleDateString();
      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td>
          <div class="table-file-name">
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline></svg>
            ${UI.escapeHtml(doc.filename)}
          </div>
        </td>
        <td><span class="badge badge-purple">${doc.doc_type || 'resume'}</span></td>
        <td>${sizeKb} KB</td>
        <td><span class="badge badge-success">${doc.status}</span></td>
        <td><span class="badge badge-accent">Indexed</span></td>
        <td>${dateStr}</td>
        <td>
          <div class="table-actions-cell">
            <button class="btn btn-sm btn-secondary" onclick="analyzeDocumentFromLibrary(${doc.id})">Analyze</button>
            <button class="btn btn-sm btn-secondary" onclick="indexDocumentRAG(${doc.id})">Index RAG</button>
            <a href="/api/v1/documents/${doc.id}/download" target="_blank" class="btn btn-sm btn-secondary">Download</a>
            <button class="btn btn-sm btn-danger" onclick="deleteDocumentFromLibrary(${doc.id})" title="Delete document">Delete</button>
          </div>
        </td>
      `;
      tbody.appendChild(tr);
    });
  } catch (e) {
    console.warn('Documents list error:', e);
  }
}

async function handleLibraryUpload(input) {
  if (input.files && input.files[0]) {
    const file = input.files[0];
    try {
      await API.documents.upload(file);
      UI.showToast(`Uploaded ${file.name}!`, 'success');
      loadDocumentsList();
    } catch (e) {
      console.error('Upload document error:', e);
      UI.showToast('Could not upload document.', 'error');
    }
  }
}

async function analyzeDocumentFromLibrary(docId) {
  switchAppTab('analyzer');
  switchMode('file');
  document.getElementById('file-label').textContent = `Document ID: #${docId} loaded. Running analysis...`;

  try {
    const jobDesc = document.getElementById('job-desc').value;
    const skillsRaw = document.getElementById('job-skills').value;
    const jobSkills = skillsRaw.split(',').map(s => s.trim()).filter(Boolean);

    const mlData = await API.ml.analyze({
      document_id: docId,
      job_description: jobDesc,
      job_skills: jobSkills
    });

    renderResults(mlData);
    UI.showToast(`Analyzed Document #${docId}!`, 'success');
  } catch (err) {
    console.error('Document analyze error:', err);
    UI.showToast('Could not analyze document.', 'error');
  }
}

async function indexDocumentRAG(docId) {
  try {
    const data = await API.rag.index(docId);
    UI.showToast(`Indexed ${data.chunks_indexed} semantic chunks into multi-tenant vector store!`, 'success');
  } catch (e) {
    console.error('RAG indexing error:', e);
    UI.showToast('Could not index document into RAG.', 'error');
  }
}

async function deleteDocumentFromLibrary(docId) {
  const confirmed = await UI.showConfirm('Delete Document', 'Are you sure you want to delete this document and its vector embeddings?', 'Delete', true);
  if (!confirmed) return;

  try {
    await API.documents.delete(docId);
    UI.showToast('Document deleted.', 'info');
    loadDocumentsList();
  } catch (e) {
    console.error('Delete doc error:', e);
    UI.showToast('Could not delete document.', 'error');
  }
}

// ==========================================================================
// Historical Analyses
// ==========================================================================

async function loadAnalysisHistory() {
  try {
    await ensureAuthSession();
    const data = await API.ml.listAnalyses();
    const items = data.items || [];
    const tbody = document.getElementById('history-table-body');
    if (!tbody) return;
    tbody.innerHTML = '';

    if (items.length === 0) {
      tbody.innerHTML = '<tr><td colspan="8" style="text-align: center; color: var(--text-tertiary); padding: 24px;">No past analyses recorded. Run an evaluation to start tracking history!</td></tr>';
      return;
    }

    items.forEach(a => {
      const score = Math.round(a.compatibility_score || 0);
      const scoreClass = score >= 80 ? 'badge-success' : (score >= 50 ? 'badge-warning' : 'badge-danger');
      const matchedCount = (a.matched_skills || []).length;
      const gapsCount = (a.missing_skills || []).length;
      const dateStr = new Date(a.created_at).toLocaleString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });

      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td><code>#${a.id}</code></td>
        <td><span class="badge ${scoreClass}" style="font-size: 13px; font-weight: 700;">${score}%</span></td>
        <td>${matchedCount} skills</td>
        <td><span style="color: var(--warning-text);">${gapsCount} gaps</span></td>
        <td><code>${a.model_version || 'v1.0.0'}</code></td>
        <td>${a.latency_ms || 15} ms</td>
        <td style="color: var(--text-tertiary); font-size: 12px;">${dateStr}</td>
        <td>
          <div class="table-actions-cell">
            <button class="btn btn-sm btn-primary" onclick="reloadHistoryAnalysis(${a.id})">Reload</button>
          </div>
        </td>
      `;
      tbody.appendChild(tr);
    });
  } catch (e) {
    console.warn('History load notice:', e);
  }
}

async function reloadHistoryAnalysis(analysisId) {
  try {
    const data = await API.ml.getAnalysis(analysisId);
    switchAppTab('analyzer');
    renderResults(data);
    UI.showToast(`Restored Analysis #${analysisId}!`, 'info');
  } catch (e) {
    console.error('Reload analysis error:', e);
    UI.showToast('Could not restore analysis.', 'error');
  }
}

// ==========================================================================
// Modals & Authentication
// ==========================================================================

async function openMetricsModal() {
  UI.openModal('modal-metrics');
  try {
    const [met, ready, ai] = await Promise.all([
      API.system.getMetrics().catch(() => null),
      API.system.getReadiness().catch(() => null),
      API.ai.getStatus().catch(() => null)
    ]);

    if (met) {
      document.getElementById('metric-ram').textContent = `${met.memory_rss_mb} MB`;
      document.getElementById('metric-python').textContent = `Python ${met.python_version}`;
      document.getElementById('metric-threads').textContent = `${met.threads_count} threads`;
      document.getElementById('metric-model').textContent = met.model_version;
    }

    if (ready) {
      document.getElementById('metric-db').textContent = `Online (${ready.checks ? ready.checks.database : 'healthy'})`;
    }

    if (ai) {
      document.getElementById('metric-llm').textContent = `${ai.provider_label} (${ai.model})`;
    }
  } catch (e) {
    console.warn('Metrics modal notice:', e);
  }
}

function openAuthModal() {
  UI.openModal('modal-auth');
}

function openAddJobModal() {
  UI.openModal('modal-add-job');
}

function switchAuthTab(mode) {
  const isLogin = mode === 'login';
  document.getElementById('auth-tab-login').classList.toggle('active', isLogin);
  document.getElementById('auth-tab-register').classList.toggle('active', !isLogin);
  document.getElementById('form-login').style.display = isLogin ? 'block' : 'none';
  document.getElementById('form-register').style.display = isLogin ? 'none' : 'block';
}

async function submitLogin() {
  const email = document.getElementById('login-email').value.trim();
  const pass = document.getElementById('login-pass').value;

  try {
    const data = await API.auth.login(email, pass);
    API.setToken(data.tokens.access_token);
    currentUser = data.user;
    updateUserPillUI();
    UI.closeModal('modal-auth');
    UI.showToast(`Welcome back, ${currentUser.full_name || currentUser.email}!`, 'success');
    loadKanbanBoard();
    loadUserProfile();
    loadUserSkills();
    loadDocumentsList();
    loadAnalysisHistory();
  } catch (e) {
    UI.showToast(e.message || 'Login failed', 'error');
  }
}

async function submitRegister() {
  const name = document.getElementById('reg-name').value.trim();
  const email = document.getElementById('reg-email').value.trim();
  const pass = document.getElementById('reg-pass').value;

  try {
    const data = await API.auth.register(name, email, pass);
    API.setToken(data.tokens.access_token);
    currentUser = data.user;
    updateUserPillUI();
    UI.closeModal('modal-auth');
    UI.showToast(`Account created! Welcome, ${name}!`, 'success');
    loadKanbanBoard();
    loadUserProfile();
    loadUserSkills();
    loadDocumentsList();
    loadAnalysisHistory();
  } catch (e) {
    UI.showToast(e.message || 'Registration failed', 'error');
  }
}

function resetToGuestSession() {
  API.clearToken();
  currentUser = null;
  UI.closeModal('modal-auth');
  ensureAuthSession().then(() => {
    loadKanbanBoard();
    loadUserProfile();
    loadUserSkills();
    loadDocumentsList();
    loadAnalysisHistory();
    UI.showToast('Switched to fresh guest session!', 'info');
  });
}
