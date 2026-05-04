let currentUser = null;
let currentToken = null;
let currentUserAvatar = null;

function initPasswordToggles() {
    document.querySelectorAll('.toggle-password').forEach(button => {
        const newButton = button.cloneNode(true);
        button.parentNode.replaceChild(newButton, button);
        newButton.addEventListener('click', function(e) {
            e.preventDefault();
            e.stopPropagation();
            const targetId = this.getAttribute('data-target');
            const input = document.getElementById(targetId);
            if (input) {
                const type = input.getAttribute('type') === 'password' ? 'text' : 'password';
                input.setAttribute('type', type);
                this.textContent = '👁️';
                if (type === 'text') this.classList.add('showing');
                else this.classList.remove('showing');
            }
        });
    });
}

function showToast(title, message, type, duration) {
    type = type || 'info'; duration = duration || 3000;
    var container = document.getElementById('toastContainer');
    if (!container) return;
    var toast = document.createElement('div');
    toast.className = 'toast ' + type;
    var icon = 'ℹ️';
    if (type === 'success') icon = '✅';
    if (type === 'error') icon = '❌';
    if (type === 'warning') icon = '⚠️';
    toast.innerHTML = '<div class="toast-icon">' + icon + '</div><div class="toast-content"><div class="toast-title">' + escapeHtml(title) + '</div><div class="toast-message">' + escapeHtml(message) + '</div></div><div class="toast-close" onclick="this.parentElement.remove()">✕</div>';
    container.appendChild(toast);
    setTimeout(function() { if (toast.parentElement) toast.remove(); }, duration);
}

function escapeHtml(text) { if (!text) return ''; var div = document.createElement('div'); div.textContent = text; return div.innerHTML; }
function loadSavedCredentials() {
    var u = localStorage.getItem('saved_username'), p = localStorage.getItem('saved_password'), r = localStorage.getItem('remember_me') === 'true';
    if (r && u) {
        var ui = document.getElementById('loginUsername'), pi = document.getElementById('loginPassword'), ri = document.getElementById('rememberMe');
        if (ui) ui.value = u; if (pi && p) pi.value = p; if (ri) ri.checked = true;
    }
}
function saveCredentials(username, password, remember) { if (remember) { localStorage.setItem('saved_username', username); localStorage.setItem('saved_password', password); localStorage.setItem('remember_me', 'true'); } else { localStorage.removeItem('saved_username'); localStorage.removeItem('saved_password'); localStorage.setItem('remember_me', 'false'); } }
function clearSavedCredentials() { localStorage.removeItem('saved_username'); localStorage.removeItem('saved_password'); localStorage.setItem('remember_me', 'false'); }
async function loadUserAvatar(username) { try { var r = await fetch('/api/user/profile/' + username); var d = await r.json(); currentUserAvatar = d.avatar; } catch (e) { currentUserAvatar = null; } }

function updateUI() {
    var authButtons = document.getElementById('authButtons'), userInfo = document.getElementById('userInfo');
    if (currentUser && currentToken) {
        if (authButtons) authButtons.style.display = 'none';
        if (userInfo) {
            userInfo.style.display = 'flex';
            var avatarHtml = currentUserAvatar ? '<img src="' + currentUserAvatar + '" style="width:32px;height:32px;border-radius:50%;object-fit:cover;">' : '<span style="width:32px;height:32px;border-radius:50%;background:linear-gradient(135deg,#e94560,#ff6b6b);display:flex;align-items:center;justify-content:center;color:white;font-weight:bold;">' + currentUser.charAt(0).toUpperCase() + '</span>';
            userInfo.innerHTML = '<button class="notifications-btn" onclick="toggleNotifications()">🔔<span class="badge" id="notifBadge" style="display:none;">0</span></button><a href="/user/' + escapeHtml(currentUser) + '" style="text-decoration:none;display:flex;align-items:center;gap:8px;outline:none;">' + avatarHtml + '<span class="user-name">' + escapeHtml(currentUser) + '</span></a><button class="logout-btn" onclick="logout()">Выйти</button>';
        }
    } else { if (authButtons) authButtons.style.display = 'flex'; if (userInfo) { userInfo.style.display = 'none'; userInfo.innerHTML = ''; } }
    var link = document.getElementById('profileNavLink'); if (link) { link.style.display = currentUser ? 'block' : 'none'; if (currentUser) link.href = '/user/' + currentUser; }
}

