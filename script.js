// KasiHub Frontend Script (Glass UI Version)
// Communicates with app.py backend

let currentUser = null; // Stores current session user data
let currentReportFilter = 'all';
let currentOutageFilter = 'all';

// --- Helper Functions ---

// Safe API wrapper that handles credentials and errors
async function api(url, options = {}) {
    const res = await fetch(url, {
        credentials: 'same-origin', // Sends Flask session cookie
        headers: { 'Content-Type': 'application/json' },
        ...options
    });
    const data = await res.json().catch(() => ({}));
    
    if (!res.ok) {
        throw new Error(data.message || 'Something went wrong');
    }
    return data;
}

// Prevents XSS attacks when injecting HTML
function escapeHtml(str) {
    if (str === null || str === undefined) return '';
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

// Shortcut for getElementById
function $(id) {
    return document.getElementById(id);
}

// --- Authentication ---

async function doLogin() {
    const btn = $('login-form').querySelector('button');
    const msg = $('login-msg');
    msg.textContent = '';
    msg.style.color = '';

    const username = $('login-username').value.trim();
    const password = $('login-password').value;

    if (!username || !password) {
        msg.textContent = '❌ Please enter username and password';
        msg.style.color = '#ff0055';
        return;
    }

    btn.disabled = true;
    btn.textContent = 'Logging in...';

    try {
        const data = await api('/api/login', {
            method: 'POST',
            body: JSON.stringify({ username, password })
        });

        currentUser = {
            id: data.id,
            username: data.username,
            role: data.role,
            location: data.location
        };

        // Save to local storage for auto-login next time
        localStorage.setItem('user', JSON.stringify(currentUser));
        
        enterApp();
    } catch (err) {
        msg.textContent = '❌ ' + err.message;
        msg.style.color = '#ff0055';
    } finally {
        btn.disabled = false;
        btn.textContent = 'Log In 🚀';
    }
}

async function doRegister() {
    const btn = $('register-form').querySelector('button');
    const msg = $('reg-msg');
    msg.textContent = '';
    msg.style.color = '';

    const username = $('reg-username').value.trim();
    const password = $('reg-password').value;
    const location = $('reg-location').value.trim();
    const role = $('reg-role').value;

    if (!username || !password || !location) {
        msg.textContent = '❌ Please fill all fields';
        msg.style.color = '#ff0055';
        return;
    }

    if (password.length < 6) {
        msg.textContent = '❌ Password must be at least 6 characters';
        msg.style.color = '#ff0055';
        return;
    }

    btn.disabled = true;
    btn.textContent = 'Creating...';

    try {
        const data = await api('/api/register', {
            method: 'POST',
            body: JSON.stringify({ username, password, location, role })
        });

        currentUser = {
            id: data.user_id,
            username: data.username,
            role: role,
            location: location
        };

        localStorage.setItem('user', JSON.stringify(currentUser));
        enterApp();
    } catch (err) {
        msg.textContent = '❌ ' + err.message;
        msg.style.color = '#ff0055';
    } finally {
        btn.disabled = false;
        btn.textContent = 'Create Account ✨';
    }
}

function doLogout() {
    api('/api/logout').catch(() => {}); // Ignore errors on logout
    currentUser = null;
    localStorage.removeItem('user');
    location.reload();
}

// --- App Navigation & State ---

function enterApp() {
    // Switch Views
    $('auth-view').classList.remove('active');
    $('dashboard-view').classList.add('active');
    $('dashboard-view').style.display = 'flex';

    // Update User Info in Sidebar
    $('display-name').textContent = currentUser.username;
    $('display-role').textContent = currentUser.role;
    $('greeting-name').textContent = currentUser.username;

    // Handle Role-Based Visibility
    if (currentUser.role === 'business') {
        document.querySelectorAll('.business-only').forEach(el => el.style.display = 'block');
    } else {
        document.querySelectorAll('.business-only').forEach(el => el.style.display = 'none');
    }

    if (currentUser.role === 'public_service') {
        document.querySelectorAll('.saps-only').forEach(el => el.style.display = 'block');
    } else {
        document.querySelectorAll('.saps-only').forEach(el => el.style.display = 'none');
    }

    // Load Dashboard Data
    loadDashboard();
}

function switchTab(tabName) {
    // Hide all tab contents
    document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
    // Remove active class from all nav items
    document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));

    // Show target tab
    const target = $('tab-' + tabName);
    if (target) target.classList.add('active');

    // Highlight target nav item
    const navMap = {
        'home': 0,
        'reports': 1,
        'resources': 2,
        'outages': 3,
        'business': 4,
        'saps': 5
    };
    
    const navItems = document.querySelectorAll('.nav-item');
    if (navItems[navMap[tabName]]) {
        navItems[navMap[tabName]].classList.add('active');
    }

    // Load data specific to the tab
    if (tabName === 'reports') loadReports();
    if (tabName === 'resources') loadHelpers();
    if (tabName === 'outages') loadOutages();
    if (tabName === 'business') loadBusinessProfile();
    if (tabName === 'saps') loadSapsMap();
}

