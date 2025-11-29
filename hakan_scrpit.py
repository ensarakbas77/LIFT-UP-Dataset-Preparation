import pdfplumber
import re
import csv
import os

# PDF'teki bozuk CID kodlarının karşılıkları
CID_MAP = {
    "(cid:3)": " ",    
    "(cid:15)": ",",   
    "(cid:17)": ".",   
    "(cid:248)": "İ",
    "(cid:81)": "n",
    "(cid:86)": "s",
    "(cid:68)": "a",
    "(cid:213)": "ı",
    "(cid:93)": "z",
    "(cid:43)": "H",
    "(cid:89)": "v",
    "(cid:36)": "A",
    "(cid:85)": "r",
    "(cid:111)": "ç",
    "(cid:79)": "l",
    "(cid:72)": "e",
    "(cid:250)": "ş",
    "(cid:76)": "i",
    "(cid:87)": "t",
    "(cid:79)": "l",
    "(cid:78)": "k",
    "(cid:88)": "u",
    "(cid:80)": "m",
    "(cid:37)": "B",
    "(cid:42)": "G",
    "(cid:124)": "ö",
    "(cid:92)": "y",
    "(cid:74)": "g",
    "(cid:69)": "b",
    "(cid:83)": "p",
    "(cid:75)": "h",
    "(cid:71)": "d",
    "(cid:77)": "j",
    "(cid:129)": "ü",
    "(cid:58)": "W",    
    "(cid:20)": "-",   
    "(cid:51)": "P",
    "(cid:54)": "S",
    "(cid:24)": "o",   
    "(cid:247)": "ğ",
    "(cid:70)": "c",
    "(cid:107)": "k",  
    "(cid:90)": "Z",
    "(cid:22)": "V",
    "(cid:21)": "(",
    "(cid:64)": ")",
    "(cid:48)": "M",
    "(cid:49)": "N",
    "(cid:55)": "T",
    "(cid:23)": "f",
    "(cid:47)": "L",
    "(cid:40)": "E",
    "(cid:53)": "R",
    "(cid:44)": "I",
    "(cid:60)": "Y",
    "(cid:56)": "U",
    "(cid:57)": "V"
}

def cid_duzelt(metin: str) -> str:
    """Metin içindeki (cid:XX) ifadelerini harflere çevirir."""
    if not metin:
        return ""
    for cid_code, char in CID_MAP.items():
        metin = metin.replace(cid_code, char)
    # Kalan tüm (cid:NNN) kalıntılarını temizle
    metin = re.sub(r'\(cid:\d+\)', '', metin)
    return metin

def sayfadan_baslik_bul(duzeltilmis_metin: str) -> str:
    """
    Sayfanın başındaki satırlardan proje başlığını tahmin eder.
    1. satırı TR başlık, 2. satırı (eğer Türkçe karakter yoksa) EN başlık kabul ediyor.
    """
    # Boş olmayan satırları al
    satirlar = [s.strip() for s in duzeltilmis_metin.splitlines() if s.strip()]
    if not satirlar:
        return ""

    # Genel header'ları (LIFT UP vs.) elemek için küçük bir filtre
    filtreli = []
    for s in satirlar:
        if "LIFT UP" in s or "Sanayi Odaklı Lisans Bitirme" in s:
            continue
        filtreli.append(s)
    if filtreli:
        satirlar = filtreli

    # İlk satırı TR başlık varsay
    baslik_tr = satirlar[0]

    # İkinci satır İngilizce başlık olabilir
    baslik_en = ""
    if len(satirlar) > 1:
        ikinci = satirlar[1]
        # İçinde Türkçe karakter yoksa İngilizce başlık olma ihtimali yüksek
        if not re.search(r'[çğıöşüÇĞİÖŞÜ]', ikinci):
            baslik_en = ikinci

    if baslik_en:
        return f"{baslik_tr} / {baslik_en}"
    return baslik_tr

# Özetçe kısmını yakalayacak regex
OZET_REGEX = re.compile(
    r'(?i)özetçe\s*[—\-–:]?\s*(.+?)(?:anahtar kelimeler|keywords|giriş\b|introduction\b|1\.)',
    re.DOTALL
)

def pdf_baslik_ve_ozet_cek(pdf_yolu: str, csv_adi: str = "projeler_ozetler.csv"):
    kayitlar = []
    print(f"--- '{pdf_yolu}' işleniyor ---")

    try:
        with pdfplumber.open(pdf_yolu) as pdf:
            for sayfa_no, page in enumerate(pdf.pages, start=1):
                text = page.extract_text()
                if not text:
                    continue

                # CID düzeltmesi
                text = cid_duzelt(text)

                # Bu sayfada "Özetçe" yoksa direkt geç
                if "Özetçe" not in text and "özetçe" not in text and "ÖZETÇE" not in text:
                    continue

                baslik = sayfadan_baslik_bul(text)

                # Özetçe'yi çek
                m = OZET_REGEX.search(text)
                if not m:
                    continue

                ozet = m.group(1)
                # Tek satır haline getir
                ozet = " ".join(ozet.split())
                import pdfplumber

 
                kayitlar.append([sayfa_no, baslik, ozet])
                print(f"-> {len(kayitlar)}. proje bulundu (Sayfa {sayfa_no})")

    except Exception as e:
        print(f"Hata: {e}")
        return

    if not kayitlar:
        print("Hiç başlık/özet bulunamadı.")
        return

    # CSV'ye yaz
    with open(csv_adi, mode="w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(["Sayfa No", "Proje Başlığı", "Özetçe"])
        writer.writerows(kayitlar)
    
    print(f"\nToplam {len(kayitlar)} kayıt bulundu.")
    print(f"CSV dosyası oluşturuldu: {csv_adi}")

# --- KULLANIM ---
dosya_adi = "Bildiri+Kitabi-2020-2021.pdf"

if os.path.exists(dosya_adi):
    pdf_baslik_ve_ozet_cek(dosya_adi, csv_adi="bildiri_ozetleri.csv")
else:
    print(f"PDF bulunamadı: {dosya_adi}")
