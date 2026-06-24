const output = document.getElementById('consola-output');
const input = document.getElementById('consola-input');
const texto = document.getElementById('consola-texto');
const statusText = document.getElementById('consola-status');

const params = new URLSearchParams(window.location.search);
const API_URL = params.get('api') || `${window.location.origin}/api/consola`;

let comandosDisponibles = {};
let currentDir = '/';
let backendStatus = 'connecting';
let cmatrixActive = false;
let cmatrixInterval = null;

function appendOutput(text = '') {
    output.textContent += text;
    output.scrollTop = output.scrollHeight;
}

function tokenizar(commandLine) {
    const tokens = [];
    const pattern = /"([^"\\]*(?:\\.[^"\\]*)*)"|'([^'\\]*(?:\\.[^'\\]*)*)'|(\S+)/g;
    let match;

    while ((match = pattern.exec(commandLine)) !== null) {
        const value = match[1] ?? match[2] ?? match[3] ?? '';
        tokens.push(value.replace(/\\(["'])/g, '$1'));
    }

    return tokens;
}

function dirDisplay(path = currentDir) {
    return path === '/' ? '/' : path;
}

function setStatus(status, message) {
    backendStatus = status;
    statusText.textContent = message;
    statusText.dataset.status = status;
}

async function cargarComandos() {
    try {
        const response = await fetch(`${API_URL}/commands`);
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const data = await response.json();
        comandosDisponibles = data.commands;
        setStatus('online', `read-only backend: ${API_URL}`);
    } catch (error) {
        setStatus('offline', `backend offline: ${API_URL}`);
        appendOutput(`No se pudo conectar al backend en ${API_URL}\n`);
        appendOutput(`Verifica que backend/main.py este corriendo y que CONSOLA_BACKEND_URL apunte al puerto correcto.\n\n`);
    }
}

async function ejecutarComandoAPI(rawCommand) {
    const args = tokenizar(rawCommand);
    const comando = args[0]?.toLowerCase();

    try {
        const response = await fetch(`${API_URL}/execute`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                command: comando,
                args: args.slice(1),
                cwd: currentDir,
                raw: rawCommand,
            }),
        });

        if (!response.ok) {
            return { output: `Error del servidor: HTTP ${response.status}`, success: false };
        }

        const data = await response.json();
        setStatus('online', `read-only backend: ${API_URL}`);

        if (data.cwd) {
            currentDir = data.cwd;
            actualizarPrompt();
            actualizarTitulo();
        }

        return data;
    } catch (error) {
        setStatus('offline', `backend offline: ${API_URL}`);
        return { output: 'Error de conexion al servidor', success: false };
    }
}

function actualizarPrompt() {
    const prompt = document.getElementById('consola-prompt');
    prompt.textContent = `consola@server:${dirDisplay()}$ `;
}

function actualizarTitulo() {
    document.title = `consola - ${dirDisplay()}`;
}

function iniciarCMatrix() {
    cmatrixActive = true;
    const chars = "01アイウエオカキクケコサシスセソタチツテトナニヌネノハヒフヘホマミムメモヤユヨラリルレロワヲン";
    const columns = Math.max(24, Math.floor(output.clientWidth / 8));
    const streams = [];

    for (let i = 0; i < columns; i++) {
        streams.push({
            y: Math.random() * 20,
            speed: Math.random() * 0.5 + 0.5,
            char: () => chars[Math.floor(Math.random() * chars.length)],
        });
    }

    cmatrixInterval = setInterval(() => {
        if (!cmatrixActive) {
            clearInterval(cmatrixInterval);
            return;
        }

        let matrix = "";

        for (let y = 0; y < 30; y++) {
            for (let x = 0; x < columns; x++) {
                const stream = streams[x];
                matrix += Math.abs(y - stream.y) < 3 ? stream.char() : " ";
            }
            matrix += "\n";
        }

        output.innerHTML = `<span class="matrix">${matrix.replace(/</g, '&lt;').replace(/>/g, '&gt;')}</span>`;

        streams.forEach((stream) => {
            stream.y += stream.speed;
            if (stream.y > 30) stream.y = 0;
        });
    }, 100);
}

function detenerCMatrix() {
    cmatrixActive = false;
    if (cmatrixInterval) clearInterval(cmatrixInterval);
}

async function ejecutarComando(cmd) {
    if (!cmd.trim()) return;

    if (cmatrixActive) {
        detenerCMatrix();
        output.textContent += '\n';
    }

    appendOutput(`consola@server:${dirDisplay()}$ ${cmd}\n`);

    const resultado = await ejecutarComandoAPI(cmd);

    if (resultado.clear) {
        output.textContent = '';
    } else if (resultado.cmatrix) {
        iniciarCMatrix();
    } else if (resultado.output) {
        appendOutput(`${resultado.output}\n`);
    }
}

input.addEventListener('keydown', (event) => {
    if (event.key === 'Enter') {
        ejecutarComando(input.value);
        input.value = '';
        texto.textContent = '';
    } else if (event.key === 'c' && event.ctrlKey && cmatrixActive) {
        event.preventDefault();
        detenerCMatrix();
        appendOutput('\n^C\n');
        actualizarPrompt();
    }
});

input.addEventListener('input', () => {
    texto.textContent = input.value;
});

document.addEventListener('click', () => {
    input.focus();
});

window.addEventListener('load', () => {
    output.textContent = [
        'Consola System',
        'Modo: solo lectura sobre carpeta intermediaria real',
        "Type 'help' for commands",
        '',
    ].join('\n');
    actualizarPrompt();
    actualizarTitulo();
    input.focus();
    cargarComandos();
});
