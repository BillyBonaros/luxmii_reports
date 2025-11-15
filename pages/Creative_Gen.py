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
    
    # Convert all images to RGB mode to prevent color quantization issues
    # This significantly improves quality by avoiding palette limitations
    rgb_images = []
    for img in images:
        # Convert to RGB if not already
        if img.mode != 'RGB':
            rgb_images.append(img.convert('RGB'))
        else:
            rgb_images.append(img)
    
    # Create a BytesIO object to store the GIF
    gif_bytes = io.BytesIO()
    
    # Save with optimal quality settings
    rgb_images[0].save(
        gif_bytes,
        format='GIF',
        append_images=rgb_images[1:],
        save_all=True,
        duration=duration,
        loop=0,  # Loop forever
        optimize=False,  # Don't optimize - better quality
        disposal=2  # Clear frame before rendering next (smoother transitions)
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
        lossless=True,  # Lossless = perfect quality
        quality=100,
        method=6  # Best compression (0=fast, 6=best)
    )
    
    webp_bytes.seek(0)
    return webp_bytes.getvalue()



def create_zip_bundle(
    main_image: Image.Image,
    pose_image: Image.Image,
    closeup_image: Image.Image,
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
        # Save the three main images as PNGs
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
        
        # Add GIF if provided
        if gif_data:
            zip_file.writestr('04_animation.gif', gif_data)
        
        # Add WebP if provided
        if webp_data:
            zip_file.writestr('05_animation.webp', webp_data)
    
    zip_buffer.seek(0)
    return zip_buffer.getvalue()


def build_main_prompt(
    user_text: str,
    inspiration_desc: Optional[str],
    has_studio_images: bool,
) -> str:
    """
    Build the base text prompt for the first image generation.
    """
    pieces = []

    if user_text:
        pieces.append(f"Creative direction: {user_text}")

    if inspiration_desc:
        pieces.append(
            f"Background & photographic style: {inspiration_desc}"
        )

    if not pieces:
        pieces.append(
            "Create a high-end fashion editorial photo."
        )

    combined = "\n".join(pieces)

    studio_instruction = (
        "Use the model and outfit from the provided studio images. "
        "Recreate this exact person wearing this exact outfit in the new environment."
        if has_studio_images
        else "Create a fashion model in a stylish outfit."
    )

    base_prompt = (
        f"Create a photorealistic fashion photograph.\n"
        f"{studio_instruction}\n\n"
        f"{combined}\n\n"
        "Full-body shot, vertical 3:4 aspect ratio, professional fashion editorial lighting, "
        "shallow depth of field, magazine-quality image."
    )

    return base_prompt

def generate_image_with_inputs(
    prompt: str,
    input_images: List,  # list of PIL Images or UploadedFiles
    model_name: str = "gemini-2.5-flash-image",
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
Upload an **inspiration photo** for background & lighting, plus your **studio images** (model + outfit).  
The app will:
1. Generate a main image combining your model/outfit with the inspiration's environment  
2. Create a different pose using the first generated image (for consistency)  
3. Create a close-up variant using the first generated image
"""
)

# --- Inputs ------------------------------------------------------------------

col_left, col_right = st.columns(2)

with col_left:
    user_description = st.text_area(
        "Additional creative direction (optional)",
        placeholder="e.g., Dramatic fashion editorial, cinematic mood, golden hour lighting...",
        height=100,
    )

    inspiration_file = st.file_uploader(
        "Inspiration image (for background & aesthetics)",
        type=["jpg", "jpeg", "png", "webp"],
    )

with col_right:
    studio_files = st.file_uploader(
        "Your studio images (model + outfit to recreate)",
        type=["jpg", "jpeg", "png", "webp"],
        accept_multiple_files=True,
    )

generate_btn = st.button("✨ Generate with Nano Banana", type="primary")

# --- Main Logic --------------------------------------------------------------

if generate_btn:
    if not inspiration_file and not studio_files:
        st.error("Please provide at least an inspiration image or studio images.")
        st.stop()

    client = get_gemini_client()

    # 1) Analyze inspiration image if provided
    inspiration_desc = None
    if inspiration_file is not None:
        with st.spinner("Analyzing inspiration image style with Gemini…"):
            insp_bytes = inspiration_file.getvalue()
            insp_mime = inspiration_file.type or "image/jpeg"

            inspiration_desc = describe_inspiration_image(
                image_bytes=insp_bytes,
                mime_type=insp_mime,
            )

        with st.expander("📸 Inspiration style description", expanded=False):
            st.write(inspiration_desc or "_No description returned._")

    # 2) Build prompt for first image
    main_prompt = build_main_prompt(
        user_text=user_description or "",
        inspiration_desc=inspiration_desc,
        has_studio_images=bool(studio_files),
    )

    with st.expander("🎯 Generated prompt for main image", expanded=False):
        st.code(main_prompt)

    # 3) Generate FIRST image (with studio images as input)
    with st.spinner("🎨 Generating main image with Nano Banana…"):
        main_image = generate_image_with_inputs(
            main_prompt, 
            studio_files or []
        )

    if not main_image:
        st.error("Failed to generate main image.")
        st.stop()

    # 4) Generate SECOND image (different pose) using the FIRST generated image
    pose_prompt = (
        "Using the provided image, create a variation with the SAME model, outfit, and environment, "
        "but in a clearly different pose and camera angle. "
        "Examples: walking, turning 3/4, shifting weight, different arm position. "
        "Keep all styling, lighting, background and the model's appearance identical. "
        "Only change the pose and camera angle."
    )

    with st.spinner("🎨 Generating different pose (using first image)…"):
        pose_image = generate_image_with_inputs(
            pose_prompt,
            [main_image]  # Use the first generated image as input
        )

    # 5) Generate THIRD image (close-up) using the FIRST generated image
    closeup_prompt = (
        "Using the provided image, create a close-up or mid-shot focusing on the upper body and face. "
        "Keep the SAME model, outfit, lighting style and background aesthetic. "
        "Use a shallower depth of field to blur the background softly. "
        "Show garment details and styling clearly."
    )

    with st.spinner("🎨 Generating close-up (using first image)…"):
        closeup_image = generate_image_with_inputs(
            closeup_prompt,
            [main_image]  # Use the first generated image as input
        )

    # 6) Display results
    st.subheader("✨ Results")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown("**Main Image**")
        if main_image:
            st.image(main_image, use_container_width=True)
        else:
            st.error("No image returned.")

    with col2:
        st.markdown("**Different Pose**")
        if pose_image:
            st.image(pose_image, use_container_width=True)
        else:
            st.error("No image returned.")

    with col3:
        st.markdown("**Close-up Variant**")
        if closeup_image:
            st.image(closeup_image, use_container_width=True)
        else:
            st.error("No image returned.")

    # 7) Create animated files automatically
    st.markdown("---")
    st.subheader("🎬 Animated Downloads")
    
    all_images = [img for img in [main_image, pose_image, closeup_image] if img is not None]
    
    gif_data = None
    webp_data = None
    
    if len(all_images) >= 2:
        col_gif, col_webp = st.columns(2)
        
        with col_gif:
            st.markdown("**GIF Animation**")
            with st.spinner("Creating GIF..."):
                gif_data = create_animated_gif(all_images, duration=500)
            
            # if gif_data:
            #     st.download_button(
            #         label="⬇️ Download GIF",
            #         data=gif_data,
            #         file_name="fashion_animation.gif",
            #         mime="image/gif",
            #         use_container_width=True
                # )
        
        with col_webp:
            st.markdown("**WebP Animation** (Higher Quality)")
            with st.spinner("Creating WebP..."):
                webp_data = create_animated_webp(all_images, duration=500)
            
            # if webp_data:
            #     st.download_button(
            #         label="⬇️ Download WebP",
            #         data=webp_data,
            #         file_name="fashion_animation.webp",
            #         mime="image/webp",
            #         use_container_width=True
            #     )
    else:
        st.warning("Need at least 2 images to create animations.")
    
    # 8) Create ZIP bundle with everything
    st.markdown("---")
    st.subheader("📦 Download Everything")
    
    with st.spinner("Creating ZIP bundle..."):
        zip_data = create_zip_bundle(
            main_image,
            pose_image,
            closeup_image,
            gif_data,
            webp_data
        )
    
    if zip_data:
        st.download_button(
            label="📥 Download Complete Package (ZIP)",
            data=zip_data,
            file_name="fashion_photoshoot_complete.zip",
            mime="application/zip",
            type="primary",
            use_container_width=True
        )
        
        # Show what's included
        with st.expander("📋 Package contents"):
            st.markdown("""
            - `01_main_image.png` - Main full-body shot
            - `02_different_pose.png` - Alternative pose
            - `03_closeup.png` - Close-up detail shot
            - `04_animation.gif` - Animated GIF (256-color)
            - `05_animation.webp` - Animated WebP (high quality)
            """)