// --- Dashboard Logic ---

async function loadDashboard() {
    try {
        const stats = await api('/api/stats');
        
        // Update Water UI
        $('water-level').textContent = stats.water + '%';
        $('water-fill').style.width = stats.water + '%';
        $('water-slider').value = stats.water;

        // Update Power UI
        $('power-status').textContent = stats.power;
        const powerIcon = $('power-icon');
        if (stats.power === 'online') {
            powerIcon.className = 'fa-solid fa-plug status-icon online';
            powerIcon.style.color = '#00ff88';
        } else {
            powerIcon.className = 'fa-solid fa-plug status-icon offline';
            powerIcon.style.color = '#ff0055';
        }

    } catch (e) {
        console.error('Stats fetch error:', e);
    }

    // Fetch Risk Prediction
    if (currentUser) {
        try {
            const risk = await api('/api/predict-risk/' + currentUser.id);
            $('risk-score').textContent = risk.risk_score;
            
            const badge = $('risk-severity');
            badge.textContent = risk.severity.charAt(0).toUpperCase() + risk.severity.slice(1);
            badge.className = 'severity-badge severity-' + risk.severity;
            
            $('risk-action').textContent = risk.next_action;

            const list = $('prediction-list');
            list.innerHTML = '';
            if (risk.predictions.length) {
                risk.predictions.forEach(t => {
                    const li = document.createElement('li');
                    li.textContent = t;
                    list.appendChild(li);
                });
            } else {
                list.innerHTML = '<li>Everything looks good! 🌟</li>';
            }
        } catch (e) {
            console.error('Risk fetch error:', e);
        }
    }

    // Fetch Weather
    try {
        const w = await api('/api/weather');
        $('weather-temp').textContent = w.temp + '°C';
        $('weather-desc').textContent = w.desc;
    } catch (e) {
        console.error('Weather fetch error:', e);
    }
}

// --- Reports Logic ---

async function loadReports() {
    const list = $('reports-list');
    list.innerHTML = '<p style="text-align:center; opacity:0.7;">Loading reports...</p>';

    try {
        let url = '/api/reports';
        if (currentReportFilter !== 'all') {
            url += '?category=' + encodeURIComponent(currentReportFilter);
        }

        const reports = await api(url);

        if (!reports.length) {
            list.innerHTML = '<p style="text-align:center; opacity:0.7;">No reports found.</p>';
            return;
        }

        list.innerHTML = reports.map(r => {
            const canResolve = r.status === 'open' && currentUser && currentUser.role === 'public_service';
            return (
                '<div class="glass-card report-card">' +
                    '<div>' +
                        '<strong>' + escapeHtml(r.issue) + '</strong><br>' +
                        '<small style="opacity:0.7;">' + escapeHtml(r.category) + ' · ' + escapeHtml(r.location) + ' · by ' + escapeHtml(r.user) + '</small>' +
                    '</div>' +
                    (canResolve 
                        ? '<button class="btn-glow" style="margin-top:10px; font-size:0.8rem;" onclick="resolveReport(' + r.id + ')">Resolve Issue</button>' 
                        : '<span class="badge badge-' + escapeHtml(r.status) + '" style="display:inline-block; margin-top:5px;">' + escapeHtml(r.status) + '</span>') +
                '</div>'
            );
        }).join('');

    } catch (e) {
        list.innerHTML = '<p class="error-msg" style="color:#ff0055;">Error loading reports: ' + escapeHtml(e.message) + '</p>';
    }
}

