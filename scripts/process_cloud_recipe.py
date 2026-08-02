import os
import glob
import json
import shutil
import time
from io import BytesIO
from google import genai
from google.genai import types
from PIL import Image

# Try importing PyMuPDF for PDF rendering
try:
    import fitz  # PyMuPDF
    PDF_SUPPORT = True
except ImportError:
    PDF_SUPPORT = False

# Connect using the official Google GenAI SDK
client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

INTAKE_DIR = "intake"
ARCHIVE_DIR = "archive/scans"
OUTPUT_DIR = "content"
ASSET_DIR = "content/assets/scans"

# BATCH LIMIT: Safely stops after 50 files per run!
MAX_FILES_PER_RUN = 50

# SAFETY LIMIT: If 3 files fail in a row, stop to protect API quotas.
MAX_CONSECUTIVE_FAILURES = 3

LIBRARIAN_PROMPT = """
You are an expert digital librarian and culinary archivist for Cucina Mezzaluna.
Your task is to take a newly scanned recipe image or PDF and process it into our standardized "Kitchen-Ready" archival schema.
SYNTHESIZE ALL PAGES OF A MULTI-PAGE DOCUMENT INTO ONE SINGLE, COHESIVE RECIPE OBJECT.

CRITICAL LIBRARIAN RULES:
1. "title": Clean, proper Title Case (e.g., "Carol's Potatoes", "Marble Cookies"). Do not mess up apostrophes.
2. "category": Strictly ONE of: Appetizers, Basics, Beverages, Bread, Breakfast, Desserts, Entrees, Preserves, Salads, Sauces, Sides, Snacks, Soups.
3. "collection" & "author": Extract collection origin or author if mentioned in the text or filename (default to "John B. Collection" and "Unattributed" if missing).
4. "tags": Array of lowercase, single-word or compressed tags without spaces (e.g., ["sidedish", "potatoes", "comfortfood"]). Do NOT include the word "vintage".
5. "equipment": Array of key kitchen tools needed (e.g., ["Mixing bowl", "Baking dish"]).
6. "ingredients_sections": Array of sections (e.g., "Main Ingredients"). Each item MUST have "measurement", "ingredient" (wrap key items in wikilinks like [[Potatoes]], [[Butter]]), and "notes" (prep state like "diced", "melted").
7. "instructions_sections": Array of chronological sections (e.g., "Step 1: Prep"). MUST BOLD all measurements and ingredient names inside the text! Include sensory doneness cues.
8. "make_ahead_notes": A 1-2 sentence storage/make-ahead tip (or null if not applicable).

Return ONLY a raw JSON object with:
{
    "title": "Carol's Potatoes",
    "category": "Sides",
    "collection": "John B. Collection",
    "author": "Carol",
    "tags": ["sidedish", "potatoes", "comfortfood"],
    "description": "A 2-sentence SEO optimized archival description.",
    "prep_time": "20 mins",
    "cook_time": "45 mins",
    "inactive_time": "None",
    "servings": "6 servings",
    "equipment": ["Baking dish"],
    "ingredients_sections": [
        {
          "section_title": "Main Ingredients",
          "items": [
            {"measurement": "4 cups", "ingredient": "[[Potatoes]]", "notes": "Sliced"}
          ]
        }
    ],
    "instructions_sections": [
        {
          "section_title": "Step 1: Baking",
          "steps": [
            "Layer the **4 cups potatoes** in a greased baking dish."
          ]
        }
    ],
    "make_ahead_notes": "Cover and refrigerate up to 24 hours before baking.",
    "json_ld_schema": "A valid stringified JSON-LD Recipe schema object."
}
"""

