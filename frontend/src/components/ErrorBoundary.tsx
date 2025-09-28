import React, { Component, ErrorInfo, ReactNode } from 'react';
import { Alert, Button, Result } from 'antd';
import { BugOutlined, ReloadOutlined } from '@ant-design/icons';

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
}

interface State {
  hasError: boolean;
  error?: Error;
  errorInfo?: ErrorInfo;
}

class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('ErrorBoundary에서 오류 발생:', error, errorInfo);
    this.setState({
      error,
      errorInfo,
    });

    // 에러 로깅 (실제로는 에러 추적 서비스에 전송)
    this.logErrorToService(error, errorInfo);
  }

  logErrorToService = (error: Error, errorInfo: ErrorInfo) => {
    // 실제 에러 추적 서비스에 전송 (예: Sentry, LogRocket 등)
    console.error('에러 로깅:', {
      message: error.message,
      stack: error.stack,
      componentStack: errorInfo.componentStack,
      timestamp: new Date().toISOString(),
    });
  };

  handleReset = () => {
    this.setState({ hasError: false, error: undefined, errorInfo: undefined });
  };

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback;
      }

      return (
        <div style={{ padding: '24px', textAlign: 'center' }}>
          <Result
            icon={<BugOutlined />}
            title="오류가 발생했습니다"
            subTitle="예상치 못한 오류가 발생했습니다. 페이지를 새로고침하거나 다시 시도해주세요."
            extra={[
              <Button
                key="reset"
                type="primary"
                icon={<ReloadOutlined />}
                onClick={this.handleReset}
              >
                다시 시도
              </Button>,
              <Button
                key="reload"
                onClick={() => window.location.reload()}
              >
                페이지 새로고침
              </Button>,
            ]}
          />

          {/* 개발 환경에서만 에러 상세 정보 표시 */}
          {process.env.NODE_ENV === 'development' && this.state.error && (
            <Alert
              message="디버그 정보"
              description={
                <div>
                  <div><strong>오류:</strong> {this.state.error.message}</div>
                  <div><strong>스택:</strong></div>
                  <pre style={{ fontSize: '12px', whiteSpace: 'pre-wrap' }}>
                    {this.state.error.stack}
                  </pre>
                </div>
              }
              type="error"
              style={{ marginTop: '16px', textAlign: 'left' }}
              closable
            />
          )}
        </div>
      );
    }

    return this.props.children;
  }
}

export default ErrorBoundary;
