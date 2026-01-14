// ============================================
// LIFT UP Dataset Extraction - Frontend Logic
// ============================================

// Global variables
let selectedFile = null;
let currentTempId = null;
let currentFilename = null;

// DOM Elements
const uploadArea = document.getElementById('uploadArea');
const pdfFileInput = document.getElementById('pdfFile');
const uploadContent = document.getElementById('uploadContent');
const fileInfo = document.getElementById('fileInfo');
const fileName = document.getElementById('fileName');
const fileSize = document.getElementById('fileSize');
const removeFileBtn = document.getElementById('removeFile');
const uploadForm = document.getElementById('uploadForm');
const submitBtn = document.getElementById('submitBtn');
const progressSection = document.getElementById('progressSection');
const progressText = document.getElementById('progressText');
const resultSection = document.getElementById('resultSection');
const resultMessage = document.getElementById('resultMessage');
const downloadBtn = document.getElementById('downloadBtn');
const analyzeBtn = document.getElementById('analyzeBtn');
const resetBtn = document.getElementById('resetBtn');
const errorSection = document.getElementById('errorSection');
const errorMessage = document.getElementById('errorMessage');
const retryBtn = document.getElementById('retryBtn');
const analysisSection = document.getElementById('analysisSection');
const downloadBtnFromAnalysis = document.getElementById('downloadBtnFromAnalysis');
const closeAnalysisBtn = document.getElementById('closeAnalysisBtn');

// ============================================
// FILE UPLOAD HANDLERS
// ============================================

// Click to upload
uploadArea.addEventListener('click', () => {
    pdfFileInput.click();
});

// File selection via input
pdfFileInput.addEventListener('change', (e) => {
    if (e.target.files.length > 0) {
        handleFileSelect(e.target.files[0]);
    }
});

// Drag and drop handlers
uploadArea.addEventListener('dragover', (e) => {
    e.preventDefault();
    uploadArea.classList.add('dragover');
});

uploadArea.addEventListener('dragleave', () => {
    uploadArea.classList.remove('dragover');
});

uploadArea.addEventListener('drop', (e) => {
    e.preventDefault();
    uploadArea.classList.remove('dragover');

    if (e.dataTransfer.files.length > 0) {
        const file = e.dataTransfer.files[0];
        if (file.type === 'application/pdf') {
            pdfFileInput.files = e.dataTransfer.files;
            handleFileSelect(file);
        } else {
            showError('Lütfen sadece PDF dosyası yükleyin!');
        }
    }
});

// Remove file button
removeFileBtn.addEventListener('click', (e) => {
    e.stopPropagation();
    resetFileUpload();
});

// ============================================
// FILE HANDLING FUNCTIONS
// ============================================

function handleFileSelect(file) {
    if (!file || file.type !== 'application/pdf') {
        showError('Lütfen geçerli bir PDF dosyası seçin!');
        return;
    }

    // Check file size (50MB limit)
    const maxSize = 50 * 1024 * 1024;
    if (file.size > maxSize) {
        showError('Dosya boyutu çok büyük! Maksimum 50MB yükleyebilirsiniz.');
        return;
    }

    selectedFile = file;

    // Update UI
    fileName.textContent = file.name;
    fileSize.textContent = formatFileSize(file.size);

    uploadContent.classList.add('d-none');
    fileInfo.classList.remove('d-none');

    // Add animation
    fileInfo.style.animation = 'fadeIn 0.5s ease';
}

function resetFileUpload() {
    selectedFile = null;
    pdfFileInput.value = '';

    uploadContent.classList.remove('d-none');
    fileInfo.classList.add('d-none');

    hideAllSections();
}

function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';

    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));

    return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
}

// ============================================
// FORM SUBMISSION
// ============================================

uploadForm.addEventListener('submit', async (e) => {
    e.preventDefault();

    if (!selectedFile) {
        showError('Lütfen bir PDF dosyası seçin!');
        return;
    }

    // Prepare form data
    const formData = new FormData();
    formData.append('pdfFile', selectedFile);
    formData.append('year', document.getElementById('year').value);

    // Show progress
    showProgress();

    try {
        const response = await fetch('/process', {
            method: 'POST',
            body: formData
        });

        const data = await response.json();

        if (data.success) {
            // Store for download
            currentTempId = data.temp_id;
            currentFilename = data.csv_filename;

            // Show success
            showSuccess(data.article_count, data.csv_filename);
        } else {
            showError(data.error || 'Bir hata oluştu!');
        }

    } catch (error) {
        console.error('Error:', error);
        showError('Sunucu hatası! Lütfen daha sonra tekrar deneyin.');
    }
});

