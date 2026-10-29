# Agent Wallet

A spending-policy gateway and governance layer for AI agents powered by PayPal Sandbox Payouts.

## Quick Start

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure Environment
```bash
cp .env.example .env
```

### 3. Run the Server
```bash
uvicorn app.main:app --reload
```

- API Health: [http://localhost:8000/health](http://localhost:8000/health)
- Dashboard: [http://localhost:8000/](http://localhost:8000/)
- API Docs: [http://localhost:8000/docs](http://localhost:8000/docs)
