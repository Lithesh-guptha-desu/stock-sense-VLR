// StockSense Frontend Engine
const API_BASE = '/api';

let currentUser = JSON.parse(localStorage.getItem('stocksense_user')) || {
    id: 1,
    name: 'Alex Mercer',
    email: 'alex@stocksense.io',
    role: 'Inventory Manager'
};

let cacheCategories = [];
let cacheWarehouses = [];
let cacheLocations = [];
let cacheProducts = [];

// Initialize Application
document.addEventListener('DOMContentLoaded', () => {
    checkAuthState();
    initApp();
});

function checkAuthState() {
    const token = localStorage.getItem('stocksense_token');
    const authOverlay = document.getElementById('auth-overlay');
    if (!token && !currentUser) {
        authOverlay.style.display = 'flex';
    } else {
        authOverlay.style.display = 'none';
        updateUserUI();
    }
}

function updateUserUI() {
    if (currentUser) {
        document.getElementById('user-name-text').innerText = currentUser.name || 'User';
        document.getElementById('user-role-text').innerText = currentUser.role || 'Inventory Manager';
        const initials = currentUser.name ? currentUser.name.split(' ').map(n => n[0]).join('').toUpperCase() : 'U';
        document.getElementById('user-avatar-text').innerText = initials;
    }
}

// ----------------------------------------------------
// AUTHENTICATION FLOWS
// ----------------------------------------------------
function showAuthTab(tab) {
    document.getElementById('login-form-box').style.display = tab === 'login' ? 'block' : 'none';
    document.getElementById('signup-form-box').style.display = tab === 'signup' ? 'block' : 'none';
    document.getElementById('forgot-form-box').style.display = tab === 'forgot' ? 'block' : 'none';
    document.getElementById('otp-step-box').style.display = 'none';
}

async function handleLogin(e) {
    e.preventDefault();
    const email = document.getElementById('login-email').value;
    const password = document.getElementById('login-password').value;

    try {
        const res = await fetch(`${API_BASE}/auth/login`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email, password })
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || 'Login failed');

        localStorage.setItem('stocksense_token', data.token);
        localStorage.setItem('stocksense_user', JSON.stringify(data.user));
        currentUser = data.user;
        updateUserUI();

        document.getElementById('auth-overlay').style.display = 'none';
        showToast('Login successful. Welcome to StockSense!', 'success');
        initApp();
    } catch (err) {
        showToast(err.message, 'error');
    }
}

async function handleRegister(e) {
    e.preventDefault();
    const name = document.getElementById('signup-name').value;
    const email = document.getElementById('signup-email').value;
    const password = document.getElementById('signup-password').value;
    const confirmPassword = document.getElementById('signup-confirm').value;

    try {
        const res = await fetch(`${API_BASE}/auth/register`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name, email, password, confirmPassword })
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || 'Registration failed');

        localStorage.setItem('stocksense_token', data.token);
        localStorage.setItem('stocksense_user', JSON.stringify(data.user));
        currentUser = data.user;
        updateUserUI();

        document.getElementById('auth-overlay').style.display = 'none';
        showToast('Account registered successfully!', 'success');
        initApp();
    } catch (err) {
        showToast(err.message, 'error');
    }
}

async function handleForgotPassword(e) {
    e.preventDefault();
    const email = document.getElementById('forgot-email').value;

    try {
        const res = await fetch(`${API_BASE}/auth/forgot-password`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email })
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || 'Request failed');

        document.getElementById('otp-step-box').style.display = 'block';
        document.getElementById('otp-hint').innerText = `OTP code sent! Demo Code: ${data.otp_debug}`;
        showToast(`OTP Code generated: ${data.otp_debug}`, 'warning');
    } catch (err) {
        showToast(err.message, 'error');
    }
}

async function handleVerifyAndResetPassword() {
    const email = document.getElementById('forgot-email').value;
    const code = document.getElementById('otp-code').value;
    const newPassword = document.getElementById('reset-new-password').value;

    try {
        const vRes = await fetch(`${API_BASE}/auth/verify-otp`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email, code })
        });
        const vData = await vRes.json();
        if (!vRes.ok) throw new Error(vData.error);

        const rRes = await fetch(`${API_BASE}/auth/reset-password`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email, code, newPassword })
        });
        const rData = await rRes.json();
        if (!rRes.ok) throw new Error(rData.error);

        showToast('Password reset successfully. Please login.', 'success');
        showAuthTab('login');
    } catch (err) {
        showToast(err.message, 'error');
    }
}

