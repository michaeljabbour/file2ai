/* 
  Minimal single-file React for the "File2AI" logic. 
  We're ignoring all the fancy UI libraries from the original repo 
  and just focusing on the logic and simple HTML form usage.
*/

/* global React, ReactDOM */

const { useState, useEffect } = React;

function File2AI() {
  // Input type and source
  const [inputType, setInputType] = useState("file"); // "file" | "repo" | "local"
  const [files, setFiles] = useState(null);
  const [repoUrl, setRepoUrl] = useState("");
  const [branch, setBranch] = useState("");
  const [token, setToken] = useState("");
  const [localDir, setLocalDir] = useState("");
  
  // Output and processing
  const [outputFormat, setOutputFormat] = useState("text");
  const [jobId, setJobId] = useState(null);
  const [status, setStatus] = useState("idle"); // "idle" | "processing" | "completed" | "failed"
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState(null);
  
  // File filtering
  const [maxFileSize, setMaxFileSize] = useState(50); // Default 50KB
  const handleMaxFileSizeChange = (e) => {
    const newValue = parseInt(e.target.value, 10);
    if (!isNaN(newValue)) {
      setMaxFileSize(newValue);
    }
  };
  const [patternMode, setPatternMode] = useState("exclude"); // "exclude" | "include"
  const [patternInput, setPatternInput] = useState("");
  // In original code, result was more complex, but we'll keep it simple:
  const [result] = useState(null);
  const [preview, setPreview] = useState(null);

  // Fetch preview content
  const fetchPreview = async (id) => {
    try {
      const res = await fetch(`/preview/${id}`);
      const data = await res.json();
      if (data.error) {
        console.error("Preview error:", data.error);
        return;
      }
      setPreview(data);
    } catch (err) {
      console.error("Failed to fetch preview:", err);
    }
  };

  // Polling status check
  useEffect(() => {
    if (!jobId || status === "completed" || status === "failed") return;
    const interval = setInterval(async () => {
      try {
        // In a real app, you'd talk to your backend here:
        const res = await fetch(`/status/${jobId}`);
        const data = await res.json();
        if (data.error) {
          setError(data.error);
          setStatus("failed");
          return;
        }
        setProgress(data.progress || 0);
        if (data.status === "completed") {
          setStatus("completed");
          // Fetch preview if format is text
          if (outputFormat === "text") {
            fetchPreview(jobId);
          }
          // Trigger file download
          window.location.href = `/download/${jobId}`;
        } else if (data.status === "failed") {
          setStatus("failed");
          setError(data.errors?.join("\n") || "Conversion failed");
        }
      } catch (err) {
        setError("Failed to check job status");
        setStatus("failed");
      }
    }, 1000);
    return () => clearInterval(interval);
  }, [jobId, status]);

  async function handleSubmit(e) {
    e.preventDefault();
    setError(null);
    setStatus("processing");
    setProgress(0);

    // Prepare form data with correct command
    const formData = new FormData();
    formData.append("format", outputFormat || "text");  // Ensure format is never empty
    
    // Add file filtering parameters
    formData.append("max_file_size_kb", maxFileSize);
    formData.append("pattern_mode", patternMode);
    formData.append("pattern_input", patternInput);
    
    if (inputType === "file" && files?.length) {
      formData.append("command", "convert");
      // Log form data for debugging
      console.log("Format:", outputFormat);
      console.log("Files:", files);
      console.log("Max file size:", maxFileSize, "KB");
      console.log("Pattern mode:", patternMode);
      console.log("Pattern input:", patternInput);
      Array.from(files).forEach((f) => formData.append("file", f));
    } else if (inputType === "repo") {
      formData.append("command", "export");
      formData.append("repo_url", repoUrl);
      if (branch) formData.append("branch", branch);
      if (token) formData.append("token", token);
    } else if (inputType === "local" && localDir) {
      formData.append("command", "export");
      formData.append("local_dir", localDir);
    }

    try {
      // Again, you'd have a backend endpoint:
      const response = await fetch("/", { method: "POST", body: formData });
      const data = await response.json();
      if (data.error) {
        setError(data.error);
        setStatus("failed");
      } else {
        setJobId(data.job_id); // triggers polling
      }
    } catch (err) {
      setError("Failed to start conversion");
      setStatus("failed");
    }
  }

  // Render unified input section
  function renderInputSection() {
    return (
      <div className="input-section">
        {/* File Upload */}
        {inputType === "file" && (
          <div className="field">
            <input
              type="file"
              multiple
              onChange={(e) => setFiles(e.target.files)}
              className="input-field"
            />
            {files && <p className="text-small">{files.length} file(s) selected</p>}
          </div>
        )}

        {/* Repository URL */}
        {inputType === "repo" && (
          <div className="repo-inputs">
            <div className="field">
              <input
                type="text"
                placeholder="https://github.com/user/repo"
                value={repoUrl}
                onChange={(e) => setRepoUrl(e.target.value)}
                className="input-field"
              />
            </div>
            <div className="repo-row">
              <div className="repo-field">
                <input
                  type="text"
                  placeholder="Branch (optional)"
                  value={branch}
                  onChange={(e) => setBranch(e.target.value)}
                  className="input-field"
                />
              </div>
              <div className="repo-field">
                <input
                  type="password"
                  placeholder="Access Token (optional)"
                  value={token}
                  onChange={(e) => setToken(e.target.value)}
                  className="input-field"
                />
              </div>
            </div>
          </div>
        )}

        {/* Local Directory */}
        {inputType === "local" && (
          <div className="field">
            <p className="text-small">
              (Directory selection requires modern browser support)
            </p>
            <input
              type="file"
              webkitdirectory="true"
              directory="true"
              onChange={(e) => {
                const file = e.target.files?.[0];
                if (file) {
                  const topFolder = file.webkitRelativePath.split("/")[0] || "";
                  setLocalDir(topFolder);
                }
              }}
              className="input-field"
            />
            {localDir && <p className="text-small">Selected folder: {localDir}</p>}
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="container">
      <form onSubmit={handleSubmit} className="card">
        <div className="input-container">
          {/* Input Type Selector */}
          <div className="field">
            <select
              value={inputType}
              onChange={(e) => setInputType(e.target.value)}
              className="input-select"
            >
              <option value="file">Upload Files</option>
              <option value="repo">Git Repository</option>
              <option value="local">Local Directory</option>
            </select>
          </div>
          
          {/* Main Input Section */}
          <div className="input-section">
            {renderInputSection()}
          </div>
        </div>

        {/* Options Panel */}
        <div className="options-panel">
          <h3 className="panel-title">Processing Options</h3>
          
          {/* File Size Slider */}
          <div className="field">
            <label>Include files under: {maxFileSize}KB</label>
            <input
              type="range"
              min="1"
              max="1000"
              value={maxFileSize}
              onChange={handleMaxFileSizeChange}
              className="range-input"
            />
          </div>

          {/* Pattern Filter */}
          <div className="field">
            <label>Pattern Filter:</label>
            <div className="flex">
              <select
                value={patternMode}
                onChange={(e) => setPatternMode(e.target.value)}
                className="pattern-select"
              >
                <option value="exclude">Exclude</option>
                <option value="include">Include</option>
              </select>
              <input
                type="text"
                placeholder="*.md, src/, etc."
                value={patternInput}
                onChange={(e) => setPatternInput(e.target.value)}
                className="pattern-input"
              />
            </div>
          </div>

          {/* Output Format */}
          <div className="field">
            <label>Output Format:</label>
            <select
              value={outputFormat}
              onChange={(e) => setOutputFormat(e.target.value)}
              className="input-select"
            >
              <option value="text">Text</option>
              <option value="json">JSON</option>
              <option value="pdf">PDF</option>
              <option value="docx">DOCX</option>
              <option value="xlsx">XLSX</option>
              <option value="pptx">PPTX</option>
            </select>
          </div>
        </div>

        {/* Submit Button */}
        <button
          type="submit"
          className={`submit-button ${status === "processing" ? "processing" : ""}`}
          disabled={
            status === "processing" ||
            (inputType === "file" && !files?.length) ||
            (inputType === "repo" && !repoUrl) ||
            (inputType === "local" && !localDir)
          }
        >
          {status === "processing" ? `Processing... ${progress}%` : "Process Files"}
        </button>
      </form>

      {/* Status Card */}
      <div className="status-card card">
        <h2 className="status-title">Status</h2>
        
        {error && (
          <div className="error">
            {error}
          </div>
        )}
        
        {status === "processing" && (
          <div>
            <p className="status-message text-small">
              Converting files... {progress}%
            </p>
            <div className="progress-container">
              <div
                className="progress-bar"
                style={{ width: `${progress}%` }}
              ></div>
            </div>
          </div>
        )}
        
        {status === "completed" && (
          <div className="success-message">
            Conversion complete! (Download triggered)
          </div>
        )}
        
        {result && (
          <div className="result-section">
            <p className="result-item">
              <strong>Files analyzed:</strong> {result.files_analyzed}
            </p>
            <p className="result-item">
              <strong>Total tokens:</strong> {result.total_tokens}
            </p>
            <p className="result-item">
              <strong>Characters:</strong> {result.total_chars}
            </p>
          </div>
        )}
        
        {/* Preview Section */}
        {preview && outputFormat === "text" && (
          <div className="preview-section">
            <div className="preview-header">
              <span className="preview-title">Text Preview</span>
              <span className="text-small">{preview.file}</span>
            </div>
            <pre className="preview-content">
              {preview.preview}
            </pre>
          </div>
        )}
      </div>
    </div>
  );
}

function App() {
  return (
    <div>
      <div className="title">
        <span style={{ fontSize: "2rem" }}>🤖</span>
        <h1>File2AI</h1>
      </div>
      <p style={{ color: "#666", marginBottom: "1.5rem" }}>
        Transform your files into AI-ready format (Minimal Flattened Demo)
      </p>
      <File2AI />
    </div>
  );
}

// Render
ReactDOM.createRoot(document.getElementById("root")).render(<App />);
