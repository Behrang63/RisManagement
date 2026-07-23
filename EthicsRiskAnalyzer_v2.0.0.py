import streamlit as st
import pandas as pd
import json
import os
import requests
import re
import plotly.express as px
import plotly.graph_objects as go

# ---------------------------------------------------------
# ۱. پیش‌نیازها و بارگذاری ایمن کتابخانه‌های جانبی پردازش سند
# ---------------------------------------------------------
try:
    import pypdf
    PYPDF_AVAILABLE = True
except ImportError:
    PYPDF_AVAILABLE = False

try:
    import docx
    DOCX_AVAILABLE = True
except ImportError:
    DOCX_AVAILABLE = False

# تنظیمات هدر و چیدمان صفحه
st.set_page_config(
    page_title="سامانه تحلیل و ممیزی اخلاقی ریسک‌های پزشکی (EthicsRiskAnalyzer v2.0.0)",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# مسیر فایل‌های ذخیره‌سازی داده‌های محلی
RISKS_FILE = 'risks.json'
ASSESSMENTS_FILE = 'assessments.json'

# ---------------------------------------------------------
# ۲. بخش هسته محاسباتی و منطق مستقل (Decoupled Core Logic)
# ---------------------------------------------------------
class DocumentProcessor:
    """کلاس مسئول پردازش و استخراج متن از فایل‌های پروپوزال"""
    @staticmethod
    def extract_text(uploaded_file) -> str:
        if uploaded_file is None:
            return ""
        
        file_name = uploaded_file.name
        file_extension = os.path.splitext(file_name)[1].lower()
        text = ""

        try:
            if file_extension == '.pdf':
                if PYPDF_AVAILABLE:
                    reader = pypdf.PdfReader(uploaded_file)
                    for page in reader.pages:
                        page_text = page.extract_text()
                        if page_text:
                            text += page_text + "\n"
                else:
                    raise ImportError("کتابخانه `pypdf` روی سرور نصب نیست. لطفاً متن را مستقیماً کپی کنید.")
            
            elif file_extension in ['.docx', '.doc']:
                if DOCX_AVAILABLE:
                    doc = docx.Document(uploaded_file)
                    for para in doc.paragraphs:
                        text += para.text + "\n"
                else:
                    raise ImportError("کتابخانه `python-docx` روی سرور نصب نیست. لطفاً متن را مستقیماً کپی کنید.")
            
            elif file_extension == '.txt':
                text = uploaded_file.read().decode('utf-8', errors='ignore')
            
            else:
                text = "فرمت فایل پشتیبانی نمی‌شود."
        except Exception as e:
            text = f"خطا در خواندن فایل: {str(e)}"
            
        return text.strip()


class EthicsRiskAnalyzerEngine:
    """موتور تحلیل سناریو و فرآیندهای ارتباطی با مدل زبانی Ollama"""
    @staticmethod
    def query_ollama(url, model, prompt, system_prompt="") -> str:
        try:
            payload = {
                "model": model,
                "prompt": prompt,
                "system": system_prompt,
                "stream": False
            }
            # ۵ ثانیه کانکشن تایم‌اوت، بدون محدودیت زمانی برای پاسخ‌دهی (رعایت استانداردهای زمانی در مدل‌های محلی)
            response = requests.post(url, json=payload, timeout=(5, None))
            if response.status_code == 200:
                return response.json().get('response', '')
            else:
                return f"ERROR: HTTP {response.status_code}"
        except requests.exceptions.ConnectTimeout:
            return "ERROR_TIMEOUT"
        except requests.exceptions.ConnectionError:
            return "ERROR_CONNECTION"
        except Exception as e:
            return f"ERROR_UNKNOWN: {str(e)}"

    @classmethod
    def extract_ethical_risks(cls, url, model, proposal_text) -> list:
        """ارسال پروپوزال و استخراج ریسک‌های اخلاقی منطبق بر استانداردهای اخلاق زیست‌پزشکی"""
        system_prompt = (
            "شما یک ممیز ارشد اخلاق پزشکی و زیستی و متخصص ارزیابی ریسک در پروژه‌های بالینی هستید. "
            "وظیفه شما استخراج ریسک‌های کلیدی مرتبط با حریم خصوصی بیماران، رضایت آگاهانه، ایمنی داده‌ها، "
            "سوگیری در نمونه‌گیری، خطرات بیولوژیکی و مجوزهای کمیته اخلاق ملی و بین‌المللی است."
        )
        
        prompt = (
            "لطفاً متن پروپوزال تحقیق و توسعه زیر را بررسی کرده و حداکثر ۵ مورد از ریسک‌های اخلاقی و بالینی کلیدی آن را استخراج کنید. "
            "پاسخ شما باید ساختار یافته و صرفاً یک آرایه معتبر JSON به فرمت زیر باشد. از نوشتن هرگونه تحلیل اضافی، سلام، احوالپرسی یا مقدمه خودداری کنید:\n"
            "[\n"
            "  {\n"
            '    "risk": "عنوان خلاصه ریسک اخلاقی به فارسی (حداکثر ۱۰ کلمه)",\n'
            '    "description": "توضیح کوتاه علت بروز ریسک",\n'
            '    "S": عدد حدودی بین ۱ تا ۱۰ برای شدت اثر,\n'
            '    "O": عدد حدودی بین ۱ تا ۱۰ برای احتمال وقوع,\n'
            '    "D": عدد حدودی بین ۱ تا ۱۰ برای قابلیت عدم کشف\n'
            "  }\n"
            "]\n\n"
            f"متن پروپوزال جهت تحلیل:\n{proposal_text}"
        )
        
        raw_response = cls.query_ollama(url, model, prompt, system_prompt)
        
        if "ERROR" in raw_response:
            return [{"error_type": raw_response}]
            
        # تلاش برای استخراج آرایه JSON از میان پاسخ هوش مصنوعی
        try:
            # پاکسازی حاشیه‌های پاسخ
            json_match = re.search(r'\[\s*\{.*\}\s*\]', raw_response, re.DOTALL)
            if json_match:
                parsed_json = json.loads(json_match.group(0))
                return parsed_json
            else:
                # تلاش ثانویه جهت پارس مستقیم کل متن
                parsed_json = json.loads(raw_response.strip())
                return parsed_json
        except Exception:
            # روش جایگزین خط به خط در صورت خرابی کامل ساختار JSON
            extracted_lines = []
            for line in raw_response.split('\n'):
                clean_line = line.strip().lstrip("0123456789.-*• ")
                if clean_line and len(clean_line) > 10:
                    extracted_lines.append({
                        "risk": clean_line[:80],
                        "description": "استخراج شده با روش پارسر جایگزین به علت ناسازگاری فرمت JSON هوش مصنوعی.",
                        "S": 5, "O": 5, "D": 5
                    })
            return extracted_lines[:5]

    @classmethod
    def generate_mitigation_plan(cls, url, model, risk_title, s, o, d) -> str:
        """تولید برنامه کاهش ریسک اختصاصی برای شاخص‌های بحرانی"""
        rpn = s * o * d
        prompt = (
            "به عنوان ممیز ارشد اخلاق پزشکی و قوانین کارآزمایی بالینی، برای رفع ریسک زیر یک راهکار اصلاحی عملیاتی، "
            "دقیق و مبتنی بر استانداردهای مراجع نظارتی سلامت ارائه دهید. راهکار باید شامل حداکثر ۳ بند شفاف و کاربردی به زبان فارسی باشد.\n\n"
            f"عنوان ریسک اخلاقی: {risk_title}\n"
            f"پارامترهای ارزیابی: شدت اثر={s}، احتمال وقوع={o}، قابلیت عدم کشف={d} (نمره اولویت خطر RPN: {rpn})"
        )
        response = cls.query_ollama(url, model, prompt)
        if "ERROR" in response:
            return "برقراری ارتباط با مدل محلی با خطا مواجه شد. لطفاً راهکار را به صورت دستی یادداشت نمایید."
        return response.strip()

# ---------------------------------------------------------
# ۳. توابع کمکی مدیریت فایل‌های داده (JSON Storage)
# ---------------------------------------------------------
def load_reference_risks():
    if os.path.exists(RISKS_FILE):
        try:
            with open(RISKS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f).get('medical_risks', [])
        except Exception:
            pass
    # ریسک‌های مرجع پیش‌فرض حوزه‌ی اخلاق زیست‌پزشکی و بالینی
    default_risks = [
        "نقص در حفاظت از داده‌ها و حریم خصوصی اطلاعات حساس بیماران",
        "تأخیر در اخذ تاییدیه پروتکل کارآزمایی از کمیته اخلاق ملی",
        "عدم دریافت رضایت‌نامه آگاهانه کتبی و معتبر از بیماران هدف",
        "سوگیری سیستماتیک در غربالگری و انتخاب جامعه نمونه (Selection Bias)",
        "عدم نظارت بر عوارض ناخواسته شدید بالینی (Adverse Events Monitoring)",
        "تضاد منافع مالی یا علمی ذینفعان و پزشکان مجری طرح در نتایج تجربی",
        "عدم تدوین فرآیند خروج امن و داوطلبانه بیماران از مطالعه بالینی",
        "ذخیره‌سازی غیرایمن نمونه‌های بیولوژیکی و ژنتیکی در آزمایشگاه‌های همکار"
    ]
    save_reference_risks(default_risks)
    return default_risks

def save_reference_risks(risk_list):
    with open(RISKS_FILE, 'w', encoding='utf-8') as f:
        json.dump({"medical_risks": risk_list}, f, ensure_ascii=False, indent=4)

def load_assessments():
    if os.path.exists(ASSESSMENTS_FILE):
        try:
            with open(ASSESSMENTS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    initial_data = [
        {"Risk": "عدم دریافت رضایت‌نامه آگاهانه کتبی و معتبر از بیماران هدف", "S": 9, "O": 4, "D": 5, "RPN": 180, "Mitigation": "تهیه فرم رضایت‌نامه دو زبانه تایید شده توسط ناظر اخلاقی و ارایه نسخه فیزیکی و شفاهی به بیماران."},
        {"Risk": "تأخیر در اخذ تاییدیه پروتکل کارآزمایی از کمیته اخلاق ملی", "S": 8, "O": 6, "D": 3, "RPN": 144, "Mitigation": "ارسال موازی پرونده به دبیرخانه کمیته و رفع ابهامات اولیه در پیش‌نویس اول پژوهش."},
        {"Risk": "نقص در حفاظت از داده‌ها و حریم خصوصی اطلاعات حساس بیماران", "S": 10, "O": 2, "D": 4, "RPN": 80, "Mitigation": "رمزنگاری دیتابیس با کلیدهای نامتقارن و بی‌نام‌سازی کامل هویت بیماران قبل از تحلیل داده."}
    ]
    save_assessments(initial_data)
    return initial_data

def save_assessments(assessments):
    with open(ASSESSMENTS_FILE, 'w', encoding='utf-8') as f:
        json.dump(assessments, f, ensure_ascii=False, indent=4)

# ---------------------------------------------------------
# ۴. مدیریت پایدار وضعیت برنامه (Streamlit Session State)
# ---------------------------------------------------------
if 'ollama_url' not in st.session_state:
    st.session_state.ollama_url = "http://localhost:11434/api/generate"
if 'ollama_model' not in st.session_state:
    st.session_state.ollama_model = "llama3"
if 'mitigation_text' not in st.session_state:
    st.session_state.mitigation_text = ""
if 'assessments' not in st.session_state:
    st.session_state.assessments = load_assessments()
if 'extracted_risks_buffer' not in st.session_state:
    st.session_state.extracted_risks_buffer = []

# حد آستانه بحرانی بودن ریسک (Critical Threshold) بر اساس منطق FMEA
CRITICAL_RPN_THRESHOLD = 120

# تابع استایل‌دهی شرطی ردیف‌های جدول - اصلاح‌شده جهت رفع باگ KeyError RPN
def highlight_rpn(row):
    # بررسی هر دو کلید خام و تغییرنام‌یافته برای امنیت ۱۰۰ درصدی عملکرد
    rpn = row.get('RPN')
    if rpn is None:
         rpn = row.get('امتیاز نهایی RPN', 0)
         
    if rpn >= 150:
        # قرمز ملایم برای سطح ریسک بحرانی
        bg_color = '#fee2e2'
        text_color = '#991b1b'
    elif rpn >= 100:
        # زرد ملایم برای ریسک متوسط رو به بالا
        bg_color = '#fef9c3'
        text_color = '#854d0e'
    else:
        # سبز ملایم برای ریسک ایمن و کنترل‌شده
        bg_color = '#dcfce7'
        text_color = '#166534'
    return [f'background-color: {bg_color}; color: {text_color}; font-weight: bold; font-family: Tahoma;'] * len(row)

# ---------------------------------------------------------
# ۵. طراحی رابط کاربری تعاملی (Presentation Layer)
# ---------------------------------------------------------

# دایرکشن کلی صفحه به صورت راست به چپ
st.markdown("""
    <style>
        .reportview-container {
            direction: rtl;
            text-align: right;
        }
        div[class*="stTextArea"] textarea {
            direction: rtl;
            text-align: right;
        }
        div[class*="stTextInput"] input {
            direction: rtl;
            text-align: right;
        }
    </style>
""", unsafe_allow_html=True)

# هدر اصلی سامانه
st.markdown("""
    <div style="text-align: right; direction: rtl; background-color: #1e293b; padding: 25px; border-radius: 12px; margin-bottom: 20px; border-right: 8px solid #0284c7;">
        <h1 style="color: #f8fafc; font-size: 2rem; margin: 0;">🛡️ سامانه جامع تحلیل و مدیریت هوشمند ریسک‌های اخلاق پزشکی</h1>
        <p style="font-size: 1.1rem; color: #cbd5e1; margin-top: 10px; margin-bottom: 0;">
            ارزیابی استاندارد FMEA به همراه پردازش معنایی اسناد پروپوزال و پشتیبانی از مدل‌های هوش مصنوعی آفلاین (Ollama)
        </p>
    </div>
""", unsafe_allow_html=True)

# تعریف تب‌های برنامه
tab_extract, tab_evaluate, tab_dashboard, tab_settings = st.tabs([
    "📥 ۱. تحلیل و استخراج از پروپوزال",
    "📋 ۲. ممیزی و ثبت چرخه ریسک",
    "📊 ۳. داشبورد تحلیلی و ماتریس ریسک",
    "⚙️ ۴. تنظیمات زیرساخت هوش مصنوعی"
])

# ---------------------------------------------------------
# تب اول: بارگذاری سند و استخراج خودکار
# ---------------------------------------------------------
with tab_extract:
    st.markdown("""
        <div style="text-align: right; direction: rtl;">
            <h3>📂 استخراج خودکار ریسک‌های اخلاقی و قوانین کارآزمایی بالینی</h3>
            <p style="color: #64748b;">فایل پروپوزال علمی یا سند فرضیات فنی پروژه را بارگذاری کنید. هسته هوش مصنوعی با تحلیل مفاهیم به صورت خودکار کاندیداهای ریسک را استخراج می‌کند.</p>
        </div>
    """, unsafe_allow_html=True)
    
    col_upload, col_preview = st.columns([1, 1])
    
    with col_upload:
        # اعلان وضعیت کتابخانه‌ها
        lib_messages = []
        if not PYPDF_AVAILABLE:
            lib_messages.append("⚠️ کتابخانه خوانش PDF (`pypdf`) نصب نیست.")
        if not DOCX_AVAILABLE:
            lib_messages.append("⚠️ کتابخانه خوانش Word (`python-docx`) نصب نیست.")
            
        if lib_messages:
            with st.expander("🛠️ راهنمای وابستگی‌های پردازش فایل", expanded=False):
                st.info("برای فعال‌سازی کامل بارگذاری مستقیم اسناد، دستورات زیر را در محیط ترمینال خود اجرا کنید:")
                st.code("pip install pypdf python-docx")
                for msg in lib_messages:
                    st.warning(msg)
                    
        uploaded_file = st.file_uploader(
            "آپلود سند پروپوزال (پشتیبانی از PDF, DOCX, TXT):", 
            type=["pdf", "docx", "txt"],
            key="proposal_file_uploader"
        )
        
        # گزینه ورودی متنی جایگزین
        st.markdown("<p style='text-align: right; font-weight: bold; margin-top:15px;'>یا متن پروپوزال را مستقیماً در کادر زیر وارد کنید:</p>", unsafe_allow_html=True)
        fallback_text = st.text_area("متن دستی پروپوزال تحقیق و توسعه پزشکی:", height=180, key="manual_text_area")
        
        # تعیین منبع متن نهایی جهت تحلیل
        final_text_to_analyze = ""
        if uploaded_file is not None:
            final_text_to_analyze = DocumentProcessor.extract_text(uploaded_file)
            st.success(f"فایل «{uploaded_file.name}» با موفقیت لود و پردازش شد.")
        else:
            final_text_to_analyze = fallback_text

    with col_preview:
        st.markdown("<p style='text-align: right; font-weight: bold;'>🔍 پیش‌نمایش متن استخراج‌شده جهت ممیزی:</p>", unsafe_allow_html=True)
        if final_text_to_analyze:
            st.text_area("محتوای متنی اسکن شده:", value=final_text_to_analyze[:1500] + ("\n... [ادامه متن]" if len(final_text_to_analyze) > 1500 else ""), height=220, disabled=True)
        else:
            st.info("سندی بارگذاری نشده است. شما می‌توانید از فیلد متنی یا آپلودر فایل استفاده کنید.")
            
        analyze_btn = st.button("🧠 استخراج هوشمند ریسک‌های اخلاقی با Ollama", use_container_width=True, type="primary")
        
        if analyze_btn:
            if final_text_to_analyze.strip():
                with st.spinner("هوش مصنوعی محلی در حال استخراج و ارزش‌گذاری اولیه ریسک‌های اخلاقی است..."):
                    results = EthicsRiskAnalyzerEngine.extract_ethical_risks(
                        st.session_state.ollama_url, 
                        st.session_state.ollama_model, 
                        final_text_to_analyze
                    )
                    
                    if results and "error_type" in results[0]:
                        err = results[0]["error_type"]
                        if err == "ERROR_CONNECTION":
                            st.error("❌ عدم اتصال به Ollama: مطمئن شوید نرم‌افزار Ollama روی سیستم شما در حال اجراست و پورت ۱۱۴۳۴ باز است.")
                        elif err == "ERROR_TIMEOUT":
                            st.error("❌ خطای اتصال به Ollama: زمان انتظار برای اتصال به سرور به پایان رسید.")
                        else:
                            st.error(f"خطای نامشخص در ارتباط با موتور هوش مصنوعی: {err}")
                    elif results:
                        st.session_state.extracted_risks_buffer = results
                        st.success(f"تعداد {len(results)} ریسک اخلاقی جدید با موفقیت کشف و در حافظه موقت لود شد.")
            else:
                st.warning("لطفاً ابتدا متنی را بنویسید یا فایلی را بارگذاری کنید.")

    # نمایش نتایج استخراج موقت جهت انتقال به جدول ممیزی نهایی
    if st.session_state.extracted_risks_buffer:
        st.markdown("---")
        st.markdown("<h3 style='text-align: right; color:#0369a1;'>📋 ریسک‌های شناسایی‌شده موقت (آماده تایید و ثبت نهایی)</h3>", unsafe_allow_html=True)
        st.write("ریسک‌های زیر از پروپوزال شما استخراج شده‌اند. می‌توانید آن‌ها را بررسی کرده و با زدن دکمه تایید، به بانک اصلی پروژه منتقل کنید:")
        
        # قالب نمایش کارت‌های ریسک به صورت شبکه
        for idx, item in enumerate(st.session_state.extracted_risks_buffer):
            with st.container():
                col_info, col_act = st.columns([4, 1])
                with col_info:
                    st.markdown(f"""
                        <div style="background-color: #f8fafc; padding: 15px; border-radius: 8px; border-right: 4px solid #0284c7; text-align: right; direction: rtl; margin-bottom: 10px;">
                            <strong style="color: #0f172a; font-size: 1.1rem;">عنوان ریسک: {item.get('risk', 'بدون نام')}</strong><br/>
                            <span style="color: #475569; font-size: 0.9rem;">توضیحات پیشنهادی: {item.get('description', '')}</span><br/>
                            <span style="color: #0369a1; font-weight: bold; font-size: 0.85rem;">ارزش‌گذاری پیش‌فرض هوش مصنوعی: S: {item.get('S', 5)} | O: {item.get('O', 5)} | D: {item.get('D', 5)}</span>
                        </div>
                    """, unsafe_allow_html=True)
                with col_act:
                    if st.button(f"➕ تایید و انتقال این ریسک", key=f"add_buffer_{idx}", use_container_width=True):
                        # انتقال به پایگاه مرجع
                        current_ref = load_reference_risks()
                        r_title = item.get('risk', 'بدون نام')
                        if r_title not in current_ref:
                            current_ref.append(r_title)
                            save_reference_risks(current_ref)
                        
                        # ثبت مستقیم در جدول ارزیابی‌ها با امتیازات پیش‌فرض استخراج شده
                        new_assessment = {
                            "Risk": r_title,
                            "S": int(item.get('S', 5)),
                            "O": int(item.get('O', 5)),
                            "D": int(item.get('D', 5)),
                            "RPN": int(item.get('S', 5)) * int(item.get('O', 5)) * int(item.get('D', 5)),
                            "Mitigation": item.get('description', 'تولید شده به وسیله پردازش هوشمند سند.')
                        }
                        st.session_state.assessments.append(new_assessment)
                        save_assessments(st.session_state.assessments)
                        
                        # حذف از بافر موقت
                        st.session_state.extracted_risks_buffer.pop(idx)
                        st.toast("ریسک با موفقیت به چرخه ممیزی نهایی پروژه اضافه شد!", icon="✅")
                        st.rerun()
                        
        if st.button("🧹 پاکسازی بافر ریسک‌های پیشنهادی موقت", use_container_width=True, type="secondary"):
            st.session_state.extracted_risks_buffer = []
            st.rerun()

# ---------------------------------------------------------
# تب دوم: ارزیابی و ممیزی دستی (فلو FMEA)
# ---------------------------------------------------------
with tab_evaluate:
    col_form, col_table_view = st.columns([2, 3])
    
    with col_form:
        st.markdown("<div style='text-align: right;'><h3>📋 ثبت و ممیزی شاخص‌های ریسک (FMEA)</h3></div>", unsafe_allow_html=True)
        
        # بارگذاری لیست مرجع
        ref_risks = load_reference_risks()
        selected_risk = st.selectbox("عنوان ریسک اخلاقی را مشخص کنید:", ref_risks, index=0, key="assess_risk_selector")
        
        st.markdown("<p style='text-align: right; font-weight: bold; margin-bottom: 0;'>تعیین پارامترهای ممیزی استاندارد (امتیاز بین ۱ تا ۱۰):</p>", unsafe_allow_html=True)
        
        s = st.slider("۱. شدت اثر ریسک در صورت وقوع (Severity - S):", 1, 10, 5, help="۱ به معنی بی‌تاثیر و ۱۰ به معنی تخریب کامل پروژه یا نقض جدی حقوق بیماران است.")
        o = st.slider("۲. احتمال رخداد و وقوع ریسک (Occurrence - O):", 1, 10, 4, help="۱ به معنی احتمال نزدیک به صفر و ۱۰ به معنی رخداد حتمی و مکرر است.")
        d = st.slider("۳. قابلیت شناسایی و عدم کشف (Detection - D):", 1, 10, 3, help="۱ به معنی کشف آنی و تضمینی ریسک و ۱۰ به معنی غیرقابل کشف بودن تا زمان بحران است.")
        
        rpn_calc = s * o * d
        
        # نمایش شاخص اولویت خطر و ارزیابی آستانه
        is_critical = rpn_calc >= CRITICAL_RPN_THRESHOLD
        
        bg_status = "#fef2f2" if is_critical else "#f0fdf4"
        border_status = "#ef4444" if is_critical else "#22c55e"
        text_status = "#991b1b" if is_critical else "#166534"
        
        st.markdown(f"""
            <div style="background-color: {bg_status}; padding: 15px; border: 1.5px solid {border_status}; border-radius: 8px; text-align: center; margin-bottom: 15px; direction: rtl;">
                <span style="font-size: 1.1rem; font-weight: bold; color: #1e293b;">شاخص اولویت خطر محاسبه شده (RPN):</span>
                <span style="font-size: 1.8rem; color: {text_status}; font-weight: bold;"> {rpn_calc}</span>
                <br/>
                <span style="font-size: 0.9rem; color: #475569;">حداکثر نمره ممکن ۱۰۰۰ | حد آستانه بحرانی بودن سیستم: {CRITICAL_RPN_THRESHOLD}</span>
            </div>
        """, unsafe_allow_html=True)
        
        if is_critical:
            st.error(f"⚠️ هشدار ممیزی: مقدار RPN از مرز بحرانی ({CRITICAL_RPN_THRESHOLD}) عبور کرده است. ثبت سناریوی کاهش و تعدیل ریسک الزامیست.")
            mitigation_lbl = "برنامه تعدیل و کنترل ریسک اخلاقی (الزامی) *"
        else:
            mitigation_lbl = "اقدام پیشگیرانه / برنامه کنترل ریسک (اختیاری):"
            
        mitigation_strategy = st.text_area(
            mitigation_lbl,
            value=st.session_state.mitigation_text,
            placeholder="برنامه تفصیلی خود برای پاسخ به این تهدید را بنویسید یا از دکمه هوشمند زیر استفاده کنید...",
            key="mitigation_text_input"
        )
        
        # ایجاد سناریوی هوش مصنوعی
        if st.button("🪄 تدوین هوشمند راهکار کنترل با Ollama", use_container_width=True):
            with st.spinner("در حال تحلیل استانداردهای اخلاقی و دریافت راهکارهای پیشگیرانه..."):
                generated_mitigation = EthicsRiskAnalyzerEngine.generate_mitigation_plan(
                    st.session_state.ollama_url,
                    st.session_state.ollama_model,
                    selected_risk, s, o, d
                )
                st.session_state.mitigation_text = generated_mitigation
                st.rerun()

        st.markdown("---")
        
        if st.button("💾 ثبت نهایی ارزیابی در ماتریس کنترل پروژه", use_container_width=True, type="primary"):
            final_mitigation = st.session_state.mitigation_text if st.session_state.mitigation_text else mitigation_strategy
            
            if is_critical and not final_mitigation.strip():
                st.error("❌ خطا در ثبت: به علت بحرانی بودن میزان ریسک، نگارش برنامه کاهش خطر اجباری است.")
            else:
                # حذف ارزیابی تکراری قبلی از همان عنوان در صورت وجود، برای جلوگیری از انباشت داده‌های منقضی
                updated_list = [item for item in st.session_state.assessments if item['Risk'] != selected_risk]
                
                new_assessment = {
                    "Risk": selected_risk,
                    "S": s,
                    "O": o,
                    "D": d,
                    "RPN": rpn_calc,
                    "Mitigation": final_mitigation.strip() if final_mitigation.strip() else "مکانیزم نظارتی خاصی اعمال نگردیده است."
                }
                updated_list.append(new_assessment)
                st.session_state.assessments = updated_list
                save_assessments(updated_list)
                
                # ریست متغیر اقدام اصلاحی
                st.session_state.mitigation_text = ""
                st.toast("ممیزی با موفقیت در مخزن پروژه به‌روزرسانی و ثبت شد!", icon="✅")
                st.rerun()

    with col_table_view:
        st.markdown("<div style='text-align: right;'><h3>🔍 لیست ریسک‌های فعال پروژه</h3></div>", unsafe_allow_html=True)
        
        if st.session_state.assessments:
            df = pd.DataFrame(st.session_state.assessments)
            df_sorted = df.sort_values(by="RPN", ascending=False).reset_index(drop=True)
            
            # تغییر نام هدرها برای نمایش کاربرپسندتر در جدول
            df_display = df_sorted.rename(columns={
                "Risk": "عنوان ریسک تحت مانیتور",
                "S": "شدت (S)",
                "O": "وقوع (O)",
                "D": "عدم‌کشف (D)",
                "RPN": "امتیاز نهایی RPN",
                "Mitigation": "برنامه مصوب اقدام اصلاحی و تعدیل"
            })
            
            # اعمال استایل پس‌زمینه رنگی بدون تداخل با نام جدید ستون RPN
            styled_df = df_display.style.apply(highlight_rpn, axis=1)
            st.dataframe(styled_df, use_container_width=True)
            
            # بخش حذف دستی رکوردها
            st.markdown("---")
            st.markdown("<p style='text-align: right; font-weight: bold;'>🗑️ حذف موارد ارزیابی شده:</p>", unsafe_allow_html=True)
            delete_option = st.selectbox("انتخاب ریسک ارزیابی‌شده جهت حذف دائمی از لیست:", df_sorted['Risk'].tolist(), key="delete_assess_selectbox")
            if st.button("❌ حذف فیزیکی ردیف ارزیابی", type="secondary", use_container_width=True):
                updated_assess = [item for item in st.session_state.assessments if item['Risk'] != delete_option]
                st.session_state.assessments = updated_assess
                save_assessments(updated_assess)
                st.toast("ردیف مد نظر از جدول ارزیابی حذف شد.", icon="🗑️")
                st.rerun()
                
            # دانلود گزارش تفصیلی ارزیابی
            csv_data = df_sorted.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 دانلود کامل گزارش ممیزی ریسک‌های اخلاقی (CSV)",
                data=csv_data,
                file_name="Ethics_FMEA_Report.csv",
                mime="text/csv",
                use_container_width=True
            )
        else:
            st.info("هیچ ریسک اخلاقی ارزیابی‌شده‌ای ثبت نشده است. لطفاً از فرم سمت راست جهت ارزیابی استفاده کنید.")

# ---------------------------------------------------------
# تب سوم: داشبورد تحلیلی و مصورسازی ماتریس ریسک
# ---------------------------------------------------------
with tab_dashboard:
    st.markdown("<div style='text-align: right;'><h3>📊 داشبورد آماری و تحلیل‌های کیفی EthicsRiskAnalyzer</h3></div>", unsafe_allow_html=True)
    
    if st.session_state.assessments:
        df_dash = pd.DataFrame(st.session_state.assessments)
        
        # ۱. ویجت‌های بالا دستی KPI
        tot_risks = len(df_dash)
        mean_rpn = int(df_dash['RPN'].mean())
        high_risk_count = len(df_dash[df_dash['RPN'] >= CRITICAL_RPN_THRESHOLD])
        
        col_kpi1, col_kpi2, col_kpi3 = st.columns(3)
        with col_kpi1:
            st.metric(label="مجموع ریسک‌های تحت پایش", value=tot_risks)
        with col_kpi2:
            st.metric(label="میانگین نمره اولویت خطر (RPN)", value=mean_rpn)
        with col_kpi3:
            st.metric(label="تعداد وضعیت بحرانی (RPN ≥ 120)", value=high_risk_count, delta="نیاز به اقدام اصلاحی فوری" if high_risk_count > 0 else "وضعیت متعادل")
            
        st.markdown("---")
        
        # نمودارها در دو ستون
        col_chart1, col_chart2 = st.columns(2)
        
        with col_chart1:
            st.markdown("<p style='text-align: right; font-weight: bold;'>🔥 ماتریس حرارتی چگالی ریسک‌ها (اثر - وقوع):</p>", unsafe_allow_html=True)
            # ایجاد یک چگالی دو بعدی برای شدت اثر و وقوع
            fig_heatmap = px.density_heatmap(
                df_dash,
                x="O",
                y="S",
                z="RPN",
                histfunc="avg",
                nbinsx=10,
                nbinsy=10,
                color_continuous_scale="Reds",
                labels={"O": "احتمال وقوع (O)", "S": "شدت اثر (S)", "RPN": "میانگین RPN"},
                range_x=[1, 10],
                range_y=[1, 10],
                title="موقعیت تراکم و ثقل ریسک بر روی نقشه خطر"
            )
            fig_heatmap.update_layout(
                xaxis=dict(tickmode='linear', tick0=1, dtick=1),
                yaxis=dict(tickmode='linear', tick0=1, dtick=1),
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)'
            )
            st.plotly_chart(fig_heatmap, use_container_width=True)
            
        with col_chart2:
            st.markdown("<p style='text-align: right; font-weight: bold;'>🕸️ نمودار راداری ابعاد ریسک‌های اخلاقی (تک‌متغیره):</p>", unsafe_allow_html=True)
            
            # انتخاب ریسک برای نمودار راداری
            radar_risk_selected = st.selectbox(
                "یک ریسک را جهت تحلیل ابعادی انتخاب کنید:",
                df_dash['Risk'].tolist(),
                key="radar_risk_select"
            )
            
            risk_data = df_dash[df_dash['Risk'] == radar_risk_selected].iloc[0]
            
            # مقادیر چارت رادار
            categories = ['شدت اثر (S)', 'احتمال وقوع (O)', 'قابلیت عدم کشف (D)']
            values = [risk_data['S'], risk_data['O'], risk_data['D']]
            
            fig_radar = go.Figure()
            fig_radar.add_trace(go.Scatterpolar(
                r=values + [values[0]], # برای بستن چندضلعی
                theta=categories + [categories[0]],
                fill='toself',
                fillcolor='rgba(2, 132, 199, 0.3)',
                line=dict(color='#0284c7', width=2),
                name=radar_risk_selected
            ))
            
            fig_radar.update_layout(
                polar=dict(
                    radialaxis=dict(
                        visible=True,
                        range=[0, 10]
                    )
                ),
                showlegend=False,
                title=f"رادار مشخصات فنی ممیزی ریسک",
                paper_bgcolor='rgba(0,0,0,0)'
            )
            st.plotly_chart(fig_radar, use_container_width=True)
            
        # بخش دوم نمودارها در یک ردیف عریض‌تر
        st.markdown("---")
        st.markdown("<p style='text-align: right; font-weight: bold;'>📊 مقایسه کلی اولویت ریسک‌ها در یک نگاه:</p>", unsafe_allow_html=True)
        fig_bar = px.bar(
            df_dash,
            x="Risk",
            y="RPN",
            color="RPN",
            color_continuous_scale=["#16a34a", "#ca8a04", "#dc2626"],
            labels={"Risk": "عنوان ریسک", "RPN": "شاخص نهایی RPN"},
            title="نمودار ستونی اولویت‌بندی کلی ریسک‌های ارزیابی‌شده"
        )
        fig_bar.update_layout(xaxis_tickangle=-15, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
        st.plotly_chart(fig_bar, use_container_width=True)
        
    else:
        st.info("داده‌ای جهت فرآیند مصورسازی یافت نشد. لطفاً ابتدا در تب دوم، ریسک‌ها را ارزیابی و ثبت کنید.")

# ---------------------------------------------------------
# تب چهارم: پیکربندی و مدیریت زیرساخت پایگاه داده و AI
# ---------------------------------------------------------
with tab_settings:
    st.markdown("<div style='text-align: right;'><h3>⚙️ پیکربندی سرویس Ollama و بانک واژگان مرجع</h3></div>", unsafe_allow_html=True)
    
    col_ai_setup, col_db_setup = st.columns(2)
    
    with col_ai_setup:
        st.markdown("<p style='text-align: right; font-weight: bold;'>🤖 اتصال به موتور هوش مصنوعی محلی (Ollama API):</p>", unsafe_allow_html=True)
        api_url = st.text_input("آدرس API محلی (آدرس پیش‌فرض ۱۱۴۳۴ سیستم محلی):", value=st.session_state.ollama_url)
        model_name = st.text_input("نام مدل لود شده روی Ollama (مثال: llama3, mistral, gemma):", value=st.session_state.ollama_model)
        
        if st.button("🔧 ذخیره و تست اتصال سرویس هوش مصنوعی", use_container_width=True):
            st.session_state.ollama_url = api_url
            st.session_state.ollama_model = model_name
            
            # ارسال یک درخواست پینگ سبک برای تست
            with st.spinner("در حال تست ارتباط با Ollama..."):
                test_prompt = "Say only 'OK'"
                res = EthicsRiskAnalyzerEngine.query_ollama(api_url, model_name, test_prompt)
                if "ERROR" in res:
                    st.error(f"❌ برقراری ارتباط ناموفق بود. خطا: {res}")
                else:
                    st.success("✔️ اتصال به موتور Ollama با موفقیت تایید شد.")
                    
    with col_db_setup:
        st.markdown("<p style='text-align: right; font-weight: bold;'>📝 مدیریت واژگان مرجع ریسک در پایگاه داده:</p>", unsafe_allow_html=True)
        current_ref_list = load_reference_risks()
        
        # افزودن دستی ریسک مرجع جدید
        new_ref_title = st.text_input("عنوان ریسک اخلاقی جدید جهت ثبت دستی در پایگاه:")
        if st.button("➕ ذخیره در پایگاه داده مرجع", use_container_width=True):
            if new_ref_title and new_ref_title not in current_ref_list:
                current_ref_list.append(new_ref_title)
                save_reference_risks(current_ref_list)
                st.success("عنوان ریسک جدید با موفقیت به بانک مرجع افزوده شد.")
                st.rerun()
                
        # حذف ریسک از بانک اطلاعاتی مرجع
        risk_to_del = st.selectbox("یک عنوان ریسک را جهت حذف دائم از پایگاه انتخاب کنید:", current_ref_list, key="delete_ref_select")
        if st.button("🗑️ حذف فیزیکی از پایگاه", use_container_width=True, type="secondary"):
            if risk_to_del in current_ref_list:
                current_ref_list.remove(risk_to_del)
                save_reference_risks(current_ref_list)
                st.toast("ریسک با موفقیت از مرجع سیستم حذف شد.", icon="🗑️")
                st.rerun()

    st.markdown("---")
    with st.expander("👀 نمایش خام پایگاه داده مرجع (risks.json) جهت عیب‌یابی ممیزی"):
        st.json({"medical_risks": current_ref_list})