def process_intake():
    os.makedirs(INTAKE_DIR, exist_ok=True)
    os.makedirs(ARCHIVE_DIR, exist_ok=True)
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs(ASSET_DIR, exist_ok=True)

    all_files = glob.glob(os.path.join(INTAKE_DIR, "**", "*.*"), recursive=True)
    
    processed_count = 0
    consecutive_failures = 0

    model_fallback_list = ['gemini-3.5-flash', 'gemini-3.5-flash-lite', 'gemini-3.1-flash-lite']
    current_model_index = 0

    for file_path in all_files:
        if processed_count >= MAX_FILES_PER_RUN:
            print(f"\n🛑 Reached safety batch limit of {MAX_FILES_PER_RUN} files!")
            print("💾 Exiting cleanly so GitHub Actions can save and push your progress.")
            break

        if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
            print(f"\n🛑 {MAX_CONSECUTIVE_FAILURES} files failed in a row! Stopping to protect quotas.")
            break

        if os.path.isdir(file_path) or file_path.endswith('.gitkeep'):
            continue

        filename = os.path.basename(file_path)
        rel_path = os.path.relpath(file_path, INTAKE_DIR)
        path_parts = os.path.split(rel_path)
        collection_name = path_parts[0] if len(path_parts) > 1 and path_parts[0] != "" else "John B. Collection"

        print(f"🥘 Processing [{collection_name}] scan: {filename}...")
        
        file_success = False
        
        while current_model_index < len(model_fallback_list):
            active_model = model_fallback_list[current_model_index]
            try:
                config = types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.2
                )
                
                img_objects = []
                is_pdf_file = file_path.lower().endswith('.pdf')

                if is_pdf_file:
                    sample_file = client.files.upload(file=file_path)
                    response = client.models.generate_content(
                        model=active_model,
                        contents=[LIBRARIAN_PROMPT, sample_file],
                        config=config
                    )
                    client.files.delete(name=sample_file.name)
                    
                    if PDF_SUPPORT:
                        doc = fitz.open(file_path)
                        for page in doc:
                            pix = page.get_pixmap(dpi=150)
                            page_img = Image.open(BytesIO(pix.tobytes("png")))
                            img_objects.append(page_img)
                
                elif file_path.lower().endswith(('png', 'jpg', 'jpeg', 'heic', 'webp')):
                    img_obj = Image.open(file_path)
                    img_objects.append(img_obj)
                    response = client.models.generate_content(
                        model=active_model,
                        contents=[LIBRARIAN_PROMPT, img_obj],
                        config=config
                    )
                
                save_and_archive(response.text, [file_path], filename, collection_name, img_objects=img_objects)
                
                processed_count += 1
                consecutive_failures = 0
                file_success = True
                time.sleep(4.5)
                break
                
            except Exception as e:
                error_msg = str(e)
                if "503" in error_msg or "UNAVAILABLE" in error_msg or "429" in error_msg or "RESOURCE_EXHAUSTED" in error_msg or "404" in error_msg or "NOT_FOUND" in error_msg:
                    print(f"⚠️ Model {active_model} is unavailable or rate-limited.")
                    current_model_index += 1
                    if current_model_index < len(model_fallback_list):
                        print(f"🔄 Switching to backup model -> {model_fallback_list[current_model_index]}...")
                        time.sleep(3)
                    else:
                        print("🛑 All backup models out of quota!")
                        break
                else:
                    print(f"❌ Failed processing on {filename}: {e}")
                    break

        if not file_success:
            consecutive_failures += 1
            print(f"⚠️ Warning: Consecutive failure count is now {consecutive_failures}/{MAX_CONSECUTIVE_FAILURES}")

    print(f"\n🎉 Session finished! Successfully processed {processed_count} new files.")

