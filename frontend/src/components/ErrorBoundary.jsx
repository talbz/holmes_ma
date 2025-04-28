import React from 'react';
import PropTypes from 'prop-types';

/**
 * Error boundary component to catch errors in React components
 * and display a fallback UI instead of crashing the entire app.
 */
export class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null, errorInfo: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    console.error('Error caught by ErrorBoundary:', error, errorInfo);
    this.setState({ errorInfo });
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="error-boundary">
          <div className="error-fallback">
            <h2>שגיאה בטעינת האפליקציה</h2>
            <p>אירעה שגיאה בעת טעינת האפליקציה. אנא נסו לרענן את הדף.</p>
            {this.state.error && (
              <details>
                <summary>פרטי השגיאה (למפתחים)</summary>
                <p>{this.state.error.toString()}</p>
                <pre>{this.state.errorInfo?.componentStack}</pre>
              </details>
            )}
            <button onClick={() => window.location.reload()}>
              רענן דף
            </button>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}

ErrorBoundary.propTypes = {
  children: PropTypes.node.isRequired
}; 