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
import pandas as pd
from datetime import datetime, timedelta
from typing import Optional, Any, cast
from pathlib import Path

import segno
from PIL import Image
import streamlit as st
import streamlit.components.v1 as components

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
DATA_FILE = "s.json"
MAX_EXPIRY_DAYS = 7

# Get the base URL from environment or Streamlit's built-in
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
    # 1. Save locally first (keeps the app fast)
    try:
        with open(DATA_FILE, 'w') as f:
            json.dump(data, f, indent=2)
    except IOError as e:
        logger.error(f"Failed to save data locally: {e}")

    # 2. The Auto-Push Pipeline to GitHub
    try:
        # Pulling your GitHub token from Streamlit's secure secrets
        if "GITHUB_TOKEN" in st.secrets:
            github_token = st.secrets["GITHUB_TOKEN"] 
            
            repo = "Tuhin108/qr-forge" # Your exact GitHub repo
            path = "analytics.json"
            url = f"https://api.github.com/repos/{repo}/contents/{path}"
            headers = {"Authorization": f"token {github_token}"}
            
            # Check if analytics.json already exists to get its 'sha' (required by GitHub to update files)
            get_resp = requests.get(url, headers=headers)
            sha = get_resp.json().get("sha") if get_resp.status_code == 200 else None
            
            # Encode the data and push the commit
            encoded_content = base64.b64encode(json.dumps(data, indent=2).encode()).decode()
            payload = {
                "message": "📊 Auto-updating QR scan analytics",
                "content": encoded_content
            }
            if sha:
                payload["sha"] = sha
                
            # Send it to GitHub
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
    scale: int = 10
) -> tuple[bytes, bytes]:
    """Generate QR code with custom styling and optional logo"""
    error_map = {"L": "l", "M": "m", "Q": "q", "H": "h"}
    error = error_map.get(error_level.upper(), "m")
    
    qr = segno.make(data, error=error)
    
    png_buffer = io.BytesIO()
    qr.save(png_buffer, kind="png", scale=scale, dark=fg_color, light=bg_color)
    png_buffer.seek(0)
    
    if logo_image:
        qr_image = Image.open(png_buffer).convert("RGBA")
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
    """Add centered logo to QR code (max 25% of QR size)"""
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
# STREAMLIT UI
# ============================================================================

st.set_page_config(
    page_title="QR Code Generator",
    page_icon="🎯",
    layout="wide"
)

# Check for redirect first
handle_redirect()

st.title("🎯 QR Forge")
st.markdown("Generate custom QR codes with expiry-based redirects")

col1, col2 = st.columns([1, 1])

with col1:
    st.subheader("Configuration")
    
    url = st.text_input(
        "Target URL",
        placeholder="https://example.com",
        help="The URL where the QR code will redirect"
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
    
    logo_file = st.file_uploader(
        "Logo (Optional)",
        type=["png", "jpg", "jpeg"],
        help="Upload a logo to overlay on the QR code"
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
                    
                    logo_image = None
                    if logo_file is not None:
                        try:
                            logo_image = Image.open(logo_file)
                        except Exception as e:
                            st.error(f"❌ Invalid logo image: {str(e)}")
                            logo_image = None

                    png_bytes, svg_bytes = generate_qr_code(
                        redirect_url, fg_color, bg_color, error_level, logo_image, scale
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
                    

# Footer
st.divider()

with st.expander("📊 Features & Deployment Guide"):
    st.markdown("""
    ### Features
    - Custom colors and error correction levels
    - Optional logo overlay (maintains scannability)
    - Expiry-based redirects with token management
    - JSON file persistence and GitHub Analytics Push
    - Scan tracking dashboard
    
    ### Deployment to Streamlit Cloud
    
    1. Set the `BASE_URL` environment variable in Streamlit Cloud:
       - Go to your app settings → Secrets
       - Add: `BASE_URL = "https://qr-forge.streamlit.app"`
    
    2. Add your GitHub Token:
       - Go to your app settings → Secrets
       - Add: `GITHUB_TOKEN = "ghp_your_token_here"`
    
    3. How redirects work:
       - QR code contains: `https://qr-forge.streamlit.app?r=https://target.com&t=token`
       - When scanned, app checks token expiry
       - If valid, redirects to target URL via JavaScript
    """)

