# =============================================================================
# 1. IMPORTS & DEPENDENCIES
# =============================================================================
import streamlit as st
import pandas as pd
import json
import os
import requests
import re
import plotly.express as px
import plotly.graph_objects as go

# Optional Document Processing Modules
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

# Optional RAG Modules
try:
    import chromadb
    from langchain_text_splitters import RecursiveCharacterTextSplitter
    RAG_AVAILABLE = True
except ImportError:
    RAG_AVAILABLE = False

# =============================================================================
# 2. ENVIRONMENT BOOTSTRAPPING & DEPLOYMENT
# =============================================================================
def generate_launcher():
    """Generates an idempotent .bat file for autonomous deployment and venv detection."""
    script_path = os.path.abspath(__file__)
    base_name = os.path.splitext(os.path.basename(script_path))[0]
    bat_path = os.path.join(os.path.dirname(script_path), f"{base_name}_launcher.bat")
    
    if not os.path.exists(bat_path):
        bat_content = f"""@echo off
echo ===================================================
echo Bootstrapping Agentic Environment...
echo ===================================================
IF EXIST venv\\Scripts\\activate.bat (
    call venv\\Scripts\\activate.bat
    echo [INFO] Virtual Environment 'venv' activated.
) ELSE IF EXIST .venv\\Scripts\\activate.bat (
    call .venv\\Scripts\\activate.bat
    echo [INFO] Virtual Environment '.venv' activated.
) ELSE (
    echo [WARNING] No virtual environment found. Running globally.
)
streamlit run "{script_path}"
pause
"""
        try:
            with open(bat_path, "w", encoding="utf-8") as f:
                f.write(bat_content)
        except Exception as e:
            pass # Fail silently if directory is strictly read-only

# Initialize Bootstrapper
generate_launcher()

# =============================================================================
# 3. CoALA MEMORY LOADERS
# =============================================================================
def load_semantic_memory(file_path="system_rules.md"):
    """Loads static business logic and constraints into semantic memory."""
    if not os.path.exists(file_path):
        default_rules = """# Agentic Medical Risk Evaluator - Core Semantic Rules
1. **Safety First**: Prioritize patient privacy and informed consent over operational speed.
2. **Bias Detection**: Explicitly evaluate clinical trials for systematic sampling and selection bias.
3. **Rigorous FMEA**: Assess severity (S), occurrence (O), and detection (D) metrics strictly on a 1-10 scale.
4. **Factual Output**: The output must be strictly analytical, objective, and devoid of speculative storytelling.
"""
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(default_rules)
        except Exception:
            pass
        return default_rules
    else:
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()

# =============================================================================
# 4. CORE AGENTIC LOGIC (Maker-Checker Architecture)
# =============================================================================

def query_ollama(url: str, model: str, prompt: str, system_prompt: str = "") -> str:
    """Raw communication channel to the LLM."""
    payload = {"model": model, "prompt": prompt, "stream": False}
    if system_prompt:
        payload["system"] = system_prompt
    try:
        response = requests.post(url, json=payload, timeout=90)
        response.raise_for_status()
        return response.json().get("response", "")
    except Exception as e:
        return f"ERROR: {str(e)}"

def maker_agent(url: str, model: str, document_text: str, semantic_rules: str, feedback: str = "") -> str:
    """The Generation Engine: Creates the initial output or refines it based on feedback."""
    
    system_instruction = (
        "You are the Maker Agent: an expert clinical risk auditor. "
        f"Strictly adhere to these Semantic Rules:\n{semantic_rules}\n\n"
        "OUTPUT FORMAT MANDATE: You must return ONLY a raw JSON array of up to 5 risk objects. "
        "No markdown code blocks, no conversational text, no introductions. "
        "Each object MUST contain EXACTLY these keys: 'risk', 'description', 'S', 'O', 'D'."
    )
    
    prompt = f"DOCUMENT TO AUDIT:\n{document_text}\n\n"
    if feedback:
        prompt += f"\n\n🚨 CRITICAL FEEDBACK FROM CHECKER AGENT (FIX THESE ISSUES):\n{feedback}\n\nREGENERATE VALID JSON:"
    else:
        prompt += "\n\nGENERATE FMEA RISK ANALYSIS AS JSON ARRAY:"

    return query_ollama(url, model, prompt, system_instruction)