function loadUser() { var t = localStorage.getItem('token'), u = localStorage.getItem('username'); if (t && u) { currentToken = t; currentUser = u; checkAuth(); } else { currentToken = null; currentUser = null; currentUserAvatar = null; updateUI(); if (typeof onAuthStateChanged === 'function') onAuthStateChanged(false); } }
async function checkAuth() { if (!currentToken) { updateUI(); if (typeof onAuthStateChanged === 'function') onAuthStateChanged(false); return; } try { var r = await fetch('/api/check-auth?token=' + currentToken); var d = await r.json(); if (d.authenticated) { await loadUserAvatar(d.username); updateUI(); if (typeof onAuthStateChanged === 'function') onAuthStateChanged(true); } else { localStorage.removeItem('token'); localStorage.removeItem('username'); currentToken = null; currentUser = null; currentUserAvatar = null; updateUI(); if (typeof onAuthStateChanged === 'function') onAuthStateChanged(false); } } catch (e) { updateUI(); if (typeof onAuthStateChanged === 'function') onAuthStateChanged(true); } }

async function login() { var u = document.getElementById('loginUsername'), p = document.getElementById('loginPassword'), r = document.getElementById('rememberMe'); if (!u || !p) return; var un = u.value.trim(), pw = p.value, rm = r ? r.checked : false; if (!un || !pw) { showToast('Ошибка', 'Введите имя и пароль', 'error'); return; } var fd = new FormData(); fd.append('username', un); fd.append('password', pw); try { var resp = await fetch('/api/login', { method: 'POST', body: fd }); var data = await resp.json(); if (data.success) { localStorage.setItem('token', data.token); localStorage.setItem('username', data.username); currentToken = data.token; currentUser = data.username; saveCredentials(un, pw, rm); closeAuthModal(); showToast('Успех!', 'Добро пожаловать, ' + currentUser, 'success'); await loadUserAvatar(currentUser); updateUI(); if (typeof onAuthStateChanged === 'function') onAuthStateChanged(true); } else showToast('Ошибка', data.error || 'Неверные данные', 'error'); } catch (e) { showToast('Ошибка', 'Нет соединения', 'error'); } }
async function register() { var u = document.getElementById('regUsername'), p = document.getElementById('regPassword'); if (!u || !p) return; var un = u.value.trim(), pw = p.value; if (!un || !pw) { showToast('Ошибка', 'Введите имя и пароль', 'error'); return; } var fd = new FormData(); fd.append('username', un); fd.append('password', pw); try { var resp = await fetch('/api/register', { method: 'POST', body: fd }); var data = await resp.json(); if (data.success) { localStorage.setItem('token', data.token); localStorage.setItem('username', data.username); currentToken = data.token; currentUser = data.username; currentUserAvatar = null; clearSavedCredentials(); closeRegisterModal(); showToast('Успех!', 'Регистрация завершена', 'success'); updateUI(); if (typeof onAuthStateChanged === 'function') onAuthStateChanged(true); } else showToast('Ошибка', data.error || 'Ошибка', 'error'); } catch (e) { showToast('Ошибка', 'Нет соединения', 'error'); } }
function logout() { localStorage.removeItem('token'); localStorage.removeItem('username'); currentToken = null; currentUser = null; currentUserAvatar = null; showToast('Выход', 'Вы вышли', 'info'); updateUI(); if (typeof onAuthStateChanged === 'function') onAuthStateChanged(false); }
function closeAuthModal() { var m = document.getElementById('authModal'); if (m) m.style.display = 'none'; }
function closeRegisterModal() { var m = document.getElementById('registerModal'); if (m) m.style.display = 'none'; }
function showAuthModal() { var m = document.getElementById('authModal'); if (m) { m.style.display = 'flex'; loadSavedCredentials(); setTimeout(initPasswordToggles, 10); } }
function showRegisterModal() { var m = document.getElementById('registerModal'); if (m) { m.style.display = 'flex'; setTimeout(initPasswordToggles, 10); } }
function showRegister() { closeAuthModal(); showRegisterModal(); }
function hideRegister() { closeRegisterModal(); showAuthModal(); }

