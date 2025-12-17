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


def create_animated_gif(images: List[Image.Image], duration: int = 1000) -> bytes:
    """
    Create a high-quality animated GIF from a list of PIL Images.
    
    Args:
        images: List of PIL Image objects
        duration: Duration of each frame in milliseconds (default 1000ms = 1 second)
    
    Returns:
        bytes: GIF file as bytes for download
    """
    if not images or len(images) == 0:
        return None
    
    rgb_images = []
    for img in images:
        if img.mode != 'RGB':
            rgb_images.append(img.convert('RGB'))
        else:
            rgb_images.append(img)
    
    gif_bytes = io.BytesIO()
    
    rgb_images[0].save(
        gif_bytes,
        format='GIF',
        append_images=rgb_images[1:],
        save_all=True,
        duration=duration,
        loop=0,
        optimize=False,
        disposal=2
    )
    
    gif_bytes.seek(0)
    return gif_bytes.getvalue()


def create_animated_webp(images: List[Image.Image], duration: int = 1000) -> bytes:
    """
    Create a high-quality animated WebP (much better than GIF).
    WebP has no color limitations and supports lossless compression.
    """
    if not images or len(images) == 0:
        return None
    
    webp_bytes = io.BytesIO()
    
    images[0].save(
        webp_bytes,
        format='WebP',
        append_images=images[1:],
        save_all=True,
        duration=duration,
        loop=0,
        lossless=True,
        quality=100,
        method=6
    )
    
    webp_bytes.seek(0)
    return webp_bytes.getvalue()


def create_zip_bundle(
    main_image: Image.Image,
    pose_image: Image.Image,
    closeup_image: Image.Image,
    backshot_image: Image.Image,
    movement_image: Image.Image,
    sideshot_image: Image.Image,
    gif_data: bytes = None,
    webp_data: bytes = None
) -> bytes:
    """
    Create a zip file containing all generated images and animations.
    
    Returns:
        bytes: Zip file as bytes for download
    """
    zip_buffer = io.BytesIO()
    
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        if main_image:
            img_buffer = io.BytesIO()
            main_image.save(img_buffer, format='PNG')
            zip_file.writestr('01_main_image.png', img_buffer.getvalue())
        
        if pose_image:
            img_buffer = io.BytesIO()
            pose_image.save(img_buffer, format='PNG')
            zip_file.writestr('02_different_pose.png', img_buffer.getvalue())
        
        if closeup_image:
            img_buffer = io.BytesIO()
            closeup_image.save(img_buffer, format='PNG')
            zip_file.writestr('03_closeup.png', img_buffer.getvalue())
        
        if backshot_image:
            img_buffer = io.BytesIO()
            backshot_image.save(img_buffer, format='PNG')
            zip_file.writestr('04_backshot.png', img_buffer.getvalue())
        
        if movement_image:
            img_buffer = io.BytesIO()
            movement_image.save(img_buffer, format='PNG')
            zip_file.writestr('05_movement.png', img_buffer.getvalue())
        
        if sideshot_image:
            img_buffer = io.BytesIO()
            sideshot_image.save(img_buffer, format='PNG')
            zip_file.writestr('06_sideshot.png', img_buffer.getvalue())
        
        if gif_data:
            zip_file.writestr('07_animation.gif', gif_data)
        
        if webp_data:
            zip_file.writestr('08_animation.webp', webp_data)
    
    zip_buffer.seek(0)
    return zip_buffer.getvalue()


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
# Streamlit UI
# -----------------------------------------------------------------------------

st.set_page_config(page_title="Nano Banana Outfit Stylist", layout="wide")
st.title("👗 Nano Banana Fashion Generator")

st.markdown(
    """
Define your model and photographic style, then generate a complete fashion photoshoot.
"""
)

# --- Input mode selection ---
st.markdown("---")
input_mode = st.radio(
    "How would you like to define the photographic style?",
    ["📸 Use inspiration image", "✍️ Write custom prompt"],
    horizontal=True
)

# --- Inputs ------------------------------------------------------------------

