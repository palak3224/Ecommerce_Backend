# 🚀 Setup Guide - Aoin-application Branch

This guide will help you set up and run the **Aoin-application** branch on your local machine.

---

## 📋 Prerequisites

Before you begin, ensure you have the following installed:

- **Python 3.8+** (Check with `python --version`)
- **MySQL Server** (5.7+ or 8.0+)
- **Git**
- **pip** (Python package manager)

---

## 🔧 Step-by-Step Setup

### 1. Clone the Repository

```bash
git clone https://github.com/palak3224/Ecommerce_Backend.git
cd Ecommerce_Backend
```

### 2. Checkout the Aoin-application Branch

```bash
git checkout Aoin-application
```

Or if you want to fetch the latest changes:

```bash
git fetch origin
git checkout Aoin-application
```

### 3. Create Virtual Environment

**Windows:**
```bash
python -m venv venv
venv\Scripts\activate
```

**Linux / macOS:**
```bash
python3 -m venv venv
source venv/bin/activate
```

You should see `(venv)` in your terminal prompt when activated.

### 4. Install Dependencies

```bash
pip install -r requirments.txt
```

**Note:** The file is named `requirments.txt` (not `requirements.txt`).

### 5. Set Up Environment Variables

Create a `.env` file in the `Ecommerce_Backend` root directory:

```bash
# Windows
type nul > .env

# Linux / macOS
touch .env
```

Add the following environment variables to your `.env` file:

```env
# Database Configuration
DATABASE_URI=mysql+pymysql://username:password@localhost:3306/your_database_name

# Flask Configuration
FLASK_APP=app.py
FLASK_ENV=development
SECRET_KEY=your-secret-key-here-change-this-in-production

# JWT Configuration
JWT_SECRET_KEY=your-jwt-secret-key-here-change-this-in-production
JWT_ACCESS_TOKEN_EXPIRES=3600
JWT_REFRESH_TOKEN_EXPIRES=86400

# Email Configuration (for email verification)
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USE_TLS=True
MAIL_USERNAME=your-email@gmail.com
MAIL_PASSWORD=your-app-password

# Google OAuth (if using Google login)
GOOGLE_CLIENT_ID=your-google-client-id
GOOGLE_CLIENT_SECRET=your-google-client-secret

# Twilio Configuration (for phone authentication)
TWILIO_ACCOUNT_SID=your-twilio-account-sid
TWILIO_AUTH_TOKEN=your-twilio-auth-token
TWILIO_PHONE_NUMBER=your-twilio-phone-number

# Cloudinary (for image uploads)
CLOUDINARY_CLOUD_NAME=your-cloudinary-cloud-name
CLOUDINARY_API_KEY=your-cloudinary-api-key
CLOUDINARY_API_SECRET=your-cloudinary-api-secret

# Razorpay (for payments)
RAZORPAY_KEY_ID=your-razorpay-key-id
RAZORPAY_KEY_SECRET=your-razorpay-key-secret

# Super Admin (created during database initialization)
SUPER_ADMIN_EMAIL=admin@aoin.com
SUPER_ADMIN_FIRST_NAME=Super
SUPER_ADMIN_LAST_NAME=Admin
SUPER_ADMIN_PASSWORD=your-secure-password

# Redis (if using caching)
REDIS_URL=redis://localhost:6379/0
```

**⚠️ Important:** Replace all placeholder values with your actual credentials.

### 6. Database Setup

#### 6.1. Start MySQL Server

Ensure MySQL is running on your system.

**Windows:**
- Check MySQL service in Services or start via command line

**Linux:**
```bash
sudo systemctl start mysql
```

**macOS:**
```bash
brew services start mysql
```

#### 6.2. Create Database

Log into MySQL and create a database:

```bash
mysql -u root -p
```

```sql
CREATE DATABASE your_database_name CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
EXIT;
```

#### 6.3. Initialize Database Tables

Run the initialization script:

```bash
python init_db.py
```

This will:
- Create all necessary tables
- Set up initial data (countries, tax categories, etc.)
- Create a super admin user (if configured in `.env`)

### 7. Apply Database Migrations (if needed)

If there are any pending migrations, apply them:

```bash
# Check for migrations directory
ls migrations/sql/

# If you see migration files, they should be applied automatically by init_db.py
# But if needed, you can run them manually using MySQL
```

### 8. Run the Application

Start the Flask development server:

```bash
python app.py
```