// Global function for the onclick attribute in HTML
window.resolveReport = async function(id) {
    try {
        await api('/api/report/' + id + '/resolve', { method: 'POST' });
        alert('Issue resolved successfully!');
        loadReports();
    } catch (e) {
        alert('Could not resolve: ' + e.message);
    }
};

// --- Resources Logic ---

async function loadHelpers() {
    const grid = $('resource-grid');
    const loc = $('resource-location').value.trim();
    
    if (!loc) {
        grid.innerHTML = '<p style="text-align:center; opacity:0.7;">Enter a location to find helpers nearby...</p>';
        return;
    }

    grid.innerHTML = '<p style="text-align:center; opacity:0.7;">Searching your area...</p>';

    try {
        const helpers = await api('/api/find-resources/' + encodeURIComponent(loc));

        if (!helpers.length) {
            grid.innerHTML = '<p style="text-align:center; opacity:0.7;">No neighbors with surplus water right now.</p>';
            return;
        }

        grid.innerHTML = helpers.map(h => `
            <div class="glass-card resource-card">
                <strong>${escapeHtml(h.name)}</strong><br>
                <small>💧 ${h.water_level}% · ⚡ ${escapeHtml(h.power_status)}</small>
            </div>
        `).join('');
    } catch (e) {
        grid.innerHTML = '<p class="error-msg" style="color:#ff0055;">Error: ' + escapeHtml(e.message) + '</p>';
    }
}

// --- Outages Logic ---

async function loadOutages() {
    const list = $('outages-list');
    list.innerHTML = '<p style="text-align:center; opacity:0.7;">Loading schedule...</p>';

    try {
        let url = '/api/outages';
        if (currentOutageFilter !== 'all') {
            url += '?type=' + encodeURIComponent(currentOutageFilter);
        }

        const outages = await api(url);
        
        if (!outages.length) {
            list.innerHTML = '<p style="text-align:center; opacity:0.7;">No outages scheduled.</p>';
            return;
        }

        list.innerHTML = outages.map(o => `
            <div class="glass-card outage-card">
                <strong>${o.type === 'power' ? '⚡' : '💧'} ${escapeHtml(o.area)}</strong><br>
                <small style="opacity:0.7;">${escapeHtml(o.start_time)} → ${escapeHtml(o.end_time)}<br>${escapeHtml(o.notes)}</small>
            </div>
        `).join('');

    } catch (e) {
        list.innerHTML = '<p class="error-msg" style="color:#ff0055;">Error: ' + escapeHtml(e.message) + '</p>';
    }
}

// --- Business Profile Logic ---

async function loadBusinessProfile() {
    try {
        const data = await api('/api/business-profile');
        
        $('biz-crime-total').textContent = data.crime_total;
        $('biz-crime-resolved').textContent = data.crime_resolved;

        const zoneTable = $('zone-stats');
        zoneTable.innerHTML = '';
        
        if (!data.zones.length) {
            zoneTable.innerHTML = '<p>No zone data available.</p>';
            return;
        }

        data.zones.forEach(z => {
            zoneTable.innerHTML += `
                <div class="glass-card">
                    <strong>${escapeHtml(z.zone)}</strong><br>
                    <small>Rate: ${z.burglary_rate} · Trend: ${z.trend}</small>
                </div>
            `;
        });

    } catch (e) {
        console.error('Business profile error:', e);
    }
}

