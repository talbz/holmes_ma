import React from 'react';
import { memo } from 'react';
import classNames from 'classnames';
import PropTypes from 'prop-types';

const ToastItem = memo(({ id, type = 'info', message, onRemove }) => {
  return (
    <div 
      className={classNames('toast', `toast-${type}`)}
      role="alert"
    >
      <div className="toast-message">{message}</div>
      <button 
        className="toast-close-button" 
        onClick={() => onRemove(id)}
        aria-label="Close notification"
      >
        ×
      </button>
    </div>
  );
});

ToastItem.displayName = 'ToastItem';

export const Toast = memo(({ toasts = [], onRemove }) => {
  if (!toasts || toasts.length === 0) {
    return null;
  }

  return (
    <div className="toast-container">
      {toasts.map(toast => (
        <ToastItem
          key={toast.id}
          id={toast.id}
          type={toast.type}
          message={toast.message}
          onRemove={onRemove}
        />
      ))}
    </div>
  );
});

Toast.displayName = 'Toast';

Toast.propTypes = {
  toasts: PropTypes.arrayOf(
    PropTypes.shape({
      id: PropTypes.number.isRequired,
      message: PropTypes.string.isRequired,
      type: PropTypes.oneOf(['info', 'success', 'warning', 'error'])
    })
  ),
  onRemove: PropTypes.func.isRequired
}; 