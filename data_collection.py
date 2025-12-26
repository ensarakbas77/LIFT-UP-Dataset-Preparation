import fitz
import re
import csv
import sys
import os
import glob

# ====================================================================
# CONFIGURATION - Buradan PDF yolunu ve ayarları değiştirebilirsiniz
# ====================================================================

# Yıl bilgisi (CSV'ye yazılacak)
YEAR = "2021-2022"

# PDF dosyası, klasörü veya glob pattern
PDF_PATH = f"Bildiri-Kitabi-{YEAR}.pdf"

# Çıktı klasörü (None ise PDF ile aynı yerde oluşturulur)
OUTPUT_DIR = None


# ====================================================================
# TEXT UTILITIES - Metin işleme yardımcı fonksiyonları
# ====================================================================

TR_CHARS = set("ğüşıöçĞÜŞİÖÇ")


def clean_text(text: str) -> str:
    """
    Metindeki fazla boşlukları temizler ve strip yapar.
    
    Args:
        text: Temizlenecek metin
        
    Returns:
        Temizlenmiş metin
    """
    if not text:
        return ""
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def contains_tr_char(s: str) -> bool:
    """
    Metinde Türkçe karakter olup olmadığını kontrol eder.
    
    Args:
        s: Kontrol edilecek metin
        
    Returns:
        True/False
    """
    return any(c in TR_CHARS for c in s)


def looks_english_line(s: str) -> bool:
    """
    Satırın İngilizce başlık satırı olup olmadığını heuristik yöntemle kontrol eder.
    TR karakteri içermeyen ve yaygın İngilizce teknik terimleri içeren satırları yakalar.
    
    Args:
        s: Kontrol edilecek satır
        
    Returns:
        True ise muhtemelen İngilizce satır
    """
    if not s:
        return False
    if contains_tr_char(s):
        return False
    
    low = s.lower()
    english_hints = [
        "production", "testing", "used in", "using", "technology",
        "system", "systems", "analysis", "design", "optimization",
        "manufacturing", "additive"
    ]
    return any(hint in low for hint in english_hints)


# ====================================================================
# CONTENT DETECTION - İçerik tespiti fonksiyonları
# ====================================================================

def is_article_start_page(text: str) -> bool:
    """
    Sayfanın yeni bir makale başlangıcı olup olmadığını kontrol eder.
    Hem "Özetçe" hem "Abstract" kelimelerini içeriyorsa makale başlangıcıdır.
    
    Args:
        text: Sayfa metni
        
    Returns:
        True ise yeni makale başlangıcı
    """
    return ("Özetçe" in text) and ("Abstract" in text)


def collect_until_markers(doc, start_idx: int, stop_markers: list, hard_limit: int = 8) -> str:
    """
    Belirli bir sayfadan başlayarak, durma işaretçilerine kadar olan metni toplar.
    Özet çıkarımında kullanılır (bir özet birkaç sayfaya yayılabilir).
    
    Args:
        doc: PDF dökümanı
        start_idx: Başlangıç sayfa indeksi
        stop_markers: Durma işaretçileri listesi (örn: ["Keywords", "Anahtar Kelimeler"])
        hard_limit: Maksimum kaç sayfa toplanacak (varsayılan: 8)
        
    Returns:
        Birleştirilmiş metin
    """
    parts = []
    for i in range(start_idx, min(len(doc), start_idx + hard_limit)):
        page_text = doc[i].get_text()
        
        # Yeni makale başladıysa dur
        if i > start_idx and is_article_start_page(page_text):
            break
            
        parts.append(page_text)
        
        # Durma işaretçilerini kontrol et
        low = page_text.lower()
        if any(marker.lower() in low for marker in stop_markers):
            break
            
    return "\n".join(parts)


# ====================================================================
# ABSTRACT EXTRACTION - Özet çıkarma fonksiyonları
# ====================================================================

def extract_abstract_tr(text: str) -> str:
    """
    Türkçe özeti "Özetçe—" ile "Anahtar Kelimeler" arasından çıkarır.
    
    Args:
        text: İşlenecek metin
        
    Returns:
        Türkçe özet
    """
    pattern = r"Özetçe\s*[—\-–]+\s*(.*?)\s*(?=Anahtar\s*Kelimeler)"
    match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
    return clean_text(match.group(1)) if match else ""


