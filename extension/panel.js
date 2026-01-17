const WS_URL = "ws://127.0.0.1:8000/ws";

let ws;
const chat = document.getElementById('chat');
const input = document.getElementById('input');
const sendBtn = document.getElementById('send-btn');
const stopBtn = document.getElementById('stop-btn');
const pauseBtn = document.getElementById('pause-btn');
const clearBtn = document.getElementById('clear-btn');
const statusDot = document.getElementById('status-dot');
const typing = document.getElementById('typing');
const welcome = document.getElementById('welcome');

let isConnected = false;
let isPaused = false;

// Авто-ресайз
input.addEventListener('input', function() {
    this.style.height = 'auto';
    this.style.height = Math.min(this.scrollHeight, 100) + 'px';
});

loadHistory();

function connect() {
    ws = new WebSocket(WS_URL);

    ws.onopen = () => {
        isConnected = true;
        statusDot.className = 'status-dot online';
        ws.send(JSON.stringify({command: "get_status"}));
    };

    ws.onclose = () => {
        isConnected = false;
        statusDot.className = 'status-dot';
        setTimeout(connect, 3000);
    };

    ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        
        if (data.type === 'status') {
            if (data.is_running) setBusyState();
            else setIdleState();
            // Сброс паузы при переподключении, если сервер не запоминает (для простоты)
            isPaused = false; 
            updatePauseUI();
            return;
        }

        if (data.type === 'tool') {
            showTyping(true);
            const friendlyText = formatToolLog(data.message);
            addMsg('tool', friendlyText, true);
        }
        else if (data.type === 'success') {
            showTyping(false);
            const text = data.message.replace('Task completed', '').replace(/^{|}$/g, '').trim();
            addMsg('ai', "✅ Готово! " + text, true);
            setIdleState();
        }
        else if (data.type === 'error') {
            addMsg('error', data.message, true);
            if (!data.message.includes('Retrying')) {
                showTyping(false);
                setIdleState();
            }
        }
        else if (data.type === 'system') {
            addMsg('system', data.message, true);
        }
    };
}

connect();

// --- ЛОГИКА КНОПОК ---

function send() {
    const text = input.value.trim();
    if (!text || !isConnected) return;

    if (welcome) welcome.style.display = 'none';

    addMsg('user', text, true);
    ws.send(JSON.stringify({command: "start", task: text}));
    
    input.value = '';
    input.style.height = 'auto';
    setBusyState();
}

function stop() {
    ws.send(JSON.stringify({command: "stop"}));
    addMsg('error', "Остановлено пользователем", true);
    setIdleState();
}

// НОВОЕ: Логика паузы
function togglePause() {
    isPaused = !isPaused;
    
    if (isPaused) {
        ws.send(JSON.stringify({command: "pause"}));
        addMsg('system', "⏸️ Пауза (нажмите Play для продолжения)", true);
    } else {
        ws.send(JSON.stringify({command: "resume"}));
        addMsg('system', "▶️ Продолжаю выполнение", true);
    }
    updatePauseUI();
}

function updatePauseUI() {
    if (isPaused) {
        pauseBtn.innerHTML = "▶️ Play";
        pauseBtn.classList.add('active');
        statusDot.className = 'status-dot paused';
        showTyping(false); // Скрываем "Выполняю"
    } else {
        pauseBtn.innerHTML = "⏸️ Pause";
        pauseBtn.classList.remove('active');
        statusDot.className = 'status-dot online';
        if (stopBtn.style.display === 'block') showTyping(true); // Возвращаем если работаем
    }
}

// --- ВИЗУАЛИЗАЦИЯ ---

function formatToolLog(text) {
    text = text.replace('🔧 ', '');
    if (text.includes('navigate')) return `🌐 Перехожу: ${text.match(/'url':\s*'([^']+)'/)?.[1] || 'сайт'}`;
    if (text.includes('click')) return `👆 Клик: ${text.match(/'selector':\s*'([^']+)'/)?.[1].replace('text=', '') || 'элемент'}`;
    if (text.includes('type_text') || text.includes('fill')) return `✍️ Ввод: "${text.match(/'text':\s*'([^']+)'/)?.[1] || '...'}"`;
    if (text.includes('press_key')) return `↵ Enter`;
    if (text.includes('scroll')) return `📜 Скролл...`;
    if (text.includes('get_page_content')) return `👀 Смотрю на страницу...`;
    if (text.includes('wait')) return `⏳ Жду...`;
    return "⚙️ " + text.substring(0, 40);
}

function addMsg(type, text, save = false) {
    if (welcome) welcome.style.display = 'none';
    const lastMsg = chat.lastElementChild;

    if (type === 'error' && lastMsg && lastMsg.classList.contains('msg-error')) {
        lastMsg.textContent = text;
        if (save) updateLastInStorage(type, text);
        return;
    }
    if (type === 'tool' && lastMsg && lastMsg.textContent === text) return;

    const div = document.createElement('div');
    div.className = `msg msg-${type}`;
    div.textContent = text;
    chat.appendChild(div);
    chat.scrollTop = chat.scrollHeight;

    if (save) saveToStorage(type, text);
}

// --- Storage ---
function saveToStorage(type, text) {
    let hist = JSON.parse(localStorage.getItem('chatHistory')) || [];
    if (hist.length > 50) hist.shift();
    hist.push({ type, text });
    localStorage.setItem('chatHistory', JSON.stringify(hist));
}

function updateLastInStorage(type, text) {
    let hist = JSON.parse(localStorage.getItem('chatHistory')) || [];
    if (hist.length > 0) {
        hist[hist.length - 1] = { type, text };
        localStorage.setItem('chatHistory', JSON.stringify(hist));
    }
}

function loadHistory() {
    const hist = JSON.parse(localStorage.getItem('chatHistory')) || [];
    if (hist.length > 0 && welcome) welcome.style.display = 'none';
    hist.forEach(m => addMsg(m.type, m.text, false));
    setTimeout(() => chat.scrollTop = chat.scrollHeight, 100);
}

clearBtn.onclick = () => {
    localStorage.removeItem('chatHistory');
    chat.innerHTML = '';
    if (welcome) { chat.appendChild(welcome); welcome.style.display = 'block'; }
};

// --- STATES ---
function showTyping(show) { typing.style.display = show ? 'flex' : 'none'; }

function setBusyState() {
    input.disabled = true;
    input.placeholder = "Агент работает...";
    sendBtn.disabled = true;
    sendBtn.style.opacity = '0.5';
    stopBtn.style.display = 'block';
    pauseBtn.style.display = 'block'; // Показываем паузу
    isPaused = false;
    updatePauseUI();
}

function setIdleState() {
    input.disabled = false;
    input.placeholder = "Напиши задачу...";
    sendBtn.disabled = false;
    sendBtn.style.opacity = '1';
    stopBtn.style.display = 'none';
    pauseBtn.style.display = 'none'; // Скрываем паузу
    input.focus();
    showTyping(false);
    isPaused = false;
    updatePauseUI();
}

sendBtn.onclick = send;
stopBtn.onclick = stop;
pauseBtn.onclick = togglePause; // Хендлер паузы

input.addEventListener('keypress', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(); }
});