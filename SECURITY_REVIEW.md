# Security & Code Quality Review

## 🔴 CRITICAL SECURITY ISSUES

### 1. XML External Entity (XXE) Attack Vulnerability
**Location:** `cli.py:201-202`
**Severity:** HIGH

```python
fahrplan_dom = minidom.parse(str(fahrplan_file))
media_dom = minidom.parse(str(media_file))
```

**Risk:** XML parser is vulnerable to:
- XML Entity Expansion (Billion Laughs Attack)
- External Entity attacks that could read local files
- DoS through deeply nested structures

**Fix:** Use defusedxml library or configure parser to disable external entities

---

### 2. Path Traversal Vulnerability
**Location:** `cli.py:145, 433`
**Severity:** MEDIUM-HIGH

```python
output_file = output_dir / yaml_file.name.replace("media_", "feed_").replace(".yml", ".xml")
output_file = Path(output) if output else Path(f"media/media_{event_key}.yml")
```

**Risk:** User-controlled paths could write files outside intended directories
**Fix:** Sanitize and validate all path components before use

---

### 3. Insecure Temporary Directory
**Location:** `cli.py:193`
**Severity:** MEDIUM

```python
cache_dir = Path("/tmp/media_feed_cache")
```

**Risk:**
- Symlink attacks in world-writable /tmp
- Cache poisoning by other users
- Information disclosure

**Fix:** Use tempfile.mkdtemp() or user-specific cache directory

---

### 4. No Input Sanitization
**Location:** `cli.py:33-71, 364-453`
**Severity:** MEDIUM

User inputs (username, comments, query) are not sanitized before:
- Writing to YAML files
- Displaying in terminal
- Using in file operations

**Risk:** YAML injection, terminal escape sequences

---

### 5. Broad Exception Handling
**Location:** `cli.py:314, 359`
**Severity:** LOW-MEDIUM

```python
except Exception as e:
    return False, str(e)
```

**Risk:** Hides security exceptions, information disclosure through error messages

---

## 🟡 CODE QUALITY ISSUES

### 1. Monolithic File Structure
**Status:** NEEDS REFACTORING

`cli.py` is 640 lines mixing concerns:
- CLI commands
- RSS generation
- HTTP requests
- XML parsing
- YAML I/O

**Impact:** Hard to test, maintain, and audit

---

### 2. Missing Resource Cleanup
**Severity:** MEDIUM

File handles not explicitly closed using context managers everywhere:
- Network connections may leak
- File descriptors may leak on errors

---

### 3. No Atomic File Writes
**Location:** `cli.py:147, 450, 553`

```python
output_file.write_text(xml_content, encoding="utf-8")
```

**Risk:** File corruption on crash or interruption
**Fix:** Write to temp file, then atomic rename

---

### 4. No Configuration Validation
**Location:** `cli.py:19-22`

Config structure not validated, will fail at runtime if keys missing

---

### 5. No Logging
**Status:** MISSING

No logging for:
- HTTP requests
- File operations
- Errors
- Security events

---

### 6. Cache Validation Missing
**Location:** `cli.py:153-163`

Downloaded content cached without:
- Checksum validation
- Content-type validation
- Size limits
- Expiry

---

### 7. Magic Numbers
Hardcoded throughout:
- timeout=30
- /tmp paths
- port numbers
- size limits

---

## ✅ RECOMMENDED ARCHITECTURE

### Proposed Module Structure:

```
src/media_feed/
├── cli.py              # CLI commands only (click decorators)
├── commands/
│   ├── build_cmd.py    # Build command logic
│   ├── add_cmd.py      # Add command logic
│   ├── rate_cmd.py     # Rate command logic
│   └── list_cmd.py     # List command logic
├── core/
│   ├── rss.py          # RSS generation
│   ├── ccc_api.py      # CCC event fetching
│   ├── yaml_io.py      # YAML operations with validation
│   └── config.py       # Configuration management
├── security/
│   ├── xml_parser.py   # Secure XML parsing
│   └── sanitizer.py    # Input sanitization
├── utils/
│   ├── constants.py    # Constants and magic numbers
│   ├── files.py        # Atomic file operations
│   └── cache.py        # Secure caching
├── feedback.py         # (existing)
└── validation.py       # (existing)
```

---

## 📋 PRIORITY ACTION ITEMS

### Immediate (Before Release):
1. ✅ Fix XXE vulnerability in XML parsing
2. ✅ Sanitize user inputs
3. ✅ Use secure temp directory
4. ✅ Add path traversal protection
5. ✅ Implement atomic file writes

### High Priority:
6. ✅ Refactor into modules
7. ✅ Add comprehensive logging
8. ✅ Validate configuration
9. ✅ Add cache validation
10. ✅ Improve error handling

### Medium Priority:
11. Add rate limiting for HTTP
12. Add SSL certificate pinning (optional)
13. Add input length limits
14. Add comprehensive tests

---

## 🔒 SECURITY BEST PRACTICES TO IMPLEMENT

1. **Principle of Least Privilege:** Don't need write access to config files
2. **Defense in Depth:** Multiple layers of input validation
3. **Fail Secure:** Default to denying operations
4. **Complete Mediation:** Check all inputs every time
5. **Logging & Monitoring:** Audit trail for security events

---

## ❓ QUESTIONS BEFORE IMPLEMENTATION

1. **Should we use defusedxml library** for XML parsing (adds dependency)?
2. **Cache location**: Use `~/.cache/media-feed/` or keep in `/tmp`?
3. **Should we add SSL certificate pinning** for CCC URLs?
4. **File size limits**: What's maximum acceptable for YAML/XML files?
5. **Breaking changes acceptable**: Refactoring may change internal APIs
6. **Add structured logging**: JSON logs or human-readable?
7. **Error handling strategy**: Fail fast or try to recover?
