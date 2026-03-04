document.addEventListener('DOMContentLoaded', () => {
    // Состояние приложения
    const state = {
        projectLoaded: false,
        scenes: [],
        selectedSceneUuid: null,
        chatHistory: [],
        filePath: null
    };

    const apiKeyScreen = document.getElementById('api-key-screen');
    const mainScreen = document.getElementById('main-screen');
    const undoBtn = document.getElementById('undo-btn');

    // Проверка API ключа
    checkConfig();

    async function checkConfig() {
        try {
            const res = await fetch('/api/config');
            const data = await res.json();
            if (!data.has_api_key) {
                alert("Ескерту: API кілті серверде табылмады! Кешікпей .env файлына GEMINI_API_KEY мәнін қосыңыз.");
            }
        } catch (e) {
            console.error("Config fetch error", e);
        }
    }

    // Переключение между инструментами
    document.querySelectorAll('.tool-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            document.querySelectorAll('.tool-btn').forEach(b => b.classList.remove('active'));
            e.target.classList.add('active');

            const toolId = e.target.getAttribute('data-tool');
            document.querySelectorAll('.tool-view').forEach(v => v.classList.add('hidden'));
            document.getElementById(`tool-${toolId}`).classList.remove('hidden');
        });
    });

    // Загрузка проекта
    document.getElementById('open-project-btn').addEventListener('click', () => {
        document.getElementById('file-input').click();
    });

    // Из-за ограничений безопасности браузер может скрыть полный путь.
    // Если file.path недоступен — запросим его у пользователя вручную.
    document.getElementById('file-input').addEventListener('change', async (e) => {
        if (!e.target.files.length) return;
        const file = e.target.files[0];

        let filePath = file.path;
        if (!filePath) {
            filePath = prompt("Браузер қауіпсіздігі файлдың толық жолын жасырады. Өтініш, файлдың толық жолын енгізіңіз (мысалы: C:\\Users\\...\\project.kitsp):", file.name);
        }

        if (!filePath) return;

        try {
            document.getElementById('project-name-display').innerText = "Жүктелуде...";
            const res = await fetch('/api/project/load', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ path: filePath })
            });
            const data = await res.json();

            if (data.scenes && data.project_name) {
                state.projectLoaded = true;
                state.scenes = data.scenes;
                state.filePath = filePath;
                document.getElementById('project-name-display').innerText = data.project_name;

                // Если нет памяти, создаём базовую пустую
                if (!data.has_memory) {
                    await fetch('/api/memory/save', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ synopsis: "", characters: [] })
                    });
                }

                renderScenes();
                loadProjectMemory();
            } else {
                alert("Жобаны жүктеу қатесі: " + (data.detail || "белгісіз қате"));
                document.getElementById('project-name-display').innerText = "Жоба таңдалмаған";
            }
        } catch (err) {
            alert("Қате: " + err.message);
            document.getElementById('project-name-display').innerText = "Жоба таңдалмаған";
        }
    });

    async function reloadScenes() {
        if (!state.filePath) return;
        try {
            const res = await fetch('/api/project/load', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ path: state.filePath })
            });
            const data = await res.json();
            if (data.scenes) {
                state.scenes = data.scenes;
                renderScenes();
            }
        } catch (e) {
            console.error("Reload scenes error", e);
        }
    }

    function renderScenes() {
        const container = document.getElementById('scenes-list');
        container.innerHTML = '';
        state.scenes.forEach(scene => {
            const div = document.createElement('div');
            div.className = 'scene-item';
            if (scene.uuid === state.selectedSceneUuid) div.classList.add('selected');

            const title = document.createElement('div');
            title.className = 'scene-title';
            title.innerText = `${scene.index}. ${scene.heading}`;
            div.appendChild(title);

            if (scene.has_dialogue) {
                const icon = document.createElement('div');
                icon.className = 'dialogue-indicator';
                icon.innerText = '💬';
                icon.title = 'Диалог бар';
                div.appendChild(icon);
            }

            div.addEventListener('click', () => selectScene(scene));
            container.appendChild(div);
        });
    }

    function selectScene(scene) {
        state.selectedSceneUuid = scene.uuid;
        renderScenes(); // Обновляем класс selected

        const sceneName = `${scene.index}. ${scene.heading}`;
        document.getElementById('dialogue-selected-scene').innerText = sceneName;
        document.getElementById('improve-selected-scene').innerText = sceneName;

        document.getElementById('dialogue-generate-btn').disabled = false;
        checkImproveBtn();
    }

    // Соңғы өзгерісті болдырмау (Доступ к кнопке "Отменить")
    function enableUndo() {
        undoBtn.disabled = false;
    }

    undoBtn.addEventListener('click', async () => {
        try {
            const res = await fetch('/api/undo', { method: 'POST' });
            const data = await res.json();
            if (data.success) {
                alert("Соңғы өзгеріс ойдағыдай болдырмалынды!");
                undoBtn.disabled = true;
            } else {
                alert("Қате: " + data.error);
            }
        } catch (e) {
            alert("Қате: " + e.message);
        }
    });

    // ============================================
    // ЖОБА МӘЛІМЕТТЕРІ (PROJECT DETAILS)
    // ============================================
    document.getElementById('save-project-data-btn').addEventListener('click', async () => {
        const synopsis = document.getElementById('project-synopsis').value;
        const characters_raw = document.getElementById('project-characters-raw').value;

        const btn = document.getElementById('save-project-data-btn');
        btn.disabled = true;
        btn.innerText = "Сақталуда...";

        try {
            const res = await fetch('/api/memory/parse-and-save', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ synopsis, characters_raw })
            });
            const data = await res.json();
            if (data.success) {
                alert('Мәліметтер сақталды!');
                renderParsedCharacters(data.characters);
            } else {
                alert('Қате: ' + (data.error || data.detail));
            }
        } catch (e) {
            alert('Қате: ' + e.message);
        } finally {
            btn.disabled = false;
            btn.innerText = "Сақтау";
        }
    });

    function renderParsedCharacters(characters) {
        const resDiv = document.getElementById('parsed-characters-result');
        if (!characters || characters.length === 0) {
            resDiv.innerText = "Кейіпкерлер табылған жоқ.";
            return;
        }
        let html = `<strong>Распознано ${characters.length} кейіпкер:</strong><br/>`;
        characters.forEach(c => {
            html += `- ${c.name}, ${c.age} жас — ${c.role_type}<br/>`;
        });
        resDiv.innerHTML = html;
    }

    async function loadProjectMemory() {
        try {
            const res = await fetch('/api/memory/load');
            const data = await res.json();
            if (!data.error) {
                document.getElementById('project-synopsis').value = data.synopsis || '';
                document.getElementById('project-characters-raw').value = data.characters_raw || '';

                if (data.characters && data.characters.length) {
                    renderParsedCharacters(data.characters);
                } else {
                    document.getElementById('parsed-characters-result').innerHTML = '';
                }
            }
        } catch (e) {
            console.error("Memory load error", e);
        }
    }

    // ============================================
    // ПОЭПИЗОДНИК ЖАСАУ
    // ============================================
    const outlineBtn = document.getElementById('outline-start-btn');
    outlineBtn.addEventListener('click', async () => {
        const wants = document.getElementById('outline-wants').value;
        const pBox = document.getElementById('outline-progress');
        const pText = document.getElementById('outline-status');

        pBox.classList.remove('hidden');
        outlineBtn.disabled = true;
        pText.innerText = "БАСТАЛУДА...";

        try {
            const response = await fetch('/api/outline/generate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ user_message: wants })
            });

            const reader = response.body.getReader();
            const decoder = new TextDecoder();

            while (true) {
                const { value, done } = await reader.read();
                if (done) break;

                const chunks = decoder.decode(value).split('\n');
                for (let chunk of chunks) {
                    if (chunk.startsWith('data: ')) {
                        const dataStr = chunk.replace('data: ', '');
                        if (dataStr === '[DONE]') break;
                        try {
                            const data = JSON.parse(dataStr);
                            if (data.step) {
                                pText.innerText = data.message;
                                if (data.step === 'done') {
                                    enableUndo();
                                    outlineBtn.disabled = false;
                                    await reloadScenes();
                                } else if (data.step === 'error') {
                                    outlineBtn.disabled = false;
                                }
                            }
                        } catch (e) { } // игнорируем пустые или битые чанки
                    }
                }
            }
        } catch (e) {
            pText.innerText = "Қате: " + e.message;
            outlineBtn.disabled = false;
        }
    });

    // ============================================
    // ДИАЛОГ ЖАЗУ
    // ============================================
    const dialogueBtn = document.getElementById('dialogue-generate-btn');
    dialogueBtn.addEventListener('click', async () => {
        if (!state.selectedSceneUuid) return;

        const wants = document.getElementById('dialogue-wants').value;
        const pBox = document.getElementById('dialogue-progress');
        const pText = document.getElementById('dialogue-status');

        pBox.classList.remove('hidden');
        dialogueBtn.disabled = true;
        pText.innerText = "Генерация жасалуда...";

        try {
            const res = await fetch('/api/dialogue/generate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ scene_uuid: state.selectedSceneUuid, user_message: wants })
            });
            const data = await res.json();
            if (data.success) {
                pText.innerText = "Дайын! KIT Scenarist-те көріңіз.";
                enableUndo();
            } else {
                pText.innerText = "Қате: " + data.error;
            }
        } catch (e) {
            pText.innerText = "Қате: " + e.message;
        } finally {
            dialogueBtn.disabled = false;
        }
    });

    // ============================================
    // СЦЕНАНЫ ЖАҚСАРТУ
    // ============================================
    const improveWants = document.getElementById('improve-wants');
    const improveBtn = document.getElementById('improve-generate-btn');

    function checkImproveBtn() {
        improveBtn.disabled = !state.selectedSceneUuid || !improveWants.value.trim();
    }

    improveWants.addEventListener('input', checkImproveBtn);

    improveBtn.addEventListener('click', async () => {
        if (!state.selectedSceneUuid || !improveWants.value.trim()) return;

        const pBox = document.getElementById('improve-progress');
        const pText = document.getElementById('improve-status');

        pBox.classList.remove('hidden');
        improveBtn.disabled = true;
        pText.innerText = "Жақсартылуда...";

        try {
            const res = await fetch('/api/improve/generate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ scene_uuid: state.selectedSceneUuid, user_message: improveWants.value })
            });
            const data = await res.json();
            if (data.success) {
                pText.innerText = "Дайын! KIT Scenarist-те көріңіз.";
                enableUndo();
            } else {
                pText.innerText = "Қате: " + data.error;
            }
        } catch (e) {
            pText.innerText = "Қате: " + e.message;
        } finally {
            checkImproveBtn();
        }
    });

    // ============================================
    // БОС ЧАТ (STREAMING)
    // ============================================
    const chatInput = document.getElementById('chat-input');
    const chatSendBtn = document.getElementById('chat-send-btn');
    const chatHistoryBox = document.getElementById('chat-history');

    chatInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendChatMessage();
        }
    });
    chatSendBtn.addEventListener('click', sendChatMessage);

    async function sendChatMessage() {
        const text = chatInput.value.trim();
        if (!text) return;

        chatInput.value = '';

        // Добавляем сообщение пользователя
        addChatMessage(text, 'user');

        // Добавляем пустой блок для потокового ответа ИИ
        const botMsgObj = addChatMessage('Ойлануда...', 'bot');

        const requestBody = {
            message: text,
            history: state.chatHistory.map(m => ({ role: m.role, text: m.text }))
        };

        state.chatHistory.push({ role: 'user', text: text });

        try {
            const response = await fetch('/api/chat/message', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(requestBody)
            });

            const reader = response.body.getReader();
            const decoder = new TextDecoder();

            let fullReply = "";
            botMsgObj.elem.innerText = "";

            while (true) {
                const { value, done } = await reader.read();
                if (done) break;

                const chunkStr = decoder.decode(value);
                const lines = chunkStr.split('\n');

                for (let line of lines) {
                    if (line.startsWith('data: ')) {
                        const dataStr = line.replace('data: ', '');
                        if (dataStr === '[DONE]') break;
                        try {
                            const data = JSON.parse(dataStr);
                            if (data.chunk) {
                                fullReply += data.chunk;
                                botMsgObj.elem.innerText = fullReply;
                                chatHistoryBox.scrollTop = chatHistoryBox.scrollHeight;
                            } else if (data.error) {
                                botMsgObj.elem.innerText += `\n[Қате: ${data.error}]`;
                            }
                        } catch (e) { }
                    }
                }
            }

            state.chatHistory.push({ role: 'bot', text: fullReply });
            botMsgObj.addInsertButton(); // Добавляем кнопку "Файлға енгізу"

        } catch (e) {
            botMsgObj.elem.innerText = "Қате: " + e.message;
        }
    }

    function addChatMessage(text, role) {
        const wrapper = document.createElement('div');
        wrapper.className = `chat-msg ${role}`;

        const content = document.createElement('div');
        content.innerText = text;
        wrapper.appendChild(content);

        chatHistoryBox.appendChild(wrapper);
        chatHistoryBox.scrollTop = chatHistoryBox.scrollHeight;

        return {
            elem: content,
            addInsertButton: () => {
                const btn = document.createElement('button');
                btn.className = 'insert-btn';
                btn.innerText = 'Таңдалған көрініске енгізу (Файлға)';
                btn.onclick = async () => {
                    if (!state.selectedSceneUuid) {
                        return alert("Алдымен оң жақтан көріністі таңдаңыз!");
                    }
                    try {
                        const res = await fetch('/api/chat/insert', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({
                                scene_uuid: state.selectedSceneUuid,
                                content: content.innerText
                            })
                        });
                        const data = await res.json();
                        if (data.success) {
                            alert("Енгізілді! KIT Scenarist-те көріңіз.");
                            enableUndo();
                        } else {
                            alert("Қате: " + data.error);
                        }
                    } catch (e) {
                        alert("Қате: " + e.message);
                    }
                };
                wrapper.appendChild(btn);
            }
        };
    }
});
