from flask import Flask, render_template, request, send_file, jsonify
from werkzeug.utils import secure_filename
import os
import tempfile
import uuid
from pathlib import Path
import sys

# data_extract ve analysis modüllerini import et
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from data_extract import PDFProcessor
from analysis import analyze_csv

# Flask uygulaması
app = Flask(__name__)

# Konfigürasyon
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB max file size
app.config['UPLOAD_FOLDER'] = tempfile.gettempdir()
app.config['SECRET_KEY'] = 'lift-up-dataset-extraction-2026'

# İzin verilen dosya uzantıları
ALLOWED_EXTENSIONS = {'pdf'}


def allowed_file(filename):
    """Dosya uzantısının geçerli olup olmadığını kontrol eder"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route('/')
def index():
    """Ana sayfa"""
    return render_template('index.html')


@app.route('/process', methods=['POST'])
def process_pdf():
    """
    PDF dosyasını işler ve CSV çıktısı oluşturur
    
    Returns:
        JSON response with success status and file info or error message
    """
    try:
        # Dosya kontrolü
        if 'pdfFile' not in request.files:
            return jsonify({'success': False, 'error': 'PDF dosyası bulunamadı'}), 400
        
        file = request.files['pdfFile']
        year = request.form.get('year', '2021-2022')
        
        if file.filename == '':
            return jsonify({'success': False, 'error': 'Dosya seçilmedi'}), 400
        
        if not allowed_file(file.filename):
            return jsonify({'success': False, 'error': 'Sadece PDF dosyaları kabul edilir'}), 400
        
        # Güvenli dosya adı oluştur
        filename = secure_filename(file.filename)
        unique_id = str(uuid.uuid4())[:8]
        
        # Geçici dizin oluştur
        temp_dir = os.path.join(app.config['UPLOAD_FOLDER'], f'lift_up_{unique_id}')
        os.makedirs(temp_dir, exist_ok=True)
        
        # PDF'i kaydet
        pdf_path = os.path.join(temp_dir, filename)
        file.save(pdf_path)
        
        # CSV çıktı yolu
        csv_filename = f"{Path(filename).stem}_extracted.csv"
        csv_path = os.path.join(temp_dir, csv_filename)
        
        # PDF'i işle
        processor = PDFProcessor()
        articles = processor.process_pdf(pdf_path, year, csv_path)
        
        # Sonuç bilgisi
        result = {
            'success': True,
            'article_count': len(articles),
            'csv_path': csv_path,
            'csv_filename': csv_filename,
            'temp_id': unique_id
        }
        
        return jsonify(result), 200
        
    except Exception as e:
        import traceback
        error_msg = str(e)
        traceback.print_exc()
        return jsonify({
            'success': False, 
            'error': f'İşleme hatası: {error_msg}'
        }), 500


@app.route('/download/<temp_id>/<filename>')
def download_csv(temp_id, filename):
    """
    Oluşturulan CSV dosyasını indirir
    
    Args:
        temp_id: Geçici dizin ID'si
        filename: CSV dosya adı
    """
    try:
        # Güvenli dosya yolu oluştur
        safe_filename = secure_filename(filename)
        temp_dir = os.path.join(app.config['UPLOAD_FOLDER'], f'lift_up_{temp_id}')
        csv_path = os.path.join(temp_dir, safe_filename)
        
        # Dosya var mı kontrol et
        if not os.path.exists(csv_path):
            return jsonify({'error': 'Dosya bulunamadı'}), 404
        
        # Dosyayı gönder
        return send_file(
            csv_path,
            mimetype='text/csv',
            as_attachment=True,
            download_name=safe_filename
        )
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/analyze/<temp_id>/<filename>')
def analyze(temp_id, filename):
    """
    CSV dosyasını analiz eder ve sonuçları döndürür
    
    Args:
        temp_id: Geçici dizin ID'si
        filename: CSV dosya adı
        
    Returns:
        JSON analiz sonuçları
    """
    try:
        # Güvenli dosya yolu oluştur
        safe_filename = secure_filename(filename)
        temp_dir = os.path.join(app.config['UPLOAD_FOLDER'], f'lift_up_{temp_id}')
        csv_path = os.path.join(temp_dir, safe_filename)
        
        # Dosya var mı kontrol et
        if not os.path.exists(csv_path):
            return jsonify({'error': 'Dosya bulunamadı'}), 404
        
        # Analiz yap
        analysis_result = analyze_csv(csv_path)
        
        return jsonify({
            'success': True,
            'analysis': analysis_result
        }), 200
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': f'Analiz hatası: {str(e)}'
        }), 500


@app.route('/cleanup/<temp_id>', methods=['POST'])
def cleanup(temp_id):
    """
    Geçici dosyaları temizler
    
    Args:
        temp_id: Geçici dizin ID'si
    """
    try:
        temp_dir = os.path.join(app.config['UPLOAD_FOLDER'], f'lift_up_{temp_id}')
        
        if os.path.exists(temp_dir):
            import shutil
            shutil.rmtree(temp_dir)
            
        return jsonify({'success': True, 'message': 'Dosyalar temizlendi'}), 200
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.errorhandler(413)
def request_entity_too_large(error):
    """Dosya boyutu çok büyük hatası"""
    return jsonify({
        'success': False, 
        'error': 'Dosya boyutu çok büyük (maksimum 50MB)'
    }), 413


if __name__ == '__main__':
    print("="*80)
    print("🚀 LIFT UP Dataset Extraction Web Interface")
    print("="*80)
    print("📍 Uygulama başlatılıyor: http://localhost:5000")
    print("="*80)
    app.run(debug=True, host='0.0.0.0', port=5000)
