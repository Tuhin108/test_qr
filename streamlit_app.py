"""
QR Code Generator with Streamlit-based Redirect Service
Includes Auto-Push Analytics to GitHub and in-app Dashboard.
"""

import os
import json
import uuid
import base64
import io
import logging
import requests
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Optional, Any, cast
from pathlib import Path

import segno
from PIL import Image, ImageEnhance, ImageFilter
import streamlit as st
import streamlit.components.v1 as components

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
DATA_FILE = "s.json"
MAX_EXPIRY_DAYS = 7

BASE_URL = os.getenv("BASE_URL", "")


# ============================================================================
# REDIRECT HANDLING (Streamlit-based)
# ============================================================================

def handle_redirect():
    """Check for redirect parameter and perform redirect using JavaScript"""
    query_params = st.query_params

    if "r" in query_params:
        target_url = query_params["r"]
        token = query_params.get("t", None)

        if token:
            redirect_data = get_redirect(token)
            if redirect_data:
                increment_scan_count(token)
                target_url = redirect_data["url"]
            else:
                show_expired_page()
                return

        st.title("🚀 Redirecting...")
        st.info(f"Taking you to: **{target_url}**")

        st.write("If Your Target app doesn't open automatically, click below:")
        st.link_button("Open Link", target_url, type="primary", use_container_width=True)

        components.html(
            f"""
            <script>
                window.top.location.href = "{target_url}";
            </script>
            """,
            height=0,
            width=0
        )

        st.stop()


def show_expired_page():
    """Show expired/invalid QR code page"""
    st.markdown("""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {
                    font-family: Arial, sans-serif;
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    height: 100vh;
                    margin: 0;
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                }
                .container {
                    background: white;
                    padding: 40px;
                    border-radius: 10px;
                    box-shadow: 0 10px 40px rgba(0,0,0,0.2);
                    text-align: center;
                    max-width: 400px;
                }
                h1 { color: #e53e3e; margin-bottom: 20px; }
                p { color: #4a5568; line-height: 1.6; }
            </style>
        </head>
        <body>
            <div class="container">
                <h1>⚠️ Invalid or Expired</h1>
                <p>This QR code has either expired or does not exist.</p>
                <p>Please contact the QR code creator for a new link.</p>
            </div>
        </body>
        </html>
    """, unsafe_allow_html=True)
    st.stop()


# ============================================================================
# JSON DATA MANAGEMENT (WITH GITHUB AUTO-PUSH)
# ============================================================================

def load_data() -> dict:
    """Load redirect data from JSON file"""
    if not Path(DATA_FILE).exists():
        return {}

    try:
        with open(DATA_FILE, 'r') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        logger.error(f"Failed to load data: {e}")
        return {}


def save_data(data: dict):
    """Save redirect data locally AND push to GitHub automatically"""
    try:
        with open(DATA_FILE, 'w') as f:
            json.dump(data, f, indent=2)
    except IOError as e:
        logger.error(f"Failed to save data locally: {e}")

    try:
        if "GITHUB_TOKEN" in st.secrets:
            github_token = st.secrets["GITHUB_TOKEN"]

            repo = "Tuhin108/qr-forge"
            path = "analytics.json"
            url = f"https://api.github.com/repos/{repo}/contents/{path}"
            headers = {"Authorization": f"token {github_token}"}

            get_resp = requests.get(url, headers=headers)
            sha = get_resp.json().get("sha") if get_resp.status_code == 200 else None

            encoded_content = base64.b64encode(json.dumps(data, indent=2).encode()).decode()
            payload = {
                "message": "📊 Auto-updating QR scan analytics",
                "content": encoded_content
            }
            if sha:
                payload["sha"] = sha

            requests.put(url, headers=headers, json=payload)

    except Exception as e:
        logger.error(f"Failed to push to GitHub: {e}")


def store_redirect(token: str, url: str, expiry_minutes: int) -> dict:
    """Store a redirect mapping in JSON"""
    created_at = datetime.utcnow()
    expires_at = created_at + timedelta(minutes=expiry_minutes)

    data = load_data()
    data[token] = {
        "url": url,
        "created_at": created_at.isoformat(),
        "expires_at": expires_at.isoformat(),
        "scan_count": 0
    }
    save_data(data)

    return {
        "token": token,
        "url": url,
        "created_at": created_at.isoformat(),
        "expires_at": expires_at.isoformat()
    }