function handleLogout() {
    localStorage.removeItem('stocksense_token');
    localStorage.removeItem('stocksense_user');
    currentUser = null;
    document.getElementById('auth-overlay').style.display = 'flex';
    showAuthTab('login');
    showToast('Logged out.', 'warning');
}

// ----------------------------------------------------
// TAB SWITCHING & ROUTING
// ----------------------------------------------------
function switchTab(tabId) {
    const views = ['dashboard', 'products', 'receipts', 'deliveries', 'transfers', 'adjustments', 'ledger', 'warehouses'];
    views.forEach(v => {
        const el = document.getElementById(`view-${v}`);
        const nav = document.getElementById(`nav-${v}`);
        if (el) el.style.display = (v === tabId) ? 'block' : 'none';
        if (nav) {
            if (v === tabId) nav.classList.add('active');
            else nav.classList.remove('active');
        }
    });

    if (tabId === 'dashboard') loadDashboard();
    else if (tabId === 'products') loadProducts();
    else if (tabId === 'receipts') loadReceipts();
    else if (tabId === 'deliveries') loadDeliveries();
    else if (tabId === 'transfers') loadTransfers();
    else if (tabId === 'adjustments') loadAdjustments();
    else if (tabId === 'ledger') loadLedger();
    else if (tabId === 'warehouses') loadWarehouses();
}

async function initApp() {
    await fetchMasterMetadata();
    loadDashboard();
    loadLowStockAlerts();
}

async function fetchMasterMetadata() {
    try {
        const [cRes, wRes, lRes, pRes] = await Promise.all([
            fetch(`${API_BASE}/categories`),
            fetch(`${API_BASE}/warehouses`),
            fetch(`${API_BASE}/locations`),
            fetch(`${API_BASE}/products`)
        ]);
        cacheCategories = await cRes.json();
        cacheWarehouses = await wRes.json();
        cacheLocations = await lRes.json();
        cacheProducts = await pRes.json();

        populateDropdowns();
    } catch (err) {
        console.error('Failed to fetch master metadata:', err);
    }
}

function populateDropdowns() {
    // Categories
    const catSelects = ['prod-category', 'prod-filter-category'];
    catSelects.forEach(id => {
        const el = document.getElementById(id);
        if (!el) return;
        let html = id.includes('filter') ? '<option value="">All Categories</option>' : '';
        cacheCategories.forEach(c => {
            html += `<option value="${c.id}">${c.name}</option>`;
        });
        el.innerHTML = html;
    });

    // Warehouses filter
    const whFilter = document.getElementById('filter-warehouse');
    if (whFilter) {
        let html = '<option value="All">All Warehouses</option>';
        cacheWarehouses.forEach(w => {
            html += `<option value="${w.id}">${w.name} (${w.code})</option>`;
        });
        whFilter.innerHTML = html;
    }

    // Receipt & Delivery Warehouses
    ['rec-warehouse', 'del-warehouse'].forEach(id => {
        const el = document.getElementById(id);
        if (!el) return;
        let html = '';
        cacheWarehouses.forEach(w => {
            html += `<option value="${w.id}">${w.name} (${w.code})</option>`;
        });
        el.innerHTML = html;
    });

    // Locations dropdowns
    ['prod-initial-location', 'trf-source-loc', 'trf-dest-loc', 'adj-loc'].forEach(id => {
        const el = document.getElementById(id);
        if (!el) return;
        let html = '';
        cacheLocations.forEach(l => {
            html += `<option value="${l.id}">${l.name} (${l.code})</option>`;
        });
        el.innerHTML = html;
    });

    // Products dropdowns
    ['rec-item-prod', 'del-item-prod', 'trf-prod', 'adj-prod'].forEach(id => {
        const el = document.getElementById(id);
        if (!el) return;
        let html = '';
        cacheProducts.forEach(p => {
            html += `<option value="${p.id}">${p.name} (${p.sku})</option>`;
        });
        el.innerHTML = html;
    });

    populateReceiptLocations();
    populateDeliveryLocations();
}

