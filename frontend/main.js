/* 
  Vanilla JavaScript implementation for File2AI
  Modern interface with minimal dependencies
*/

document.addEventListener('DOMContentLoaded', () => {
  // Application state with default values
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
    maxFileSize: 100, // Default 100KB
    patternMode: 'exclude', // 'exclude' | 'include'
    patternInput: '', // Default empty string for no patterns
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
    const hasFiles = state.files && state.files.length > 0;
    const hasRepoUrl = Boolean(state.repoUrl && state.repoUrl.trim());
    const hasLocalDir = Boolean(state.localDir && state.localDir.trim());
    const isValidGithubUrl = hasRepoUrl && (
      state.repoUrl.trim().match(/^https:\/\/github\.com\/[^/]+\/[^/]+/) ||
      state.repoUrl.trim().match(/^github\.com\/[^/]+\/[^/]+/)
    );
    
    // For local directory mode, we consider it valid if we have files with webkitRelativePath
    const hasValidLocalDir = state.inputType === 'local' && hasFiles && 
      Array.from(state.files).some(f => f.webkitRelativePath);
    
    // If we have valid local directory files, ensure state.localDir is set
    if (hasValidLocalDir && !state.localDir) {
      const firstFile = state.files[0];
      if (firstFile?.webkitRelativePath) {
        state.localDir = firstFile.webkitRelativePath.split('/')[0];
      }
    }
    
    const isValid = (
      (state.inputType === 'file' && hasFiles) ||
      (state.inputType === 'repo' && isValidGithubUrl) ||
      hasValidLocalDir
    );
    
    console.log('Form validation state:', {
      inputType: state.inputType,
      hasFiles,
      repoUrl: hasRepoUrl,
      localDir: hasLocalDir,
      isValid,
      status: state.status
    });
    
    const isProcessing = state.status === 'processing';
    const isFailed = state.status === 'failed';
    
    // Enable button if form is valid and not processing, or if there was an error
    elements.submitButton.disabled = (!isValid && !isFailed) || isProcessing;
    
    if (isProcessing) {
      elements.submitButton.textContent = `Processing... ${state.progress}%`;
      elements.progressBar.style.display = 'block';
      const progressBarEl = elements.progressBar.querySelector('.progress-bar');
      if (progressBarEl) {
        progressBarEl.style.width = `${state.progress}%`;
      }
    } else if (isFailed) {
      elements.submitButton.textContent = 'Failed - Try Again';
      elements.progressBar.style.display = 'none';
      // Re-enable button to allow retry
      elements.submitButton.disabled = false;
    } else {
      elements.submitButton.textContent = 'Process Files';
      elements.progressBar.style.display = 'none';
    }
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
    
    // Update preview content
    elements.previewContent.textContent = state.preview.preview;
    elements.previewContainer.style.display = 'block';
    
    // Add copy button if not already present
    let copyButton = elements.previewContainer.querySelector('.copy-button');
    if (!copyButton) {
      copyButton = document.createElement('button');
      copyButton.className = 'copy-button';
      copyButton.textContent = 'Copy';
      copyButton.addEventListener('click', async () => {
        if (!navigator.clipboard) {
          console.error('Clipboard API not available');
          return;
        }
        try {
          await navigator.clipboard.writeText(state.preview.preview);
          copyButton.textContent = 'Copied!';
          copyButton.classList.add('copied');
          setTimeout(() => {
            copyButton.textContent = 'Copy';
            copyButton.classList.remove('copied');
          }, 2000);
        } catch (err) {
          console.error('Failed to copy:', err);
          copyButton.textContent = 'Copy failed';
          setTimeout(() => {
            copyButton.textContent = 'Copy';
          }, 2000);
        }
      });
      
      // Find or create preview header
      let previewHeader = elements.previewContainer.querySelector('.preview-header');
      if (!previewHeader) {
        previewHeader = document.createElement('div');
        previewHeader.className = 'preview-header';
        const title = document.createElement('span');
        title.className = 'preview-title';
        title.textContent = 'Text Preview';
        previewHeader.appendChild(title);
        elements.previewContainer.insertBefore(previewHeader, elements.previewContent);
      }
      
      previewHeader.appendChild(copyButton);
    }
  }

  function showError(message) {
    elements.errorContainer.textContent = message;
    elements.errorContainer.style.display = 'block';
  }

  // Status polling interval reference
  let statusInterval = null;

  function startPolling() {
    if (statusInterval) return; // Don't start multiple intervals
    statusInterval = setInterval(checkJobStatus, 1000);
  }

  function stopPolling() {
    if (statusInterval) {
      clearInterval(statusInterval);
      statusInterval = null;
    }
  }

  async function checkJobStatus() {
    if (!state.jobId || state.status === 'completed' || state.status === 'failed') {
      stopPolling();
      return;
    }

    try {
      const response = await fetch(`/status/${state.jobId}`);
      const data = await response.json();
      
      if (data.error) {
        state.error = data.error;
        state.status = 'failed';
        showError(data.error);
        stopPolling();
        return;
      }

      state.progress = data.progress || 0;
      const progressBarEl = elements.progressBar.querySelector('.progress-bar');
      if (progressBarEl) {
        progressBarEl.style.width = `${state.progress}%`;
      }
      updateSubmitButton();

      if (data.status === 'completed') {
        state.status = 'completed';
        if (state.outputFormat === 'text') {
          await fetchPreview(state.jobId);
        }
        window.location.href = `/download/${state.jobId}`;
        elements.progressBar.style.display = 'none';
        stopPolling();
      } else if (data.status === 'failed') {
        state.status = 'failed';
        state.error = data.errors?.join('\n') || 'Conversion failed';
        showError(state.error);
        stopPolling();
      }
    } catch (err) {
      state.error = 'Failed to check job status';
      state.status = 'failed';
      showError(state.error);
      stopPolling();
    }
  }

  // No example repositories in this version

  // Event Listeners
  elements.inputType.addEventListener('change', (e) => {
    state.inputType = e.target.value;
    // Reset all form state
    state.status = 'idle';
    state.error = null;
    state.files = null;
    state.repoUrl = '';
    state.branch = '';
    state.token = '';
    state.localDir = '';
    state.jobId = null;
    state.progress = 0;
    
    // Reset UI elements
    elements.errorContainer.style.display = 'none';
    elements.progressBar.style.display = 'none';
    elements.previewContainer.style.display = 'none';
    if (elements.repoUrl) elements.repoUrl.value = '';
    if (elements.branch) elements.branch.value = '';
    if (elements.token) elements.token.value = '';
    if (elements.fileInput) elements.fileInput.value = '';
    
    updateInputSection();
    updateSubmitButton();
    console.log('Input type changed:', state.inputType);
  });

  elements.fileInput.addEventListener('change', (e) => {
    state.files = e.target.files;
    state.status = 'idle';  // Reset status when new files are selected
    state.error = null;     // Clear any previous errors
    elements.errorContainer.style.display = 'none';
    elements.progressBar.style.display = 'none';
    console.log('File input change:', {
      files: state.files,
      length: state.files?.length,
      names: Array.from(state.files || []).map(f => f.name)
    });
    updateSubmitButton();
  });

  elements.repoUrl.addEventListener('input', (e) => {
    state.repoUrl = e.target.value;
    state.status = 'idle';
    updateSubmitButton();
  });

  elements.branch.addEventListener('input', (e) => {
    state.branch = e.target.value;
  });

  elements.token.addEventListener('input', (e) => {
    state.token = e.target.value;
  });

  // Directory Tree Functions
  function createDirectoryTree(files) {
    const tree = {};
    Array.from(files).forEach(file => {
      const parts = file.webkitRelativePath.split('/');
      let current = tree;
      parts.forEach((part, i) => {
        if (!current[part]) {
          current[part] = i === parts.length - 1 ? null : {};
        }
        if (i < parts.length - 1) {
          current = current[part];
        }
      });
    });
    return tree;
  }

  function renderDirectoryTree(tree, level = 0) {
    const container = document.createElement('div');
    container.className = 'directory-tree';
    
    Object.entries(tree).forEach(([name, subtree]) => {
      const item = document.createElement('div');
      item.className = `directory-item ${subtree === null ? 'file' : 'folder'}`;
      item.style.paddingLeft = `${level * 20}px`;
      item.textContent = name;
      container.appendChild(item);
      
      if (subtree !== null) {
        container.appendChild(renderDirectoryTree(subtree, level + 1));
      }
    });
    
    return container;
  }

  // Configure directory input element when input type changes
  function configureDirectoryInput() {
    if (elements.localDir && state.inputType === 'local') {
      // Create a new input element with directory selection enabled
      const newInput = document.createElement('input');
      newInput.type = 'file';
      newInput.id = elements.localDir.id;
      newInput.className = elements.localDir.className;
      
      // Set directory selection attributes
      newInput.setAttribute('webkitdirectory', '');
      newInput.setAttribute('directory', '');
      newInput.setAttribute('multiple', '');
      newInput.webkitdirectory = true;
      newInput.directory = true;
      newInput.multiple = true;
      
      // Replace old input with new one
      const parent = elements.localDir.parentNode;
      parent.replaceChild(newInput, elements.localDir);
      elements.localDir = newInput;
      
      // Reattach event listener to new input
      elements.localDir.addEventListener('change', (e) => {
        const files = e.target.files;
        if (files?.length) {
          // Get directory path from first file
          const relativePath = files[0].webkitRelativePath;
          const dirPath = relativePath.split('/')[0];
          state.localDir = dirPath;
          state.files = files;
          
          // Create and display directory tree
          const tree = createDirectoryTree(files);
          const treeElement = renderDirectoryTree(tree);
          
          // Find or create container for directory tree
          let container = document.getElementById('directoryTree');
          if (!container) {
            container = document.createElement('div');
            container.id = 'directoryTree';
            elements.sections.local.appendChild(container);
          }
          
          // Update container content
          container.innerHTML = '';
          container.appendChild(treeElement);
          
          console.log('Directory selected:', {
            dirPath,
            fileCount: files.length,
            firstFile: relativePath
          });
          
          updateSubmitButton();
        }
      });
      
      console.log('Directory input reconfigured:', {
        webkitdirectory: elements.localDir.webkitdirectory,
        directory: elements.localDir.directory,
        multiple: elements.localDir.multiple
      });
    }
  }
  
  // Initial configuration
  configureDirectoryInput();
  
  // Reconfigure when input type changes
  elements.inputType.addEventListener('change', () => {
    configureDirectoryInput();
  });

  elements.localDir.addEventListener('change', (e) => {
    const files = e.target.files;
    if (files?.length) {
      // Get directory path from first file
      const relativePath = files[0].webkitRelativePath;
      const dirPath = relativePath.split('/')[0];
      state.localDir = dirPath;
      // Store directory files for filtering
      state.files = files;
      
      // Create and display directory tree
      const tree = createDirectoryTree(files);
      const treeElement = renderDirectoryTree(tree);
      
      // Find or create container for directory tree
      let container = document.getElementById('directoryTree');
      if (!container) {
        container = document.createElement('div');
        container.id = 'directoryTree';
        elements.sections.local.appendChild(container);
      }
      
      // Update container content
      container.innerHTML = '';
      container.appendChild(treeElement);
      
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
    console.log('Form submitted');
    
    state.error = null;
    state.status = 'processing';
    state.progress = 0;
    elements.errorContainer.style.display = 'none';
    elements.progressBar.style.display = 'block';
    updateSubmitButton();

    const formData = new FormData();
    console.log('Form state:', {
      inputType: state.inputType,
      files: state.files,
      outputFormat: state.outputFormat,
      maxFileSize: state.maxFileSize,
      patternMode: state.patternMode,
      patternInput: state.patternInput
    });
    
    // Add core parameters with fallback defaults
    formData.append('format', state.outputFormat || 'text');
    formData.append('max_file_size_kb', state.maxFileSize || 100);
    formData.append('pattern_mode', state.patternMode || 'exclude');
    formData.append('pattern_input', state.patternInput || '');
    
    // Handle file uploads
    if (state.inputType === 'file' && state.files?.length) {
      console.log('Processing file upload');
      formData.append('command', 'convert');
      Array.from(state.files).forEach((f) => {
        console.log('Appending file:', f.name);
        formData.append('file', f);
      });
    } 
    // Handle repository export
    else if (state.inputType === 'repo') {
      console.log('Processing repository export');
      formData.append('command', 'export');
      // Clean and normalize repository URL
      let cleanUrl = state.repoUrl.trim();
      if (!cleanUrl.startsWith('http')) {
        cleanUrl = 'https://' + cleanUrl;
      }
      // Remove /tree/branch and any trailing HEAD
      cleanUrl = cleanUrl.replace(/\/tree\/[^/]+(?:\s+HEAD)?$/, '');
      formData.append('repo_url', cleanUrl);
      
      // Extract branch from URL or use provided branch
      let branch = state.branch;
      if (!branch && state.repoUrl.includes('/tree/')) {
        const branchMatch = state.repoUrl.match(/\/tree\/([^/]+)/);
        if (branchMatch) {
          branch = branchMatch[1];
        }
      }
      
      if (branch) {
        // Clean branch name - remove HEAD and sanitize spaces
        branch = branch.replace(/\s+HEAD$/, '').trim();
        // Replace spaces with empty string for compatibility
        branch = branch.replace(/\s+/g, '');
        formData.append('branch', branch);
        console.log('Using branch:', branch);
      }
      
      if (state.token) formData.append('token', state.token);
    } 
    // Handle local directory
    else if (state.inputType === 'local' && state.files) {
      console.log('Processing local directory');
      formData.append('command', 'export');
      
      // Get directory path from first file's relative path
      if (state.files[0]?.webkitRelativePath) {
        const dirPath = state.files[0].webkitRelativePath.split('/')[0];
        formData.append('local_dir', dirPath);
        console.log('Using directory path:', dirPath);
      }
      
      // Filter and append files
      Array.from(state.files).forEach(file => {
        const size = file.size / 1024; // Convert to KB
        if (size <= state.maxFileSize) {
          // Use proper pattern matching based on file's relative path
          const relativePath = file.webkitRelativePath;
          let shouldInclude = true;
          
          if (state.patternInput) {
            const patterns = state.patternInput.split(';').filter(p => p.trim());
            const matches = patterns.some(pattern => {
              // Normalize pattern to match backend's Path.match() behavior
              let normalizedPattern = pattern.trim();
              // Remove trailing slashes
              while (normalizedPattern.endsWith('/')) {
                normalizedPattern = normalizedPattern.slice(0, -1);
              }
              // Handle directory patterns
              if (normalizedPattern.includes('/') && !normalizedPattern.startsWith('**/')) {
                normalizedPattern = `**/${normalizedPattern}`;
              }
              // Handle extension patterns
              if (normalizedPattern.startsWith('*.') && !normalizedPattern.includes('/')) {
                normalizedPattern = `**/${normalizedPattern}`;
              }
              // Use minimatch for glob pattern matching
              return minimatch(relativePath, normalizedPattern);
            });
            
            shouldInclude = (state.patternMode === 'include') ? matches : !matches;
          }
          
          if (shouldInclude) {
            formData.append('directory_files[]', file);
            console.log('Including file:', relativePath);
          }
        }
      });
    }

    try {
      console.log('Sending form data:', {
        command: formData.get('command'),
        format: formData.get('format'),
        files: formData.getAll('file').map(f => f.name)
      });
      
      const response = await fetch('/', {
        method: 'POST',
        body: formData
      });
      
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      
      const data = await response.json();
      console.log('Server response:', data);
      
      if (data.error) {
        state.error = data.error;
        state.status = 'failed';
        showError(data.error);
      } else {
        state.jobId = data.job_id;
        console.log('Starting polling for job:', state.jobId);
        startPolling(); // Start polling for status updates
      }
    } catch (err) {
      console.error('Form submission error:', err);
      state.error = 'Failed to start conversion: ' + err.message;
      state.status = 'failed';
      showError(state.error);
    }
  });

  // Initialize UI
  updateInputSection();
  updateMaxFileSizeLabel();
  updateSubmitButton();
});
