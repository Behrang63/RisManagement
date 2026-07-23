name: agentic-resilience-english
description: A strict architectural and security guideline for building self-correcting Agentic Systems (Maker-Checker) robust against LLM hallucinations, laziness, boundary leaks, and syntax artifacts, specifically optimized for clinical/analytical contexts.

Agentic Resilience & Security Standards

This skill is designed for engineering and reviewing Agentic Systems. The primary objective of this skill is to prevent destructive behavior, Laziness, and Hallucination of Large Language Models (LLMs) within a Maker-Checker loop.

When generating or reviewing Python code for Agentic Systems, adherence to the following 6 principles is MANDATORY. Any deviation from these principles is considered Fragile Code.

1. Stateful Correction (Solving Agent Amnesia)

Problem: If the Checker agent only reports "an error occurred" but the Maker agent doesn't know what it generated that caused the error, the model gets stuck in an infinite loop of repeating the same mistake.
Rule: The previous invalid output (previous_output) MUST always be passed to the Maker along with the critical feedback.
Execution in prompt:

🚨 PREVIOUS FAILED OUTPUT (DO NOT REPEAT THIS MISTAKE):
{previous_output}
🚨 CRITICAL EVIDENCE FROM CHECKER AGENT:
{feedback}


2. Anti-Placeholder & Lazy Scoring Detection (Combating Model Laziness)

Problem: To avoid deep analysis, models often generate neutral values (like "unnamed") or median scores (like 5-5-5 in a risk matrix). If the evaluator only checks the Syntax, it gets easily fooled.
Rule: The Checker must include a blacklist of meaningless words and proactively block lazy default values.
Execution:

Block placeholders like ["unnamed", "unknown", "none", "null", "role", "risk", "error", "problem"].

Block scores indicating a lack of genuine evaluation (e.g., if S==5 and O==5 and D==5, the output must be rejected).

3. Hidden Character Cleanup & Length Constraints (Closing Filter Bypasses)

Problem: The model might bypass blacklist filters using zero-width non-joiners (e.g., \u200c in Persian/Arabic) or other hidden characters. It might also return irrelevant single-word titles to satisfy key requirements.
Rule: Hidden characters must be sanitized before evaluation, and the length of sensitive phrases must be strictly checked.
Execution:

Use text sanitization like text.replace('\u200c', ' ').strip().

Enforce word count limits (e.g., a risk title must be at least 2 words len(title_words) >= 2 to prevent meaningless single words while still accepting valid two-word clinical risks like "surgical error").

Inject an explicit Language Mandate to the Maker to enforce standard academic grammar and prevent robotic, machine-translated tones.

4. Hard Error Boundaries (Preventing Boundary Leaks)

Problem: If the agentic loop exhausts its retry limit (MAX_RETRIES) and fails to validate, the system must never send raw, failed, or default data to the User Interface (UI).
Rule: The agentic loop must implement a Hard Error Boundary. If validation is ultimately unsuccessful, the orchestrator function must only return None and display an explicit error (e.g., st.error) to the user. Injecting fake or fallback data to prevent application crashes is strictly prohibited.

5. Pre-Parse Regex Sanitization (Resilience Against Local Model Syntax Errors)

Problem: Local/Open-source LLMs frequently produce syntax artifacts like trailing commas at the end of JSON arrays or objects (e.g., },]), which instantly crash standard parsers like json.loads.
Rule: The model's raw output must be sanitized by Regex before being passed to the JSON parser.
Execution:

clean_text = re.sub(r',\s*\}', '}', clean_text)
clean_text = re.sub(r',\s*\]', ']', clean_text)
parsed_data = json.loads(clean_text)


6. Infrastructure Resilience (Safe Pathing & Network Bottleneck Tolerance)

Problem: Code fails to locate folders across different operating systems due to relative pathing. Additionally, network connections drop with Timeout errors because local models require significant processing time for large context windows.
Rule: * To create and read skill/settings directories (e.g., Ethic_SKILL), absolute pathing based on the executable file must be used: os.path.join(os.path.dirname(os.path.abspath(__file__)), "DirName") along with os.makedirs(exist_ok=True).

In requests.post calls to local models (like Ollama), time limits must never interrupt execution. Always use timeout=None.

Checklist for Code Reviewers

When reviewing code based on this skill, ask the following questions:

[ ] Does the Maker Agent receive its previous output for stateful correction upon receiving an error?

[ ] Does the Checker Agent evaluate values semantically (Semantic & Length Check) rather than just superficially checking for dictionary keys?

[ ] Are extra trailing commas in JSON arrays sanitized via Regex before json.loads?

[ ] In the MAX_RETRIES loop, upon exhausting all attempts, is the output exactly None?

[ ] Is the time limit (timeout=None) removed for the local LLM network requests?

[ ] Are file paths constructed dynamically and absolutely (e.g., using os.path.abspath)?