function toggleNotifications() { var p = document.getElementById('notificationsPanel'); if (!p) return; p.classList.toggle('active'); if (p.classList.contains('active')) loadNotifications(); }
async function loadNotifications() { if (!currentToken) return; try { var r = await fetch('/api/notifications?token=' + currentToken); window._notifs = await r.json(); renderNotifications(); } catch (e) {} }
function renderNotifications() { var p = document.getElementById('notificationsPanel'), badge = document.getElementById('notifBadge'); if (!p) return; var notifs = window._notifs || [], unread = 0; for (var i = 0; i < notifs.length; i++) { if (!notifs[i].read) unread++; } if (badge) { badge.textContent = unread > 99 ? '99+' : unread; badge.style.display = unread > 0 ? 'block' : 'none'; } if (!notifs.length) { p.innerHTML = '<div class="notifications-empty">🔔 Пока нет уведомлений</div>'; return; } var html = '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;"><span style="color:#ff6b6b;">Уведомления (' + notifs.length + ')</span><button onclick="clearNotifications()" style="background:transparent;border:none;color:#aaa;cursor:pointer;font-size:0.8rem;">🗑️ Очистить</button></div>'; for (var i = 0; i < notifs.length; i++) { var n = notifs[i], icon = n.type === 'like' ? '❤️' : '💬', text = '<strong>@' + escapeHtml(n.from_user) + '</strong> '; if (n.type === 'like') text += 'лайкнул вашу работу'; else if (n.type === 'reply') text += 'ответил на ваш комментарий'; else text += 'прокомментировал вашу работу'; var bg = n.read ? '' : 'background:rgba(233,69,96,0.05);'; html += '<div class="notification-item" style="' + bg + '"><div class="notification-icon">' + icon + '</div><div class="notification-text">' + text + '<div class="notification-time">' + formatNotifTime(n.timestamp) + '</div></div></div>'; } p.innerHTML = html; }
function formatNotifTime(ts) { var d = Date.now() - new Date(ts).getTime(); if (d < 60000) return 'только что'; if (d < 3600000) return Math.floor(d / 60000) + ' мин.'; if (d < 86400000) return Math.floor(d / 3600000) + ' ч.'; return new Date(ts).toLocaleDateString('ru-RU', { day: 'numeric', month: 'short' }); }
async function clearNotifications() { var fd = new FormData(); fd.append('token', currentToken); await fetch('/api/notifications/clear', { method: 'POST', body: fd }); window._notifs = []; renderNotifications(); }

document.addEventListener('click', function(e) { var am = document.getElementById('authModal'), rm = document.getElementById('registerModal'), np = document.getElementById('notificationsPanel'), nb = document.querySelector('.notifications-btn'); if (e.target === am) am.style.display = 'none'; if (e.target === rm) rm.style.display = 'none'; if (np && nb && !np.contains(e.target) && !nb.contains(e.target)) np.classList.remove('active'); });
document.addEventListener('keydown', function(e) { if (e.key === 'Escape') { closeAuthModal(); closeRegisterModal(); } });
document.addEventListener('DOMContentLoaded', function() { loadUser(); setTimeout(function() { if (document.getElementById('loginUsername')) loadSavedCredentials(); }, 100); });