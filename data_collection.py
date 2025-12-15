import fitz
import re
import csv
import sys


def clean_text(text):
    """
    Metindeki fazla boşlukları ve satır sonlarını temizler.
    """
    if not text:
        return ""
    # Birden fazla boşluğu tek boşluğa indir
    text = re.sub(r'\s+', ' ', text)
    # Başındaki ve sonundaki boşlukları temizle
    text = text.strip()
    return text


def extract_title(page):
    """Makale başlığını (Türkçe + İngilizce birlikte) font boyutuna göre bulur.

    Mantık:
    - Sayfadaki tüm metni "dict" formatında alır.
    - En büyük font boyutuna sahip, sayfanın üst kısmındaki satırları aday
      başlık olarak seçer.
    - "LIFT UP" / "Bildiri Kitabı" gibi kitap başlığı satırlarını atlar.
    - "Özetçe" / "Abstract" gördüğünde başlık toplamayı bırakır.
    - İlk birkaç (en fazla 5) başlık satırını birleştirip tek bir metin döner.

    Dönen sonuç doğrudan CSV'deki Title_TR kolonuna yazılır (TR \ EN birlikte).
    Title_EN kolonu bu script içinde bilerek boş bırakılır.
    """
    info = page.get_text("dict")
    page_height = float(page.rect.height)

    spans = []
    for block in info.get("blocks", []):
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                text = span.get("text", "").strip()
                if not text:
                    continue
                # Çok kısa gürültü satırları atla
                if len(text) < 3:
                    continue
                bbox = span.get("bbox", [0, 0, 0, 0])
                y_top = float(bbox[1])
                size = float(span.get("size", 0))
                spans.append({
                    "text": text,
                    "y": y_top,
                    "size": size,
                })

    if not spans:
        return ""

    # En büyük font boyutunu bul
    max_size = max(s["size"] for s in spans)
    if max_size <= 0:
        return ""

    # Başlık için: en büyük fonta çok yakın olan (örn. -1pt içinde) satırları al
    size_threshold = max_size - 1.0
    candidate_spans = [
        s for s in spans
        if s["size"] >= size_threshold and s["y"] <= page_height * 0.5
    ]

    # Y pozisyonuna göre sırala (üstten alta), sonra metin sırasına göre
    candidate_spans.sort(key=lambda s: (s["y"], s["text"]))

    raw_lines = []
    for s in candidate_spans:
        text = s["text"]

        # Kitap başlığını atla
        if "LIFT UP" in text or "Bildiri Kitabı" in text:
            continue

        # Özet bölümüne geldiysek başlık biter
        if "Özetçe" in text or "Abstract" in text:
            break

        # Açıkça başlık olmayan bazı satırlar görünürse başlığı sonlandır
        if "@" in text:
            break
        if "Üniversitesi" in text or "Mühendisliği" in text:
            break
        if text in ["Ankara, Türkiye", "İstanbul, Türkiye", "Türkiye", "Turkey"]:
            break
        if "A.Ş." in text:
            break

        raw_lines.append(text)

        # Çok uzamaması için 5 satırla sınırla
        if len(raw_lines) >= 5:
            break

    if not raw_lines:
        return ""

    # TR \ EN ayrımı: sadece karakter yapısına ve sıra bilgisine göre böl
    tr_lines = []
    en_lines = []
    found_english = False

    for line in raw_lines:
        has_turkish = any(c in line for c in "ğüşıöçĞÜŞİÖÇ")

        # Türkçe karakter gördüğümüz sürece bunları TR tarafına ekle
        if has_turkish and not found_english:
            tr_lines.append(line)
            continue

        # Daha önce TR gördük ve şimdi Türkçe karakter içermeyen, yeterince uzun bir satır geliyorsa
        # bunu İngilizce kısmın başlangıcı olarak kabul et
        if not has_turkish and tr_lines:
            found_english = True
            en_lines.append(line)
            continue

        # Hiç TR bulunamadıysa veya kararsız durumdaysak
        if not tr_lines and not found_english:
            # Çok kısa/garip satırları TR'ye eklemek yerine yoksaymıyoruz, çünkü
            # başlıkların genellikle yeterince uzun olduğu varsayımı var.
            tr_lines.append(line)
        else:
            # İngilizce kısmı başladıktan sonra gelen her şeyi EN'e ekle
            en_lines.append(line)

    title_tr = clean_text(" ".join(tr_lines)) if tr_lines else ""
    title_en = clean_text(" ".join(en_lines)) if en_lines else ""

    if title_tr and title_en:
        return f"{title_tr} \ {title_en}"
    if title_tr:
        return title_tr
    if title_en:
        return title_en
    return ""


