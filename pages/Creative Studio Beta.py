# main.py

import io
from typing import List, Optional

import streamlit as st
from PIL import Image

from google import genai
from google.genai import types
from dotenv import load_dotenv
load_dotenv()
import zipfile
import requests
import json
import os

# --- Prompt Library ----------------------------------------------------------

STYLE_PRESETS = {
    "Custom": "",
    "Minimalist Studio": "Shot against a clean, textured concrete wall. Soft, diffused natural light from a large window on the left. High-key lighting, neutral color palette (whites, beiges, greys). Sharp focus, high quality commercial fashion photography.",
    "Urban Street": "Street style photography in a bustling city environment. Blurred city background with bokeh. Natural daylight, slightly overcast for soft shadows. Dynamic angle, capturing the energy of the city. Modern, edgy vibe.",
    "Golden Hour Field": "Outdoor setting in a tall grass field during golden hour. Warm, back-lit sun creating a halo effect on hair. Dreamy, romantic atmosphere. Soft focus background, nature-inspired color palette.",
    "Neon Night": "Nighttime city scene with vibrant neon signs reflecting on wet pavement. Cyberpunk aesthetic, moody and dramatic lighting. Contrasting colors (blue/pink/purple). Cinematic look.",
    "Luxury Interior": "Inside a high-end luxury apartment or hotel lobby. Elegant furniture, warm ambient lighting, marble textures. Sophisticated and wealthy atmosphere. Depth of field focusing on the model.",
    "Film Grain Black & White": "High-contrast black and white photography. intense shadows and bright highlights. Added film grain texture for a vintage, artistic look. Timeless and dramatic.",
}

CREATIVE_DIRECTIONS = {
    "None": "",
    "Billys Flash":"Illuminated with direct flash that gives the image a raw, spontaneous, 90s-inspired aesthetic. The background falls slightly darker due to the strong frontal light. Natural, unposed expression, contemporary fashion styling, crisp details, magazine editorial feel. Shot on 35mm point-and-shoot–style perspective, vibrant colors, high realism.",
    "Editorial High Fashion": "High fashion magazine editorial. Avant-garde poses, confident expression. Focus on the geometry of the outfit and the model's presence.",
    "Lifestyle Candid": "Natural, candid moment. The model is laughing or looking away, not posing directly for the camera. Authentic, slice-of-life feel.",
    "Catalogue Clean": "Clean, simple commercial catalogue look. Model looking directly at camera, neutral expression. Focus entirely on clear representation of the clothing.",
    "Cinematic Storytelling": "A scene that looks like a still from a movie. Emotional, narrative-driven. The model looks like they are in the middle of an action or deep thought.",
}


st.set_page_config(
    page_title="Studio v2.1",
    page_icon="✨",
    layout="wide"
)

