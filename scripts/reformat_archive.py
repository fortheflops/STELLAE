import os
import json
import shutil
import time
from google import genai
from google.genai import types

# Connect using the official Google GenAI SDK
client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
MODEL_ID = 'gemini-3.5-flash'

CONTENT_DIR = "content"
ASSET_DIR = "content/assets/scans"

LIBRARIAN_PROMPT = """
You are an expert digital librarian and culinary archivist for Cucina Mezzaluna.
Your task is to take an older recipe file and upgrade it into our standardized "Kitchen-Ready" archival schema.

CRITICAL LIBRARIAN RULES:
1. "title": Clean, proper Title Case (e.g., "Mocha Rolls", "Chilled Spiced Rhubarb Soup").
2. "category": Strictly ONE of: Appetizers, Basics, Beverages, Bread, Breakfast, Desserts, Entrees, Preserves, Salads, Sauces, Sides, Snacks, Soups.
3. "collection" & "author": Extract collection origin or author if mentioned in the text or filename abbreviations like GC, UK15, JC, LOC (default to "General Archive" and "Unknown" if missing).
4. "tags": Array of lowercase tags (e.g., dish type, primary ingredients, make-ahead, vintage).
5. "equipment": Array of key kitchen tools needed (e.g., ["3-quart saucepan", "Wire whisk"]).
6. "ingredients_sections": Array of sections (e.g., "For the Base", "For the Topping"). If flat, use "Main Ingredients". Each item MUST have "measurement", "ingredient" (wrap key items in wikilinks like [[Rhubarb]]), and "notes" (prep state like "diced", "cold", or "divided").
7. "instructions_sections": Array of chronological sections (e.g., "Step 1: Simmer the Base"). MUST BOLD all measurements and ingredient names inside the text! Include sensory doneness cues (e.g., "...until golden brown and fragrant").
8. "make_ahead_notes": A 1-2 sentence storage/make-ahead tip (or null if not applicable).
9. "existing_image_path": Extract the exact relative or absolute path of any existing markdown image link (e.g., ![](/assets/scans/foo.webp) or ![](Assets/foo.webp)). If none exists, return null.

Return ONLY a raw JSON object with:
{
    "title": "Clean Title Case Name",
    "category": "Desserts",
    "collection": "Patsy's Collection",
    "author": "Patsy",
    "tags": ["vintage", "rhubarb", "make-ahead"],
    "description": "A 2-sentence SEO optimized archival description.",
    "prep_time": "15 mins",
    "cook_time": "20 mins",
    "inactive_time": "2 hours (Chilling)",
    "servings": "4–6 Servings",
    "equipment": ["3-quart saucepan", "Wire whisk"],
    "existing_image_path": "/assets/scans/example.webp",
    "ingredients_sections": [
        {
          "section_title": "For the Base",
          "items": [
            {"measurement": "4 Cups", "ingredient": "[[Rhubarb]]", "notes": "Diced into ½-inch pieces"}
          ]
        }
    ],
    "instructions_sections": [
        {
          "section_title": "Step 1: Simmer",
          "steps": [
            "In a saucepan, combine the **4 cups rhubarb** and **water**. Simmer for **20 minutes** until tender."
          ]
        }
    ],
    "make_ahead_notes": "Store sealed in the refrigerator for up to 4 days.",
    "json_ld_schema": "A valid stringified JSON-LD Recipe schema object."
}
"""

def reformat_archive():
    print(f"🔍 Deep scanning '{CONTENT_DIR}/' for all recipe files...")
    
    all_md_files = []
    for root, dirs, files in os.walk(CONTENT_DIR):
        for file in files:
            if file.lower().endswith('.md'):
                all_md_files.append(os.path.join(root, file))
                
    print(f"📖 Found {len(all_md_files)} markdown file(s). Starting Kitchen-Ready upgrade with rate-limit protection...")
    
    for file_path in all_md_files:
        filename = os.path.basename(file_path)
        
        # Skip system landing pages and Quartz navigation files
        if filename.lower() in ["index.md", "about.md", "contact.md", "404.md"]:
            continue
            
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                raw_content = f.read()
                
            # SMART SKIP: If file is already upgraded to Kitchen-Ready format, skip it!
            if "### 🔪 Key Equipment" in raw_content or "| Inactive / Chill Time |" in raw_content:
                print(f"⏭️ Already upgraded, skipping: {filename}")
                continue
                
            print(f"📚 Processing: {filename}...")
            
            # AUTO-RETRY LOOP: Tries up to 3 times if Google throws a 429 or 503 error
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    config = types.GenerateContentConfig(response_mime_type="application/json", temperature=0.1)
                    response = client.models.generate_content(
                        model=MODEL_ID,
                        contents=[LIBRARIAN_PROMPT, f"CURRENT FILE PATH: {file_path}\n\nRAW RECIPE CONTENT:\n{raw_content}"],
                        config=config
                    )
                    
                    data = json.loads(response.text)
                    save_upgraded_recipe(file_path, data)
                    
                    # SMART THROTTLE: Sleep 3.5 seconds to stay under Google's 20 RPM Free Tier limit!
                    time.sleep(3.5)
                    break # Success! Break out of the retry loop
                    
                except Exception as e:
                    error_msg = str(e)
                    if "429" in error_msg or "RESOURCE_EXHAUSTED" in error_msg or "503" in error_msg:
                        wait_time = 60 * (attempt + 1)
                        print(f"⏳ Rate limit or server spike hit! Resting for {wait_time} seconds before attempt {attempt + 2}/{max_retries}...")
                        time.sleep(wait_time)
                    else:
                        print(f"❌ Failed librarian reformat on {filename}: {e}")
                        break
            
        except Exception as e:
            print(f"❌ Could not open file {filename}: {e}")

    # Prune empty legacy subfolders after moving recipes to top-level rooms
    cleanup_empty_folders(CONTENT_DIR)