// ============================================
// DOWNLOAD HANDLER
// ============================================

downloadBtn.addEventListener('click', async () => {
    await downloadCSV();
});

downloadBtnFromAnalysis.addEventListener('click', async () => {
    await downloadCSV();
});

async function downloadCSV() {
    if (!currentTempId || !currentFilename) {
        showError('İndirme bilgileri bulunamadı!');
        return;
    }

    try {
        // Download file
        const downloadUrl = `/download/${currentTempId}/${currentFilename}`;

        // Create invisible link and click it
        const link = document.createElement('a');
        link.href = downloadUrl;
        link.download = currentFilename;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);

        // Show success notification
        showNotification('CSV dosyası indiriliyor...', 'success');

        // Cleanup after download
        setTimeout(() => {
            cleanupTempFiles();
        }, 2000);

    } catch (error) {
        console.error('Download error:', error);
        showError('İndirme sırasında bir hata oluştu!');
    }
}

// ============================================
// ANALYSIS HANDLER
// ============================================

analyzeBtn.addEventListener('click', async () => {
    if (!currentTempId || !currentFilename) {
        showError('Analiz bilgileri bulunamadı!');
        return;
    }

    try {
        showNotification('Analiz yapılıyor...', 'info');

        const response = await fetch(`/analyze/${currentTempId}/${currentFilename}`);
        const data = await response.json();

        if (data.success) {
            displayAnalysis(data.analysis);
        } else {
            showError(data.error || 'Analiz sırasında bir hata oluştu!');
        }

    } catch (error) {
        console.error('Analysis error:', error);
        showError('Analiz sırasında bir hata oluştu!');
    }
});

closeAnalysisBtn.addEventListener('click', () => {
    analysisSection.classList.add('d-none');
    resultSection.classList.remove('d-none');
});

