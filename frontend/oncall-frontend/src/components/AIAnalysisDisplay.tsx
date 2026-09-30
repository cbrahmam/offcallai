import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
  AlertTriangle,
  CheckCircle,
  Clock,
  Cpu,
  Info,
  MessagesSquare,
  RefreshCw,
  Rocket,
  ShieldCheck,
  Sparkles,
  Zap
} from 'lucide-react';
import { API_URL } from '../config/api';

// Cache analysis results in sessionStorage to survive re-mounts
const getStorageKey = (incidentId: string) => `ai_analysis_${incidentId}`;

const getCachedAnalysis = (incidentId: string): { claude?: any; gemini?: any } | null => {
  try {
    const cached = sessionStorage.getItem(getStorageKey(incidentId));
    if (cached) {
      return JSON.parse(cached);
    }
  } catch (e) {
    // Ignore errors
  }
  return null;
};

const cacheAnalysis = (incidentId: string, analyses: { claude?: any; gemini?: any }) => {
  try {
    sessionStorage.setItem(getStorageKey(incidentId), JSON.stringify(analyses));
  } catch (e) {
    // Ignore errors
  }
};

const clearCachedAnalysis = (incidentId: string) => {
  try {
    sessionStorage.removeItem(getStorageKey(incidentId));
  } catch (e) {
    // Ignore errors
  }
};

// Track in-flight requests to prevent duplicates
const inFlightRequests = new Set<string>();

interface AIAnalysis {
  provider: 'claude' | 'gemini';
  confidence: number;
  rootCause: string;
  solution: {
    description: string;
    steps: string[];
    commands: string[];
    estimatedTime: string;
    riskLevel: 'low' | 'medium' | 'high';
    reversible: boolean;
  };
  impact: {
    affectedSystems: string[];
    businessImpact: string;
    userImpact: string;
  };
  preventionSteps: string[];
}

interface AIAnalysisDisplayProps {
  incidentId: string;
  onDeploymentSelect?: (provider: 'claude' | 'gemini', solution: any) => void;
  isLoading?: boolean;
}

