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
from PIL import Image, ImageEnhance, ImageFilter, ImageDraw
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
            f"""<script>window.top.location.href = "{target_url}";</script>""",
            height=0, width=0
        )
        st.stop()


def show_expired_page():
    """Show expired/invalid QR code page"""
    st.markdown("""
        <!DOCTYPE html><html><head><style>
        body { font-family: Arial, sans-serif; display: flex; justify-content: center;
               align-items: center; height: 100vh; margin: 0;
               background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); }
        .container { background: white; padding: 40px; border-radius: 10px;
                     box-shadow: 0 10px 40px rgba(0,0,0,0.2); text-align: center; max-width: 400px; }
        h1 { color: #e53e3e; margin-bottom: 20px; }
        p { color: #4a5568; line-height: 1.6; }
        </style></head><body><div class="container">
        <h1>⚠️ Invalid or Expired</h1>
        <p>This QR code has either expired or does not exist.</p>
        <p>Please contact the QR code creator for a new link.</p>
        </div></body></html>
    """, unsafe_allow_html=True)
    st.stop()


# ============================================================================
# JSON DATA MANAGEMENT (WITH GITHUB AUTO-PUSH)
# ============================================================================

def load_data() -> dict:
    if not Path(DATA_FILE).exists():
        return {}
    try:
        with open(DATA_FILE, 'r') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        logger.error(f"Failed to load data: {e}")
        return {}


def save_data(data: dict):
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
            payload = {"message": "📊 Auto-updating QR scan analytics", "content": encoded_content}
            if sha:
                payload["sha"] = sha
            requests.put(url, headers=headers, json=payload)
    except Exception as e:
        logger.error(f"Failed to push to GitHub: {e}")


def store_redirect(token: str, url: str, expiry_minutes: int) -> dict:
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
    return {"token": token, "url": url,
            "created_at": created_at.isoformat(), "expires_at": expires_at.isoformat()}


def get_redirect(token: str) -> Optional[dict]:
    data = load_data()
    if token not in data:
        return None
    redirect = data[token]
    expires_at = datetime.fromisoformat(redirect["expires_at"])
    if datetime.utcnow() > expires_at:
        return None
    return redirect


def increment_scan_count(token: str):
    data = load_data()
    if token in data:
        data[token]["scan_count"] = data[token].get("scan_count", 0) + 1
        save_data(data)


# ============================================================================
# STANDARD QR CODE GENERATION
# ============================================================================

def validate_url(url: str) -> bool:
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
    png_bytes = png_buffer.getvalue()

    svg_buffer = io.BytesIO()
    qr.save(svg_buffer, kind="svg", scale=4, dark=fg_color, light=bg_color)
    svg_bytes = svg_buffer.getvalue()

    return png_bytes, svg_bytes