function populateReceiptLocations() {
    const whId = document.getElementById('rec-warehouse')?.value;
    const el = document.getElementById('rec-item-loc');
    if (!el) return;
    const locs = cacheLocations.filter(l => !whId || l.warehouse_id == whId);
    el.innerHTML = locs.map(l => `<option value="${l.id}">${l.name} (${l.code})</option>`).join('');
}

function populateDeliveryLocations() {
    const whId = document.getElementById('del-warehouse')?.value;
    const el = document.getElementById('del-item-loc');
    if (!el) return;
    const locs = cacheLocations.filter(l => !whId || l.warehouse_id == whId);
    el.innerHTML = locs.map(l => `<option value="${l.id}">${l.name} (${l.code})</option>`).join('');
}

// ----------------------------------------------------
// 1. DASHBOARD
// ----------------------------------------------------
async function loadDashboard() {
    try {
        const sRes = await fetch(`${API_BASE}/dashboard/summary`);
        const summary = await sRes.json();

        document.getElementById('kpi-total-stock').innerText = summary.total_stock_quantity.toLocaleString();
        document.getElementById('kpi-product-count').innerText = summary.total_products_count;
        document.getElementById('kpi-low-stock').innerText = summary.low_stock_count;
        document.getElementById('kpi-out-stock').innerText = summary.out_of_stock_count;
        document.getElementById('kpi-pending-receipts').innerText = summary.pending_receipts;
        document.getElementById('kpi-pending-deliveries').innerText = summary.pending_deliveries;
        document.getElementById('kpi-pending-transfers').innerText = summary.pending_transfers;

        loadDashboardOperations();
        loadLowStockAlerts();
    } catch (err) {
        console.error('Failed to load dashboard:', err);
    }
}

async function loadDashboardOperations() {
    const docType = document.getElementById('filter-doc-type')?.value || 'All';
    const status = document.getElementById('filter-status')?.value || 'All';
    const wh = document.getElementById('filter-warehouse')?.value || 'All';

    try {
        const res = await fetch(`${API_BASE}/dashboard/operations?doc_type=${docType}&status=${status}&warehouse_id=${wh}`);
        const ops = await res.json();

        const tbody = document.getElementById('dashboard-ops-tbody');
        if (!ops.length) {
            tbody.innerHTML = `<tr><td colspan="6" style="text-align:center; color:var(--text-dim);">No operations match filter criteria.</td></tr>`;
            return;
        }

        tbody.innerHTML = ops.map(o => `
            <tr>
                <td style="font-weight:700; color:var(--accent-cyan);">${o.reference_number}</td>
                <td><span class="badge ${getOpBadgeClass(o.type)}">${o.type}</span></td>
                <td>${o.party}</td>
                <td>${o.warehouse_name || 'Multi-Location'}</td>
                <td style="font-size:0.8rem; color:var(--text-muted);">${formatDate(o.created_at)}</td>
                <td><span class="badge ${getStatusBadgeClass(o.status)}">${o.status}</span></td>
            </tr>
        `).join('');
    } catch (err) {
        console.error('Failed ops:', err);
    }
}

async function loadLowStockAlerts() {
    try {
        const res = await fetch(`${API_BASE}/dashboard/low-stock`);
        const items = await res.json();

        const countEl = document.getElementById('notification-count');
        const headerEl = document.getElementById('alert-dropdown-header');
        const container = document.getElementById('low-stock-items-container');

        countEl.innerText = items.length;
        headerEl.innerText = `${items.length} Low Stock Items`;

        if (!items.length) {
            container.innerHTML = `<div style="font-size:0.8rem; color:var(--accent-emerald); text-align:center; padding:1rem;">✓ All inventory stock levels healthy!</div>`;
            return;
        }

        container.innerHTML = items.map(item => `
            <div style="display:flex; justify-content:space-between; align-items:center; background:rgba(255,255,255,0.03); padding:0.6rem 0.8rem; border-radius:6px; border-left:3px solid ${item.current_stock === 0 ? 'var(--accent-rose)' : 'var(--accent-amber)'};">
                <div>
                    <div style="font-size:0.85rem; font-weight:700;">${item.name}</div>
                    <div style="font-size:0.72rem; color:var(--text-dim);">${item.sku} • Threshold: ${item.reorder_level}</div>
                </div>
                <div style="text-align:right;">
                    <span class="badge ${item.current_stock === 0 ? 'badge-out-stock' : 'badge-low-stock'}">${item.current_stock} left</span>
                </div>
            </div>
        `).join('');
    } catch (err) {
        console.error(err);
    }
}