# Custom CSS
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Outfit', sans-serif;
        color: #E2E8F0;
    }
    
    .stApp {
        background-color: #0F172A; /* Slate 900 */
    }

    h1 {
        background: linear-gradient(135deg, #F472B6 0%, #A78BFA 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-size: 3.5rem !important;
        padding-bottom: 20px;
        margin-bottom: 10px;
    }
    
    h3, h4 {
        color: #F8FAFC;
        margin-top: 0.5rem;
    }

    /* Section dividers */
    hr {
        border: none;
        border-top: 1px solid #334155;
        margin: 2rem 0;
    }

    /* Cards */
    .stCard {
        background-color: #1E293B;
        padding: 24px;
        border-radius: 16px;
        border: 1px solid #334155;
    }

    /* Buttons */
    .stButton > button {
        background: linear-gradient(135deg, #6366F1 0%, #8B5CF6 100%);
        color: white;
        border: none;
        font-weight: 500;
        border-radius: 8px;
        transition: all 0.2s;
    }
    .stButton > button:hover {
        transform: scale(1.02);
        box-shadow: 0 4px 12px rgba(99, 102, 241, 0.4);
    }
    
    /* Secondary/Outline Buttons */
    button[kind="secondary"] {
        background: transparent;
        border: 1px solid #475569;
        color: #94A3B8;
    }

    /* Tag Pills */
    .tag-pill {
        display: inline-block;
        background: #334155;
        padding: 4px 12px;
        border-radius: 20px;
        font-size: 0.85rem;
        margin: 4px;
        cursor: pointer;
        border: 1px solid #475569;
    }
    .tag-pill:hover {
        background: #475569;
        border-color: #6366F1;
    }

    /* Text inputs & textareas */
    .stTextArea textarea {
        background-color: #1E293B;
        border: 1px solid #334155;
        border-radius: 8px;
        color: #E2E8F0;
    }

    /* File uploader */
    [data-testid="stFileUploader"] {
        background-color: #1E293B;
        border: 1px dashed #475569;
        border-radius: 8px;
        padding: 1rem;
    }

    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
</style>
""", unsafe_allow_html=True)



# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------

@st.cache_resource
def get_gemini_client():
    """
    Create a single Gemini client for the app.
    Uses GEMINI_API_KEY from environment by default.
    """
    return genai.Client()


def describe_inspiration_image(image_bytes: bytes, mime_type: str = "image/jpeg") -> str:
    """
    Use Gemini text model to describe the inspiration image.
    Focus on background, lighting, and atmosphere ONLY - NOT clothing or model.
    """
    client = get_gemini_client()

    img_part = types.Part.from_bytes(
        data=image_bytes,
        mime_type=mime_type,
    )

    stylist_prompt = (
        "You are a fashion photography director analyzing the environment and mood of this image. "
        "Describe ONLY the following elements:\n\n"
        "1. BACKGROUND & SETTING: The physical environment, location, textures (e.g., concrete wall, studio, outdoor park, urban street)\n"
        "2. LIGHTING: The type and quality of light (e.g., soft natural daylight, dramatic side lighting, golden hour, studio lighting)\n"
        "3. MOOD & ATMOSPHERE: The overall feeling and vibe (e.g., minimalist, moody, elegant, energetic, serene)\n"
        "4. COLOR PALETTE: Background colors and tones (e.g., cool grays, warm earth tones, vibrant neon)\n"
        "5. COMPOSITION: Camera angle, framing, depth of field if relevant to the environment\n\n"
        "CRITICAL: Do NOT describe the person, their clothing, outfit details, accessories, or what they're wearing. "
        "Completely ignore all garments and fashion items. Focus ONLY on the photographic environment, "
        "setting, lighting conditions, and aesthetic atmosphere.\n\n"
        "Keep your description to 3-4 concise sentences suitable for an AI image generator."
    )

    resp = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=[stylist_prompt, img_part],
    )

    return (resp.text or "").strip()


# -----------------------------------------------------------------------------
# Shopify Helpers
# -----------------------------------------------------------------------------

CACHE_FILE = "shopify_products_cache.json"

def fetch_shopify_products_api(shop_url, access_token):
    """
    Fetches products from Shopify Admin API.
    Returns list of products with images.
    """
    if not shop_url or not access_token:
        st.error("Missing Shopify Credentials in .env")
        return []

    # clean url
    shop_url = shop_url.replace("https://", "").replace("http://", "").strip()
    
    all_products = []
    page_info = None
    
    url = f"https://{shop_url}/admin/api/2023-10/products.json"
    headers = {
        "X-Shopify-Access-Token": access_token,
        "Content-Type": "application/json"
    }
    
    while True:
        params = {
            "limit": 250, # Max limit
            "fields": "id,title,images,variants"
        }
        if page_info:
            params["page_info"] = page_info
            
        try:
            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()
            data = response.json()
            products = data.get("products", [])
            all_products.extend(products)
            
            # Check for Link header for pagination
            link_header = response.headers.get('Link')
            if not link_header or 'rel="next"' not in link_header:
                break
                
            # Extract page_info from Link header
            # Link header format: <https://...page_info=...>; rel="next"
            # We can just extract the URL or parse it. A simple split works for standard Shopify headers.
            # But the params are already in the URL in the Link header.
            # Let's extract values.
            links = link_header.split(',')
            next_link = next((l for l in links if 'rel="next"' in l), None)
            
            if next_link:
                # Extract URL from brackets <url>
                next_url = next_link.split(';')[0].strip('<> ')
                # Update url and clear params since next_url has them
                url = next_url
                page_info = None # Not needed as it's in the URL
                params = {} # Clear params as they are in the URL
            else:
                break
                
        except Exception as e:
            st.error(f"Error fetching from Shopify: {e}")
            break
            
    return all_products

def manage_shopify_products():
    """
    Handles caching and fetching of Shopify products.
    Returns list of products.
    """
    products = []
    
    # Load cache if exists
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, 'r') as f:
                products = json.load(f)
        except:
            pass

    # Sidebar control to refresh
    # We'll put this logic near the selector for better UX or in sidebar
    return products

def save_cache(products):
    with open(CACHE_FILE, 'w') as f:
        json.dump(products, f)






def generate_image_with_inputs(
    prompt: str,
    input_images: List,  # list of PIL Images or UploadedFiles
    model_name: str = "gemini-3-pro-image-preview",
) -> Optional[Image.Image]:
    """
    Generate an image using Nano Banana with text prompt + input images.
    Returns a PIL Image or None.
    """
    client = get_gemini_client()

    contents: List = [prompt]

    # Add all input images as Parts
    for img_input in input_images:
        if isinstance(img_input, Image.Image):
            # Convert PIL Image to bytes
            img_bytes_io = io.BytesIO()
            img_input.save(img_bytes_io, format='PNG')
            img_bytes = img_bytes_io.getvalue()
            mime_type = "image/png"
        else:
            # Assume UploadedFile
            img_bytes = img_input.getvalue()
            mime_type = img_input.type or "image/jpeg"

        contents.append(
            types.Part.from_bytes(
                data=img_bytes,
                mime_type=mime_type,
            )
        )

    resp = client.models.generate_content(
        model=model_name,
        contents=contents,
    )

    # Extract the first image from the response
    for part in resp.parts:
        if part.inline_data is not None:
            image_bytes = part.inline_data.data
            img = Image.open(io.BytesIO(image_bytes))
            if img.format is None:
                img.format = 'PNG'
            return img

    return None

# -----------------------------------------------------------------------------
# Model Library Helpers
# -----------------------------------------------------------------------------

def list_models():
    """
    Scans the 'models' directory for subdirectories (models) and their images.
    Returns a dict: {model_name: [list_of_image_paths]}
    """
    models_dir = "./models"
    if not os.path.exists(models_dir):
        return {}
    
    models = {}
    for entry in os.scandir(models_dir):
        if entry.is_dir():
            images = []
            for img in os.scandir(entry.path):
                if img.is_file() and img.name.lower().endswith(('.png', '.jpg', '.jpeg', '.webp')):
                    images.append(img.path)
            if images:
                models[entry.name] = sorted(images)
    return models

# -----------------------------------------------------------------------------
# Streamlit UI
# -----------------------------------------------------------------------------

# st.set_page_config(page_title="Nano Banana Outfit Stylist", layout="wide")
st.title("Creative Studio")

st.markdown(
    """
Define your model and photographic style, then generate a complete fashion photoshoot.
"""
)



# --- Configuration Check ---
REQUIRED_KEYS = ["SHOPIFY_SHOP_URL", "SHOPIFY_ACCESS_TOKEN"]
missing_keys = [k for k in REQUIRED_KEYS if not os.getenv(k)]
if missing_keys:
    st.warning(f"⚠️ Missing environment variables for Shopify: {', '.join(missing_keys)}. functionality will be limited.")


# --- Inputs ------------------------------------------------------------------

# Create main input sections side by side
st.markdown("---")

# Top section: Style & Atmosphere
st.markdown("### 🎨 Style & Atmosphere")

col_style_1, col_style_2 = st.columns([1, 1])

with col_style_1:
    input_mode = st.radio(
        "Style Input Mode",
        ["📸 Use inspiration image", "✍️ Write custom prompt"],
        horizontal=True
    )


# Style-specific inputs
col_style_input_1, col_style_input_2 = st.columns([1, 1])

if input_mode == "📸 Use inspiration image":
    with col_style_input_1:
        inspiration_file = st.file_uploader(
            "Upload Insight Image (Background/Vibe)",
            type=["jpg", "jpeg", "png", "webp"],
            help="The AI will analyze the style, lighting, and background of this image."
        )
        if inspiration_file:
            st.image(inspiration_file, caption="Inspiration Image", width=250)
    custom_style_prompt = None
else:  # Custom prompt mode
    with col_style_input_1:
        # -- Presets for Style --
        style_preset = st.selectbox("Photography Style Preset", list(STYLE_PRESETS.keys()))
        default_style = STYLE_PRESETS[style_preset]

        custom_style_prompt = st.text_area(
            "Style Description",
            value=default_style,
            placeholder="e.g., Shot against a minimalist concrete wall, soft natural window light from the left...",
            height=120,
            help="Select a preset above to populate this field."
        )
    inspiration_file = None

with col_style_input_2:
        # -- Presets for Direction --
    direction_preset = st.selectbox("Creative Direction Preset", list(CREATIVE_DIRECTIONS.keys()))

    default_direction = CREATIVE_DIRECTIONS[direction_preset]

    user_description = st.text_area(
        "Creative Direction Details",
        value=default_direction,
        placeholder="e.g., Dramatic fashion editorial, cinematic mood, golden hour lighting...",
        height=120,
        help="You can edit the preset text or write your own."
    )


st.markdown("---")

# 2. Main Area: Model & Outfit
st.markdown("### 💃 Model & Outfit")

col_model_1, col_model_2 = st.columns([1, 1])

with col_model_1:
    st.markdown("#### 1. The Model")
    
    model_source = st.radio(
        "Model Source",
        ["📤 Upload Photos", "📂 Select from Library"],
        horizontal=True,
        label_visibility="collapsed"
    )

    model_reference_files = None
    studio_files = None # Kept for compatibility if we revert
    shopify_img_url = None
    shopify_img_bytes = None
    
    available_models = list_models()

    if model_source == "📤 Upload Photos":
        model_reference_files = st.file_uploader(
            "Model reference photos (Face & Body)",
            type=["jpg", "jpeg", "png", "webp"],
            accept_multiple_files=True,
            help="Upload clear photos of the model's face from different angles"
        )
        if model_reference_files and len(model_reference_files) > 5:
            st.warning("⚠️ Maximum 5 reference photos recommended for best results")
            model_reference_files = model_reference_files[:5]
            
    else: # Select from Library
        if not available_models:
             st.info("No models found in `models/` directory. content")
             st.write("Create folders in `models/` (e.g. `models/Billy/`) and add images there.")
        else:
            selected_model_name = st.selectbox("Choose Model", list(available_models.keys()))
            if selected_model_name:
                model_paths = available_models[selected_model_name]
                # Load images as PIL for compatibility with generation function
                # We need to simulate UploadedFile or just list of PILs
                # Our generator accepts PIL images, so let's load them.
                try:
                    loaded_model_images = []
                    # Limit to 5
                    for p in model_paths[:5]:
                         loaded_model_images.append(Image.open(p))
                    
                    model_reference_files = loaded_model_images # This Variable is used in generation
                    
                    st.success(f"Loaded {len(loaded_model_images)} images for {selected_model_name}")
                    
                    # Preview
                    cols = st.columns(len(loaded_model_images))
                    for i, img in enumerate(loaded_model_images):
                        with cols[i]:
                            st.image(img, width=200)
                            
                except Exception as e:
                    st.error(f"Error loading model images: {e}")

with col_model_2:
    st.markdown("#### 2. The Outfit")

    outfit_source = st.radio(
        "Source",
        ["🛍️ Shopify Store", "📤 Manual Upload"],
        horizontal=True,
        label_visibility="collapsed"
    )
    
    final_outfit_image_pil = None
    shopify_image_pil = None
    
    if outfit_source == "🛍️ Shopify Store":
        # Shopify Logic
        cached_products = manage_shopify_products()
        
        col_shop_1, col_shop_2 = st.columns([1, 1])
        with col_shop_1:
            if st.button("🔄 Sync with Shopify"):
                with st.spinner("Fetching products..."):
                    shop_url = os.getenv("SHOPIFY_SHOP_URL")
                    access_token = os.getenv("SHOPIFY_ACCESS_TOKEN")
                    new_products = fetch_shopify_products_api(shop_url, access_token)
                    if new_products:
                        save_cache(new_products)
                        cached_products = new_products
                        st.success(f"Synced {len(new_products)} products!")
                        st.rerun()

        selected_product_name = st.selectbox(
            "Choose Product",
            options=["Select a product..."] + [p['title'] for p in cached_products]
        )

        if selected_product_name != "Select a product...":
            # Find product
            product = next((p for p in cached_products if p['title'] == selected_product_name), None)
            if product and product.get('images'):
                
                # --- COMPACT GRID LOGIC ---
                
                # Initialize state for this product's selection if not present
                idx_key = f"selected_img_idx_{product['id']}"
                if idx_key not in st.session_state:
                        st.session_state[idx_key] = 0
                
                # Initialize state for grid visibility (collapsed by default)
                grid_vis_key = f"show_grid_{product['id']}"
                if grid_vis_key not in st.session_state:
                    st.session_state[grid_vis_key] = False
                
                current_idx = st.session_state[idx_key]
                show_grid = st.session_state[grid_vis_key]
                
                # 1. Show Selected Image Preview (Compact Mode)
                selected_img_data = product['images'][current_idx] if current_idx < len(product['images']) else product['images'][0]
                shopify_img_url = selected_img_data['src']
                
                # Use columns to align preview and controls
                col_preview, col_controls = st.columns([1, 2])
                with col_preview:
                    st.image(selected_img_data['src'], caption=f"Selected: Image {current_idx+1}", width=150)
                
                with col_controls:
                    # 2. Toggle Button for Grid
                    if not show_grid:
                        st.info("Currently using this image.")
                        if st.button("🔄 Change Variant / Image", key=f"open_grid_{product['id']}"):
                            st.session_state[grid_vis_key] = True
                            st.rerun()
                    else:
                        if st.button("❌ Close Grid", key=f"close_grid_{product['id']}"):
                            st.session_state[grid_vis_key] = False
                            st.rerun()

                # 3. The Grid (Conditional)
                if show_grid:
                    st.markdown("---")
                    st.write("Select variant image:")
                    # Limit to first 9 images
                    disp_images = product['images'][:9]
                    img_cols = st.columns(3)
                    
                    for idx, img_data in enumerate(disp_images):
                        col_i = idx % 3
                        with img_cols[col_i]:
                            if st.button(f"Select {idx+1}", key=f"btn_{product['id']}_{idx}", use_container_width=True, 
                                            type="primary" if idx == current_idx else "secondary"):
                                st.session_state[idx_key] = idx
                                st.session_state[grid_vis_key] = False # Auto-close on selection
                                st.rerun()
                            st.image(img_data['src'])

            else:
                st.warning("No images found for this product.")
            
    # --- Option B: Manual Upload ---
    else:
        outfit_upload = st.file_uploader(
            "Upload Outfit Image",
            type=["jpg", "jpeg", "png", "webp"],
            help="Upload a clear image of the outfit you want to use."
        )
        if outfit_upload:
            shopify_img_bytes = outfit_upload.getvalue()
            # Create a mock product object for consistency if needed, strictly we just need the bytes/PIL
            # But we'll handle it in the generation step.
            shopify_image_pil = Image.open(io.BytesIO(shopify_img_bytes)) # Pre-load for preview
            st.image(shopify_image_pil, caption="Selected Outfit", width=200)
            final_outfit_image_pil = shopify_image_pil


st.markdown("---")

# Generate button - centered and prominent
col_gen_1, col_gen_2, col_gen_3 = st.columns([1, 2, 1])
with col_gen_2:
    generate_btn = st.button("✨ Generate with Nano Banana", type="primary", use_container_width=True)


# --- Main Logic --------------------------------------------------------------

if generate_btn:
    # Validation

    if not model_reference_files:
        st.error("Please upload at least one model reference photo.")
        st.stop()

    
    # Logic to set final_outfit_image_pil from Shopify if not already set by manual upload
    if outfit_source == "🛍️ Shopify Store":
        if not shopify_img_url:
             st.warning("⚠️ You haven't selected a product image. Generation will rely solely on model photos.")
        else:
            try:
                 with st.spinner("Downloading product image..."):
                    r = requests.get(shopify_img_url, stream=True)
                    r.raise_for_status()
                    final_outfit_image_pil = Image.open(io.BytesIO(r.content))
            except Exception as e:
                st.error(f"Failed to load Shopify image: {e}")
                st.stop()
    elif outfit_source == "📤 Manual Upload":
         if not final_outfit_image_pil:
             st.warning("⚠️ No outfit image uploaded.")

    # Harmonize variable for prompt
    # If manual upload, we used `shopify_image_pil` name in the block above (oops, let's fix that connection)
    
    # RE-MAPPING for clarity:
    # 1. `shopify_image_pil` needs to be `final_outfit_image_pil`
    # Let's clean up the variable usage in the Manual block in next step or just ensure it propagates.
    # Actually, let's fix the variable name in the previous chunk if possible, or handle it here.
    
    if outfit_source == "📤 Manual Upload" and shopify_image_pil:
        final_outfit_image_pil = shopify_image_pil

    client = get_gemini_client()

    # 1) Analyze inspiration image OR use custom prompt
    inspiration_desc = None

    if input_mode == "📸 Use inspiration image" and inspiration_file is not None:
        with st.spinner("Analyzing inspiration image style with Gemini…"):
            insp_bytes = inspiration_file.getvalue()
            insp_mime = inspiration_file.type or "image/jpeg"

            inspiration_desc = describe_inspiration_image(
                image_bytes=insp_bytes,
                mime_type=insp_mime,
            )

        with st.expander("📸 Inspiration style description", expanded=False):
            st.write(inspiration_desc or "_No description returned._")
            
    elif input_mode == "✍️ Write custom prompt":
        inspiration_desc = custom_style_prompt
        with st.expander("📸 Custom style description", expanded=False):
            st.write(inspiration_desc or "_No description provided._")

    # 2) Build prompt for first image
    studio_instruction = (
        f"PERSON TO RECREATE: The first {len(model_reference_files)} reference images show the model. "
        f"Use their EXACT facial features, skin tone, hair, and body type. "
        f"{'OUTFIT TO USE: The last reference image is the Product/Outfit. Dress the model in this exact outfit. ' if final_outfit_image_pil else 'Create a stylish high-fashion outfit. '}"
        "Combine the person with the outfit in the new photographic environment."
    )
    
    pieces = []
    if user_description:
        pieces.append(f"Creative direction: {user_description}")
    if inspiration_desc:
        pieces.append(f"Background & photographic style: {inspiration_desc}")
    if not pieces:
        pieces.append("Create a high-end fashion editorial photo.")
    
    combined = "\n".join(pieces)
    
    main_prompt = (
        f"Create a photorealistic fashion photograph.\n"
        f"{studio_instruction}\n\n"
        f"{combined}\n\n"
        "Full-body shot, vertical 3:4 aspect ratio, professional fashion editorial lighting, "
        "shallow depth of field, magazine-quality image."
    )

    with st.expander("🎯 Generated prompt for main image", expanded=False):
        st.code(main_prompt)

    # 3) Generate FIRST image
    with st.spinner("🎨 Generating main image with Nano Banana…"):
        # Combine all reference images
        all_reference_images = []
        if model_reference_files:
            all_reference_images.extend(model_reference_files)
        
        # Add Outfit image last
        if final_outfit_image_pil:
            all_reference_images.append(final_outfit_image_pil)
        
        main_image = generate_image_with_inputs(
            main_prompt, 
            all_reference_images
        )

    if not main_image:
        st.error("Failed to generate main image.")
        st.stop()



    # 9) Display results
    st.subheader("✨ Results")

    # First row
    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown("**Main Image**")
        if main_image:
            st.image(main_image)
        else:
            st.error("No image returned.")


    # 10) Store all generated images in session state for re-use
    if 'generated_images' not in st.session_state:
        st.session_state.generated_images = []
    
    if 'reference_files_stored' not in st.session_state:
        st.session_state.reference_files_stored = []

    # Store current batch
    st.session_state.generated_images = [
        {"name": "Main Image", "image": main_image}

    ]
    
    # Store all reference files for variations
    st.session_state.reference_files_stored = all_reference_images


    all_images = [img for img in [main_image] if img is not None]
    


# 12) Interactive variation generator - OUTSIDE generate_btn block
if 'generated_images' in st.session_state and st.session_state.generated_images:
    st.markdown("---")
    st.subheader("🎨 Generate Custom Variations")

    st.markdown("""
    Create additional variations using any of your generated images as a reference.
    This lets you iterate and explore different creative directions.
    """)

    col_base, col_prompt = st.columns([1, 2])

    with col_base:
        # Select base image
        base_image_options = [img["name"] for img in st.session_state.generated_images if img["image"] is not None]
        
        if base_image_options:
            selected_base = st.selectbox(
                "Use as reference:",
                base_image_options
            )
            
            # Show preview of selected base
            selected_img = next(
                img["image"] for img in st.session_state.generated_images 
                if img["name"] == selected_base
            )
            st.image(selected_img, caption=f"Reference: {selected_base}")

    with col_prompt:
        variation_prompt = st.text_area(
            "Describe your variation:",
            placeholder="Examples:\n- Same outfit but sitting on a bench\n- Add dramatic rim lighting from behind\n- Change to urban rooftop setting at sunset\n- Crop tighter on face and shoulders",
            height=150,
            key="variation_prompt"
        )
        
        include_ref = st.checkbox(
            "Include original reference images for consistency",
            value=True,
            help="Recommended for maintaining model/outfit fidelity"
        )
        
        generate_variation_btn = st.button(
            "✨ Generate Variation",
            type="secondary",
            use_container_width=True
        )

    # Generate custom variation
    if generate_variation_btn and variation_prompt:
        with st.spinner("🎨 Generating custom variation…"):
            
            # Build input list
            input_images = [selected_img]
            if include_ref and 'reference_files_stored' in st.session_state and st.session_state.reference_files_stored:
                input_images.extend(st.session_state.reference_files_stored)
            
            # Enhanced prompt
            enhanced_variation_prompt = (
                f"{variation_prompt}\n\n"
                f"FROM THE REFERENCE IMAGE: Maintain consistency with the model's appearance, outfit, and overall aesthetic. "
                f"{'FROM THE REFERENCE IMAGES: Maintain the model and outfit details. ' if include_ref else ''}"
                f"Apply the requested changes while keeping everything else consistent. "
                f"Vertical 3:4 aspect ratio, professional fashion editorial quality."
            )
            
            variation_image = generate_image_with_inputs(
                enhanced_variation_prompt,
                input_images
            )
        
        if variation_image:
            st.success("✅ Variation generated!")
            
            col_result, col_download = st.columns([3, 1])
            
            with col_result:
                st.image(variation_image, caption="Custom Variation")
            
            with col_download:
                # Convert to bytes for download
                img_bytes = io.BytesIO()
                variation_image.save(img_bytes, format='PNG')
                
                st.download_button(
                    label="💾 Download",
                    data=img_bytes.getvalue(),
                    file_name=f"variation_{len(st.session_state.generated_images)+1}.png",
                    mime="image/png",
                    use_container_width=True
                )
            
            # Add to session state for future iterations
            st.session_state.generated_images.append({
                "name": f"Custom Variation {len(st.session_state.generated_images)-5}",
                "image": variation_image
            })
            
            st.info("💡 This variation is now available as a reference for generating more variations!")
        else:
            st.error("Failed to generate variation. Please try again.")

    elif generate_variation_btn and not variation_prompt:
        st.warning("⚠️ Please describe the variation you want to generate.")