def save_and_archive(json_text, source_files, archive_name, collection_name, img_objects=None):
    data = json.loads(json_text)
    
    safe_title = data.get('title', 'Untitled Dish').strip()
    
    category = data.get('category', 'Other').strip().title()
    valid_cats = ["Appetizers", "Basics", "Beverages", "Bread", "Breakfast", "Desserts", "Entrees", "Preserves", "Salads", "Sauces", "Sides", "Snacks", "Soups"]
    if category not in valid_cats:
        category = "Other"

    # Strips spaces/punctuation from tags, removes "vintage", and adds folder name as a tag
    raw_tags = data.get('tags', [])
    clean_tags = [t.lower().strip().replace(" ", "").replace("-", "") for t in raw_tags if t and t.lower().strip() != "vintage"]
    
    collection_tag = collection_name.lower().strip().replace(" ", "").replace(".", "").replace("'", "")
    if collection_tag and collection_tag not in clean_tags:
        clean_tags.append(collection_tag)

    # UNIQUE FILENAME: Appends collection name so duplicate titles never overwrite each other
    safe_base = safe_title.lower().replace(" ", "-").replace("'", "")
    collection_slug = collection_name.lower().replace(" ", "-").replace("'", "").replace(".", "")
    safe_filename = f"{safe_base}-{collection_slug}.md"
    
    webp_embeds = ""
    if img_objects:
        webp_embeds += "\n---\n## Original Recipe Scan\n"
        for idx, img_obj in enumerate(img_objects):
            page_suffix = f"-p{idx+1}" if len(img_objects) > 1 else ""
            webp_filename = safe_base + "-" + archive_name.replace(" ", "-").replace(".pdf", "") + page_suffix + ".webp"
            webp_path = os.path.join(ASSET_DIR, webp_filename)
            img_obj.convert("RGB").save(webp_path, "WEBP", quality=82)
            
            label = f"Page {idx+1}" if len(img_objects) > 1 else "Original Handwritten Card"
            webp_embeds += f"![{label}]({'/assets/scans/' + webp_filename})\n\n"

    equip_list = data.get('equipment', [])
    equip_md = "### 🔪 Key Equipment\n" + "\n".join([f"* {item}" for item in equip_list]) + "\n\n---\n" if equip_list else ""

    ing_md = "## Ingredients\n\n"
    for sec in data.get('ingredients_sections', []):
        sec_title = sec.get('section_title', 'Main Ingredients')
        if sec_title != 'Main Ingredients':
            ing_md += f"### {sec_title}\n"
        ing_md += "| Measurements | Ingredients | Prep / Notes |\n| :--- | :--- | :--- |\n"
        for item in sec.get('items', []):
            ing_md += f"| {item.get('measurement', '')} | {item.get('ingredient', '')} | {item.get('notes', '')} |\n"
        ing_md += "\n"

    inst_md = "## Instructions\n\n"
    step_num = 1
    for sec in data.get('instructions_sections', []):
        sec_title = sec.get('section_title', '')
        if sec_title:
            inst_md += f"### {sec_title}\n"
        for step in sec.get('steps', []):
            inst_md += f"{step_num}. {step}\n"
            step_num += 1
        inst_md += "\n"

    make_ahead = data.get('make_ahead_notes')
    make_ahead_md = f"---\n\n> 💡 **Make-Ahead & Storage:** {make_ahead}\n" if make_ahead else ""

    markdown_content = f"""---
title: {json.dumps(safe_title)}
category: {json.dumps(category)}
collection: {json.dumps(collection_name)}
source: {json.dumps(data.get('author', 'Unattributed'))}
tags: {json.dumps(clean_tags)}
description: {json.dumps(data.get('description', ''))}
date: "2026-07-30"
draft: false
recipe: {json.dumps(data.get('json_ld_schema', dict()))}
---

# {safe_title}

> 📜 **Collection:** {collection_name} | ✍️ **Attribution:** {data.get('author', 'Unattributed')} | 📂 **Category:** {category}
> *{data.get('description', '')}*

---

| Prep Time | Cook Time | Inactive / Chill Time | Yield / Servings |
| :--- | :--- | :--- | :--- |
| {data.get('prep_time', 'N/A')} | {data.get('cook_time', 'N/A')} | {data.get('inactive_time', 'None')} | {data.get('servings', 'N/A')} |

---

{equip_md}{ing_md}---

{inst_md}{make_ahead_md}{webp_embeds}"""

    cat_dir = os.path.join(OUTPUT_DIR, category)
    os.makedirs(cat_dir, exist_ok=True)
    out_path = os.path.join(cat_dir, safe_filename)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(markdown_content)
    print(f"✅ Generated Page in [{category}]: {out_path}")

    archive_dest = os.path.join(ARCHIVE_DIR, collection_name)
    os.makedirs(archive_dest, exist_ok=True)
    for file_path in source_files:
        shutil.move(file_path, os.path.join(archive_dest, os.path.basename(file_path)))

if __name__ == "__main__":
    process_intake()
