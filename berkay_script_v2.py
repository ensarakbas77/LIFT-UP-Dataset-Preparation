# """
# PDF Özet Çıkarıcı - Footer Düzeltmeli Sürüm

# Değişiklikler:
# 1. Sayfa numarası algılama alanı genişletildi (Alt 80px).
# 2. Yıl sayıları (örn: 2021) sayfa numarası olarak algılanmaması için filtre eklendi.
# 3. Klasör yapısı korundu.
# """

# import pdfplumber
# import re
# import csv
# import json
# import os
# import logging
# from typing import Dict, List, Tuple, Optional
# from dataclasses import dataclass, asdict

# # ==============================================================================
# # AYARLAR
# # ==============================================================================
# PROJECT_YEAR = 2021
# PDF_FOLDER = "Bildiri Kitapları"

# # ==============================================================================
# # 1. KONFİGÜRASYON
# # ==============================================================================
# class Configuration:
#     def __init__(self, config_file: str = "config.json"):
#         self.config_file = config_file
#         self.data = self._load()
#         self._prepare()
    
#     def _load(self) -> Dict:
#         try:
#             with open(self.config_file, 'r', encoding='utf-8') as f:
#                 return json.load(f)
#         except (FileNotFoundError, json.JSONDecodeError):
#             return self._default_config()
    
#     def _default_config(self) -> Dict:
#         return {
#             "start_keywords": ["Özetçe", "Özet", "Abstract"],
#             "end_keywords": ["Anahtar Kelimeler", "Keywords"],
#             "csv_output_name": "ozetler.csv",
#             "min_text_length": 20
#         }
    
#     def _prepare(self):
#         self.start_keywords = self.data.get("start_keywords", [])
#         self.end_keywords = self.data.get("end_keywords", [])
#         self.csv_output_name = self.data.get("csv_output_name", "ozetler.csv")
#         self.min_len = self.data.get("min_text_length", 20)

# # ==============================================================================
# # 2. VERİ MODELİ
# # ==============================================================================
# @dataclass
# class Project:
#     page_no: int
#     pdf_name: str
#     title: str
#     abstract_tr: str
#     abstract_en: str
#     year: int
    
#     def clean(self, max_length: int = 5000) -> 'Project':
#         return Project(
#             page_no=self.page_no,
#             pdf_name=self.pdf_name,
#             title=self._clean_text(self.title, 500),
#             abstract_tr=self._clean_text(self.abstract_tr, max_length),
#             abstract_en=self._clean_text(self.abstract_en, max_length),
#             year=self.year
#         )
    
#     @staticmethod
#     def _clean_text(text: str, max_length: int) -> str:
#         if not text: return ""
#         try:
#             text = text.encode('utf-8').decode('utf-8')
#         except UnicodeError:
#             text = text.encode('utf-8', errors='ignore').decode('utf-8')
        
#         text = text.replace('\n', ' ')
#         text = ' '.join(text.split())
#         if len(text) > max_length: text = text[:max_length] + "..."
#         return text.strip()

# # ==============================================================================
# # 3. MOTOR
# # ==============================================================================
# class PDFAbstractExtractor:
#     def __init__(self, config: Optional[Configuration] = None):
#         self.config = config or Configuration()

#     def clean_text(self, text: str) -> str:
#         if not text: return ""
#         return ' '.join(text.split())

#     def _extract_single_abstract(self, text: str, start_list: List[str], end_list: List[str]) -> str:
#         start_index = -1
#         best_match_len = 0
#         for start_kw in start_list:
#             match = re.search(rf"\b{re.escape(start_kw)}\b", text, re.IGNORECASE)
#             if not match: match = re.search(rf"{re.escape(start_kw)}", text, re.IGNORECASE)
#             if match:
#                 start_index = match.start()
#                 best_match_len = len(match.group(0))
#                 break
        
#         if start_index == -1: return ""
#         cut_text = text[start_index + best_match_len:]
        
#         end_index = -1
#         for end_kw in end_list:
#             match = re.search(rf"{re.escape(end_kw)}", cut_text, re.IGNORECASE)
#             if match:
#                 end_index = match.start()
#                 break
        