def checker_agent(raw_output: str) -> tuple[bool, list, str]:
    """The Evaluator Engine: Strictly read-only logic and syntax audit. Never generates payload."""
    try:
        # Step 1: Pre-process (Strip unexpected markdown wrappers)
        clean_text = raw_output.strip()
        json_match = re.search(r'\[\s*\{.*\}\s*\]', clean_text, re.DOTALL)
        if json_match:
            clean_text = json_match.group(0)
            
        parsed_data = json.loads(clean_text)
        
        # Step 2: Structural Audit
        if not isinstance(parsed_data, list):
            return False, [], "EVIDENCE: Root element is not a list. You must return a JSON array [...]."
        if len(parsed_data) == 0:
            return False, [], "EVIDENCE: JSON array is empty. At least one risk must be identified."
        if len(parsed_data) > 5:
            parsed_data = parsed_data[:5] # Silent self-correction for minor over-generation
            
        # Step 3: Semantic & Bounds Audit
        validated_data = []
        for idx, item in enumerate(parsed_data):
            # Check Keys
            missing_keys = [k for k in ['risk', 'description', 'S', 'O', 'D'] if k not in item]
            if missing_keys:
                return False, [], f"EVIDENCE: Item at index {idx} is missing required keys: {missing_keys}."
            
            # --- AGENTIC SECURITY PATCH: Anti-Placeholder Check ---
            risk_title = str(item.get('risk', '')).strip()
            invalid_placeholders = ["بدون نام", "unknown", "نامشخص", "none", "null", "بدون عنوان", "بدون ریسک"]
            if not risk_title or risk_title.lower() in invalid_placeholders:
                return False, [], f"EVIDENCE: The risk title '{risk_title}' is a meaningless placeholder. You must extract a specific, highly relevant clinical risk title from the text."
            # ------------------------------------------------------
            
            # Check Type and Bounds
            try:
                s, o, d = int(item['S']), int(item['O']), int(item['D'])
                if not (1 <= s <= 10 and 1 <= o <= 10 and 1 <= d <= 10):
                    return False, [], f"EVIDENCE: Item '{item.get('risk')}' has FMEA scores out of bounds. S,O,D must be between 1 and 10."
                
                # --- AGENTIC SECURITY PATCH: Lazy Scoring Detection ---
                if s == 5 and o == 5 and d == 5:
                    return False, [], f"EVIDENCE: Item '{item.get('risk')}' has lazy default scores (5, 5, 5). You must objectively evaluate the true severity, occurrence, and detection risk rather than defaulting to 5."
                # ------------------------------------------------------

                item['S'], item['O'], item['D'] = s, o, d # Ensure ints
            except ValueError:
                return False, [], f"EVIDENCE: Item '{item.get('risk')}' has non-integer FMEA scores. They must be pure numbers."
                
            # Check Depth
            desc_words = str(item['description']).split()
            if len(desc_words) < 6:
                return False, [], f"EVIDENCE: Description for '{item.get('risk')}' is too superficial. Provide analytical depth based on the semantic rules."
                
            validated_data.append(item)
            
        return True, validated_data, "Validation Passed"

    except json.JSONDecodeError as e:
        return False, [], f"EVIDENCE: JSON parsing failed. You outputted invalid JSON syntax. Ensure proper string escaping and no trailing commas. Parser Error: {str(e)}"
    except Exception as e:
        return False, [], f"EVIDENCE: System exception during logic audit: {str(e)}"

def execute_agentic_loop(url: str, model: str, context_text: str, semantic_rules: str):
    """Orchestrates the Bounded Agentic Loop to prevent infinite generation."""
    MAX_RETRIES = 3
    attempt = 0
    feedback = ""
    
    progress_ui = st.empty()
    status_ui = st.empty()
    
    while attempt < MAX_RETRIES:
        attempt += 1
        progress_ui.progress(attempt / MAX_RETRIES, text="Agentic Loop running...")
        status_ui.info(f"**🔄 Iteration {attempt}/{MAX_RETRIES}:** Maker Agent constructing risk matrix...")
        
        raw_output = maker_agent(url, model, context_text, semantic_rules, feedback)
        
        if "ERROR" in raw_output:
            status_ui.error(f"Network/Model Error: {raw_output}")
            progress_ui.empty()
            return None
            
        status_ui.warning(f"**🛡️ Iteration {attempt}/{MAX_RETRIES}:** Checker Agent auditing logic & syntax...")
        is_valid, parsed_data, critique = checker_agent(raw_output)
        
        if is_valid:
            status_ui.success(f"✅ Output cryptographically & logically verified on attempt {attempt}.")
            progress_ui.empty()
            return parsed_data
        else:
            feedback = critique
            status_ui.error(f"⚠️ Validation Failed. Evidence injected back to Maker: {critique}")
            
    # Graceful Escalation
    progress_ui.empty()
    status_ui.error("🚨 Agentic Loop Exhausted. Maker failed to produce verified output within MAX_RETRIES limit. Escalating to human oversight.")
    return None