def get_redirect(token: str) -> Optional[dict]:
    """Retrieve redirect data and check expiry"""
    data = load_data()

    if token not in data:
        return None

    redirect = data[token]
    expires_at = datetime.fromisoformat(redirect["expires_at"])

    if datetime.utcnow() > expires_at:
        return None

    return redirect


def increment_scan_count(token: str):
    """Increment the scan counter for a token"""
    data = load_data()

    if token in data:
        data[token]["scan_count"] = data[token].get("scan_count", 0) + 1
        save_data(data)


# ============================================================================
# QR CODE GENERATION
# ============================================================================

def validate_url(url: str) -> bool:
    """Validate URL format"""
    return url.startswith(("http://", "https://"))


def generate_qr_code(
    data: str,
    fg_color: str = "#000000",
    bg_color: str = "#ffffff",
    error_level: str = "M",
    logo_image: Optional[Image.Image] = None,
    background_image: Optional[Image.Image] = None,
    scale: int = 10
) -> tuple[bytes, bytes]:
    """Generate QR code with custom styling, optional background, and optional logo"""
    error_map = {"L": "l", "M": "m", "Q": "q", "H": "h"}
    error = error_map.get(error_level.upper(), "m")

    qr = segno.make(data, error=error)

    png_buffer = io.BytesIO()
    qr.save(png_buffer, kind="png", scale=scale, dark=fg_color, light=bg_color)
    png_buffer.seek(0)

    qr_image = Image.open(png_buffer).convert("RGBA")

    if background_image:
        bg = background_image.convert("RGBA").resize(qr_image.size)
        qr_image = Image.blend(bg, qr_image, alpha=0.65)

    if logo_image:
        qr_image = add_logo_to_qr(qr_image, logo_image)

    png_buffer = io.BytesIO()
    qr_image.save(png_buffer, format="PNG")
    png_buffer.seek(0)

    png_bytes = png_buffer.getvalue()

    svg_buffer = io.BytesIO()
    qr.save(svg_buffer, kind="svg", scale=4, dark=fg_color, light=bg_color)
    svg_buffer.seek(0)
    svg_bytes = svg_buffer.getvalue()

    return png_bytes, svg_bytes


def add_logo_to_qr(qr_image: Image.Image, logo: Image.Image) -> Image.Image:
    """Add centered logo to QR code"""
    qr_width, qr_height = qr_image.size
    max_logo_size = int(min(qr_width, qr_height) * 0.25)

    logo.thumbnail((max_logo_size, max_logo_size), Image.Resampling.LANCZOS)

    if logo.mode != "RGBA":
        logo = logo.convert("RGBA")

    logo_pos = (
        (qr_width - logo.width) // 2,
        (qr_height - logo.height) // 2
    )

    logo_bg = Image.new("RGBA", logo.size, cast(Any, (255, 255, 255, 255)))
    logo_bg.paste(logo, (0, 0), logo)
    qr_image.paste(logo_bg, logo_pos, logo_bg)

    return qr_image


# ============================================================================
# ARTISTIC IMAGE-TO-QR GENERATION
# ============================================================================