#         result = cut_text[:end_index] if end_index != -1 else cut_text[:1500]
#         return re.sub(r'^[\s:\.\-—–]+', '', result).strip()

#     # --- KRİTİK GÜNCELLEME: SAYFA NUMARASI BULUCU ---
#     def find_page_number(self, page: pdfplumber.page.Page) -> int:
#         """
#         Sol alt köşedeki (Footer) sayfa numarasını bulur.
#         Yıl sayılarını (2021) eler.
#         """
#         try:
#             # 1. Alanı Genişlet: Yüksekliğin son 80 pikseline bak (Daha yukarıyı da görsün)
#             # Sol tarafın %50'sine bak.
#             footer_box = (0, page.height - 80, page.width * 0.50, page.height)
#             footer_crop = page.crop(footer_box)
            
#             text = footer_crop.extract_text()
#             if not text:
#                 return page.page_number # Bulamazsa PDF indexini dön

#             # 2. Sayıları Ayıkla
#             numbers = re.findall(r'\d+', text)
            
#             valid_numbers = []
#             for n in numbers:
#                 val = int(n)
#                 # 3. Filtreleme: 1900'den büyük sayıları YIL varsay ve alma.
#                 # Sayfa numarası genelde 1-1000 arasıdır.
#                 if val < 1900: 
#                     valid_numbers.append(val)
            
#             if valid_numbers:
#                 # 4. Seçim: Genelde ilk bulunan sayı sayfa numarasıdır.
#                 # Örn: "50 | TUSAŞ" -> [50]
#                 return valid_numbers[0]
            
#             return page.page_number 
        
#         except Exception:
#             return page.page_number

#     def find_title(self, page: pdfplumber.page.Page) -> str:
#         try:
#             header_box = (0, 0, page.width, page.height * 0.20)
#             header_crop = page.crop(header_box)
#             chars = header_crop.chars
#             if not chars: return "Başlık Bulunamadı"
            
#             max_size = max(c['size'] for c in chars if c['size'])
#             title_chars = [c['text'] for c in chars if c['size'] and c['size'] > max_size * 0.8]
#             return self.clean_text("".join(title_chars))
#         except:
#             return "Hata"

#     def extract_abstracts_smart(self, page: pdfplumber.page.Page) -> Tuple[str, str]:
#         try:
#             width = page.width
#             height = page.height
#             half = width / 2
            
#             left_text = self.clean_text(page.crop((0, 0, half-10, height)).extract_text() or "")
#             right_text = self.clean_text(page.crop((half+10, 0, width, height)).extract_text() or "")
            
#             ab_tr = self._extract_single_abstract(left_text, self.config.start_keywords, self.config.end_keywords)
#             if not ab_tr: ab_tr = self._extract_single_abstract(right_text, self.config.start_keywords, self.config.end_keywords)
            
#             ab_en = self._extract_single_abstract(left_text, ["Abstract"], self.config.end_keywords)
#             if not ab_en: ab_en = self._extract_single_abstract(right_text, ["Abstract"], self.config.end_keywords)
            
#             return ab_tr, ab_en
#         except:
#             return "", ""

#     def extract_data_from_pdf(self, pdf_path: str) -> List[Project]:
#         logging.info(f"İşleniyor: {os.path.basename(pdf_path)}")
#         projects = []
#         titles_seen = set()
#         pdf_name = os.path.basename(pdf_path)
        
#         try:
#             with pdfplumber.open(pdf_path) as pdf:
#                 for i, page in enumerate(pdf.pages):
#                     try:
#                         raw = self.clean_text(page.extract_text() or "")
#                         if any(kw in raw for kw in ["Özet", "Abstract"]):
                            
#                             # GÜNCELLENMİŞ FONKSİYON BURADA KULLANILIYOR
#                             page_num = self.find_page_number(page)
                            
#                             title = self.find_title(page)
#                             tr, en = self.extract_abstracts_smart(page)
                            
#                             missing = []
#                             if not title: missing.append("Başlık")
#                             if len(tr) < self.config.min_len: missing.append("TR")
#                             if len(en) < self.config.min_len: missing.append("EN")
                            