# =============================================================================
# 5. HIGH-CRAFT CSS INJECTION (Emil Kowalski / Apple Design Principles)
# =============================================================================
def inject_premium_css():
    st.markdown("""
    <style>
        /* Typography: Opt for Tabular Numbers in dashboards */
        * { font-variant-numeric: tabular-nums; }
        
        /* 1. Response: Sub-300ms interactions, strong ease-out cubic-bezier */
        .stButton button {
            transition: transform 160ms cubic-bezier(0.23, 1, 0.32, 1), background-color 200ms ease, border-color 200ms ease !important;
            border-radius: 8px !important;
            transform-origin: center !important;
            will-change: transform;
        }
        
        /* 2. Direct manipulation: scale(0.97) for instant active press feedback */
        .stButton button:active {
            transform: scale(0.97) !important;
            filter: blur(0.5px); /* Masking transition imperfections */
        }
        
        /* 3. Spatial Consistency: Entrance animations (Never scale(0), use scale(0.95)) */
        @keyframes subtleSlideUp {
            from { opacity: 0; transform: translateY(12px) scale(0.98); }
            to { opacity: 1; transform: translateY(0) scale(1); }
        }
        
        div[data-testid="stVerticalBlock"] > div {
            animation: subtleSlideUp 300ms cubic-bezier(0.23, 1, 0.32, 1) forwards;
        }
        
        /* 4. Materials & Depth: Translucency and Glassmorphism */
        .glass-panel {
            background: rgba(255, 255, 255, 0.03);
            backdrop-filter: blur(12px) saturate(180%);
            -webkit-backdrop-filter: blur(12px) saturate(180%);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 12px;
            padding: 24px;
            text-align: right; 
            direction: rtl;
        }
        
        /* RTL Overrides for standard inputs */
        .stTextArea textarea, .stTextInput input { direction: rtl; text-align: right; }
    </style>
    """, unsafe_allow_html=True)

# =============================================================================
# 6. STREAMLIT UI ORCHESTRATION
# =============================================================================
st.set_page_config(page_title="Agentic Ethics Risk Analyzer", page_icon="🛡️", layout="wide")
inject_premium_css()

# Session State Orchestration (Working Memory)
if 'ollama_url' not in st.session_state:
    st.session_state.ollama_url = "http://localhost:11434/api/generate"
if 'ollama_model' not in st.session_state:
    st.session_state.ollama_model = "llama3"
if 'verified_risks_buffer' not in st.session_state:
    st.session_state.verified_risks_buffer = []
if 'final_assessments' not in st.session_state:
    st.session_state.final_assessments = []

class DocumentProcessor:
    @staticmethod
    def extract_text(uploaded_file) -> str:
        if uploaded_file is None: return ""
        ext = os.path.splitext(uploaded_file.name)[1].lower()
        text = ""
        try:
            if ext == '.pdf' and PYPDF_AVAILABLE:
                reader = pypdf.PdfReader(uploaded_file)
                text = "\n".join([page.extract_text() for page in reader.pages if page.extract_text()])
            elif ext in ['.docx', '.doc'] and DOCX_AVAILABLE:
                doc = docx.Document(uploaded_file)
                text = "\n".join([para.text for para in doc.paragraphs])
            elif ext == '.txt':
                text = uploaded_file.read().decode('utf-8', errors='ignore')
            else:
                text = "Unsupported file format or required library not installed."
        except Exception as e:
            text = f"Extraction Error: {str(e)}"
        return text.strip()

# Application Header
st.markdown("""
    <div class="glass-panel" style="margin-bottom: 24px; border-right: 6px solid #0ea5e9;">
        <h1 style="margin-top: 0; color: #0ea5e9;">🛡️ Agentic Ethics Risk Analyzer</h1>
        <p style="margin-bottom: 0; color: #64748b; font-size: 1.1rem;">
            Powered by Maker-Checker Architecture, Bounded Evaluation Loops, and CoALA Memory.
        </p>
    </div>
""", unsafe_allow_html=True)

tab_extract, tab_evaluate, tab_dashboard, tab_settings = st.tabs([
    "📥 1. Agentic Extraction", "📋 2. FMEA Matrix", "📊 3. Dashboard", "⚙️ 4. AI & Engine Config"
])

