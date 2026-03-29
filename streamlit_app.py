"""
QR Forge — QR Code Generator with Redirect Service, Artistic Mode, and Permanent QR.
Includes Auto-Push Analytics to GitHub and in-app Dashboard.
Optimised for Google search ranking via injected meta / structured-data tags.
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
from typing import Optional, Any, cast, Tuple, Literal

from pathlib import Path

import segno
from PIL import Image, ImageEnhance, ImageFilter, ImageDraw
import streamlit as st
import streamlit.components.v1 as components

# ── Color constants ──────────────────────────────────────────────────────────
WHITE_RGB_INT = 0xFFFFFF
WHITE_RGBA_INT = 0xFFFFFFFF
WHITE_TRANS_INT = 0x00FFFFFF
BLACK_RGB_INT = 0x000000

# ── logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ── runtime config ────────────────────────────────────────────────────────────
DATA_FILE = "s.json"
MAX_EXPIRY_DAYS = 7
BASE_URL = os.getenv("BASE_URL", "")
APP_URL = BASE_URL if BASE_URL else "https://qr-forge.streamlit.app"


# ============================================================================
# SEO — inject <meta> tags + JSON-LD structured data into <head>
# ============================================================================

def inject_seo():
    """
    Streamlit renders inside an iframe-like shell; the only reliable way to
    write into <head> from Python is via a zero-height components.html block
    whose JavaScript mutates the parent document's <head>.
    This runs once on every page load and is transparent to the user.
    """
    seo_script = f"""
    <script>
    (function() {{
        var head = window.parent.document.head;

        function setMeta(name, content, prop) {{
            var sel = prop
                ? 'meta[property="' + name + '"]'
                : 'meta[name="'     + name + '"]';
            var el  = head.querySelector(sel);
            if (!el) {{
                el = window.parent.document.createElement('meta');
                if (prop) el.setAttribute('property', name);
                else       el.setAttribute('name', name);
                head.appendChild(el);
            }}
            el.setAttribute('content', content);
        }}

        // ── Primary meta ─────────────────────────────────────────────────────
        setMeta('description',
            'QR Forge — free online QR code generator. Create custom QR codes ' +
            'with logo, colors, expiry-redirect, artistic image-style, and permanent ' +
            'QR codes. No sign-up required. Download PNG & SVG instantly.');
        setMeta('keywords',
            'QR code generator, free QR code, custom QR code, QR code with logo, ' +
            'QR code maker, artistic QR code, permanent QR code, dynamic QR code, ' +
            'QR code online, QR code download, QR code redirect');
        setMeta('robots', 'index, follow');
        setMeta('author', 'Tuhin Kumar Singha Roy');

        // ── Open Graph ───────────────────────────────────────────────────────
        setMeta('og:type',        'website',                    true);
        setMeta('og:title',       'QR Forge — Free Custom QR Code Generator', true);
        setMeta('og:description',
            'Generate custom, artistic, or permanent QR codes in seconds. ' +
            'Add your logo, pick colors, set expiry. Free, no sign-up.',   true);
        setMeta('og:url',         '{APP_URL}',                  true);
        setMeta('og:image',       '{APP_URL}/favicon.ico',      true);
        setMeta('og:site_name',   'QR Forge',                   true);

        // ── Twitter Card ─────────────────────────────────────────────────────
        setMeta('twitter:card',        'summary_large_image');
        setMeta('twitter:title',       'QR Forge — Free Custom QR Code Generator');
        setMeta('twitter:description',
            'Custom • Artistic • Permanent QR codes. Logo support, color picker, ' +
            'expiry redirects. Free & instant.');
        setMeta('twitter:image',  '{APP_URL}/favicon.ico');

        // ── Canonical link ───────────────────────────────────────────────────
        if (!head.querySelector('link[rel="canonical"]')) {{
            var link = window.parent.document.createElement('link');
            link.rel  = 'canonical';
            link.href = '{APP_URL}';
            head.appendChild(link);
        }}

        // ── JSON-LD structured data (WebApplication schema) ──────────────────
        if (!head.querySelector('#qrforge-jsonld')) {{
            var script = window.parent.document.createElement('script');
            script.id   = 'qrforge-jsonld';
            script.type = 'application/ld+json';
            script.text = JSON.stringify({{
                "@context": "https://schema.org",
                "@type": "WebApplication",
                "name": "QR Forge",
                "url": "{APP_URL}",
                "description":
                    "Free online QR code generator. Create custom, artistic, " +
                    "and permanent QR codes with logo, colors, and expiry redirect. " +
                    "Download PNG and SVG instantly — no sign-up required.",
                "applicationCategory": "UtilitiesApplication",
                "operatingSystem": "All",
                "offers": {{
                    "@type": "Offer",
                    "price": "0",
                    "priceCurrency": "USD"
                }},
                "author": {{
                    "@type": "Person",
                    "name": "Tuhin Kumar Singha Roy",
                    "url": "https://www.linkedin.com/in/tuhininaiml"
                }},
                "featureList": [
                    "Custom QR code with logo",
                    "Color customization",
                    "Expiry-based redirect QR codes",
                    "Artistic image-style QR codes",
                    "Permanent QR codes",
                    "PNG and SVG download"
                ]
            }});
            head.appendChild(script);
        }}
    }})();
