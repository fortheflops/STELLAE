def save_upgraded_recipe(old_file_path, data):
    raw_title = data.get('title', 'Untitled Dish').strip().title()
    safe_title = raw_title.replace("/", "-").replace("\\", "-")
    new_filename = safe_title + ".md"
    
    category = data.get('category', 'Other').strip().title()
    if category not in ["Appetizers", "Beverages", "Bread", "Desserts", "Entrees", "Salads", "Sauces", "Sides", "Snacks", "Soups"]:
        category = "Other"
        
    # Migrate scattered images to content/assets/scans/
    img_path = data.get('existing_image_path')
    webp_embed = ""
    
    if img_path:
        old_img_full_path = os.path.join(CONTENT_DIR, img_path.lstrip('/'))
        if os.path.exists(old_img_full_path):
            img_name = os.path.basename(old_img_full_path)
            new_img_full_path = os.path.join("content/assets/scans", img_name)
            os.makedirs("content/assets/scans", exist_ok=True)
            
            # Move the image to the central assets folder if it's not already there
            if os.path.abspath(old_img_full_path) != os.path.abspath(new_img_full_path):
                shutil.move(old_img_full_path, new_img_full_path)
                
            webp_embed = f"\n---\n## Original Recipe Card\n![Original Handwritten Card](/assets/scans/{img_name})\n"
        else:
            # Preserve existing link path if file was already in central directory
            webp_embed = f"\n---\n## Original Recipe Card\n![Original Handwritten Card]({img_path})\n"

    # Clean up empty legacy Assets folders
    old_dir = os.path.dirname(old_file_path)
    legacy_assets_folder = os.path.join(old_dir, "Assets")
    if os.path.exists(legacy_assets_folder) and not os.listdir(legacy_assets_folder):
        os.rmdir(legacy_assets_folder)