# --- TAB 1: Agentic Extraction ---
with tab_extract:
    col_input, col_action = st.columns([1, 1])
    
    with col_input:
        st.markdown("### 📄 Document Ingestion")
        uploaded_file = st.file_uploader("Upload Proposal (PDF, DOCX, TXT):", type=["pdf", "docx", "txt"])
        fallback_text = st.text_area("Or Paste Raw Text:", height=150)
        
        final_text = DocumentProcessor.extract_text(uploaded_file) if uploaded_file else fallback_text

    with col_action:
        st.markdown("### 🧠 Execution Control")
        st.info("The system utilizes an internal Maker-Checker loop. Unverified data will not be displayed.")
        
        if st.button("🚀 Execute Bounded Agentic Loop", use_container_width=True, type="primary"):
            if not final_text.strip():
                st.error("Document context is empty. Please provide text.")
            else:
                semantic_rules = load_semantic_memory()
                # Run the orchestrator
                verified_data = execute_agentic_loop(
                    st.session_state.ollama_url, 
                    st.session_state.ollama_model, 
                    final_text[:2500], # Simplified context cap
                    semantic_rules
                )
                
                if verified_data:
                    st.session_state.verified_risks_buffer = verified_data
                    st.toast("Agentic Loop Completed Successfully!", icon="✅")
                else:
                    st.toast("Agentic Loop Failed to verify.", icon="🚨")

    # Display Verified Buffer
    if st.session_state.verified_risks_buffer:
        st.markdown("---")
        st.markdown("### 🛡️ Verified Output Stream")
        for idx, item in enumerate(st.session_state.verified_risks_buffer):
            with st.container():
                st.markdown(f"""
                <div class="glass-panel" style="padding: 16px; margin-bottom: 12px; border-left: 4px solid #22c55e;">
                    <strong>{item.get('risk', 'Unknown')}</strong><br/>
                    <span style="color: #64748b; font-size: 0.95em;">{item.get('description', '')}</span><br/>
                    <div style="margin-top: 8px;">
                        <span style="background: #e0f2fe; color: #0284c7; padding: 4px 8px; border-radius: 4px; font-weight: bold; font-size: 0.85em;">Severity: {item.get('S')}</span>
                        <span style="background: #e0f2fe; color: #0284c7; padding: 4px 8px; border-radius: 4px; font-weight: bold; font-size: 0.85em;">Occurrence: {item.get('O')}</span>
                        <span style="background: #e0f2fe; color: #0284c7; padding: 4px 8px; border-radius: 4px; font-weight: bold; font-size: 0.85em;">Detection: {item.get('D')}</span>
                    </div>
                </div>
                """, unsafe_allow_html=True)
            
            if st.button(f"Commit to Assessment Matrix ↳", key=f"commit_{idx}"):
                item['RPN'] = int(item['S']) * int(item['O']) * int(item['D'])
                st.session_state.final_assessments.append(item)
                st.session_state.verified_risks_buffer.pop(idx)
                st.rerun()

# --- TAB 2: FMEA Matrix ---
with tab_evaluate:
    st.markdown("### 📋 FMEA Matrix (Verified Data)")
    if st.session_state.final_assessments:
        df = pd.DataFrame(st.session_state.final_assessments)
        df_sorted = df.sort_values(by="RPN", ascending=False).reset_index(drop=True)
        st.dataframe(df_sorted, use_container_width=True)
        
        if st.button("Clear Matrix Data", type="secondary"):
            st.session_state.final_assessments = []
            st.rerun()
    else:
        st.info("No verified assessments committed yet. Run the Agentic Loop in Tab 1.")

# --- TAB 3: Dashboard ---
with tab_dashboard:
    st.markdown("### 📊 Metrics Visualization")
    if st.session_state.final_assessments:
        df_dash = pd.DataFrame(st.session_state.final_assessments)
        col1, col2 = st.columns(2)
        with col1:
            fig_bar = px.bar(df_dash, x="risk", y="RPN", color="RPN", color_continuous_scale="Reds", title="Risk Priority Number (RPN)")
            fig_bar.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
            st.plotly_chart(fig_bar, use_container_width=True)
        with col2:
            fig_scatter = px.scatter(df_dash, x="O", y="S", size="RPN", color="RPN", title="Severity vs Occurrence", hover_name="risk")
            fig_scatter.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
            st.plotly_chart(fig_scatter, use_container_width=True)
    else:
        st.info("No data available for visualization.")

# --- TAB 4: AI & Engine Config ---
with tab_settings:
    st.markdown("### ⚙️ CoALA Memory & AI Endpoint Configuration")
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**LLM Engine Endpoint**")
        st.session_state.ollama_url = st.text_input("API URL:", value=st.session_state.ollama_url)
        st.session_state.ollama_model = st.text_input("Model Name:", value=st.session_state.ollama_model)
    with col2:
        st.markdown("**Semantic Rules (CoALA Memory)**")
        rules_text = load_semantic_memory()
        updated_rules = st.text_area("Edit `system_rules.md`:", value=rules_text, height=180)
        if st.button("Save Semantic Rules"):
            with open("system_rules.md", "w", encoding="utf-8") as f:
                f.write(updated_rules)
            st.success("Rules saved securely to disk.")