</script>
    """
    components.html(seo_script, height=0, width=0)


# ============================================================================
# REDIRECT HANDLING
# ============================================================================

def handle_redirect():
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

        st.title("🚀 Redirecting…")
        st.info(f"Taking you to: **{target_url}**")
        st.write("If your target doesn't open automatically, click below:")
        st.link_button("Open Link", target_url, type="primary", width="stretch")
        components.html(
            f"""<script>window.top.location.href = "{target_url}";</script>""",
            height=0, width=0
        )
        st.stop()


def show_expired_page():
    st.markdown("""
        <div style="font-family:Arial,sans-serif;text-align:center;padding:60px 20px;">
        <h1 style="color:#e53e3e;">⚠️ Invalid or Expired</h1>
        <p style="color:#4a5568;">This QR code has expired or does not exist.<br>
        Please contact the creator for a new link.</p></div>
    """, unsafe_allow_html=True)
    st.stop()


# ============================================================================
# DATA MANAGEMENT
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
            encoded = base64.b64encode(json.dumps(data, indent=2).encode()).decode()
            payload = {"message": "📊 Auto-updating QR scan analytics", "content": encoded}
            if sha:
                payload["sha"] = sha
            requests.put(url, headers=headers, json=payload)
    except Exception as e:
        logger.error(f"GitHub push failed: {e}")


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
# QR CODE GENERATION — STANDARD
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
    logo_bg = Image.new("RGBA", logo.size, WHITE_RGBA_INT)
    logo_bg.paste(logo, (0, 0), logo)
    qr_image.paste(logo_bg, logo_pos, logo_bg)
    return qr_image


# ============================================================================
# QR CODE GENERATION — ARTISTIC
# ============================================================================

def _is_finder_or_separator(row: int, col: int, n: int) -> bool:
    margin = 8
    in_tl = row < margin and col < margin
    in_tr = row < margin and col >= (n - margin)
    in_bl = row >= (n - margin) and col < margin
    return in_tl or in_tr or in_bl


def generate_artistic_qr(
    qr_data: str,
    art_image: Image.Image,
    error_level: str = "H",
    bg_style: str = "White",
    saturation: float = 1.3,
    module_size: int = 16,
) -> bytes:
    def safe_radius(r: float) -> int:
        """Convert float radius to int for type compatibility."""
        return int(r)

    error_map = {"L": "l", "M": "m", "Q": "q", "H": "h"}
    error = error_map.get(error_level.upper(), "h")
    qr = segno.make(qr_data, error=error)

    matrix = list(qr.matrix)
    n_rows = len(matrix)
    n_cols = len(matrix[0]) if n_rows else 0

    canvas_w = n_cols * module_size
    canvas_h = n_rows * module_size

    art = art_image.convert("RGB")
    art = ImageEnhance.Contrast(art).enhance(1.2)
    art = ImageEnhance.Color(art).enhance(saturation)
    art_small = art.resize((n_cols, n_rows), Image.Resampling.LANCZOS)
    art_pixels = np.array(art_small, dtype=np.uint8)

    if bg_style == "Transparent":
        canvas = Image.new("RGBA", (canvas_w, canvas_h), WHITE_TRANS_INT)
    else:
        canvas = Image.new("RGB", (canvas_w, canvas_h), WHITE_RGB_INT)

    draw = ImageDraw.Draw(canvas)

    WHITE_RGB = (255, 255, 255)
    BLACK_RGB = (0, 0, 0)

    for r in range(n_rows):
        for c in range(n_cols):
            is_dark = matrix[r][c] != 0
            x0 = c * module_size
            y0 = r * module_size
            x1 = x0 + module_size - 1
            y1 = y0 + module_size - 1

            if _is_finder_or_separator(r, c, n_rows):
                color: Tuple[int, int, int] = BLACK_RGB if is_dark else WHITE_RGB
                draw.rectangle([x0, y0, x1, y1], fill=color)
            elif is_dark:
                pr, pg, pb = int(art_pixels[r, c, 0]), int(art_pixels[r, c, 1]), int(art_pixels[r, c, 2])
                f = 0.75
                draw.rectangle([x0, y0, x1, y1], fill=(int(pr*f), int(pg*f), int(pb*f)))
            else:
                if bg_style == "Image tint":
                    pr, pg, pb = int(art_pixels[r, c, 0]), int(art_pixels[r, c, 1]), int(art_pixels[r, c, 2])
                    draw.rectangle([x0, y0, x1, y1], fill=(
                        int(pr * 0.15 + 255 * 0.85),
                        int(pg * 0.15 + 255 * 0.85),
                        int(pb * 0.15 + 255 * 0.85)
                    ))
                elif bg_style == "Transparent":
                    pass
                else:
                    draw.rectangle([x0, y0, x1, y1], fill=(255, 255, 255))

    if bg_style != "Transparent":
        canvas = canvas.filter(ImageFilter.UnsharpMask(radius=safe_radius(0.8), percent=100, threshold=2))

    buf = io.BytesIO()
    canvas.save(buf, format="PNG", optimize=True)
    buf.seek(0)
    return buf.getvalue()


# ============================================================================
# QR CODE GENERATION — PERMANENT (URL embedded directly, no redirect)
# ============================================================================

def generate_permanent_qr(
    url: str,
    fg_color: str = "#000000",
    bg_color: str = "#ffffff",
    error_level: str = "M",
    logo_image: Optional[Image.Image] = None,
    scale: int = 10,
) -> tuple[bytes, bytes]:
    """
    Encodes the URL directly into the QR — no token, no server, never expires.
    Returns (png_bytes, svg_bytes).
    """
    return generate_qr_code(
        data=url,
        fg_color=fg_color,
        bg_color=bg_color,
        error_level=error_level,
        logo_image=logo_image,
        background_image=None,
        scale=scale,
    )


# ============================================================================
# STREAMLIT PAGE CONFIG  (must come before any other st.* call)
# ============================================================================

st.set_page_config(
    page_title="QR Forge — Free Custom QR Code Generator",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Inject SEO (runs after set_page_config) ───────────────────────────────────
inject_seo()

# ── Handle redirect before rendering UI ──────────────────────────────────────
handle_redirect()


# ============================================================================
# GLOBAL STYLES — minimal polish on top of Streamlit's default theme
# ============================================================================

st.markdown("""
<style>
/* ── Kill Streamlit's default top padding ── */
section.main > div:first-child { padding-top: 0.6rem !important; }
div[data-testid="stAppViewBlockContainer"] { padding-top: 0.5rem !important; }
header[data-testid="stHeader"] { display: none !important; }

