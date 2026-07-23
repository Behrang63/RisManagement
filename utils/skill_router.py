import os

def select_skills_rule_based(proposal_text: str) -> list[str]:
    """
    تحلیل متن پروپوزال و انتخاب هوشمند فایل‌های مهارتی مرتبط بر اساس کلیدواژه‌ها.
    """
    # ۱. مهارت‌های پایه که همیشه و برای تمامی پروپوزال‌ها فعال هستند
    selected_skills = [
        "SKILL_Ethics_Core.md",
        "SKILL_Ethics_Decision_Tree.md",
        "SKILL_Ethics_Risk_Taxonomy.md"
    ]
    
    text_lower = proposal_text.lower()

    # ۲. جدول نگاشت کلیدواژه‌ها به فایل‌های مهارتی تخصصی
    skill_rules = {
        # رفاه حیوانات آزمایشگاهی و الگوریتم 3Rs
        "skill_animal_welfare_3rs.md": [
            "حیوان", "جانور", "موش", "خرگوش", "سگ", "میمون", "پری‌کلینیکال", "پیش‌بالینی", 
            "آزمایشگاهی", "یوتانازی", "مرگ آسان", "3rs", "in-vivo", "rat", "mice", "animal", "arrive"
        ],
        
        # متدولوژی کارآزمایی‌های بالینی و طراحی مطالعه
        "skill_clinical_methodology_audit.md": [
            "کارآزمایی بالینی", "آزمودنی", "کورسازی", "تصادفی‌سازی", "پنهان‌سازی", 
            "دارونما", "پلاسبو", "گروه کنترل", "متقاطع", "crossover", "irct", "randomization", "blinding"
        ],
        
        # محاسبات آمار بالینی، حجم نمونه و فرضیات آماری
        "skills_skill_1_clinical_statistics.md": [
            "حجم نمونه", "توان آماری", "سطح معنی‌داری", "اندازه اثر", "پیامد اصلی", 
            "پایانه‌ اولیه", "عدم فروتری", "هم‌ارزی", "برتری", "itt", "per-protocol", "sample size", "power"
        ],
        
        # رگولاتوری، کلاس خطر تجهیزات پزشکی و مجوزهای دارویی
        "skill_regulatory_classifier.md": [
            "تجهیزات پزشکی", "ملزومات پزشکی", "فرآورده بیولوژیک", "ژن‌درمانی", 
            "دارو", "مکمل", "بیوسیملار", "ژنریک", "هم‌ارزی زیستی", "gmp", "cta", "cea", "سازمان غذا و دارو"
        ],
        
        # ارزیابی فرم رضایت‌نامه آگاهانه و ساده‌سازی NLP
        "skill_consent_readability_analyzer.md": [
            "رضایت‌نامه", "رضایت آگاهانه", "رضایت کتبی", "فرم رضایت", "حق انصراف", "کودک", "قیم قانونی", "icf"
        ],
        
        # امنیت داده، بی‌نام‌سازی و حریم خصوصی
        "skill_data_privacy_security.md": [
            "حریم خصوصی", "بی‌نام‌سازی", "کدگذاری", "داده‌های سلامت", "پرونده الکترونیک", 
            "کد ملی", "ژنتیک", "زیست‌بانک", "بانک نمونه", "اومیکس", "ecrf", "ehr", "his", "hipaa", "gdpr"
        ],
        
        # ممیزی مالی، پوشش بیمه‌ای و تعارض منافع
        "skill_financial_coi_auditor.md": [
            "بودجه", "هزینه", "اسپانسر", "حامی مالی", "بیمه", "بیمه‌نامه", "غرامت", 
            "تعارض منافع", "سهام‌داری", "حق‌الزحمه", "coi"
        ],
        
        # جرم‌یابی علمی، ممیزی تصاویر و تقلب پژوهشی
        "skill_misconduct_forensics.md": [
            "تصویر", "فیگور", "پاتولوژی", "میکروسکوپ", "وسترن بلات", "ژل الکتروفورز", 
            "سرقت ادبی", "همانندجویی", "دستکاری داده", "جعل", "مجلات یغماگر", "لیست سیاه", "western blot", "plagiarism"
        ]
    }

    # ۳. اسکن متن و افزودن مهارت در صورت کشف کلیدواژه
    for skill_file, keywords in skill_rules.items():
        if any(keyword in text_lower for keyword in keywords):
            selected_skills.append(skill_file)

    return list(set(selected_skills))


def load_skill_contents(selected_skills: list[str], skills_dir: str = "Ethic_SKILL") -> tuple[str, list[str]]:
    """
    خواندن محتوای متنی فایل‌های انتخاب‌شده از پوشه Ethic_SKILL و ترکیب آن‌ها جهت تزریق به System Prompt.
    """
    combined_instructions = ""
    loaded_skills_names = []

    for file_name in selected_skills:
        file_path = os.path.join(skills_dir, file_name)
        if os.path.exists(file_path):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read().strip()
                    combined_instructions += f"\n\n====================\nدستورالعمل مهارت: {file_name}\n====================\n{content}\n"
                    loaded_skills_names.append(file_name)
            except Exception as e:
                print(f"خطا در خواندن فایل مهارت {file_name}: {str(e)}")

    return combined_instructions, loaded_skills_names