function displayAnalysis(analysis) {
    // Genel istatistikler
    const basicStats = analysis.basic_stats;
    document.getElementById('statTotalArticles').textContent = basicStats.total_articles;
    document.getElementById('statTotalColumns').textContent = basicStats.total_columns;

    // Dosya boyutu formatla
    document.getElementById('statFileSize').textContent = formatFileSize(basicStats.file_size);

    // Eksik değerler
    const missingValues = analysis.missing_values;
    document.getElementById('statMissingValues').textContent = missingValues.total_missing;

    // Eksik değer detayları
    if (missingValues.has_missing && missingValues.details.length > 0) {
        const missingSection = document.getElementById('missingDetailsSection');
        const missingList = document.getElementById('missingDetailsList');

        let html = '<ul class="mb-0">';
        missingValues.details.forEach(item => {
            html += `<li><strong>${item.column}:</strong> ${item.count} eksik değer (${item.percentage}%)</li>`;
        });
        html += '</ul>';

        missingList.innerHTML = html;
        missingSection.classList.remove('d-none');
    }

    // Dil istatistikleri
    const langStats = analysis.language_stats;
    if (langStats) {
        document.getElementById('trPercentage').textContent = `${langStats.tr_completeness}%`;
        document.getElementById('enPercentage').textContent = `${langStats.en_completeness}%`;

        document.getElementById('trProgressBar').style.width = `${langStats.tr_completeness}%`;
        document.getElementById('enProgressBar').style.width = `${langStats.en_completeness}%`;
    }

    // İlk 5 satır
    const firstRows = analysis.first_rows;
    const tableBody = document.getElementById('dataPreviewBody');
    tableBody.innerHTML = '';

    firstRows.forEach((row, index) => {
        const tr = document.createElement('tr');

        // Durum kontrolü
        const hasAllData = row.Title_TR && row.Title_EN && row.Abstract_TR && row.Abstract_EN;
        const statusBadge = hasAllData
            ? '<span class="badge bg-success">Tam</span>'
            : '<span class="badge bg-warning">Eksik</span>';

        tr.innerHTML = `
            <td>${row.PageNumber || '-'}</td>
            <td>${row.Year || '-'}</td>
            <td title="${row.Title_TR || '-'}">${truncateText(row.Title_TR || '-', 50)}</td>
            <td title="${row.Title_EN || '-'}">${truncateText(row.Title_EN || '-', 50)}</td>
            <td>${statusBadge}</td>
        `;

        tableBody.appendChild(tr);
    });

    // Analiz bölümünü göster, result bölümünü gizle
    resultSection.classList.add('d-none');
    analysisSection.classList.remove('d-none');

    // Scroll to analysis
    analysisSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

function truncateText(text, maxLength) {
    if (!text) return '-';
    if (text.length <= maxLength) return text;
    return text.substring(0, maxLength) + '...';
}

// ============================================
// CLEANUP
// ============================================

async function cleanupTempFiles() {
    if (!currentTempId) return;

    try {
        await fetch(`/cleanup/${currentTempId}`, {
            method: 'POST'
        });
    } catch (error) {
        console.error('Cleanup error:', error);
    }
}

// ============================================
// RESET HANDLERS
// ============================================

resetBtn.addEventListener('click', () => {
    resetFileUpload();
    document.getElementById('year').value = '2021-2022';
    currentTempId = null;
    currentFilename = null;
});

retryBtn.addEventListener('click', () => {
    hideAllSections();
    submitBtn.classList.remove('d-none');
});

// ============================================
// UI STATE FUNCTIONS
// ============================================

function showProgress() {
    hideAllSections();
    submitBtn.classList.add('d-none');
    progressSection.classList.remove('d-none');

    // Update progress text
    const messages = [
        'PDF dosyanız yükleniyor...',
        'Makaleler taranıyor...',
        'Başlıklar çıkarılıyor...',
        'Özetler işleniyor...',
        'Anahtar kelimeler belirleniyor...',
        'CSV dosyası oluşturuluyor...'
    ];

    let index = 0;
    const interval = setInterval(() => {
        progressText.textContent = messages[index];
        index = (index + 1) % messages.length;
    }, 2000);

    // Store interval ID to clear it later
    progressSection.dataset.intervalId = interval;
}

function showSuccess(articleCount, filename) {
    hideAllSections();

    // Clear progress interval
    if (progressSection.dataset.intervalId) {
        clearInterval(parseInt(progressSection.dataset.intervalId));
    }

    resultMessage.innerHTML = `
        <strong>${articleCount}</strong> makale başarıyla işlendi! 
        <br><small class="text-muted mt-1">${filename}</small>
    `;
    resultSection.classList.remove('d-none');

    // Add animation
    resultSection.style.animation = 'slideIn 0.5s ease';
}

function showError(message) {
    hideAllSections();

    // Clear progress interval
    if (progressSection.dataset.intervalId) {
        clearInterval(parseInt(progressSection.dataset.intervalId));
    }

    submitBtn.classList.remove('d-none');
    errorMessage.textContent = message;
    errorSection.classList.remove('d-none');

    // Add animation
    errorSection.style.animation = 'slideIn 0.5s ease';
}

function hideAllSections() {
    progressSection.classList.add('d-none');
    resultSection.classList.add('d-none');
    errorSection.classList.add('d-none');
    analysisSection.classList.add('d-none');
}

function showNotification(message, type = 'info') {
    // Create toast notification
    const toast = document.createElement('div');
    toast.className = `alert alert-${type} position-fixed top-0 start-50 translate-middle-x mt-3`;
    toast.style.zIndex = '9999';
    toast.style.minWidth = '300px';
    toast.innerHTML = `
        <i class="fas fa-${type === 'success' ? 'check-circle' : 'info-circle'} me-2"></i>
        ${message}
    `;

    document.body.appendChild(toast);

    // Auto remove after 3 seconds
    setTimeout(() => {
        toast.style.animation = 'fadeOut 0.5s ease';
        setTimeout(() => {
            document.body.removeChild(toast);
        }, 500);
    }, 3000);
}

// ============================================
// PAGE LOAD
// ============================================

document.addEventListener('DOMContentLoaded', () => {
    console.log('🚀 LIFT UP Dataset Extraction Tool - Ready!');

    // Add fade-out animation keyframe
    const style = document.createElement('style');
    style.textContent = `
        @keyframes fadeOut {
            from { opacity: 1; }
            to { opacity: 0; }
        }
    `;
    document.head.appendChild(style);
});