#                             if (len(tr) > 20 or len(en) > 20) and title not in titles_seen:
#                                 p = Project(page_num, pdf_name, title, tr, en, PROJECT_YEAR).clean()
#                                 projects.append(p)
#                                 titles_seen.add(title)
#                                 if not missing:
#                                     logging.info(f"✅ Sayfa {page_num}: OK ({title[:20]}...)")
#                                 else:
#                                     logging.warning(f"⚠️ Sayfa {page_num}: Eksik {missing}")
#                     except Exception as e:
#                         logging.error(f"Hata Sayfa {i+1}: {e}")
#         except Exception as e:
#             logging.error(f"PDF Açılamadı: {e}")
#         return projects

#     def export_csv_append(self, projects: List[Project]):
#         filename = self.config.csv_output_name
#         if not projects: return
#         file_exists = os.path.exists(filename)
        
#         try:
#             with open(filename, 'a', newline='', encoding='utf-8-sig') as f:
#                 writer = csv.writer(f)
#                 if not file_exists or os.stat(filename).st_size == 0:
#                     writer.writerow(["Dosya", "Yıl", "Sayfa", "Başlık", "Özet (TR)", "Abstract (EN)"])
#                 for p in projects:
#                     writer.writerow([p.pdf_name, p.year, p.page_no, p.title, p.abstract_tr, p.abstract_en])
#             logging.info(f"💾 {len(projects)} proje CSV'ye eklendi.")
#         except Exception as e:
#             logging.error(f"Yazma hatası: {e}")

# # ==============================================================================
# # MAIN
# # ==============================================================================
# def main():
#     logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s', handlers=[logging.StreamHandler()])
    
#     if not os.path.isdir(PDF_FOLDER):
#         logging.error(f"Klasör bulunamadı: {PDF_FOLDER}")
#         return

#     config = Configuration()
#     extractor = PDFAbstractExtractor(config)
    
#     files = [os.path.join(PDF_FOLDER, f) for f in os.listdir(PDF_FOLDER) if f.lower().endswith('.pdf')]
#     logging.info(f"📁 Klasörde {len(files)} PDF bulundu.")
    
#     for pdf in files:
#         data = extractor.extract_data_from_pdf(pdf)
#         extractor.export_csv_append(data)

# if __name__ == "__main__":
#     main()


#--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------



#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PDF Özet Çıkarıcı - Akıllı Başlangıç Tespiti (False Positive Önleme)

Değişiklikler:
1. 'Özet/Abstract' kelimesinin sayfanın neresinde olduğuna bakılır (Y koordinatı).
   Eğer sayfanın çok aşağısındaysa (örn: dipnotlarda) o sayfa atlanır.
