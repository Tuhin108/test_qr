# 🎯 QR Forge

QR Forge is a comprehensive, Streamlit-based application designed to generate custom QR codes featuring built-in URL redirection, automated scan tracking, and expiration capabilities. 

## ✨ Key Features

* **Dynamic QR Generation**: Create fully customized QR codes by adjusting foreground and background colors, selecting error correction levels (L, M, Q, or H), and adjusting the code scale.
* **Logo Integration**: Optionally upload and embed a centralized logo (automatically scaled to a maximum of 25% of the QR code size) into the generated QR image.
* **Time-Limited Links**: Configure QR codes with custom expiration times, up to a maximum of 7 days. Users attempting to scan an expired QR code are automatically routed to a dedicated "Invalid or Expired" landing page.
* **Redirection & Analytics**: QR codes act as intermediate routing links (`?r=...&t=...`) that silently increment scan counters before forwarding the user to the target URL using JavaScript injection.
* **Automated GitHub Sync**: Analytics data is written locally for performance, but an integrated auto-push pipeline automatically syncs scan metrics and token data to `analytics.json` in the connected GitHub repository using the GitHub API.
* **Multiple Export Formats**: Instantly download generated QR codes in either PNG or scalable SVG formats.

## 🏗️ Architecture Overview

The core logic handles redirection dynamically through Streamlit's query parameters. When a QR code is generated, it is assigned a unique UUID token, mapped to the target URL, and stored alongside its creation and expiration timestamps. 

Data is primarily tracked in two files:
1. `s.json`: The local operational database that maintains high-speed read/write access for the app.
2. `analytics.json`: The remote analytics ledger containing URL metadata, creation/expiration timestamps, and scan counts, continuously updated via the GitHub API pipeline.

## 📦 Prerequisites and Dependencies

The application runs on Python 3.11+ and relies on the following core dependencies:
* `streamlit>=1.28.0`
* `segno>=1.5.0` (for QR code encoding)
* `Pillow>=10.0.0` (for image and logo processing)
* `requests` and `pandas`

## 🚀 Installation & Local Setup

1. **Clone the Repository:**
   ```bash
   git clone [https://github.com/Tuhin108/qr-forge.git](https://github.com/Tuhin108/qr-forge.git)
   cd qr-forge

```

2. **Install Dependencies:**
```bash
pip install -r requirements.txt

```


3. **Configure Secrets (Required for Analytics Push):**
Create a `.streamlit/secrets.toml` file in the root directory and add a GitHub Personal Access Token to enable the auto-push pipeline:
```toml
GITHUB_TOKEN = "your_personal_access_token_here"

```


4. **Environment Variables (Optional):**
You can specify a custom `BASE_URL` environment variable for routing. If omitted, the app defaults to `https://qr-forge.streamlit.app`.
5. **Run the Application:**
```bash
streamlit run streamlit_app.py

```



## 🐳 DevContainer Support

For seamless development, this repository includes a configured `.devcontainer/devcontainer.json`. Opening the project in GitHub Codespaces or a local VS Code Docker environment will automatically:

* Provision a Debian-based Python 3.11 environment.
* Install the Python extensions (`ms-python.python`, `ms-python.vscode-pylance`).
* Update the OS and install all package requirements automatically.
* Expose and forward port `8501` to preview the Streamlit app.

---
```
Built by (Tuhin Kumar Singha Roy)[https://github.com/Tuhin108]

```

