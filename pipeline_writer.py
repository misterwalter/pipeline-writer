#!/usr/bin/env python3
"""
Pipeline Writer

Writes stories semi-autonomously
"""

import json
import re
import time
import os
import requests
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple, Dict, Any

# =============================================================================
# CONFIGURATION & CONSTANTS
# =============================================================================

DEFAULT_CONFIG = {
    "model": "huihui_ai/qwen3-coder-next-abliterated:latest",
    "iteration_count": 4,
    "push_forward": True,
    "context_truncation_limit": 2000
}

OLLAMA_API_URL = "http://localhost:11434/api/generate"
LOOP_DELAY = 5
GENERATION_DELAY = 2
HANG_TIMEOUT = 900
STORIES_ROOT = "pipeline_stories"

# File Names
CONFIG_FILE = "_config.md"
PAUSE_GLOBAL = "_pause.md"
PAUSE_LOCAL = "_pause.md"
SEED_FILE = "_seed.md"
OUTLINE_FILE = "_outline.md"
LOG_FILE = "_log.md"
PROMPT_FILE = "_prompt.md"
SAMPLE_FILE = "_sample.md"
GLOBAL_LOG_FILE = "pipeline_logs.md"

## This prompt and others are cutting against the models biases to try to balance them out. Semi-effective.
GLOBAL_SYSTEM_PROMPT = """You are an expert fiction author specializing in visceral, campy, and fun narratives.
Your style is SIMPLE, DIRECT, and IMMEDIATE. Think of a B-movie or a pulp novel.

STYLE RULES:
1. NO FLOWERY LANGUAGE.
2. SIMPLE SENTENCES.
3. SHOW, DON'T TELL.
4. NO PRETENSION.
5. CAMPY TONE.
"""

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_timestamp() -> str:
    return f"[[{datetime.now().strftime('%Y-%m-%d')}]] {datetime.now().strftime('%H:%M:%S')}"

def log_message(message: str, emoji: str = "ℹ️") -> None:
    timestamp = get_timestamp()
    console_msg = f"[{timestamp}] {emoji} {message}"
    print(console_msg, flush=True)
    append_to_global_log(f"{emoji} {message}")

def append_to_global_log(message: str) -> None:
    log_path = Path(GLOBAL_LOG_FILE)
    try:
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"{get_timestamp()} {message}\n")
    except Exception as e:
        print(f"⚠️ Failed to write to {GLOBAL_LOG_FILE}: {e}", flush=True)

def log_to_story(story_path: Path, message: str) -> None:
    log_path = story_path / LOG_FILE
    try:
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"{get_timestamp()} {message}\n")
    except Exception as e:
        log_message(f"Failed to write to {story_path.name}/{LOG_FILE}: {e}", "⚠️")

def sanitize_folder_name(name: str) -> str:
    """Sanitize folder name for filenames. Replaces non-alphanum with underscore."""
    if not name:
        return "story"
    sanitized = re.sub(r'[^a-zA-Z0-9_-]', '_', name)
    sanitized = re.sub(r'_+', '_', sanitized).strip('_')
    return sanitized if sanitized else "story"

def parse_yaml_config(content: str) -> Dict[str, Any]:
    """Parse simple YAML config. Handles key: value, booleans, integers, and quoted strings."""
    config = {}
    # Regex to capture key: value, ignoring comments
    pattern = re.compile(r'^\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*:\s*(.+?)\s*(?:#.*)?$')
    
    for line in content.splitlines():
        match = pattern.match(line)
        if match:
            key = match.group(1)
            value = match.group(2).strip().strip('"').strip("'")
            
            if value.lower() == 'true':
                config[key] = True
            elif value.lower() == 'false':
                config[key] = False
            elif value.isdigit():
                config[key] = int(value)
            else:
                config[key] = value
    return config