// --- SAPS Map Logic ---
async function loadSapsMap() {
    // In a real app, this would initialize Leaflet/Google Maps
    // For now, we just show a placeholder
    const mapContainer = $('map-placeholder');
    mapContainer.innerHTML = '<p><i class="fa-solid fa-map-location-dot"></i> Interactive Map Loaded</p><p class="small">Connected to live report dots.</p>';
}

// --- Interactive Elements ---

function updateWater(val) {
    $('water-level').textContent = val + '%';
    $('water-fill').style.width = val + '%';
    
    // Debounce or direct save? Let's save directly for responsiveness
    api('/api/water-level', {
        method: 'POST',
        body: JSON.stringify({ water_level: parseInt(val) })
    }).catch(e => console.error('Water update error:', e));
}

function toggleTheme() {
    document.body.classList.toggle('dark-mode');
    const icon = $('theme-toggle').querySelector('i');
    if (document.body.classList.contains('dark-mode')) {
        icon.className = 'fa-solid fa-sun';
    } else {
        icon.className = 'fa-solid fa-moon';
    }
}

// --- Modal Logic ---

function openReportModal() {
    $('report-modal').style.display = 'flex';
}

function closeReportModal() {
    $('report-modal').style.display = 'none';
    $('report-issue').value = '';
}

async function submitReport() {
    const issue = $('report-issue').value.trim();
    if (!issue) {
        alert('Please describe the issue');
        return;
    }

    const btn = $('report-form').querySelector('button');
    btn.disabled = true;

    try {
        await api('/api/report', {
            method: 'POST',
            body: JSON.stringify({
                issue: issue,
                category: $('report-category').value,
                location: currentUser.location
            })
        });

        closeReportModal();
        loadReports(); // Refresh list
    } catch (e) {
        alert('Failed to submit: ' + e.message);
    } finally {
        btn.disabled = false;
    }
}

// --- Initialization ---

document.addEventListener('DOMContentLoaded', () => {
    // Auth Event Listeners
    $('login-form').addEventListener('submit', (e) => {
        e.preventDefault();
        doLogin();
    });
    
    $('register-form').addEventListener('submit', (e) => {
        e.preventDefault();
        doRegister();
    });

    $('logout-btn').addEventListener('click', doLogout);

    // Report Modal Events
    $('new-report-btn').addEventListener('click', openReportModal);
    $('cancel-report-btn').addEventListener('click', closeReportModal);
    $('submit-report-btn').addEventListener('click', submitReport);

    // Close modal if clicking outside
    $('report-modal').addEventListener('click', (e) => {
        if (e.target === $('report-modal')) closeReportModal();
    });

    // Filter Event Listeners
    document.querySelectorAll('#reports-section .filter').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('#reports-section .filter').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            currentReportFilter = btn.dataset.cat;
            loadReports();
        });
    });

    document.querySelectorAll('#outages-section .filter').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('#outages-section .filter').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            currentOutageFilter = btn.dataset.type;
            loadOutages();
        });
    });

    // Resource Search Input
    $('resource-location').addEventListener('input', loadHelpers);

    // Auto-login check on page load
    const savedUser = localStorage.getItem('user');
    if (savedUser) {
        try {
            const user = JSON.parse(savedUser);
            // Verify session is still valid
            api('/api/profile')
                .then(data => {
                    currentUser = {
                        id: data.id,
                        username: data.name,
                        role: data.role,
                        location: data.location
                    };
                    enterApp();
                })
                .catch(() => {
                    // Session expired, clear local storage
                    localStorage.removeItem('user');
                });
        } catch (e) {
            localStorage.removeItem('user');
        }
    } else {
        // Check for existing session cookie
        api('/api/profile')
            .then(data => {
                currentUser = {
                    id: data.id,
                    username: data.name,
                    role: data.role,
                    location: data.location
                };
                localStorage.setItem('user', JSON.stringify(currentUser));
                enterApp();
            })
            .catch(() => {
                // Not logged in, show login screen (default)
            });
    }
});