def generate_artistic_qr(
    qr_data: str,
    art_image: Image.Image,
    error_level: str = "H",
    blend_mode: str = "Multiply",
    contrast: float = 1.4,
    protect_finders: bool = True,
) -> bytes:
    """
    Generate an artistic QR code where the uploaded image is woven into
    the QR pattern itself — dark modules take the image's dark tones,
    light modules take the image's light tones, producing a scannable
    image-embedded QR code.
    """
    error_map = {"L": "l", "M": "m", "Q": "q", "H": "h"}
    error = error_map.get(error_level.upper(), "h")

    # Generate base QR at large scale for quality
    qr = segno.make(qr_data, error=error)

    scale = 12
    png_buffer = io.BytesIO()
    qr.save(png_buffer, kind="png", scale=scale, dark="#000000", light="#ffffff")
    png_buffer.seek(0)

    qr_base = Image.open(png_buffer).convert("RGB")
    qr_size = qr_base.size  # (W, H)

    # Prepare the art image
    art = art_image.convert("RGB").resize(qr_size, Image.Resampling.LANCZOS)

    # Boost contrast so the image reads through the QR pattern
    art = ImageEnhance.Contrast(art).enhance(contrast)
    art = ImageEnhance.Sharpness(art).enhance(1.5)

    # Convert both to numpy arrays
    qr_arr = np.array(qr_base, dtype=np.float32)
    art_arr = np.array(art, dtype=np.float32)

    # Build mask from QR: dark pixels = 1, light pixels = 0
    qr_gray = np.mean(qr_arr, axis=2)
    dark_mask = (qr_gray < 128).astype(np.float32)
    light_mask = 1.0 - dark_mask

    dark_mask3  = np.stack([dark_mask]  * 3, axis=2)
    light_mask3 = np.stack([light_mask] * 3, axis=2)

    if blend_mode == "Multiply":
        dark_result  = art_arr * dark_mask3 * 0.55
        light_result = (art_arr * 0.55 + 120) * light_mask3
        result = dark_result + light_result

    elif blend_mode == "Grayscale overlay":
        art_gray = np.mean(art_arr, axis=2, keepdims=True)
        art_gray3 = np.repeat(art_gray, 3, axis=2)
        dark_result  = art_gray3 * dark_mask3 * 0.5
        light_result = (art_gray3 * 0.4 + 130) * light_mask3
        result = dark_result + light_result

    elif blend_mode == "Colorful":
        dark_result  = art_arr * dark_mask3 * 0.45
        light_result = np.clip(art_arr * 0.3 + 160, 0, 255) * light_mask3
        result = dark_result + light_result

    else:  # Classic blend
        dark_result  = art_arr * dark_mask3 * 0.6
        light_result = (255 - (255 - art_arr) * 0.35) * light_mask3
        result = dark_result + light_result

    result = np.clip(result, 0, 255).astype(np.uint8)
    output = Image.fromarray(result, "RGB")

    # Protect finder patterns (3 corner squares) for scannability
    if protect_finders:
        qr_module_count = qr.symbol_size()[0]
        module_px = qr_size[0] // qr_module_count
        quiet = module_px

        finder_px = 7 * module_px
        corners = [
            (quiet, quiet),
            (qr_size[0] - quiet - finder_px, quiet),
            (quiet, qr_size[1] - quiet - finder_px),
        ]

        qr_base_arr = np.array(qr_base, dtype=np.uint8)
        out_arr = np.array(output, dtype=np.uint8)

        for (cx, cy) in corners:
            x1, y1 = cx, cy
            x2 = min(cx + finder_px, qr_size[0])
            y2 = min(cy + finder_px, qr_size[1])
            out_arr[y1:y2, x1:x2] = qr_base_arr[y1:y2, x1:x2]

        output = Image.fromarray(out_arr, "RGB")

    # Subtle sharpening pass for crispness
    output = output.filter(ImageFilter.UnsharpMask(radius=1, percent=120, threshold=3))

    buf = io.BytesIO()
    output.save(buf, format="PNG", optimize=True)
    buf.seek(0)
    return buf.getvalue()


# ============================================================================
# STREAMLIT UI
# ============================================================================

st.set_page_config(
    page_title="QR Forge",
    page_icon="🎯",
    layout="wide"
)

# Check for redirect first
handle_redirect()

st.title("🎯 QR Forge")
st.markdown("Generate custom QR codes with expiry-based redirects")

# Tabs
tab_gen, tab_art = st.tabs(["✏️ Generate QR", "🖼️ Image → QR"])


