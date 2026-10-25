// Kasihub frontend script
// connects to app.py backend using session cookies

let currentUser = null; // stores logged in user info
let currentReportFilter = 'all';
let currentOutageFilter = 'all';

// helper function to make api calls easier
async function api(url, options = {}) {
    const res = await fetch(url, {
        credentials: 'same-origin', // sends flask session cookie
        headers: { 'Content-Type': 'application/json' },
        ...options
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
        throw new Error(data.message || 'something went wrong');
    }
    return data;
}

// prevents xss attacks when injecting html
function escapeHtml(str) {
    if (str === null || str === undefined) return '';
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

function $(id) {
    return document.getElementById(id);
}

// ---------- login stuff ----------

async function doLogin() {
    const btn = $('login-btn');
    const errEl = $('login-error');
    errEl.textContent = '';

    const username = $('login-username').value.trim();
    const role = $('login-role').value;

    if (!username) {
        errEl.textContent = 'please enter a username';
        return;
    }

    btn.disabled = true;
    btn.textContent = 'logging in...';

    try {
        const data = await api('/api/login', {
            method: 'POST',
            body: JSON.stringify({ username, role })
        });

        currentUser = {
            id: data.id,
            username: data.username,
            role: data.role,
            location: data.location
        };

        enterApp();
    } catch (err) {
        errEl.textContent = err.message;
    } finally {
        btn.disabled = false;
        btn.textContent = 'Log In';
    }
}

async function doLogout() {
    try {
        await api('/api/logout');
    } catch (e) {
        // ignore errors here, we just want to clear the frontend state
    }

    currentUser = null;
    $('user-info').innerHTML = '';
    document.querySelectorAll('.section').forEach(s => s.classList.add('hidden'));
    $('login-section').classList.remove('hidden');
    $('login-username').value = '';
    $('login-error').textContent = '';
}

function enterApp() {
    $('login-section').classList.add('hidden');

    $('user-info').innerHTML =
        '<strong>' + escapeHtml(currentUser.username) + '</strong><br>' +
        '<span style="opacity:0.7">' + escapeHtml(currentUser.role) + '</span><br>' +
        '<span style="opacity:0.7">' + escapeHtml(currentUser.location) + '</span>';

    // only show "My Stores" if they are a business account
    $('nav-stores').classList.toggle('hidden', currentUser.role !== 'business');

    showSection('dashboard');
    loadDashboard();
}

// ---------- navigation ----------

function showSection(name) {
    document.querySelectorAll('.section').forEach(s => s.classList.add('hidden'));

    const target = $(name + '-section');
    if (target) target.classList.remove('hidden');

    document.querySelectorAll('.nav-links li').forEach(li => li.classList.remove('active'));
    const activeLink = Array.from(document.querySelectorAll('.nav-links li'))
        .find(li => (li.getAttribute('onclick') || '').includes("'" + name + "'"));
    if (activeLink) activeLink.classList.add('active');

    // load data when section is opened instead of all at once
    if (name === 'dashboard') loadDashboard();
    if (name === 'reports') loadReports();
    if (name === 'resources') loadResourcesTab('stores-tab');
    if (name === 'outages') loadOutages();
    if (name === 'profile') loadProfile();
    if (name === 'stores') loadManageStores();
}

// ---------- dashboard ----------

async function loadDashboard() {
    try {
        const stats = await api('/api/stats');
        $('dash-water-val').textContent = stats.water + '%';
        $('dash-water-bar').innerHTML =
            '<div class="progress-fill" style="width:' + stats.water + '%"></div>';
        $('dash-power').textContent = stats.power.replace('_', ' ');
    } catch (e) {
        $('dash-water-val').textContent = 'failed to load';
        $('dash-power').textContent = 'failed to load';
    }

    if (currentUser) {
        try {
            const risk = await api('/api/predict-risk/' + currentUser.id);
            const el = $('dash-risk');
            el.textContent = risk.risk_score + '/100 (' + risk.severity + ')';
            el.className = 'risk-' + risk.severity;

            $('dash-tips').innerHTML = risk.predictions.length
                ? risk.predictions.map(t => '<li>' + escapeHtml(t) + '</li>').join('')
                : '<li>all good for now 👍</li>';
        } catch (e) {
            $('dash-risk').textContent = 'N/A';
            $('dash-tips').innerHTML = '<li>could not calculate risk.</li>';
        }
    }

    try {
        const w = await api('/api/weather');
        $('dash-weather').textContent =
            w.temp + '°C · ' + w.desc + (w.warning && w.warning !== 'None' ? ' · ⚠️ ' + w.warning : '');
    } catch (e) {
        $('dash-weather').textContent = 'weather unavailable';
    }
}

// ---------- reports ----------

async function loadReports() {
    const list = $('reports-list');
    list.innerHTML = '<p>loading reports...</p>';

    try {
        const url = currentReportFilter === 'all'
            ? '/api/reports'
            : '/api/reports?category=' + encodeURIComponent(currentReportFilter);

        const reports = await api(url);

        if (!reports.length) {
            list.innerHTML = '<p>no reports found.</p>';
            return;
        }

        list.innerHTML = reports.map(r => {
            const canResolve = r.status === 'open' && currentUser && currentUser.role === 'public_service';
            return (
                '<div class="list-item ' + (r.status === 'resolved' ? 'resolved' : '') + '">' +
                    '<div class="item-content">' +
                        '<div class="item-title">' + escapeHtml(r.issue) + '</div>' +
                        '<div classitem-meta">' +
                            escapeHtml(r.category) + ' · ' + escapeHtml(r.location) +
                            ' · by ' + escapeHtml(r.user) +
                            ' · <span class="badge badge-' + escapeHtml(r.status) + '">' +
                                escapeHtml(r.status) + '</span>' +
                        '</div>' +
                    '</div>' +
                    (canResolve
                        ? '<button class="success" data-resolve="' + r.id + '">Resolve</button>'
                        : '') +
                '</div>'
            );
        }).join('');

        // using event delegation instead of inline onclick because its cleaner
        list.querySelectorAll('[data-resolve]').forEach(btn => {
            btn.addEventListener('click', () => resolveReport(btn.dataset.resolve));
        });

    } catch (e) {
        list.innerHTML = '<p class="error-msg">could not load reports: ' + escapeHtml(e.message) + '</p>';
    }
}

async function resolveReport(id) {
    try {
        await api('/api/report/' + id + '/resolve', { method: 'POST' });
        loadReports();
    } catch (e) {
        alert('could not resolve: ' + e.message);
    }
}

function openReportModal() {
    $('report-location').value = currentUser.location;
    $('report-modal').classList.remove('hidden');
}

function closeReportModal() {
    $('report-modal').classList.add('hidden');
    $('report-issue').value = '';
}

async function submitReport() {
    const issue = $('report-issue').value.trim();
    if (!issue) {
        alert('please describe the issue');
        return;
    }

    const btn = $('submit-report-btn');
    btn.disabled = true;

    try {
        await api('/api/report', {
            method: 'POST',
            body: JSON.stringify({
                issue: issue,
                category: $('report-category').value,
                location: $('report-location').value.trim() || currentUser.location
            })
        });

        closeReportModal();
        loadReports();
    } catch (e) {
        alert('failed to submit: ' + e.message);
    } finally {
        btn.disabled = false;
    }
}

// ---------- resources tab stuff ----------

async function loadResourcesTab(tabId) {
    document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));

    $(tabId).classList.add('active');
    const btn = Array.from(document.querySelectorAll('.tab-btn')).find(b => b.dataset.tab === tabId);
    if (btn) btn.classList.add('active');

    if (tabId === 'stores-tab') loadStoresList();
    if (tabId === 'services-tab') loadServicesList();
    if (tabId === 'helpers-tab') loadHelpers();
}

