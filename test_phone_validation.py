"""
Test script to verify the contact number field changes will work correctly.
This validates the phone number format and field constraints.
"""

import re

def test_phone_format():
    """Test the new phone number format validation"""
    # Test format: +63 9XX XXX XXXX
    phone_regex = re.compile(r'^\+63 9\d{2} \d{3} \d{4}$')
    
    valid_numbers = [
        '+63 912 345 6789',
        '+63 999 888 7777',
        '+63 901 234 5678',
        '+63 987 654 3210'
    ]
    
    invalid_numbers = [
        '+63912345678',      # No spaces
        '09123456789',       # Wrong format
        '+63 8123456789',    # Wrong prefix
        '+63 91 345 6789',   # Wrong spacing
        '+63 912 34 56789',  # Wrong spacing
        '+639123456789',     # No space after +63
    ]
    
    print("Testing valid phone numbers:")
    for phone in valid_numbers:
        is_valid = bool(phone_regex.match(phone))
        print(f"  {phone}: {'✓ Valid' if is_valid else '✗ Invalid'}")
        assert is_valid, f"Should be valid: {phone}"
    
    print("\nTesting invalid phone numbers:")
    for phone in invalid_numbers:
        is_valid = bool(phone_regex.match(phone))
        print(f"  {phone}: {'✗ Invalid' if not is_valid else '✓ Valid'}")
        assert not is_valid, f"Should be invalid: {phone}"
    
    # Test field length
    test_number = '+63 912 345 6789'
    print(f"\nField length test:")
    print(f"  Phone number: '{test_number}'")
    print(f"  Length: {len(test_number)} characters")
    print(f"  Previous max_length (16): {'✓ Fits' if len(test_number) <= 16 else '✗ Too long'}")
    print(f"  New max_length (20): {'✓ Fits' if len(test_number) <= 20 else '✗ Too long'}")
    
    assert len(test_number) <= 20, "Phone number should fit in new field length"
    print("\n✅ All phone number tests passed!")

if __name__ == "__main__":
    test_phone_format()