def extract_abstract_en(text: str) -> str:
    """
    İngilizce özeti "Abstract—" ile "Keywords" arasından çıkarır.
    
    Args:
        text: İşlenecek metin
        
    Returns:
        İngilizce özet
    """
    pattern = r"Abstract\s*[—\-–]+\s*(.*?)\s*(?=Keywords)"
    match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
    return clean_text(match.group(1)) if match else ""


def extract_keywords_tr(text: str) -> str:
    """
    Türkçe anahtar kelimeleri "Anahtar Kelimeler—" ile "Abstract" arasından çıkarır.
    
    Anahtar kelimeler genellikle Türkçe özetin hemen ardından gelir ve virgülle ayrılmış
    kelime/kelime grupları şeklindedir.
    
    Args:
        text: İşlenecek metin
        
    Returns:
        Türkçe anahtar kelimeler (virgülle ayrılmış)
    """
    # "Anahtar Kelimeler" ile "Abstract" arasındaki metni yakala
    # Farklı tire karakterlerini (—, -, –, :, ;) destekle
    # Noktalı virgül (;) bazı makalelerde kullanılıyor
    pattern = r"Anahtar\s*Kelimeler\s*[—:\-–;]+\s*(.*?)\s*(?=Abstract)"
    match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
    return clean_text(match.group(1)) if match else ""


def extract_keywords_en(text: str) -> str:
    """
    İngilizce anahtar kelimeleri "Keywords—" ile "Giriş" veya "Problem Tanımı" bölümü arasından çıkarır.
    
    Anahtar kelimeler genellikle İngilizce özetin hemen ardından gelir ve virgülle ayrılmış
    kelime/kelime grupları şeklindedir. Giriş bölümü farklı formatlarda olabilir:
    - "I." veya "I " (Roma rakamı) - yeni satırda veya aynı satırda olabilir
    - "GİRİŞ" (Türkçe)
    - "INTRODUCTION" (İngilizce)
    - "PROBLEM" veya "PROBLEMİN TANIMI" gibi varyasyonlar
    - Bazen hiçbir başlık olmayabilir, bu durumda ilk satırı al
    
    Args:
        text: İşlenecek metin
        
    Returns:
        İngilizce anahtar kelimeler (virgülle ayrılmış)
    """
    # "Keywords" ile giriş bölümü arasındaki metni yakala
    # Farklı tire karakterlerini (—, -, –, :, ;) destekle
    # Noktalı virgül (;) bazı makalelerde kullanılıyor
    # Giriş bölümü için birden fazla pattern kontrol et:
    # - \n\s*I\. : yeni satırda "I." (eski pattern)
    # - I\.\s : "I." sonrası boşluk (I. GİRİŞ, I. PROBLEM gibi aynı satırda)
    # - PROBLEM : "PROBLEM TANIMI", "PROBLEMİN TANIMI" vb. için genel pattern
    pattern = r"Keywords\s*[—:\-–;]+\s*(.*?)(?=\n\s*I\.|I\.\s|GİRİŞ|INTRODUCTION|PROBLEM|\n\s*\n\s*[A-Z][a-z]+)"
    match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
    
    if match:
        result = clean_text(match.group(1))
        # Eğer sonuç çok uzunsa (>200 karakter), muhtemelen yanlış yakalanmıştır, sadece ilk cümleyi al
        if len(result) > 200:
            # Nokta veya çift newline'da kes
            parts = result.split('.')
            if parts:
                result = clean_text(parts[0] + '.')
        return result
    
    # Eğer yukarıdaki pattern başarısız olursa, daha basit bir yöntem dene
    # Keywords'den sonra ilk satırı al (çift newline'a kadar)
    simple_pattern = r"Keywords\s*[—:\-–;]+\s*([^\n]+)"
    simple_match = re.search(simple_pattern, text, re.IGNORECASE)
    if simple_match:
        return clean_text(simple_match.group(1))
    
    return ""


# ====================================================================
# TITLE EXTRACTION - Başlık çıkarma fonksiyonları
# ====================================================================

