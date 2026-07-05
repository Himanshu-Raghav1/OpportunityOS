# 🚀 Deploying OpportunityOS AI for Free on Streamlit Cloud

You can host and showcase your AI Agent app entirely for free using **GitHub** and **Streamlit Community Cloud**. Follow this step-by-step guide:

---

## 🛠️ Step 1: Create a GitHub Repository

1. Go to [GitHub](https://github.com/) and log in.
2. Click **New** to create a new repository.
3. Name it `OpportunityOS-AI` (or any name you prefer).
4. Set the repository to **Public** (required for the free tier of Streamlit Cloud).
5. Click **Create Repository**.

---

## 📤 Step 2: Push Your Code to GitHub

Open Git Bash or your terminal in your project directory and run:

```bash
# Initialize git
git init

# Add all files to staging (make sure .env is in your .gitignore so you don't leak keys!)
git add .

# Commit changes
git commit -m "feat: initial commit for competition"

# Rename branch to main
git branch -M main

# Link to your GitHub repo and push
git remote add origin https://github.com/YOUR_GITHUB_USERNAME/OpportunityOS-AI.git
git push -u origin main
```

> [!WARNING]
> **Do not push your `.env` file containing your private API keys to GitHub!** 
> Make sure `.gitignore` contains `.env`. You will configure your keys securely in the next step.

---

## 🌐 Step 3: Deploy on Streamlit Community Cloud

1. Visit [Streamlit Community Cloud](https://share.streamlit.io/) and log in using your GitHub account.
2. Click the **New app** button.
3. Fill in the deployment details:
   * **Repository:** Select your `OpportunityOS-AI` repository.
   * **Branch:** `main`
   * **Main file path:** `app.py`
4. Click **Advanced settings** (or settings icon) before deploying:
   * Navigate to the **Secrets** section.
   * Paste your API credentials in TOML format:
     ```toml
     GOOGLE_API_KEY = "your-google-gemini-key"
     SERPAPI_KEY = "your-serpapi-key"
     TAVILY_API_KEY = "your-tavily-key"
     FIRECRAWL_API_KEY = "your-firecrawl-key"
     ```
   * Click **Save**.
5. Click **Deploy!**

Streamlit Cloud will automatically download all dependencies from `requirements.txt`, configure the environment secrets, and launch your application under a public shareable URL!

---

## ⚡ Key Compatibility Optimizations Already Implemented:
* **SQLite Override:** Standard Streamlit Cloud servers run on Linux and often have outdated SQLite packages that crash `ChromaDB` (`sqlite3.OperationalError`). I implemented a `pysqlite3-binary` override dynamically in `core/memory.py` so the app will bypass this crash seamlessly on Debian Linux containers.
* **REST API Transport:** Bypasses blocked TCP/gRPC ports inside Streamlit hosting sandboxes by routing all Gemini commands over HTTP.
