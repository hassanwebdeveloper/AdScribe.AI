# Email Configuration for Admin OTP

This guide explains how to configure email sending for admin OTP authentication.

## For Development (No Email Configuration)

If you don't configure email settings, the system will work in simulation mode:
- OTP codes will be logged to the server console
- You can find the OTP in the backend logs when testing
- The admin login will show "check server logs" message

## For Production (Real Email Sending)

### Gmail Configuration (IMPORTANT: App Password Required)

⚠️ **CRITICAL**: Gmail requires an "App Password" when 2-factor authentication is enabled. You CANNOT use your regular Gmail password.

1. **Enable 2-Factor Authentication** on your Gmail account
2. **Generate an App Password**:
   - Go to Google Account settings: https://myaccount.google.com/
   - Click "Security" → "2-Step Verification" → "App passwords"
   - Select "Mail" as the app type
   - Copy the 16-character password (remove spaces)

3. **Add to your `.env` file**:
```env
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=abcdefghijklmnop
SMTP_FROM_EMAIL=noreply@yourdomain.com
```

**Common Errors:**
- `Application-specific password required` → You're using your regular password instead of App Password
- `Username and Password not accepted` → Check if 2-factor auth is enabled and use App Password
- `Less secure app access` → Enable App Passwords instead

### Other Email Providers

**Outlook/Hotmail:**
```env
SMTP_SERVER=smtp-mail.outlook.com
SMTP_PORT=587
SMTP_USERNAME=your-email@outlook.com
SMTP_PASSWORD=your-password
```

**Custom SMTP:**
```env
SMTP_SERVER=your-smtp-server.com
SMTP_PORT=587
SMTP_USERNAME=your-username
SMTP_PASSWORD=your-password
```

## Testing

1. Start the backend: `python -m uvicorn app.main:app --reload`
2. Go to admin login: `http://localhost:8000/admin/login`
3. Enter an authorized email (`shoaibahmad99@gmail.com` or `h.baig34@gmail.com`)
4. Check your email or server logs for the OTP code

## Troubleshooting

### Gmail Issues:
- **Error 534**: App Password required → Generate App Password from Google Account settings
- **Error 535**: Username/Password incorrect → Verify App Password is correct (16 chars, no spaces)
- **No App Password option**: Enable 2-Factor Authentication first

### General Issues:
- Check SMTP server and port settings
- Verify firewall/network allows SMTP connections
- Test with a simple email client first

## Security Notes

- OTP codes expire in 1 minute
- Maximum 3 attempts per OTP
- Sessions last 8 hours
- Only authorized emails can request OTPs
- All attempts are logged for security monitoring
- Never share App Passwords - they have full email access 