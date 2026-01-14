import fitz
import re
import csv
import os
import glob
from typing import Optional, Tuple, List, Dict
from dataclasses import dataclass


# ====================================================================
# DATA MODELS
# ====================================================================

@dataclass
class Article:
    """Makale verilerini tutan veri modeli"""
    page_number: int
    year: str
    title_tr: str
    title_en: str
    abstract_tr: str
    abstract_en: str
    keywords_tr: str
    keywords_en: str
    
    def to_dict(self) -> Dict[str, any]:
        """Makale verisini dictionary'ye çevirir (CSV için)"""
        return {
            "PageNumber": self.page_number,
            "Year": self.year,
            "Title_TR": self.title_tr,
            "Title_EN": self.title_en,
            "Abstract_TR": self.abstract_tr,
            "Abstract_EN": self.abstract_en,
            "Keywords_TR": self.keywords_tr,
            "Keywords_EN": self.keywords_en,
        }


# ====================================================================
# TEXT UTILITIES
# ====================================================================

class TextUtils:
    """Metin işleme yardımcı sınıfı"""
    
    TR_CHARS = set("ğüşıöçĞÜŞİÖÇ")
    
    @staticmethod
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
    
    @classmethod
    def contains_tr_char(cls, text: str) -> bool:
        """
        Metinde Türkçe karakter olup olmadığını kontrol eder.
        
        Args:
            text: Kontrol edilecek metin
            
        Returns:
            True/False
        """
        return any(c in cls.TR_CHARS for c in text)
    
    @classmethod
    def looks_english_line(cls, text: str) -> bool:
        """
        Satırın İngilizce başlık satırı olup olmadığını heuristik yöntemle kontrol eder.
        
        Args:
            text: Kontrol edilecek satır
            
        Returns:
            True ise muhtemelen İngilizce satır
        """
        if not text:
            return False
        if cls.contains_tr_char(text):
            return False
        
        low = text.lower()
        english_hints = [
            "production", "testing", "used in", "using", "technology",
            "system", "systems", "analysis", "design", "optimization",
            "manufacturing", "additive"
        ]
        return any(hint in low for hint in english_hints)


# ====================================================================
# PAGE ANALYZER
# ====================================================================

class PageAnalyzer:
    """Sayfa analizi ve içerik tespiti sınıfı"""
    
    @staticmethod
    def is_article_start_page(text: str) -> bool:
        """
        Sayfanın yeni bir makale başlangıcı olup olmadığını kontrol eder.
        
        Args:
            text: Sayfa metni
            
        Returns:
            True ise yeni makale başlangıcı
        """
        return ("Özetçe" in text) and ("Abstract" in text)
    
    @staticmethod
    def collect_until_markers(doc, start_idx: int, stop_markers: List[str], 
                            hard_limit: int = 8) -> str:
        """
        Belirli bir sayfadan başlayarak, durma işaretçilerine kadar olan metni toplar.
        
        Args:
            doc: PDF dökümanı
            start_idx: Başlangıç sayfa indeksi
            stop_markers: Durma işaretçileri listesi
            hard_limit: Maksimum kaç sayfa toplanacak
            
        Returns:
            Birleştirilmiş metin
        """
        parts = []
        analyzer = PageAnalyzer()
        
        for i in range(start_idx, min(len(doc), start_idx + hard_limit)):
            page_text = doc[i].get_text()
            
            # Yeni makale başladıysa dur
            if i > start_idx and analyzer.is_article_start_page(page_text):
                break
                
            parts.append(page_text)
            
            # Durma işaretçilerini kontrol et
            low = page_text.lower()
            if any(marker.lower() in low for marker in stop_markers):
                break
                
        return "\n".join(parts)


# ====================================================================
# ABSTRACT EXTRACTOR
# ====================================================================

