import React, { useState, useEffect } from "react";
import { Save, RefreshCw } from "lucide-react";
import { adminGetSettings, adminUpdateSetting } from "../api";

/**
 * Settings panel for admin-configurable billing settings
 */
export default function SettingsPanel() {
    const [settings, setSettings] = useState(null);
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState({});
    const [error, setError] = useState(null);
    const [editValues, setEditValues] = useState({});

    const fetchSettings = async () => {
        try {
            setLoading(true);
            setError(null);
            const data = await adminGetSettings();
            setSettings(data);
            // Initialize edit values
            const values = {};
            for (const key of Object.keys(data)) {
                values[key] = data[key].value;
            }
            setEditValues(values);
        } catch (err) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchSettings();
    }, []);

    const handleChange = (key, value) => {
        setEditValues(prev => ({ ...prev, [key]: value }));
    };

    const handleSave = async (key) => {
        try {
            setSaving(prev => ({ ...prev, [key]: true }));
            await adminUpdateSetting(key, editValues[key]);
            // Refresh settings
            await fetchSettings();
        } catch (err) {
            setError(`Failed to update ${key}: ${err.message}`);
        } finally {
            setSaving(prev => ({ ...prev, [key]: false }));
        }
    };

    if (loading) {
        return (
            <div className="p-8 text-center text-[var(--text-muted)]">
                Loading settings...
            </div>
        );
    }

    if (error) {
        return (
            <div className="p-4 border border-red-500 text-red-500 flex justify-between items-center">
                <span>{error}</span>
                <button onClick={fetchSettings} className="text-xs underline">Retry</button>
            </div>
        );
    }

    const settingKeys = [
        { key: 'tokens_per_credit', type: 'number', label: 'Tokens per Credit' },
        { key: 'daily_credit_cap', type: 'number', label: 'Daily Credit Cap' },
        { key: 'free_credits', type: 'number', label: 'Free Credits (New Users)' },
        { key: 'max_tokens_per_query', type: 'number', label: 'Max Tokens per Query' },
        { key: 'low_credit_threshold', type: 'number', label: 'Low Credit Threshold' },
        { key: 'bot_creation_cost', type: 'number', label: 'Bot Creation Cost (Credits)' },
        { key: 'demo_bot_time_limit_hours', type: 'number', label: 'Demo Bot Time Limit (Hours)' },
        { key: 'demo_bot_credit_limit', type: 'number', label: 'Demo Bot Credit Limit' },
    ];

    return (
        <div className="space-y-6">
            <div className="flex justify-between items-center mb-2">
                <h3 className="text-lg font-bold text-[var(--text-primary)]">
                    System Settings
                </h3>
                <button
                    onClick={fetchSettings}
                    className="btn btn-secondary btn-sm flex items-center gap-2"
                >
                    <RefreshCw className="w-4 h-4" />
                    Refresh
                </button>
            </div>

            <div className="grid gap-4">
                {settingKeys.map(({ key, type, label }) => (
                    <div key={key} className="card p-6 hover:shadow-lg transition-all">
                        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                            <div className="flex-1">
                                <p className="text-sm font-semibold text-[var(--text-primary)] mb-1">{label}</p>
                                <p className="text-xs text-[var(--text-muted)]">
                                    {settings?.[key]?.description || ''}
                                </p>
                                {settings?.[key]?.updated_at && (
                                    <p className="text-[10px] text-[var(--text-muted)] mt-2">
                                        Last updated: {new Date(settings[key].updated_at).toLocaleString()}
                                        {settings[key].updated_by && ` by ${settings[key].updated_by}`}
                                    </p>
                                )}
                            </div>
                            <div className="flex items-center gap-3">
                                <input
                                    type={type}
                                    value={editValues[key] ?? ''}
                                    onChange={(e) => handleChange(key, type === 'number' ? parseInt(e.target.value) || 0 : e.target.value)}
                                    className="input w-28 text-center"
                                />
                                <button
                                    onClick={() => handleSave(key)}
                                    disabled={saving[key] || editValues[key] === settings?.[key]?.value}
                                    className="btn btn-primary btn-sm"
                                >
                                    {saving[key] ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
                                </button>
                            </div>
                        </div>
                    </div>
                ))}
            </div>

            <div className="card p-6 bg-[var(--bg-tertiary)]">
                <p className="text-xs text-[var(--text-muted)]">
                    <strong className="text-[var(--text-primary)]">Note:</strong> Changes take effect immediately. The "Tokens per Credit" setting affects how usage is calculated for all queries.
                </p>
            </div>
        </div>
    );
}
