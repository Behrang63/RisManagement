import streamlit as st
import pandas as pd
import json
import os
import requests
import plotly.express as px

# تنظیمات هدر و چیدمان صفحه
st.set_page_config(
    page_title="سامانه مدیریت ریسک R&D پزشکی و هوشمند",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# مسیر فایل‌های ذخیره‌سازی
RISKS_FILE = 'risks.json'
ASSESSMENTS_FILE = 'assessments.json'

# مقداردهی اولیه متغیرهای ارتباطی Ollama در Session State
if 'ollama_url' not in st.session_state:
    st.session_state.ollama_url = "http://localhost:11434/api/generate"
if 'ollama_model' not in st.session_state:
    st.session_state.ollama_model = "llama3"
if 'mitigation_text' not in st.session_state:
    st.session_state.mitigation_text = ""

# ۱. توابع ارتباطی با هوش مصنوعی Ollama
def query_ollama(prompt, system_prompt=""):
    """ارسال درخواست به سرویس محلی Ollama بدون محدودیت زمانی در تولید و دریافت پاسخ"""
    try:
        payload = {
            "model": st.session_state.ollama_model,
            "prompt": prompt,
            "system": system_prompt,
            "stream": False
        }
        # تفکیک تایم‌اوت: ۵ ثانیه برای اتصال اولیه و بدون محدودیت زمانی (None) برای خواندن و تولید پاسخ
        timeout_config = (5, None)
        
        response = requests.post(st.session_state.ollama_url, json=payload, timeout=timeout_config)
        
        if response.status_code == 200:
            return response.json().get('response', '')
        else:
            st.error(f"خطای سرور Ollama: کد وضعیت {response.status_code}")
            
    except requests.exceptions.ConnectTimeout:
        st.error("❌ خطای اتصال به Ollama: زمان انتظار برای اتصال به سرور به پایان رسید. مطمئن شوید سرویس فعال است.")
    except requests.exceptions.ConnectionError:
        st.error("❌ عدم اتصال به Ollama: مطمئن شوید نرم‌افزار Ollama روی سیستم شما در حال اجراست و پورت ۱۱۴۳۴ باز است.")
    except Exception as e:
        st.error(f"خطای غیرمنتظره در ارتباط با هوش مصنوعی: {e}")
    return None

# ۲. توابع مدیریت فایل‌های JSON
def load_reference_risks():
    """بارگذاری لیست ریسک‌های مرجع از فایل JSON"""
    if os.path.exists(RISKS_FILE):
        try:
            with open(RISKS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f).get('medical_risks', [])
        except Exception:
            pass
    default_risks = [
        "تأخیر در اخذ مجوز کمیته اخلاق",
        "نقص در حفاظت از داده‌ها و حریم خصوصی بیماران",
        "آلودگی، تخریب یا فساد نمونه‌های زیستی در آزمایشگاه",
        "خرابی یا کالیبره نبودن تجهیزات حساس آزمایشگاهی",
        "سوگیری در غربالگری و انتخاب نمونه‌های بالینی (Selection Bias)",
        "عدم تکرارپذیری نتایج تجربی (Reproducibility Crisis)",
        "فرسایش یا خروج نخبگان و نیروی انسانی کلیدی از پروژه",
        "تأخیر در زنجیره تأمین کیت‌ها، معرف‌ها و تجهیزات وارداتی"
    ]
    save_reference_risks(default_risks)
    return default_risks

def save_reference_risks(risk_list):
    """ذخیره لیست مرجع در فایل JSON"""
    with open(RISKS_FILE, 'w', encoding='utf-8') as f:
        json.dump({"medical_risks": risk_list}, f, ensure_ascii=False, indent=4)

def load_assessments():
    """بارگذاری ارزیابی‌های ثبت‌شده"""
    if os.path.exists(ASSESSMENTS_FILE):
        try:
            with open(ASSESSMENTS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    initial_data = [
        {"Risk": "تأخیر در اخذ مجوز کمیته اخلاق", "S": 8, "O": 6, "D": 5, "RPN": 240, "Mitigation": "رایزنی زودهنگام با اعضای کمیته و پیش‌نویس دقیق پروپوزال"},
        {"Risk": "خرابی یا کالیبره نبودن تجهیزات حساس آزمایشگاهی", "S": 7, "O": 4, "D": 4, "RPN": 112, "Mitigation": "قرارداد پشتیبانی فنی و کالیبراسیون دوره‌ای ۶ ماهه"},
        {"Risk": "آلودگی، تخریب یا فساد نمونه‌های زیستی در آزمایشگاه", "S": 9, "O": 2, "D": 3, "RPN": 54, "Mitigation": "نصب سیستم هشدار دمای یخچال‌ها و ژنراتور اضطراری"}
    ]
    save_assessments(initial_data)
    return initial_data

def save_assessments(assessments):
    """ذخیره ارزیابی‌ها در فایل JSON"""
    with open(ASSESSMENTS_FILE, 'w', encoding='utf-8') as f:
        json.dump(assessments, f, ensure_ascii=False, indent=4)

# بارگذاری داده‌های اولیه
if 'assessments' not in st.session_state:
    st.session_state.assessments = load_assessments()

# ۳. تابع کمکی برای استایل‌دهی شرطی جدول
def highlight_rpn(row):
    rpn = row['RPN']
    if rpn >= 200:
        color = '#f8d7da'  # قرمز ملایم
        text_color = '#721c24'
    elif rpn >= 100:
        color = '#fff3cd'  # زرد ملایم
        text_color = '#856404'
    else:
        color = '#d4edda'  # سبز ملایم
        text_color = '#155724'
    return [f'background-color: {color}; color: {text_color}; font-weight: bold;'] * len(row)

# --- بدنه اصلی نرم‌افزار ---

st.markdown("""
    <div style="text-align: right; direction: rtl;">
        <h1 style="color: #1E3A8A;">سامانه ارزیابی و مدیریت هوشمند ریسک R&D</h1>
        <p style="font-size: 1.1rem; color: #4B5563;">یکپارچه‌سازی فرآیندهای تحلیل ریسک FMEA با قوای تحلیلی هوش مصنوعی آفلاین (Ollama)</p>
    </div>
    <hr>
""", unsafe_allow_html=True)

# تقسیم‌بندی برنامه به ۳ بخش مجزا (Tabs)
tab_assess, tab_dashboard, tab_settings = st.tabs([
    "📋 ثبت و ارزیابی ریسک‌ها",
    "📊 داشبورد تحلیلی و نمودارها",
    "⚙️ تنظیمات سیستم و منبع داده"
])

# ---------------------------------------------------------
# تب ۱: ارزیابی و ثبت ریسک
# ---------------------------------------------------------
with tab_assess:
    col_input, col_table = st.columns([1, 2])
    
    with col_input:
        st.markdown("<div style='text-align: right;'><h3>ورودی اطلاعات FMEA</h3></div>", unsafe_allow_html=True)
        
        # بخش هوشمند: استخراج ریسک‌ها از متن پروپوزال
        with st.expander("📝 استخراج هوشمند ریسک از پروپوزال با هوش مصنوعی"):
            st.markdown("<p style='text-align: right; font-size: 0.9rem;'>متن پروپوزال یا فرضیات فنی پروژه را در کادر زیر وارد کنید تا هوش مصنوعی ریسک‌های منطبق بر آن را برای شما استخراج کند.</p>", unsafe_allow_html=True)
            proposal_text = st.text_area("خلاصه یا متن پروپوزال تحقیق و توسعه:", height=120)
            if st.button("🔍 تحلیل و استخراج خودکار ریسک‌ها", use_container_width=True):
                if proposal_text.strip():
                    prompt = (
                        "شما یک دستیار حرفه‌ای مدیریت ریسک در پروژه‌های تحقیقاتی و بالینی هستید. "
                        f"لطفاً متن پروپوزال زیر را بخوانید و حداکثر ۵ مورد از ریسک‌های کلیدی (فنی، اخلاقی، عملیاتی یا کیفی) آن را استخراج کنید. "
                        "پاسخ باید دقیق، به زبان فارسی و خلاصه باشد. هر ریسک را فقط در یک خط جداگانه بدون شماره، بالت یا کاراکتر اضافی قرار دهید.\n\n"
                        f"متن پروپوزال:\n{proposal_text}"
                    )
                    with st.spinner("هوش مصنوعی در حال بررسی علمی پروپوزال شما..."):
                        extracted_response = query_ollama(prompt)
                        if extracted_response:
                            raw_lines = extracted_response.split("\n")
                            clean_risks = []
                            for line in raw_lines:
                                clean_line = line.strip().lstrip("0123456789.-*• ")
                                if clean_line and len(clean_line) > 5:
                                    clean_risks.append(clean_line)
                            
                            if clean_risks:
                                current_list = load_reference_risks()
                                added_count = 0
                                for risk in clean_risks:
                                    if risk not in current_list:
                                        current_list.append(risk)
                                        added_count += 1
                                if added_count > 0:
                                    save_reference_risks(current_list)
                                    st.success(f"موفقیت: تعداد {added_count} ریسک جدید شناسایی و به منبع فرآیند افزوده شد.")
                                    st.rerun()
                                else:
                                    st.info("ریسک‌های شناسایی‌شده از قبل در بانک اطلاعاتی موجود بودند.")
                else:
                    st.error("لطفاً ابتدا متنی را برای تحلیل وارد کنید.")

        st.markdown("---")
        
        # خواندن لیست ریسک‌ها از منبع JSON
        ref_risks = load_reference_risks()
        selected_risk = st.selectbox("عنوان ریسک را انتخاب کنید:", ref_risks, index=0)
        
        st.markdown("<p style='text-align: right; font-weight: bold;'>تعیین شاخص‌های سه‌گانه (۱ تا ۱۰):</p>", unsafe_allow_html=True)
        s = st.slider("شدت اثر (Severity - S):", 1, 10, 5)
        o = st.slider("احتمال وقوع (Occurrence - O):", 1, 10, 4)
        d = st.slider("قابلیت عدم کشف (Detection - D):", 1, 10, 3)
        
        # محاسبه اولویت ریسک (RPN)
        rpn_calc = s * o * d
        
        st.markdown(f"""
            <div style="background-color: #F3F4F6; padding: 10px; border-radius: 5px; text-align: center; margin-bottom: 15px;">
                <span style="font-size: 1.1rem; font-weight: bold;">شاخص اولویت خطر (RPN):</span>
                <span style="font-size: 1.5rem; color: #1E3A8A; font-weight: bold;"> {rpn_calc}</span>
            </div>
        """, unsafe_allow_html=True)
        
        RPN_THRESHOLD = 100
        requires_mitigation = rpn_calc >= RPN_THRESHOLD
        
        if requires_mitigation:
            st.warning(f"⚠️ توجه: شاخص RPN بزرگتر یا مساوی {RPN_THRESHOLD} است. ارائه‌ی استراتژی اصلاحی الزامیست.")
            mitigation_label = "اقدام اصلاحی / استراتژی کاهش ریسک (الزامی) *"
        else:
            mitigation_label = "اقدام اصلاحی / استراتژی کاهش ریسک (اختیاری):"

        # ورودی متن اقدام اصلاحی با متغیر اختصاصی از Session State
        mitigation = st.text_area(
            mitigation_label,
            value=st.session_state.mitigation_text,
            placeholder="برنامه تفصیلی خود برای پاسخ به این تهدید را بنویسید یا از دکمه جادویی هوش مصنوعی زیر استفاده کنید...",
            key="mitigation_text_area"
        )
        
        # دکمه جادویی هوش مصنوعی
        if st.button("🪄 پیشنهاد استراتژی هوشمند با Ollama", use_container_width=True):
            prompt = (
                "شما یک ممیز مدیریت ریسک و متخصص فرآیندهای تحقیق و توسعه (R&D) هستید. "
                "برای ریسک مشخص‌شده زیر، یک اقدام اصلاحی دقیق، کاربردی و گام‌به‌گام ارائه کنید تا این ریسک خنثی یا تعدیل شود. "
                "پاسخ باید تخصصی، منطبق بر صنعت زیست‌پزشکی و کوتاه (حداکثر در ۳ بند مشخص) باشد. لطفاً فقط پاسخ نهایی را به زبان فارسی ارائه دهید.\n\n"
                f"عنوان ریسک: {selected_risk}\n"
                f"شاخص‌های عددی: شدت {s}، احتمال {o}، قابلیت عدم کشف {d} (شاخص RPN نهایی: {rpn_calc})"
            )
            with st.spinner("هوش مصنوعی در حال تدوین سناریوی تعدیل ریسک..."):
                response_strategy = query_ollama(prompt)
                if response_strategy:
                    st.session_state.mitigation_text = response_strategy.strip()
                    st.rerun()

        st.markdown("---")
        
        if st.button("💾 ثبت نهایی ارزیابی در جدول", use_container_width=True, type="primary"):
            actual_mitigation = st.session_state.mitigation_text if st.session_state.mitigation_text else mitigation
            
            if requires_mitigation and not actual_mitigation.strip():
                st.error("❌ خطا در ثبت: شاخص RPN این ریسک بالاست و پر کردن بخش اقدام اصلاحی اجباری است.")
            else:
                new_assessment = {
                    "Risk": selected_risk,
                    "S": s,
                    "O": o,
                    "D": d,
                    "RPN": rpn_calc,
                    "Mitigation": actual_mitigation.strip() if actual_mitigation.strip() else "اقدام مقتضی خاصی ثبت نشده است."
                }
                st.session_state.assessments.append(new_assessment)
                save_assessments(st.session_state.assessments)
                # ریست کردن فیلد متنی برای فرم بعدی
                st.session_state.mitigation_text = ""
                st.toast("ارزیابی ریسک با موفقیت در مخزن پروژه ذخیره شد!", icon="✅")
                st.rerun()

    with col_table:
        st.markdown("<div style='text-align: right;'><h3>جدول ارزیابی ریسک‌های ثبت‌شده</h3></div>", unsafe_allow_html=True)
        
        if st.session_state.assessments:
            df = pd.DataFrame(st.session_state.assessments)
            df_sorted = df.sort_values(by="RPN", ascending=False).reset_index(drop=True)
            
            styled_df = df_sorted.style.apply(highlight_rpn, axis=1)
            st.dataframe(styled_df, use_container_width=True)
            
            # مدیریت حذف رکوردها
            st.markdown("---")
            st.markdown("<p style='text-align: right; font-weight: bold;'>مدیریت و حذف ردیف‌ها:</p>", unsafe_allow_html=True)
            delete_option = st.selectbox("انتخاب ردیف جهت حذف:", df_sorted['Risk'].tolist(), key="delete_risk_selectbox")
            if st.button("❌ حذف ریسک انتخاب شده", type="secondary"):
                updated_assessments = [item for item in st.session_state.assessments if item['Risk'] != delete_option]
                st.session_state.assessments = updated_assessments
                save_assessments(updated_assessments)
                st.toast("ردیف مورد نظر با موفقیت حذف شد.", icon="🗑️")
                st.rerun()
                
            # دکمه دانلود CSV
            csv_data = df_sorted.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 دانلود خروجی گزارش ریسک (CSV)",
                data=csv_data,
                file_name="RD_FMEA_Report.csv",
                mime="text/csv",
                use_container_width=True
            )
        else:
            st.info("هیچ ریسکی برای این پروژه مانیتور نشده است.")

# ---------------------------------------------------------
# تب ۲: داشبورد تحلیلی و نمودارها
# ---------------------------------------------------------
with tab_dashboard:
    st.markdown("<div style='text-align: right;'><h3>گزارش‌های تحلیلی و ماتریس تصمیم‌گیری</h3></div>", unsafe_allow_html=True)
    
    if st.session_state.assessments:
        df_dash = pd.DataFrame(st.session_state.assessments)
        
        total_items = len(df_dash)
        avg_rpn = int(df_dash['RPN'].mean())
        critical_count = len(df_dash[df_dash['RPN'] >= 200])
        
        kpi1, kpi2, kpi3 = st.columns(3)
        with kpi1:
            st.metric(label="کل ریسک‌های مانیتور شده", value=total_items)
        with kpi2:
            st.metric(label="میانگین RPN کل پروژه", value=avg_rpn)
        with kpi3:
            st.metric(label="ریسک‌های بسیار بحرانی (RPN ≥ 200)", value=critical_count)
            
        st.markdown("---")
        
        chart_col1, chart_col2 = st.columns(2)
        
        with chart_col1:
            fig_bar = px.bar(
                df_dash, 
                x='RPN', 
                y='Risk', 
                orientation='h',
                color='RPN',
                color_continuous_scale=['#d4edda', '#fff3cd', '#f8d7da'],
                labels={'RPN': 'عدد اولویت ریسک (RPN)', 'Risk': 'عنوان ریسک'},
                title="توزیع فراوانی ریسک‌ها براساس امتیاز RPN"
            )
            fig_bar.update_layout(yaxis={'categoryorder':'total ascending'}, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
            st.plotly_chart(fig_bar, use_container_width=True)
            
        with chart_col2:
            fig_scatter = px.scatter(
                df_dash, 
                x="O", 
                y="S", 
                size="RPN", 
                color="RPN",
                hover_name="Risk",
                size_max=30,
                color_continuous_scale=['#2ca02c', '#ff7f0e', '#d62728'],
                labels={"O": "احتمال وقوع (O)", "S": "شدت اثر (S)"},
                title="موقعیت ریسک‌ها بر روی ماتریس اثر-احتمال"
            )
            fig_scatter.add_vline(x=5, line_width=1.5, line_dash="dash", line_color="gray")
            fig_scatter.add_hline(y=5, line_width=1.5, line_dash="dash", line_color="gray")
            fig_scatter.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
            st.plotly_chart(fig_scatter, use_container_width=True)
    else:
        st.info("برای نمایش نمودارها و آمار، ابتدا باید ریسک‌های پروژه را در تب اول ثبت کنید.")

# ---------------------------------------------------------
# تب ۳: تنظیمات سیستم و منبع داده
# ---------------------------------------------------------
with tab_settings:
    st.markdown("<div style='text-align: right;'><h3>پیکربندی هوش مصنوعی و بانک اطلاعاتی مرجع</h3></div>", unsafe_allow_html=True)
    
    col_ai_conf, col_db_conf = st.columns(2)
    
    with col_ai_conf:
        st.markdown("<p style='text-align: right; font-weight: bold;'>🤖 پیکربندی مدل Ollama محلی:</p>", unsafe_allow_html=True)
        # تخصیص مقادیر پیش‌فرض پویا از State
        url_input = st.text_input("آدرس API محلی Ollama (پورت پیش‌فرض ۱۱۴۳۴):", value=st.session_state.ollama_url)
        model_input = st.text_input("نام دقیق مدل نصب‌شده (مانند Llama3 یا Mistral):", value=st.session_state.ollama_model)
        
        if st.button("🔧 ذخیره و اعمال تغییرات هوش مصنوعی", use_container_width=True):
            st.session_state.ollama_url = url_input
            st.session_state.ollama_model = model_input
            st.success("تنظیمات هسته Ollama با موفقیت به‌روزرسانی شد.")
            
    with col_db_conf:
        st.markdown("<p style='text-align: right; font-weight: bold;'>📝 مدیریت دستی عناوین پایگاه داده مرجع:</p>", unsafe_allow_html=True)
        current_list = load_reference_risks()
        
        # افزودن ریسک جدید به صورت دستی
        new_risk_title = st.text_input("ثبت دستی ریسک جدید به پایگاه مرجع:")
        if st.button("➕ ثبت دستی در پایگاه", use_container_width=True):
            if new_risk_title and new_risk_title not in current_list:
                current_list.append(new_risk_title)
                save_reference_risks(current_list)
                st.success("ریسک با موفقیت اضافه شد.")
                st.rerun()
                
        # حذف ریسک از پایگاه مرجع
        risk_to_remove = st.selectbox("یک ریسک را برای حذف دائم از پایگاه انتخاب کنید:", current_list)
        if st.button("🗑️ حذف از منبع سیستم", use_container_width=True, type="secondary"):
            if risk_to_remove in current_list:
                current_list.remove(risk_to_remove)
                save_reference_risks(current_list)
                st.toast("ریسک از فایل مرجع حذف شد.", icon="🗑️")
                st.rerun()

    st.markdown("---")
    with st.expander("👀 ساختار خام داده‌های risks.json جهت عیب‌یابی"):
        st.json({"medical_risks": current_list})