function toggleLowStockDropdown() {
    const el = document.getElementById('low-stock-dropdown');
    el.style.display = (el.style.display === 'none') ? 'block' : 'none';
}

// ----------------------------------------------------
// 2. PRODUCTS
// ----------------------------------------------------
async function loadProducts() {
    const search = document.getElementById('prod-search-input')?.value || '';
    const catId = document.getElementById('prod-filter-category')?.value || '';
    const status = document.getElementById('prod-filter-status')?.value || 'All';

    try {
        const res = await fetch(`${API_BASE}/products?search=${encodeURIComponent(search)}&category_id=${catId}&stock_status=${status}`);
        const products = await res.json();
        cacheProducts = products;

        const tbody = document.getElementById('products-tbody');
        if (!products.length) {
            tbody.innerHTML = `<tr><td colspan="8" style="text-align:center; color:var(--text-dim);">No products found matching filters.</td></tr>`;
            return;
        }

        tbody.innerHTML = products.map(p => `
            <tr>
                <td style="font-weight:700; font-size:0.92rem;">${p.name}</td>
                <td><span class="brand-tag">${p.sku}</span></td>
                <td>${p.category_name}</td>
                <td>${p.unit_of_measure}</td>
                <td style="font-weight:800; font-size:1rem; color:${p.total_stock === 0 ? 'var(--accent-rose)' : (p.total_stock <= p.reorder_level ? 'var(--accent-amber)' : 'var(--text-main)')}">${p.total_stock}</td>
                <td>${p.reorder_level}</td>
                <td><span class="badge ${getStatusBadgeClass(p.stock_status)}">${p.stock_status}</span></td>
                <td>
                    <button class="quick-btn" style="padding:0.3rem 0.6rem; font-size:0.75rem;" onclick="viewProductAuditDetail(${p.id})">🔍 Audit Ledger</button>
                </td>
            </tr>
        `).join('');
    } catch (err) {
        console.error(err);
    }
}

async function viewProductAuditDetail(prodId) {
    try {
        const res = await fetch(`${API_BASE}/products/${prodId}`);
        const p = await res.json();

        document.getElementById('prod-detail-title').innerText = p.name;
        document.getElementById('prod-detail-sku').innerText = p.sku;
        document.getElementById('detail-cat-name').innerText = p.category_name;
        document.getElementById('detail-total-stock').innerText = p.total_stock;
        document.getElementById('detail-reorder-level').innerText = p.reorder_level;

        // Locations
        const locTbody = document.getElementById('detail-locations-tbody');
        locTbody.innerHTML = p.locations.map(l => `
            <tr>
                <td>${l.warehouse_name}</td>
                <td><span class="brand-tag">${l.location_code}</span></td>
                <td>${l.location_name}</td>
                <td style="font-weight:700;">${l.quantity}</td>
            </tr>
        `).join('') || `<tr><td colspan="4" style="text-align:center;">No stock recorded yet.</td></tr>`;

        // Ledger history
        const ledgerTbody = document.getElementById('detail-ledger-tbody');
        ledgerTbody.innerHTML = p.ledger_history.map(lh => `
            <tr>
                <td style="font-size:0.78rem;">${formatDate(lh.date_time)}</td>
                <td><span class="badge ${getOpBadgeClass(lh.operation_type)}">${lh.operation_type}</span></td>
                <td style="font-weight:700;">${lh.reference_id}</td>
                <td style="font-weight:700; color:${lh.quantity > 0 ? 'var(--accent-emerald)' : 'var(--accent-rose)'}">${lh.quantity > 0 ? '+' : ''}${lh.quantity}</td>
                <td>${lh.new_quantity}</td>
            </tr>
        `).join('') || `<tr><td colspan="5" style="text-align:center;">No movement history.</td></tr>`;

        openModal('modal-prod-detail');
    } catch (err) {
        showToast(err.message, 'error');
    }
}