2. Başlık tespiti sıkılaştırıldı.
"""

import pdfplumber
import re
import csv
import json
import os
import logging
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, asdict

# ==============================================================================
# AYARLAR
# ==============================================================================
PROJECT_YEAR = 2021
PDF_FOLDER = "Bildiri Kitapları"

# ==============================================================================
# 1. KONFİGÜRASYON
# ==============================================================================
class Configuration:
    def __init__(self, config_file: str = "config.json"):
        self.config_file = config_file
        self.data = self._load()
        self._prepare()
    
    def _load(self) -> Dict:
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return self._default_config()
    
    def _default_config(self) -> Dict:
        return {
            "start_keywords": ["Özetçe","Abstract"],
            "end_keywords": ["Anahtar Kelimeler", "Keywords"],
            "csv_output_name": "ozetler.csv",
            "min_text_length": 20
        }
    
    def _prepare(self):
        self.start_keywords = self.data.get("start_keywords", [])
        self.end_keywords = self.data.get("end_keywords", [])
        self.csv_output_name = self.data.get("csv_output_name", "ozetler.csv")
        self.min_len = self.data.get("min_text_length", 20)

# ==============================================================================
# 2. VERİ MODELİ
# ==============================================================================
@dataclass
class Project:
    page_no: int
    pdf_name: str
    title: str
    abstract_tr: str
    abstract_en: str
    year: int
    
    def clean(self, max_length: int = 5000) -> 'Project':
        return Project(
            page_no=self.page_no,
            pdf_name=self.pdf_name,
            title=self._clean_text(self.title, 500),
            abstract_tr=self._clean_text(self.abstract_tr, max_length),
            abstract_en=self._clean_text(self.abstract_en, max_length),
            year=self.year
        )
    
    @staticmethod
    def _clean_text(text: str, max_length: int) -> str:
        if not text: return ""
        try:
            text = text.encode('utf-8').decode('utf-8')
        except UnicodeError:
            text = text.encode('utf-8', errors='ignore').decode('utf-8')
        
        text = text.replace('\n', ' ')
        text = ' '.join(text.split())
        if len(text) > max_length: text = text[:max_length] + "..."
        return text.strip()

# ==============================================================================
# 3. MOTOR
# ==============================================================================
class PDFAbstractExtractor:
    def __init__(self, config: Optional[Configuration] = None):
        self.config = config or Configuration()

    def clean_text(self, text: str) -> str:
        if not text: return ""
        return ' '.join(text.split())

    # --- YENİ ÖZELLİK: Sayfa Başlangıç Kontrolü ---
    def is_project_start_page(self, page: pdfplumber.page.Page) -> bool:
        """
        Bir sayfanın proje başlangıç sayfası olup olmadığını kontrol eder.
        Kriter: "Özet" veya "Abstract" kelimesi sayfanın ÜST YARISINDA (top %60) olmalı.
        Ayrıca sol sütunda olmalı.
        """
        try:
            width = page.width
            height = page.height
            
            # Sadece sayfanın üst yarısını ve sol tarafını tara
            # (Abstract genelde sol üstte başlar)
            check_box = (0, 0, width / 2 + 50, height * 0.60) 
            check_crop = page.crop(check_box)
            
            text = check_crop.extract_text() or ""
            
            # Kelimeleri ara (Büyük/Küçük harf duyarsız)
            keywords = ["Özet", "Abstract", "Özetçe"]
            for kw in keywords:
                if re.search(rf"\b{kw}\b", text, re.IGNORECASE):
                    return True
                # Bazen "Abstract :" gibi yazılır, onu da yakala
                if re.search(rf"{kw}\s*[:\.]", text, re.IGNORECASE):
                    return True
            
            return False
        except Exception:
            return False

    def _extract_single_abstract(self, text: str, start_list: List[str], end_list: List[str]) -> str:
        start_index = -1
        best_match_len = 0
        for start_kw in start_list:
            match = re.search(rf"\b{re.escape(start_kw)}\b", text, re.IGNORECASE)
            if not match: match = re.search(rf"{re.escape(start_kw)}", text, re.IGNORECASE)
            if match:
                start_index = match.start()
                best_match_len = len(match.group(0))
                break
        
        if start_index == -1: return ""
        cut_text = text[start_index + best_match_len:]
        
        end_index = -1
        for end_kw in end_list:
            match = re.search(rf"{re.escape(end_kw)}", cut_text, re.IGNORECASE)
            if match:
                end_index = match.start()
                break
        
        result = cut_text[:end_index] if end_index != -1 else cut_text[:1500]
        return re.sub(r'^[\s:\.\-—–]+', '', result).strip()

    def find_page_number(self, page: pdfplumber.page.Page) -> int:
        try:
            footer_box = (0, page.height - 80, page.width * 0.50, page.height)
            footer_crop = page.crop(footer_box)
            text = footer_crop.extract_text()
            if not text: return page.page_number

            numbers = re.findall(r'\d+', text)
            valid_numbers = [int(n) for n in numbers if int(n) < 1900]
            
            if valid_numbers: return valid_numbers[0]
            return page.page_number 
        except Exception:
            return page.page_number

    def find_title(self, page: pdfplumber.page.Page) -> str:
        try:
            header_box = (0, 0, page.width, page.height * 0.20)
            header_crop = page.crop(header_box)
            chars = header_crop.chars
            if not chars: return "Başlık Bulunamadı"
            
            max_size = max(c['size'] for c in chars if c['size'])
            title_chars = [c['text'] for c in chars if c['size'] and c['size'] > max_size * 0.8]
            return self.clean_text("".join(title_chars))
        except:
            return "Hata"

    def extract_abstracts_smart(self, page: pdfplumber.page.Page) -> Tuple[str, str]:
        try:
            width = page.width
            height = page.height
            half = width / 2
            
            left_text = self.clean_text(page.crop((0, 0, half-10, height)).extract_text() or "")
            right_text = self.clean_text(page.crop((half+10, 0, width, height)).extract_text() or "")
            
            ab_tr = self._extract_single_abstract(left_text, self.config.start_keywords, self.config.end_keywords)
            if not ab_tr: ab_tr = self._extract_single_abstract(right_text, self.config.start_keywords, self.config.end_keywords)
            
            ab_en = self._extract_single_abstract(left_text, ["Abstract"], self.config.end_keywords)
            if not ab_en: ab_en = self._extract_single_abstract(right_text, ["Abstract"], self.config.end_keywords)
            
            return ab_tr, ab_en
        except:
            return "", ""

    def extract_data_from_pdf(self, pdf_path: str) -> List[Project]:
        logging.info(f"İşleniyor: {os.path.basename(pdf_path)}")
        projects = []
        titles_seen = set()
        pdf_name = os.path.basename(pdf_path)
        
        try:
            with pdfplumber.open(pdf_path) as pdf:
                for i, page in enumerate(pdf.pages):
                    try:
                        # 1. ADIM: Bu sayfa bir proje başlangıcı mı? (Özet kelimesi yukarıda mı?)
                        if self.is_project_start_page(page):
                            
                            page_num = self.find_page_number(page)
                            title = self.find_title(page)
                            tr, en = self.extract_abstracts_smart(page)
                            
                            missing = []
                            if not title: missing.append("Başlık")
                            if len(tr) < self.config.min_len: missing.append("TR")
                            if len(en) < self.config.min_len: missing.append("EN")
                            
                            if (len(tr) > 20 or len(en) > 20) and title not in titles_seen:
                                p = Project(page_num, pdf_name, title, tr, en, PROJECT_YEAR).clean()
                                projects.append(p)
                                titles_seen.add(title)
                                if not missing:
                                    logging.info(f"✅ Sayfa {page_num}: OK ({title[:20]}...)")
                                else:
                                    logging.warning(f"⚠️ Sayfa {page_num}: Eksik {missing}")
                    except Exception as e:
                        logging.error(f"Hata Sayfa {i+1}: {e}")
        except Exception as e:
            logging.error(f"PDF Açılamadı: {e}")
        return projects

    def export_csv_append(self, projects: List[Project]):
        filename = self.config.csv_output_name
        if not projects: return
        file_exists = os.path.exists(filename)
        
        try:
            with open(filename, 'a', newline='', encoding='utf-8-sig') as f:
                writer = csv.writer(f)
                if not file_exists or os.stat(filename).st_size == 0:
                    writer.writerow(["Dosya", "Yıl", "Sayfa", "Başlık", "Özet (TR)", "Abstract (EN)"])
                for p in projects:
                    writer.writerow([p.pdf_name, p.year, p.page_no, p.title, p.abstract_tr, p.abstract_en])
            logging.info(f"💾 {len(projects)} proje CSV'ye eklendi.")
        except Exception as e:
            logging.error(f"Yazma hatası: {e}")

# ==============================================================================
# MAIN
# ==============================================================================
def main():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s', handlers=[logging.StreamHandler()])
    
    if not os.path.isdir(PDF_FOLDER):
        logging.error(f"Klasör bulunamadı: {PDF_FOLDER}")
        return

    config = Configuration()
    extractor = PDFAbstractExtractor(config)
    
    files = [os.path.join(PDF_FOLDER, f) for f in os.listdir(PDF_FOLDER) if f.lower().endswith('.pdf')]
    logging.info(f"📁 Klasörde {len(files)} PDF bulundu.")
    
    for pdf in files:
        data = extractor.extract_data_from_pdf(pdf)
        extractor.export_csv_append(data)

if __name__ == "__main__":
    main()