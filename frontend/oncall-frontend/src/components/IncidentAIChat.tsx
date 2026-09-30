// frontend/oncall-frontend/src/components/IncidentAIChat.tsx
// ENHANCED VERSION - Chat History + Image Upload + Better UI

import React, { useState, useEffect, useRef } from 'react';
import {
  Clock,
  Image,
  MessagesSquare,
  Send,
  ShieldCheck,
  Sparkles,
  X
} from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import { useNotifications } from '../contexts/NotificationContext';
import { Button } from './ui/button';
import { Textarea } from './ui/textarea';

import { API_URL as API_BASE_URL } from '../config/api';

interface IncidentAIChatProps {
  incidentId: string;
  incidentContext: any;
}

// AI Chat is now available in the base plan for all users

type AIProvider = 'claude' | 'gemini' | 'both';

interface Message {
  id?: string;
  role: 'user' | 'assistant';
  content: string;
  provider?: string;
  timestamp?: string;
  created_at?: string;
  attachments?: {
    image?: string;
  };
}

interface ChatSession {
  id: string;
  incident_id: string;
  title: string;
  is_encrypted: boolean;
  created_at: string;
  message_count: number;
}

const IncidentAIChat: React.FC<IncidentAIChatProps> = ({ incidentId, incidentContext }) => {
  // AI Chat is now available in the base plan for all users
  const { showToast } = useNotifications();
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [loadingHistory, setLoadingHistory] = useState(true);
  const [selectedProvider, setSelectedProvider] = useState<AIProvider>('claude');
  const [session, setSession] = useState<ChatSession | null>(null);
  const [selectedImage, setSelectedImage] = useState<string | null>(null);
  const [imagePreview, setImagePreview] = useState<string | null>(null);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Auto-scroll to bottom
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  // Load chat history
  useEffect(() => {
    loadChatHistory();
  }, [incidentId]);

  const loadChatHistory = async () => {
    try {
      setLoadingHistory(true);
      const token = localStorage.getItem('access_token');

      // Get session
      const sessionRes = await fetch(`${API_BASE_URL}/incidents/${incidentId}/chat/session`, {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });

      if (sessionRes.ok) {
        const sessionData = await sessionRes.json();
        setSession(sessionData);

        // Get messages
        const messagesRes = await fetch(`${API_BASE_URL}/incidents/${incidentId}/chat/messages`, {
          headers: {
            'Authorization': `Bearer ${token}`
          }
        });

        if (messagesRes.ok) {
          const messagesData = await messagesRes.json();
          setMessages(messagesData);
        }
      }
    } catch (error) {
      console.error('Failed to load chat history:', error);
    } finally {
      setLoadingHistory(false);
    }
  };

  const handleImageSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    // Check file size (max 5MB)
    if (file.size > 5 * 1024 * 1024) {
      showToast({
        type: 'error',
        title: 'File Too Large',
        message: 'Image must be less than 5MB',
        autoClose: true
      });
      return;
    }

    // Check file type
    if (!file.type.startsWith('image/')) {
      showToast({
        type: 'error',
        title: 'Invalid File',
        message: 'Please select an image file',
        autoClose: true
      });
      return;
    }

    const reader = new FileReader();
    reader.onloadend = () => {
      const base64 = reader.result as string;
      setSelectedImage(base64);
      setImagePreview(base64);
    };
    reader.readAsDataURL(file);
  };

  const removeImage = () => {
    setSelectedImage(null);
    setImagePreview(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const sendMessage = async () => {
    if (!input.trim() && !selectedImage) return;

    const userMessage = input;
    const imageData = selectedImage;

    // Clear input
    setInput('');
    removeImage();

    // Add user message to UI immediately
    const tempUserMsg: Message = {
      role: 'user',
      content: userMessage,
      timestamp: new Date().toISOString(),
      attachments: imageData ? { image: imageData } : undefined
    };
    setMessages(prev => [...prev, tempUserMsg]);

    setLoading(true);

    // For streaming providers (claude, gemini), use the stream endpoint
    // For 'both', use the regular endpoint
    const useStreaming = selectedProvider !== 'both';

    try {
      const token = localStorage.getItem('access_token');

      if (useStreaming) {
        // Use streaming endpoint for real-time response
        const response = await fetch(`${API_BASE_URL}/incidents/${incidentId}/chat/stream`, {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({
            content: userMessage,
            provider: selectedProvider,
            image_base64: imageData
          })
        });

        if (!response.ok) {
          throw new Error('Failed to get AI response');
        }

        // Add placeholder AI message that we'll update
        const aiMsgId = `streaming-${Date.now()}`;
        const streamingMsg: Message = {
          id: aiMsgId,
          role: 'assistant',
          content: '',
          provider: selectedProvider,
          timestamp: new Date().toISOString()
        };
        setMessages(prev => [...prev, streamingMsg]);
        setLoading(false); // Show the streaming message instead of loading dots

        // Read the stream
        const reader = response.body?.getReader();
        const decoder = new TextDecoder();
        let accumulatedContent = '';

        if (reader) {
          while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            const chunk = decoder.decode(value);
            const lines = chunk.split('\n');

            for (const line of lines) {
              if (line.startsWith('data: ')) {
                const dataStr = line.slice(6).trim();
                if (dataStr === '[DONE]') {
                  continue;
                }
                try {
                  const data = JSON.parse(dataStr);
                  if (data.text) {
                    accumulatedContent += data.text;
                    // Update the streaming message with new content
                    setMessages(prev => prev.map(msg =>
                      msg.id === aiMsgId
                        ? { ...msg, content: accumulatedContent }
                        : msg
                    ));
                  } else if (data.error) {
                    throw new Error(data.error);
                  }
                } catch (parseErr) {
                  // Ignore parse errors for incomplete chunks
                }
              }
            }
          }
        }
      } else {
        // Use regular endpoint for 'both' provider
        const response = await fetch(`${API_BASE_URL}/incidents/${incidentId}/chat`, {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({
            content: userMessage,
            provider: selectedProvider,
            image_base64: imageData
          })
        });

        if (response.ok) {
          const aiMessage = await response.json();
          setMessages(prev => [...prev, aiMessage]);
        } else {
          throw new Error('Failed to get AI response');
        }
        setLoading(false);
      }
    } catch (error) {
      console.error('Error sending message:', error);
      showToast({
        type: 'error',
        title: 'Error',
        message: 'Failed to send message. Please try again.',
        autoClose: true
      });
      setLoading(false);
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  const formatTimestamp = (timestamp?: string) => {
    if (!timestamp) return '';
    const date = new Date(timestamp);
    return date.toLocaleTimeString('en-US', {
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  // Main chat UI
  return (
    <div className="border border-border rounded-lg bg-transparent overflow-hidden flex flex-col h-[600px]">
      {/* Header */}
      <div className="p-4 border-b border-border bg-secondary/50">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center space-x-3">
            <MessagesSquare className="w-6 h-6 text-foreground" />
            <h3 className="text-base font-medium text-foreground">Ask AI About This Incident</h3>
          </div>
          {session?.is_encrypted && (
            <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border bg-emerald-500/10 text-emerald-400 border-emerald-500/20 gap-1">
              <ShieldCheck className="w-3 h-3" />
              End-to-end encrypted
            </span>
          )}
        </div>

        {/* Provider Selection */}
        <div className="flex space-x-2">
          {['claude', 'gemini', 'both'].map((provider) => (
            <Button
              key={provider}
              variant={selectedProvider === provider ? 'default' : 'secondary'}
              size="sm"
              onClick={() => setSelectedProvider(provider as AIProvider)}
            >
              {provider === 'both' ? 'Both' : provider.charAt(0).toUpperCase() + provider.slice(1)}
            </Button>
          ))}
        </div>

        {/* Session info */}
        {session && session.message_count > 0 && (
          <div className="mt-2 flex items-center space-x-2 text-xs text-muted-foreground">
            <Clock className="w-4 h-4" />
            <span>{session.message_count} messages in this conversation</span>
          </div>
        )}
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {loadingHistory ? (
          <div className="flex items-center justify-center h-full">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
          </div>
        ) : messages.length === 0 ? (
          <div className="flex flex-col h-full">
            {/* AI Context Welcome */}
            <div className="bg-secondary/50 border border-border rounded-lg p-4 mb-4">
              <div className="flex items-start gap-3">
                <div className="w-8 h-8 bg-purple-500/10 rounded-lg flex items-center justify-center flex-shrink-0">
                  <Sparkles className="w-5 h-5 text-purple-400" />
                </div>
                <div>
                  <p className="text-sm font-medium text-foreground mb-2">
                    AI is ready to help with this incident
                  </p>
                  <p className="text-sm text-muted-foreground mb-3">
                    I already know about: <strong>{incidentContext?.title || 'this incident'}</strong>
                    {incidentContext?.severity && (
                      <span className="ml-2 text-xs px-2 py-0.5 rounded bg-accent">
                        {incidentContext.severity.toUpperCase()}
                      </span>
                    )}
                  </p>
                  <div className="flex flex-wrap gap-2">
                    <button
                      onClick={() => setInput("What's likely causing this issue?")}
                      className="text-xs px-3 py-1.5 bg-accent hover:bg-accent rounded-full transition-colors"
                    >
                      What's causing this?
                    </button>
                    <button
                      onClick={() => setInput("Show me the kubectl commands to investigate")}
                      className="text-xs px-3 py-1.5 bg-accent hover:bg-accent rounded-full transition-colors"
                    >
                      kubectl commands
                    </button>
                    <button
                      onClick={() => setInput("What should I check first?")}
                      className="text-xs px-3 py-1.5 bg-accent hover:bg-accent rounded-full transition-colors"
                    >
                      What to check first?
                    </button>
                    <button
                      onClick={() => setInput("Have we seen similar issues before?")}
                      className="text-xs px-3 py-1.5 bg-accent hover:bg-accent rounded-full transition-colors"
                    >
                      Similar past issues?
                    </button>
                  </div>
                </div>
              </div>
            </div>
            <div className="flex-1 flex flex-col items-center justify-center text-center">
              <p className="text-sm text-muted-foreground/70">
                Click a suggestion above or type your question below
              </p>
            </div>
          </div>
        ) : (
          messages.map((message, index) => (
            <div
              key={message.id || index}
              className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}
            >
              <div
                className={`max-w-[80%] rounded-lg p-4 ${
                  message.role === 'user'
                    ? 'bg-secondary text-foreground'
                    : 'bg-accent text-foreground'
                }`}
              >
                {/* Message content */}
                <div className="whitespace-pre-wrap break-words prose prose-sm prose-invert max-w-none">
                  <ReactMarkdown
                    components={{
                      // Style markdown elements
                      p: ({node, ...props}) => <p className="mb-2 last:mb-0" {...props} />,
                      strong: ({node, ...props}) => <strong className="font-semibold" {...props} />,
                      ul: ({node, ...props}) => <ul className="list-disc ml-4 mb-2" {...props} />,
                      li: ({node, ...props}) => <li className="mb-1" {...props} />,
                      code: ({node, inline, ...props}: any) =>
                        inline ?
                          <code className="bg-background/50 px-1 rounded text-sm" {...props} /> :
                          <code className="block bg-background/50 p-2 rounded text-sm my-2 overflow-x-auto whitespace-pre" {...props} />,
                      pre: ({node, ...props}) => <pre className="overflow-x-auto" {...props} />
                    }}
                  >
                    {message.content}
                  </ReactMarkdown>
                </div>

                {/* Image attachment */}
                {message.attachments?.image && (
                  <div className="mt-2">
                    <img
                      src={message.attachments.image}
                      alt="Attachment"
                      className="rounded-lg max-w-full h-auto max-h-64 object-contain"
                    />
                  </div>
                )}

                {/* Metadata */}
                <div className="flex items-center justify-between mt-2 text-xs opacity-70">
                  <span>
                    {message.role === 'assistant' && message.provider && (
                      <span className="font-medium">{message.provider} - </span>
                    )}
                    {formatTimestamp(message.created_at || message.timestamp)}
                  </span>
                </div>
              </div>
            </div>
          ))
        )}

        {loading && (
          <div className="flex justify-start">
            <div className="bg-accent rounded-lg p-4">
              <div className="flex items-center space-x-1">
                <div className="w-2 h-2 bg-secondary rounded-full animate-pulse"></div>
                <div className="w-2 h-2 bg-secondary rounded-full animate-pulse delay-75"></div>
                <div className="w-2 h-2 bg-secondary rounded-full animate-pulse delay-150"></div>
              </div>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Image Preview */}
      {imagePreview && (
        <div className="p-4 border-t border-border bg-secondary/50">
          <div className="relative inline-block">
            <img
              src={imagePreview}
              alt="Preview"
              className="rounded-lg max-h-20 object-contain"
            />
            <button
              onClick={removeImage}
              className="absolute -top-2 -right-2 p-1 bg-destructive rounded-full text-destructive-foreground hover:bg-destructive/80 transition-colors"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>
      )}

      {/* Input */}
      <div className="p-4 border-t border-border bg-secondary/50">
        <div className="flex space-x-2">
          <input
            type="file"
            ref={fileInputRef}
            onChange={handleImageSelect}
            accept="image/*"
            className="hidden"
          />

          <Button
            variant="secondary"
            size="icon"
            onClick={() => fileInputRef.current?.click()}
            title="Attach image"
          >
            <Image className="w-5 h-5" />
          </Button>

          <Textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyPress={handleKeyPress}
            placeholder="Ask about metrics, logs, similar incidents..."
            className="flex-1 min-h-[44px] max-h-32 resize-none"
            rows={1}
            disabled={loading}
          />

          <Button
            onClick={sendMessage}
            disabled={loading || (!input.trim() && !selectedImage)}
            className="gap-2"
          >
            <Send className="w-5 h-5" />
            <span className="hidden sm:inline">Send</span>
          </Button>
        </div>

        <p className="mt-2 text-xs text-muted-foreground">
          Tip: Ask specific questions for better answers. Try "Show kubectl commands" or "What changed recently?"
        </p>
      </div>
    </div>
  );
};

export default IncidentAIChat;
