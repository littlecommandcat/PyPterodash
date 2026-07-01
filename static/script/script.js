const defaultLocale = 'en';

function startLoading() {
    const overlay = document.getElementById('loading-overlay');
    if (overlay) overlay.style.display = 'flex';
}

function stopLoading() {
    const overlay = document.getElementById('loading-overlay');
    if (overlay) overlay.style.display = 'none';
}

function showModal(title, message) {
    return new Promise((resolve) => {
        const modal = document.getElementById('custom-modal');
        const titleEl = document.getElementById('modal-title');
        const msgEl = document.getElementById('modal-message');
        const confirmBtn = document.getElementById('modal-confirm-btn');
        const cancelBtn = document.getElementById('modal-cancel-btn');

        if (!modal || !titleEl || !msgEl || !confirmBtn || !cancelBtn) return resolve();

        titleEl.textContent = title;
        msgEl.textContent = message;
        cancelBtn.style.display = 'none';
        modal.style.display = 'flex';

        confirmBtn.onclick = () => {
            modal.style.display = 'none';
            resolve();
        };
    });
}

function showConfirm(title, message) {
    return new Promise((resolve) => {
        const modal = document.getElementById('custom-modal');
        const titleEl = document.getElementById('modal-title');
        const msgEl = document.getElementById('modal-message');
        const confirmBtn = document.getElementById('modal-confirm-btn');
        const cancelBtn = document.getElementById('modal-cancel-btn');

        if (!modal || !titleEl || !msgEl || !confirmBtn || !cancelBtn) return resolve(false);

        titleEl.textContent = title;
        msgEl.textContent = message;
        cancelBtn.style.display = 'inline-block';
        modal.style.display = 'flex';

        confirmBtn.onclick = () => {
            modal.style.display = 'none';
            resolve(true);
        };

        cancelBtn.onclick = () => {
            modal.style.display = 'none';
            resolve(false);
        };
    });
}

function getCurrentLocale() {
    return localStorage.getItem('panel-locale') || defaultLocale;
}

async function loadLocale(locale) {
    try {
        const response = await fetch(`/static/locals/${locale}.json`);
        if (!response.ok) throw new Error(`Locale file [${locale}] not found`);
        return await response.json();
    } catch (error) {
        console.error('Failed to load locale:', error);
        return null;
    }
}

function applyTranslations(translations) {
    if (!translations) return;
    
    document.querySelectorAll('[data-i18n]').forEach(element => {
        const key = element.getAttribute('data-i18n');
        if (translations[key]) {
            if (element.tagName === 'TITLE') {
                document.title = translations[key];
            } else {
                element.textContent = translations[key];
            }
        }
    });

    document.querySelectorAll('[data-i18n-placeholder]').forEach(element => {
        const key = element.getAttribute('data-i18n-placeholder');
        if (translations[key]) {
            element.placeholder = translations[key];
        }
    });

    const welcomeEl = document.getElementById('welcome-text');
    if (welcomeEl && translations['welcome']) {
        const username = welcomeEl.getAttribute('data-username');
        if (username) {
            welcomeEl.textContent = translations['welcome'].replace('{username}', username);
        }
    }
}

async function changeLanguage(locale) {
    localStorage.setItem('panel-locale', locale);
    document.documentElement.lang = locale;
    const translations = await loadLocale(locale);
    applyTranslations(translations);
}

async function initI18n() {
    const locale = getCurrentLocale();
    document.documentElement.lang = locale;
    
    const switcher = document.getElementById('language-switcher');
    if (switcher) switcher.value = locale;

    const translations = await loadLocale(locale);
    applyTranslations(translations);
}

function initLogin() {
    const loginBtn = document.getElementById('loginBtn');
    if (loginBtn) {
        loginBtn.addEventListener('click', () => {
            window.location.href = '/login';
        });
    }
}

document.addEventListener('DOMContentLoaded', () => {
    initI18n();
    initLogin();
});

async function handleCreateServer(event) {
    event.preventDefault();
    
    const nameEl = document.getElementById('server_name');
    const ramEl = document.getElementById('server_ram');
    const eggEl = document.getElementById('server_egg');
    const cpuEl = document.getElementById('server_cpu');
    const diskEl = document.getElementById('server_disk');
    if (!nameEl || !ramEl || !eggEl || !cpuEl || !diskEl) return;

    const serverName = nameEl.value;
    const ramMb = parseInt(ramEl.value);
    const eggId = parseInt(eggEl.value);
    const cpuPercent = parseInt(cpuEl.value);
    const diskMb = parseInt(diskEl.value);
    
    const maxRam = parseInt(document.getElementById('max_memory')?.value || 0);
    const usedRam = parseInt(document.getElementById('used_memory')?.value || 0);
    const discordId = document.getElementById('user_discord_id')?.value;
    
    if (ramMb > (maxRam - usedRam)) {
        await showModal('Action Failed', `RAM Allocation (${ramMb} MB) exceeds your remaining quota (${maxRam - usedRam} MB)!`);
        return;
    }

    const payload = {
        "name": serverName,
        "user_id": discordId,
        "egg_id": eggId, 
        "limits": { "memory": ramMb, "cpu": cpuPercent, "disk": diskMb }
    };

    startLoading();

    try {
        const res = await fetch('/api/dashboard/server/create', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const data = await res.json();
        
        stopLoading();

        if (!res.ok) throw new Error(data.message || data.detail || 'API Request Failed');

        if (data.status === 'success') {
            await showModal('Success', 'Server created successfully!');
            window.location.reload();
        } else {
            await showModal('Failed', data.message);
        }
    } catch (err) {
        stopLoading();
        await showModal('Error', err.message);
    }
}

async function handleDeleteServer(serverId) {
    const confirmed = await showConfirm('Confirm Deletion', `Are you sure you want to delete server [ID: ${serverId}]?`);
    if (!confirmed) return;

    startLoading();

    try {
        const res = await fetch('/api/dashboard/server/delete', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ "server_id": serverId, "force": false })
        });
        const data = await res.json();
        
        stopLoading();

        if (!res.ok) throw new Error(data.message || data.detail || 'API Request Failed');

        await showModal('Success', 'Server deleted successfully.');
        window.location.reload();
    } catch (err) {
        stopLoading();
        await showModal('Error', err.message);
    }
}

function handleLogout() {
    fetch('/api/auth/logout', { method: 'POST' })
    .then(() => window.location.href = '/');
}

async function processPurchase(itemType) {
    const inputElement = document.getElementById(`qty-${itemType}`);
    if (!inputElement) return;

    const amount = parseInt(inputElement.value);

    if (isNaN(amount) || amount <= 0) {
        await showModal('Error', 'Invalid quantity.');
        return;
    }

    const confirmed = await showConfirm('Confirm Purchase', `Confirm purchase of ${amount} unit(s) of ${itemType.toUpperCase()}?`);
    if (!confirmed) return;

    const payload = {
        "item_type": itemType,
        "amount": amount
    };

    startLoading();

    try {
        const res = await fetch('/api/trade/buy', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        
        const data = await res.json();
        
        stopLoading();

        if (!res.ok) throw new Error(data.detail || data.message || 'Purchase failed');

        if (data.status === 'success' || data.message) {
            await showModal('Success', data.message + '\n' + (data.detail || ''));
            window.location.reload();
        }
    } catch (err) {
        stopLoading();
        await showModal('Error', err.message);
    }
}