def _filter_noise_spans(spans: list, page_height: float) -> list:
    """
    Başlık aday span'lerinden gürültüyü filtreler (header, footer, vb).
    
    Args:
        spans: Span listesi
        page_height: Sayfa yüksekliği
        
    Returns:
        Filtrelenmiş span listesi
    """
    filtered = []
    for s in spans:
        text = s["text"]
        
        # Çok kısa veya boş metinleri atla
        if len(text) < 2:
            continue
            
        # Kitap başlığı/header bilgilerini atla
        if "LIFT UP" in text or "Bildiri Kitabı" in text:
            continue
            
        # Email adresleri atla
        if "@" in text:
            continue
            
        filtered.append(s)
    
    return filtered


def _group_spans_into_lines(spans: list, y_tolerance: float = 3.0) -> list:
    """
    Span'leri Y pozisyonuna göre satırlara gruplar.
    
    Args:
        spans: Span listesi (Y'ye göre sıralanmış olmalı)
        y_tolerance: Aynı satırdaki span'ler için Y toleransı
        
    Returns:
        Satır listesi [{"y": avg_y, "text": line_text}, ...]
    """
    lines = []
    current_line = []
    current_y = None
    
    def flush_line():
        """Mevcut satırı lines listesine ekle"""
        if not current_line:
            return
        current_line.sort(key=lambda d: d["x"])
        line_text = clean_text(" ".join(d["text"] for d in current_line))
        if line_text:
            avg_y = sum(d["y"] for d in current_line) / len(current_line)
            lines.append({"y": avg_y, "text": line_text})
    
    for span in spans:
        if current_y is None:
            current_y = span["y"]
            current_line = [span]
            continue
        
        # Aynı satırda mı?
        if abs(span["y"] - current_y) <= y_tolerance:
            current_line.append(span)
        else:
            # Yeni satır başladı
            flush_line()
            current_y = span["y"]
            current_line = [span]
    
    # Son satırı ekle
    flush_line()
    
    return lines


def _filter_non_title_lines(lines: list) -> list:
    """
    Başlık olmayan satırları filtreler (yazar bilgileri, kurumlar, vb).
    
    Args:
        lines: Satır listesi
        
    Returns:
        Filtrelenmiş satır listesi
    """
    filtered = []
    
    for line in lines:
        text = line["text"]
        
        # Özet bölümüne geldiysek dur
        if "Özetçe" in text or "Abstract" in text:
            break
        
        # Yazar/kurum bilgileri
        if text.startswith("Öğrenci") or text.startswith("Akademik Danışman") or text.startswith("Sanayi Danışmanı"):
            break
        
        # Email, şehir, şirket bilgileri
        if "@" in text:
            break
        if text in ["Ankara, Türkiye", "İstanbul, Türkiye", "Türkiye", "Turkey"]:
            break
        if "A.Ş." in text:
            break
        
        # Çok kısa satırları atla
        if len(text) < 3:
            continue
        
        filtered.append(line)
        
        # Başlık çok uzun olmasın (maksimum 12 satır)
        if len(filtered) >= 12:
            break
    
    return filtered


def _split_tr_en_by_gap(texts: list, ys: list, gap_threshold: float = 8.0) -> tuple[str, str]:
    """
    Satırlar arasındaki gap'e (boşluk) bakarak TR ve EN başlıkları ayırır.
    
    Args:
        texts: Satır metinleri listesi
        ys: Satırların Y pozisyonları
        gap_threshold: Minimum gap boyutu
        
    Returns:
        (title_tr, title_en) tuple
    """
    if len(ys) < 2:
        return "", ""
    
    # Ardışık satırlar arasındaki gap'leri hesapla
    gaps = [ys[i + 1] - ys[i] for i in range(len(ys) - 1)]
    max_gap = max(gaps)
    max_gap_idx = gaps.index(max_gap)
    
    # Yeterince büyük gap yoksa None döndür
    if max_gap < gap_threshold:
        return "", ""
    
    # Gap'e göre böl
    split_idx = max_gap_idx + 1
    top_texts = texts[:split_idx]
    bottom_texts = texts[split_idx:]
    
    # Hangi grup daha çok İngilizce ipucu içeriyor?
    top_en_score = sum(1 for t in top_texts if looks_english_line(t))
    bottom_en_score = sum(1 for t in bottom_texts if looks_english_line(t))
    
    if bottom_en_score >= top_en_score:
        return clean_text(" ".join(top_texts)), clean_text(" ".join(bottom_texts))
    else:
        return clean_text(" ".join(bottom_texts)), clean_text(" ".join(top_texts))