class AbstractExtractor:
    """Özet ve anahtar kelime çıkarma sınıfı"""
    
    def __init__(self):
        self.text_utils = TextUtils()
    
    def extract_abstract_tr(self, text: str) -> str:
        """Türkçe özeti çıkarır"""
        pattern = r"Özetçe\s*[—\-–]+\s*(.*?)\s*(?=Anahtar\s*Kelimeler)"
        match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
        return self.text_utils.clean_text(match.group(1)) if match else ""
    
    def extract_abstract_en(self, text: str) -> str:
        """İngilizce özeti çıkarır"""
        pattern = r"Abstract\s*[—\-–]+\s*(.*?)\s*(?=Keywords)"
        match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
        return self.text_utils.clean_text(match.group(1)) if match else ""
    
    def extract_keywords_tr(self, text: str) -> str:
        """Türkçe anahtar kelimeleri çıkarır"""
        pattern = r"Anahtar\s*Kelimeler\s*[—:\-–;]+\s*(.*?)\s*(?=Abstract)"
        match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
        return self.text_utils.clean_text(match.group(1)) if match else ""
    
    def extract_keywords_en(self, text: str) -> str:
        """İngilizce anahtar kelimeleri çıkarır"""
        pattern = r"Keywords\s*[—:\-–;]+\s*(.*?)(?=\n\s*I\.|I\.\s|GİRİŞ|INTRODUCTION|PROBLEM|\n\s*\n\s*[A-Z][a-z]+)"
        match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
        
        if match:
            result = self.text_utils.clean_text(match.group(1))
            # Çok uzunsa ilk cümleyi al
            if len(result) > 200:
                parts = result.split('.')
                if parts:
                    result = self.text_utils.clean_text(parts[0] + '.')
            return result
        
        # Basit pattern dene
        simple_pattern = r"Keywords\s*[—:\-–;]+\s*([^\n]+)"
        simple_match = re.search(simple_pattern, text, re.IGNORECASE)
        if simple_match:
            return self.text_utils.clean_text(simple_match.group(1))
        
        return ""
    
    def extract_with_fallback(self, doc, page_idx: int) -> Tuple[str, str, str, str]:
        """
        Özet ve anahtar kelimeleri fallback stratejileriyle çıkarır.
        
        Returns:
            (abstract_tr, abstract_en, keywords_tr, keywords_en) tuple
        """
        page_analyzer = PageAnalyzer()
        
        # Özetleri çıkar
        merged_tr = page_analyzer.collect_until_markers(
            doc, page_idx, ["Anahtar Kelimeler"], hard_limit=8
        )
        merged_en = page_analyzer.collect_until_markers(
            doc, page_idx, ["Keywords"], hard_limit=8
        )
        abs_tr = self.extract_abstract_tr(merged_tr)
        abs_en = self.extract_abstract_en(merged_en)
        
        # Türkçe özet fallback
        if not abs_tr:
            merged_tr2 = page_analyzer.collect_until_markers(
                doc, page_idx, ["Abstract", "Keywords"], hard_limit=8
            )
            match = re.search(
                r"Özetçe\s*[—\-–]+\s*(.*?)\s*(?=Abstract|Keywords)",
                merged_tr2,
                re.DOTALL | re.IGNORECASE
            )
            abs_tr = self.text_utils.clean_text(match.group(1)) if match else ""
        
        # İngilizce özet fallback
        if not abs_en:
            merged_en2 = page_analyzer.collect_until_markers(
                doc, page_idx, ["I.", "I ", "GİRİŞ"], hard_limit=8
            )
            match = re.search(
                r"Abstract\s*[—\-–]+\s*(.*?)\s*(?=Keywords|I\.\s|I\s|GİRİŞ)",
                merged_en2,
                re.DOTALL | re.IGNORECASE
            )
            abs_en = self.text_utils.clean_text(match.group(1)) if match else ""
        
        # Anahtar kelimeleri çıkar
        keywords_text = page_analyzer.collect_until_markers(
            doc, page_idx, ["I.", "GİRİŞ", "INTRODUCTION"], hard_limit=3
        )
        keywords_tr = self.extract_keywords_tr(keywords_text)
        keywords_en = self.extract_keywords_en(keywords_text)
        
        return abs_tr, abs_en, keywords_tr, keywords_en


# ====================================================================
# TITLE EXTRACTOR
# ====================================================================

