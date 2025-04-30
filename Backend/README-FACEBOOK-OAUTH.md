# Facebook OAuth Integration

This guide explains how to set up and use Facebook OAuth authentication for AdScribe.AI.

## Configuration

Add the following to your `.env` file:

```
# Facebook OAuth Configuration
FACEBOOK_CLIENT_ID=your_facebook_app_id
FACEBOOK_CLIENT_SECRET=your_facebook_app_secret
FACEBOOK_REDIRECT_URI=http://localhost:8000/api/v1/auth/facebook/callback
FRONTEND_URL=http://localhost:5173
```

## Facebook App Setup

1. Create a Facebook App on the [Facebook Developers Portal](https://developers.facebook.com/)
2. Set up the app for "Website" and "Facebook Login"
3. Configure the OAuth redirect URI in the app settings
4. Add the following permissions to your app:
   - `email`
   - `public_profile`
   - `ads_management`
   - `ads_read`

## Authentication Flow

1. User clicks "Login with Facebook" button which points to:
   ```
   GET /api/v1/auth/facebook/login
   ```

2. The backend redirects to Facebook's OAuth page

3. User authorizes the application on Facebook

4. Facebook redirects back to the callback URL:
   ```
   GET /api/v1/auth/facebook/callback?code=...
   ```

5. The backend exchanges the code for an access token

6. The backend gets the user's profile and finds or creates a user

7. The backend redirects to the frontend with a JWT token:
   ```
   /auth/facebook/success?token=jwt_token
   ```

## Ad Account Selection

After a user logs in with Facebook, they need to select which ad account to use:

1. Get the list of available ad accounts:
   ```
   GET /api/v1/auth/facebook/ad-accounts
   ```

2. Set the ad account to use:
   ```
   POST /api/v1/auth/facebook/ad-account
   {
     "account_id": "act_123456789"
   }
   ```

3. The backend will immediately schedule metrics collection for this account

## Token Refresh

Facebook tokens can expire. Long-lived tokens last about 60 days. You should implement a token refresh mechanism in a production application.

## Frontend Integration

In your frontend (React) code, implement:

1. A "Login with Facebook" button that links to `/api/v1/auth/facebook/login`
2. A callback handler for `/auth/facebook/success` that stores the token
3. An ad account selection UI after successful login
4. Error handling for `/auth/facebook/error`

## Data Storage

User Facebook profile and credentials are stored in the User model:

```json
{
  "facebook_profile": {
    "id": "12345678",
    "name": "John Doe",
    "email": "john@example.com"
  },
  "facebook_credentials": {
    "access_token": "EAABsbCS1IPkBOwfLZCjMmzNHRyH...",
    "account_id": "act_123456789",
    "token_expires_at": "2023-12-31T23:59:59"
  },
  "is_facebook_login": true
}
``` 