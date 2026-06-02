# ⚡ bsodbot plus

<div align="center">
  <p>
    <b>The ultimate ultra-lightweight, high-performance AI agent gateway and automation framework.</b>
  </p>
  <p>
    <img src="https://img.shields.io/badge/python-≥3.11-blue" alt="Python">
    <img src="https://img.shields.io/badge/license-MIT-green" alt="License">
    <img src="https://img.shields.io/badge/status-active-success" alt="Status">
  </p>
</div>

---

## 🐈 What is bsodbot plus?

**bsodbot plus** is an open-source, ultra-lightweight, and highly customizable AI agent gateway designed for power users, developers, and automation enthusiasts. It keeps the core agent loop small, blazing fast, and readable while supporting multi-channel communication, persistent memory, Model Context Protocol (MCP), and advanced tool execution.

Whether you want to run a local terminal assistant, a long-running Telegram/Discord bot, or a fully autonomous background worker, **bsodbot plus** provides the perfect foundation with zero bloat and maximum performance.

---

## ✨ Key Features

- 🚀 **Blazing Fast & Lightweight**: Minimal memory footprint, optimized for low-resource environments (runs perfectly on cheap VPS instances).
- 🧠 **Persistent Memory & Context**: Advanced two-stage memory system (Dream) that automatically summarizes and retains key facts across restarts.
- 🔌 **Model Context Protocol (MCP)**: Seamlessly connect to any MCP server to extend the agent's capabilities with custom tools.
- 💬 **Multi-Channel Integration**: Out-of-the-box support for Telegram, Discord, Slack, WebUI, and WebSockets.
- 🛠️ **Powerful Built-in Tools**: Secure shell execution, surgical file patching, web search, web scraping, and image generation.
- 🤖 **Model Agnostic**: Supports OpenAI, Anthropic, Google Gemini, DeepSeek, Groq, AWS Bedrock, and local LLMs.

---

## 🛠️ Quick Start

### 1. Installation

Clone the repository and install the dependencies using `uv` or `pip`:

```bash
git clone https://github.com/nulls-brawl-site/bsodbot-plus.git
cd bsodbot-plus
pip install -e .
```

### 2. Configuration

Create a `config.json` file in your workspace directory:

```json
{
  "providers": {
    "openai": {
      "api_key": "your-api-key"
    }
  },
  "channels": {
    "telegram": {
      "enabled": true,
      "token": "your-bot-token"
    }
  }
}
```

### 3. Run the Agent

Start the agent gateway:

```bash
python3 -m nanobot
```

---

## 📂 Project Structure

```text
├── nanobot/               # Core agent runtime and loop
│   ├── agent/             # Agent loop, memory, and tool execution
│   ├── api/               # REST API and server endpoints
│   ├── channels/          # Telegram, Discord, Slack, and WebUI channels
│   ├── providers/         # LLM provider integrations (OpenAI, Anthropic, Gemini, etc.)
│   └── skills/            # Built-in and custom agent skills
├── webui/                 # Modern React-based Web UI
├── tests/                 # Comprehensive test suite
└── docker-compose.yml     # Docker deployment configuration
```

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
