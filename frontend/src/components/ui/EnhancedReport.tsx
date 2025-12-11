import { motion } from 'framer-motion';
import {
    FileText,
    Clock,
    AlertTriangle,
    Scale,
    ChevronDown,
    ChevronUp,
    Loader2,
    AlertCircle,
} from 'lucide-react';
import { useState } from 'react';
import type { EnhancedReport as EnhancedReportType } from '../../types/api';
import { Card } from './Card';

interface EnhancedReportProps {
    report: EnhancedReportType | null;
    loading?: boolean;
    error?: string;
}

interface SectionProps {
    title: string;
    icon: React.ReactNode;
    content: string;
    defaultOpen?: boolean;
}

const ReportSection = ({ title, icon, content, defaultOpen = false }: SectionProps) => {
    const [isOpen, setIsOpen] = useState(defaultOpen);

    if (!content || content.trim() === '') {
        return null;
    }

    return (
        <div className="border border-slate-700/50 rounded-xl overflow-hidden mb-4">
            <button
                onClick={() => setIsOpen(!isOpen)}
                className="w-full p-4 flex items-center justify-between bg-slate-800/30 hover:bg-slate-800/50 transition-colors"
            >
                <div className="flex items-center gap-3">
                    <div className="w-8 h-8 rounded-lg bg-blue-500/10 flex items-center justify-center">
                        {icon}
                    </div>
                    <span className="font-medium text-white">{title}</span>
                </div>
                {isOpen ? (
                    <ChevronUp className="w-5 h-5 text-slate-400" />
                ) : (
                    <ChevronDown className="w-5 h-5 text-slate-400" />
                )}
            </button>

            {isOpen && (
                <motion.div
                    initial={{ opacity: 0, height: 0 }}
                    animate={{ opacity: 1, height: 'auto' }}
                    exit={{ opacity: 0, height: 0 }}
                    className="p-4 bg-slate-900/50"
                >
                    <div className="prose prose-invert prose-sm max-w-none">
                        {content.split('\n').map((paragraph, idx) => {
                            if (paragraph.trim() === '') return null;

                            // Handle headers
                            if (paragraph.startsWith('###')) {
                                return (
                                    <h4 key={idx} className="text-lg font-semibold text-white mt-4 mb-2">
                                        {paragraph.replace(/^###\s*/, '')}
                                    </h4>
                                );
                            }
                            if (paragraph.startsWith('##')) {
                                return (
                                    <h3 key={idx} className="text-xl font-semibold text-white mt-4 mb-2">
                                        {paragraph.replace(/^##\s*/, '')}
                                    </h3>
                                );
                            }

                            // Handle bullet points
                            if (paragraph.trim().startsWith('-') || paragraph.trim().startsWith('•')) {
                                return (
                                    <p key={idx} className="text-slate-300 ml-4 my-1">
                                        {paragraph}
                                    </p>
                                );
                            }

                            return (
                                <p key={idx} className="text-slate-300 leading-relaxed my-2">
                                    {paragraph}
                                </p>
                            );
                        })}
                    </div>
                </motion.div>
            )}
        </div>
    );
};

export const EnhancedReport = ({ report, loading, error }: EnhancedReportProps) => {
    if (loading) {
        return (
            <Card>
                <div className="flex flex-col items-center justify-center py-16">
                    <Loader2 className="w-12 h-12 text-blue-400 animate-spin mb-4" />
                    <p className="text-slate-400">Loading enhanced report...</p>
                </div>
            </Card>
        );
    }

    if (error) {
        return (
            <Card>
                <div className="flex flex-col items-center justify-center py-16">
                    <AlertCircle className="w-12 h-12 text-red-400 mb-4" />
                    <h4 className="text-lg font-medium text-white mb-2">Failed to Load Report</h4>
                    <p className="text-slate-400 text-center max-w-md">{error}</p>
                </div>
            </Card>
        );
    }

    if (!report) {
        return (
            <Card>
                <div className="flex flex-col items-center justify-center py-16">
                    <FileText className="w-12 h-12 text-slate-500 mb-4" />
                    <h4 className="text-lg font-medium text-white mb-2">No Enhanced Report Available</h4>
                    <p className="text-slate-400 text-center max-w-md">
                        The enhanced documentation report is not available for this analysis.
                        This may be because Ollama was not running during analysis.
                    </p>
                </div>
            </Card>
        );
    }

    if (!report.success) {
        return (
            <Card>
                <div className="flex flex-col items-center justify-center py-16">
                    <AlertTriangle className="w-12 h-12 text-yellow-400 mb-4" />
                    <h4 className="text-lg font-medium text-white mb-2">Report Generation Failed</h4>
                    <p className="text-slate-400 text-center max-w-md">
                        {report.error || 'An error occurred while generating the enhanced report.'}
                    </p>
                </div>
            </Card>
        );
    }

    const sections = report.sections;
    const metadata = report.metadata;

    return (
        <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="space-y-6"
        >
            {/* Report Header */}
            <Card>
                <div className="flex flex-wrap items-center justify-between gap-4 mb-6">
                    <div className="flex items-center gap-4">
                        <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-purple-500/20 to-blue-500/20 flex items-center justify-center">
                            <FileText className="w-7 h-7 text-purple-400" />
                        </div>
                        <div>
                            <h3 className="text-xl font-semibold text-white">
                                Enhanced Incident Documentation
                            </h3>
                            <p className="text-sm text-slate-400">
                                Police-ready detailed incident report
                            </p>
                        </div>
                    </div>

                    {metadata && (
                        <div className="flex items-center gap-6 text-sm text-slate-400">
                            <div className="flex items-center gap-2">
                                <Clock className="w-4 h-4" />
                                <span>Generated in {(metadata.generation_time_ms / 1000).toFixed(1)}s</span>
                            </div>
                            <div className="flex items-center gap-2">
                                <AlertTriangle className="w-4 h-4" />
                                <span>{metadata.observation_count} observations</span>
                            </div>
                        </div>
                    )}
                </div>

                {/* Sections */}
                {sections ? (
                    <div className="space-y-2">
                        <ReportSection
                            title="Executive Summary"
                            icon={<FileText className="w-4 h-4 text-blue-400" />}
                            content={sections.executive_summary}
                            defaultOpen={true}
                        />
                        <ReportSection
                            title="Detailed Narrative"
                            icon={<FileText className="w-4 h-4 text-green-400" />}
                            content={sections.narrative_summary}
                        />
                        <ReportSection
                            title="Chronological Breakdown"
                            icon={<Clock className="w-4 h-4 text-yellow-400" />}
                            content={sections.incident_breakdown}
                        />
                        <ReportSection
                            title="Evidence Mapping"
                            icon={<AlertTriangle className="w-4 h-4 text-orange-400" />}
                            content={sections.evidence_mapping}
                        />
                        <ReportSection
                            title="Classification & Severity"
                            icon={<Scale className="w-4 h-4 text-red-400" />}
                            content={sections.classification}
                        />
                        <ReportSection
                            title="Legal & Procedural Notes"
                            icon={<Scale className="w-4 h-4 text-purple-400" />}
                            content={sections.legal_notes}
                        />
                    </div>
                ) : (
                    /* Fallback: Display raw content if sections not parsed */
                    <div className="prose prose-invert prose-sm max-w-none">
                        <div className="p-4 bg-slate-800/30 rounded-xl max-h-[600px] overflow-y-auto">
                            {report.content.split('\n').map((line, idx) => {
                                if (line.trim() === '') return <br key={idx} />;

                                if (line.startsWith('# ')) {
                                    return <h2 key={idx} className="text-2xl font-bold text-white mt-6 mb-3">{line.replace('# ', '')}</h2>;
                                }
                                if (line.startsWith('## ')) {
                                    return <h3 key={idx} className="text-xl font-semibold text-white mt-5 mb-2">{line.replace('## ', '')}</h3>;
                                }
                                if (line.startsWith('### ')) {
                                    return <h4 key={idx} className="text-lg font-medium text-white mt-4 mb-2">{line.replace('### ', '')}</h4>;
                                }
                                if (line.startsWith('**') && line.endsWith('**')) {
                                    return <p key={idx} className="font-semibold text-white my-2">{line.replace(/\*\*/g, '')}</p>;
                                }

                                return <p key={idx} className="text-slate-300 leading-relaxed my-1">{line}</p>;
                            })}
                        </div>
                    </div>
                )}
            </Card>
        </motion.div>
    );
};