async function loadStoresList() {
    const list = $('stores-list');
    list.innerHTML = '<p>loading stores...</p>';

    try {
        const stores = await api('/api/stores');
        list.innerHTML = stores.map(s => `
            <div class="list-item">
                <div class="item-content">
                    <div class="item-title">${escapeHtml(s.name)}</div>
                    <div class="item-meta">${escapeHtml(s.type)} · ${escapeHtml(s.location)}</div>
                </div>
                <div>⚡ ${s.has_power ? '✅' : '❌'} &nbsp; 💧 ${s.has_water ? '✅' : '❌'}</div>
            </div>
        `).join('');
    } catch (e) {
        list.innerHTML = '<p class="error-msg">' + escapeHtml(e.message) + '</p>';
    }
}

async function loadServicesList() {
    const list = $('services-list');
    list.innerHTML = '<p>loading services...</p>';

    try {
        const services = await api('/api/services');
        list.innerHTML = services.map(s => `
            <div class="list-item">
                <div class="item-content">
                    <div class="item-title">${escapeHtml(s.name)}</div>
                    <div class="item-meta">${escapeHtml(s.type)} · ${escapeHtml(s.address)}</div>
                </div>
                <a href="tel:${escapeHtml(s.phone)}" class="outline" style="text-decoration:none">${escapeHtml(s.phone)}</a>
            </div>
        `).join('');
    } catch (e) {
        list.innerHTML = '<p class="error-msg">' + escapeHtml(e.message) + '</p>';
    }
}