def save_upgraded_recipe(old_file_path, data):
    raw_title = data.get('title', 'Untitled Dish').strip().title()
    safe_title = raw_title.replace("/", "-").replace("\\", "-")
    new_filename = safe_title + ".md"
    
    category = data.get('category', 'Other').strip().title()
    valid_cats = ["Appetizers", "Basics", "Beverages", "Bread", "Breakfast", "Desserts", "Entrees", "Preserves", "Salads", "Sauces", "Sides", "Snacks", "Soups"]
    if category not in valid_cats:
        category = "Other"
        
    img_path = data.get('existing_image_path')
    webp_embed = ""
    
    if img_path:
        old_img_full = os.path.join(CONTENT_DIR, img_path.lstrip('/'))
        if not os.path.exists(old_img_full):
            old_img_full = os.path.join(os.path.dirname(old_file_path), img_path)
            
        if os.path.exists(old_img_full) and not os.path.isdir(old_img_full):
            img_name = os.path.basename(old_img_full)
            new_img_full = os.path.join(ASSET_DIR, img_name)
            os.makedirs(ASSET_DIR, exist_ok=True)
            
            if os.path.abspath(old_img_full) != os.path.abspath(new_img_full):
                shutil.move(old_img_full, new_img_full)
                
            webp_embed = f"\n---\n## Original Recipe Scan\n![Original Handwritten Card](/assets/scans/{img_name})\n"
        else:
            webp_embed = f"\n---\n## Original Recipe Scan\n![Original Handwritten Card]({img_path})\n"

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
title: "{safe_title}"
category: "{category}"
collection: "{data.get('collection', 'General Archive')}"
source: "{data.get('author', 'Unknown')}"
tags: {json.dumps(data.get('tags', []))}
description: "{data.get('description', '')}"
date: "2026-07-24"
draft: false
recipe: {json.dumps(data.get('json_ld_schema', '{}'))}
---

# {safe_title}

> 📜 **Collection:** {data.get('collection', 'General Archive')} | ✍️ **Attribution:** {data.get('author', 'Unknown')} | 📂 **Category:** {category}
> *{data.get('description', '')}*

---

| Prep Time | Cook Time | Inactive / Chill Time | Yield / Servings |
| :--- | :--- | :--- | :--- |
| {data.get('prep_time', 'N/A')} | {data.get('cook_time', 'N/A')} | {data.get('inactive_time', 'None')} | {data.get('servings', 'N/A')} |

---

{equip_md}{ing_md}---

{inst_md}{make_ahead_md}{webp_embed}"""

    cat_dir = os.path.join(CONTENT_DIR, category)
    os.makedirs(cat_dir, exist_ok=True)
    new_file_path = os.path.join(cat_dir, new_filename)
    
    with open(new_file_path, "w", encoding="utf-8") as f:
        f.write(markdown_content)
    print(f"✨ Upgraded -> [{category}]: {new_filename}")
    
    if os.path.abspath(old_file_path) != os.path.abspath(new_file_path):
        os.remove(old_file_path)
        print(f"🗑️ Cleaned up old file path: {old_file_path}")

def cleanup_empty_folders(directory):
    print("🧹 Cleaning up empty legacy subfolders...")
    for root, dirs, files in os.walk(directory, topdown=False):
        for name in dirs:
            folder_path = os.path.join(root, name)
            if os.path.abspath(folder_path) == os.path.abspath(ASSET_DIR):
                continue
            try:
                if not os.listdir(folder_path):
                    os.rmdir(folder_path)
                    print(f"🗑️ Pruned empty folder: {folder_path}")
            except Exception as e:
                pass

if __name__ == "__main__":
    reformat_archive()
