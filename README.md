# Aoin - Ecommerce Backend

This is the backend service for **Aoin Ecommerce**, built with Python. It provides APIs, database integration, and a chatbot service.

---

## 🚀 Getting Started

Follow the steps below to set up the backend locally.

### 1. Clone the repository
```bash
git clone <repository-url>
cd Ecommerce_Backend
```
### 2. Create virtual environment
```bash
python -m venv venv
```
### Activate the virtual environment:
Linux / macOS
```bash


source venv/bin/activate
```

Windows
```bash 
venv\Scripts\activate
```

### 3. Install dependencies
``` bash
pip install -r requirements.txt
```
### Environment Variables

Create a .env file in the project root with your database credentials:

⚠️ Update the database username and password with your local MySQL credentials.

### Database Setup

Ensure MySQL server is running.

Create the database and initialize tables:
```bash
python init_db.py
```
### Running the Backend

Start the application server:
```bash
python app.py

```
The server will start (default: http://localhost:5110).

### Chatbot

To run the chatbot service:
```bash
python chatbot.py
```
