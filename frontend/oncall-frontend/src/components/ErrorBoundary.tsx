import React, { Component, ErrorInfo, ReactNode } from 'react';
import {
  AlertTriangle,
  Home,
  RefreshCw
} from 'lucide-react';

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
  onError?: (error: Error, errorInfo: ErrorInfo) => void;
}

interface State {
  hasError: boolean;
  error: Error | null;
  errorInfo: ErrorInfo | null;
}

class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = {
      hasError: false,
      error: null,
      errorInfo: null
    };
  }

  static getDerivedStateFromError(error: Error): Partial<State> {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo): void {
    this.setState({ errorInfo });

    // Log to console in development
    console.error('Error Boundary caught an error:', error, errorInfo);

    // Call optional error handler
    if (this.props.onError) {
      this.props.onError(error, errorInfo);
    }

    // In production, you could send to an error tracking service here
    // Example: Sentry.captureException(error);
  }

  handleRetry = (): void => {
    this.setState({
      hasError: false,
      error: null,
      errorInfo: null
    });
  };

  handleGoHome = (): void => {
    window.location.href = '/';
  };

  render(): ReactNode {
    if (this.state.hasError) {
      // Custom fallback UI if provided
      if (this.props.fallback) {
        return this.props.fallback;
      }

      // Default fallback UI
      return (
        <div className="min-h-[400px] flex items-center justify-center p-8">
          <div className="border border-border rounded-lg bg-transparent max-w-md w-full p-8 text-center">
            <div className="flex justify-center mb-4">
              <div className="p-3 rounded-xl bg-red-500/10">
                <AlertTriangle className="w-8 h-8 text-red-400" />
              </div>
            </div>

            <h2 className="text-base font-medium text-foreground mb-2 block">
              Something went wrong
            </h2>

            <p className="text-muted-foreground text-sm mb-6">
              We encountered an unexpected error. Please try again or return to the home page.
            </p>

            {process.env.NODE_ENV === 'development' && this.state.error && (
              <div className="mb-6 text-left">
                <details className="bg-secondary/50 border border-border rounded-lg p-3">
                  <summary className="text-sm font-medium text-foreground cursor-pointer">
                    Error Details (Development Only)
                  </summary>
                  <div className="mt-2 text-xs text-red-400 font-mono overflow-auto max-h-40">
                    <p className="font-semibold">{this.state.error.name}: {this.state.error.message}</p>
                    {this.state.errorInfo && (
                      <pre className="mt-2 whitespace-pre-wrap text-muted-foreground">
                        {this.state.errorInfo.componentStack}
                      </pre>
                    )}
                  </div>
                </details>
              </div>
            )}

            <div className="flex gap-3 justify-center">
              <button
                onClick={this.handleRetry}
                className="bg-primary text-primary-foreground hover:bg-white/90 rounded-md px-6 py-2.5 text-sm font-medium inline-flex items-center gap-2"
              >
                <RefreshCw className="w-4 h-4" />
                Try Again
              </button>
              <button
                onClick={this.handleGoHome}
                className="border border-border text-foreground hover:bg-accent rounded-md px-6 py-2.5 text-sm font-medium inline-flex items-center gap-2"
              >
                <Home className="w-4 h-4" />
                Go Home
              </button>
            </div>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}

// Functional wrapper for easier use with hooks
export const withErrorBoundary = <P extends object>(
  WrappedComponent: React.ComponentType<P>,
  fallback?: ReactNode
) => {
  return function WithErrorBoundary(props: P) {
    return (
      <ErrorBoundary fallback={fallback}>
        <WrappedComponent {...props} />
      </ErrorBoundary>
    );
  };
};

export default ErrorBoundary;
