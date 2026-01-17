import React, { useState, useEffect } from "react";
import { Plus, Edit2, ToggleLeft, ToggleRight } from "lucide-react";
import { adminGetPlans, adminCreatePlan, adminUpdatePlan, adminDeletePlan } from "../api";
import PlanEditorModal from "./PlanEditorModal";

/**
 * Plans management panel for admin
 */
export default function PlansPanel() {
    const [plans, setPlans] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [editingPlan, setEditingPlan] = useState(null); // null = closed, {} = new, {...} = edit
    const [showModal, setShowModal] = useState(false);

    const fetchPlans = async () => {
        try {
            setLoading(true);
            setError(null);
            const data = await adminGetPlans();
            setPlans(data);
        } catch (err) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchPlans();
    }, []);

    const handleSave = async (planData, isEdit) => {
        if (isEdit) {
            await adminUpdatePlan(planData.id, planData);
        } else {
            await adminCreatePlan(planData);
        }
        await fetchPlans();
    };

    const handleDelete = async (planId) => {
        await adminDeletePlan(planId);
        await fetchPlans();
    };

    const handleToggleActive = async (plan) => {
        await adminUpdatePlan(plan.id, { is_active: !plan.is_active });
        await fetchPlans();
    };

    const openNewPlan = () => {
        setEditingPlan(null);
        setShowModal(true);
    };

    const openEditPlan = (plan) => {
        setEditingPlan(plan);
        setShowModal(true);
    };

    if (loading) {
        return (
            <div className="p-8 text-center text-[var(--text-muted)]">
                Loading plans...
            </div>
        );
    }

    if (error) {
        return (
            <div className="p-4 border border-red-500 text-red-500 flex justify-between items-center">
                <span>{error}</span>
                <button onClick={fetchPlans} className="text-xs underline">Retry</button>
            </div>
        );
    }

    return (
        <div className="space-y-6">
            <div className="flex justify-between items-center mb-2">
                <h3 className="text-lg font-bold text-[var(--text-primary)]">
                    Subscription Plans
                </h3>
                <button
                    onClick={openNewPlan}
                    className="btn btn-primary flex items-center gap-2"
                >
                    <Plus className="w-4 h-4" />
                    New Plan
                </button>
            </div>

            <div className="grid gap-4">
                {plans.length === 0 ? (
                    <div className="card p-8 text-center text-[var(--text-muted)]">
                        No plans yet. Create your first subscription plan.
                    </div>
                ) : (
                    plans.map(plan => (
                        <div
                            key={plan.id}
                            className={`card p-6 hover:shadow-lg transition-all ${!plan.is_active ? 'opacity-60' : ''}`}
                        >
                            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                                <div className="flex-1">
                                    <div className="flex items-center gap-2 mb-1">
                                        <span className="text-sm font-medium text-[var(--text-primary)]">
                                            {plan.name}
                                        </span>
                                        <span className="text-[10px] px-2 py-0.5 border border-[var(--border-color)] text-[var(--text-muted)]">
                                            {plan.id}
                                        </span>
                                        {!plan.is_active && (
                                            <span className="text-[10px] px-2 py-0.5 border border-red-500 text-red-500">
                                                Inactive
                                            </span>
                                        )}
                                    </div>
                                    <p className="text-xs text-[var(--text-muted)]">
                                        {plan.description}
                                    </p>
                                </div>
                                <div className="flex items-center gap-4 sm:gap-6">
                                    <div className="text-right">
                                        <p className="text-lg font-light text-[var(--text-primary)]">₹{plan.amount_inr}</p>
                                        <p className="text-xs text-[var(--text-muted)]">
                                            {plan.credits.toLocaleString('en-US')}
                                            {plan.bonus_credits > 0 && (
                                                <span className="text-green-500"> +{plan.bonus_credits.toLocaleString('en-US')}</span>
                                            )} =
                                            <span className="font-bold"> {plan.total_credits.toLocaleString('en-US')}</span>
                                        </p>
                                    </div>
                                    <div className="flex items-center gap-2">
                                        <button
                                            onClick={() => handleToggleActive(plan)}
                                            className="p-2 text-[var(--text-muted)] hover:text-[var(--text-primary)]"
                                            title={plan.is_active ? 'Deactivate' : 'Activate'}
                                        >
                                            {plan.is_active ? (
                                                <ToggleRight className="w-5 h-5 text-green-500" />
                                            ) : (
                                                <ToggleLeft className="w-5 h-5" />
                                            )}
                                        </button>
                                        <button
                                            onClick={() => openEditPlan(plan)}
                                            className="p-2 text-[var(--text-muted)] hover:text-[var(--text-primary)]"
                                            title="Edit"
                                        >
                                            <Edit2 className="w-4 h-4" />
                                        </button>
                                    </div>
                                </div>
                            </div>
                        </div>
                    ))
                )}
            </div>

            {showModal && (
                <PlanEditorModal
                    plan={editingPlan}
                    onSave={handleSave}
                    onDelete={handleDelete}
                    onClose={() => setShowModal(false)}
                />
            )}
        </div>
    );
}
