document.addEventListener('DOMContentLoaded', function () {
  var form = document.getElementById('register-form');
  var nameInput = document.getElementById('name');
  var emailInput = document.getElementById('email');
  var roleInput = document.getElementById('role');
  var submitBtn = document.getElementById('submit-btn');
  var formError = document.getElementById('form-error');

  var VALID_ROLES = ['Writer', 'Director', 'Composer', 'Post-Production', 'Student', 'Other'];
  var EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

  function showFieldError(id, msg) {
    var el = document.getElementById(id + '-error');
    var input = document.getElementById(id);
    el.textContent = msg;
    if (msg) {
      input.classList.add('invalid');
    } else {
      input.classList.remove('invalid');
    }
  }

  function validateName() {
    var val = nameInput.value.trim();
    if (!val) {
      showFieldError('name', 'Name is required');
      return false;
    }
    if (val.length > 100) {
      showFieldError('name', 'Name must be 100 characters or fewer');
      return false;
    }
    showFieldError('name', '');
    return true;
  }

  function validateEmail() {
    var val = emailInput.value.trim();
    if (!val) {
      showFieldError('email', 'Email is required');
      return false;
    }
    if (!EMAIL_RE.test(val)) {
      showFieldError('email', 'Enter a valid email address');
      return false;
    }
    showFieldError('email', '');
    return true;
  }

  function validateRole() {
    var val = roleInput.value;
    if (!val || VALID_ROLES.indexOf(val) === -1) {
      showFieldError('role', 'Select a valid role');
      return false;
    }
    showFieldError('role', '');
    return true;
  }

  function validateAll() {
    var a = validateName();
    var b = validateEmail();
    var c = validateRole();
    return a && b && c;
  }

  nameInput.addEventListener('blur', validateName);
  emailInput.addEventListener('blur', validateEmail);
  roleInput.addEventListener('change', validateRole);

  form.addEventListener('submit', function (e) {
    e.preventDefault();
    formError.hidden = true;
    formError.textContent = '';

    if (!validateAll()) return;

    submitBtn.disabled = true;
    submitBtn.textContent = 'Submitting...';

    var payload = {
      name: nameInput.value.trim(),
      email: emailInput.value.trim(),
      role: roleInput.value
    };

    fetch('/api/register', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    })
      .then(function (res) {
        return res.json().then(function (data) {
          return { status: res.status, body: data };
        });
      })
      .then(function (result) {
        if (result.status === 201) {
          if (result.body.status === 'pending_payment' && result.body.checkout_url) {
            window.location.href = result.body.checkout_url;
            return;
          }
          if (result.body.queue_position !== undefined) {
            formError.hidden = false;
            formError.className = 'waitlist-msg';
            formError.textContent = 'You have been added to the waitlist. Queue position: ' + result.body.queue_position;
            submitBtn.disabled = false;
            submitBtn.textContent = 'Register';
            return;
          }
          window.location.href = '/register/success?registrant_id=' + encodeURIComponent(result.body.id || '');
          return;
        }
        formError.hidden = false;
        formError.className = 'error-banner';
        formError.textContent = result.body.error || 'Registration failed. Please try again.';
        submitBtn.disabled = false;
        submitBtn.textContent = 'Register';
      })
      .catch(function () {
        formError.hidden = false;
        formError.className = 'error-banner';
        formError.textContent = 'Unable to reach the server. Please try again later.';
        submitBtn.disabled = false;
        submitBtn.textContent = 'Register';
      });
  });
});