def load_config(story_path: Path) -> Dict[str, Any]:
    """Load config. Creates default if missing."""
    config_path = story_path / CONFIG_FILE
    
    if not config_path.exists():
        default_content = (
            "# Story Configuration\n"
            f"model: \"{DEFAULT_CONFIG['model']}\"\n"
            f"iteration_count: {DEFAULT_CONFIG['iteration_count']}\n"
            f"push_forward: {str(DEFAULT_CONFIG['push_forward']).lower()}\n"
            f"context_truncation_limit: {DEFAULT_CONFIG['context_truncation_limit']}\n"
        )
        config_path.write_text(default_content, encoding="utf-8")
        log_message(f"Created default config for '{story_path.name}'", "📝")
        log_to_story(story_path, "Default config created")
        return DEFAULT_CONFIG.copy()
    
    try:
        content = config_path.read_text(encoding="utf-8")
        config = parse_yaml_config(content)
        
        # Merge with defaults
        final_config = DEFAULT_CONFIG.copy()
        final_config.update(config)
        
        # Validation
        if not isinstance(final_config['iteration_count'], int) or final_config['iteration_count'] < 1:
            final_config['iteration_count'] = DEFAULT_CONFIG['iteration_count']
        if not isinstance(final_config['push_forward'], bool):
            final_config['push_forward'] = DEFAULT_CONFIG['push_forward']
        if not isinstance(final_config['context_truncation_limit'], int):
            final_config['context_truncation_limit'] = DEFAULT_CONFIG['context_truncation_limit']
            
        return final_config
    except Exception as e:
        log_message(f"Error parsing config for '{story_path.name}': {e}. Using defaults.", "⚠️")
        return DEFAULT_CONFIG.copy()

def read_file_safe(path: Path) -> str:
    if not path.exists():
        return ""
    try:
        return path.read_text(encoding="utf-8")
    except Exception as e:
        log_message(f"Error reading {path}: {e}", "⚠️")
        return ""

def get_story_folders() -> List[Path]:
    root_path = Path(STORIES_ROOT)
    if not root_path.exists():
        log_message(f"Root directory '{STORIES_ROOT}' not found. Creating it...", "📂")
        root_path.mkdir(parents=True, exist_ok=True)
        return []

    folders = []
    for item in root_path.iterdir():
        if item.is_dir() and (item / SEED_FILE).exists():
            folders.append(item)
    return sorted(folders)

def get_global_pause() -> bool:
    return Path(PAUSE_GLOBAL).exists()

def get_local_pause(story_path: Path) -> bool:
    return (story_path / PAUSE_LOCAL).exists()