// ----------------------------------------------------
// 3. RECEIPTS
// ----------------------------------------------------
async function loadReceipts() {
    try {
        const res = await fetch(`${API_BASE}/receipts`);
        const receipts = await res.json();

        const tbody = document.getElementById('receipts-tbody');
        tbody.innerHTML = receipts.map(r => `
            <tr>
                <td style="font-weight:700; color:var(--accent-cyan);">${r.reference_number}</td>
                <td>${r.supplier}</td>
                <td>${r.warehouse_name}</td>
                <td>${r.item_count} items</td>
                <td style="font-weight:700;">${r.total_quantity}</td>
                <td style="font-size:0.8rem; color:var(--text-muted);">${formatDate(r.created_at)}</td>
                <td><span class="badge ${getStatusBadgeClass(r.status)}">${r.status}</span></td>
                <td>
                    ${r.status !== 'DONE' && r.status !== 'CANCELED' ? `
                        <button class="quick-btn quick-btn-primary" style="padding:0.3rem 0.6rem; font-size:0.75rem;" onclick="validateReceipt(${r.id})">✓ Validate Stock</button>
                    ` : `<span style="font-size:0.75rem; color:var(--text-dim);">Completed</span>`}
                </td>
            </tr>
        `).join('');
    } catch (err) {
        console.error(err);
    }
}

async function validateReceipt(recId) {
    try {
        const res = await fetch(`${API_BASE}/receipts/${recId}/validate`, { method: 'POST' });
        const data = await res.json();
        if (!res.ok) throw new Error(data.error);

        showToast(data.message, 'success');
        loadReceipts();
        fetchMasterMetadata();
    } catch (err) {
        showToast(err.message, 'error');
    }
}

// ----------------------------------------------------
// 4. DELIVERIES
// ----------------------------------------------------
async function loadDeliveries() {
    try {
        const res = await fetch(`${API_BASE}/deliveries`);
        const deliveries = await res.json();

        const tbody = document.getElementById('deliveries-tbody');
        tbody.innerHTML = deliveries.map(d => `
            <tr>
                <td style="font-weight:700; color:var(--accent-purple);">${d.reference_number}</td>
                <td>${d.customer}</td>
                <td>${d.warehouse_name}</td>
                <td><span class="badge badge-done">${d.picking_status}</span></td>
                <td><span class="badge badge-ready">${d.packing_status}</span></td>
                <td style="font-size:0.8rem; color:var(--text-muted);">${formatDate(d.created_at)}</td>
                <td><span class="badge ${getStatusBadgeClass(d.status)}">${d.status}</span></td>
                <td>
                    ${d.status !== 'DONE' && d.status !== 'CANCELED' ? `
                        <button class="quick-btn quick-btn-primary" style="padding:0.3rem 0.6rem; font-size:0.75rem;" onclick="validateDelivery(${d.id})">✓ Validate Dispatch</button>
                    ` : `<span style="font-size:0.75rem; color:var(--text-dim);">Completed</span>`}
                </td>
            </tr>
        `).join('');
    } catch (err) {
        console.error(err);
    }
}

async function validateDelivery(delId) {
    try {
        const res = await fetch(`${API_BASE}/deliveries/${delId}/validate`, { method: 'POST' });
        const data = await res.json();
        if (!res.ok) throw new Error(data.error);

        showToast(data.message, 'success');
        loadDeliveries();
        fetchMasterMetadata();
    } catch (err) {
        showToast(err.message, 'error');
    }
}

// ----------------------------------------------------
// 5. TRANSFERS
// ----------------------------------------------------
async function loadTransfers() {
    try {
        const res = await fetch(`${API_BASE}/transfers`);
        const transfers = await res.json();

        const tbody = document.getElementById('transfers-tbody');
        tbody.innerHTML = transfers.map(t => `
            <tr>
                <td style="font-weight:700; color:var(--accent-cyan);">${t.reference_number}</td>
                <td><span class="brand-tag">${t.source_code}</span> ${t.source_location_name}</td>
                <td><span class="brand-tag">${t.destination_code}</span> ${t.destination_location_name}</td>
                <td>${t.item_count} items</td>
                <td style="font-weight:700;">${t.total_quantity}</td>
                <td><span class="badge ${getStatusBadgeClass(t.status)}">${t.status}</span></td>
                <td>
                    ${t.status !== 'DONE' && t.status !== 'CANCELED' ? `
                        <button class="quick-btn quick-btn-primary" style="padding:0.3rem 0.6rem; font-size:0.75rem;" onclick="validateTransfer(${t.id})">✓ Confirm Transfer</button>
                    ` : `<span style="font-size:0.75rem; color:var(--text-dim);">Completed</span>`}
                </td>
            </tr>
        `).join('');
    } catch (err) {
        console.error(err);
    }
}

