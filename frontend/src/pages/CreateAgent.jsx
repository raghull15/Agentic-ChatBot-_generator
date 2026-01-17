import React, { useState, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import Navbar from "../components/Navbar";
import { useAgent } from "../context/AgentContext";
import { Bot, Upload, FileText, FileSpreadsheet, Database, Server, X, AlertCircle, Coins, ArrowRight, CheckCircle } from "lucide-react";

export default function CreateAgent() {
  const [name, setName] = useState("");
  const [domain, setDomain] = useState("");
  const [description, setDescription] = useState("");
  const [sourceType, setSourceType] = useState("pdf");
  const [files, setFiles] = useState([]);

  // Database connection fields
  const [connectionString, setConnectionString] = useState("");
  const [databaseName, setDatabaseName] = useState("");
  const [tables, setTables] = useState("");
  const [collections, setCollections] = useState("");
  const [sampleLimit, setSampleLimit] = useState("1000");

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [creditsRequired, setCreditsRequired] = useState(null);
  const { addAgent, addAgentFromSource } = useAgent();
  const navigate = useNavigate();

  const sourceTypes = [
    { id: "pdf", label: "PDF", icon: FileText, accept: ".pdf", color: "#EF4444" },
    { id: "txt", label: "TXT", icon: FileText, accept: ".txt", color: "#71717A" },
    { id: "csv", label: "CSV", icon: FileSpreadsheet, accept: ".csv", color: "#10B981" },
    { id: "word", label: "Word", icon: FileText, accept: ".docx,.doc", color: "#2563EB" },
    { id: "sql", label: "SQL", icon: Database, color: "#7C3AED" },
    { id: "nosql", label: "MongoDB", icon: Server, color: "#10B981" },
  ];

  const handleFileChange = (e) => {
    const newFiles = Array.from(e.target.files);
    setFiles(prev => [...prev, ...newFiles]);
    e.target.value = '';
  };

  const removeFile = (indexToRemove) => {
    setFiles(prev => prev.filter((_, index) => index !== indexToRemove));
  };

  const clearAllFiles = () => {
    setFiles([]);
  };

  const getFileAccept = () => {
    const source = sourceTypes.find(s => s.id === sourceType);
    return source?.accept || "";
  };

  // Define these before useMemo
  const isFileSource = ["pdf", "csv", "word", "txt"].includes(sourceType);
  const isDbSource = ["sql", "nosql"].includes(sourceType);

  // Estimate credits required
  const estimatedCredits = useMemo(() => {
    if (isFileSource && files.length > 0) {
      // Rough estimate: 10 credits per file
      return files.length * 10;
    } else if (isDbSource) {
      // Rough estimate: 50 credits for database
      return 50;
    }
    return 0;
  }, [files, sourceType, isFileSource, isDbSource]);

  const handleSubmit = async (e) => {
    e.preventDefault();

    if (!name.trim()) {
      setError("Agent name is required");
      return;
    }
    if (!domain.trim()) {
      setError("Domain is required");
      return;
    }

    // Validate based on source type
    if (["pdf", "csv", "word", "txt"].includes(sourceType)) {
      if (!files || files.length === 0) {
        setError(`Please upload at least one ${sourceType.toUpperCase()} file`);
        return;
      }
    } else if (sourceType === "sql") {
      if (!connectionString.trim()) {
        setError("SQL connection string is required");
        return;
      }
    } else if (sourceType === "nosql") {
      if (!connectionString.trim() || !databaseName.trim()) {
        setError("MongoDB connection string and database name are required");
        return;
      }
    }

    try {
      setLoading(true);
      setError(null);
      setCreditsRequired(null);

      if (sourceType === "pdf") {
        await addAgent(name, domain, description, files);
      } else {
        const sourceConfig = {};

        if (["csv", "word", "txt"].includes(sourceType)) {
          sourceConfig.files = files;
        } else if (sourceType === "sql") {
          sourceConfig.connection_string = connectionString;
          sourceConfig.tables = tables ? tables.split(",").map(t => t.trim()) : null;
          sourceConfig.sample_limit = parseInt(sampleLimit) || 1000;
        } else if (sourceType === "nosql") {
          sourceConfig.connection_string = connectionString;
          sourceConfig.database = databaseName;
          sourceConfig.collections = collections ? collections.split(",").map(c => c.trim()) : null;
          sourceConfig.sample_limit = parseInt(sampleLimit) || 1000;
        }

        await addAgentFromSource(name, domain, description, sourceType, sourceConfig);
      }

      navigate("/home");
    } catch (err) {
      // Check for insufficient credits error (402)
      if (err.message?.includes("Insufficient") || err.message?.includes("credits")) {
        const match = err.message.match(/(\d+)/);
        const requiredCredits = match ? parseInt(match[1]) : null;
        setCreditsRequired(requiredCredits);
        setError("Insufficient credits to create this bot");
      } else {
        setError(err.message);
      }
    } finally {
      setLoading(false);
    }
  };

  const domains = ["Technology", "Medical", "Legal", "Finance", "Education", "Marketing"];

  return (
    <div className="min-h-screen bg-[var(--bg-primary)]">
      <Navbar />

      <div className="max-w-7xl mx-auto px-4 py-6 sm:px-6 sm:py-12">
        {/* Header */}
        <div className="mb-8 animate-fadeIn">
          <div className="flex items-center gap-4 mb-2">
            <div className="w-14 h-14 bg-gradient-to-br from-[var(--primary)] to-[var(--primary-hover)] rounded-2xl flex items-center justify-center shadow-lg">
              <Bot className="w-7 h-7 text-white" />
            </div>
            <div>
              <h1 className="text-3xl font-bold text-[var(--text-primary)]">
                Create AI Agent
              </h1>
              <p className="text-[var(--text-muted)]">
                Train your AI assistant from multiple data sources
              </p>
            </div>
          </div>
        </div>

        {/* Two Column Layout */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
          {/* Left Column - Form */}
          <div className="space-y-6">
            <form onSubmit={handleSubmit} className="space-y-6">
              {/* Error Alert */}
              {error && (
                <div className="alert alert-error">
                  <AlertCircle className="w-5 h-5" />
                  <div className="flex-1">
                    {error}
                    {creditsRequired && (
                      <p className="text-sm mt-1">
                        Required: {creditsRequired} credits
                      </p>
                    )}
                  </div>
                  {creditsRequired && (
                    <button
                      type="button"
                      onClick={() => navigate("/billing")}
                      className="btn btn-success btn-sm"
                    >
                      Buy Credits
                    </button>
                  )}
                </div>
              )}

              {/* Agent Name */}
              <div>
                <label className="block text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)] mb-2">
                  Agent Name *
                </label>
                <input
                  type="text"
                  className="input"
                  placeholder="My Customer Support Bot"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  disabled={loading}
                />
              </div>

              {/* Domain */}
              <div>
                <label className="block text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)] mb-2">
                  Domain *
                </label>
                <select
                  className="input"
                  value={domain}
                  onChange={(e) => setDomain(e.target.value)}
                  disabled={loading}
                >
                  <option value="">Select domain</option>
                  {domains.map(d => (
                    <option key={d} value={d}>{d}</option>
                  ))}
                </select>
              </div>

              {/* Description */}
              <div>
                <label className="block text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)] mb-2">
                  Description (Optional)
                </label>
                <textarea
                  className="input"
                  placeholder="Describe what your agent does..."
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  disabled={loading}
                  rows={3}
                />
              </div>

              {/* Data Source Selection */}
              <div>
                <label className="block text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)] mb-3">
                  Data Source *
                </label>
                <div className="grid grid-cols-3 gap-3">
                  {sourceTypes.map((source) => {
                    const Icon = source.icon;
                    const isSelected = sourceType === source.id;
                    return (
                      <button
                        key={source.id}
                        type="button"
                        onClick={() => {
                          setSourceType(source.id);
                          setFiles([]);
                          setError(null);
                        }}
                        className={`p-4 rounded-xl border-2 transition-all ${isSelected
                          ? 'border-[var(--primary)] bg-[var(--primary)]/5 shadow-lg'
                          : 'border-[var(--border-color)] hover:border-[var(--text-muted)]'
                          }`}
                        style={isSelected ? { boxShadow: `0 0 20px ${source.color}40` } : {}}
                      >
                        <div
                          className="w-10 h-10 mx-auto mb-2 rounded-lg flex items-center justify-center"
                          style={{ backgroundColor: `${source.color}20` }}
                        >
                          <Icon className="w-5 h-5" style={{ color: source.color }} />
                        </div>
                        <p className="text-xs font-semibold text-[var(--text-primary)]">
                          {source.label}
                        </p>
                      </button>
                    );
                  })}
                </div>
              </div>

              {/* File Upload Section */}
              {isFileSource && (
                <div>
                  <label className="block text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)] mb-3">
                    Upload Files *
                  </label>

                  {/* Dropzone */}
                  <label className="block border-2 border-dashed border-[var(--border-color)] rounded-xl p-8 text-center cursor-pointer hover:border-[var(--primary)] hover:bg-[var(--bg-secondary)] transition-all">
                    <input
                      type="file"
                      multiple
                      accept={getFileAccept()}
                      onChange={handleFileChange}
                      disabled={loading}
                      className="hidden"
                    />
                    <Upload className="w-10 h-10 mx-auto mb-3 text-[var(--text-muted)]" />
                    <p className="text-sm font-semibold text-[var(--text-primary)] mb-1">
                      Click to upload or drag and drop
                    </p>
                    <p className="text-xs text-[var(--text-muted)]">
                      {sourceType.toUpperCase()} files only
                    </p>
                  </label>

                  {/* File List */}
                  {files.length > 0 && (
                    <div className="mt-4 space-y-2">
                      <div className="flex justify-between items-center">
                        <p className="text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)]">
                          {files.length} file{files.length !== 1 ? 's' : ''} selected
                        </p>
                        <button
                          type="button"
                          onClick={clearAllFiles}
                          className="text-xs text-[var(--danger)] hover:text-[var(--danger-hover)] font-semibold"
                        >
                          Clear All
                        </button>
                      </div>
                      <div className="space-y-2 max-h-48 overflow-y-auto">
                        {files.map((file, idx) => (
                          <div
                            key={idx}
                            className="flex items-center justify-between p-3 bg-[var(--bg-secondary)] border border-[var(--border-color)] rounded-lg"
                          >
                            <div className="flex items-center gap-3 min-w-0 flex-1">
                              <FileText className="w-4 h-4 text-[var(--text-muted)] flex-shrink-0" />
                              <span className="text-sm text-[var(--text-primary)] truncate">
                                {file.name}
                              </span>
                              <span className="text-xs text-[var(--text-muted)] flex-shrink-0">
                                {(file.size / 1024).toFixed(1)} KB
                              </span>
                            </div>
                            <button
                              type="button"
                              onClick={() => removeFile(idx)}
                              className="ml-2 p-1 text-[var(--text-muted)] hover:text-[var(--danger)] transition-colors"
                            >
                              <X className="w-4 h-4" />
                            </button>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )}

              {/* Database Connection Section */}
              {isDbSource && (
                <div className="card p-6 space-y-4">
                  <h3 className="text-sm font-bold uppercase tracking-wider text-[var(--text-primary)]">
                    {sourceType === "sql" ? "SQL Database" : "MongoDB"} Connection
                  </h3>

                  <div>
                    <label className="block text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)] mb-2">
                      Connection String *
                    </label>
                    <input
                      type="text"
                      className="input font-mono text-xs"
                      placeholder={
                        sourceType === "sql"
                          ? "postgresql://user:pass@host:5432/db"
                          : "mongodb://user:pass@host:27017"
                      }
                      value={connectionString}
                      onChange={(e) => setConnectionString(e.target.value)}
                      disabled={loading}
                    />
                  </div>

                  {sourceType === "nosql" && (
                    <div>
                      <label className="block text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)] mb-2">
                        Database Name *
                      </label>
                      <input
                        type="text"
                        className="input"
                        placeholder="myDatabase"
                        value={databaseName}
                        onChange={(e) => setDatabaseName(e.target.value)}
                        disabled={loading}
                      />
                    </div>
                  )}

                  <div>
                    <label className="block text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)] mb-2">
                      {sourceType === "sql" ? "Tables" : "Collections"} (Optional)
                    </label>
                    <input
                      type="text"
                      className="input"
                      placeholder="table1, table2, table3"
                      value={sourceType === "sql" ? tables : collections}
                      onChange={(e) =>
                        sourceType === "sql"
                          ? setTables(e.target.value)
                          : setCollections(e.target.value)
                      }
                      disabled={loading}
                    />
                    <p className="text-xs text-[var(--text-muted)] mt-1">
                      Leave empty to use all {sourceType === "sql" ? "tables" : "collections"}
                    </p>
                  </div>

                  <div>
                    <label className="block text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)] mb-2">
                      Sample Limit
                    </label>
                    <input
                      type="number"
                      className="input"
                      placeholder="1000"
                      value={sampleLimit}
                      onChange={(e) => setSampleLimit(e.target.value)}
                      disabled={loading}
                      min="1"
                      max="10000"
                    />
                    <p className="text-xs text-[var(--text-muted)] mt-1">
                      Max rows per table (1-10,000)
                    </p>
                  </div>
                </div>
              )}

              {/* Submit Button */}
              <button
                type="submit"
                className="btn btn-primary w-full"
                disabled={loading}
              >
                {loading ? (
                  <>
                    <div className="animate-spin w-5 h-5 border-2 border-white border-t-transparent rounded-full" />
                    Creating Agent...
                  </>
                ) : (
                  <>
                    <Bot className="w-5 h-5" />
                    Create Agent
                    <ArrowRight className="w-5 h-5" />
                  </>
                )}
              </button>
            </form>
          </div>

          {/* Right Column - Live Preview */}
          <div className="lg:sticky lg:top-24 h-fit space-y-6">
            {/* Preview Card */}
            <div className="card p-6">
              <h3 className="text-sm font-bold uppercase tracking-wider text-[var(--text-muted)] mb-4">
                Live Preview
              </h3>

              <div className="space-y-4">
                {/* Agent Name Preview */}
                <div>
                  <p className="text-xs text-[var(--text-muted)] mb-1">Agent Name</p>
                  <p className="text-lg font-bold text-[var(--text-primary)]">
                    {name || "My Agent"}
                  </p>
                </div>

                {/* Domain Preview */}
                {domain && (
                  <div>
                    <p className="text-xs text-[var(--text-muted)] mb-1">Domain</p>
                    <span className="badge badge-primary">{domain}</span>
                  </div>
                )}

                {/* Description Preview */}
                {description && (
                  <div>
                    <p className="text-xs text-[var(--text-muted)] mb-1">Description</p>
                    <p className="text-sm text-[var(--text-secondary)]">
                      {description}
                    </p>
                  </div>
                )}

                {/* Source Type Preview */}
                <div>
                  <p className="text-xs text-[var(--text-muted)] mb-1">Data Source</p>
                  <div className="flex items-center gap-2">
                    {(() => {
                      const source = sourceTypes.find(s => s.id === sourceType);
                      const Icon = source?.icon;
                      return (
                        <>
                          <div
                            className="w-8 h-8 rounded-lg flex items-center justify-center"
                            style={{ backgroundColor: `${source?.color}20` }}
                          >
                            <Icon className="w-4 h-4" style={{ color: source?.color }} />
                          </div>
                          <span className="text-sm font-semibold text-[var(--text-primary)]">
                            {source?.label}
                          </span>
                        </>
                      );
                    })()}
                  </div>
                </div>

                {/* Files Preview */}
                {isFileSource && files.length > 0 && (
                  <div>
                    <p className="text-xs text-[var(--text-muted)] mb-1">Files</p>
                    <div className="flex items-center gap-2">
                      <CheckCircle className="w-4 h-4 text-[var(--secondary)]" />
                      <span className="text-sm text-[var(--text-primary)]">
                        {files.length} file{files.length !== 1 ? 's' : ''} ready
                      </span>
                    </div>
                  </div>
                )}
              </div>
            </div>

            {/* Cost Estimator */}
            {estimatedCredits > 0 && (
              <div className="card p-6 bg-gradient-to-br from-[var(--warning)]/10 to-[var(--warning)]/5 border-2 border-[var(--warning)]">
                <div className="flex items-center gap-3 mb-3">
                  <Coins className="w-6 h-6 text-[var(--warning)]" />
                  <h3 className="text-sm font-bold uppercase tracking-wider text-[var(--text-primary)]">
                    Estimated Cost
                  </h3>
                </div>
                <p className="text-3xl font-bold text-[var(--warning)] mb-2">
                  ~{estimatedCredits} Credits
                </p>
                <p className="text-xs text-[var(--text-muted)]">
                  Actual cost may vary based on document size and complexity
                </p>
              </div>
            )}

            {/* Info Card */}
            <div className="card p-6 bg-[var(--bg-secondary)]">
              <h3 className="text-sm font-bold uppercase tracking-wider text-[var(--text-primary)] mb-3">
                💡 Tips
              </h3>
              <ul className="space-y-2 text-sm text-[var(--text-muted)]">
                <li className="flex items-start gap-2">
                  <span className="text-[var(--primary)]">•</span>
                  <span>Use descriptive names for better organization</span>
                </li>
                <li className="flex items-start gap-2">
                  <span className="text-[var(--primary)]">•</span>
                  <span>Larger files require more credits to process</span>
                </li>
                <li className="flex items-start gap-2">
                  <span className="text-[var(--primary)]">•</span>
                  <span>You can update your agent with more data later</span>
                </li>
              </ul>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
