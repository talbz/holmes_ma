import { memo } from 'react';
import classNames from 'classnames';
import PropTypes from 'prop-types';

export const Toast = memo(({ type = 'info', message, onClose }) => {
  return (
    <div 
      className={classNames('toast', `toast-${type}`)}
      role="alert"
    >
      <div className="toast-message">{message}</div>
      <button 
        className="toast-close-button" 
        onClick={onClose}
        aria-label="Close notification"
      >
        ×
      </button>
    </div>
  );
});

Toast.displayName = 'Toast';

Toast.propTypes = {
  type: PropTypes.oneOf(['info', 'success', 'warning', 'error']),
  message: PropTypes.string.isRequired,
  onClose: PropTypes.func.isRequired
}; 