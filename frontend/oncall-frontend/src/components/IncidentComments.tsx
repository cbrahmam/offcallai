// frontend/oncall-frontend/src/components/IncidentComments.tsx
import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
  AtSign,
  MessageSquare,
  Paperclip,
  Send,
  Smile
} from 'lucide-react';
import { useNotifications } from '../contexts/NotificationContext';

import { API_URL as API_BASE_URL } from '../config/api';


interface Comment {
  id: string;
  content: string;
  user_name: string;
  user_id: string;
  user_avatar?: string;
  created_at: string;
  updated_at?: string;
  is_internal: boolean;
  attachments?: Array<{
    id: string;
    filename: string;
    size: number;
    type: string;
    url: string;
  }>;
  reactions?: Array<{
    type: 'like' | 'heart' | 'thumbs_up';
    users: string[];
  }>;
  mentions?: string[];
}

interface IncidentCommentsProps {
  incidentId: string;
}

const IncidentComments: React.FC<IncidentCommentsProps> = ({ incidentId }) => {
  const { showToast } = useNotifications();
  const [comments, setComments] = useState<Comment[]>([]);
  const [newComment, setNewComment] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showEmojiPicker, setShowEmojiPicker] = useState(false);
  const [isInternal, setIsInternal] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const fetchComments = useCallback(async () => {
    try {
      setError(null);
      const token = localStorage.getItem('access_token');
      const response = await fetch(`${API_BASE_URL}/incidents/${incidentId}/comments`, {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      });

      if (response.ok) {
        const data = await response.json();
        setComments(data.comments || []);
      } else if (response.status === 404) {
        // Comments endpoint may not exist for this incident yet - that's OK
        setComments([]);
      } else {
        setError('Failed to load comments. Please try again.');
      }
    } catch (error) {
      setError('Unable to connect to server. Please check your connection.');
    } finally {
      setIsLoading(false);
    }
  }, [incidentId]);

  useEffect(() => {
    fetchComments();
    // Set up polling for real-time comments (only if no error)
    const interval = setInterval(() => {
      if (!error) {
        fetchComments();
      }
    }, 15000); // Poll every 15 seconds
    return () => clearInterval(interval);
  }, [fetchComments, error]);

  const handleSubmitComment = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!newComment.trim()) return;

    setIsSubmitting(true);

    try {
      const token = localStorage.getItem('access_token');
      const response = await fetch(`${API_BASE_URL}/incidents/${incidentId}/comments`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          content: newComment,
          is_internal: isInternal
        }),
      });

      if (response.ok) {
        const data = await response.json();
        setComments(prev => [...prev, data]);
        setNewComment('');
        showToast({
          type: 'success',
          title: 'Comment Added',
          message: 'Your comment has been posted successfully'
        });
      } else {
        const errorData = await response.json().catch(() => ({}));
        showToast({
          type: 'error',
          title: 'Error',
          message: errorData.detail || 'Failed to post comment. Please try again.'
        });
      }
    } catch (error) {
      showToast({
        type: 'error',
        title: 'Connection Error',
        message: 'Unable to connect to server. Please check your connection.'
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
      handleSubmitComment(e);
    }
  };

  const formatTimestamp = (timestamp: string) => {
    const date = new Date(timestamp);
    const now = new Date();
    const diff = now.getTime() - date.getTime();
    const minutes = Math.floor(diff / 60000);
    const hours = Math.floor(minutes / 60);
    const days = Math.floor(hours / 24);

    if (days > 0) return `${days}d ago`;
    if (hours > 0) return `${hours}h ago`;
    if (minutes > 0) return `${minutes}m ago`;
    return 'Just now';
  };

  const formatFileSize = (bytes: number) => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  const addReaction = (commentId: string, reactionType: 'like' | 'heart' | 'thumbs_up') => {
    setComments(prev => prev.map(comment => {
      if (comment.id === commentId) {
        const reactions = comment.reactions || [];
        const existingReaction = reactions.find(r => r.type === reactionType);

        if (existingReaction) {
          // Toggle reaction
          if (existingReaction.users.includes('You')) {
            existingReaction.users = existingReaction.users.filter(u => u !== 'You');
          } else {
            existingReaction.users.push('You');
          }
        } else {
          // Add new reaction
          reactions.push({ type: reactionType, users: ['You'] });
        }

        return { ...comment, reactions };
      }
      return comment;
    }));
  };

  const renderReactions = (comment: Comment) => {
    if (!comment.reactions || comment.reactions.length === 0) return null;

    return (
      <div className="flex items-center space-x-2 mt-2">
        {comment.reactions.map((reaction, index) => {
          if (reaction.users.length === 0) return null;

          const emoji = reaction.type === 'like' ? '👍' : reaction.type === 'heart' ? '❤️' : '👍';
          const isActive = reaction.users.includes('You');

          return (
            <button
              key={index}
              onClick={() => addReaction(comment.id, reaction.type)}
              className={`flex items-center space-x-1 px-2 py-1 rounded-full text-xs transition-all duration-300 ${
                isActive
                  ? 'bg-blue-500/10 text-blue-400 border border-blue-500/20'
                  : 'bg-secondary/50 text-muted-foreground hover:bg-accent border border-transparent'
              }`}
            >
              <span>{emoji}</span>
              <span>{reaction.users.length}</span>
            </button>
          );
        })}

        {/* Add reaction button */}
        <div className="relative">
          <button
            onClick={() => setShowEmojiPicker(!showEmojiPicker)}
            className="p-1 text-muted-foreground hover:text-foreground transition-colors rounded"
          >
            <Smile className="w-4 h-4" />
          </button>

          {showEmojiPicker && (
            <div className="absolute bottom-full left-0 mb-2 bg-background backdrop-blur-xl border border-border/50 rounded-lg p-2 flex space-x-1 z-10">
              <button
                onClick={() => {
                  addReaction(comment.id, 'thumbs_up');
                  setShowEmojiPicker(false);
                }}
                className="p-1 hover:bg-accent/50 rounded"
              >
                👍
              </button>
              <button
                onClick={() => {
                  addReaction(comment.id, 'heart');
                  setShowEmojiPicker(false);
                }}
                className="p-1 hover:bg-accent/50 rounded"
              >
                ❤️
              </button>
              <button
                onClick={() => {
                  addReaction(comment.id, 'like');
                  setShowEmojiPicker(false);
                }}
                className="p-1 hover:bg-accent/50 rounded"
              >
                👍
              </button>
            </div>
          )}
        </div>
      </div>
    );
  };

  // SECURITY FIX: Render mentions safely without dangerouslySetInnerHTML to prevent XSS
  const renderMentions = (content: string, mentions?: string[]): React.ReactNode => {
    if (!mentions || mentions.length === 0) return content;

    // Split content by mentions and render safely as React elements
    const parts: React.ReactNode[] = [];
    let remainingContent = content;
    let keyIndex = 0;

    mentions.forEach(mention => {
      const mentionText = `@${mention}`;
      const mentionIndex = remainingContent.indexOf(mentionText);

      if (mentionIndex !== -1) {
        // Add text before the mention
        if (mentionIndex > 0) {
          parts.push(remainingContent.substring(0, mentionIndex));
        }
        // Add the styled mention as a React element (safe, no HTML injection)
        parts.push(
          <span
            key={`mention-${keyIndex++}`}
            className="text-blue-400 bg-blue-500/20 px-1 rounded"
          >
            {mentionText}
          </span>
        );
        // Update remaining content
        remainingContent = remainingContent.substring(mentionIndex + mentionText.length);
      }
    });

    // Add any remaining text
    if (remainingContent) {
      parts.push(remainingContent);
    }

    return <>{parts}</>;
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="w-8 h-8 border-4 border-purple-500/30 border-t-purple-500 rounded-full animate-spin"></div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="text-center py-12">
        <div className="p-3 rounded-xl bg-red-500/10 w-fit mx-auto mb-4">
          <MessageSquare className="w-6 h-6 text-red-400" />
        </div>
        <h3 className="text-lg font-semibold text-muted-foreground mb-2">Unable to Load Comments</h3>
        <p className="text-muted-foreground text-sm mb-4">{error}</p>
        <button
          onClick={() => fetchComments()}
          className="bg-primary text-primary-foreground hover:bg-white/90 rounded-md px-6 py-2.5 text-sm font-medium"
        >
          Try Again
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Comments List */}
      <div className="space-y-4">
        {comments.length === 0 ? (
          <div className="text-center py-12">
            <div className="p-3 rounded-xl bg-purple-500/10 w-fit mx-auto mb-4">
              <MessageSquare className="w-10 h-10 text-purple-400" />
            </div>
            <h3 className="text-lg font-semibold text-muted-foreground mb-2">No Comments Yet</h3>
            <p className="text-muted-foreground text-sm">
              Start the conversation by adding the first comment.
            </p>
          </div>
        ) : (
          comments.map((comment) => (
            <div key={comment.id} className={`border border-border rounded-lg bg-transparent p-4 ${comment.is_internal ? 'border-yellow-500/30' : ''}`}>
              {comment.is_internal && (
                <div className="flex items-center space-x-2 mb-2">
                  <span className="h-2.5 w-2.5 rounded-full bg-yellow-500 inline-block" />
                  <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border bg-yellow-500/10 text-yellow-400 border-yellow-500/20">INTERNAL COMMENT</span>
                </div>
              )}

              <div className="flex items-start space-x-3">
                <div className="flex-shrink-0">
                  <div className="w-8 h-8 bg-secondary rounded-full flex items-center justify-center text-foreground text-sm font-medium">
                    {comment.user_avatar || comment.user_name.charAt(0).toUpperCase()}
                  </div>
                </div>

                <div className="flex-1 min-w-0">
                  <div className="flex items-center space-x-2">
                    <span className="font-medium text-foreground">{comment.user_name}</span>
                    <span className="text-muted-foreground text-sm">{formatTimestamp(comment.created_at)}</span>
                  </div>

                  <div className="mt-2 text-foreground leading-relaxed">
                    {renderMentions(comment.content, comment.mentions)}
                  </div>

                  {comment.attachments && comment.attachments.length > 0 && (
                    <div className="mt-3 space-y-2">
                      {comment.attachments.map((attachment) => (
                        <div key={attachment.id} className="flex items-center space-x-2 p-2 bg-secondary/50 rounded-lg border border-border/30">
                          <Paperclip className="w-4 h-4 text-muted-foreground" />
                          <span className="text-sm text-blue-400 hover:text-blue-300 cursor-pointer transition-colors">
                            {attachment.filename}
                          </span>
                          <span className="text-xs text-muted-foreground">
                            ({formatFileSize(attachment.size)})
                          </span>
                        </div>
                      ))}
                    </div>
                  )}

                  {renderReactions(comment)}
                </div>
              </div>
            </div>
          ))
        )}
      </div>

      {/* New Comment Form */}
      <div className="border border-border rounded-lg bg-transparent p-4">
        <form onSubmit={handleSubmitComment}>
          <div className="space-y-3">
            {/* Internal Comment Toggle */}
            <div className="flex items-center space-x-2">
              <input
                type="checkbox"
                id="internal-comment"
                checked={isInternal}
                onChange={(e) => setIsInternal(e.target.checked)}
                className="rounded text-yellow-500 focus:ring-yellow-500 focus:ring-offset-0 bg-secondary/50 border-border/50"
              />
              <label htmlFor="internal-comment" className="text-sm text-foreground">
                Internal comment (only visible to team members)
              </label>
            </div>

            {/* Comment Input */}
            <div className="relative">
              <textarea
                ref={textareaRef}
                value={newComment}
                onChange={(e) => setNewComment(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Add a comment... (Cmd/Ctrl + Enter to submit)"
                className="w-full px-4 py-3 bg-secondary/50 border border-border/50 rounded-xl text-foreground placeholder-muted-foreground focus:outline-none focus:ring-2 focus:ring-purple-500/50 focus:border-transparent transition-all duration-200 resize-none"
                rows={3}
                disabled={isSubmitting}
              />

              {/* Toolbar */}
              <div className="absolute bottom-3 left-3 flex items-center space-x-2">
                <button
                  type="button"
                  onClick={() => fileInputRef.current?.click()}
                  className="p-1 text-muted-foreground hover:text-foreground transition-colors"
                  disabled={isSubmitting}
                >
                  <Paperclip className="w-4 h-4" />
                </button>
                <button
                  type="button"
                  className="p-1 text-muted-foreground hover:text-foreground transition-colors"
                  disabled={isSubmitting}
                >
                  <AtSign className="w-4 h-4" />
                </button>
                <button
                  type="button"
                  className="p-1 text-muted-foreground hover:text-foreground transition-colors"
                  disabled={isSubmitting}
                >
                  <Smile className="w-4 h-4" />
                </button>
              </div>
            </div>

            {/* Submit Button */}
            <div className="flex justify-between items-center">
              <div className="text-xs text-muted-foreground">
                Use @ to mention team members
              </div>
              <button
                type="submit"
                disabled={!newComment.trim() || isSubmitting}
                className="bg-primary text-primary-foreground hover:bg-white/90 rounded-md px-6 py-2.5 text-sm font-medium inline-flex items-center gap-2 disabled:opacity-50"
              >
                {isSubmitting ? (
                  <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin"></div>
                ) : (
                  <Send className="w-4 h-4" />
                )}
                <span>{isSubmitting ? 'Posting...' : 'Post Comment'}</span>
              </button>
            </div>
          </div>

          {/* Hidden File Input */}
          <input
            ref={fileInputRef}
            type="file"
            multiple
            className="hidden"
            onChange={(e) => {
              // TODO: Implement file upload functionality
              if (e.target.files && e.target.files.length > 0) {
                showToast({
                  type: 'info',
                  title: 'Coming Soon',
                  message: 'File attachments will be available in a future update.'
                });
              }
            }}
          />
        </form>
      </div>

      {/* Real-time Indicator */}
      <div className="flex items-center justify-center">
        <div className="flex items-center space-x-2 px-3 py-1 bg-green-500/10 rounded-full border border-green-500/20">
          <span className="h-2.5 w-2.5 rounded-full bg-emerald-500 inline-block" />
          <span className="text-emerald-400 text-xs font-medium">Live Comments</span>
        </div>
      </div>
    </div>
  );
};

export default IncidentComments;
