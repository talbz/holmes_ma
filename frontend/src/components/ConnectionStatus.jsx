import React from 'react';
import PropTypes from 'prop-types';

export const ConnectionStatus = ({ status, reconnectInfo, onReconnect }) => {
  // Format connection status text and styles
  const getConnectionInfo = () => {
    switch (status) {
      case 'connected':
        return { class: 'connected', text: 'מחובר לשרת' };
      case 'connecting':
        return { class: 'connecting', text: 'מתחבר לשרת...' };
      case 'disconnected':
        return { 
          class: 'disconnected', 
          text: reconnectInfo?.countdown
            ? `מנותק (התחברות מחדש בעוד ${reconnectInfo.countdown} שניות)`
            : 'מנותק מהשרת'
        };
      case 'error':
        return { class: 'error', text: 'שגיאת חיבור' };
      default:
        return { class: 'unknown', text: 'סטטוס לא ידוע' };
    }
  };

  const connectionInfo = getConnectionInfo();

  return (
    <div className={`connection-status status-${connectionInfo.class}`}>
      <span className="status-text">{connectionInfo.text}</span>
      {status !== 'connected' && (
        <button 
          onClick={onReconnect} 
          className="reconnect-button"
          disabled={status === 'connecting'}
        >
          {status === 'connecting' ? 'מתחבר...' : 'התחבר מחדש'}
        </button>
      )}
    </div>
  );
};

ConnectionStatus.propTypes = {
  status: PropTypes.string.isRequired,
  reconnectInfo: PropTypes.shape({
    attemptCount: PropTypes.number,
    nextAttempt: PropTypes.number,
    countdown: PropTypes.number
  }),
  onReconnect: PropTypes.func.isRequired
}; 