// frontend/oncall-frontend/src/components/AlertDetail.tsx

import React, { useState, useEffect } from 'react';
import {
  Activity,
  AlertCircle,
  ExternalLink,
  FileText,
  Layers,
  MessageSquare,
  RefreshCw,
  TrendingUp
} from 'lucide-react';
import { Button } from './ui/button';
import { API_URL } from '../config/api';

interface AlertDetailProps {
  alertId: string;
  onBack?: () => void;
}

interface AlertData {
  id: string;
  title: string;
  description: string;
  severity: string;
  status: string;
  service_name: string;
  source: string;
  created_at: string;
  started_at: string;
}

interface Enrichment {
  alert_id: string;
  related_metrics: Record<string, any>;
  related_logs: any[];
  related_traces: any[];
  dashboard_url?: string;
  logs_url?: string;
  traces_url?: string;
  correlated_alerts: string[];
  correlation_score: number;
  correlation_reason: string;
  ai_severity_score: number;
  severity_confidence: number;
  original_severity: string;
  adjusted_severity: string;
  severity_factors: Record<string, any>;
  processing_time_ms: number;
  enriched_at: string;
}

interface ChatMessage {
  role: 'user' | 'assistant' | 'error';
  content: string;
  provider?: string;
}

const AlertDetail: React.FC<AlertDetailProps> = ({ alertId, onBack }) => {
  const [alert, setAlert] = useState<AlertData | null>(null);
  const [enrichment, setEnrichment] = useState<Enrichment | null>(null);
  const [loading, setLoading] = useState(true);
  const [enriching, setEnriching] = useState(false);
  const [chatMessage, setChatMessage] = useState('');
  const [chatHistory, setChatHistory] = useState<ChatMessage[]>([]);
  const [chatLoading, setChatLoading] = useState(false);

  useEffect(() => {
    const fetchAlertData = async () => {
      try {
        const token = localStorage.getItem('access_token');

        const alertRes = await fetch(`${API_URL}/alerts/${alertId}`, {
          headers: { 'Authorization': `Bearer ${token}` }
        });
        const alertData = await alertRes.json();
        setAlert(alertData);

        try {
          const enrichRes = await fetch(`${API_URL}/alerts/${alertId}/enrichment`, {
            headers: { 'Authorization': `Bearer ${token}` }
          });
          if (enrichRes.ok) {
            const enrichData = await enrichRes.json();
            setEnrichment(enrichData);
          }
        } catch (err) {
          console.log('No enrichment data yet');
        }

        setLoading(false);
      } catch (error) {
        console.error('Failed to fetch alert:', error);
        setLoading(false);
      }
    };

    fetchAlertData();
  }, [alertId]);

  const triggerEnrichment = async () => {
    setEnriching(true);
    try {
      const token = localStorage.getItem('access_token');
      const res = await fetch(`${API_URL}/alerts/${alertId}/enrich`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}` }
      });
      const data = await res.json();
      setEnrichment(data);
    } catch (error) {
      console.error('Enrichment failed:', error);
      window.alert('Failed to enrich alert. Check console for details.');
    }
    setEnriching(false);
  };

  const sendChatMessage = async () => {
    if (!chatMessage.trim()) return;

    setChatLoading(true);
    const userMessage: ChatMessage = { role: 'user', content: chatMessage };
    setChatHistory(prev => [...prev, userMessage]);

    try {
      const token = localStorage.getItem('access_token');
      const res = await fetch(`${API_URL}/alerts/${alertId}/chat`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ message: chatMessage })
      });
      const data = await res.json();

      const assistantMessage: ChatMessage = {
        role: 'assistant',
        content: data.response,
        provider: data.provider
      };
      setChatHistory(prev => [...prev, assistantMessage]);
      setChatMessage('');
    } catch (error) {
      console.error('Chat failed:', error);
      const errorMessage: ChatMessage = {
        role: 'error',
        content: 'Failed to get AI response. Please try again.'
      };
      setChatHistory(prev => [...prev, errorMessage]);
    }
    setChatLoading(false);
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <RefreshCw className="w-8 h-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (!alert) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <div className="text-center">
          <div className="p-3 rounded-xl bg-red-500/10 w-fit mx-auto mb-4">
            <AlertCircle className="w-10 h-10 text-red-400" />
          </div>
          <h2 className="text-2xl font-bold text-foreground mb-2">Alert Not Found</h2>
          <p className="text-muted-foreground text-sm">The alert you're looking for doesn't exist.</p>
        </div>
      </div>
    );
  }

  const severityColor = (severity: string) => {
    switch (severity?.toLowerCase()) {
      case 'critical': return 'text-red-400 bg-red-500/10 border border-red-500/20';
      case 'high': return 'text-yellow-400 bg-yellow-500/10 border border-yellow-500/20';
      case 'medium': return 'text-yellow-400 bg-yellow-500/10 border border-yellow-500/20';
      case 'low': return 'text-blue-400 bg-blue-500/10 border border-blue-500/20';
      default: return 'text-muted-foreground bg-accent border border-border';
    }
  };

  return (
    <div className="min-h-screen bg-background p-6">
      <div className="max-w-7xl mx-auto space-y-6">
        {/* Header */}
        <div className="bg-transparent border border-border rounded-xl p-6">
          <div className="flex items-center justify-between">
            <div className="flex-1">
              <div className="flex items-center gap-4 mb-2">
                <div className="p-2.5 rounded-xl bg-red-500/10">
                  <AlertCircle className="w-4 h-4 text-red-400" />
                </div>
                <h1 className="text-[20px] font-semibold text-foreground">{alert.title}</h1>
              </div>
              <p className="text-muted-foreground mb-4 text-sm">{alert.description}</p>

              <div className="flex items-center gap-2 text-sm flex-wrap">
                <span className={`inline-flex items-center px-2.5 py-1 rounded-md text-xs font-medium ${severityColor(alert.severity)}`}>
                  {alert.severity || 'UNKNOWN'}
                </span>
                <span className="text-muted-foreground">Service: <strong className="text-foreground">{alert.service_name || 'unknown'}</strong></span>
                <span className="text-muted-foreground">Source: <strong className="text-foreground">{alert.source || 'unknown'}</strong></span>
                <span className="inline-flex items-center px-2.5 py-1 rounded-md text-xs font-medium text-blue-400 bg-blue-500/10 border border-blue-500/20">
                  {alert.status || 'unknown'}
                </span>
              </div>
            </div>

            <Button
              onClick={triggerEnrichment}
              disabled={enriching}
              className="bg-primary text-primary-foreground hover:bg-white/90 text-sm"
            >
              <RefreshCw className={`w-4 h-4 mr-2 ${enriching ? 'animate-spin' : ''}`} />
              {enriching ? 'Enriching...' : enrichment ? 'Re-enrich' : 'Enrich Alert'}
            </Button>
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Left Column - Enrichment Data */}
          <div className="lg:col-span-2 space-y-6">
            {!enrichment ? (
              <div className="bg-transparent border border-border rounded-xl p-6 text-center">
                <div className="p-2.5 rounded-xl bg-secondary w-fit mx-auto mb-3">
                  <Activity className="w-8 h-8 text-muted-foreground" />
                </div>
                <h3 className="text-base font-medium text-foreground mb-2">No Enrichment Data Yet</h3>
                <p className="text-muted-foreground mb-4 text-sm">
                  Click "Enrich Alert" to fetch metrics, logs, and AI analysis from <strong className="text-foreground">{alert.source}</strong>
                </p>
              </div>
            ) : (
              <>
                {/* AI Severity Analysis */}
                <div className="bg-transparent border border-border rounded-xl p-6">
                  <h3 className="text-base font-medium mb-4 flex items-center gap-2">
                    <div className="p-2 rounded-xl bg-blue-500/10">
                      <TrendingUp className="w-4 h-4 text-blue-400" />
                    </div>
                    <span className="text-foreground">AI Severity Analysis</span>
                  </h3>
                  <div className="space-y-3">
                    <div className="flex justify-between items-center">
                      <span className="text-muted-foreground text-sm">AI Severity Score:</span>
                      <span className="text-2xl font-bold text-blue-400">
                        {enrichment.ai_severity_score?.toFixed(1) || 'N/A'}/100
                      </span>
                    </div>
                    <div className="w-full bg-secondary rounded-full h-2">
                      <div
                        className="bg-blue-500 h-2 rounded-full transition-all"
                        style={{ width: `${enrichment.ai_severity_score || 0}%` }}
                      />
                    </div>
                    <div className="flex justify-between items-center">
                      <span className="text-muted-foreground text-sm">Confidence:</span>
                      <span className="font-medium text-foreground text-sm">
                        {((enrichment.severity_confidence || 0) * 100).toFixed(0)}%
                      </span>
                    </div>
                    <div className="flex justify-between items-center">
                      <span className="text-muted-foreground text-sm">Original {'->'} Adjusted:</span>
                      <span className="font-medium text-foreground text-sm">
                        {enrichment.original_severity} {'->'} {enrichment.adjusted_severity}
                      </span>
                    </div>
                    {enrichment.correlation_score > 0 && (
                      <div className="mt-4 p-3 bg-yellow-500/5 border border-yellow-500/20 rounded-lg">
                        <p className="text-sm text-yellow-400">
                          <strong>Correlation Detected:</strong> {enrichment.correlation_reason}
                        </p>
                        <p className="text-xs text-muted-foreground mt-1">
                          Score: {(enrichment.correlation_score * 100).toFixed(0)}%
                        </p>
                      </div>
                    )}
                    <div className="text-xs text-muted-foreground mt-2">
                      Processed in {enrichment.processing_time_ms?.toFixed(0)}ms
                    </div>
                  </div>
                </div>

                {/* Metrics */}
                {enrichment.related_metrics && Object.keys(enrichment.related_metrics).length > 0 && (
                  <div className="bg-transparent border border-border rounded-xl p-6">
                    <h3 className="text-base font-medium mb-4 flex items-center gap-2">
                      <div className="p-2 rounded-xl bg-emerald-500/10">
                        <Activity className="w-4 h-4 text-emerald-400" />
                      </div>
                      <span className="text-foreground">Related Metrics from {alert.source}</span>
                    </h3>
                    <pre className="bg-secondary/50 p-4 rounded-lg text-xs overflow-auto max-h-64 border border-border text-emerald-400 font-mono">
                      {JSON.stringify(enrichment.related_metrics, null, 2)}
                    </pre>
                  </div>
                )}

                {/* Logs */}
                {enrichment.related_logs && enrichment.related_logs.length > 0 && (
                  <div className="bg-transparent border border-border rounded-xl p-6">
                    <h3 className="text-base font-medium mb-4 flex items-center gap-2">
                      <div className="p-2 rounded-xl bg-orange-500/10">
                        <FileText className="w-4 h-4 text-orange-400" />
                      </div>
                      <span className="text-foreground">Recent Error Logs ({enrichment.related_logs.length})</span>
                    </h3>
                    <div className="space-y-2 max-h-96 overflow-auto">
                      {enrichment.related_logs.slice(0, 10).map((log, idx) => (
                        <div key={idx} className="bg-secondary/50 text-emerald-400 p-3 rounded-lg text-xs font-mono border border-border">
                          {typeof log === 'string' ? log : JSON.stringify(log)}
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Traces */}
                {enrichment.related_traces && enrichment.related_traces.length > 0 && (
                  <div className="bg-transparent border border-border rounded-xl p-6">
                    <h3 className="text-base font-medium mb-4 flex items-center gap-2">
                      <div className="p-2 rounded-xl bg-purple-500/10">
                        <Layers className="w-4 h-4 text-purple-400" />
                      </div>
                      <span className="text-foreground">Distributed Traces ({enrichment.related_traces.length})</span>
                    </h3>
                    <div className="space-y-2 max-h-64 overflow-auto">
                      {enrichment.related_traces.slice(0, 5).map((trace, idx) => (
                        <div key={idx} className="bg-secondary/50 p-3 rounded-lg text-xs border border-border text-foreground">
                          {typeof trace === 'string' ? trace : JSON.stringify(trace)}
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Drill-down Links */}
                {(enrichment.dashboard_url || enrichment.logs_url || enrichment.traces_url) && (
                  <div className="bg-transparent border border-border rounded-xl p-6">
                    <h3 className="text-base font-medium mb-4 flex items-center gap-2">
                      <div className="p-2 rounded-xl bg-cyan-500/10">
                        <Layers className="w-4 h-4 text-cyan-400" />
                      </div>
                      <span className="text-foreground">Quick Links to {alert.source}</span>
                    </h3>
                    <div className="space-y-2">
                      {enrichment.dashboard_url && (
                        <a
                          href={enrichment.dashboard_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="flex items-center gap-2 text-muted-foreground hover:text-foreground transition-colors text-sm"
                        >
                          <ExternalLink className="w-4 h-4" />
                          View in Dashboard
                        </a>
                      )}
                      {enrichment.logs_url && (
                        <a
                          href={enrichment.logs_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="flex items-center gap-2 text-muted-foreground hover:text-foreground transition-colors text-sm"
                        >
                          <ExternalLink className="w-4 h-4" />
                          View Logs
                        </a>
                      )}
                      {enrichment.traces_url && (
                        <a
                          href={enrichment.traces_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="flex items-center gap-2 text-muted-foreground hover:text-foreground transition-colors text-sm"
                        >
                          <ExternalLink className="w-4 h-4" />
                          View Traces
                        </a>
                      )}
                    </div>
                  </div>
                )}
              </>
            )}
          </div>

          {/* Right Column - AI Chat */}
          <div className="lg:col-span-1">
            <div className="bg-transparent border border-border rounded-xl p-6 sticky top-6">
              <h3 className="text-base font-medium mb-4 flex items-center gap-2">
                <div className="p-2 rounded-xl bg-secondary">
                  <MessageSquare className="w-4 h-4 text-muted-foreground" />
                </div>
                <span className="text-foreground">Ask AI Assistant</span>
              </h3>

              <div className="space-y-4 mb-4 max-h-96 overflow-auto">
                {chatHistory.length === 0 ? (
                  <div className="text-muted-foreground text-sm text-center py-8">
                    <div className="p-2.5 rounded-xl bg-secondary w-fit mx-auto mb-3">
                      <MessageSquare className="w-10 h-10 text-muted-foreground" />
                    </div>
                    <p className="text-foreground text-sm">Ask questions about this alert.</p>
                    <p className="text-xs mt-2 text-muted-foreground">
                      The AI has access to all enrichment data including metrics, logs, and traces.
                    </p>
                  </div>
                ) : (
                  chatHistory.map((msg, idx) => (
                    <div
                      key={idx}
                      className={`p-3 rounded-lg border ${
                        msg.role === 'user' ? 'bg-blue-500/5 border-blue-500/20 ml-8' :
                        msg.role === 'error' ? 'bg-red-500/5 border-red-500/20' : 'bg-secondary/50 border-border mr-8'
                      }`}
                    >
                      <div className="text-xs uppercase tracking-wider text-muted-foreground mb-1">
                        {msg.role === 'user' ? 'You' : msg.role === 'error' ? 'Error' : `AI (${msg.provider || 'assistant'})`}
                      </div>
                      <div className="text-sm whitespace-pre-wrap text-foreground">{msg.content}</div>
                    </div>
                  ))
                )}
                {chatLoading && (
                  <div className="flex items-center gap-2 text-muted-foreground p-3">
                    <RefreshCw className="w-4 h-4 animate-spin" />
                    <span className="text-sm">AI is analyzing...</span>
                  </div>
                )}
              </div>

              <div className="flex gap-2">
                <input
                  type="text"
                  value={chatMessage}
                  onChange={(e) => setChatMessage(e.target.value)}
                  onKeyPress={(e) => {
                    if (e.key === 'Enter' && !e.shiftKey) {
                      e.preventDefault();
                      sendChatMessage();
                    }
                  }}
                  placeholder="Ask about this alert..."
                  disabled={chatLoading}
                  className="flex-1 px-3 py-2 bg-accent border border-border rounded-lg text-foreground placeholder-muted-foreground focus:ring-1 focus:ring-primary/30 focus:border-white/20 transition-all text-sm"
                />
                <Button
                  onClick={sendChatMessage}
                  disabled={chatLoading || !chatMessage.trim()}
                  className="bg-primary text-primary-foreground hover:bg-white/90 text-sm"
                >
                  Send
                </Button>
              </div>

              <div className="mt-4 text-xs text-muted-foreground">
                Try asking: "What caused this?", "How do I fix this?", "Show me similar past incidents"
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default AlertDetail;