async function loadHelpers() {
    const list = $('helpers-list');
    list.innerHTML = '<p>searching your area...</p>';

    try {
        // uses the logged in user's actual location instead of hardcoded "Diepsloot"
        const area = currentUser.location.split(' ')[0];
        const helpers = await api('/api/find-resources/' + encodeURIComponent(area));

        if (!helpers.length) {
            list.innerHTML = '<p>no neighbors with surplus water right now.</p>';
            return;
        }

        list.innerHTML = helpers.map(h => `
            <div class="list-item">
                <div class="item-content">
                    <div class="item-title">${escapeHtml(h.name)}</div>
                    <div class="item-meta">💧 ${h.water_level}% · ⚡ ${escapeHtml(h.power_status)}</div>
                </div>
            </div>
        `).join('');
    } catch (e) {
        list.innerHTML = '<p class="error-msg">' + escapeHtml(e.message) + '</p>';
    }
}

// ---------- outages ----------

async function loadOutages() {
    const list = $('outages-list');
    list.innerHTML = '<p>loading schedule...</p>';

    try {
        const url = currentOutageFilter === 'all'
            ? '/api/outages'
            : '/api/outages?type=' + encodeURIComponent(currentOutageFilter);

        const outages = await api(url);
        list.innerHTML = outages.map(o => `
            <div class="list-item">
                <div class="item-content">
                    <div class="item-title">${o.type === 'power' ? '⚡' : '💧'} ${escapeHtml(o.area)}</div>
                    <div class="item-meta">
                        ${escapeHtml(o.start_time)} → ${escapeHtml(o.end_time)} ·
                        ${escapeHtml(o.stage)} · ${escapeHtml(o.notes)}
                    </div>
                </div>
            </div>
        `).join('');
    } catch (e) {
        list.innerHTML = '<p class="error-msg">' + escapeHtml(e.message) + '</p>';
    }
}

// ---------- manage my stores (ownership check happens here too) ----------