def truncate_text(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return "..." + text[-max_chars:]

def check_pause_between_calls() -> bool:
    if get_global_pause():
        #log_message("Global pause detected. Waiting...", "⏸️")  Excessive logging
        time.sleep(LOOP_DELAY)
        return True
    return False

def stream_ollama_api(system_prompt: str, user_prompt: str, 
                      model_name: str,
                      timeout: int = HANG_TIMEOUT,
                      story_path: Optional[Path] = None) -> Tuple[Optional[str], bool]:
    payload = {
        "model": model_name,
        "prompt": user_prompt,
        "system": system_prompt,
        "stream": True,
        "options": {"temperature": 0.8, "num_predict": 4096, "top_p": 0.9}
    }

    log_message(f"Starting API generation with model: {model_name}...", "⏳")
    if story_path:
        log_to_story(story_path, f"Starting generation with model: {model_name}")
    
    print("   (Waiting for response...)", flush=True)
    
    try:
        response = requests.post(OLLAMA_API_URL, json=payload, stream=True, timeout=timeout)
        response.raise_for_status()

        full_response = []
        last_update_time = time.time()
        first_token_received = False
        is_hung = False

        for line in response.iter_lines():
            if not line:
                continue
            
            if check_pause_between_calls():
                log_message("Paused during generation. Saving partial output.", "⏸️")
                is_hung = True
                break

            if time.time() - last_update_time > timeout:
                log_message(f"HANG DETECTED: No tokens for {timeout} seconds. Aborting.", "❌")
                is_hung = True
                break

            try:
                data = json.loads(line)
                if "response" in data:
                    chunk = data["response"]
                    full_response.append(chunk)
                    print(chunk, end="", flush=True)
                    last_update_time = time.time()
                    if not first_token_received:
                        first_token_received = True
                        log_message("First token received.", "✨")
                
                if data.get("done", False):
                    break
            except json.JSONDecodeError:
                continue

        print() 
        response_text = "".join(full_response)
        
        if is_hung:
            log_message(f"Generation interrupted. Saving partial output ({len(response_text)} chars).", "⚠️")
            if story_path:
                log_to_story(story_path, f"Generation interrupted (hung). Model: {model_name}")
            return response_text, False
        
        if not first_token_received:
            log_message("API returned no tokens.", "❌")
            if story_path:
                log_to_story(story_path, f"Generation failed: No tokens received. Model: {model_name}")
            return response_text, False
            
        return response_text, True

    except requests.exceptions.Timeout:
        log_message("Request timed out.", "❌")
        if story_path:
            log_to_story(story_path, f"Generation failed: Timeout. Model: {model_name}")
        return "", False
    except requests.exceptions.ConnectionError:
        log_message("Could not connect to Ollama API. Is it running?", "❌")
        if story_path:
            log_to_story(story_path, f"Generation failed: Connection error. Model: {model_name}")
        return "", False
    except Exception as e:
        log_message(f"API Error: {e}", "❌")
        if story_path:
            log_to_story(story_path, f"Generation failed: {e}. Model: {model_name}")
        return "", False

def get_iteration_letter(index: int) -> str:
    """Convert 1-based index to letter (a-z). Caps at z."""
    if index < 1: return 'a'
    if index > 26: return 'z'
    return chr(ord('a') + index - 1)

def get_existing_iterations(story_path: Path, chapter_num: int, sanitized_name: str) -> List[int]:
    """Returns list of existing iteration indices (1, 2, 3...) for a chapter."""
    existing = []
    # Pattern: Name_ChapterNumLetter.md
    pattern = re.compile(rf"^{re.escape(sanitized_name)}_{chapter_num:02d}([a-z])\.md$")
    
    for f in story_path.iterdir():
        if f.is_file():
            match = pattern.match(f.name)
            if match:
                letter = match.group(1)
                idx = ord(letter) - ord('a') + 1
                existing.append(idx)
    return sorted(existing)

def get_canonical_chapter_path(story_path: Path, chapter_num: int, sanitized_name: str) -> Optional[Path]:
    path = story_path / f"{sanitized_name}_{chapter_num:02d}.md"
    return path if path.exists() else None

def get_previous_chapter_context(story_path: Path, chapter_num: int, sanitized_name: str, config: Dict[str, Any]) -> str:
    """
    Get context from previous chapter.
    Priority: Canonical > Iteration 'a'.
    Raises ValueError if context missing for Chapter > 1.
    """
    if chapter_num == 1:
        return ""
    
    prev_chap = chapter_num - 1
    
    # 1. Try Canonical
    canonical_path = get_canonical_chapter_path(story_path, prev_chap, sanitized_name)
    if canonical_path:
        text = read_file_safe(canonical_path)
        return truncate_text(text, config['context_truncation_limit'])
    
    # 2. Try Iteration 'a'
    existing_iters = get_existing_iterations(story_path, prev_chap, sanitized_name)
    if 1 in existing_iters:
        iter_path = story_path / f"{sanitized_name}_{prev_chap:02d}a.md"
        text = read_file_safe(iter_path)
        return truncate_text(text, config['context_truncation_limit'])
    
    # 3. Error
    raise ValueError(f"Missing context for Chapter {chapter_num}. No canonical or iteration 'a' found for Chapter {prev_chap}.")

def build_system_prompt(story_path: Path, config: Dict[str, Any]) -> str:
    base_prompt = GLOBAL_SYSTEM_PROMPT
    
    prompt_path = story_path / PROMPT_FILE
    story_prompt = read_file_safe(prompt_path).strip()
    if story_prompt:
        base_prompt += f"\n\nSTORY-SPECIFIC GUIDANCE:\n{story_prompt}"
    
    sample_path = story_path / SAMPLE_FILE
    sample_content = read_file_safe(sample_path).strip()
    if sample_content:
        base_prompt += f"\n\nPROSE SAMPLE TO EMULATE:\n{sample_content}"
    
    return base_prompt

# =============================================================================
# PIPELINE STAGES
# =============================================================================

def stage_1_seed_to_outline(story_path: Path, config: Dict[str, Any]) -> bool:
    seed_path = story_path / SEED_FILE
    outline_path = story_path / OUTLINE_FILE
    model_name = config['model']
    
    log_message(f"Stage 1: Converting Seed to Outline for '{story_path.name}'...", "📝")
    log_to_story(story_path, f"Starting Stage 1: Converting Seed to Outline (Model: {model_name})")
    
    content = read_file_safe(seed_path)
    if not content:
        log_message("Seed file empty.", "❌")
        log_to_story(story_path, "Error: seed.md is empty")
        return False

    min_chapters = 12
    match = re.search(r"^TARGET_LENGTH:\s*(\d+)", content, re.MULTILINE | re.IGNORECASE)
    if match:
        try:
            val = int(match.group(1))
            min_chapters = max(3, min(50, val))
        except ValueError:
            pass

    log_message(f"Target Length: {min_chapters} chapters", "🎯")
    log_to_story(story_path, f"Target length: {min_chapters} chapters")

    system_prompt = build_system_prompt(story_path, config)
    prompt = f"""
    Based on the seed concept, create a detailed story outline.
    
    CRITICAL REQUIREMENT:
    You MUST break this story into exactly {min_chapters} distinct chapters.
    For EACH chapter, provide a DETAILED summary including:
    - Specific actions.
    - Character emotional states.
    - Key dialogue or events.
    
    Structure:
    1. **Characters**: Names, roles, flaws.
    2. **Setting**: Location.
    3. **Chapter Breakdown**:
       - **Chapter 1**: [Detailed summary]
       - **Chapter 2**: [Detailed summary]
       ...
       - **Chapter {min_chapters}**: [Detailed summary]
    
    Seed Concept:
    {content}
    """
    
    response, success = stream_ollama_api(system_prompt, prompt, model_name, story_path=story_path)

    if response:
        outline_path.write_text(response, encoding="utf-8")
        if success:
            log_message(f"Outline saved: {OUTLINE_FILE}", "✅")
            log_to_story(story_path, "Outline created successfully")
        else:
            log_message(f"Outline saved (PARTIAL/HUNG): {OUTLINE_FILE}", "⚠️")
            log_to_story(story_path, "Outline created (partial/hung)")
        return True
    return False

def stage_2_generate_chapters(story_path: Path, config: Dict[str, Any]) -> bool:
    seed_name = story_path.name
    outline_path = story_path / OUTLINE_FILE
    model_name = config['model']
    sanitized_name = sanitize_folder_name(seed_name)
    iteration_count = config['iteration_count']
    push_forward = config['push_forward']
    
    outline_content = read_file_safe(outline_path)
    if not outline_content:
        log_message("Outline missing.", "❌")
        log_to_story(story_path, "Error: outline.md missing")
        return False

    # Parse chapters
    chapter_pattern = r"\*\*- Chapter (\d+): (.+?)(?=\*\*- Chapter \d+:|$)"
    matches = re.findall(chapter_pattern, outline_content, re.DOTALL)
    if not matches:
        chapter_pattern = r"- Chapter (\d+): (.+?)(?=- Chapter \d+:|$)"
        matches = re.findall(chapter_pattern, outline_content, re.DOTALL)
    if not matches:
        chapter_pattern = r"Chapter (\d+): (.+?)(?=Chapter \d+:|$)"
        matches = re.findall(chapter_pattern, outline_content, re.DOTALL)
    if not matches:
        chapter_pattern = r"\*\*Chapter (\d+)\*\*: (.+?)(?=\*\*Chapter \d+\*\*:|$)"
        matches = re.findall(chapter_pattern, outline_content, re.DOTALL)

    if not matches:
        log_message("Could not parse chapters from outline.", "❌")
        log_to_story(story_path, "Error: Could not parse chapters from outline")
        return False

    matches.sort(key=lambda x: int(x[0]))
    total_chapters = len(matches)
    
    chapter_to_process = None
    
    for i in range(1, total_chapters + 1):
        canonical_exists = get_canonical_chapter_path(story_path, i, sanitized_name) is not None
        existing_iters = get_existing_iterations(story_path, i, sanitized_name)
        
        if canonical_exists:
            continue
            
        if len(existing_iters) < iteration_count:
            chapter_to_process = i
            break
        
        # If iterations done but no canonical
        if len(existing_iters) >= iteration_count and not canonical_exists:
            if not push_forward:
                chapter_to_process = i # Wait for user
                break
            # If push_forward is True, we skip this and move to next chapter

    if chapter_to_process is None:
        return True

    # Check context availability
    if chapter_to_process > 1:
        try:
            get_previous_chapter_context(story_path, chapter_to_process, sanitized_name, config)
        except ValueError as e:
            log_message(str(e), "❌")
            log_to_story(story_path, str(e))
            return False

    # Get Chapter Plan
    chapter_data = None
    for num, desc in matches:
        if int(num) == chapter_to_process:
            chapter_data = desc.strip()
            break
    
    if not chapter_data:
        log_message(f"Missing plan for Chapter {chapter_to_process} in outline.", "❌")
        log_to_story(story_path, f"Error: Missing plan for Chapter {chapter_to_process}")
        return False

    # Get Context
    try:
        recent_context = get_previous_chapter_context(story_path, chapter_to_process, sanitized_name, config)
    except ValueError as e:
        log_message(str(e), "❌")
        log_to_story(story_path, str(e))
        return False

    # Determine next iteration
    existing_iters = get_existing_iterations(story_path, chapter_to_process, sanitized_name)
    next_iter_idx = max(existing_iters) + 1 if existing_iters else 1
    if next_iter_idx > 26: next_iter_idx = 26
    
    iteration_letter = get_iteration_letter(next_iter_idx)
    filename = f"{sanitized_name}_{chapter_to_process:02d}{iteration_letter}.md"
    
    log_message(f"Generating {filename} (Iteration {next_iter_idx}) for '{story_path.name}'...", "🔄")
    log_to_story(story_path, f"Generating {filename}")

    system_prompt = build_system_prompt(story_path, config)
    
    prompt = f"""
    Write Chapter {chapter_to_process} of the story.
    
    MASTER OUTLINE (The Bible):
    {outline_content}
    
    IMMEDIATE CONTEXT (Previous Chapter):
    {recent_context if recent_context else "No previous chapters."}
    
    CURRENT CHAPTER PLAN:
    {chapter_data}
    
    INSTRUCTIONS:
    1. The MASTER OUTLINE is the absolute truth.
    2. Use the IMMEDIATE CONTEXT to match tone and flow.
    3. Follow the CURRENT CHAPTER PLAN.
    4. If Plan conflicts with Outline, prioritize Outline.
    5. Simple, direct, explicit style.
    6. This is iteration {next_iter_idx} (letter {iteration_letter}).
    
    Start writing immediately.
    """
    
    response, success = stream_ollama_api(system_prompt, prompt, model_name, story_path=story_path)
    
    if response:
        lines = response.split('\n')
        clean_lines = [l for l in lines if not l.lower().startswith(("here is", "sure", "of course", "chapter", "writing"))]
        clean_response = '\n'.join(clean_lines).strip()
        
        chap_path = story_path / filename
        final_content = f"# Chapter {chapter_to_process} (Iteration {iteration_letter})\n\n{clean_response}"
        chap_path.write_text(final_content, encoding="utf-8")
        
        if success:
            log_message(f"{filename} saved.", "✅")
            log_to_story(story_path, f"{filename} completed successfully")
        else:
            log_message(f"{filename} saved (PARTIAL/HUNG).", "⚠️")
            log_to_story(story_path, f"{filename} completed (partial/hung)")
        
        time.sleep(GENERATION_DELAY)
        return True
    else:
        log_message(f"{filename} failed completely.", "❌")
        log_to_story(story_path, f"Error: {filename} generation failed")
        chap_path = story_path / filename
        chap_path.write_text(f"# Chapter {chapter_to_process} (Iteration {iteration_letter})\n\n[ERROR: Generation failed completely]", encoding="utf-8")
        return False

# =============================================================================
# MAIN LOOP
# =============================================================================

def main():
    log_message("=" * 60, "🚀")
    log_message("Sequential Story Pipeline Generator (Final Iteration System)", "🚀")
    log_message(f"Looking for stories in: ./{STORIES_ROOT}/", "📂")
    log_message("=" * 60, "🚀")
    
    try:
        r = requests.get("http://localhost:11434/api/tags")
        if r.status_code != 200:
            log_message("Ollama API not responding. Is 'ollama serve' running?", "❌")
            return
    except:
        log_message("Cannot connect to Ollama. Is it running?", "❌")
        return

    while True:
        if get_global_pause():
            #log_message("Global pause active. Waiting...", "⏸️")    Excessive logging
            time.sleep(LOOP_DELAY)
            continue
        
        processed_any = False
        story_folders = get_story_folders()
        
        if not story_folders:
            time.sleep(LOOP_DELAY)
            continue
        
        for story_path in story_folders:
            if get_global_pause():
                #log_message("Global pause active. Stopping iteration.", "⏸️") excessive logging
                break
            
            if get_local_pause(story_path):
                #log_message(f"Skipping '{story_path.name}': Local pause active.", "⏭️") excessive logging
                continue
            
            story_name = story_path.name
            
            log_path = story_path / LOG_FILE
            if not log_path.exists():
                log_path.write_text(f"# Log for {story_name}\n\n", encoding="utf-8")
                log_to_story(story_path, "Story folder initialized")
            
            config = load_config(story_path)
            
            seed_path = story_path / SEED_FILE
            if not seed_path.exists():
                log_message(f"Skipping '{story_name}': No seed.md found.", "⏭️")
                continue
            
            outline_path = story_path / OUTLINE_FILE
            if not outline_path.exists():
                log_message(f"Processing Stage 1 for '{story_name}'...", "📝")
                if stage_1_seed_to_outline(story_path, config):
                    processed_any = True
                    time.sleep(1)
                    continue
            
            if stage_2_generate_chapters(story_path, config):
                processed_any = True
                time.sleep(1)
                continue
        
        if not processed_any:
            time.sleep(LOOP_DELAY)

if __name__ == "__main__":
    main()
