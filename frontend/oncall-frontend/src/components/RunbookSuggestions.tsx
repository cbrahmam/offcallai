// RunbookSuggestions.tsx - Shows runbook suggestions for an incident or alert
import React, { useState, useEffect } from 'react';
import {
  AlertTriangle,
  BookOpen,
  CheckCircle,
  ChevronDown,
  ChevronUp,
  Info,
  Play,
  Sparkles
} from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';
import { useNotifications } from '../contexts/NotificationContext';
// Magic UI imports removed - using plain HTML/Tailwind equivalents

import { API_URL as API_BASE_URL } from '../config/api';

interface Runbook {
  id: string;
  title: string;
  description: string | null;
  content: string;
  tags: string[];
  service_names: string[];
  is_active: boolean;
  usage_count: number;
}

interface RunbookSuggestion {
  runbook: Runbook;
  match_score: number;
  match_reason: string;
  matched_patterns: string[];
}

interface ExecutionResponse {
  id: string;
  status: string;
  is_dry_run: boolean;
}

interface RunbookSuggestionsProps {
  incidentId?: string;
  alertId?: string;
  onExecutionStarted?: (executionId: string) => void;
}

const RunbookSuggestions: React.FC<RunbookSuggestionsProps> = ({
  incidentId,
  alertId,
  onExecutionStarted
}) => {
  const { token } = useAuth();
  const { showToast } = useNotifications();

  const [suggestions, setSuggestions] = useState<RunbookSuggestion[]>([]);
  const [loading, setLoading] = useState(true);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [executing, setExecuting] = useState<string | null>(null);
  const [showVariablesModal, setShowVariablesModal] = useState<RunbookSuggestion | null>(null);
  const [executionContext, setExecutionContext] = useState<Record<string, string>>({});
  const [dryRun, setDryRun] = useState(false);

  // Load suggestions
  useEffect(() => {
    const loadSuggestions = async () => {
      if (!token || (!incidentId && !alertId)) {
        setLoading(false);
        return;
      }

      try {
        setLoading(true);
        const endpoint = incidentId
          ? `${API_BASE_URL}/runbooks/suggestions/incident/${incidentId}`
          : `${API_BASE_URL}/runbooks/suggestions/alert/${alertId}`;

        const response = await fetch(endpoint, {
          headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json'
          }
        });

        if (!response.ok) throw new Error('Failed to fetch suggestions');

        const data = await response.json();
        setSuggestions(data.suggestions || []);
      } catch (error) {
        console.error('Error loading suggestions:', error);
      } finally {
        setLoading(false);
      }
    };

    loadSuggestions();
  }, [token, incidentId, alertId]);

  // Execute runbook
  const executeRunbook = async (suggestion: RunbookSuggestion) => {
    if (!token) return;

    try {
      setExecuting(suggestion.runbook.id);

      const response = await fetch(`${API_BASE_URL}/runbooks/${suggestion.runbook.id}/execute`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          incident_id: incidentId || null,
          execution_context: executionContext,
          dry_run: dryRun
        })
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to execute runbook');
      }

      const execution: ExecutionResponse = await response.json();

      showToast({
        message: dryRun
          ? 'Dry run completed - no changes made'
          : 'Runbook execution started',
        type: 'success'
      });

      if (onExecutionStarted && !dryRun) {
        onExecutionStarted(execution.id);
      }

      setShowVariablesModal(null);
      setExecutionContext({});
      setDryRun(false);
    } catch (error: any) {
      console.error('Error executing runbook:', error);
      showToast({ message: error.message || 'Failed to execute runbook', type: 'error' });
    } finally {
      setExecuting(null);
    }
  };

  // Get match score badge classes
  const getScoreBadgeClasses = (score: number): string => {
    if (score >= 0.8) return 'border-emerald-500/30 bg-emerald-500/10 text-emerald-400';
    if (score >= 0.5) return 'border-yellow-500/30 bg-yellow-500/10 text-yellow-400';
    return 'border-border bg-secondary text-foreground';
  };

  // Extract variables from content
  const extractVariables = (content: string): string[] => {
    const matches = content.match(/\{\{(\w+)\}\}/g);
    if (!matches) return [];
    return Array.from(new Set(matches.map(m => m.replace(/[{}]/g, ''))));
  };

  if (loading) {
    return (
      <div className="border border-border rounded-lg bg-transparent">
        <div className="p-4">
          <div className="flex items-center gap-2 mb-4">
            <div className="w-6 h-6 bg-purple-500/10 rounded flex items-center justify-center">
              <Sparkles className="h-4 w-4 text-purple-400" />
            </div>
            <h3 className="font-semibold text-foreground">Suggested Runbooks</h3>
          </div>
          <div className="flex justify-center py-4">
            <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-indigo-600"></div>
          </div>
        </div>
      </div>
    );
  }

  if (suggestions.length === 0) {
    return (
      <div className="border border-border rounded-lg bg-transparent">
        <div className="p-4">
          <div className="flex items-center gap-2 mb-4">
            <div className="w-6 h-6 bg-purple-500/10 rounded flex items-center justify-center">
              <Sparkles className="h-4 w-4 text-purple-400" />
            </div>
            <h3 className="font-semibold text-foreground">Suggested Runbooks</h3>
          </div>
          <div className="text-center py-4 text-muted-foreground">
            <BookOpen className="h-8 w-8 mx-auto mb-2 opacity-50" />
            <p className="text-sm">No matching runbooks found for this incident.</p>
            <p className="text-xs mt-1">Create runbooks with alert patterns to see suggestions here.</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="border border-border rounded-lg bg-transparent overflow-hidden">
      <div className="p-4 border-b border-border">
        <div className="flex items-center gap-2">
          <div className="w-6 h-6 bg-purple-500/10 rounded flex items-center justify-center">
            <Sparkles className="h-4 w-4 text-purple-400" />
          </div>
          <h3 className="font-semibold text-foreground">Suggested Runbooks</h3>
          <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border border-blue-500/30 bg-blue-500/10 text-blue-400">
            {suggestions.length} matches
          </span>
        </div>
      </div>

      <div className="divide-y divide-border">
        {suggestions.map((suggestion) => (
          <div key={suggestion.runbook.id} className="p-4">
            <div className="flex items-start justify-between">
              <div className="flex-1">
                <div className="flex items-center gap-2">
                  <BookOpen className="h-5 w-5 text-muted-foreground" />
                  <h4 className="font-medium text-foreground">
                    {suggestion.runbook.title}
                  </h4>
                  <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border ${getScoreBadgeClasses(suggestion.match_score)}`}>
                    {Math.round(suggestion.match_score * 100)}% match
                  </span>
                </div>
                {suggestion.runbook.description && (
                  <p className="text-sm text-muted-foreground mt-1 ml-7">
                    {suggestion.runbook.description}
                  </p>
                )}
                <p className="text-xs text-muted-foreground mt-1 ml-7">
                  {suggestion.match_reason}
                </p>
              </div>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => setExpandedId(expandedId === suggestion.runbook.id ? null : suggestion.runbook.id)}
                  className="border border-border text-foreground hover:bg-accent rounded-md px-2 py-1.5 text-sm font-medium"
                >
                  {expandedId === suggestion.runbook.id ? (
                    <ChevronUp className="h-5 w-5" />
                  ) : (
                    <ChevronDown className="h-5 w-5" />
                  )}
                </button>
                <button
                  onClick={() => {
                    const vars = extractVariables(suggestion.runbook.content);
                    if (vars.length > 0) {
                      setShowVariablesModal(suggestion);
                    } else {
                      executeRunbook(suggestion);
                    }
                  }}
                  disabled={executing === suggestion.runbook.id}
                  className="bg-primary text-primary-foreground hover:bg-white/90 rounded-md px-4 py-1.5 text-sm font-medium inline-flex items-center gap-1 disabled:opacity-50"
                >
                  {executing === suggestion.runbook.id ? (
                    <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-zinc-400"></div>
                  ) : (
                    <Play className="h-4 w-4 mr-1" />
                  )}
                  Execute
                </button>
              </div>
            </div>

            {/* Expanded content */}
            {expandedId === suggestion.runbook.id && (
              <div className="mt-4 ml-7 space-y-3">
                {suggestion.runbook.tags.length > 0 && (
                  <div className="flex flex-wrap gap-1">
                    {suggestion.runbook.tags.map((tag, i) => (
                      <span key={i} className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border border-border bg-secondary text-foreground">
                        {tag}
                      </span>
                    ))}
                  </div>
                )}
                <div>
                  <h5 className="text-xs font-medium text-muted-foreground mb-1">
                    Content Preview
                  </h5>
                  <pre className="text-xs bg-accent text-foreground p-3 rounded-lg overflow-x-auto max-h-40">
                    {suggestion.runbook.content.slice(0, 400)}
                    {suggestion.runbook.content.length > 400 && '...'}
                  </pre>
                </div>
                <div className="flex items-center gap-4 text-xs text-muted-foreground">
                  <span>Used {suggestion.runbook.usage_count} times</span>
                  {suggestion.runbook.service_names.length > 0 && (
                    <span>Services: {suggestion.runbook.service_names.join(', ')}</span>
                  )}
                </div>
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Variables Modal */}
      {showVariablesModal && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 p-4">
          <div className="border border-border rounded-lg bg-background w-full max-w-md">
            <div className="p-4 border-b border-border">
              <h3 className="text-lg font-semibold text-foreground">
                Execute: {showVariablesModal.runbook.title}
              </h3>
            </div>

            <div className="p-4 space-y-4">
              <div className="flex items-start gap-2 p-3 bg-blue-500/10 rounded-lg border border-blue-500/20">
                <Info className="h-5 w-5 text-blue-400 flex-shrink-0 mt-0.5" />
                <p className="text-sm text-blue-400">
                  This runbook requires some variables. Please provide values below.
                </p>
              </div>

              {extractVariables(showVariablesModal.runbook.content).map((variable) => (
                <div key={variable}>
                  <label className="block text-sm font-medium text-foreground mb-1">
                    {variable}
                  </label>
                  <input
                    type="text"
                    value={executionContext[variable] || ''}
                    onChange={(e) => setExecutionContext({
                      ...executionContext,
                      [variable]: e.target.value
                    })}
                    className="w-full px-3 py-2 border border-border rounded-lg bg-accent text-foreground"
                    placeholder={`Enter ${variable}`}
                  />
                </div>
              ))}

              <div className="flex items-center gap-3 pt-2">
                <input
                  type="checkbox"
                  id="dry_run"
                  checked={dryRun}
                  onChange={(e) => setDryRun(e.target.checked)}
                  className="h-4 w-4 text-indigo-600 rounded"
                />
                <label htmlFor="dry_run" className="text-sm text-foreground">
                  Dry run (preview steps without executing)
                </label>
              </div>

              {dryRun && (
                <div className="flex items-start gap-2 p-3 bg-yellow-500/10 rounded-lg border border-yellow-500/20">
                  <AlertTriangle className="h-5 w-5 text-yellow-400 flex-shrink-0 mt-0.5" />
                  <p className="text-sm text-yellow-400">
                    Dry run mode: Steps will be previewed but not executed.
                  </p>
                </div>
              )}
            </div>

            <div className="p-4 border-t border-border flex justify-end gap-3">
              <button
                onClick={() => {
                  setShowVariablesModal(null);
                  setExecutionContext({});
                  setDryRun(false);
                }}
                className="border border-border text-foreground hover:bg-accent rounded-md px-6 py-2.5 text-sm font-medium"
              >
                Cancel
              </button>
              <button
                onClick={() => executeRunbook(showVariablesModal)}
                disabled={executing !== null}
                className="bg-primary text-primary-foreground hover:bg-white/90 rounded-md px-6 py-2.5 text-sm font-medium inline-flex items-center gap-1 disabled:opacity-50"
              >
                {executing && <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-zinc-400 mr-2"></div>}
                <Play className="h-4 w-4 mr-1" />
                {dryRun ? 'Preview Steps' : 'Execute'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default RunbookSuggestions;
