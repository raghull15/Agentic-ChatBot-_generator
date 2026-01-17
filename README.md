# 🤖 AgenticAI - RAG Chatbot Generator

A full-stack application to create, manage, and embed AI chatbots powered by your PDF documents using RAG (Retrieval-Augmented Generation).

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Node](https://img.shields.io/badge/node-18%2B-green.svg)
![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)

## ✨ Features

- **PDF-Based AI Agents** - Upload PDFs to create intelligent chatbots
- **JWT Authentication** - Secure user registration and login
- **Embeddable Widget** - Deploy chatbots on any website with a script tag
- **Professional UI** - Modern, responsive interface with Lucide icons
- **Multi-Agent Support** - Create unlimited agents per user
- **Rate Limiting** - Built-in protection for embed endpoints

## 🏗️ Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   React Frontend │────▶│  Express Auth   │     │  Flask Backend  │
│   (Vite + Tailwind)    │  (JWT + MongoDB) │     │  (LangChain + Ollama)
└─────────────────┘     └─────────────────┘     └─────────────────┘
        │                                                │
        └────────────────────────────────────────────────┘
```

## 📋 Prerequisites

- **Node.js** 18+ and npm
- **Python** 3.10+
- **MongoDB** (local or Atlas)
- **Ollama** with models installed

### Install Ollama Models

```bash
ollama pull llama3.2:3b
ollama pull mxbai-embed-large
```

## 🚀 Quick Start

### 1. Clone the Repository

```bash
git clone https://github.com/srinia7san/ChatBot-_generator.git
cd "Chat bot generator"
```

### 2. Setup Auth Server (Express + MongoDB)

```bash
cd backend-nodejs
npm install
```

Create `.env` file:

```env
MONGODB_URI=mongodb://localhost:27017/agentic-auth
JWT_SECRET=your-super-secret-jwt-key-change-in-production
JWT_EXPIRES_IN=7d
PORT=3000
```

Start the server:

```bash
node server.js
```

### 3. Setup Backend (Flask + LangChain)

```bash
cd backend-flask
pip install -r requirements.txt
```

Set environment variable (same JWT secret as auth server):

```bash
# Windows
set JWT_SECRET=your-super-secret-jwt-key-change-in-production

# Linux/Mac
export JWT_SECRET=your-super-secret-jwt-key-change-in-production
```

Start the server:

```bash
python api_server.py
```

### 4. Setup Frontend (React + Vite)

```bash
cd frontend
npm install
npm run dev
```

### 5. Access the Application

Open http://localhost:5173 in your browser.

## 📁 Project Structure

```
Chat bot generator/
├── frontend/                     # React Frontend
│   ├── src/
│   │   ├── components/          # Reusable components
│   │   ├── pages/               # Page components
│   │   ├── context/             # React contexts
│   │   ├── api.js               # API service layer
│   │   └── index.css            # Tailwind styles
│   └── vite.config.js
│
├── backend-nodejs/              # Express Auth Server
│   ├── models/User.js           # Mongoose user model
│   ├── middleware/auth.js       # JWT middleware
│   ├── routes/auth.js           # Auth endpoints
│   └── server.js                # Entry point
│
└── backend-flask/               # Flask RAG Backend
    ├── api_server.py            # REST API endpoints
    ├── rag_agent_system.py      # RAG logic
    ├── widget/                  # Embeddable widget
    │   ├── widget.js
    │   └── test.html
    └── requirements.txt
```

## 🔌 API Endpoints

### Auth Server (Port 3000)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/auth/register` | Register new user |
| POST | `/auth/login` | Login user |
| GET | `/auth/verify` | Verify JWT token |
| GET | `/auth/me` | Get current user |

### Flask Backend (Port 5000)

**Protected (JWT Required)**

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/agents` | List user's agents |
| POST | `/agents/create` | Create new agent |
| GET | `/agents/<name>` | Get agent info |
| POST | `/agents/<name>/query` | Query agent |
| POST | `/agents/<name>/embed-token` | Generate embed token |
| DELETE | `/agents/<name>` | Delete agent |

**Public (No Auth)**

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/widget.js` | Embed widget script |
| GET | `/embed/<token>/info` | Get agent info |
| POST | `/embed/<token>/query` | Query via embed |

## 🔗 Embedding Chatbots

After creating an agent and generating an embed token:

```html
<script 
  src="http://localhost:5000/widget.js"
  data-token="YOUR_EMBED_TOKEN"
  data-theme="light"
  data-position="bottom-right"
  data-title="AI Assistant"
></script>
```

### Widget Options

| Attribute | Values | Default |
|-----------|--------|---------|
| `data-token` | Your embed token | Required |
| `data-theme` | `light`, `dark` | `light` |
| `data-position` | `bottom-right`, `bottom-left`, `top-right`, `top-left` | `bottom-right` |
| `data-title` | Custom title | Agent name |

## 🛠️ Development

### Running All Services

Open 3 terminals:

```bash
# Terminal 1 - Auth Server
cd backend-nodejs && node server.js

# Terminal 2 - Flask Backend
cd backend-flask && python api_server.py

# Terminal 3 - React Frontend
cd frontend && npm run dev
```

### Environment Variables

| Service | Variable | Description |
|---------|----------|-------------|
| Auth Server | `MONGODB_URI` | MongoDB connection string |
| Auth Server | `JWT_SECRET` | JWT signing secret |
| Auth Server | `JWT_EXPIRES_IN` | Token expiry (e.g., `7d`) |
| Flask | `JWT_SECRET` | Must match auth server |
| Flask | `MONGODB_URI` | MongoDB connection (optional, defaults to localhost) |

## 🔒 Security Notes

- Change `JWT_SECRET` in production
- Use HTTPS in production
- Configure CORS for your domains
- Enable rate limiting for production

## 📄 License

MIT License - see [LICENSE](LICENSE) for details.

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Open a Pull Request

---

Made with ❤️ using React, Flask, LangChain, and Ollama