const AIAnalysisDisplay: React.FC<AIAnalysisDisplayProps> = ({
  incidentId,
  onDeploymentSelect,
  isLoading = false
}) => {
  const [analyses, setAnalyses] = useState<{
    claude?: AIAnalysis;
    gemini?: AIAnalysis;
  }>({});
  const [selectedProvider, setSelectedProvider] = useState<'claude' | 'gemini' | null>(null);
  const [analyzingState, setAnalyzingState] = useState({
    claude: 'pending',
    gemini: 'pending'
  });
  const [apiErrors, setApiErrors] = useState<string[]>([]);
  const [providerErrors, setProviderErrors] = useState<{ claude?: string; gemini?: string }>({});
  const isAnalyzingRef = useRef(false);
  const mountedRef = useRef(true);

  // Cleanup on unmount
  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  useEffect(() => {
    if (!incidentId) return;

    // Check for cached results first
    const cached = getCachedAnalysis(incidentId);
    if (cached && (cached.claude || cached.gemini)) {
      console.log('Loading cached AI analysis for incident:', incidentId);
      setAnalyses(cached);
      setAnalyzingState({
        claude: cached.claude ? 'complete' : 'error',
        gemini: cached.gemini ? 'complete' : 'error'
      });
      return;
    }

    // Don't auto-start analysis - wait for user to click button
    // Just set state to pending
    console.log('No cached analysis for incident, ready to analyze:', incidentId);
    setAnalyzingState({ claude: 'pending', gemini: 'pending' });

    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [incidentId]);

  const performAIAnalysis = async () => {
    // Prevent duplicate calls
    if (isAnalyzingRef.current) {
      console.log('Analysis already in progress, skipping...');
      return;
    }
    isAnalyzingRef.current = true;

    console.log('Starting AI analysis for incident:', incidentId);
    if (mountedRef.current) {
      setAnalyzingState({ claude: 'analyzing', gemini: 'analyzing' });
      setApiErrors([]);
      setProviderErrors({});
    }

    try {
      const token = localStorage.getItem('access_token');

      const response = await fetch(`${API_URL}/incidents/${incidentId}/ai-analysis?providers=claude&providers=gemini`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      });

      // Check if still mounted before updating state
      if (!mountedRef.current) return;

      if (!response.ok) {
        const errorData = await response.json().catch(() => null);
        console.error('AI analysis API error:', response.status, errorData);

        // Extract error messages
        let errorMessages: string[] = [];
        if (errorData?.detail?.errors) {
          errorMessages = errorData.detail.errors;
        } else if (errorData?.detail?.message) {
          errorMessages = [errorData.detail.message];
        } else if (errorData?.detail) {
          errorMessages = [typeof errorData.detail === 'string' ? errorData.detail : 'AI analysis failed'];
        } else if (errorData?.message) {
          errorMessages = [errorData.message];
        } else {
          errorMessages = [`AI analysis failed with status ${response.status}`];
        }

        // Check for specific error types
        const errorStr = JSON.stringify(errorData).toLowerCase();
        if (errorStr.includes('credit') || errorStr.includes('balance') || errorStr.includes('billing')) {
          errorMessages = ['API credits exhausted. Please add credits to your Claude/Gemini accounts or update API keys in Settings.'];
        } else if (errorStr.includes('quota') || errorStr.includes('rate') || errorStr.includes('429')) {
          errorMessages = ['API rate limit reached. Please wait a few minutes and try again.'];
        }

        setApiErrors(errorMessages);
        setAnalyzingState({ claude: 'error', gemini: 'error' });
        return; // Don't throw, just return after setting error state
      }

      const data = await response.json();
      console.log('AI analysis response:', data);

      // Check if still mounted before updating state
      if (!mountedRef.current) return;

      // Parse provider-specific errors from the errors array
      const newProviderErrors: { claude?: string; gemini?: string } = {};
      if (data.errors && data.errors.length > 0) {
        setApiErrors(data.errors);

        // Check for provider-specific error messages
        data.errors.forEach((err: string) => {
          const errLower = err.toLowerCase();

          // Check for Claude/Anthropic errors
          const isClaudeError = errLower.includes('claude') || errLower.includes('anthropic');
          const isGeminiError = errLower.includes('gemini') || errLower.includes('google');

          // Parse error type
          const isCreditError = errLower.includes('credit') || errLower.includes('balance') || errLower.includes('billing');
          const isRateError = errLower.includes('rate') || errLower.includes('quota') || errLower.includes('429');
          const isKeyError = errLower.includes('key') || errLower.includes('invalid') || errLower.includes('auth');

          if (isClaudeError) {
            if (isCreditError) {
              newProviderErrors.claude = 'Claude API credits exhausted. Add credits at console.anthropic.com';
            } else if (isRateError) {
              newProviderErrors.claude = 'Claude API rate limit reached. Try again in a few minutes.';
            } else if (isKeyError) {
              newProviderErrors.claude = 'Claude API key invalid. Update in Settings.';
            } else {
              newProviderErrors.claude = err;
            }
          } else if (isGeminiError) {
            if (isCreditError || isRateError) {
              newProviderErrors.gemini = 'Gemini API quota exhausted. Check your Google Cloud billing.';
            } else if (isKeyError) {
              newProviderErrors.gemini = 'Gemini API key invalid. Update in Settings.';
            } else {
              newProviderErrors.gemini = err;
            }
          } else {
            // Error doesn't mention provider - infer from which analysis is missing
            if (!data.claude_analysis && data.gemini_analysis) {
              if (isCreditError) {
                newProviderErrors.claude = 'Claude API credits exhausted. Add credits at console.anthropic.com';
              } else if (isRateError) {
                newProviderErrors.claude = 'Claude API rate limit reached. Try again in a few minutes.';
              } else {
                newProviderErrors.claude = err;
              }
            } else if (data.claude_analysis && !data.gemini_analysis) {
              if (isCreditError || isRateError) {
                newProviderErrors.gemini = 'Gemini API quota exhausted. Check Google Cloud billing.';
              } else {
                newProviderErrors.gemini = err;
              }
            }
          }
        });
        setProviderErrors(newProviderErrors);
      }

      // Build the final analyses object
      const newAnalyses: { claude?: AIAnalysis; gemini?: AIAnalysis } = {};
      const newState = { claude: 'error' as string, gemini: 'error' as string };

      // Process Claude analysis - NO FALLBACK VALUES
      if (data.claude_analysis) {
        console.log('Claude analysis received');
        newAnalyses.claude = {
          provider: 'claude',
          confidence: data.claude_analysis.confidence_score > 1
            ? data.claude_analysis.confidence_score / 100
            : data.claude_analysis.confidence_score,
          rootCause: data.claude_analysis.root_cause,
          solution: {
            description: data.claude_analysis.solution_description || data.claude_analysis.recommended_actions?.[0],
            steps: data.claude_analysis.solution_steps || data.claude_analysis.recommended_actions,
            commands: data.claude_analysis.deployment_commands || [],
            estimatedTime: data.claude_analysis.estimated_time || data.claude_analysis.estimated_resolution_time,
            riskLevel: data.claude_analysis.risk_level || 'medium',
            reversible: data.claude_analysis.reversible !== false
          },
          impact: {
            affectedSystems: data.claude_analysis.affected_systems || [],
            businessImpact: data.claude_analysis.business_impact,
            userImpact: data.claude_analysis.user_impact
          },
          preventionSteps: data.claude_analysis.prevention_steps || []
        };
        newState.claude = 'complete';
      }

      // Process Gemini analysis - NO FALLBACK VALUES
      if (data.gemini_analysis) {
        console.log('Gemini analysis received');
        newAnalyses.gemini = {
          provider: 'gemini',
          confidence: data.gemini_analysis.confidence_score > 1
            ? data.gemini_analysis.confidence_score / 100
            : data.gemini_analysis.confidence_score,
          rootCause: data.gemini_analysis.root_cause,
          solution: {
            description: data.gemini_analysis.solution_description || data.gemini_analysis.recommended_actions?.[0],
            steps: data.gemini_analysis.solution_steps || data.gemini_analysis.recommended_actions,
            commands: data.gemini_analysis.deployment_commands || [],
            estimatedTime: data.gemini_analysis.estimated_time || data.gemini_analysis.estimated_resolution_time,
            riskLevel: data.gemini_analysis.risk_level || 'medium',
            reversible: data.gemini_analysis.reversible !== false
          },
          impact: {
            affectedSystems: data.gemini_analysis.affected_systems || [],
            businessImpact: data.gemini_analysis.business_impact,
            userImpact: data.gemini_analysis.user_impact
          },
          preventionSteps: data.gemini_analysis.prevention_steps || []
        };
        newState.gemini = 'complete';
      }

      // Cache the results for future re-mounts
      if (newAnalyses.claude || newAnalyses.gemini) {
        cacheAnalysis(incidentId, newAnalyses);
        console.log('Cached AI analysis results for incident:', incidentId);
      }

      // Update state
      setAnalyses(newAnalyses);
      setAnalyzingState(newState);

    } catch (error: any) {
      console.error('AI analysis error:', error);
      if (mountedRef.current) {
        // Set a user-friendly error message
        const errorMessage = error?.message || 'An unexpected error occurred during AI analysis';
        setApiErrors([errorMessage]);
        setAnalyzingState({ claude: 'error', gemini: 'error' });
      }
    } finally {
      isAnalyzingRef.current = false;
      inFlightRequests.delete(incidentId);
    }
  };

  const handleProviderSelect = (provider: 'claude' | 'gemini') => {
    setSelectedProvider(provider);
    const analysis = provider === 'claude' ? analyses.claude : analyses.gemini;
    if (analysis && onDeploymentSelect) {
      onDeploymentSelect(provider, analysis.solution);
    }
  };

  const getConfidenceColor = (confidence: number) => {
    if (confidence >= 0.8) return 'text-green-400';
    if (confidence >= 0.6) return 'text-yellow-400';
    return 'text-red-400';
  };

  const getConfidenceBadgeClasses = (confidence: number): string => {
    if (confidence >= 0.8) return 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20';
    if (confidence >= 0.6) return 'bg-yellow-500/10 text-yellow-400 border-yellow-500/20';
    return 'bg-red-500/10 text-red-400 border-red-500/20';
  };

  const getRiskBadgeClasses = (risk: string): string => {
    switch (risk) {
      case 'low': return 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20';
      case 'medium': return 'bg-yellow-500/10 text-yellow-400 border-yellow-500/20';
      case 'high': return 'bg-red-500/10 text-red-400 border-red-500/20';
      default: return 'bg-secondary text-muted-foreground border-border';
    }
  };

  const AnalysisCard = ({ provider, analysis }: { provider: 'claude' | 'gemini', analysis?: AIAnalysis }) => {
    const state = analyzingState[provider];
    const isSelected = selectedProvider === provider;

    return (
      <div
        className={`border border-border rounded-lg bg-transparent p-6 transition-all duration-300 ${isSelected ? 'border-border' : ''}`}
      >
        {/* Header */}
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center space-x-3">
            <div className={`p-2 rounded-xl ${provider === 'claude' ? 'bg-blue-500/10' : 'bg-purple-500/10'}`}>
              <Cpu className={`w-6 h-6 ${provider === 'claude' ? 'text-blue-400' : 'text-purple-400'}`} />
            </div>
            <div>
              <h3 className="text-base font-medium text-purple-400">
                {provider === 'claude' ? 'Claude' : 'Gemini'} AI
              </h3>
              <p className="text-sm text-muted-foreground">
                {provider === 'claude' ? 'Advanced analysis' : 'Fast automation'}
              </p>
            </div>
          </div>

          {analysis && (
            <div className="text-right">
              <div className={`text-2xl font-bold ${getConfidenceColor(analysis.confidence)}`}>
                {Math.round(analysis.confidence * 100)}%
              </div>
              <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border mt-1 ${getConfidenceBadgeClasses(analysis.confidence)}`}>
                confidence
              </span>
            </div>
          )}
        </div>

        {/* Analysis State */}
        {state === 'analyzing' && (
          <div className="flex items-center justify-center py-8">
            <RefreshCw className="w-8 h-8 text-blue-400 animate-spin mr-3" />
            <span className="text-foreground">Analyzing incident...</span>
          </div>
        )}

        {state === 'error' && (
          <div className="flex items-center justify-center py-8 text-red-400">
            <AlertTriangle className="w-8 h-8 mr-3" />
            <span>Analysis failed</span>
          </div>
        )}

        {/* Analysis Results */}
        {state === 'complete' && analysis && (
          <div className="space-y-5">
            {/* Root Cause */}
            <div className="bg-transparent border border-border rounded-lg p-4">
              <h4 className="text-sm font-medium text-purple-400 mb-3 flex items-center">
                <AlertTriangle className="w-4 h-4 mr-2 text-yellow-400" />
                Root Cause Analysis
              </h4>
              <p className="text-muted-foreground text-sm leading-relaxed whitespace-pre-line">
                {analysis.rootCause}
              </p>
            </div>

            {/* Solution Overview */}
            <div className="bg-transparent border border-border rounded-lg p-4">
              <h4 className="text-sm font-medium text-purple-400 mb-3 flex items-center">
                <Rocket className="w-4 h-4 mr-2 text-green-400" />
                Recommended Solution
              </h4>
              <p className="text-muted-foreground text-sm leading-relaxed whitespace-pre-line mb-4">
                {analysis.solution.description}
              </p>

              <div className="flex items-center flex-wrap gap-3 pt-3 border-t border-border">
                <span className="flex items-center text-muted-foreground text-sm">
                  <Clock className="w-4 h-4 mr-1.5" />
                  {analysis.solution.estimatedTime}
                </span>
                <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border ${getRiskBadgeClasses(analysis.solution.riskLevel)}`}>
                  {analysis.solution.riskLevel} risk
                </span>
                {analysis.solution.reversible && (
                  <span className="flex items-center text-green-400 text-sm">
                    <ShieldCheck className="w-4 h-4 mr-1.5" />
                    Reversible
                  </span>
                )}
              </div>
            </div>

            {/* Solution Steps Preview */}
            <div className="bg-transparent border border-border rounded-lg p-4">
              <h4 className="text-sm font-medium text-purple-400 mb-3 flex items-center">
                <CheckCircle className="w-4 h-4 mr-2 text-blue-400" />
                Resolution Steps
              </h4>
              <ul className="space-y-3">
                {analysis.solution.steps.slice(0, 5).map((step, index) => (
                  <li key={index} className="text-sm text-foreground flex items-start">
                    <span className={`w-6 h-6 rounded-full flex items-center justify-center text-xs mr-3 flex-shrink-0 mt-0.5 ${provider === 'claude' ? 'bg-blue-500/20 text-blue-400' : 'bg-purple-500/20 text-purple-400'}`}>
                      {index + 1}
                    </span>
                    <span className="flex-1 leading-relaxed">{step}</span>
                  </li>
                ))}
                {analysis.solution.steps.length > 5 && (
                  <li className="text-sm text-muted-foreground ml-9">
                    +{analysis.solution.steps.length - 5} more steps...
                  </li>
                )}
              </ul>
            </div>

            {/* Affected Systems */}
            {analysis.impact.affectedSystems.length > 0 && (
              <div className="bg-transparent border border-border rounded-lg p-4">
                <h4 className="text-sm font-medium text-purple-400 mb-3 flex items-center">
                  <Zap className="w-4 h-4 mr-2 text-orange-400" />
                  Affected Systems
                </h4>
                <div className="flex flex-wrap gap-2">
                  {analysis.impact.affectedSystems.map((system, index) => (
                    <span key={index} className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border bg-secondary text-muted-foreground border-border">
                      {system}
                    </span>
                  ))}
                </div>
              </div>
            )}


          </div>
        )}
      </div>
    );
  };

  // Show loading state when analysis is in progress
  if (analyzingState.claude === 'analyzing' || analyzingState.gemini === 'analyzing') {
    return (
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-base font-medium text-purple-400 mb-2">AI Analysis Results</h2>
            <p className="text-muted-foreground">Analyzing your incident with AI...</p>
          </div>
        </div>
        <div className="border border-border rounded-lg bg-transparent p-12 text-center">
          <RefreshCw className="w-12 h-12 text-blue-400 animate-spin mx-auto mb-4" />
          <h3 className="text-base font-medium text-purple-400 mb-2">Analyzing Incident</h3>
          <p className="text-muted-foreground">Claude and Gemini are analyzing your incident...</p>
        </div>
      </div>
    );
  }

  // Show pending state - waiting for user to start analysis
  if (analyzingState.claude === 'pending' && analyzingState.gemini === 'pending' && !analyses.claude && !analyses.gemini) {
    return (
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-base font-medium text-purple-400 mb-2">AI Analysis</h2>
            <p className="text-muted-foreground">Get AI-powered insights for this incident</p>
          </div>
        </div>
        <div className="border border-border rounded-lg bg-transparent p-12 text-center">
          <div className="p-3 rounded-xl bg-purple-500/10 w-fit mx-auto mb-4">
            <Sparkles className="w-8 h-8 text-purple-400" />
          </div>
          <h3 className="text-base font-medium text-purple-400 mb-2">Ready to Analyze</h3>
          <p className="text-muted-foreground mb-6">Click below to get AI analysis of this incident</p>
          <button
            className="bg-primary text-primary-foreground hover:bg-white/90 rounded-md px-6 py-2.5 text-sm font-medium inline-flex items-center gap-2"
            onClick={() => {
              inFlightRequests.add(incidentId);
              performAIAnalysis();
            }}
          >
            <Sparkles className="w-5 h-5" />
            Start AI Analysis
          </button>
        </div>
      </div>
    );
  }

  // Show state where analysis "completed" but no data - offer to re-run
  if (!analyses.claude && !analyses.gemini && (analyzingState.claude === 'complete' || analyzingState.gemini === 'complete')) {
    return (
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-base font-medium text-purple-400 mb-2">AI Analysis</h2>
            <p className="text-muted-foreground">Analysis data not available</p>
          </div>
        </div>
        <div className="border border-border rounded-lg bg-transparent p-12 text-center">
          <AlertTriangle className="w-12 h-12 text-yellow-400 mx-auto mb-4" />
          <h3 className="text-base font-medium text-purple-400 mb-2">Analysis Results Not Found</h3>
          <p className="text-muted-foreground mb-6">The previous analysis data couldn't be loaded. Run a new analysis.</p>
          <button
            className="bg-primary text-primary-foreground hover:bg-white/90 rounded-md px-6 py-2.5 text-sm font-medium inline-flex items-center gap-2"
            onClick={() => {
              clearCachedAnalysis(incidentId);
              inFlightRequests.delete(incidentId);
              setAnalyses({});
              setAnalyzingState({ claude: 'pending', gemini: 'pending' });
              inFlightRequests.add(incidentId);
              performAIAnalysis();
            }}
          >
            <Sparkles className="w-5 h-5" />
            Run AI Analysis
          </button>
        </div>
      </div>
    );
  }

  // Show error UI if no analysis available
  if (!analyses.claude && !analyses.gemini && (analyzingState.claude === 'error' || analyzingState.gemini === 'error')) {
    const isRateLimitError = apiErrors.some(e => e.toLowerCase().includes('rate') || e.toLowerCase().includes('quota') || e.toLowerCase().includes('429'));

    return (
      <div className="space-y-6">
        <div>
          <h2 className="text-base font-medium text-purple-400 mb-2">AI Analysis</h2>
          <p className="text-muted-foreground">Unable to complete analysis</p>
        </div>

        <div className={`border border-border rounded-lg bg-transparent p-6 text-center ${isRateLimitError ? 'border-orange-500/30' : 'border-red-500/30'}`}>
          <AlertTriangle className={`w-12 h-12 ${isRateLimitError ? 'text-orange-400' : 'text-yellow-400'} mx-auto mb-4`} />
          <h3 className="text-base font-medium text-purple-400 mb-2">
            {isRateLimitError ? 'API Rate Limit Reached' : 'AI Analysis Failed'}
          </h3>
          <p className="text-foreground mb-4 max-w-md mx-auto">
            {isRateLimitError
              ? 'The AI providers have temporarily limited requests. Please wait a few minutes and try again.'
              : apiErrors.length > 0
                ? apiErrors.join(', ')
                : 'Configure your AI API keys in Settings to enable intelligent incident analysis'}
          </p>

          {apiErrors.length > 0 && (
            <div className="bg-transparent border border-border rounded-lg p-3 mb-4 text-left max-w-md mx-auto">
              <p className="text-xs text-muted-foreground mb-1">Error details:</p>
              <p className="text-xs text-muted-foreground font-mono">{apiErrors.join('; ')}</p>
            </div>
          )}

          <div className="flex gap-3 justify-center">
            <button
              className="bg-primary text-primary-foreground hover:bg-white/90 rounded-md px-6 py-2.5 text-sm font-medium"
              onClick={() => {
                clearCachedAnalysis(incidentId);
                inFlightRequests.delete(incidentId);
                isAnalyzingRef.current = false;
                setAnalyses({});
                setApiErrors([]);
                setAnalyzingState({ claude: 'analyzing', gemini: 'analyzing' });
                inFlightRequests.add(incidentId);
                performAIAnalysis();
              }}
            >
              Try Again
            </button>
            <button
              className="border border-border text-foreground hover:bg-accent rounded-md px-6 py-2.5 text-sm font-medium"
              onClick={() => window.location.href = '/settings'}
            >
              Configure API Keys
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-base font-medium text-purple-400 mb-2">AI Analysis</h2>
          <p className="text-muted-foreground">
            {analyses.claude && analyses.gemini
              ? 'Multiple AI providers have analyzed your incident for maximum accuracy.'
              : analyses.claude || analyses.gemini
                ? 'AI analysis completed. Add a second provider for dual AI comparison.'
                : 'Get AI-powered root cause analysis and resolution steps'}
          </p>
        </div>

        {(analyzingState.claude === 'complete' || analyzingState.gemini === 'complete') && (
          <button
            className="border border-border text-foreground hover:bg-accent rounded-md px-6 py-2.5 text-sm font-medium inline-flex items-center gap-2"
            onClick={() => {
              // Clear the cache and tracking so re-analysis can happen
              clearCachedAnalysis(incidentId);
              inFlightRequests.delete(incidentId);
              isAnalyzingRef.current = false;
              setAnalyses({});
              setAnalyzingState({ claude: 'pending', gemini: 'pending' });
              // Add to in-flight and start analysis
              inFlightRequests.add(incidentId);
              performAIAnalysis();
            }}
          >
            <RefreshCw className="w-4 h-4" />
            <span>Re-analyze</span>
          </button>
        )}
      </div>

      {/* Error Banner - Show when one provider failed */}
      {providerErrors.claude && analyses.gemini && !analyses.claude && (
        <div className="p-4 border border-red-500/30 rounded-lg bg-transparent">
          <div className="flex items-start gap-3">
            <AlertTriangle className="w-5 h-5 text-red-400 flex-shrink-0 mt-0.5" />
            <div className="flex-1">
              <p className="text-red-300 text-sm font-medium mb-1">
                Claude AI Unavailable
              </p>
              <p className="text-red-200/80 text-xs">
                {providerErrors.claude}
              </p>
            </div>
            <button
              onClick={() => window.location.href = '/settings'}
              className="text-red-300 text-xs border border-border hover:bg-accent rounded-md px-4 py-1.5 font-medium"
            >
              Fix in Settings
            </button>
          </div>
        </div>
      )}

      {providerErrors.gemini && analyses.claude && !analyses.gemini && (
        <div className="p-4 border border-red-500/30 rounded-lg bg-transparent">
          <div className="flex items-start gap-3">
            <AlertTriangle className="w-5 h-5 text-red-400 flex-shrink-0 mt-0.5" />
            <div className="flex-1">
              <p className="text-red-300 text-sm font-medium mb-1">
                Gemini AI Unavailable
              </p>
              <p className="text-red-200/80 text-xs">
                {providerErrors.gemini}
              </p>
            </div>
            <button
              onClick={() => window.location.href = '/settings'}
              className="text-red-300 text-xs border border-border hover:bg-accent rounded-md px-4 py-1.5 font-medium"
            >
              Fix in Settings
            </button>
          </div>
        </div>
      )}

      {/* Single Provider Info Banner - CLAUDE ONLY (no error) */}
      {(analyses.claude && !analyses.gemini && !providerErrors.gemini) && (
        <div className="p-4 border border-blue-500/30 rounded-lg bg-transparent">
          <div className="flex items-start gap-3">
            <Info className="w-5 h-5 text-blue-400 flex-shrink-0 mt-0.5" />
            <div className="flex-1">
              <p className="text-blue-300 text-sm font-medium mb-1">
                Using Claude AI Analysis
              </p>
              <p className="text-blue-200/80 text-xs">
                Add Gemini API key in Settings for dual AI comparison
              </p>
            </div>
            <button
              onClick={() => window.location.href = '/settings'}
              className="text-blue-300 text-xs border border-border hover:bg-accent rounded-md px-4 py-1.5 font-medium"
            >
              Add Gemini
            </button>
          </div>
        </div>
      )}

      {/* Single Provider Info Banner - GEMINI ONLY (no error) */}
      {(!analyses.claude && analyses.gemini && !providerErrors.claude) && (
        <div className="p-4 border border-purple-500/30 rounded-lg bg-transparent">
          <div className="flex items-start gap-3">
            <Info className="w-5 h-5 text-purple-400 flex-shrink-0 mt-0.5" />
            <div className="flex-1">
              <p className="text-purple-300 text-sm font-medium mb-1">
                Using Gemini AI Analysis
              </p>
              <p className="text-purple-200/80 text-xs">
                Add Claude API key in Settings for dual AI comparison
              </p>
            </div>
            <button
              onClick={() => window.location.href = '/settings'}
              className="text-purple-300 text-xs border border-border hover:bg-accent rounded-md px-4 py-1.5 font-medium"
            >
              Add Claude
            </button>
          </div>
        </div>
      )}

      {/* Analysis Cards */}
      <div className={`grid gap-6 ${analyses.claude && analyses.gemini ? 'lg:grid-cols-2' : 'lg:grid-cols-1'}`}>
        {analyses.claude && <AnalysisCard provider="claude" analysis={analyses.claude} />}
        {analyses.gemini && <AnalysisCard provider="gemini" analysis={analyses.gemini} />}

        {/* FALLBACK: If we somehow got here with no data, show start button */}
        {!analyses.claude && !analyses.gemini && (
          <div className="p-12 text-center col-span-full border border-border rounded-lg bg-transparent">
            <div className="p-3 rounded-xl bg-purple-500/10 w-fit mx-auto mb-4">
              <Sparkles className="w-8 h-8 text-purple-400" />
            </div>
            <h3 className="text-base font-medium text-purple-400 mb-2">No Analysis Data</h3>
            <p className="text-muted-foreground mb-6">Click below to analyze this incident with AI</p>
            <button
              className="bg-primary text-primary-foreground hover:bg-white/90 rounded-md px-6 py-2.5 text-sm font-medium inline-flex items-center gap-2"
              onClick={() => {
                clearCachedAnalysis(incidentId);
                inFlightRequests.delete(incidentId);
                isAnalyzingRef.current = false;
                setAnalyses({});
                setAnalyzingState({ claude: 'analyzing', gemini: 'analyzing' });
                inFlightRequests.add(incidentId);
                performAIAnalysis();
              }}
            >
              <Sparkles className="w-5 h-5" />
              Start AI Analysis
            </button>
          </div>
        )}
      </div>

      {/* Comparison Summary - Only when both available */}
      {analyses.claude && analyses.gemini && (
        <div className="p-6 bg-transparent border border-border rounded-lg">
          <h3 className="text-base font-medium text-foreground mb-4 flex items-center">
            <Zap className="w-5 h-5 mr-2 text-yellow-400" />
            Dual AI Comparison
          </h3>
          <p className="text-muted-foreground text-sm mb-4">
            Both AI providers analyzed this incident. Compare their insights below:
          </p>

          <div className="grid md:grid-cols-2 gap-6">
            <div className="bg-blue-500/10 border border-blue-500/20 rounded-lg p-4">
              <h4 className="text-sm font-medium text-blue-400 mb-3">Claude AI Analysis</h4>
              <ul className="text-sm text-foreground space-y-2">
                <li className="flex justify-between">
                  <span>Confidence:</span>
                  <span className="font-semibold">{Math.round(analyses.claude.confidence * 100)}%</span>
                </li>
                <li className="flex justify-between">
                  <span>Est. time:</span>
                  <span className="font-semibold">{analyses.claude.solution.estimatedTime}</span>
                </li>
                <li className="flex justify-between">
                  <span>Risk level:</span>
                  <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border ${getRiskBadgeClasses(analyses.claude.solution.riskLevel)}`}>
                    {analyses.claude.solution.riskLevel}
                  </span>
                </li>
              </ul>
            </div>

            <div className="bg-purple-500/10 border border-purple-500/20 rounded-lg p-4">
              <h4 className="text-sm font-medium text-purple-400 mb-3">Gemini AI Analysis</h4>
              <ul className="text-sm text-foreground space-y-2">
                <li className="flex justify-between">
                  <span>Confidence:</span>
                  <span className="font-semibold">{Math.round(analyses.gemini.confidence * 100)}%</span>
                </li>
                <li className="flex justify-between">
                  <span>Est. time:</span>
                  <span className="font-semibold">{analyses.gemini.solution.estimatedTime}</span>
                </li>
                <li className="flex justify-between">
                  <span>Risk level:</span>
                  <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border ${getRiskBadgeClasses(analyses.gemini.solution.riskLevel)}`}>
                    {analyses.gemini.solution.riskLevel}
                  </span>
                </li>
              </ul>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default AIAnalysisDisplay;
