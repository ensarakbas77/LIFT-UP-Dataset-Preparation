import pdfplumber
import re
import csv
import os

# PDF'teki bozuk CID kodlarının karşılıkları (Senin çıktından analiz edildi)
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

def cid_duzelt(metin):
    """
    Metin içindeki (cid:XX) ifadelerini harflere çevirir.
    """
    if not metin:
        return ""
    
    # 1. Sözlükteki bilinen karakterleri değiştir
    for cid_code, char in CID_MAP.items():
        metin = metin.replace(cid_code, char)
    
    # 2. Hala (cid:...) kaldıysa onları temizle veya işaretle
    # (İstersen bunları boşlukla değiştirebilirsin, şimdilik okumayı kolaylaştırmak için siliyoruz)
    metin = re.sub(r'\(cid:\d+\)', '', metin)
    
    return metin

def pdf_ozet_temizle_ve_cek(pdf_yolu, csv_adi="deneme_ozetler.csv", limit=10):
    bulunan_veriler = []
    print(f"--- '{pdf_yolu}' işleniyor (Tesseract yok, CID düzeltme devrede) ---")

    try:
        with pdfplumber.open(pdf_yolu) as pdf:
            for i, page in enumerate(pdf.pages):
                if len(bulunan_veriler) >= limit:
                    break
                
                # Sayfadaki tüm metni çek
                text = page.extract_text()
                if not text:
                    continue
                
                # --- CID DÜZELTME ADIMI ---
                # Metni regex'e sokmadan önce CID karakterlerini düzeltiyoruz
                text = cid_duzelt(text)

                # Regex: Özet -> Giriş/Anahtar Kelimeler
                pattern = r'(?i)(?:özet|abstract|özetçe|öz)\s*[:\.]?\s*\n?(.*?)(?:\n\s*(?:anahtar kelimeler|keywords|giriş|introduction|1\.))'
                
                matches = re.findall(pattern, text, re.DOTALL)
                
                for match in matches:
                    clean_text = " ".join(match.split())
                    
                    if len(clean_text) > 40:
                        bulunan_veriler.append([i + 1, clean_text])
                        print(f"-> {len(bulunan_veriler)}. özet bulundu (Sayfa {i+1})")
                        
                        if len(bulunan_veriler) >= limit:
                            break

    except Exception as e:
        print(f"Hata: {e}")

    # CSV Kaydet
    if bulunan_veriler:
        with open(csv_adi, mode='w', newline='', encoding='utf-8-sig') as file:
            writer = csv.writer(file)
            writer.writerow(["Sayfa No", "Ozet Metni"])
            writer.writerows(bulunan_veriler)
        print(f"\nDosya oluşturuldu: {csv_adi}")
        print("Not: Metinde hala eksik harfler varsa 'CID_MAP' sözlüğüne ekleme yapılabilir.")
    else:
        print("Veri bulunamadı.")

# --- KULLANIM ---
dosya_adi = "Bildiri+Kitabi-2020-2021.pdf" 

if os.path.exists(dosya_adi):
    pdf_ozet_temizle_ve_cek(dosya_adi, limit=20)