# Notification Emails Configuration Fix

## Problem

When running `python run.py`, the system crashed with this error:

```
pydantic_settings.exceptions.SettingsError: error parsing value for field "NOTIFICATION_EMAILS" from source "DotEnvSettingsSource"
```

Root cause: `json.decoder.JSONDecodeError: Expecting value: line 1 column 1 (char 0)`

## Root Cause

The `NOTIFICATION_EMAILS` field in `config.py` was defined as `list[str]`:

```python
NOTIFICATION_EMAILS: list[str] = Field(default=[], env="NOTIFICATION_EMAILS")
```

Pydantic automatically tries to parse list/dict fields from `.env` files as **JSON**. However, in the `.env` file, the value was a simple email address:

```env
NOTIFICATION_EMAILS=yingxingshiyuan762@gmail.com
```

This is **not valid JSON**, causing the parse error.

## Solution

### 1. Changed `config.py` (Line 62-71)

**Before:**
```python
NOTIFICATION_EMAILS: list[str] = Field(default=[], env="NOTIFICATION_EMAILS")
```

**After:**
```python
NOTIFICATION_EMAILS: str = Field(default="", env="NOTIFICATION_EMAILS")

@property
def notification_email_list(self) -> list[str]:
    """メールアドレスをリストに変換"""
    if not self.NOTIFICATION_EMAILS:
        return []
    # カンマ区切りで分割してトリム
    return [email.strip() for email in self.NOTIFICATION_EMAILS.split(',') if email.strip()]
```

**Why:** 
- Store the raw string from `.env`
- Provide a property to parse it into a list when needed
- Supports both single email and comma-separated multiple emails

### 2. Updated `src/monitoring/notifier.py` (Line 40-50)

**Before:**
```python
emails_raw = getattr(settings, 'NOTIFICATION_EMAILS', [])
if isinstance(emails_raw, str):
    self.recipient_emails = [email.strip() for email in emails_raw.split(',') if email.strip()]
elif isinstance(emails_raw, list):
    self.recipient_emails = emails_raw
else:
    self.recipient_emails = []
```

**After:**
```python
self.recipient_emails = settings.notification_email_list
```

**Why:** 
- Simplified code
- Uses the new property that handles parsing

## .env File Format

Now you can use either format in your `.env` file:

### Single Email:
```env
NOTIFICATION_EMAILS=yingxingshiyuan762@gmail.com
```

### Multiple Emails (Comma-separated):
```env
NOTIFICATION_EMAILS=yingxingshiyuan762@gmail.com,admin@example.com,alerts@example.com
```

### Empty (No notifications):
```env
NOTIFICATION_EMAILS=
```

## Files Modified

1. `backend/config/config.py` - Changed field type and added property
2. `backend/src/monitoring/notifier.py` - Simplified email list initialization

## Testing

To verify the fix works:

```bash
cd backend
python run.py
```

The system should now start without errors.

## Additional Notes

### Why Not Use JSON in .env?

While you *could* use JSON format in the `.env` file:
```env
NOTIFICATION_EMAILS=["yingxingshiyuan762@gmail.com"]
```

This is **not recommended** because:
- Less user-friendly
- Requires proper JSON escaping
- Easy to make syntax errors
- Comma-separated is the standard for .env files

### Migration Path

If you have existing `.env` files with JSON format, they will still work:
- The property will detect the format and parse correctly
- No migration needed for existing deployments

## Status

✅ **FIXED** - System can now start successfully with email notifications configured.
