import React, { useState, useEffect } from 'react';
import { Card } from './ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from './ui/tabs';
import { 
  FileText, GitBranch, FolderOpen, Bot, RefreshCw, 
  UploadCloud, AlertCircle 
} from 'lucide-react';

interface ConversionResult {
  files_analyzed: number;
  total_tokens?: number;
  total_chars?: number;
}

const File2AI: React.FC = () => {
  const [selectedTab, setSelectedTab] = useState('file');
  const [files, setFiles] = useState<FileList | null>(null);
  const [repoUrl, setRepoUrl] = useState('');
  const [localDir, setLocalDir] = useState('');
  const [branch, setBranch] = useState('');
  const [token, setToken] = useState('');
  const [outputFormat, setOutputFormat] = useState('text');
  const [jobId, setJobId] = useState<string | null>(null);
  const [status, setStatus] = useState<'idle' | 'processing' | 'completed' | 'failed'>('idle');
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [result] = useState<ConversionResult | null>(null);

  useEffect(() => {
    if (!jobId || status === 'completed' || status === 'failed') return;

    const interval = setInterval(async () => {
      try {
        const response = await fetch(`/status/${jobId}`);
        const data = await response.json();
        
        if (data.error) {
          setError(data.error);
          setStatus('failed');
          return;
        }

        setProgress(data.progress);
        if (data.status === 'completed' || data.status === 'completed_with_errors') {
          setStatus('completed');
          window.location.href = `/download/${jobId}`;
          fetch(`/cleanup/${jobId}`);
        } else if (data.status === 'failed') {
          setStatus('failed');
          setError(data.errors?.join('\n') || 'Conversion failed');
        }
      } catch (err) {
        setError('Failed to check job status');
        setStatus('failed');
      }
    }, 1000);

    return () => clearInterval(interval);
  }, [jobId, status]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setStatus('processing');
    setProgress(0);
    
    const formData = new FormData();
    formData.append('format', outputFormat);

    if (selectedTab === 'file' && files) {
      Array.from(files).forEach(file => formData.append('file', file));
    } else if (selectedTab === 'repo') {
      formData.append('repo_url', repoUrl);
      if (branch) formData.append('branch', branch);
      if (token) formData.append('token', token);
    } else if (selectedTab === 'local') {
      formData.append('local_dir', localDir);
    }

    try {
      const response = await fetch('/', {
        method: 'POST',
        body: formData
      });
      
      const data = await response.json();
      if (data.error) {
        setError(data.error);
        setStatus('failed');
      } else {
        setJobId(data.job_id);
      }
    } catch (err) {
      setError('Failed to start conversion');
      setStatus('failed');
    }
  };

  return (
    <div className="min-h-screen bg-gray-50 p-8">
      <div className="max-w-6xl mx-auto">
        <div className="text-center mb-8">
          <div className="flex items-center justify-center gap-3 mb-4">
            <Bot className="w-12 h-12 text-blue-600" />
            <h1 className="text-4xl font-bold">File2AI</h1>
          </div>
          <p className="text-lg text-gray-600">
            Transform your files into AI-ready format
          </p>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
          <Card>
            <div className="p-6">
              <h2 className="text-xl font-semibold mb-4">Input Source</h2>
              <form onSubmit={handleSubmit} className="space-y-6">
                <Tabs value={selectedTab} onValueChange={setSelectedTab}>
                  <TabsList className="grid w-full grid-cols-3">
                    <TabsTrigger value="file" className="flex items-center gap-2">
                      <FileText className="w-4 h-4" />
                      Files
                    </TabsTrigger>
                    <TabsTrigger value="repo" className="flex items-center gap-2">
                      <GitBranch className="w-4 h-4" />
                      Repository
                    </TabsTrigger>
                    <TabsTrigger value="local" className="flex items-center gap-2">
                      <FolderOpen className="w-4 h-4" />
                      Local Dir
                    </TabsTrigger>
                  </TabsList>

                  <TabsContent value="file">
                    <div className="border-2 border-dashed border-gray-300 rounded-lg p-8 text-center">
                      <input
                        type="file"
                        multiple
                        onChange={(e) => setFiles(e.target.files)}
                        className="hidden"
                        id="file-upload"
                      />
                      <label htmlFor="file-upload" className="cursor-pointer block">
                        <UploadCloud className="w-12 h-12 mx-auto mb-4 text-gray-400" />
                        <span className="text-sm text-gray-600">
                          Drop files here or click to upload
                        </span>
                        {files && (
                          <div className="mt-4 text-sm text-gray-600">
                            {files.length} file(s) selected
                          </div>
                        )}
                      </label>
                    </div>
                  </TabsContent>

                  <TabsContent value="repo">
                    <div className="space-y-4">
                      <div>
                        <label className="block text-sm font-medium mb-2">
                          Repository URL
                        </label>
                        <input
                          type="text"
                          value={repoUrl}
                          onChange={(e) => setRepoUrl(e.target.value)}
                          placeholder="https://github.com/user/repo"
                          className="w-full p-3 border rounded-lg"
                        />
                      </div>
                      <div className="grid grid-cols-2 gap-4">
                        <div>
                          <label className="block text-sm font-medium mb-2">
                            Branch (optional)
                          </label>
                          <input
                            type="text"
                            value={branch}
                            onChange={(e) => setBranch(e.target.value)}
                            placeholder="main"
                            className="w-full p-3 border rounded-lg"
                          />
                        </div>
                        <div>
                          <label className="block text-sm font-medium mb-2">
                            Access Token
                          </label>
                          <input
                            type="password"
                            value={token}
                            onChange={(e) => setToken(e.target.value)}
                            placeholder="For private repos"
                            className="w-full p-3 border rounded-lg"
                          />
                        </div>
                      </div>
                    </div>
                  </TabsContent>

                  <TabsContent value="local">
                    <div className="border-2 border-dashed border-gray-300 rounded-lg p-8 text-center">
                      <input
                        type="file"
                        {...{
                          webkitdirectory: "true",
                          directory: "true"
                        } as any}
                        onChange={(e) => {
                          const file = e.target.files?.[0];
                          // Use webkitRelativePath instead of path for web compatibility
                          setLocalDir(file?.webkitRelativePath?.split('/')[0] || '');
                        }}
                        className="hidden"
                        id="dir-upload"
                      />
                      <label htmlFor="dir-upload" className="cursor-pointer block">
                        <FolderOpen className="w-12 h-12 mx-auto mb-4 text-gray-400" />
                        <span className="text-sm text-gray-600">
                          Select a directory
                        </span>
                        {localDir && (
                          <div className="mt-4 text-sm text-gray-600">
                            Selected: {localDir}
                          </div>
                        )}
                      </label>
                    </div>
                  </TabsContent>
                </Tabs>

                <div className="space-y-4 border-t pt-4">
                  <div>
                    <label className="block text-sm font-medium mb-2">
                      Output Format
                    </label>
                    <select
                      value={outputFormat}
                      onChange={(e) => setOutputFormat(e.target.value)}
                      className="w-full p-3 border rounded-lg"
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

                <button
                  type="submit"
                  disabled={status === 'processing' || 
                    (selectedTab === 'file' && !files?.length) ||
                    (selectedTab === 'repo' && !repoUrl) ||
                    (selectedTab === 'local' && !localDir)}
                  className="w-full bg-blue-600 text-white p-3 rounded-lg hover:bg-blue-700 disabled:opacity-50"
                >
                  {status === 'processing' ? (
                    <span className="flex items-center justify-center gap-2">
                      <RefreshCw className="w-4 h-4 animate-spin" />
                      Processing... {progress.toFixed(0)}%
                    </span>
                  ) : 'Process'}
                </button>
              </form>
            </div>
          </Card>

          <Card>
            <div className="p-6">
              <h2 className="text-xl font-semibold mb-4">Status</h2>
              {error && (
                <div className="flex items-center gap-2 text-red-600 p-4 bg-red-50 rounded-lg mb-4">
                  <AlertCircle className="w-5 h-5" />
                  {error}
                </div>
              )}

              {status === 'processing' && (
                <div className="space-y-4">
                  <div className="h-2 bg-gray-200 rounded-full overflow-hidden">
                    <div 
                      className="h-full bg-blue-600 transition-all duration-500"
                      style={{ width: `${progress}%` }}
                    />
                  </div>
                  <p className="text-center text-sm text-gray-600">
                    Converting files... {progress.toFixed(0)}%
                  </p>
                </div>
              )}

              {status === 'completed' && (
                <div className="text-center text-green-600">
                  <p>Conversion complete! Downloading files...</p>
                </div>
              )}

              {result && (
                <div className="mt-4 grid grid-cols-3 gap-4 text-center">
                  <div>
                    <div className="text-2xl font-bold">{result.files_analyzed}</div>
                    <div className="text-sm text-gray-500">Files Analyzed</div>
                  </div>
                  <div>
                    <div className="text-2xl font-bold">
                      {result.total_tokens?.toLocaleString()}
                    </div>
                    <div className="text-sm text-gray-500">Total Tokens</div>
                  </div>
                  <div>
                    <div className="text-2xl font-bold">
                      {result.total_chars?.toLocaleString()}
                    </div>
                    <div className="text-sm text-gray-500">Characters</div>
                  </div>
                </div>
              )}
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
};

export default File2AI;
