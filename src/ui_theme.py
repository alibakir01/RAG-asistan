"""app.py görsel temasından çıkarılan paylaşılan UI parçaları (CSS assets/app_style.css'te)."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def global_css() -> str:
    p = ROOT / "assets" / "app_style.css"
    return p.read_text(encoding="utf-8") if p.exists() else ""

SUGGESTIONS = {'bilgisayar': [('📚', '2023 girişliyim 3. dönem hangi dersler var?'),
                ('🔢', 'COMP 101 dersi kaç AKTS?'),
                ('🧩', 'COMP 305 dersinin ön şartı nedir?'),
                ('📋', 'Staj yönergesi maddeleri neler?')],
 'makine': [('📚', '2024 girişliyim 4. dönem dersleri neler?'),
            ('⚙️', 'ME 201 dersi kaç kredi?'),
            ('🧩', 'ME 301 ön şartı var mı?'),
            ('📋', 'Makine müfredatı 2025 nasıl?')],
 'endustri': [('📚', '2022 girişli 2. sınıf dersleri neler?'),
              ('📊', 'IE 202 kaç AKTS?'),
              ('🧩', 'IE 305 ön şartları neler?'),
              ('📋', '2021 müfredatı tüm dersler')],
 'elektrik': [('📚', '2023 girişli 5. dönem dersleri?'),
              ('⚡', 'EE 201 dersi içeriği nedir?'),
              ('🧩', 'Seçmeli kapsüller nelerdir?'),
              ('📋', '2025 müfredatı 1. sınıf')],
 'insaat': [('📚', '2023 girişliyim 3. dönem dersleri?'),
            ('🏗️', 'CE 201 kaç kredi?'),
            ('🧩', 'CE 305 ön şartı?'),
            ('📋', '2021 müfredatı tüm dersler')],
 'malzeme': [('📚', '1. sınıf dersleri neler?'),
             ('🔬', 'MSNE 201 kaç AKTS?'),
             ('🧩', 'Müfredat hakkında bilgi'),
             ('📋', 'Tüm dersleri listele')],
 'mimarlik': [('📚', '1. sınıf mimarlık dersleri neler?'),
              ('🏛️', 'ARCH 101 dersinin içeriği nedir?'),
              ('🧩', 'ARCH 223 kaç kredi?'),
              ('📋', '3. sınıf güz dönemi dersleri')],
 'isletme': [('📚', '1. sınıf işletme dersleri neler?'),
             ('📊', 'BA 207 Principles of Finance kaç AKTS?'),
             ('🧩', 'BA 222 ön şartı var mı?'),
             ('📋', '3. sınıf güz dönemi dersleri')],
 'ekonomi': [('📚', '1. sınıf ekonomi dersleri neler?'),
             ('📈', 'ECON 201 Microeconomics I ön şartı nedir?'),
             ('🧩', 'ECON 301 Econometrics I kaç AKTS?'),
             ('📋', '3. sınıf güz dönemi ekonomi dersleri')],
 'siyaset': [('📚', '1. sınıf siyaset bilimi dersleri neler?'),
             ('🏛️', 'POLS 101 Siyaset Bilimine Giriş kaç AKTS?'),
             ('🧩', 'POLS 299 Yaz Stajı I ön şartı nedir?'),
             ('📋', '3. sınıf güz dönemi POLS dersleri')],
 'psikoloji': [('📚', 'Core Courses II dersleri neler?'),
               ('🧠', 'PSYC 104 Statistics for Psychology ön şartı nedir?'),
               ('🧩', "Fundamental Cluster I'de hangi dersler var?"),
               ('📋', 'Tüm seçmeli seminer (PSYS) dersleri')],
 'biyomuhendislik': [('📚', '1. sınıf güz dönemi biyomühendislik dersleri neler?'),
                     ('🧬', 'BENG 201 Biyokimya ön şartı nedir?'),
                     ('🧩', '4. sınıf alan seçimi nasıl yapılır?'),
                     ('📋', 'Biyomühendislik stajı kaç gün ve nasıl değerlendirilir?')],
 'mbg': [('📚', '1. sınıf güz dönemi MBG dersleri neler?'),
         ('🧬', 'MBG 207 Organik Kimya ön şartı nedir?'),
         ('🔬', 'MBG alan teknik seçmeli dersleri neler?'),
         ('🎓', 'Moleküler Biyoloji ve Genetik mezuniyet koşulları neler?')]}

BOLUM_SVG = {'bilgisayar': '<span class="bolum-icon" title="Bilgisayar Mühendisliği"><svg viewBox="0 0 24 24" '
               'xmlns="http://www.w3.org/2000/svg"><rect x="2" y="3" width="20" height="14" rx="2"/><path d="M8 '
               '21h8"/><path d="M12 17v4"/><path d="M9 8l-2 2 2 2"/><path d="M15 8l2 2-2 2"/></svg></span>',
 'makine': '<span class="bolum-emoji" title="Makine Mühendisliği">⚙️</span>',
 'endustri': '<span class="bolum-icon" title="Endüstri Mühendisliği"><svg viewBox="0 0 24 24" '
             'xmlns="http://www.w3.org/2000/svg"><path d="M3 3v18h18"/><rect x="7" y="13" width="3" height="5"/><rect '
             'x="12" y="9" width="3" height="9"/><rect x="17" y="5" width="3" height="13"/></svg></span>',
 'elektrik': '<span class="bolum-icon" title="Elektrik-Elektronik Mühendisliği"><svg viewBox="0 0 24 24" '
             'xmlns="http://www.w3.org/2000/svg"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 '
             '2"/></svg></span>',
 'insaat': '<span class="bolum-emoji" title="İnşaat Mühendisliği">🏗️</span>',
 'malzeme': '<span class="bolum-icon" title="Malzeme Bilimi ve Nanoteknoloji"><svg viewBox="0 0 24 24" '
            'xmlns="http://www.w3.org/2000/svg"><circle cx="12" cy="12" r="1.2" fill="#fff"/><ellipse cx="12" cy="12" '
            'rx="10" ry="4"/><ellipse cx="12" cy="12" rx="10" ry="4" transform="rotate(60 12 12)"/><ellipse cx="12" '
            'cy="12" rx="10" ry="4" transform="rotate(120 12 12)"/></svg></span>',
 'mimarlik': '<span class="bolum-icon" title="Mimarlık"><svg viewBox="0 0 24 24" '
             'xmlns="http://www.w3.org/2000/svg"><path d="M3 21h18"/><path d="M5 21V8l7-5 7 5v13"/><path d="M9 '
             '21v-6h6v6"/></svg></span>',
 'isletme': '<span class="bolum-icon" title="İşletme"><svg viewBox="0 0 24 24" '
            'xmlns="http://www.w3.org/2000/svg"><path d="M3 21V8h18v13"/><path d="M9 21V12h6v9"/><path d="M3 8l9-5 9 '
            '5"/><path d="M7 16h2"/><path d="M15 16h2"/></svg></span>',
 'ekonomi': '<span class="bolum-icon" title="Ekonomi"><svg viewBox="0 0 24 24" '
            'xmlns="http://www.w3.org/2000/svg"><path d="M3 17l6-6 4 4 8-8"/><path d="M14 7h7v7"/></svg></span>',
 'siyaset': '<span class="bolum-icon" title="Siyaset Bilimi ve Uluslararası İlişkiler"><svg viewBox="0 0 24 24" '
            'xmlns="http://www.w3.org/2000/svg"><path d="M3 21h18"/><path d="M12 3v18"/><path d="M12 3l7 4-7 4"/><path '
            'd="M5 21V10"/><path d="M19 21V14"/></svg></span>',
 'psikoloji': '<span class="bolum-emoji" title="Psikoloji" style="font-family: \'Times New Roman\', serif; '
              'font-weight: 700; font-size: 1.15em; line-height: 1;">Ψ</span>',
 'biyomuhendislik': '<span class="bolum-icon" title="Biyomühendislik"><svg viewBox="0 0 24 24" '
                    'xmlns="http://www.w3.org/2000/svg"><path d="M9 3c0 4 6 5 6 9s-6 5-6 9"/><path d="M15 3c0 4-6 5-6 '
                    '9s6 5 6 9"/><path d="M8.5 7h7"/><path d="M8.5 17h7"/><path d="M10 5.5h4"/><path d="M10 '
                    '18.5h4"/></svg></span>',
 'mbg': '<span class="bolum-icon" title="Moleküler Biyoloji ve Genetik"><svg viewBox="0 0 24 24" '
        'xmlns="http://www.w3.org/2000/svg"><circle cx="6" cy="7" r="2.5"/><circle cx="18" cy="7" r="2.5"/><circle '
        'cx="12" cy="17" r="2.5"/><path d="M8 8.5l3 6.5"/><path d="M16 8.5l-3 6.5"/><path d="M8 7h8"/></svg></span>'}