# ============================================================================
# TAB 1 — Standard QR Generator (unchanged)
# ============================================================================
with tab_gen:
    col1, col2 = st.columns([1, 1])

    with col1:
        st.subheader("Configuration")

        url = st.text_input(
            "Target URL",
            placeholder="https://example.com",
            help="The URL where the QR code will redirect",
            key="gen_url"
        )

        col_a, col_b = st.columns(2)
        with col_a:
            fg_color = st.color_picker("Foreground Color", "#000000")
        with col_b:
            bg_color = st.color_picker("Background Color", "#ffffff")

        error_level = st.selectbox(
            "Error Correction Level",
            ["L", "M", "Q", "H"],
            index=1,
            help="L=7%, M=15%, Q=25%, H=30% error correction"
        )

        expiry_minutes = st.slider(
            "Expiry Time (minutes)",
            min_value=1,
            max_value=MAX_EXPIRY_DAYS * 24 * 60,
            value=60,
            help=f"Max {MAX_EXPIRY_DAYS} days"
        )

        scale = st.slider(
            "QR Code Scale (size)",
            min_value=5,
            max_value=20,
            value=10,
            help="Higher = larger image"
        )

        bg_file = st.file_uploader(
            "Background Picture (Optional)",
            type=["png", "jpg", "jpeg"],
            help="Upload an image to mix into the whole QR code"
        )

        logo_file = st.file_uploader(
            "Logo (Optional)",
            type=["png", "jpg", "jpeg"],
            help="Upload a logo to overlay on the center of the QR code"
        )

        generate_btn = st.button("🎨 Generate QR Code", type="primary", use_container_width=True)

    with col2:
        st.subheader("Generated QR Code")

        if generate_btn:
            if not url:
                st.error("❌ Please enter a target URL")
            elif not validate_url(url):
                st.error("❌ URL must start with http:// or https://")
            else:
                with st.spinner("Generating QR code..."):
                    try:
                        token = str(uuid.uuid4())
                        redirect_data = store_redirect(token, url, expiry_minutes)

                        if BASE_URL:
                            app_base = BASE_URL
                        else:
                            app_base = "https://qr-forge.streamlit.app"

                        import urllib.parse
                        encoded_url = urllib.parse.quote(url, safe='')
                        redirect_url = f"{app_base}?r={encoded_url}&t={token}"

                        background_image = None
                        if bg_file is not None:
                            try:
                                background_image = Image.open(bg_file)
                            except Exception as e:
                                st.error(f"❌ Invalid background image: {str(e)}")

                        logo_image = None
                        if logo_file is not None:
                            try:
                                logo_image = Image.open(logo_file)
                            except Exception as e:
                                st.error(f"❌ Invalid logo image: {str(e)}")

                        png_bytes, svg_bytes = generate_qr_code(
                            redirect_url, fg_color, bg_color, error_level,
                            logo_image, background_image, scale
                        )

                        st.image(png_bytes, use_container_width=True)

                        expires_at = datetime.fromisoformat(redirect_data["expires_at"])
                        st.success("✅ QR Code Generated Successfully!")

                        st.markdown(f"""
                        **Redirect URL:** `{redirect_url}`
                        **Token:** `{token}`
                        **Expires:** {expires_at.strftime('%Y-%m-%d %H:%M:%S')} UTC
                        **Target URL:** {url}
                        """)

                        col_d1, col_d2 = st.columns(2)
                        with col_d1:
                            st.download_button(
                                "📥 Download PNG",
                                data=png_bytes,
                                file_name=f"qr_{token}.png",
                                mime="image/png",
                                use_container_width=True
                            )
                        with col_d2:
                            st.download_button(
                                "📥 Download SVG",
                                data=svg_bytes,
                                file_name=f"qr_{token}.svg",
                                mime="image/svg+xml",
                                use_container_width=True
                            )

                    except Exception as e:
                        st.error(f"❌ Error generating QR code: {str(e)}")


