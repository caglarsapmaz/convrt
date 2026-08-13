document.addEventListener('DOMContentLoaded', () => {
    // --- ÇEVİRİ SÖZLÜĞÜ (i18n) ---
    const i18n = {
        en: {
            title: "100% Free. Lightning Fast.<br><span class='accent-text'>Zero Ads.</span>",
            subtitle: "Secure, local-first conversion. Your files are never stored.",
            dropTitle: "Drag & drop your file here",
            dropDesc: "or click to browse from your computer",
            lightMode: "Light Mode",
            darkMode: "Dark Mode",
            errorSize: "File is too large. Maximum size is {max} MB.",
            errorFormat: "Unsupported file format.",
            convertTo: "Convert to:",
            cancel: "Cancel",
            convertBtn: "Convert to",
            converting: "Converting your file...",
            formattingNote: "Formatting may vary depending on the source document.",
            completed: "Conversion Completed!",
            convertAnother: "Convert Another File",
            error: "Error",
            tryAgain: "Try Again",
            errorGeneric: "Something went wrong while converting your file.",
            builtBy: "Built by Çağlar Sapmaz"
        },
        tr: {
            title: "%100 Ücretsiz. Işık Hızında.<br><span class='accent-text'>Sıfır Reklam.</span>",
            subtitle: "Güvenli ve yerel dönüşüm. Dosyalarınız asla kaydedilmez.",
            dropTitle: "Dosyanızı buraya sürükleyin",
            dropDesc: "veya bilgisayarınızdan seçmek için tıklayın",
            lightMode: "Açık Tema",
            darkMode: "Koyu Tema",
            errorSize: "Dosya çok büyük. Maksimum boyut {max} MB.",
            errorFormat: "Desteklenmeyen dosya formatı.",
            convertTo: "Hedef Format:",
            cancel: "İptal",
            convertBtn: "Dönüştür",
            converting: "Dosyanız dönüştürülüyor...",
            formattingNote: "Kaynak belgeye bağlı olarak biçimlendirmede farklılıklar olabilir.",
            completed: "Dönüşüm Tamamlandı!",
            convertAnother: "Başka Bir Dosya Dönüştür",
            error: "Hata",
            tryAgain: "Tekrar Dene",
            errorGeneric: "Dosyanız dönüştürülürken bir hata oluştu.",
            builtBy: "Çağlar Sapmaz tarafından geliştirildi"
        }
    };

    // Maksimum boyut, backend'deki /api/config uç noktasından alınır (tek kaynak).
    // Sunucuya erişilemezse güvenli varsayılan kullanılır.
    let MAX_FILE_SIZE_MB = 4.5;

    fetch('/api/config')
        .then(r => r.json())
        .then(cfg => {
            if (cfg && typeof cfg.max_file_size_mb === 'number') {
                MAX_FILE_SIZE_MB = cfg.max_file_size_mb;
            }
        })
        .catch(() => { /* varsayılan değerle devam edilir */ });

    let currentLang = 'en';

    const dropZone = document.getElementById('drop-zone');
    const themeBtn = document.getElementById('theme-toggle');
    const htmlEl = document.documentElement;
    const originalDropZoneHTML = dropZone.innerHTML;

    let currentFile = null;
    let selectedTargetFormat = null;

    // --- YARDIMCILAR ---
    // innerHTML'e yazılan tüm dinamik metinlerden geçirilir (XSS koruması)
    function escapeHtml(value) {
        const div = document.createElement('div');
        div.textContent = String(value ?? '');
        return div.innerHTML;
    }

    function getFileInput() {
        return document.getElementById('file-input');
    }

    // Drop zone içeriği her sıfırlandığında yeni <input> oluşur; bu yüzden
    // dinleyici her seferinde yeniden bağlanmalıdır (aksi halde dosya seçici çalışmaz).
    function attachFileInput() {
        const input = getFileInput();
        if (input) {
            input.addEventListener('change', function () {
                handleFiles(this.files);
            });
        }
    }

    function applyLanguage(lang) {
        currentLang = lang;
        htmlEl.lang = lang === 'tr' ? 'tr' : 'en';
        document.querySelectorAll('[data-i18n]').forEach(el => {
            const key = el.getAttribute('data-i18n');
            if (i18n[lang][key]) {
                el.innerHTML = i18n[lang][key];
            }
        });
        const isDark = htmlEl.getAttribute('data-theme') === 'dark';
        themeBtn.textContent = isDark ? i18n[lang].lightMode : i18n[lang].darkMode;
    }

    // --- DARK / LIGHT MODE ---
    // Öncelik: URL parametresi (?theme=) > kayıtlı tercih > sistem teması
    const urlTheme = new URLSearchParams(window.location.search).get('theme');
    const savedTheme = localStorage.getItem('theme');
    if (urlTheme === 'light' || urlTheme === 'dark') {
        htmlEl.setAttribute('data-theme', urlTheme);
    } else if (savedTheme) {
        htmlEl.setAttribute('data-theme', savedTheme);
    } else if (window.matchMedia && window.matchMedia('(prefers-color-scheme: light)').matches) {
        htmlEl.setAttribute('data-theme', 'light');
    }
    themeBtn.textContent = htmlEl.getAttribute('data-theme') === 'dark'
        ? i18n[currentLang].lightMode : i18n[currentLang].darkMode;

    themeBtn.addEventListener('click', () => {
        const newTheme = htmlEl.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
        htmlEl.setAttribute('data-theme', newTheme);
        localStorage.setItem('theme', newTheme);
        themeBtn.textContent = newTheme === 'dark'
            ? i18n[currentLang].lightMode : i18n[currentLang].darkMode;
    });

    // --- DİL SEÇİMİ ---
    document.querySelectorAll('.lang-option').forEach(option => {
        option.addEventListener('click', (e) => {
            document.querySelectorAll('.lang-option').forEach(el => el.classList.remove('active'));
            e.target.classList.add('active');
            applyLanguage(e.target.getAttribute('data-lang'));
            if (currentFile) {
                resetUI();
            }
        });
    });

    // --- DOSYA İKONU BELİRLEYİCİ ---
    function getFileIcon(fileName) {
        const ext = fileName.split('.').pop().toLowerCase();
        switch (ext) {
            case 'pdf': return '<i class="fa-solid fa-file-pdf" style="color: #F40F02;"></i>';
            case 'docx': return '<i class="fa-solid fa-file-word" style="color: #2B579A;"></i>';
            case 'xlsx': return '<i class="fa-solid fa-file-excel" style="color: #217346;"></i>';
            case 'csv': return '<i class="fa-solid fa-file-csv" style="color: #28a745;"></i>';
            case 'html': case 'htm': return '<i class="fa-solid fa-file-code" style="color: #e34c26;"></i>';
            case 'txt': return '<i class="fa-solid fa-file-lines" style="color: #6c757d;"></i>';
            case 'jpg': case 'jpeg': case 'png': case 'webp': case 'gif': case 'bmp': case 'tiff': case 'ico':
                return '<i class="fa-solid fa-file-image" style="color: #0078D7;"></i>';
            default: return '<i class="fa-solid fa-file" style="color: #777777;"></i>';
        }
    }

    // Backend'deki SUPPORTED_TARGETS (api/index.py) ile birebir uyumlu
    const conversionMap = {
        'pdf': ['docx', 'txt', 'html', 'png', 'jpg'],
        'docx': ['pdf', 'txt'],
        'txt': ['docx'],
        'html': ['pdf'],
        'htm': ['pdf'],
        'xlsx': ['csv'],
        'csv': ['xlsx'],
        'png': ['jpg', 'webp', 'gif', 'bmp', 'tiff', 'ico', 'pdf'],
        'jpg': ['png', 'webp', 'gif', 'bmp', 'tiff', 'ico', 'pdf'],
        'jpeg': ['png', 'webp', 'gif', 'bmp', 'tiff', 'ico', 'pdf'],
        'webp': ['png', 'jpg', 'gif', 'bmp', 'tiff', 'ico', 'pdf'],
        'gif': ['png', 'jpg', 'webp', 'bmp', 'tiff', 'ico', 'pdf'],
        'bmp': ['png', 'jpg', 'webp', 'gif', 'tiff', 'ico', 'pdf'],
        'tiff': ['png', 'jpg', 'webp', 'gif', 'bmp', 'ico', 'pdf'],
        'ico': ['png', 'jpg', 'webp', 'gif', 'bmp', 'tiff', 'pdf']
    };

    // --- DRAG & DROP VE UI ---
    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
        dropZone.addEventListener(eventName, preventDefaults, false);
    });

    function preventDefaults(e) {
        e.preventDefault();
        e.stopPropagation();
    }

    ['dragenter', 'dragover'].forEach(eventName => {
        dropZone.addEventListener(eventName, () => dropZone.style.borderColor = 'var(--accent)', false);
    });

    ['dragleave', 'drop'].forEach(eventName => {
        dropZone.addEventListener(eventName, () => dropZone.style.borderColor = 'var(--border)', false);
    });

    dropZone.addEventListener('drop', (e) => {
        handleFiles(e.dataTransfer.files);
    });

    dropZone.addEventListener('click', (e) => {
        if (!e.target.closest('.format-btn') && !e.target.closest('.action-buttons')) {
            const input = getFileInput();
            if (input) input.click();
        }
    });

    attachFileInput();

    function handleFiles(files) {
        if (!files || files.length === 0) return;
        const file = files[0];

        const fileSizeMB = file.size / (1024 * 1024);
        if (fileSizeMB > MAX_FILE_SIZE_MB) {
            showError(i18n[currentLang].errorSize.replace('{max}', String(MAX_FILE_SIZE_MB)));
            return;
        }

        const ext = file.name.split('.').pop().toLowerCase();
        if (!conversionMap[ext]) {
            showError(i18n[currentLang].errorFormat);
            return;
        }

        currentFile = file;
        renderConversionUI(file, ext);
    }

    // --- ŞIK BUTONLU YENİ ARAYÜZ ---
    function renderConversionUI(file, ext) {
        const targets = conversionMap[ext];
        selectedTargetFormat = targets[0];

        const formatBtnsHTML = targets.map(t =>
            `<button class="format-btn ${t === selectedTargetFormat ? 'selected' : ''}" data-format="${t}">${t.toUpperCase()}</button>`
        ).join('');

        dropZone.innerHTML = `
            <div style="width: 100%; display: flex; flex-direction: column; height: 100%; justify-content: center;">
                <div class="file-preview">
                    <div class="file-preview-icon">
                        ${getFileIcon(file.name)}
                    </div>
                    <div class="file-preview-details">
                        <span class="file-preview-name">${escapeHtml(file.name)}</span>
                        <span class="file-preview-size">${(file.size / (1024*1024)).toFixed(2)} MB</span>
                    </div>
                </div>

                <div style="margin-bottom: 0.5rem; color: var(--text-muted); font-size: 0.9rem;">${i18n[currentLang].convertTo}</div>

                <div class="format-grid">
                    ${formatBtnsHTML}
                </div>

                <div class="action-buttons">
                    <button class="btn-cancel" id="cancel-btn">${i18n[currentLang].cancel}</button>
                    <button class="btn-convert" id="convert-btn">${i18n[currentLang].convertBtn} ${selectedTargetFormat.toUpperCase()}</button>
                </div>
            </div>
        `;

        const formatBtns = document.querySelectorAll('.format-btn');
        const convertBtn = document.getElementById('convert-btn');

        formatBtns.forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                formatBtns.forEach(b => b.classList.remove('selected'));
                btn.classList.add('selected');

                selectedTargetFormat = btn.getAttribute('data-format');
                convertBtn.textContent = `${i18n[currentLang].convertBtn} ${selectedTargetFormat.toUpperCase()}`;
            });
        });

        document.getElementById('cancel-btn').addEventListener('click', (e) => {
            e.stopPropagation();
            resetUI();
        });

        document.getElementById('convert-btn').addEventListener('click', (e) => {
            e.stopPropagation();
            startConversion();
        });
    }

    function resetUI() {
        currentFile = null;
        selectedTargetFormat = null;
        dropZone.innerHTML = originalDropZoneHTML;
        const input = getFileInput();
        if (input) input.value = '';
        // Yeni <input> öğesine dinleyiciyi yeniden bağla (dosya seçme bug'ı düzeltmesi)
        attachFileInput();
        applyLanguage(currentLang);
    }

    // --- BACKEND İLE İLETİŞİM ---
    async function startConversion() {
        if (!currentFile || !selectedTargetFormat) return;

        const formData = new FormData();
        formData.append('file', currentFile);
        formData.append('target_format', selectedTargetFormat);

        dropZone.innerHTML = `
            <div style="text-align: center; color: var(--accent); display: flex; flex-direction: column; align-items: center; justify-content: center; height: 100%;">
                <i class="fa-solid fa-circle-notch fa-spin" style="font-size: 32px; margin-bottom: 1rem;"></i>
                <p style="font-weight: 600; font-size: 1.1rem; color: var(--text-main);">${i18n[currentLang].converting}</p>
                <p style="font-size: 0.85rem; color: var(--text-muted); margin-top: 0.5rem;">${i18n[currentLang].formattingNote}</p>
            </div>
        `;

        try {
            const response = await fetch('/api/convert', {
                method: 'POST',
                body: formData
            });

            if (!response.ok) {
                let message = i18n[currentLang].errorGeneric;
                try {
                    const errorData = await response.json();
                    if (errorData && errorData.detail) {
                        message = errorData.detail;
                    }
                } catch (_) { /* JSON yoksa genel mesaj kullanılır */ }
                throw new Error(message);
            }

            const blob = await response.blob();
            const downloadUrl = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = downloadUrl;

            const contentDisposition = response.headers.get('content-disposition') || '';
            const match = contentDisposition.match(/filename="?([^";]+)"?/i);
            const filename = match ? match[1] : `converted.${selectedTargetFormat}`;

            a.download = filename;
            document.body.appendChild(a);
            a.click();
            a.remove();
            window.URL.revokeObjectURL(downloadUrl);

            dropZone.innerHTML = `
                <div style="text-align: center; display: flex; flex-direction: column; align-items: center; justify-content: center; height: 100%;">
                    <div style="color: #34c759; margin-bottom: 1rem;">
                        <i class="fa-solid fa-circle-check" style="font-size: 40px;"></i>
                    </div>
                    <p style="font-weight: 600; font-size: 1.2rem; color: var(--text-main);">${i18n[currentLang].completed}</p>
                    <button class="btn-cancel" id="convert-another-btn" style="margin-top: 1.5rem;">${i18n[currentLang].convertAnother}</button>
                </div>
            `;

            document.getElementById('convert-another-btn').addEventListener('click', (e) => {
                e.stopPropagation();
                resetUI();
            });

        } catch (error) {
            showError(error.message);
        }
    }

    function showError(message) {
        dropZone.innerHTML = `
            <div style="text-align: center; display: flex; flex-direction: column; align-items: center; justify-content: center; height: 100%;">
                <div style="color: #ff3b30; margin-bottom: 1rem;">
                    <i class="fa-solid fa-circle-exclamation" style="font-size: 32px;"></i>
                </div>
                <p style="font-weight: 600; font-size: 1rem; color: var(--text-main);">${i18n[currentLang].error}</p>
                <p style="font-size: 0.9rem; color: var(--text-muted); margin-top: 0.5rem; max-width: 300px; margin-left: auto; margin-right: auto;">${escapeHtml(message)}</p>
                <button class="btn-cancel" id="try-again-btn" style="margin-top: 1.5rem;">${i18n[currentLang].tryAgain}</button>
            </div>
        `;
        document.getElementById('try-again-btn').addEventListener('click', (e) => {
            e.stopPropagation();
            resetUI();
        });
    }
});