async function loadManageStores() {
    const msg = $('store-manage-msg');
    const list = $('manage-stores-list');
    list.innerHTML = '';
    msg.textContent = 'loading...';

    try {
        const stores = await api('/api/stores');

        // filter to only the stores owned by this user
        // backend also checks this so even if someone edits the js they still get a 403
        const mine = stores.filter(s => s.owner_user_id === currentUser.id);

        if (!mine.length) {
            msg.textContent = "you don't own any registered stores yet. ask an admin to link one to your account.";
            return;
        }

        msg.textContent = 'these stores are linked to your account. update their live status below.';

        list.innerHTML = mine.map(s => `
            <div class="list-item">
                <div class="item-content">
                    <div class="item-title">${escapeHtml(s.name)}</div>
                    <div class="item-meta">${escapeHtml(s.type)} · ${escapeHtml(s.location)}</div>
                </div>
                <div style="display:flex; gap:0.5rem; align-items:center;">
                    <label><input type="checkbox" id="pwr-${s.id}" ${s.has_power ? 'checked' : ''}> Power</label>
                    <label><input type="checkbox" id="wat-${s.id}" ${s.has_water ? 'checked' : ''}> Water</label>
                    <button class="primary" data-save-store="${s.id}">Save</button>
                </div>
            </div>
        `).join('');

        list.querySelectorAll('[data-save-store]').forEach(btn => {
            btn.addEventListener('click', () => saveStoreStatus(btn.dataset.saveStore));
        });

    } catch (e) {
        msg.textContent = 'error: ' + e.message;
    }
}

async function saveStoreStatus(sid) {
    try {
        await api('/api/store/' + sid + '/status', {
            method: 'POST',
            body: JSON.stringify({
                has_power: $('pwr-' + sid).checked,
                has_water: $('wat-' + sid).checked
            })
        });
        alert('saved!');
    } catch (e) {
        // this is where "Not your store" would come back from the server
        alert('save failed: ' + e.message);
    }
}

// ---------- profile ----------

async function loadProfile() {
    try {
        const p = await api('/api/profile');
        $('profile-name').textContent = p.name;
        $('profile-role').textContent = p.role;
        $('profile-loc').textContent = p.location;
        $('profile-water').textContent = p.water_level;
        $('water-slider').value = p.water_level;
    } catch (e) {
        console.error(e);
    }
}

async function saveWaterLevel() {
    const level = parseInt($('water-slider').value, 10);
    try {
        const res = await api('/api/water-level', {
            method: 'POST',
            body: JSON.stringify({ water_level: level })
        });
        $('profile-water').textContent = res.water_level;
        $('water-status').textContent = 'updated ✅';
        setTimeout(() => $('water-status').textContent = '', 2000);
    } catch (e) {
        $('water-status').textContent = 'failed: ' + e.message;
    }
}

// ---------- event wiring ----------

document.addEventListener('DOMContentLoaded', () => {
    $('login-btn').addEventListener('click', doLogin);
    $('logout-btn').addEventListener('click', doLogout);
    $('new-report-btn').addEventListener('click', openReportModal);
    $('cancel-report-btn').addEventListener('click', closeReportModal);
    $('submit-report-btn').addEventListener('click', submitReport);
    $('save-water-btn').addEventListener('click', saveWaterLevel);

    // report category filters
    document.querySelectorAll('#reports-section .filter').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('#reports-section .filter').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            currentReportFilter = btn.dataset.cat;
            loadReports();
        });
    });

    // outage type filters
    document.querySelectorAll('#outages-section .filter').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('#outages-section .filter').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            currentOutageFilter = btn.dataset.type;
            loadOutages();
        });
    });

    // resource tabs
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.addEventListener('click', () => loadResourcesTab(btn.dataset.tab));
    });

    // pressing enter in the username field logs you in
    $('login-username').addEventListener('keydown', (e) => {
        if (e.key === 'Enter') doLogin();
    });

    // clicking outside the modal closes it
    $('report-modal').addEventListener('click', (e) => {
        if (e.target === $('report-modal')) closeReportModal();
    });

    // check if there is already a session when the page loads
    api('/api/profile')
        .then(user => {
            currentUser = { id: user.id, username: user.name, role: user.role, location: user.location };
            enterApp();
        })
        .catch(() => {
            // not logged in, just leave the login screen showing
        });
});