col_left, col_right = st.columns(2)

with col_left:
    user_description = st.text_area(
        "Additional creative direction (optional)",
        placeholder="e.g., Dramatic fashion editorial, cinematic mood, golden hour lighting...",
        height=100,
    )

    if input_mode == "📸 Use inspiration image":
        inspiration_file = st.file_uploader(
            "Inspiration image (for background & aesthetics)",
            type=["jpg", "jpeg", "png", "webp"],
        )
        custom_style_prompt = None
    else:  # Custom prompt mode
        custom_style_prompt = st.text_area(
            "Describe the photographic style",
            placeholder="e.g., Shot against a minimalist concrete wall, soft natural window light from the left, moody atmosphere with cool gray tones, shallow depth of field, film photography aesthetic",
            height=150,
        )
        inspiration_file = None

with col_right:
    # Model reference photos (NEW)
    st.markdown("**Define Your Model**")
    
    model_mode = st.radio(
        "Choose how to define the model:",
        ["📷 Upload model reference photos", "👤 Studio images include model"],
        horizontal=True,
        help="Upload 1-5 photos of the person you want as your model, OR use studio images that already show your model in the outfit"
    )
    
    model_reference_files = None
    studio_files = None
    outfit_files = None
    
    if model_mode == "📷 Upload model reference photos":
        model_reference_files = st.file_uploader(
            "Model reference photos (1-5 images of the person)",
            type=["jpg", "jpeg", "png", "webp"],
            accept_multiple_files=True,
            help="Upload clear photos of the model's face from different angles"
        )
        
        if model_reference_files and len(model_reference_files) > 5:
            st.warning("⚠️ Maximum 5 reference photos recommended for best results")
            model_reference_files = model_reference_files[:5]
        
        outfit_files = st.file_uploader(
            "Outfit reference images (optional)",
            type=["jpg", "jpeg", "png", "webp"],
            accept_multiple_files=True,
            help="Upload images showing the outfit you want the model to wear"
        )
    else:
        studio_files = st.file_uploader(
            "Studio images (model + outfit together)",
            type=["jpg", "jpeg", "png", "webp"],
            accept_multiple_files=True,
            help="Images showing both your model and the outfit"
        )

generate_btn = st.button("✨ Generate with Nano Banana", type="primary")

# --- Main Logic --------------------------------------------------------------

if generate_btn:
    # Validation
    if model_mode == "📷 Upload model reference photos":
        if not model_reference_files:
            st.error("Please upload at least one model reference photo.")
            st.stop()
    else:
        if not studio_files:
            st.error("Please upload studio images showing your model and outfit.")
            st.stop()
    
    if input_mode == "📸 Use inspiration image" and not inspiration_file:
        st.error("Please provide an inspiration image.")
        st.stop()
    elif input_mode == "✍️ Write custom prompt" and not custom_style_prompt:
        st.error("Please provide a custom style prompt.")
        st.stop()

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
    if model_mode == "📷 Upload model reference photos":
        studio_instruction = (
            f"PERSON TO RECREATE: The first {len(model_reference_files)} reference images show the model. "
            f"Use their EXACT facial features, skin tone, hair, and body type. "
            f"{'OUTFIT TO USE: The remaining reference images show the outfit to dress them in. ' if outfit_files else 'Create a stylish high-fashion outfit. '}"
            "Combine the person with the outfit in the new photographic environment."
        )
    else:
        studio_instruction = (
            "Use the model and outfit from the provided studio images. "
            "Recreate this exact person wearing this exact outfit in the new environment."
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
        if outfit_files:
            all_reference_images.extend(outfit_files)
        if studio_files:
            all_reference_images.extend(studio_files)
        
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
            st.image(main_image, use_container_width=True)
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

    # 11) ZIP bundle
    st.markdown("---")
    st.subheader("📦 Download Everything")
    
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
            st.image(selected_img, caption=f"Reference: {selected_base}", use_container_width=True)

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
                st.image(variation_image, caption="Custom Variation", use_container_width=True)
            
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
