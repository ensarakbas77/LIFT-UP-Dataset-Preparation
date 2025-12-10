import pdfplumber
import re
import csv
import json
import os
import logging
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, asdict

class Konfigurasyon:
    
    def __init__(self, config_dosyasi: str = "config.json"):
        self.config_dosyasi = config_dosyasi
        self.veriler = self._yukle()
        self._hazirla()
    
    def _yukle(self) -> Dict:
        try:
            with open(self.config_dosyasi, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            # Dosya yoksa veya hatalıysa varsayılanları kullan
            return self._varsayilan_konfig()
    
    def _varsayilan_konfig(self) -> Dict:
        return {
            "baslangic_kelimeler": ["Özet", "Özetçe", "Abstract"],
            "bitis_kelimeler": ["Anahtar Kelimeler", "Keywords", "Giriş", "Introduction"],
            "csv_cikti_adi": "ozet.csv",
            "json_cikti_adi": "projeler.jsonl"
        }
    
    def _hazirla(self):
        self.baslangic_kelimeler: List[str] = self.veriler.get("baslangic_kelimeler", [])
        self.bitis_kelimeler: List[str] = self.veriler.get("bitis_kelimeler", [])
        self.csv_cikti_adi: str = self.veriler.get("csv_cikti_adi", "ozet.csv")
        self.json_cikti_adi: str = self.veriler.get("json_cikti_adi", "projeler.jsonl")


@dataclass
class Proje:
    sayfa_no: int
    baslik: str
    ozet_tr: str
    ozet_en: str
    
    def temizle(self, maks_uzunluk: int = 5000) -> 'Proje':
        return Proje(
            sayfa_no=self.sayfa_no,
            baslik=self._temizle_metin(self.baslik, maks_uzunluk),
            ozet_tr=self._temizle_metin(self.ozet_tr, maks_uzunluk),
            ozet_en=self._temizle_metin(self.ozet_en, maks_uzunluk)
        )
    
    @staticmethod
    def _temizle_metin(metin: str, maks_uzunluk: int) -> str:
        if not metin:
            return ""
        
        # UTF-8 kontrolü (basit)
        try:
            metin = metin.encode('utf-8').decode('utf-8')
        except UnicodeError:
            metin = metin.encode('utf-8', errors='ignore').decode('utf-8')
        
        # Satır sonlarını boşluğa çevir ve gereksiz boşlukları temizle
        metin = metin.replace('\n', ' ')
        metin = ' '.join(metin.split())
        
        # Maksimum uzunluk kontrolü
        if len(metin) > maks_uzunluk:
            metin = metin[:maks_uzunluk] + "..."
        
        return metin.strip()

class PDFOzetCikarici:
    def __init__(self, config: Optional[Konfigurasyon] = None):
        self.config = config or Konfigurasyon()
        self.projeler: List[Proje] = []
    
    
    def metin_temizle(self, metin: str) -> str:
        if not metin:
            return ""
        
        # Satır birleştirme ve fazla boşlukları silme
        return ' '.join(metin.split())
    
    
    def baslik_bul(self, page: pdfplumber.page.Page) -> str:
        try:
            # Sayfanın üst %20'si
            header_box = (0, 0, page.width, page.height * 0.20)
            header_crop = page.crop(header_box)
            
            chars = header_crop.chars
            if not chars:
                return "Başlık Bulunamadı"
            
            # En büyük font boyutunu bul
            max_size = max(c['size'] for c in chars if c['size'])
            
            # Büyük fontlu karakterleri seç (%80 eşik değeri ile)
            title_chars = [
                c['text'] for c in chars 
                if c['size'] and c['size'] > max_size * 0.8 
            ]
            
            raw_title = "".join(title_chars)
            return self.metin_temizle(raw_title)
            
        except Exception as e:
            logging.error(f"Başlık bulma hatası: {e}")
            return "Başlık Hatası"
    
    def _tek_ozet_cek(self, metin: str, baslangic_liste: List[str], bitis_liste: List[str]) -> str:
        # Başlangıç kelimesini bul
        baslangic_index = -1
        en_uygun_baslangic = ""
        
        for bas in baslangic_liste:
            # Kelime sınırlarına dikkat ederek ara
            match = re.search(rf"\b{re.escape(bas)}\b", metin, re.IGNORECASE)
            if not match:
                match = re.search(rf"{re.escape(bas)}", metin, re.IGNORECASE)
            
            if match:
                baslangic_index = match.start()
                en_uygun_baslangic = match.group(0)
                break
        
        if baslangic_index == -1:
            return "Bulunamadı"
        
        # Metni başlangıçtan itibaren kes
        kesilmis_metin = metin[baslangic_index + len(en_uygun_baslangic):]
        
        # Bitiş kelimesini bul
        bitis_index = -1
        for bit in bitis_liste:
            match = re.search(rf"{re.escape(bit)}", kesilmis_metin, re.IGNORECASE)
            if match:
                bitis_index = match.start()
                break
        
        # Sonucu al
        if bitis_index != -1:
            sonuc = kesilmis_metin[:bitis_index]
        else:
            # Bitiş bulunamazsa, makul bir sınır koy (örn: 1500 karakter)
            sonuc = kesilmis_metin[:1500]
        
        # Temizlik (Baştaki noktalama işaretlerini sil)
        sonuc = re.sub(r'^[\s:\.\-—–]+', '', sonuc).strip()
        return sonuc
    
    def sol_sutun_ozet_cek(self, page: pdfplumber.page.Page) -> Tuple[str, str]:
        try:
            width = page.width
            height = page.height
            
            # Sol sütunu kırp (Sayfa genişliğinin yarısı)
            left_box = (0, 0, (width / 2) - 10, height)
            left_crop = page.crop(left_box)
            
            text = left_crop.extract_text()
            if not text:
                return "Bulunamadı", "Bulunamadı"
            
            clean_text = self.metin_temizle(text)
            
            # Türkçe özet
            ozet_tr = self._tek_ozet_cek(
                clean_text, 
                ["Özetçe", "Özet"], 
                ["Anahtar", "Abstract", "Key"]
            )
            
            # İngilizce özet
            ozet_en = self._tek_ozet_cek(
                clean_text,
                ["Abstract"],
                ["Keywords", "Key Words", "Anahtar", "Introduction", "I."]
            )
            
            return ozet_tr, ozet_en
            
        except Exception as e:
            logging.error(f"Sol sütun özet çıkarma hatası: {e}")
            return f"Hata: {e}", f"Hata: {e}"
    
    
    def verileri_cek(self, pdf_yolu: str) -> List[Proje]:
        logging.info(f"PDF işleniyor: {pdf_yolu}")
        
        projeler = []
        basliklar = set()  # Tekrar kontrolü için
        
        try:
            with pdfplumber.open(pdf_yolu) as pdf:
                for i, page in enumerate(pdf.pages):
                    try:
                        raw_text = page.extract_text() or ""
                        clean_text = self.metin_temizle(raw_text)
                        
                        # Sadece özet içeren sayfaları işle
                        if any(kelime in clean_text for kelime in ["Özet", "Abstract"]):
                            baslik = self.baslik_bul(page)
                            ozet_tr, ozet_en = self.sol_sutun_ozet_cek(page)
                            
                            # Kalite kontrolü: Anlamlı uzunlukta veri var mı ve başlık tekrar ediyor mu?
                            if (len(ozet_tr) > 20 or len(ozet_en) > 20) and baslik not in basliklar:
                                proje = Proje(
                                    sayfa_no=i + 1,
                                    baslik=baslik,
                                    ozet_tr=ozet_tr,
                                    ozet_en=ozet_en
                                ).temizle()
                                
                                projeler.append(proje)
                                basliklar.add(baslik)
                                
                                logging.info(f"Sayfa {i+1}: '{baslik[:50]}...' eklendi")
                    
                    except Exception as e:
                        logging.warning(f"Sayfa {i+1} işlenirken hata: {e}")
                        continue
        
        except Exception as e:
            logging.error(f"PDF okuma veya dosya erişim hatası: {e}")
            return []
        
        logging.info(f"Toplam {len(projeler)} proje bulundu")
        return projeler
    
    
    def csv_cikti_ver(self, projeler: List[Proje], cikti_dosyasi: Optional[str] = None):
        cikti_dosyasi = cikti_dosyasi or self.config.csv_cikti_adi
        
        if not projeler:
            logging.warning("Çıktı verilecek proje yok")
            return
        
        try:
            with open(cikti_dosyasi, mode='w', newline='', encoding='utf-8-sig') as file:
                writer = csv.writer(file)
                writer.writerow(["Sayfa No", "Proje Başlığı", "Türkçe Özet", "İngilizce Abstract"])
                
                for proje in projeler:
                    writer.writerow([proje.sayfa_no, proje.baslik, proje.ozet_tr, proje.ozet_en])
            
            logging.info(f"CSV dosyası oluşturuldu: {cikti_dosyasi}")
            
        except IOError as e:
            logging.error(f"CSV yazma hatası: {e}")
    
    def json_cikti_ver(self, projeler: List[Proje], cikti_dosyasi: Optional[str] = None):
        cikti_dosyasi = cikti_dosyasi or self.config.json_cikti_adi
        
        if not projeler:
            logging.warning("Çıktı verilecek proje yok")
            return
        
        try:
            with open(cikti_dosyasi, 'w', encoding='utf-8') as f:
                for proje in projeler:
                    json.dump(asdict(proje), f, ensure_ascii=False)
                    f.write('\n')
            
            logging.info(f"JSON Lines dosyası oluşturuldu: {cikti_dosyasi}")
            
        except IOError as e:
            logging.error(f"JSON yazma hatası: {e}")
    
    def cikti_ver(self, projeler: List[Proje], formatlar: List[str] = ["csv", "json"]):
        for fmt in formatlar:
            if fmt.lower() == "csv":
                self.csv_cikti_ver(projeler)
            elif fmt.lower() == "json":
                self.json_cikti_ver(projeler)
            else:
                logging.warning(f"Desteklenmeyen format: {fmt}")

def main():
    # Logging ayarla
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('pdf_ozet_cikarici.log', encoding='utf-8'),
            logging.StreamHandler()
        ]
    )
    
    # Konfigürasyon
    config = Konfigurasyon()
    
    # PDF okuyucu
    ozet_cikarici = PDFOzetCikarici(config)
    
    # PDF dosyası - Burayı kendi dosya adınızla değiştirin
    dosya_adi = "Bildiri Kitabi 2020-2021_demo.pdf"
    
    if not os.path.exists(dosya_adi):
        logging.error(f"Dosya bulunamadı: {dosya_adi}")
        return
    
    # Verileri çek
    projeler = ozet_cikarici.verileri_cek(dosya_adi)
    
    if projeler:
        # Çıktıları ver
        ozet_cikarici.cikti_ver(projeler, ["csv", "json"])
        logging.info(f"İşlem başarıyla tamamlandı. {len(projeler)} proje işlendi.")
    else:
        logging.warning("İşlenen proje bulunamadı.")

if __name__ == "__main__":
    main()