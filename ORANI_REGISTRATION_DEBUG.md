# Orani Municipality Registration Debugging

## Issue Description
Registration fails when users select Orani municipality (pk=9) during the registration process.

## Debugging Features Added

### 1. Backend Debugging (base/views.py)
- ✅ Comprehensive logging for form validation
- ✅ Database operation tracking
- ✅ Municipality/Barangay relationship verification
- ✅ Specific error handling for IntegrityError and ValidationError
- ✅ Transaction debugging

### 2. Frontend Debugging (register_step1.html)
- ✅ Form submission event capture
- ✅ Municipality selection detection
- ✅ Validation status reporting
- ✅ JavaScript console logging

### 3. Database Integrity Checks
- ✅ AccountType/AccountStatus existence verification
- ✅ Municipality/Barangay relationship validation
- ✅ Unique constraint violation detection

## How to Test

### 1. Start the Django Development Server
```
cd "c:\Users\326w\OneDrive\Documents\BPSU FILES\BPSU 2024-2 stuff\Fruit Cast Folder\FRUIT CAST PROJECT"
python manage.py runserver
```

### 2. Navigate to Registration Page
- Go to: http://127.0.0.1:8000/register/ (or whatever your registration URL is)

### 3. Test Orani Municipality Registration
- Fill out the registration form
- **IMPORTANT**: Select "Orani" as the municipality
- Select any barangay from Orani
- Submit the form

### 4. Monitor Debug Output

#### In Terminal (Backend):
Look for messages like:
```
🔍 REGISTRATION DEBUG START
📧 Email being registered: [email]
🏘️ Municipality selected: 9 (Orani)
🏠 Barangay selected: [barangay_id]
📝 Form validation result: [True/False]
```

#### In Browser Console (Frontend):
Press F12 and check Console tab for:
```
🚀 Form submission started
📝 Municipality selected: 9
🏠 Barangay selected: [barangay_id]
✅ Form validation: passed
```

### 5. Error Analysis

#### If IntegrityError occurs:
- Check for duplicate email addresses
- Check for duplicate RSBSA reference numbers
- Verify foreign key relationships

#### If ValidationError occurs:
- Check form field validation rules
- Verify required fields are populated
- Check data format constraints

#### If General Exception occurs:
- Review full traceback in terminal
- Check database connection
- Verify model relationships

## Files Modified

1. **base/views.py**
   - Added comprehensive debugging to register_step1 function
   - Enhanced error handling with specific exception types
   - Added transaction debugging

2. **base/templates/registration/register_step1.html**
   - Added JavaScript form submission tracking
   - Enhanced client-side validation debugging

## Next Steps

1. **Test Registration**: Try registering with Orani municipality
2. **Analyze Output**: Review debug messages in both terminal and browser console
3. **Identify Root Cause**: Based on error messages, determine if issue is:
   - Form validation problem
   - Database constraint violation
   - Missing data (AccountType/AccountStatus)
   - Municipality/Barangay relationship issue

## Common Solutions

### If missing AccountType "Farmer":
```python
python manage.py shell
>>> from base.models import AccountType
>>> AccountType.objects.create(account_type="Farmer")
```

### If missing AccountStatus "Verified":
```python
python manage.py shell
>>> from base.models import AccountStatus
>>> AccountStatus.objects.create(acc_status="Verified")
```

### If missing Orani municipality or barangays:
```python
python manage.py shell
>>> from base.models import Municipality, Barangay
>>> orani = Municipality.objects.get(pk=9)
>>> print(f"Orani: {orani.municipality_name}")
>>> barangays = Barangay.objects.filter(municipality_id=9)
>>> print(f"Barangays count: {barangays.count()}")
```

## Contact Information
If the issue persists after following these debugging steps, provide:
1. Complete error messages from terminal
2. Browser console output
3. The specific test data used during registration
4. Database query results for Orani municipality and its barangays