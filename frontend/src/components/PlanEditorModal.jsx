import React, { useState, useEffect } from "react";
import { X, Save, Trash2 } from "lucide-react";

/**
 * Modal for creating/editing subscription plans
 */
export default function PlanEditorModal({ plan, onSave, onClose, onDelete }) {
    const [formData, setFormData] = useState({
        id: '',
        name: '',
        description: '',
        amount_inr: '',
        credits: '',
        bonus_credits: '0',
        is_active: true,
        sort_order: 0
    });
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState(null);

    useEffect(() => {
        if (plan) {
            setFormData({
                id: plan.id || '',
                name: plan.name || '',
                description: plan.description || '',
                amount_inr: plan.amount_inr?.toString() || '',
                credits: plan.credits?.toString() || '',
                bonus_credits: plan.bonus_credits?.toString() || '0',
                is_active: plan.is_active ?? true,
                sort_order: plan.sort_order || 0
            });
        }
    }, [plan]);

    const handleChange = (e) => {
        const { name, value, type, checked } = e.target;
        setFormData(prev => ({
            ...prev,
            [name]: type === 'checkbox' ? checked : value
        }));
        setError(null);
    };

    const handleSubmit = async (e) => {
        e.preventDefault();

        // Validation
        if (!formData.id.trim()) {
            setError('Plan ID is required (e.g., "starter")');
            return;
        }
        if (!formData.name.trim()) {
            setError('Plan name is required');
            return;
        }
        if (!formData.amount_inr || parseFloat(formData.amount_inr) <= 0) {
            setError('Valid price is required');
            return;
        }
        if (!formData.credits || parseFloat(formData.credits) <= 0) {
            setError('Valid credits amount is required');
            return;
        }

        const planData = {
            id: formData.id.toLowerCase().replace(/\s+/g, '-'),
            name: formData.name,
            description: formData.description,
            amount_paise: Math.round(parseFloat(formData.amount_inr) * 100),
            credits: parseFloat(formData.credits),
            bonus_credits: parseFloat(formData.bonus_credits) || 0,
            is_active: formData.is_active,
            sort_order: parseInt(formData.sort_order) || 0
        };

        try {
            setSaving(true);
            await onSave(planData, !!plan);
            onClose();
        } catch (err) {
            setError(err.message);
        } finally {
            setSaving(false);
        }
    };

    const handleDelete = async () => {
        if (!plan || !window.confirm(`Deactivate plan "${plan.name}"?`)) return;

        try {
            setSaving(true);
            await onDelete(plan.id);
            onClose();
        } catch (err) {
            setError(err.message);
        } finally {
            setSaving(false);
        }
    };

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
            <div className="card w-full max-w-lg max-h-[90vh] overflow-y-auto animate-fadeIn">
                <div className="flex justify-between items-center mb-6">
                    <h3 className="text-xl font-bold text-[var(--text-primary)]">
                        {plan ? 'Edit Plan' : 'Create Plan'}
                    </h3>
                    <button
                        onClick={onClose}
                        className="text-[var(--text-muted)] hover:text-[var(--text-primary)] transition-colors"
                    >
                        <X className="w-6 h-6" />
                    </button>
                </div>

                {error && (
                    <div className="mb-4 p-4 bg-red-500/10 border border-red-500 text-red-500 text-sm rounded">
                        {error}
                    </div>
                )}

                <form onSubmit={handleSubmit} className="space-y-5">
                    <div>
                        <label className="block text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)] mb-2">
                            Plan ID *
                        </label>
                        <input
                            type="text"
                            name="id"
                            value={formData.id}
                            onChange={handleChange}
                            disabled={!!plan}
                            placeholder="e.g., starter"
                            className="input w-full disabled:opacity-50 disabled:cursor-not-allowed"
                        />
                    </div>

                    <div>
                        <label className="block text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)] mb-2">
                            Name *
                        </label>
                        <input
                            type="text"
                            name="name"
                            value={formData.name}
                            onChange={handleChange}
                            placeholder="e.g., Starter Pack"
                            className="input w-full"
                        />
                    </div>

                    <div>
                        <label className="block text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)] mb-2">
                            Description
                        </label>
                        <input
                            type="text"
                            name="description"
                            value={formData.description}
                            onChange={handleChange}
                            placeholder="e.g., Great for beginners"
                            className="input w-full"
                        />
                    </div>

                    <div className="grid grid-cols-2 gap-4">
                        <div>
                            <label className="block text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)] mb-2">
                                Price (₹) *
                            </label>
                            <input
                                type="number"
                                name="amount_inr"
                                value={formData.amount_inr}
                                onChange={handleChange}
                                min="1"
                                step="1"
                                placeholder="499"
                                className="input w-full"
                            />
                        </div>
                        <div>
                            <label className="block text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)] mb-2">
                                Credits *
                            </label>
                            <input
                                type="number"
                                name="credits"
                                value={formData.credits}
                                onChange={handleChange}
                                min="1"
                                step="1"
                                placeholder="500"
                                className="input w-full"
                            />
                        </div>
                    </div>

                    <div className="grid grid-cols-2 gap-4">
                        <div>
                            <label className="block text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)] mb-2">
                                Bonus Credits
                            </label>
                            <input
                                type="number"
                                name="bonus_credits"
                                value={formData.bonus_credits}
                                onChange={handleChange}
                                min="0"
                                step="1"
                                placeholder="0"
                                className="input w-full"
                            />
                        </div>
                        <div>
                            <label className="block text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)] mb-2">
                                Sort Order
                            </label>
                            <input
                                type="number"
                                name="sort_order"
                                value={formData.sort_order}
                                onChange={handleChange}
                                min="0"
                                placeholder="0"
                                className="input w-full"
                            />
                        </div>
                    </div>

                    <div className="flex items-center gap-3 p-4 bg-[var(--bg-tertiary)] rounded">
                        <input
                            type="checkbox"
                            name="is_active"
                            id="is_active"
                            checked={formData.is_active}
                            onChange={handleChange}
                            className="w-4 h-4 accent-[var(--secondary)]"
                        />
                        <label htmlFor="is_active" className="text-sm font-medium text-[var(--text-primary)] cursor-pointer">
                            Active (visible to users)
                        </label>
                    </div>

                    <div className="flex gap-3 pt-4 border-t border-[var(--border-color)]">
                        {plan && (
                            <button
                                type="button"
                                onClick={handleDelete}
                                disabled={saving}
                                className="btn btn-danger flex items-center gap-2"
                            >
                                <Trash2 className="w-4 h-4" />
                                Delete
                            </button>
                        )}
                        <button
                            type="button"
                            onClick={onClose}
                            className="btn btn-secondary flex-1"
                        >
                            Cancel
                        </button>
                        <button
                            type="submit"
                            disabled={saving}
                            className="btn btn-primary flex-1 flex items-center justify-center gap-2"
                        >
                            {saving ? 'Saving...' : (
                                <>
                                    <Save className="w-4 h-4" />
                                    {plan ? 'Update' : 'Create'}
                                </>
                            )}
                        </button>
                    </div>
                </form>
            </div>
        </div>
    );
}
