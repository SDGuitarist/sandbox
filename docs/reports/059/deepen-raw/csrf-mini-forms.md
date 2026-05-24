# Flask-WTF CSRF Token Handling with Multiple Mini-Forms

## Summary

Flask-WTF generates one random CSRF token per session and one signed token per request. All forms on a page share the identical signed token because `generate_csrf()` caches the result in Flask's `g` object. Having 10, 50, or even 200+ hidden inputs on one page causes zero performance concern -- every call to `{{ csrf_token() }}` after the first is a simple dictionary lookup. The main risk for this project is **token expiry**: the default 1-hour `WTF_CSRF_TIME_LIMIT` will cause failures if a user opens the dashboard in the morning and submits a toggle in the evening. The plan should address this with a config change. The hidden-input approach is fine for server-rendered forms; the meta-tag approach adds no benefit here since there is no JavaScript-driven form submission.

## Findings

### 1. Token generation: per-session raw token, per-request signed token

Source: `/opt/homebrew/lib/python3.14/site-packages/flask_wtf/csrf.py`, lines 23-63.

The `generate_csrf()` function works in two layers:

- **Raw token (session-scoped):** A random SHA-1 hex digest (`hashlib.sha1(os.urandom(64)).hexdigest()`) is generated once and stored in `session['csrf_token']`. It persists for the lifetime of the session. It is never regenerated unless the session is cleared or the stored value is corrupted.
- **Signed token (request-scoped):** The raw token is signed with `URLSafeTimedSerializer` (from `itsdangerous`), which embeds a timestamp. This signed value is cached in `g.csrf_token` (Flask's per-request `g` object). Within a single request, every call to `generate_csrf()` returns the same signed string.

All forms on a page therefore share the exact same signed token string. There is no "one token per form" behavior.

### 2. Performance with many forms: negligible overhead

The first call to `{{ csrf_token() }}` in a template does the work:
1. Check if `'csrf_token'` exists in `session` (dict lookup).
2. Sign the raw token with `URLSafeTimedSerializer.dumps()` (HMAC + base64).
3. Store the signed result in `g.csrf_token`.

Every subsequent call (2nd through Nth form) hits this path:

```python
if field_name not in g:
    # ... skipped on 2nd+ call
return g.get(field_name)  # simple dict lookup
```

This means rendering 200 forms with `{{ csrf_token() }}` costs one HMAC operation plus 199 dictionary lookups. There is no measurable performance concern, even on the calendar page with 7 x N forms.

### 3. Token expiry when a page is left open

This is the **most important finding** for this project.

The default `WTF_CSRF_TIME_LIMIT` is **3600 seconds (1 hour)**. The timestamp is embedded in the signed token at render time. When the form is submitted, `validate_csrf()` calls `s.loads(data, max_age=time_limit)`, which checks:

```python
# itsdangerous/timed.py, lines 138-146
if max_age is not None:
    age = self.get_timestamp() - ts_int
    if age > max_age:
        raise SignatureExpired(...)
```

**Scenario:** User opens the dashboard at 8 AM. All toggle forms get tokens signed at 8:00:00. At 9:01 AM (61 minutes later), any toggle submission will fail with "The CSRF token has expired." The user sees a 400 Bad Request.

**Mitigations (pick one):**

- **Increase the time limit:** `app.config['WTF_CSRF_TIME_LIMIT'] = 86400` (24 hours). This is safe for a single-user habit tracker since the session itself provides the security boundary.
- **Disable time limit entirely:** `app.config['WTF_CSRF_TIME_LIMIT'] = None`. When `time_limit` is `None`, the `_get_config` call passes `None` through, `s.loads(data, max_age=None)` is called, and itsdangerous skips the age check entirely (line 138: `if max_age is not None`). The token is still validated cryptographically -- only the timestamp check is skipped. The token remains valid as long as the session exists.
- **Add a meta-refresh or JS timer** to reload the page before expiry. This is overengineered for this app.

**Recommendation:** Set `WTF_CSRF_TIME_LIMIT = None` for a personal habit tracker. The session cookie expiry provides sufficient time-bounding. If this were a multi-user app with persistent sessions, increasing to 86400 (24 hours) would be more appropriate than disabling entirely.

### 4. `csrf_token()` in Jinja `for` loops works correctly

The `csrf_token` name is registered as a Jinja global in `CSRFProtect.init_app()`:

```python
app.jinja_env.globals["csrf_token"] = generate_csrf
```

It is a plain Python function reference. Calling it inside a `{% for %}` loop is no different from calling it outside one. Each call returns the same cached signed token (as explained in Finding 2). There are no known issues, race conditions, or template-engine quirks with this pattern.

Example that works correctly:

```html
{% for habit in habits %}
<form method="post" action="{{ url_for('toggle', habit_id=habit.id) }}">
    <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
    <button type="submit">Toggle</button>
</form>
{% endfor %}
```

### 5. POST-redirect-GET and CSRF tokens: no "consumed" token issue

Flask-WTF does **not** consume or invalidate the CSRF token on use. The validation logic in `validate_csrf()` (lines 66-115) does the following:

1. Deserialize the signed token (checking signature and optionally timestamp).
2. Compare the deserialized value against `session['csrf_token']` using `hmac.compare_digest()`.
3. If they match, the request proceeds. The session value is **not rotated or deleted**.

After a POST, the `redirect()` triggers a new GET request. On that GET:
- `generate_csrf()` is called again during template rendering.
- It finds `session['csrf_token']` still present (same raw token).
- It generates a new signed token (new timestamp) and caches it in `g`.

The new page's forms will have freshly-signed tokens, but old tokens from the previous page load are also still valid (until they expire or the session ends). There is **no issue** with POST-redirect-GET consuming tokens. Multiple tabs with the same session also work fine because they all share the same `session['csrf_token']` raw value.

### 6. Meta tag vs hidden inputs: hidden inputs are the right choice here

The meta tag approach looks like this:

```html
<head>
    <meta name="csrf-token" content="{{ csrf_token() }}">
</head>
```

JavaScript then reads the meta tag and sends the token in an `X-CSRFToken` header with AJAX requests.

**When to use meta tags:**
- Single-page applications (SPAs) or heavy AJAX usage.
- JavaScript-driven form submissions where forms are created dynamically in the DOM.

**When to use hidden inputs:**
- Server-rendered HTML forms submitted via standard browser POST.
- No JavaScript form handling.

This project uses standard HTML form submissions (POST from `<form>` elements). The hidden input approach is the correct choice. Using a meta tag would require JavaScript to read the tag and inject it into each form, which adds complexity with no security benefit. Since `{{ csrf_token() }}` returns the same cached value on every call, there is no duplication cost -- it is just the same string repeated in the HTML.

**One minor note:** The total page size increases by ~100 bytes per form (the hidden input HTML). With 200 forms, that is ~20 KB of repeated token strings. This is negligible for any modern connection but could be reduced with the meta tag + JS injection approach if page weight ever became a concern. It will not for this app.

## Recommended Plan Changes

- **Add `WTF_CSRF_TIME_LIMIT = None` to the app config.** Without this, any dashboard or calendar page left open for more than 1 hour will produce 400 errors on toggle submissions. For a personal single-user habit tracker, disabling the time limit is safe -- the session cookie provides the time boundary. If the plan has a config section, add this there. If not, add a note in the Flask app setup section.
- **No other changes needed.** The hidden input approach in `for` loops is correct, performant, and has no gotchas with POST-redirect-GET. The meta tag approach is unnecessary since there is no AJAX. Token generation with many forms has negligible cost.

## Sources

- Flask-WTF source code v1.2.2: `csrf.py` (generate_csrf, validate_csrf, CSRFProtect)
- Flask-WTF source code v1.2.2: `form.py` (FlaskForm, Meta class)
- itsdangerous source code: `timed.py` (TimestampSigner.unsign, max_age=None behavior)
- [Flask-WTF CSRF Documentation (1.3.x)](https://flask-wtf.readthedocs.io/en/latest/csrf/)
- [Flask-WTF Configuration Documentation (1.2.x)](https://flask-wtf.readthedocs.io/en/latest/config/)
- [PythonAnywhere CSRF Token Timeout Forum](https://www.pythonanywhere.com/forums/topic/27865/)
- [Flask-WTF GitHub Issue #195: CSRF for SPAs](https://github.com/lepture/flask-wtf/issues/195)
- [Flask-WTF GitHub Issue #320: hidden_tag with multiple forms](https://github.com/lepture/flask-wtf/issues/320)