class TitleExtractor:
    """Başlık çıkarma sınıfı"""
    
    def __init__(self):
        self.text_utils = TextUtils()
    
    def _filter_noise_spans(self, spans: List[Dict], page_height: float) -> List[Dict]:
        """Başlık aday span'lerinden gürültüyü filtreler"""
        filtered = []
        for s in spans:
            text = s["text"]
            
            # Çok kısa veya boş metinleri atla
            if len(text) < 2:
                continue
                
            # Header bilgilerini atla
            if "LIFT UP" in text or "Bildiri Kitabı" in text:
                continue
                
            # Email adresleri atla
            if "@" in text:
                continue
                
            filtered.append(s)
        
        return filtered
    
    def _group_spans_into_lines(self, spans: List[Dict], y_tolerance: float = 3.0) -> List[Dict]:
        """Span'leri Y pozisyonuna göre satırlara gruplar"""
        lines = []
        current_line = []
        current_y = None
        
        def flush_line():
            """Mevcut satırı lines listesine ekle"""
            if not current_line:
                return
            current_line.sort(key=lambda d: d["x"])
            line_text = self.text_utils.clean_text(" ".join(d["text"] for d in current_line))
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
    
    def _filter_non_title_lines(self, lines: List[Dict]) -> List[Dict]:
        """Başlık olmayan satırları filtreler"""
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
    
    def _split_tr_en_by_gap(self, texts: List[str], ys: List[float], 
                           gap_threshold: float = 8.0) -> Tuple[str, str]:
        """Satırlar arasındaki gap'e bakarak TR ve EN başlıkları ayırır"""
        if len(ys) < 2:
            return "", ""
        
        # Ardışık satırlar arasındaki gap'leri hesapla
        gaps = [ys[i + 1] - ys[i] for i in range(len(ys) - 1)]
        max_gap = max(gaps)
        max_gap_idx = gaps.index(max_gap)
        
        # Yeterince büyük gap yoksa boş döndür
        if max_gap < gap_threshold:
            return "", ""
        
        # Gap'e göre böl
        split_idx = max_gap_idx + 1
        top_texts = texts[:split_idx]
        bottom_texts = texts[split_idx:]
        
        # Hangi grup daha çok İngilizce ipucu içeriyor?
        top_en_score = sum(1 for t in top_texts if self.text_utils.looks_english_line(t))
        bottom_en_score = sum(1 for t in bottom_texts if self.text_utils.looks_english_line(t))
        
        if bottom_en_score >= top_en_score:
            return self.text_utils.clean_text(" ".join(top_texts)), self.text_utils.clean_text(" ".join(bottom_texts))
        else:
            return self.text_utils.clean_text(" ".join(bottom_texts)), self.text_utils.clean_text(" ".join(top_texts))
    
    def _split_tr_en_by_english_hint(self, texts: List[str]) -> Tuple[str, str]:
        """İngilizce ipuçlarına bakarak TR ve EN başlıkları ayırır"""
        first_en_idx = None
        for i, text in enumerate(texts):
            if self.text_utils.looks_english_line(text):
                first_en_idx = i
                break
        
        if first_en_idx is not None and first_en_idx > 0:
            title_tr = self.text_utils.clean_text(" ".join(texts[:first_en_idx]))
            title_en = self.text_utils.clean_text(" ".join(texts[first_en_idx:]))
            return title_tr, title_en
        
        return "", ""
    
    def _split_tr_en_by_char(self, texts: List[str]) -> Tuple[str, str]:
        """Türkçe karakter varlığına bakarak TR ve EN başlıkları ayırır"""
        tr_lines = []
        en_lines = []
        found_en = False
        
        for text in texts:
            # Türkçe karakter var ve henüz EN başlamadıysa -> TR
            if self.text_utils.contains_tr_char(text) and not found_en:
                tr_lines.append(text)
                continue
            
            # TR bittikten sonra Türkçe karakter yok -> EN başladı
            if not self.text_utils.contains_tr_char(text) and tr_lines:
                found_en = True
                en_lines.append(text)
                continue
            
            # Belirsiz durumlar
            if not tr_lines and not found_en:
                tr_lines.append(text)
            else:
                en_lines.append(text)
        
        return self.text_utils.clean_text(" ".join(tr_lines)), self.text_utils.clean_text(" ".join(en_lines))
    
    def extract(self, page) -> Tuple[str, str]:
        """
        Sayfadan makale başlığını Türkçe ve İngilizce olarak ayrı çıkarır.
        
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
        
        # 2. Özetçe/Abstract'ın Y pozisyonunu bul
        y_abstract = None
        for s in spans:
            if "Özetçe" in s["text"] or "Abstract" in s["text"]:
                if y_abstract is None or s["y"] < y_abstract:
                    y_abstract = s["y"]
        if y_abstract is None:
            y_abstract = page_h * 0.60
        
        # 3. Başlık bölgesini belirle
        y_max = y_abstract - 2
        region = [s for s in spans if s["y"] <= y_max]
        if not region:
            return "", ""
        
        # 4. En büyük fontu bul ve tolerans bandı seç
        max_size = max(s["size"] for s in region)
        if max_size <= 0:
            return "", ""
        
        band = [s for s in region if s["size"] >= max_size - 4.0]
        if not band:
            return "", ""
        
        # 5. Span'leri Y pozisyonuna göre sırala
        band.sort(key=lambda d: (d["y"], d["x"]))
        
        # 6. Gürültüyü filtrele
        band = self._filter_noise_spans(band, page_h)
        if not band:
            return "", ""
        
        # 7. Span'leri satırlara grupla
        lines = self._group_spans_into_lines(band, y_tolerance=3.0)
        if not lines:
            return "", ""
        
        # 8. Başlık olmayan satırları filtrele
        lines = self._filter_non_title_lines(lines)
        if not lines:
            return "", ""
        
        # 9. Y pozisyonuna göre sırala
        lines.sort(key=lambda d: d["y"])
        texts = [line["text"] for line in lines]
        ys = [line["y"] for line in lines]
        
        # 10. Üç aşamalı ayırma stratejisi
        
        # Strateji 1: Gap ile ayır
        title_tr, title_en = self._split_tr_en_by_gap(texts, ys, gap_threshold=8.0)
        if title_tr and title_en:
            return title_tr, title_en
        
        # Strateji 2: İngilizce ipuçlarına göre ayır
        title_tr, title_en = self._split_tr_en_by_english_hint(texts)
        if title_tr and title_en:
            return title_tr, title_en
        
        # Strateji 3: Türkçe karakter varlığına göre ayır
        return self._split_tr_en_by_char(texts)


# ====================================================================
# PDF PROCESSOR
# ====================================================================

class PDFProcessor:
    """PDF işleme ve makale çıkarma ana sınıfı"""
    
    def __init__(self):
        self.page_analyzer = PageAnalyzer()
        self.title_extractor = TitleExtractor()
        self.abstract_extractor = AbstractExtractor()
    
    def process_pdf(self, pdf_path: str, year: str, output_csv: Optional[str] = None) -> List[Article]:
        """
        Tek bir PDF dosyasından tüm makaleleri çıkarır.
        
        Args:
            pdf_path: PDF dosya yolu
            year: Yıl bilgisi
            output_csv: Çıktı CSV dosya yolu (None ise otomatik oluşturulur)
            
        Returns:
            Çıkarılan Article nesnelerinin listesi
        """
        print(f"📄 PDF açılıyor: {pdf_path}")
        doc = fitz.open(pdf_path)
        print(f"📊 Toplam sayfa sayısı: {len(doc)}")
        
        articles = []
        
        # Her sayfayı tara
        for page_idx in range(len(doc)):
            page = doc[page_idx]
            text = page.get_text()
            
            # Bu sayfa yeni makale başlangıcı mı?
            if not self.page_analyzer.is_article_start_page(text):
                continue
            
            # Başlıkları çıkar
            title_tr, title_en = self.title_extractor.extract(page)
            
            # Özetleri ve anahtar kelimeleri çıkar
            abs_tr, abs_en, keywords_tr, keywords_en = self.abstract_extractor.extract_with_fallback(
                doc, page_idx
            )
            
            # Makale nesnesi oluştur
            article = Article(
                page_number=page_idx + 1,
                year=year,
                title_tr=title_tr,
                title_en=title_en,
                abstract_tr=abs_tr,
                abstract_en=abs_en,
                keywords_tr=keywords_tr,
                keywords_en=keywords_en
            )
            articles.append(article)
            
            # İlerleme göster
            print(f"✅ Sayfa {page_idx+1}: TR='{title_tr[:60]}...' | EN='{title_en[:60]}...'")
        
        doc.close()
        
        # CSV'ye yaz
        if output_csv is None:
            base = os.path.splitext(pdf_path)[0]
            output_csv = base + ".csv"
        
        self._write_to_csv(articles, output_csv)
        print(f"\n✨ {len(articles)} makale bulundu. CSV yazıldı: {output_csv}")
        
        return articles
    
    def _write_to_csv(self, articles: List[Article], output_path: str):
        """Makaleleri CSV dosyasına yazar"""
        fieldnames = ["PageNumber", "Year", "Title_TR", "Title_EN", 
                     "Abstract_TR", "Abstract_EN", "Keywords_TR", "Keywords_EN"]
        
        with open(output_path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for article in articles:
                writer.writerow(article.to_dict())
    
    def process_path(self, input_path: str, year: str, out_dir: Optional[str] = None):
        """
        PDF dosyası, klasör veya glob pattern'i işler.
        
        Args:
            input_path: PDF dosyası, klasör yolu veya glob pattern
            year: Yıl bilgisi
            out_dir: Çıktı dizini (None ise PDF ile aynı yerde oluşturulur)
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
            
            self.process_pdf(pdf, year, out_csv)


# ====================================================================
# MAIN EXECUTION
# ====================================================================

def main():
    """Ana çalıştırma fonksiyonu"""
    # Konfigürasyon
    YEAR = "2021-2022"
    PDF_PATH = f"Bildiri-Kitabi-{YEAR}.pdf"
    OUTPUT_DIR = None
    
    print("="*80)
    print("LIFT UP Dataset Extraction Tool (OOP Implementation)")
    print("="*80)
    print(f"PDF Path: {PDF_PATH}")
    print(f"Year: {YEAR}")
    print(f"Output Dir: {OUTPUT_DIR}")
    print("="*80 + "\n")
    
    try:
        processor = PDFProcessor()
        processor.process_path(PDF_PATH, YEAR, OUTPUT_DIR)
        print("\n🎉 İşlem başarıyla tamamlandı!")
    except Exception as e:
        print(f"\n❌ HATA: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
