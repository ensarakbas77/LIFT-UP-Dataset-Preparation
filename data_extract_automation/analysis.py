"""
CSV Analysis Module for LIFT UP Dataset
========================================
CSV dosyalarını analiz eder ve istatistikler çıkarır
"""

import pandas as pd
from typing import Dict, List, Any
import os


class CSVAnalyzer:
    """CSV dosyası analiz sınıfı"""
    
    def __init__(self, csv_path: str):
        """
        Args:
            csv_path: Analiz edilecek CSV dosya yolu
        """
        self.csv_path = csv_path
        self.df = None
        self._load_csv()
    
    def _load_csv(self):
        """CSV dosyasını yükler"""
        if not os.path.exists(self.csv_path):
            raise FileNotFoundError(f"CSV dosyası bulunamadı: {self.csv_path}")
        
        self.df = pd.read_csv(self.csv_path, encoding='utf-8-sig')
    
    def get_basic_stats(self) -> Dict[str, Any]:
        """
        Temel istatistikleri döndürür
        
        Returns:
            İstatistik bilgileri içeren dictionary
        """
        if self.df is None:
            return {}
        
        stats = {
            'total_articles': len(self.df),
            'total_columns': len(self.df.columns),
            'columns': self.df.columns.tolist(),
            'file_size': os.path.getsize(self.csv_path),
        }
        
        return stats
    
    def get_missing_values(self) -> Dict[str, Any]:
        """
        Eksik değerleri analiz eder
        
        Returns:
            Eksik değer bilgileri
        """
        if self.df is None:
            return {}
        
        missing = self.df.isnull().sum()
        missing_percent = (missing / len(self.df) * 100).round(2)
        
        missing_data = []
        for col in self.df.columns:
            if missing[col] > 0:
                missing_data.append({
                    'column': col,
                    'count': int(missing[col]),
                    'percentage': float(missing_percent[col])
                })
        
        return {
            'has_missing': len(missing_data) > 0,
            'total_missing': int(missing.sum()),
            'details': missing_data
        }
    
    def get_first_n_rows(self, n: int = 5) -> List[Dict]:
        """
        İlk N satırı döndürür
        
        Args:
            n: Kaç satır döndürülecek
            
        Returns:
            İlk N satırın listesi
        """
        if self.df is None:
            return []
        
        # NaN değerlerini boş string'e çevir
        df_clean = self.df.head(n).fillna('')
        
        return df_clean.to_dict('records')
    
    def get_year_distribution(self) -> Dict[str, int]:
        """
        Yıllara göre makale dağılımını döndürür
        
        Returns:
            Yıl bazında makale sayıları
        """
        if self.df is None or 'Year' not in self.df.columns:
            return {}
        
        year_counts = self.df['Year'].value_counts().to_dict()
        return {str(k): int(v) for k, v in year_counts.items()}
    
    def get_language_stats(self) -> Dict[str, Any]:
        """
        Dil bazlı istatistikler (TR/EN)
        
        Returns:
            Dil bazlı istatistikler
        """
        if self.df is None:
            return {}
        
        stats = {
            'tr_titles_filled': int((~self.df['Title_TR'].isnull()).sum()),
            'en_titles_filled': int((~self.df['Title_EN'].isnull()).sum()),
            'tr_abstracts_filled': int((~self.df['Abstract_TR'].isnull()).sum()),
            'en_abstracts_filled': int((~self.df['Abstract_EN'].isnull()).sum()),
            'tr_keywords_filled': int((~self.df['Keywords_TR'].isnull()).sum()),
            'en_keywords_filled': int((~self.df['Keywords_EN'].isnull()).sum()),
        }
        
        # Yüzde hesapla
        total = len(self.df)
        stats['tr_completeness'] = round((stats['tr_titles_filled'] + 
                                          stats['tr_abstracts_filled'] + 
                                          stats['tr_keywords_filled']) / (total * 3) * 100, 2)
        stats['en_completeness'] = round((stats['en_titles_filled'] + 
                                          stats['en_abstracts_filled'] + 
                                          stats['en_keywords_filled']) / (total * 3) * 100, 2)
        
        return stats
    
    def get_text_length_stats(self) -> Dict[str, Any]:
        """
        Metin uzunluğu istatistikleri
        
        Returns:
            Ortalama metin uzunlukları
        """
        if self.df is None:
            return {}
        
        stats = {}
        
        text_columns = ['Title_TR', 'Title_EN', 'Abstract_TR', 'Abstract_EN', 
                       'Keywords_TR', 'Keywords_EN']
        
        for col in text_columns:
            if col in self.df.columns:
                # Boş olmayanların uzunluğunu hesapla
                lengths = self.df[col].dropna().str.len()
                if len(lengths) > 0:
                    stats[col] = {
                        'avg_length': round(lengths.mean(), 2),
                        'min_length': int(lengths.min()),
                        'max_length': int(lengths.max())
                    }
        
        return stats
    
    def get_full_analysis(self) -> Dict[str, Any]:
        """
        Tüm analizleri birleştirir
        
        Returns:
            Tam analiz raporu
        """
        return {
            'basic_stats': self.get_basic_stats(),
            'missing_values': self.get_missing_values(),
            'first_rows': self.get_first_n_rows(5),
            'year_distribution': self.get_year_distribution(),
            'language_stats': self.get_language_stats(),
            'text_length_stats': self.get_text_length_stats()
        }


def analyze_csv(csv_path: str) -> Dict[str, Any]:
    """
    CSV dosyasını analiz eder (helper function)
    
    Args:
        csv_path: CSV dosya yolu
        
    Returns:
        Analiz sonuçları
    """
    analyzer = CSVAnalyzer(csv_path)
    return analyzer.get_full_analysis()