def _split_tr_en_by_english_hint(texts: list) -> tuple[str, str]:
    """
    İngilizce ipuçlarına bakarak TR ve EN başlıkları ayırır.
    
    Args:
        texts: Satır metinleri listesi
        
    Returns:
        (title_tr, title_en) tuple
    """
    first_en_idx = None
    for i, text in enumerate(texts):
        if looks_english_line(text):
            first_en_idx = i
            break
    
    if first_en_idx is not None and first_en_idx > 0:
        title_tr = clean_text(" ".join(texts[:first_en_idx]))
        title_en = clean_text(" ".join(texts[first_en_idx:]))
        return title_tr, title_en
    
    return "", ""


def _split_tr_en_by_char(texts: list) -> tuple[str, str]:
    """
    Türkçe karakter varlığına bakarak TR ve EN başlıkları ayırır (fallback method).
    
    Args:
        texts: Satır metinleri listesi
        
    Returns:
        (title_tr, title_en) tuple
    """
    tr_lines = []
    en_lines = []
    found_en = False
    
    for text in texts:
        # Türkçe karakter var ve henüz EN başlamadıysa -> TR
        if contains_tr_char(text) and not found_en:
            tr_lines.append(text)
            continue
        
        # TR bittikten sonra Türkçe karakter yok -> EN başladı
        if not contains_tr_char(text) and tr_lines:
            found_en = True
            en_lines.append(text)
            continue
        
        # Belirsiz durumlar
        if not tr_lines and not found_en:
            tr_lines.append(text)
        else:
            en_lines.append(text)
    
    return clean_text(" ".join(tr_lines)), clean_text(" ".join(en_lines))


def extract_title_tr_en(page) -> tuple[str, str]:
    """
    Sayfadan makale başlığını Türkçe ve İngilizce olarak ayrı çıkarır.
    
    Üç aşamalı ayırma stratejisi:
    1. Gap-based: Satırlar arası ≥8pt boşluk varsa bunu TR/EN sınırı kabul et
    2. English hint: İngilizce kelime ipuçlarına göre ayır
    3. Character-based: Türkçe karakter varlığına göre ayır (fallback)
    
    Font boyutu toleransı: max_size - 4pt (başlığın ilk satırları bazen daha küçük olabiliyor)
    
    Args:
        page: PyMuPDF page objesi
        
    Returns:
        (title_tr, title_en) tuple
    """
    info = page.get_text("dict")
    page_h = float(page.rect.height)

    # 1. Tüm span'leri topla
    spans = []
    for block in info.get("blocks", []):
        for line in block.get("lines", []):
            for sp in line.get("spans", []):
                txt = (sp.get("text") or "").strip()
                if not txt or len(txt) < 2:
                    continue
                x0, y0, x1, y1 = sp.get("bbox", [0, 0, 0, 0])
                spans.append({
                    "text": txt,
                    "x": float(x0),
                    "y": float(y0),
                    "size": float(sp.get("size", 0.0)),
                })

    if not spans:
        return "", ""

    # 2. Özetçe/Abstract'ın Y pozisyonunu bul (başlık alanının alt sınırı)
    y_abstract = None
    for s in spans:
        if "Özetçe" in s["text"] or "Abstract" in s["text"]:
            if y_abstract is None or s["y"] < y_abstract:
                y_abstract = s["y"]
    if y_abstract is None:
        y_abstract = page_h * 0.60

    # 3. Başlık bölgesini belirle (sayfanın üstünden özete kadar)
    y_max = y_abstract - 2
    region = [s for s in spans if s["y"] <= y_max]
    if not region:
        return "", ""

    # 4. En büyük fontu bul ve tolerans bandı seç
    max_size = max(s["size"] for s in region)
    if max_size <= 0:
        return "", ""
    
    # Font toleransı: max_size - 4pt (başlığın ilk satırları bazen daha küçük)
    band = [s for s in region if s["size"] >= max_size - 4.0]
    if not band:
        return "", ""

    # 5. Span'leri Y pozisyonuna göre sırala
    band.sort(key=lambda d: (d["y"], d["x"]))
    
    # 6. Gürültüyü filtrele
    band = _filter_noise_spans(band, page_h)
    if not band:
        return "", ""

    # 7. Span'leri satırlara grupla
    lines = _group_spans_into_lines(band, y_tolerance=3.0)
    if not lines:
        return "", ""

    # 8. Başlık olmayan satırları filtrele
    lines = _filter_non_title_lines(lines)
    if not lines:
        return "", ""

    # 9. Y pozisyonuna göre sırala
    lines.sort(key=lambda d: d["y"])
    texts = [line["text"] for line in lines]
    ys = [line["y"] for line in lines]

    # 10. Üç aşamalı ayırma stratejisi
    
    # Strateji 1: Gap ile ayır
    title_tr, title_en = _split_tr_en_by_gap(texts, ys, gap_threshold=8.0)
    if title_tr and title_en:
        return title_tr, title_en

    # Strateji 2: İngilizce ipuçlarına göre ayır
    title_tr, title_en = _split_tr_en_by_english_hint(texts)
    if title_tr and title_en:
        return title_tr, title_en

    # Strateji 3: Türkçe karakter varlığına göre ayır (fallback)
    return _split_tr_en_by_char(texts)