def extract_abstract_tr(text):
    """
    Türkçe özeti çıkarır. 
    "Özetçe—" ile başlar ve "Anahtar Kelimeler" ile biter.
    """
    # Regex ile Türkçe özeti bul - farklı tire türlerini yakala
    pattern = r'Özetçe[\s—\-–]+\s*(.*?)\s*(?=Anahtar Kelimeler)'
    match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
    
    if match:
        abstract = match.group(1)
        return clean_text(abstract)
    return ""


def extract_abstract_en(text):
    """
    İngilizce özeti çıkarır.
    "Abstract—" ile başlar ve "Keywords" ile biter.
    """
    # Regex ile İngilizce özeti bul - farklı tire türlerini yakala
    pattern = r'Abstract[\s—\-–]+\s*(.*?)\s*(?=Keywords)'
    match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
    
    if match:
        abstract = match.group(1)
        return clean_text(abstract)
    return ""


def is_article_start_page(text):
    """
    Bu sayfanın yeni bir makale başlangıcı olup olmadığını kontrol eder.
    Özetçe ve Abstract kelimelerinin varlığına bakar.
    """
    return ('Özetçe' in text or 'Özetçe—' in text) and ('Abstract' in text or 'Abstract—' in text)


def extract_year_from_text(text):
    """
    PDF içinden yıl bilgisini çıkarır.
    Genellikle "2020-2021" formatındadır.
    """
    # Yıl bilgisi genellikle PDF'in başında veya her sayfada bulunur
    year_match = re.search(r'(20\d{2})\s*-\s*(20\d{2})', text)
    if year_match:
        return f"{year_match.group(1)}-{year_match.group(2)}"
    return "2020-2021"  # Varsayılan değer


def process_pdf(pdf_path, year, output_csv=None):
    """
    PDF dosyasını işler ve makale bilgilerini CSV'ye yazar.
    
    Args:
        pdf_path: PDF dosyasının yolu
        output_csv: Çıktı CSV dosyasının adı
    """
    print(f"PDF açılıyor: {pdf_path}")
    doc = fitz.open(pdf_path)
    print(f"Toplam sayfa sayısı: {len(doc)}")

    articles = []
    
    # Her sayfayı tara
    for page_num in range(len(doc)):
        page = doc[page_num]
        text = page.get_text()
        
        # Bu sayfa yeni bir makale mi?
        if is_article_start_page(text):
            print(f"\n{'='*80}")
            print(f"Sayfa {page_num + 1}: Yeni makale tespit edildi")
            print(f"{'='*80}")
            
            # Makale bilgilerini çıkar
            title = extract_title(page)
            abstract_tr = extract_abstract_tr(text)
            abstract_en = extract_abstract_en(text)

            print(f"Başlık (TR+EN): {title[:100]}...")
            print(f"Türkçe Özet: {abstract_tr[:100]}...")
            print(f"İngilizce Özet: {abstract_en[:100]}...")
            
            # Makale bilgilerini kaydet
            article = {
                'PageNumber': page_num + 1,  # 1-indexed
                'Year': year,
                # Title_TR içinde TR ve EN birlikte tutulur
                'Title_TR': title,
                # Title_EN istenen senaryoda bilerek boş bırakılır
                'Title_EN': "",
                'Abstract_TR': abstract_tr,
                'Abstract_EN': abstract_en
            }
            articles.append(article)
    
    print(f"\n{'='*80}")
    print(f"Toplam {len(articles)} makale bulundu")
    print(f"{'='*80}")

    # Çıktı CSV ismi: pdf_path ile aynı isim, sadece uzantısı .csv olacak şekilde
    if output_csv is None:
        base = pdf_path.rsplit('.', 1)[0]
        output_csv = f"{base}.csv"

    # CSV'ye yaz
    if articles:
        with open(output_csv, 'w', newline='', encoding='utf-8-sig') as csvfile:
            fieldnames = ['PageNumber', 'Year', 'Title_TR', 'Title_EN', 'Abstract_TR', 'Abstract_EN']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            
            writer.writeheader()
            for article in articles:
                writer.writerow(article)
        
        print(f"\n✓ Veriler '{output_csv}' dosyasına kaydedildi")
    else:
        print("\n✗ Hiç makale bulunamadı!")
    
    doc.close()


if __name__ == "__main__":
    # PDF dosya yolu
    year = "2021-2022"
    pdf_path = f"{year}/105_202.pdf"
    
    try:
        process_pdf(pdf_path, year)
    except FileNotFoundError:
        print(f"HATA: '{pdf_path}' dosyası bulunamadı!")
        print("Lütfen PDF dosyasının script ile aynı dizinde olduğundan emin olun.")
        sys.exit(1)
    except Exception as e:
        print(f"HATA oluştu: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)