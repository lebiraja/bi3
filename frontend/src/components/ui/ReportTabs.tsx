import { motion } from 'framer-motion';
import { FileText, ClipboardList } from 'lucide-react';

export type ReportTabType = 'classical' | 'enhanced';

interface ReportTabsProps {
    activeTab: ReportTabType;
    onTabChange: (tab: ReportTabType) => void;
    enhancedAvailable?: boolean;
}

export const ReportTabs = ({ activeTab, onTabChange, enhancedAvailable = true }: ReportTabsProps) => {
    const tabs = [
        {
            id: 'classical' as ReportTabType,
            label: 'Classical Report',
            icon: ClipboardList,
            description: 'Standard observations view',
        },
        {
            id: 'enhanced' as ReportTabType,
            label: 'Enhanced Documentation',
            icon: FileText,
            description: 'Police-ready detailed report',
            disabled: !enhancedAvailable,
        },
    ];

    return (
        <div className="flex flex-wrap gap-3 mb-6">
            {tabs.map((tab) => {
                const Icon = tab.icon;
                const isActive = activeTab === tab.id;
                const isDisabled = tab.disabled;

                return (
                    <button
                        key={tab.id}
                        onClick={() => !isDisabled && onTabChange(tab.id)}
                        disabled={isDisabled}
                        className={`
              relative flex items-center gap-3 px-5 py-3 rounded-xl transition-all duration-200
              ${isActive
                                ? 'bg-gradient-to-r from-blue-600 to-purple-600 text-white shadow-lg shadow-blue-500/25'
                                : isDisabled
                                    ? 'bg-slate-800/30 text-slate-500 cursor-not-allowed'
                                    : 'bg-slate-800/50 text-slate-300 hover:bg-slate-700/50 hover:text-white'
                            }
            `}
                    >
                        <div className={`
              w-10 h-10 rounded-lg flex items-center justify-center
              ${isActive
                                ? 'bg-white/20'
                                : isDisabled
                                    ? 'bg-slate-700/30'
                                    : 'bg-slate-700/50'
                            }
            `}>
                            <Icon className={`w-5 h-5 ${isActive ? 'text-white' : isDisabled ? 'text-slate-600' : 'text-slate-400'}`} />
                        </div>
                        <div className="text-left">
                            <p className={`font-medium ${isDisabled ? 'text-slate-500' : ''}`}>
                                {tab.label}
                            </p>
                            <p className={`text-xs ${isActive ? 'text-white/70' : 'text-slate-500'}`}>
                                {tab.description}
                            </p>
                        </div>

                        {isActive && (
                            <motion.div
                                layoutId="activeTabIndicator"
                                className="absolute inset-0 rounded-xl bg-gradient-to-r from-blue-600 to-purple-600 -z-10"
                                transition={{ duration: 0.2 }}
                            />
                        )}
                    </button>
                );
            })}
        </div>
    );
};
