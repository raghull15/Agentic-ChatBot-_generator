import React, { useState, useEffect } from "react";
import { useNavigate, useParams } from "react-router-dom";
import Navbar from "../components/Navbar";
import { getAgent, updateAgentData } from "../api";
import { Plus, Upload, FileCheck, X, Database, FileSpreadsheet, FileText, Server, ArrowLeft } from "lucide-react";

export default function UpdateAgent() {
    const { name } = useParams();
    const navigate = useNavigate();

    const [agent, setAgent] = useState(null);
    const [sourceType, setSourceType] = useState("pdf");
    const [files, setFiles] = useState([]);

    // Database connection fields
    const [connectionString, setConnectionString] = useState("");
    const [databaseName, setDatabaseName] = useState("");
    const [tables, setTables] = useState("");
    const [collections, setCollections] = useState("");
    const [sampleLimit, setSampleLimit] = useState("1000");

    const [loading, setLoading] = useState(false);
    const [loadingAgent, setLoadingAgent] = useState(true);
    const [error, setError] = useState(null);
    const [success, setSuccess] = useState(null);

    const sourceTypes = [
        { id: "pdf", label: "PDF", icon: FileText, accept: ".pdf" },
        { id: "csv", label: "CSV", icon: FileSpreadsheet, accept: ".csv" },
        { id: "word", label: "Word", icon: FileText, accept: ".docx,.doc" },
        { id: "sql", label: "SQL", icon: Database },
        { id: "nosql", label: "MongoDB", icon: Server },
    ];

    useEffect(() => {
        const loadAgent = async () => {
            try {
                const agentData = await getAgent(decodeURIComponent(name));
                setAgent(agentData);
            } catch (err) {
                setError(err.message);
            } finally {
                setLoadingAgent(false);
            }
        };
        loadAgent();
    }, [name]);

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

    const handleSubmit = async (e) => {
        e.preventDefault();
        setError(null);
        setSuccess(null);

        // Validate based on source type
        if (["pdf", "csv", "word"].includes(sourceType)) {
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

            const sourceConfig = {};

            if (["pdf", "csv", "word"].includes(sourceType)) {
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

            const result = await updateAgentData(decodeURIComponent(name), sourceType, sourceConfig);

            setSuccess(`Added ${result.new_chunks_added} new chunks. Total: ${result.total_chunks} chunks.`);
            setFiles([]);

            // Refresh agent data
            const updatedAgent = await getAgent(decodeURIComponent(name));
            setAgent(updatedAgent);

        } catch (err) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    };

    const isFileSource = ["pdf", "csv", "word"].includes(sourceType);
    const isDbSource = ["sql", "nosql"].includes(sourceType);

    if (loadingAgent) {
        return (
            <div className="min-h-screen bg-[var(--bg-primary)]">
                <Navbar />
                <div className="max-w-xl mx-auto px-4 py-12 text-center">
                    <p className="text-[var(--text-muted)]">Loading agent...</p>
                </div>
            </div>
        );
    }

    return (
        <div className="min-h-screen bg-[var(--bg-primary)]">
            <Navbar />

            <div className="max-w-xl mx-auto px-4 py-6 sm:px-6 sm:py-12">
                {/* Back Button */}
                <button
                    onClick={() => navigate("/home")}
                    className="flex items-center gap-2 text-[var(--text-muted)] bg-transparent border-none cursor-pointer text-sm mb-6 sm:mb-8 p-0"
                >
                    <ArrowLeft className="w-4 h-4" />
                    Back to Dashboard
                </button>

                {/* Header */}
                <div className="mb-6 sm:mb-8 animate-fadeIn">
                    <div className="flex items-center gap-3 sm:gap-4 mb-2">
                        <div className="w-10 h-10 sm:w-12 sm:h-12 bg-[var(--accent)] flex items-center justify-center">
                            <Plus className="w-5 h-5 sm:w-6 sm:h-6 text-[var(--accent-text)]" />
                        </div>
                        <div>
                            <h1 className="text-xl sm:text-2xl font-light tracking-tight text-[var(--text-primary)] m-0">
                                Update Agent
                            </h1>
                            <p className="text-xs sm:text-sm text-[var(--text-muted)] m-0">
                                {agent?.name}
                            </p>
                        </div>
                    </div>
                </div>

                {/* Agent Stats */}
                {agent && (
                    <div className="p-4 bg-[var(--bg-secondary)] border border-[var(--border-color)] mb-6">
                        <p className="text-sm text-[var(--text-secondary)] m-0">
                            <strong className="text-[var(--text-primary)]">Current Data:</strong>{' '}
                            {agent.num_documents || 0} chunks from {(agent.source_files || agent.pdf_files || []).length} source(s)
                        </p>
                    </div>
                )}

                {/* Form Card */}
                <div className="bg-[var(--bg-primary)] border border-[var(--border-color)] p-4 sm:p-8 animate-fadeIn">
                    {error && (
                        <div className="mb-6 p-4 bg-[var(--bg-secondary)] border border-red-500 text-red-500 text-sm">
                            {error}
                        </div>
                    )}

                    {success && (
                        <div className="mb-6 p-4 bg-[var(--bg-secondary)] border border-green-500 text-green-500 text-sm">
                            {success}
                        </div>
                    )}

                    <form onSubmit={handleSubmit}>
                        {/* Data Source Type */}
                        <div className="mb-6">
                            <label className="block text-xs font-medium uppercase tracking-wider text-[var(--text-muted)] mb-2">
                                Add Data From
                            </label>
                            <div className="grid grid-cols-3 sm:grid-cols-5 gap-2">
                                {sourceTypes.map((source) => {
                                    const Icon = source.icon;
                                    const isActive = sourceType === source.id;
                                    return (
                                        <button
                                            key={source.id}
                                            type="button"
                                            onClick={() => {
                                                setSourceType(source.id);
                                                setFiles([]);
                                                setConnectionString("");
                                                setDatabaseName("");
                                                setTables("");
                                                setCollections("");
                                            }}
                                            className={`p-3 flex flex-col items-center gap-1 cursor-pointer transition-all ${isActive
                                                    ? 'border-2 border-[var(--accent)] bg-[var(--bg-secondary)]'
                                                    : 'border border-[var(--border-color)] bg-transparent'
                                                }`}
                                            disabled={loading}
                                        >
                                            <Icon className="w-4 h-4 text-[var(--text-secondary)]" />
                                            <span className="text-[9px] sm:text-[10px] font-medium text-[var(--text-secondary)] uppercase tracking-wide">
                                                {source.label}
                                            </span>
                                        </button>
                                    );
                                })}
                            </div>
                        </div>

                        {/* File Upload */}
                        {isFileSource && (
                            <div className="mb-6">
                                <label className="block text-xs font-medium uppercase tracking-wider text-[var(--text-muted)] mb-2">
                                    {sourceType.toUpperCase()} Files
                                </label>
                                <div className="border-2 border-dashed border-[var(--border-color)] p-6 sm:p-8 text-center cursor-pointer bg-[var(--bg-primary)]">
                                    <input
                                        type="file"
                                        accept={getFileAccept()}
                                        multiple
                                        onChange={handleFileChange}
                                        disabled={loading}
                                        className="hidden"
                                        id="file-upload"
                                    />
                                    <label htmlFor="file-upload" className="cursor-pointer">
                                        <Upload className="w-8 h-8 text-[var(--text-muted)] mx-auto mb-3" />
                                        <p className="text-sm text-[var(--text-secondary)] m-0">
                                            Click to upload {sourceType.toUpperCase()} files
                                        </p>
                                    </label>
                                </div>

                                {files.length > 0 && (
                                    <div className="mt-4 p-4 bg-[var(--bg-secondary)] border border-[var(--border-color)]">
                                        <div className="flex justify-between items-center mb-3">
                                            <div className="flex items-center gap-2 text-[var(--text-primary)] text-sm font-medium">
                                                <FileCheck className="w-4 h-4" />
                                                {files.length} file(s) selected
                                            </div>
                                            <button
                                                type="button"
                                                onClick={clearAllFiles}
                                                className="text-xs text-red-500 bg-transparent border-none cursor-pointer uppercase tracking-wide"
                                                disabled={loading}
                                            >
                                                Clear all
                                            </button>
                                        </div>
                                        <ul className="list-none m-0 p-0">
                                            {files.map((file, i) => (
                                                <li key={i} className="flex items-center justify-between p-2 bg-[var(--bg-primary)] mb-1">
                                                    <span className="text-xs text-[var(--text-secondary)] flex-1 truncate">
                                                        {file.name}
                                                    </span>
                                                    <button
                                                        type="button"
                                                        onClick={() => removeFile(i)}
                                                        className="ml-2 p-1 bg-transparent border-none cursor-pointer text-[var(--text-muted)]"
                                                        disabled={loading}
                                                    >
                                                        <X className="w-3 h-3" />
                                                    </button>
                                                </li>
                                            ))}
                                        </ul>
                                    </div>
                                )}
                            </div>
                        )}

                        {/* Database Connection */}
                        {isDbSource && (
                            <div className="mb-6 p-4 sm:p-5 bg-[var(--bg-secondary)] border border-[var(--border-color)]">
                                <div className="mb-4">
                                    <label className="block text-xs font-medium uppercase tracking-wider text-[var(--text-muted)] mb-2">
                                        Connection String
                                    </label>
                                    <input
                                        className="w-full p-3 sm:p-4 text-xs sm:text-sm font-mono bg-[var(--bg-primary)] text-[var(--text-primary)] border border-[var(--border-color)] outline-none focus:border-[var(--text-muted)]"
                                        placeholder={sourceType === "sql" ? "postgresql://user:pass@localhost:5432/db" : "mongodb://localhost:27017"}
                                        value={connectionString}
                                        onChange={(e) => setConnectionString(e.target.value)}
                                        disabled={loading}
                                    />
                                </div>

                                {sourceType === "nosql" && (
                                    <div className="mb-4">
                                        <label className="block text-xs font-medium uppercase tracking-wider text-[var(--text-muted)] mb-2">
                                            Database Name
                                        </label>
                                        <input
                                            className="w-full p-3 sm:p-4 text-sm bg-[var(--bg-primary)] text-[var(--text-primary)] border border-[var(--border-color)] outline-none focus:border-[var(--text-muted)]"
                                            placeholder="my_database"
                                            value={databaseName}
                                            onChange={(e) => setDatabaseName(e.target.value)}
                                            disabled={loading}
                                        />
                                    </div>
                                )}

                                <div className="mb-4">
                                    <label className="block text-xs font-medium uppercase tracking-wider text-[var(--text-muted)] mb-2">
                                        {sourceType === "sql" ? "Tables" : "Collections"}
                                        <span className="font-normal normal-case ml-1">(comma-separated)</span>
                                    </label>
                                    <input
                                        className="w-full p-3 sm:p-4 text-sm bg-[var(--bg-primary)] text-[var(--text-primary)] border border-[var(--border-color)] outline-none focus:border-[var(--text-muted)]"
                                        placeholder={sourceType === "sql" ? "users, orders" : "customers, transactions"}
                                        value={sourceType === "sql" ? tables : collections}
                                        onChange={(e) => sourceType === "sql" ? setTables(e.target.value) : setCollections(e.target.value)}
                                        disabled={loading}
                                    />
                                </div>

                                <div>
                                    <label className="block text-xs font-medium uppercase tracking-wider text-[var(--text-muted)] mb-2">
                                        Sample Limit
                                    </label>
                                    <input
                                        type="number"
                                        className="w-full p-3 sm:p-4 text-sm bg-[var(--bg-primary)] text-[var(--text-primary)] border border-[var(--border-color)] outline-none focus:border-[var(--text-muted)]"
                                        value={sampleLimit}
                                        onChange={(e) => setSampleLimit(e.target.value)}
                                        disabled={loading}
                                        min="1"
                                        max="10000"
                                    />
                                </div>
                            </div>
                        )}

                        {/* Submit */}
                        <button
                            type="submit"
                            className="btn btn-primary w-full p-3 sm:p-4 flex items-center justify-center gap-2"
                            disabled={loading}
                        >
                            {loading ? "Adding Data..." : "Add Data to Agent"}
                            {!loading && <Plus className="w-4 h-4" />}
                        </button>
                    </form>
                </div>
            </div>
        </div>
    );
}
