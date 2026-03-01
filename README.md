# QR Forge 🚀

> Generate custom QR codes with expiry-based redirects and analytics

## 📖 Description

A powerful QR Code Generator built with **Streamlit** and **FastAPI** that creates customizable QR codes with time-based redirect functionality. Perfect for marketing campaigns, event promotions, or any scenario where you need trackable, temporary QR codes.

The application runs Streamlit on port 8501 with a FastAPI backend running on port 8000 for handling redirects and API requests.

## ✨ Features

| Feature | Description |
|---------|-------------|
| 🎨 **Custom QR Codes** | Generate QR codes with custom foreground/background colors |
| 🖼️ **Logo Overlay** | Add your logo to QR codes (max 25% of QR size) |
| 📊 **Error Correction** | Choose from L (7%), M (15%), Q (25%), H (30%) levels |
| ⏰ **Expiry-based Redirects** | Set QR codes to expire from 1 minute to 7 days |
| 📈 **Scan Analytics** | Track how many times each QR code has been scanned |
| 💾 **JSON Persistence** | Redirect data persists in `redirects.json` |
| 📦 **Multiple Formats** | Export as PNG or SVG |
| ⚡ **Rate Limiting** | API limited to 10 requests per minute per IP |
| 🔗 **Direct URL Mode** | Option to encode target URL directly without redirect |
| 🔌 **RESTful API** | Full API for programmatic QR generation |

## 🧰 Tech Stack

| Category | Technology |
|----------|------------|
| Frontend | Streamlit |
| Backend | FastAPI (Python) |
| QR Library | segno |
| Image Processing | Pillow |
| Server | Uvicorn |

## 📁 Project Structure

```
├── app.py              # Main application (Streamlit UI + FastAPI backend)
├── requirements.txt    # Python dependencies
└── README.md           # This file
```

## ⚙️ How to Run

### Prerequisites

```
bash
pip install -r requirements.txt
```

### Run the Application

```
bash
streamlit run app.py
```

The app will be available at:
- **Streamlit UI**: http://localhost:8501

## 📦 API Reference

### Generate QR Code

```
bash
curl -X POST "http://localhost:8000/api/generate" \
  -F "url=https://example.com" \
  -F "fg_color=#000000" \
  -F "bg_color=#ffffff" \
  -F "error_level=M" \
  -F "expiry_minutes=60"
```

**With Logo:**
```
bash
curl -X POST "http://localhost:8000/api/generate" \
  -F "url=https://example.com" \
  -F "logo=@logo.png"
```

**Response:**
```
json
{
  "token": "uuid-string",
  "redirect_url": "http://localhost:8000/redirect/uuid-string",
  "expires_at": "2024-01-15T14:30:00",
  "qr_image_base64": "iVBORw0KGgoAAAANSUhEUg...",
  "scan_count": 0,
  "direct_encoded": false
}
```

### Redirect Endpoint

```
bash
# Visit this URL (scan QR code)
http://localhost:8000/redirect/{token}
```

**Response Codes:**
- `302`: Valid redirect → redirects to target URL
- `404`: Token expired or invalid → shows error page

### API Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `url` | string | required | Target URL (must start with http:// or https://) |
| `fg_color` | string | "#000000" | QR foreground color |
| `bg_color` | string | "#ffffff" | QR background color |
| `error_level` | string | "M" | Error correction: L, M, Q, or H |
| `expiry_minutes` | int | 60 | Expiry time (1-10080 minutes) |
| `use_direct` | bool | false | Encode URL directly (no redirect) |
| `logo` | file | null | PNG/JPG logo image |

## 🔧 Error Correction Levels

| Level | Correction | Best For |
|-------|------------|----------|
| L | 7% | Clean environments, lots of data |
| M | 15% | General use (default) |
| Q | 25% | Slight damage potential |
| H | 30% | Heavy damage, logos, print wear |

> **Tip:** Use error level H when adding logos to ensure scannability.

## 🗄️ Data Storage

Redirects are stored in `redirects.json`:

```
json
{
  "token-uuid": {
    "url": "https://example.com",
    "created_at": "2024-01-15T12:00:00",
    "expires_at": "2024-01-15T13:00:00",
    "scan_count": 42
  }
}
```

## 🔒 Security

- **Rate Limit**: 10 requests/minute per IP on `/api/generate`
- **URL Validation**: Must start with `http://` or `https://`
- **Expiry Range**: 1 to 10,080 minutes (7 days max)
- **Token**: UUIDv4 (128-bit random)
- **No Authentication**: Public endpoints (add your own if needed)

## ☁️ Deployment
https://qr-forge.streamlit.app/

## 🧪 Testing

```
bash
# Run locally
streamlit run app.py

# Test API endpoint
curl -X POST "http://localhost:8000/api/generate" \
  -F "url=https://example.com" \
  -F "expiry_minutes=60"

# Test redirect (replace token)
curl -L "http://localhost:8000/redirect/YOUR-TOKEN-HERE"
```

👤 Author
--------
The QR Code Generator with Redirect Service was created by [Tuhin108](https://github.com/Tuhin108).

---

Built with ❤️ by [Tuhin108](https://github.com/Tuhin108)