async function validateTransfer(trfId) {
    try {
        const res = await fetch(`${API_BASE}/transfers/${trfId}/validate`, { method: 'POST' });
        const data = await res.json();
        if (!res.ok) throw new Error(data.error);

        showToast(data.message, 'success');
        loadTransfers();
        fetchMasterMetadata();
    } catch (err) {
        showToast(err.message, 'error');
    }
}

// ----------------------------------------------------
// 6. ADJUSTMENTS
// ----------------------------------------------------
async function loadAdjustments() {
    try {
        const res = await fetch(`${API_BASE}/adjustments`);
        const list = await res.json();

        const tbody = document.getElementById('adjustments-tbody');
        tbody.innerHTML = list.map(a => `
            <tr>
                <td style="font-weight:700; color:var(--accent-amber);">${a.reference_number}</td>
                <td style="font-weight:700;">${a.product_name} (${a.sku})</td>
                <td><span class="brand-tag">${a.location_code}</span> ${a.location_name}</td>
                <td>${a.system_quantity}</td>
                <td style="font-weight:700; color:var(--accent-cyan);">${a.physical_quantity}</td>
                <td style="font-weight:700; color:${a.difference >= 0 ? 'var(--accent-emerald)' : 'var(--accent-rose)'};">${a.difference >= 0 ? '+' : ''}${a.difference}</td>
                <td>${a.reason}</td>
                <td style="font-size:0.8rem; color:var(--text-muted);">${formatDate(a.created_at)}</td>
            </tr>
        `).join('');
    } catch (err) {
        console.error(err);
    }
}

function updateAdjustmentCurrentStock() {
    const prodId = document.getElementById('adj-prod')?.value;
    const locId = document.getElementById('adj-loc')?.value;
    const sysEl = document.getElementById('adj-sys-qty');

    if (!prodId || !locId || !sysEl) return;

    const prod = cacheProducts.find(p => p.id == prodId);
    if (!prod || !prod.locations) {
        sysEl.value = '0';
        return;
    }

    const locStock = prod.locations.find(l => l.location_id == locId || l.id == locId);
    sysEl.value = locStock ? locStock.quantity : 0;
}

// ----------------------------------------------------
// 7. STOCK LEDGER AUDIT LOG
// ----------------------------------------------------
async function loadLedger() {
    const search = document.getElementById('ledger-search')?.value || '';
    const op = document.getElementById('ledger-filter-op')?.value || 'All';

    try {
        const res = await fetch(`${API_BASE}/ledger?search=${encodeURIComponent(search)}&operation_type=${op}`);
        const items = await res.json();

        const tbody = document.getElementById('ledger-tbody');
        if (!items.length) {
            tbody.innerHTML = `<tr><td colspan="9" style="text-align:center; color:var(--text-dim);">No ledger records found.</td></tr>`;
            return;
        }

        tbody.innerHTML = items.map(l => {
            const locFlow = l.operation_type === 'INTERNAL TRANSFER' ? 
                `<span class="brand-tag">${l.source_location_code}</span> ➔ <span class="brand-tag">${l.destination_location_code}</span>` :
                (l.source_location_name ? `From ${l.source_location_name}` : `To ${l.destination_location_name}`);

            return `
                <tr>
                    <td style="font-size:0.8rem; color:var(--text-muted);">${formatDate(l.date_time)}</td>
                    <td>
                        <div style="font-weight:700;">${l.product_name}</div>
                        <div style="font-size:0.75rem;" class="brand-tag">${l.sku}</div>
                    </td>
                    <td><span class="badge ${getOpBadgeClass(l.operation_type)}">${l.operation_type}</span></td>
                    <td style="font-weight:700; color:var(--accent-cyan);">${l.reference_id}</td>
                    <td>${locFlow}</td>
                    <td style="font-weight:800; color:${l.quantity >= 0 ? 'var(--accent-emerald)' : 'var(--accent-rose)'};">${l.quantity >= 0 ? '+' : ''}${l.quantity} ${l.unit_of_measure}</td>
                    <td>${l.previous_quantity}</td>
                    <td style="font-weight:700;">${l.new_quantity}</td>
                    <td style="font-size:0.8rem; color:var(--text-dim);">${l.user_name || 'System Admin'}</td>
                </tr>
            `;
        }).join('');
    } catch (err) {
        console.error(err);
    }
}