def add_logo_to_qr(qr_image: Image.Image, logo: Image.Image) -> Image.Image:
    qr_width, qr_height = qr_image.size
    max_logo_size = int(min(qr_width, qr_height) * 0.25)
    logo.thumbnail((max_logo_size, max_logo_size), Image.Resampling.LANCZOS)
    if logo.mode != "RGBA":
        logo = logo.convert("RGBA")
    logo_pos = ((qr_width - logo.width) // 2, (qr_height - logo.height) // 2)
    logo_bg = Image.new("RGBA", logo.size, cast(Any, (255, 255, 255, 255)))
    logo_bg.paste(logo, (0, 0), logo)
    qr_image.paste(logo_bg, logo_pos, logo_bg)
    return qr_image


# ============================================================================
# ARTISTIC IMAGE → QR  (module-by-module pixel coloring)
# ============================================================================

def _is_finder_or_separator(row: int, col: int, n: int) -> bool:
    """
    Returns True if (row, col) falls inside one of the three finder patterns
    or their separator zones (8x8 area in each corner).
    """
    margin = 8  # 7-module finder + 1-module separator
    in_tl = row < margin and col < margin
    in_tr = row < margin and col >= (n - margin)
    in_bl = row >= (n - margin) and col < margin
    return in_tl or in_tr or in_bl


def generate_artistic_qr(
    qr_data: str,
    art_image: Image.Image,
    error_level: str = "H",
    module_style: str = "Square",
    bg_style: str = "White",
    saturation: float = 1.3,
    module_size: int = 16,
) -> bytes:
    """
    True image-into-QR technique:
    - Each QR module is drawn as a colored square/dot/rounded tile.
    - The color of every dark module is sampled from the corresponding
      pixel of the art image — making the QR pattern visually read as
      the image when viewed from a distance.
    - Light (background) modules are drawn white / transparent / or a
      very light tint of the image — keeping the QR scannable.
    - Finder patterns are always kept clean black-on-white.
    """
    error_map = {"L": "l", "M": "m", "Q": "q", "H": "h"}
    error = error_map.get(error_level.upper(), "h")

    qr = segno.make(qr_data, error=error)

    # --- Get the raw module matrix ---
    # segno's matrix is a tuple of bytearrays; non-zero = dark module
    matrix = list(qr.matrix)
    n_rows = len(matrix)
    n_cols = len(matrix[0]) if n_rows else 0

    # Canvas size in pixels
    canvas_w = n_cols * module_size
    canvas_h = n_rows * module_size

    # --- Prepare art image: resize to exactly (n_cols, n_rows) so each
    #     pixel maps 1-to-1 onto one QR module ---
    art = art_image.convert("RGB")
    art = ImageEnhance.Contrast(art).enhance(1.2)
    art = ImageEnhance.Saturation(art).enhance(saturation)
    art_small = art.resize((n_cols, n_rows), Image.Resampling.LANCZOS)
    art_pixels = np.array(art_small, dtype=np.uint8)   # shape (n_rows, n_cols, 3)

    # --- Create output canvas ---
    if bg_style == "Transparent":
        canvas = Image.new("RGBA", (canvas_w, canvas_h), (255, 255, 255, 0))
    else:
        canvas = Image.new("RGB", (canvas_w, canvas_h), (255, 255, 255))

    draw = ImageDraw.Draw(canvas)

    for r in range(n_rows):
        for c in range(n_cols):
            is_dark = matrix[r][c] != 0

            x0 = c * module_size
            y0 = r * module_size
            x1 = x0 + module_size - 1
            y1 = y0 + module_size - 1

            if _is_finder_or_separator(r, c, n_rows):
                # ── Finder / separator: keep clean black or white ──
                color = (0, 0, 0) if is_dark else (255, 255, 255)
                draw.rectangle([x0, y0, x1, y1], fill=color)

            elif is_dark:
                # ── Dark data module: color from art image ──
                pr, pg, pb = int(art_pixels[r, c, 0]), int(art_pixels[r, c, 1]), int(art_pixels[r, c, 2])

                # Darken slightly so modules stay readable
                factor = 0.75
                pr, pg, pb = int(pr * factor), int(pg * factor), int(pb * factor)
                color = (pr, pg, pb)

                if module_style == "Circle":
                    draw.ellipse([x0, y0, x1, y1], fill=color)
                elif module_style == "Rounded":
                    radius = module_size // 3
                    draw.rounded_rectangle([x0, y0, x1, y1], radius=radius, fill=color)
                else:  # Square
                    draw.rectangle([x0, y0, x1, y1], fill=color)

            else:
                # ── Light module: background treatment ──
                if bg_style == "Image tint":
                    pr, pg, pb = int(art_pixels[r, c, 0]), int(art_pixels[r, c, 1]), int(art_pixels[r, c, 2])
                    # Very light wash — blend toward white
                    pr = int(pr * 0.15 + 255 * 0.85)
                    pg = int(pg * 0.15 + 255 * 0.85)
                    pb = int(pb * 0.15 + 255 * 0.85)
                    draw.rectangle([x0, y0, x1, y1], fill=(pr, pg, pb))
                elif bg_style == "Transparent":
                    # Leave transparent (already set on canvas)
                    pass
                else:  # White
                    draw.rectangle([x0, y0, x1, y1], fill=(255, 255, 255))

    # Light sharpening for crisp module edges
    if bg_style != "Transparent":
        canvas = canvas.filter(ImageFilter.UnsharpMask(radius=0.8, percent=100, threshold=2))

    buf = io.BytesIO()
    fmt = "PNG"
    canvas.save(buf, format=fmt, optimize=True)
    buf.seek(0)
    return buf.getvalue()


# ============================================================================
# STREAMLIT UI
# ============================================================================

st.set_page_config(page_title="QR Forge", page_icon="🎯", layout="wide")

handle_redirect()

st.title("🎯 QR Forge")
st.markdown("Generate custom QR codes with expiry-based redirects")

tab_gen, tab_art = st.tabs(["✏️ Generate QR", "🖼️ Image → QR"])


# ============================================================================
# TAB 1 — Standard QR Generator
# ============================================================================
with tab_gen:
    col1, col2 = st.columns([1, 1])

    with col1:
        st.subheader("Configuration")
        url = st.text_input("Target URL", placeholder="https://example.com",
                            help="The URL where the QR code will redirect", key="gen_url")

        col_a, col_b = st.columns(2)
        with col_a:
            fg_color = st.color_picker("Foreground Color", "#000000")
        with col_b:
            bg_color = st.color_picker("Background Color", "#ffffff")

        error_level = st.selectbox("Error Correction Level", ["L", "M", "Q", "H"], index=1,
                                   help="L=7%, M=15%, Q=25%, H=30% error correction")
        expiry_minutes = st.slider("Expiry Time (minutes)", min_value=1,
                                   max_value=MAX_EXPIRY_DAYS * 24 * 60, value=60)
        scale = st.slider("QR Code Scale (size)", min_value=5, max_value=20, value=10)
        bg_file = st.file_uploader("Background Picture (Optional)", type=["png", "jpg", "jpeg"])
        logo_file = st.file_uploader("Logo (Optional)", type=["png", "jpg", "jpeg"])
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
                        app_base = BASE_URL if BASE_URL else "https://qr-forge.streamlit.app"
                        import urllib.parse
                        encoded_url = urllib.parse.quote(url, safe='')
                        redirect_url = f"{app_base}?r={encoded_url}&t={token}"

                        background_image = Image.open(bg_file) if bg_file else None
                        logo_image = Image.open(logo_file) if logo_file else None

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
                            st.download_button("📥 Download PNG", data=png_bytes,
                                               file_name=f"qr_{token}.png", mime="image/png",
                                               use_container_width=True)
                        with col_d2:
                            st.download_button("📥 Download SVG", data=svg_bytes,
                                               file_name=f"qr_{token}.svg", mime="image/svg+xml",
                                               use_container_width=True)
                    except Exception as e:
                        st.error(f"❌ Error generating QR code: {str(e)}")


# ============================================================================
# TAB 2 — Artistic Image → QR
# ============================================================================
with tab_art:
    st.subheader("🖼️ Turn Your Image into a QR Code")
    st.markdown(
        "Upload any image — its colors are mapped **module by module** onto the QR pattern. "
        "The result looks like your image made of QR pixels, and is fully scannable."
    )

    art_col1, art_col2 = st.columns([1, 1])

    with art_col1:
        art_url = st.text_input("Target URL", placeholder="https://example.com",
                                help="The URL this QR code will redirect to", key="art_url")

        art_image_file = st.file_uploader("Upload Image", type=["png", "jpg", "jpeg", "webp"],
                                          help="This image's colors will fill the QR modules",
                                          key="art_image")

        art_error = st.selectbox(
            "Error Correction Level", ["M", "Q", "H"], index=2,
            help="H = 30% damage tolerance — recommended for artistic QR codes",
            key="art_error"
        )

        art_module_style = st.selectbox(
            "Module Shape",
            ["Square", "Circle", "Rounded"],
            index=0,
            help="Shape of each QR module tile"
        )

        art_bg = st.selectbox(
            "Background Style",
            ["White", "Image tint", "Transparent"],
            index=0,
            help="White = clean scannable background | Image tint = subtle color wash | Transparent = PNG with alpha"
        )

        art_saturation = st.slider(
            "Color Saturation", min_value=0.5, max_value=2.5, value=1.3, step=0.1,
            help="Boost image colors so they show clearly in the modules"
        )

        art_module_px = st.slider(
            "Module Size (px)", min_value=8, max_value=24, value=16, step=2,
            help="Pixel size of each QR module — larger = higher resolution output"
        )

        art_expiry = st.slider("Expiry Time (minutes)", min_value=1,
                               max_value=MAX_EXPIRY_DAYS * 24 * 60, value=60, key="art_expiry")

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
                with st.spinner("Mapping image colors onto QR modules…"):
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
                            module_style=art_module_style,
                            bg_style=art_bg,
                            saturation=art_saturation,
                            module_size=art_module_px,
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
                            "💡 **Tip:** Test scanning before sharing. "
                            "If it won't scan, switch to **Square** modules and **White** background."
                        )
                        st.download_button(
                            "📥 Download Artistic QR (PNG)", data=png_bytes,
                            file_name=f"art_qr_{token}.png", mime="image/png",
                            use_container_width=True
                        )
                    except Exception as e:
                        st.error(f"❌ Error: {str(e)}")
        else:
            st.markdown(
                """
                <div style="border:2px dashed #cbd5e0; border-radius:12px; height:340px;
                            display:flex; flex-direction:column; align-items:center;
                            justify-content:center; color:#a0aec0; font-size:15px;
                            text-align:center; padding:20px;">
                    <div style="font-size:52px; margin-bottom:14px;">🖼️</div>
                    <div>Upload an image + enter a URL<br>Your image becomes the QR pattern</div>
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
               style="text-decoration:none; margin-right:15px; color:#0077B5; font-weight:bold;">
               🔗 LinkedIn</a>
            <a href="https://github.com/Tuhin108" target="_blank"
               style="text-decoration:none; color:#333; font-weight:bold;">
               💻 GitHub</a>
        </p>
    </div>
    """,
    unsafe_allow_html=True
)