# ====================================================================
# PDF PROCESSING - Ana işleme fonksiyonları
# ====================================================================

def extract_abstracts_with_fallback(doc, page_idx: int) -> tuple[str, str]:
    """
    Özet çıkarımını birden fazla stratejiyle dener (bazı özetler birkaç sayfaya yayılabilir).
    
    Args:
        doc: PDF dökümanı
        page_idx: Makale başlangıç sayfası indeksi
        
    Returns:
        (abstract_tr, abstract_en) tuple
    """
    # İlk deneme: Normal marker'larla
    merged_tr = collect_until_markers(doc, page_idx, ["Anahtar Kelimeler"], hard_limit=8)
    merged_en = collect_until_markers(doc, page_idx, ["Keywords"], hard_limit=8)
    abs_tr = extract_abstract_tr(merged_tr)
    abs_en = extract_abstract_en(merged_en)

    # Türkçe özet bulunamadıysa alternatif deneme
    if not abs_tr:
        merged_tr2 = collect_until_markers(doc, page_idx, ["Abstract", "Keywords"], hard_limit=8)
        match = re.search(
            r"Özetçe\s*[—\-–]+\s*(.*?)\s*(?=Abstract|Keywords)",
            merged_tr2,
            re.DOTALL | re.IGNORECASE
        )
        abs_tr = clean_text(match.group(1)) if match else ""

    # İngilizce özet bulunamadıysa alternatif deneme
    if not abs_en:
        merged_en2 = collect_until_markers(doc, page_idx, ["I.", "I ", "GİRİŞ"], hard_limit=8)
        match = re.search(
            r"Abstract\s*[—\-–]+\s*(.*?)\s*(?=Keywords|I\.\s|I\s|GİRİŞ)",
            merged_en2,
            re.DOTALL | re.IGNORECASE
        )
        abs_en = clean_text(match.group(1)) if match else ""

    return abs_tr, abs_en