// ----------------------------------------------------
// 8. WAREHOUSES
// ----------------------------------------------------
async function loadWarehouses() {
    try {
        const res = await fetch(`${API_BASE}/warehouses`);
        const warehouses = await res.json();

        const container = document.getElementById('warehouses-cards-container');
        container.innerHTML = warehouses.map(w => `
            <div class="glass-panel" style="padding:1.5rem;">
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:1rem;">
                    <div>
                        <h3 style="font-family:var(--font-heading); font-size:1.15rem;">${w.name}</h3>
                        <span class="brand-tag">${w.code}</span>
                    </div>
                    <span class="badge badge-done">${w.status}</span>
                </div>
                <p style="font-size:0.85rem; color:var(--text-muted); margin-bottom:1.25rem;">📍 ${w.address || 'No address registered'}</p>

                <h4 style="font-size:0.82rem; font-weight:700; text-transform:uppercase; color:var(--text-dim); margin-bottom:0.6rem;">Locations / Racks Structure</h4>
                <div style="display:flex; flex-direction:column; gap:0.4rem;">
                    ${w.locations.map(loc => `
                        <div style="display:flex; justify-content:space-between; background:rgba(255,255,255,0.03); padding:0.5rem 0.75rem; border-radius:6px; font-size:0.85rem;">
                            <span>📁 ${loc.name}</span>
                            <span class="brand-tag">${loc.code}</span>
                        </div>
                    `).join('')}
                </div>
            </div>
        `).join('');
    } catch (err) {
        console.error(err);
    }
}

// ----------------------------------------------------
// FORM SUBMISSIONS & MODALS
// ----------------------------------------------------
function openModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
        modal.classList.add('active');
        if (modalId === 'modal-adjustment') updateAdjustmentCurrentStock();
    }
}

function closeModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) modal.classList.remove('active');
}

async function submitCreateProduct(e) {
    e.preventDefault();
    const name = document.getElementById('prod-name').value;
    const sku = document.getElementById('prod-sku').value;
    const category_id = document.getElementById('prod-category').value;
    const unit_of_measure = document.getElementById('prod-uom').value;
    const reorder_level = document.getElementById('prod-reorder').value;
    const initial_stock = document.getElementById('prod-initial-stock').value;
    const location_id = document.getElementById('prod-initial-location').value;

    try {
        const res = await fetch(`${API_BASE}/products`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name, sku, category_id, unit_of_measure, reorder_level, initial_stock, location_id })
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.error);

        showToast(data.message, 'success');
        closeModal('modal-product');
        fetchMasterMetadata();
        loadProducts();
    } catch (err) {
        showToast(err.message, 'error');
    }
}

async function submitCreateReceipt(e) {
    e.preventDefault();
    const supplier = document.getElementById('rec-supplier').value;
    const warehouse_id = document.getElementById('rec-warehouse').value;
    const prod_id = document.getElementById('rec-item-prod').value;
    const loc_id = document.getElementById('rec-item-loc').value;
    const qty = document.getElementById('rec-item-qty').value;

    try {
        const res = await fetch(`${API_BASE}/receipts`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                supplier,
                warehouse_id,
                items: [{ product_id: prod_id, location_id: loc_id, quantity: qty }]
            })
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.error);

        showToast(data.message, 'success');
        closeModal('modal-receipt');
        loadReceipts();
    } catch (err) {
        showToast(err.message, 'error');
    }
}

