
def escape_md(text):
    if not text: return ""
    special_chars = r"_*[]()~`>#+-=|{}.!"
    for char in special_chars:
        text = text.replace(char, f"\\{char}")
    return text

def test_escape():
    print("🧪 Testing Markdown Escaping...")
    
    # TC 1: Event ID with underscore (The culprit!)
    raw_id = "_88o3ccph88q3aba56so3cb9k6gpj6ba274q3ab9i8d1kchhi8p0j4c248k"
    safe_id = escape_md(raw_id)
    print(f"Raw ID: {raw_id}")
    print(f"Safe ID: {safe_id}")
    
    if r"\_" in safe_id:
        print("✅ Underscore escaped correctly.")
    else:
        print("❌ Underscore NOT escaped.")

    # TC 2: Summary with special chars
    raw_summary = "Project Update [Important] & (Review)"
    safe_summary = escape_md(raw_summary)
    print(f"\nRaw Summary: {raw_summary}")
    print(f"Safe Summary: {safe_summary}")
    
    if r"\[" in safe_summary and r"\(" in safe_summary:
         print("✅ Brackets/Parentheses escaped correctly.")
    else:
         print("❌ Brackets/Parentheses NOT escaped.")

if __name__ == "__main__":
    test_escape()