def process_pdf(pdf_path: str, year: str, output_csv: str | None = None):
    """
    Tek bir PDF dosyasından tüm makaleleri çıkarır ve CSV'ye yazar.
    
    Args:
        pdf_path: PDF dosya yolu
        year: Yıl bilgisi (CSV'ye yazılacak)
        output_csv: Çıktı CSV dosya yolu (None ise otomatik oluşturulur)
    """
    print(f"📄 PDF açılıyor: {pdf_path}")
    doc = fitz.open(pdf_path)
    print(f"📊 Toplam sayfa sayısı: {len(doc)}")

    rows = []

    # Her sayfayı tara
    for page_idx in range(len(doc)):
        page = doc[page_idx]
        text = page.get_text()

        # Bu sayfa yeni makale başlangıcı mı?
        if not is_article_start_page(text):
            continue

        # Başlıkları çıkar (TR ve EN ayrı)
        title_tr, title_en = extract_title_tr_en(page)

        # Özetleri çıkar (fallback stratejileriyle)
        abs_tr, abs_en = extract_abstracts_with_fallback(doc, page_idx)

        # Anahtar kelimeleri çıkar (TR ve EN ayrı)
        # Anahtar kelimeler için sayfa metnini topla (birkaç sayfaya yayılabilir)
        keywords_text = collect_until_markers(doc, page_idx, ["I.", "GİRİŞ", "INTRODUCTION"], hard_limit=3)
        keywords_tr = extract_keywords_tr(keywords_text)
        keywords_en = extract_keywords_en(keywords_text)

        # Makale bilgilerini kaydet
        rows.append({
            "PageNumber": page_idx + 1,
            "Year": year,
            "Title_TR": title_tr,
            "Title_EN": title_en,
            "Abstract_TR": abs_tr,
            "Abstract_EN": abs_en,
            "Keywords_TR": keywords_tr,
            "Keywords_EN": keywords_en,
        })

        # İlerleme göster
        print(f"✅ Sayfa {page_idx+1}: TR='{title_tr[:60]}...' | EN='{title_en[:60]}...'")

    doc.close()

    # CSV dosya adını belirle
    if output_csv is None:
        base = os.path.splitext(pdf_path)[0]
        output_csv = base + ".csv"

    # CSV'ye yaz
    with open(output_csv, "w", newline="", encoding="utf-8-sig") as f:
        fieldnames = ["PageNumber", "Year", "Title_TR", "Title_EN", "Abstract_TR", "Abstract_EN", "Keywords_TR", "Keywords_EN"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)

    print(f"\n✨ {len(rows)} makale bulundu. CSV yazıldı: {output_csv}")


def process_path(input_path: str, year: str, out_dir: str | None = None):
    """
    PDF dosyası, klasör veya glob pattern'i işler.
    
    Args:
        input_path: PDF dosyası, klasör yolu veya glob pattern (örn: "2021-2022/*.pdf")
        year: Yıl bilgisi
        out_dir: Çıktı dizini (None ise PDF ile aynı yerde oluşturulur)
        
    Raises:
        FileNotFoundError: PDF bulunamazsa
    """
    pdfs = []
    
    # Klasör mü, dosya mı, glob pattern mi?
    if os.path.isdir(input_path):
        pdfs = sorted(glob.glob(os.path.join(input_path, "*.pdf")))
    else:
        matches = glob.glob(input_path)
        if matches:
            pdfs = sorted([p for p in matches if p.lower().endswith(".pdf")])
        elif input_path.lower().endswith(".pdf"):
            pdfs = [input_path]

    if not pdfs:
        raise FileNotFoundError(f"❌ PDF bulunamadı: {input_path}")

    print(f"\n🔍 {len(pdfs)} PDF dosyası bulundu\n")

    # Çıktı dizinini oluştur
    if out_dir is not None:
        os.makedirs(out_dir, exist_ok=True)

    # Her PDF'i işle
    for idx, pdf in enumerate(pdfs, 1):
        print(f"\n{'='*80}")
        print(f"[{idx}/{len(pdfs)}] İşleniyor...")
        print(f"{'='*80}")
        
        if out_dir:
            out_csv = os.path.join(out_dir, os.path.splitext(os.path.basename(pdf))[0] + ".csv")
        else:
            out_csv = None
        
        process_pdf(pdf, year, out_csv)


# ====================================================================
# MAIN EXECUTION
# ====================================================================

if __name__ == "__main__":
    print("="*80)
    print("LIFT UP Dataset Extraction Tool")
    print("="*80)
    print(f"PDF Path: {PDF_PATH}")
    print(f"Year: {YEAR}")
    print(f"Output Dir: {OUTPUT_DIR}")
    print("="*80 + "\n")
    
    try:
        process_path(PDF_PATH, YEAR, OUTPUT_DIR)
        print("\n🎉 İşlem başarıyla tamamlandı!")
    except Exception as e:
        print(f"\n❌ HATA: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