You should see output like:
```
 * Running on http://127.0.0.1:5110
```

The server will be available at: **http://localhost:5110**

---

## 🧪 Testing the Setup

### Test Phone Authentication (New Feature)

1. **Send OTP:**
   ```bash
   curl -X POST http://localhost:5110/api/auth/phone/send-otp \
     -H "Content-Type: application/json" \
     -d '{"phone": "+919171453224"}'
   ```

2. **Verify OTP and Sign Up:**
   ```bash
   curl -X POST http://localhost:5110/api/auth/phone/verify-signup \
     -H "Content-Type: application/json" \
     -d '{
       "phone": "+919171453224",
       "otp": "123456",
       "first_name": "John",
       "last_name": "Doe"
     }'
   ```

### Test Other Endpoints

- **Health Check:** `GET http://localhost:5110/api/health`
- **API Documentation:** `GET http://localhost:5110/api/docs` (if Swagger is enabled)

---

## 🐛 Troubleshooting

### Issue: Module not found errors

**Solution:**
```bash
# Make sure virtual environment is activated
# Reinstall dependencies
pip install -r requirments.txt
```

### Issue: Database connection error

**Solution:**
- Check MySQL is running
- Verify `DATABASE_URI` in `.env` is correct
- Ensure database exists
- Check MySQL user has proper permissions

### Issue: Twilio authentication error

**Solution:**
- Verify `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, and `TWILIO_PHONE_NUMBER` in `.env`
- Ensure Twilio account is active
- For testing, verify your phone number in Twilio console

### Issue: Port already in use

**Solution:**
- Change port in `app.py` or kill the process using port 5110
- Windows: `netstat -ano | findstr :5110` then `taskkill /PID <pid> /F`
- Linux/macOS: `lsof -ti:5110 | xargs kill -9`

### Issue: Enum error for auth_provider

**Solution:**
- The database enum should be lowercase: `ENUM('local', 'google', 'phone')`
- If you see uppercase enum errors, run:
  ```sql
  ALTER TABLE users MODIFY COLUMN auth_provider ENUM('local', 'google', 'phone') NOT NULL DEFAULT 'local';
  UPDATE users SET auth_provider = LOWER(auth_provider);
  ```

---

## 📚 Additional Information

### Project Structure

```
Ecommerce_Backend/
├── auth/              # Authentication module
│   ├── controllers.py # Auth logic
│   ├── routes.py      # Auth endpoints
│   ├── models/        # User models
│   ├── utils.py       # Auth utilities
│   └── twilio_service.py  # Twilio SMS service
├── models/            # Database models
├── routes/            # API routes
├── config.py          # Configuration
├── app.py             # Flask application
├── init_db.py         # Database initialization
└── requirments.txt    # Python dependencies
```

### Key Features in This Branch

- ✅ Phone number authentication with Twilio OTP
- ✅ Email/password authentication
- ✅ Google OAuth authentication
- ✅ JWT token-based authentication
- ✅ Role-based access control (USER, MERCHANT, ADMIN, SUPER_ADMIN)
- ✅ Phone authentication restricted to regular users only

### API Endpoints

**Authentication:**
- `POST /api/auth/register` - Email/password registration
- `POST /api/auth/login` - Email/password login
- `POST /api/auth/google` - Google OAuth login
- `POST /api/auth/phone/send-otp` - Send OTP to phone
- `POST /api/auth/phone/verify-signup` - Verify OTP and sign up
- `POST /api/auth/phone/verify-login` - Verify OTP and login

---

## 🔐 Security Notes

1. **Never commit `.env` file** - It contains sensitive credentials
2. **Use strong secret keys** in production
3. **Keep dependencies updated** - Run `pip list --outdated` regularly
4. **Use environment-specific configurations** for production

---

## 📞 Support

If you encounter any issues:
1. Check the troubleshooting section above
2. Review error logs in the terminal
3. Verify all environment variables are set correctly
4. Ensure all prerequisites are installed

---

## ✅ Verification Checklist

Before running the application, ensure:

- [ ] Python 3.8+ installed
- [ ] MySQL server running
- [ ] Virtual environment created and activated
- [ ] Dependencies installed (`pip install -r requirments.txt`)
- [ ] `.env` file created with all required variables
- [ ] Database created
- [ ] `init_db.py` run successfully
- [ ] No errors in terminal when starting server

---

**Happy Coding! 🎉**

