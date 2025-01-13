/* 
  Vanilla JavaScript implementation for File2AI
  Modern interface with minimal dependencies
*/

document.addEventListener('DOMContentLoaded', () => {
  // Application state
  const state = {
    inputType: 'file', // 'file' | 'repo' | 'local'
    files: null,
    repoUrl: '',
    branch: '',
    token: '',
    localDir: '',
    outputFormat: 'text',
    jobId: null,
    status: 'idle', // 'idle' | 'processing' | 'completed' | 'failed'
    progress: 0,
    error: null,
    maxFileSize: 50, // Default 50KB
    patternMode: 'exclude', // 'exclude' | 'include'
    patternInput: '',
    preview: null,
    result: null
  };

  // DOM Elements
  const elements = {
    form: document.getElementById('uploadForm'),
    inputType: document.getElementById('inputType'),
    fileInput: document.getElementById('fileInput'),
    repoUrl: document.getElementById('repoUrl'),
    branch: document.getElementById('branch'),
    token: document.getElementById('token'),
    localDir: document.getElementById('localDir'),
    outputFormat: document.getElementById('outputFormat'),
    maxFileSize: document.getElementById('maxFileSize'),
    maxFileSizeLabel: document.getElementById('maxFileSizeLabel'),
    patternMode: document.getElementById('patternMode'),
    patternInput: document.getElementById('patternInput'),
    submitButton: document.getElementById('submitButton'),
    progressBar: document.getElementById('progressBar'),
    progressText: document.getElementById('progressText'),
    errorContainer: document.getElementById('errorContainer'),
    previewContainer: document.getElementById('previewContainer'),
    previewContent: document.getElementById('previewContent'),
    sections: {
      file: document.getElementById('fileSection'),
      repo: document.getElementById('repoSection'),
      local: document.getElementById('localSection')
    }
  };

  // UI Update Functions
  function updateInputSection() {
    Object.entries(elements.sections).forEach(([type, section]) => {
      section.style.display = state.inputType === type ? 'block' : 'none';
    });
  }

  function updateMaxFileSizeLabel() {
    elements.maxFileSizeLabel.textContent = `Include files under: ${state.maxFileSize}KB`;
  }

  function updateSubmitButton() {
    const isValid = (
      (state.inputType === 'file' && state.files?.length) ||
      (state.inputType === 'repo' && state.repoUrl) ||
      (state.inputType === 'local' && state.localDir)
    );
    elements.submitButton.disabled = !isValid || state.status === 'processing';
    elements.submitButton.textContent = state.status === 'processing' 
      ? `Processing... ${state.progress}%` 
      : 'Process Files';
  }

  // Preview Functions
  async function fetchPreview(id) {
    try {
      const res = await fetch(`/preview/${id}`);
      const data = await res.json();
      if (data.error) {
        console.error('Preview error:', data.error);
        return;
      }
      state.preview = data;
      showPreview();
    } catch (err) {
      console.error('Failed to fetch preview:', err);
    }
  }

  function showPreview() {
    if (!state.preview) return;
    elements.previewContent.textContent = state.preview.preview;
    elements.previewContainer.style.display = 'block';
  }

  function showError(message) {
    elements.errorContainer.textContent = message;
    elements.errorContainer.style.display = 'block';
  }

  async function checkJobStatus() {
    try {
      const response = await fetch(`/status/${state.jobId}`);
      const data = await response.json();
      
      if (data.error) {
        state.error = data.error;
        state.status = 'failed';
        showError(data.error);
        return;
      }

      state.progress = data.progress || 0;
      updateSubmitButton();

      if (data.status === 'completed') {
        state.status = 'completed';
        if (state.outputFormat === 'text') {
          await fetchPreview(state.jobId);
        }
        window.location.href = `/download/${state.jobId}`;
        elements.progressBar.style.display = 'none';
      } else if (data.status === 'failed') {
        state.status = 'failed';
        state.error = data.errors?.join('\n') || 'Conversion failed';
        showError(state.error);
      } else {
        setTimeout(checkJobStatus, 1000);
      }
    } catch (err) {
      state.error = 'Failed to check job status';
      state.status = 'failed';
      showError(state.error);
    }
  }

  // Event Listeners
  elements.inputType.addEventListener('change', (e) => {
    state.inputType = e.target.value;
    updateInputSection();
    updateSubmitButton();
  });

  elements.fileInput.addEventListener('change', (e) => {
    state.files = e.target.files;
    updateSubmitButton();
  });

  elements.repoUrl.addEventListener('input', (e) => {
    state.repoUrl = e.target.value;
    updateSubmitButton();
  });

  elements.branch.addEventListener('input', (e) => {
    state.branch = e.target.value;
  });

  elements.token.addEventListener('input', (e) => {
    state.token = e.target.value;
  });

  elements.localDir.addEventListener('change', (e) => {
    const file = e.target.files?.[0];
    if (file) {
      state.localDir = file.webkitRelativePath.split('/')[0] || '';
      updateSubmitButton();
    }
  });

  elements.outputFormat.addEventListener('change', (e) => {
    state.outputFormat = e.target.value;
  });

  elements.maxFileSize.addEventListener('input', (e) => {
    const newValue = parseInt(e.target.value, 10);
    if (!isNaN(newValue)) {
      state.maxFileSize = newValue;
      updateMaxFileSizeLabel();
    }
  });

  elements.patternMode.addEventListener('change', (e) => {
    state.patternMode = e.target.value;
  });

  elements.patternInput.addEventListener('input', (e) => {
    state.patternInput = e.target.value;
  });

  // Form Submission
  elements.form.addEventListener('submit', async (e) => {
    e.preventDefault();
    state.error = null;
    state.status = 'processing';
    state.progress = 0;
    elements.errorContainer.style.display = 'none';
    elements.progressBar.style.display = 'block';
    updateSubmitButton();

    const formData = new FormData();
    formData.append('format', state.outputFormat);
    formData.append('max_file_size_kb', state.maxFileSize);
    formData.append('pattern_mode', state.patternMode);
    formData.append('pattern_input', state.patternInput);

    if (state.inputType === 'file' && state.files?.length) {
      formData.append('command', 'convert');
      Array.from(state.files).forEach((f) => formData.append('file', f));
    } else if (state.inputType === 'repo') {
      formData.append('command', 'export');
      formData.append('repo_url', state.repoUrl);
      if (state.branch) formData.append('branch', state.branch);
      if (state.token) formData.append('token', state.token);
    } else if (state.inputType === 'local') {
      formData.append('command', 'export');
      formData.append('local_dir', state.localDir);
    }

    try {
      const response = await fetch('/', {
        method: 'POST',
        body: formData
      });
      const data = await response.json();
      
      if (data.error) {
        state.error = data.error;
        state.status = 'failed';
        showError(data.error);
      } else {
        state.jobId = data.job_id;
        checkJobStatus();
      }
    } catch (err) {
      state.error = 'Failed to start conversion';
      state.status = 'failed';
      showError(state.error);
    }
  });

  // Initialize UI
  updateInputSection();
  updateMaxFileSizeLabel();
  updateSubmitButton();
});
