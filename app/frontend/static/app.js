const form = document.querySelector('#admission-form');
const status = document.querySelector('#status');

form.addEventListener('submit', async (event) => {
  event.preventDefault();
  status.textContent = 'Submitting...';
  status.className = '';

  try {
    const response = await fetch('/api/admissions', {
      method: 'POST',
      body: new FormData(form),
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || 'Submission failed.');
    status.textContent = result.message;
    status.className = 'success';
    form.reset();
  } catch (error) {
    status.textContent = error.message;
    status.className = 'error';
  }
});