async function submitCreateDelivery(e) {
    e.preventDefault();
    const customer = document.getElementById('del-customer').value;
    const warehouse_id = document.getElementById('del-warehouse').value;
    const prod_id = document.getElementById('del-item-prod').value;
    const loc_id = document.getElementById('del-item-loc').value;
    const qty = document.getElementById('del-item-qty').value;

    try {
        const res = await fetch(`${API_BASE}/deliveries`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                customer,
                warehouse_id,
                items: [{ product_id: prod_id, location_id: loc_id, quantity: qty }]
            })
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.error);

        showToast(data.message, 'success');
        closeModal('modal-delivery');
        loadDeliveries();
    } catch (err) {
        showToast(err.message, 'error');
    }
}

async function submitCreateTransfer(e) {
    e.preventDefault();
    const source_location_id = document.getElementById('trf-source-loc').value;
    const destination_location_id = document.getElementById('trf-dest-loc').value;
    const prod_id = document.getElementById('trf-prod').value;
    const qty = document.getElementById('trf-qty').value;

    try {
        const res = await fetch(`${API_BASE}/transfers`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                source_location_id,
                destination_location_id,
                items: [{ product_id: prod_id, quantity: qty }]
            })
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.error);

        showToast(data.message, 'success');
        closeModal('modal-transfer');
        loadTransfers();
    } catch (err) {
        showToast(err.message, 'error');
    }
}

async function submitCreateAdjustment(e) {
    e.preventDefault();
    const product_id = document.getElementById('adj-prod').value;
    const location_id = document.getElementById('adj-loc').value;
    const physical_quantity = document.getElementById('adj-physical-qty').value;
    const reason = document.getElementById('adj-reason').value;

    try {
        const res = await fetch(`${API_BASE}/adjustments`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ product_id, location_id, physical_quantity, reason })
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.error);

        showToast(data.message, 'success');
        closeModal('modal-adjustment');
        loadAdjustments();
        fetchMasterMetadata();
    } catch (err) {
        showToast(err.message, 'error');
    }
}

async function submitCreateWarehouse(e) {
    e.preventDefault();
    const name = document.getElementById('wh-name').value;
    const code = document.getElementById('wh-code').value;
    const address = document.getElementById('wh-address').value;

    try {
        const res = await fetch(`${API_BASE}/warehouses`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name, code, address })
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.error);

        showToast(data.message, 'success');
        closeModal('modal-warehouse');
        fetchMasterMetadata();
        loadWarehouses();
    } catch (err) {
        showToast(err.message, 'error');
    }
}

function handleGlobalSearch(query) {
    query = query.trim().toLowerCase();
    if (!query) return;

    // Switch to products tab if searching
    const prodInput = document.getElementById('prod-search-input');
    if (prodInput) {
        prodInput.value = query;
        switchTab('products');
    }
}

// ----------------------------------------------------
// UTILITIES & BADGES
// ----------------------------------------------------
function getStatusBadgeClass(status) {
    if (!status) return 'badge-draft';
    const s = status.toUpperCase();
    if (s === 'DRAFT') return 'badge-draft';
    if (s === 'WAITING') return 'badge-waiting';
    if (s === 'READY') return 'badge-ready';
    if (s === 'DONE' || s === 'IN STOCK') return 'badge-done';
    if (s === 'CANCELED' || s === 'OUT OF STOCK') return 'badge-canceled';
    if (s === 'LOW STOCK') return 'badge-low-stock';
    return 'badge-draft';
}

function getOpBadgeClass(type) {
    if (!type) return 'badge-draft';
    const t = type.toUpperCase();
    if (t.includes('RECEIPT')) return 'badge-done';
    if (t.includes('DELIVERY')) return 'badge-ready';
    if (t.includes('INTERNAL')) return 'badge-waiting';
    if (t.includes('ADJUSTMENT')) return 'badge-canceled';
    return 'badge-draft';
}

function formatDate(dtStr) {
    if (!dtStr) return '-';
    const d = new Date(dtStr);
    if (isNaN(d.getTime())) return dtStr;
    return d.toLocaleString('en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
}

function showToast(message, type = 'info') {
    const container = document.getElementById('toast-container');
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;

    let icon = 'ℹ';
    if (type === 'success') icon = '✓';
    if (type === 'error') icon = '✕';
    if (type === 'warning') icon = '⚠';

    toast.innerHTML = `<span style="font-weight:700;">${icon}</span> <span>${message}</span>`;
    container.appendChild(toast);

    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateX(100%)';
        setTimeout(() => toast.remove(), 300);
    }, 4000);
}