/* ── Tab highlight ── */
div[data-baseweb="tab-list"] button[aria-selected="true"] {
    border-bottom: 3px solid #667eea;
    color: #667eea;
}
/* ── Download-button accent ── */
div[data-testid="stDownloadButton"] button {
    background: linear-gradient(135deg,#667eea,#764ba2);
    color: #fff;
    border: none;
}
/* ── Hero headline — big & gradient ── */
.qf-hero {
    font-size: 3.6rem;
    font-weight: 900;
    letter-spacing: -1.5px;
    line-height: 1.05;
    margin-bottom: 6px;
    background: linear-gradient(135deg,#667eea 0%,#f093fb 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
}
.qf-sub  { color: #718096; font-size: 1rem; margin-top: 0; margin-bottom: 18px; }
/* ── Info cards ── */
.qf-card { background:#f7fafc; border-left:4px solid #667eea;
           padding:12px 16px; border-radius:6px; margin-bottom:8px; font-size:.9rem; }
/* ── Artistic QR preview: cap height so it never overflows ── */
.art-qr-preview img {
    max-height: 420px !important;
    width: auto !important;
    display: block;
    margin: 0 auto;
}
</style>
""", unsafe_allow_html=True)


# ============================================================================
# HERO HEADER
# ============================================================================

st.markdown('<p class="qf-hero">🎯 QR Forge</p>', unsafe_allow_html=True)
st.markdown(
    '<p class="qf-sub">Free custom QR codes — dynamic redirects · artistic image-style · '
    'permanent embed · logo support · PNG & SVG download</p>',
    unsafe_allow_html=True
)


# ============================================================================
# TABS
# ============================================================================

tab_gen, tab_art, tab_perm = st.tabs([
    "✏️ Dynamic QR (with redirect)",
    "🖼️ Artistic QR",
    "🔒 Permanent QR",
])


# ── TAB 1 — Dynamic QR ───────────────────────────────────────────────────────
with tab_gen:
    col1, col2 = st.columns([1, 1])

    with col1:
        st.subheader("Configuration")
        st.caption(
            "The QR points to a **trackable short-link** that redirects to your URL. "
            "Scans are counted, and the link expires after the time you choose."
        )
        url = st.text_input("Target URL", placeholder="https://example.com", key="gen_url")

        col_a, col_b = st.columns(2)
        with col_a:
            fg_color = st.color_picker("Foreground", "#000000")
        with col_b:
            bg_color = st.color_picker("Background", "#ffffff")

        error_level = st.selectbox("Error Correction", ["L", "M", "Q", "H"], index=1,
                                   help="L=7% · M=15% · Q=25% · H=30%")
        expiry_minutes = st.slider("Expiry (minutes)", 1, MAX_EXPIRY_DAYS * 24 * 60, 60)
        scale = st.slider("Scale (size)", 5, 20, 10)
        bg_file   = st.file_uploader("Background image (optional)", type=["png","jpg","jpeg"])
        logo_file = st.file_uploader("Logo (optional)",             type=["png","jpg","jpeg"])
        generate_btn = st.button("🎨 Generate Dynamic QR", type="primary", width="stretch")

    with col2:
        st.subheader("Preview")
        if generate_btn:
            if not url:
                st.error("❌ Please enter a target URL")
            elif not validate_url(url):
                st.error("❌ URL must start with http:// or https://")
            else:
                with st.spinner("Generating…"):
                    try:
                        import urllib.parse
                        token = str(uuid.uuid4())
                        redirect_data = store_redirect(token, url, expiry_minutes)
                        encoded_url   = urllib.parse.quote(url, safe='')
                        redirect_url  = f"{APP_URL}?r={encoded_url}&t={token}"

                        bg_img   = Image.open(bg_file)   if bg_file   else None
                        logo_img = Image.open(logo_file) if logo_file else None

                        png_bytes, svg_bytes = generate_qr_code(
                            redirect_url, fg_color, bg_color,
                            error_level, logo_img, bg_img, scale
                        )
                        st.image(png_bytes, width="stretch")
                        expires_at = datetime.fromisoformat(redirect_data["expires_at"])
                        st.success("✅ QR Code Generated!")
                        st.markdown(
                            f'<div class="qf-card">🔗 <b>Redirect URL:</b> <code>{redirect_url}</code><br>'
                            f'🪙 <b>Token:</b> <code>{token}</code><br>'
                            f'⏰ <b>Expires:</b> {expires_at.strftime("%Y-%m-%d %H:%M")} UTC<br>'
                            f'🎯 <b>Target:</b> {url}</div>',
                            unsafe_allow_html=True
                        )
                        c1, c2 = st.columns(2)
                        with c1:
                            st.download_button("📥 PNG", data=png_bytes,
                                               file_name=f"qr_{token}.png",
                                               mime="image/png", width="stretch")
                        with c2:
                            st.download_button("📥 SVG", data=svg_bytes,
                                               file_name=f"qr_{token}.svg",
                                               mime="image/svg+xml", width="stretch")
                    except Exception as e:
                        st.error(f"❌ {e}")


# ── TAB 2 — Artistic QR ──────────────────────────────────────────────────────
with tab_art:
    st.subheader("🖼️ Turn Your Image into a QR Code")
    st.markdown(
        "Upload any image — its colors are mapped **module by module** onto the QR pattern. "
        "Looks like your image, scans like a QR code."
    )

    art_col1, art_col2 = st.columns([1, 1])

    with art_col1:
        art_url        = st.text_input("Target URL", placeholder="https://example.com", key="art_url")
        art_image_file = st.file_uploader("Upload Image", type=["png","jpg","jpeg","webp"], key="art_img")
        art_error      = st.selectbox("Error Correction", ["M","Q","H"], index=2, key="art_err")
        art_bg         = st.selectbox("Background Style", ["White","Image tint","Transparent"])
        art_saturation = st.slider("Color Saturation", 0.5, 2.5, 1.3, 0.1)
        art_module_px  = st.slider("Module Size (px)", 8, 24, 16, 2)
        art_expiry     = st.slider("Expiry (minutes)", 1, MAX_EXPIRY_DAYS * 24 * 60, 60, key="art_exp")
        art_btn        = st.button("🎨 Generate Artistic QR", type="primary", width="stretch")

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
                        import urllib.parse
                        token = str(uuid.uuid4())
                        redirect_data = store_redirect(token, art_url, art_expiry)
                        encoded_url   = urllib.parse.quote(art_url, safe='')
                        redirect_url  = f"{APP_URL}?r={encoded_url}&t={token}"

                        art_image = Image.open(art_image_file)
                        png_bytes = generate_artistic_qr(
                            qr_data=redirect_url,
                            art_image=art_image,
                            error_level=art_error,
                            bg_style=art_bg,
                            saturation=art_saturation,
                            module_size=art_module_px,
                        )
                        # Cap to 420 px — artistic QRs are high-res and overflow otherwise
                        st.markdown('<div class="art-qr-preview">', unsafe_allow_html=True)
                        st.image(png_bytes, width=420)
                        st.markdown('</div>', unsafe_allow_html=True)
                        expires_at = datetime.fromisoformat(redirect_data["expires_at"])
                        st.success("✅ Artistic QR Generated!")
                        st.markdown(
                            f'<div class="qf-card">🪙 <b>Token:</b> <code>{token}</code><br>'
                            f'⏰ <b>Expires:</b> {expires_at.strftime("%Y-%m-%d %H:%M")} UTC<br>'
                            f'🎯 <b>Target:</b> {art_url}</div>',
                            unsafe_allow_html=True
                        )
                        st.info("💡 Tip: test scanning before sharing. If it won't scan, use **White** background.")
                        st.download_button("📥 Download Artistic QR (PNG)", data=png_bytes,
                                           file_name=f"art_qr_{token}.png",
                                           mime="image/png", width="stretch")
                    except Exception as e:
                        st.error(f"❌ {e}")
        else:
            st.markdown("""
                <div style="border:2px dashed #cbd5e0;border-radius:12px;height:340px;
                            display:flex;flex-direction:column;align-items:center;
                            justify-content:center;color:#a0aec0;font-size:15px;
                            text-align:center;padding:20px;">
                    <div style="font-size:52px;margin-bottom:14px;">🖼️</div>
                    <div>Upload an image + enter a URL<br>Your image becomes the QR pattern</div>
                </div>
            """, unsafe_allow_html=True)


# ── TAB 3 — Permanent QR ─────────────────────────────────────────────────────
with tab_perm:
    st.subheader("🔒 Permanent QR Code")

    # Explain the difference clearly
    st.markdown("""
    <div style="background:#ebf8ff;border-left:4px solid #3182ce;padding:14px 18px;
                border-radius:6px;margin-bottom:18px;font-size:.95rem;color:#2c5282;">
    <b>What is a Permanent QR?</b><br>
    The destination URL is <b>baked directly into the QR pattern</b> — there is no
    redirect server, no token, and <b>no expiry</b>. The code will work forever, even
    if this app goes offline. Trade-off: you cannot track scan counts or change the
    destination later.
    </div>
    """, unsafe_allow_html=True)

    perm_col1, perm_col2 = st.columns([1, 1])

    with perm_col1:
        st.subheader("Configuration")

        perm_url = st.text_input(
            "Destination URL",
            placeholder="https://example.com",
            key="perm_url",
            help="This URL is embedded directly in the QR — no server involved."
        )

        col_pa, col_pb = st.columns(2)
        with col_pa:
            perm_fg = st.color_picker("Foreground", "#000000", key="perm_fg")
        with col_pb:
            perm_bg = st.color_picker("Background", "#ffffff", key="perm_bg")

        perm_error = st.selectbox(
            "Error Correction",
            ["L", "M", "Q", "H"],
            index=1,
            key="perm_err",
            help="Higher = more damage-resistant but denser QR. M is fine for most uses."
        )
        perm_scale = st.slider("Scale (size)", 5, 20, 10, key="perm_scale")
        perm_logo  = st.file_uploader("Logo (optional)", type=["png","jpg","jpeg"], key="perm_logo")

        # Comparison helper
        with st.expander("Dynamic vs Permanent — which should I use?"):
            st.markdown("""
            | Feature | Dynamic QR | Permanent QR |
            |---|---|---|
            | Works forever | ❌ (expires) | ✅ |
            | Scan analytics | ✅ | ❌ |
            | Change destination | ✅ (re-generate) | ❌ |
            | Needs internet to scan | ✅ | ❌ |
            | Smaller QR pattern | ✅ | Depends on URL length |
            """)

        perm_btn = st.button("🔒 Generate Permanent QR", type="primary", width="stretch")

    with perm_col2:
        st.subheader("Preview")

        if perm_btn:
            if not perm_url:
                st.error("❌ Please enter a destination URL")
            elif not validate_url(perm_url):
                st.error("❌ URL must start with http:// or https://")
            else:
                with st.spinner("Embedding URL directly into QR…"):
                    try:
                        logo_img = Image.open(perm_logo) if perm_logo else None

                        png_bytes, svg_bytes = generate_permanent_qr(
                            url=perm_url,
                            fg_color=perm_fg,
                            bg_color=perm_bg,
                            error_level=perm_error,
                            logo_image=logo_img,
                            scale=perm_scale,
                        )

                        st.image(png_bytes, width="stretch")
                        st.success("✅ Permanent QR Generated — never expires!")

                        st.markdown(
                            f'<div class="qf-card">'
                            f'🎯 <b>Embedded URL:</b> <code>{perm_url}</code><br>'
                            f'🔒 <b>Type:</b> Permanent (no redirect, no expiry)<br>'
                            f'🗜️ <b>Error Correction:</b> {perm_error}'
                            f'</div>',
                            unsafe_allow_html=True
                        )

                        # Verify by showing what a scanner would get
                        st.info(
                            "🔍 **Verify:** Scan this QR with your phone — it should open "
                            f"`{perm_url}` directly, with no intermediate page."
                        )

                        c1, c2 = st.columns(2)
                        with c1:
                            st.download_button(
                                "📥 Download PNG",
                                data=png_bytes,
                                file_name="permanent_qr.png",
                                mime="image/png",
                                width="stretch"
                            )
                        with c2:
                            st.download_button(
                                "📥 Download SVG",
                                data=svg_bytes,
                                file_name="permanent_qr.svg",
                                mime="image/svg+xml",
                                width="stretch"
                            )

                    except Exception as e:
                        st.error(f"❌ {e}")
        else:
            st.markdown("""
                <div style="border:2px dashed #bee3f8;border-radius:12px;height:340px;
                            display:flex;flex-direction:column;align-items:center;
                            justify-content:center;color:#90cdf4;font-size:15px;
                            text-align:center;padding:20px;">
                    <div style="font-size:52px;margin-bottom:14px;">🔒</div>
                    <div>Enter a URL and click Generate<br>
                    <span style="font-size:13px;">URL embedded permanently — no server, no expiry</span>
                    </div>
                </div>
            """, unsafe_allow_html=True)


# ============================================================================
# SEO CONTENT BLOCK — visible keyword-rich text for crawlers
# ============================================================================

st.divider()
with st.expander("ℹ️ About QR Forge — Free Online QR Code Generator", expanded=False):
    st.markdown("""
    **QR Forge** is a free, no-sign-up QR code generator that supports three modes:

    - **Dynamic QR codes** — your URL is tracked through a short-link with scan analytics
      and an optional expiry timer. Great for marketing campaigns, event tickets, and
      time-limited promotions.
    - **Artistic QR codes** — upload any image and its colors are mapped pixel-by-pixel
      onto the QR modules. The result looks like your photo but scans perfectly.
    - **Permanent QR codes** — the destination URL is encoded directly into the QR pattern.
      No server involved, works forever, even offline.

    **Features:** custom foreground/background colors · logo overlay · background image blending ·
    error-correction control (L / M / Q / H) · PNG & SVG download · auto-push analytics to GitHub.

    Built with ❤️ by **Tuhin Kumar Singha Roy** using Python, Streamlit, segno, and Pillow.
    """)


# ============================================================================
# FOOTER
# ============================================================================

st.markdown("""
<div style='text-align:center;margin-top:20px;'>
    <p style='color:#4a5568;font-size:16px;'>Built with ❤️ by <b>Tuhin Kumar Singha Roy</b></p>
    <p>
        <a href="https://www.linkedin.com/in/tuhininaiml" target="_blank"
           style="text-decoration:none;margin-right:15px;color:#0077B5;font-weight:bold;">
           🔗 LinkedIn</a>
        <a href="https://github.com/Tuhin108" target="_blank"
           style="text-decoration:none;color:#333;font-weight:bold;">
           💻 GitHub</a>
    </p>
    <p style='color:#a0aec0;font-size:12px;'>
        QR Forge · Free QR Code Generator · Custom · Artistic · Permanent QR codes
    </p>
</div>
""", unsafe_allow_html=True)