# ============================================================================
# TAB 2 — Artistic Image → QR
# ============================================================================
with tab_art:
    st.subheader("🖼️ Embed an Image into Your QR Code")
    st.markdown(
        "Upload any image and it will be woven into the QR pattern — "
        "the result is fully scannable while the image remains visible inside the code."
    )

    art_col1, art_col2 = st.columns([1, 1])

    with art_col1:
        art_url = st.text_input(
            "Target URL",
            placeholder="https://example.com",
            help="The URL this QR code will redirect to",
            key="art_url"
        )

        art_image_file = st.file_uploader(
            "Upload Image",
            type=["png", "jpg", "jpeg", "webp"],
            help="The image to embed inside the QR code pattern",
            key="art_image"
        )

        art_error = st.selectbox(
            "Error Correction Level",
            ["M", "Q", "H"],
            index=2,
            help="Higher correction = more resilient QR (recommended for artistic QR)",
            key="art_error"
        )

        art_blend = st.selectbox(
            "Blend Style",
            ["Multiply", "Colorful", "Grayscale overlay", "Classic blend"],
            index=0,
            help="How the image colors are merged with the QR pattern"
        )

        art_contrast = st.slider(
            "Image Contrast",
            min_value=0.8,
            max_value=2.5,
            value=1.4,
            step=0.1,
            help="Higher contrast makes the image stand out more"
        )

        art_expiry = st.slider(
            "Expiry Time (minutes)",
            min_value=1,
            max_value=MAX_EXPIRY_DAYS * 24 * 60,
            value=60,
            key="art_expiry"
        )

        art_btn = st.button("🎨 Generate Artistic QR", type="primary", use_container_width=True)

    with art_col2:
        st.subheader("Result")

        if art_btn:
            if not art_url:
                st.error("❌ Please enter a target URL")
            elif not validate_url(art_url):
                st.error("❌ URL must start with http:// or https://")
            elif art_image_file is None:
                st.error("❌ Please upload an image")
            else:
                with st.spinner("Crafting your artistic QR code..."):
                    try:
                        token = str(uuid.uuid4())
                        redirect_data = store_redirect(token, art_url, art_expiry)

                        app_base = BASE_URL if BASE_URL else "https://qr-forge.streamlit.app"
                        import urllib.parse
                        encoded_url = urllib.parse.quote(art_url, safe='')
                        redirect_url = f"{app_base}?r={encoded_url}&t={token}"

                        art_image = Image.open(art_image_file)

                        png_bytes = generate_artistic_qr(
                            qr_data=redirect_url,
                            art_image=art_image,
                            error_level=art_error,
                            blend_mode=art_blend,
                            contrast=art_contrast,
                            protect_finders=True,
                        )

                        st.image(png_bytes, use_container_width=True)

                        expires_at = datetime.fromisoformat(redirect_data["expires_at"])
                        st.success("✅ Artistic QR Generated!")

                        st.markdown(f"""
                        **Token:** `{token}`
                        **Expires:** {expires_at.strftime('%Y-%m-%d %H:%M:%S')} UTC
                        **Target URL:** {art_url}
                        """)

                        st.info(
                            "💡 **Tip:** Test scannability with your phone camera before distributing. "
                            "If it doesn't scan, try increasing Error Correction to **H** or reducing contrast."
                        )

                        st.download_button(
                            "📥 Download Artistic QR (PNG)",
                            data=png_bytes,
                            file_name=f"art_qr_{token}.png",
                            mime="image/png",
                            use_container_width=True
                        )

                    except Exception as e:
                        st.error(f"❌ Error generating artistic QR: {str(e)}")

        else:
            st.markdown(
                """
                <div style="
                    border: 2px dashed #cbd5e0;
                    border-radius: 12px;
                    height: 320px;
                    display: flex;
                    flex-direction: column;
                    align-items: center;
                    justify-content: center;
                    color: #a0aec0;
                    font-size: 15px;
                    text-align: center;
                    padding: 20px;
                ">
                    <div style="font-size: 48px; margin-bottom: 12px;">🖼️</div>
                    <div>Upload an image and enter a URL<br>to generate your artistic QR code</div>
                </div>
                """,
                unsafe_allow_html=True
            )


# ============================================================================
# FOOTER
# ============================================================================
st.divider()

st.markdown(
    """
    <div style='text-align: center; margin-top: 20px;'>
        <p style='color: #4a5568; font-size: 16px;'>Built with ❤️ by <b>Tuhin Kumar Singha Roy</b></p>
        <p>
            <a href="https://www.linkedin.com/in/tuhininaiml" target="_blank"
               style="text-decoration: none; margin-right: 15px; color: #0077B5; font-weight: bold;">
               🔗 LinkedIn
            </a>
            <a href="https://github.com/Tuhin108" target="_blank"
               style="text-decoration: none; color: #333; font-weight: bold;">
               💻 GitHub
            </a>
        </p>
    </div>
    """,
    unsafe_allow_html=True
)
