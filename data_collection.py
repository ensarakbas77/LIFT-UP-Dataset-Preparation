import fitz  # PyMuPDF
import csv
import re

def fix_encoding(text):
    """Türkçe karakter kodlama sorunlarını düzelt"""
    # Yaygın bozuk kodlamalar
    replacements = {
        'Õ': 'ı', 'ø': 'İ', 'ú': 'ş', 'o': 'ç', 'ü': 'ü',
        'ö': 'ö', 'û': 'ğ', 'þ': 'ş', 'ý': 'ı', 'ð': 'ğ',
        'Ý': 'İ', 'Þ': 'Ş', 'Ð': 'Ğ', 'Ü': 'Ü', 'Ö': 'Ö',
        '$': 'A', 'ÿ': 'ü', '÷': 'ö', 'ñ': 'ğ', 'õ': 'ı',
    }
    
    for old, new in replacements.items():
        text = text.replace(old, new)
    
    return text

def extract_title_and_abstract(pdf_path, start_page=15, num_articles=10):
    """
    PDF'den başlık ve özet bilgilerini çıkarır.
    
    Args:
        pdf_path: PDF dosyasının yolu
        start_page: Makalelerin başladığı sayfa (0-indexed, 16. sayfa = 15)
        num_articles: Çıkarılacak makale sayısı
    """
    articles = []
    
    # PDF'i aç
    pdf = fitz.open(pdf_path)
    page_num = start_page
    article_count = 0
    
    try:
        while article_count < num_articles and page_num < len(pdf):
            try:
                page = pdf[page_num]
                text = page.get_text("text")  # PyMuPDF ile metin çıkar
                
                # Kodlama sorunlarını düzelt
                text = fix_encoding(text)
                
                if text and len(text) > 100:  # Çok kısa sayfaları atla
                    lines = [line.strip() for line in text.split('\n') if line.strip()]
                    
                    title = None
                    abstract = None
                    
                    # Başlık bul - Türkçe ve İngilizce başlıklar için
                    # Başlık genellikle ilk birkaç satırda, en az 15 karakter
                    for i, line in enumerate(lines[:20]):
                        if len(line) > 15 and len(line) < 200:
                            # Atlayacağımız kelimeler
                            skip_patterns = [
                                'LIFT UP', 'Bildiri', 'Kitab', '2020', '2021',
                                '@', 'http', 'www', '.com', '.tr', '.edu',
                                'Üniversitesi', 'University', 'Türkiye', 'Turkey',
                                'Ankara', 'İstanbul', 'Mühendisliği', 'Engineering',
                                'Design for', 'Magnetic Resonance'
                            ]
                            
                            # Bu satırda atlayacağımız kelime var mı?
                            should_skip = any(skip in line for skip in skip_patterns)
                            
                            # Sayı veya tek karakter değil ve atlama listesinde değilse
                            if not should_skip and not line.isdigit() and i > 0:
                                title = line
                                break
                    
                    # Özet bul - "Özetçe" veya benzeri kelimelerden sonra
                    text_lower = text.lower()
                    
                    # Özetçe başlangıcını bul
                    ozet_patterns = ['özetçe', 'özet:', 'abstract:']
                    ozet_pos = -1
                    
                    for pattern in ozet_patterns:
                        pos = text_lower.find(pattern)
                        if pos != -1:
                            ozet_pos = pos
                            break
                    
                    # Anahtar kelimeler pozisyonunu bul
                    anahtar_patterns = ['anahtar kelime', 'keywords', 'anahtar sözcük']
                    anahtar_pos = -1
                    
                    for pattern in anahtar_patterns:
                        pos = text_lower.find(pattern, ozet_pos if ozet_pos != -1 else 0)
                        if pos != -1:
                            anahtar_pos = pos
                            break
                    
                    # Özeti çıkar
                    if ozet_pos != -1 and anahtar_pos != -1 and anahtar_pos > ozet_pos:
                        # Özetçe kelimesinden sonra başla
                        ozet_start = ozet_pos + 10  # "Özetçe" kelimesini atla
                        abstract_raw = text[ozet_start:anahtar_pos]
                        
                        # Temizleme
                        abstract = ' '.join(abstract_raw.split())
                        abstract = abstract.strip()
                    
                    # Başlık ve özet varsa kaydet
                    if title and abstract and len(abstract) > 80:
                        articles.append({
                            'sayfa': page_num + 1,
                            'baslik': title,
                            'ozet': abstract
                        })
                        article_count += 1
                        print(f"✓ Makale {article_count} bulundu (Sayfa {page_num + 1})")
                        print(f"  Başlık: {title[:70]}...")
                        print(f"  Özet: {abstract[:100]}...")
                        print()
                
            except Exception as e:
                print(f"! Sayfa {page_num + 1} işlenirken hata: {str(e)}")
            
            page_num += 1
            
            # Güvenlik için maksimum 200 sayfa tara
            if page_num > start_page + 200:
                break
    
    finally:
        pdf.close()
    
    return articles

def save_to_csv(articles, output_file='makaleler.csv'):
    """
    Çıkarılan makaleleri CSV dosyasına kaydeder.
    """
    if not articles:
        print("Kaydedilecek makale bulunamadı!")
        return
    
    with open(output_file, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=['sayfa', 'baslik', 'ozet'])
        writer.writeheader()
        writer.writerows(articles)
    
    print(f"\n{len(articles)} makale '{output_file}' dosyasına kaydedildi.")

def main():
    # PDF dosya yolu
    pdf_path = r"Bildiri Kitapları\Bildiri Kitabi 2020-2021.pdf"
    
    print("PDF'den başlık ve özet çıkarılıyor...")
    print(f"Dosya: {pdf_path}")
    print(f"Başlangıç sayfası: 16 (makalelerin başladığı sayfa)")
    print(f"Hedef: İlk 10 makale\n")
    print("="*80)
    print()
    
    # Başlık ve özetleri çıkar
    articles = extract_title_and_abstract(
        pdf_path=pdf_path,
        start_page=15,  # 16. sayfa (0-indexed)
        num_articles=10
    )
    
    # CSV'ye kaydet
    if articles:
        save_to_csv(articles, 'makaleler_ilk_10.csv')
        
        # Özet bilgi yazdır
        print("\n" + "="*80)
        print("ÇIKARILAN MAKALELER:")
        print("="*80)
        for i, article in enumerate(articles, 1):
            print(f"\n{i}. Makale (Sayfa {article['sayfa']}):")
            print(f"   Başlık: {article['baslik']}")
            print(f"   Özet (ilk 100 karakter): {article['ozet'][:100]}...")
    else:
        print("\nHiç makale bulunamadı. Lütfen PDF yapısını kontrol edin.")

if __name__ == "__main__":
    main()
