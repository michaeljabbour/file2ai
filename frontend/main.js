/* 
  Minimal single-file React for the "File2AI" logic. 
  We're ignoring all the fancy UI libraries from the original repo 
  and just focusing on the logic and simple HTML form usage.
*/

/* global React, ReactDOM */

const { useState, useEffect } = React;

function File2AI() {
  const [selectedTab, setSelectedTab] = useState("file"); // "file" | "repo" | "local"
  const [files, setFiles] = useState(null);
  const [repoUrl, setRepoUrl] = useState("");
  const [branch, setBranch] = useState("");
  const [token, setToken] = useState("");
  const [localDir, setLocalDir] = useState("");
  const [outputFormat, setOutputFormat] = useState("text");
  const [jobId, setJobId] = useState(null);
  const [status, setStatus] = useState("idle"); // "idle" | "processing" | "completed" | "failed"
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState(null);
  // In original code, result was more complex, but we'll keep it simple:
  const [result] = useState(null);

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
          // Download attempt, e.g. window.location = `/download/${jobId}`;
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
    formData.append("format", outputFormat);

    if (selectedTab === "file" && files?.length) {
      formData.append("command", "convert");
      Array.from(files).forEach((f) => formData.append("file", f));
    } else if (selectedTab === "repo") {
      formData.append("command", "export");
      formData.append("repo_url", repoUrl);
      if (branch) formData.append("branch", branch);
      if (token) formData.append("token", token);
    } else if (selectedTab === "local" && localDir) {
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

  // Simple tab content render
  function renderTabContents() {
    switch (selectedTab) {
      case "file":
        return (
          <div className="field">
            <input
              type="file"
              multiple
              onChange={(e) => setFiles(e.target.files)}
            />
            {files && <p className="text-small">{files.length} file(s) selected</p>}
          </div>
        );
      case "repo":
        return (
          <>
            <div className="field">
              <label>Repository URL:</label>
              <input
                type="text"
                placeholder="https://github.com/user/repo"
                value={repoUrl}
                onChange={(e) => setRepoUrl(e.target.value)}
              />
            </div>
            <div className="field">
              <label>Branch (optional):</label>
              <input
                type="text"
                placeholder="main"
                value={branch}
                onChange={(e) => setBranch(e.target.value)}
              />
            </div>
            <div className="field">
              <label>Access Token (optional):</label>
              <input
                type="password"
                placeholder="For private repos"
                value={token}
                onChange={(e) => setToken(e.target.value)}
              />
            </div>
          </>
        );
      case "local":
        return (
          <>
            <p className="text-small">
              (Selecting a directory depends on advanced file APIs, 
              may not work in all browsers)
            </p>
            <input
              type="file"
              webkitdirectory="true"
              directory="true"
              onChange={(e) => {
                const file = e.target.files?.[0];
                if (file) {
                  // Using webkitRelativePath to get top-level folder name
                  const topFolder = file.webkitRelativePath.split("/")[0] || "";
                  setLocalDir(topFolder);
                }
              }}
            />
            {localDir && <p className="text-small">Selected folder: {localDir}</p>}
          </>
        );
      default:
        return null;
    }
  }

  return (
    <div>
      <h2 style={{ marginBottom: "1rem" }}>Input Source</h2>

      <div style={{ display: "flex", gap: "0.5rem", marginBottom: "1rem" }}>
        <button
          type="button"
          style={{
            background: selectedTab === "file" ? "#0074d9" : "#ccc",
          }}
          onClick={() => setSelectedTab("file")}
        >
          Files
        </button>
        <button
          type="button"
          style={{
            background: selectedTab === "repo" ? "#0074d9" : "#ccc",
          }}
          onClick={() => setSelectedTab("repo")}
        >
          Repository
        </button>
        <button
          type="button"
          style={{
            background: selectedTab === "local" ? "#0074d9" : "#ccc",
          }}
          onClick={() => setSelectedTab("local")}
        >
          Local Dir
        </button>
      </div>

      <form onSubmit={handleSubmit} className="card">
        {renderTabContents()}

        <div className="field">
          <label>Output Format:</label>
          <select
            value={outputFormat}
            onChange={(e) => setOutputFormat(e.target.value)}
          >
            <option value="text">Text</option>
            <option value="json">JSON</option>
            <option value="pdf">PDF</option>
            <option value="docx">DOCX</option>
            <option value="xlsx">XLSX</option>
            <option value="pptx">PPTX</option>
          </select>
        </div>

        <button
          type="submit"
          disabled={
            status === "processing" ||
            (selectedTab === "file" && !files?.length) ||
            (selectedTab === "repo" && !repoUrl) ||
            (selectedTab === "local" && !localDir)
          }
        >
          {status === "processing" ? `Processing... ${progress}%` : "Process"}
        </button>
      </form>

      <div className="card">
        <h2 style={{ marginBottom: "1rem" }}>Status</h2>
        {error && <div className="error">{error}</div>}
        {status === "processing" && (
          <div>
            <p className="text-small">Converting files... {progress}%</p>
            <div className="progress-container">
              <div
                className="progress-bar"
                style={{ width: `${progress}%` }}
              ></div>
            </div>
          </div>
        )}
        {status === "completed" && (
          <div style={{ color: "green" }}>Conversion complete! (Download triggered)</div>
        )}
        {result && (
          <div style={{ marginTop: "1rem" }}>
            <p>
              <strong>Files analyzed:</strong> {result.files_analyzed}
            </p>
            <p>
              <strong>Total tokens:</strong> {result.total_tokens}
            </p>
            <p>
              <strong>Characters:</strong> {result.total_chars}
            </p>
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
