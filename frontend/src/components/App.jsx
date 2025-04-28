import React, { useState, useEffect, useCallback } from 'react';
import Filters from './Filters';
import ClassList from './ClassList';
import ClubList from './ClubList';
import CrawlerStatus from './CrawlerStatus';
import CrawlerControls from './CrawlerControls';
import { ConnectionStatus } from './ConnectionStatus';
import useWebSocket from 'react-use-websocket';
import '../styles/App.scss';

const WS_URL = 'ws://localhost:8000/ws';

export const App = () => {
  const [selectedClubs, setSelectedClubs] = useState([]);
  const [filters, setFilters] = useState({});
  const [classes, setClasses] = useState([]);
  const [clubStatuses, setClubStatuses] = useState({});
  const [crawlStatus, setCrawlStatus] = useState(null);
  const [headlessMode, setHeadlessMode] = useState(false);
  const [dataInfo, setDataInfo] = useState(null);
  const [connectionStatus, setConnectionStatus] = useState('connecting');
  const [reconnectInfo, setReconnectInfo] = useState(null);

  // Enhanced WebSocket connection with better error handling and reconnection logic
  const { sendJsonMessage, lastJsonMessage, readyState } = useWebSocket(WS_URL, {
    onOpen: () => {
      console.log('WebSocket connection established');
      setConnectionStatus('connected');
      setReconnectInfo(null);
    },
    onClose: () => {
      console.log('WebSocket connection closed');
      setConnectionStatus('disconnected');
    },
    onError: (error) => {
      console.error('WebSocket error:', error);
      setConnectionStatus('error');
    },
    shouldReconnect: (closeEvent) => {
      // Don't reconnect if the server explicitly closed the connection
      if (closeEvent.code === 1000) return false;
      return true;
    },
    reconnectInterval: (attemptNumber) => {
      // Exponential backoff with a max of 10 seconds
      const backoff = Math.min(1000 * Math.pow(2, attemptNumber), 10000);
      setReconnectInfo({
        attemptCount: attemptNumber,
        nextAttempt: Date.now() + backoff,
        countdown: Math.ceil(backoff / 1000)
      });
      return backoff;
    },
    reconnectAttempts: 10
  });

  // Handle WebSocket messages
  useEffect(() => {
    if (lastJsonMessage) {
      const { type, data } = lastJsonMessage;
      
      switch (type) {
        case 'crawl_status':
          setCrawlStatus(data);
          break;
        case 'club_status':
          setClubStatuses(prev => ({ ...prev, ...data }));
          break;
        case 'data_info':
          setDataInfo(data);
          break;
        case 'error':
          console.error('WebSocket error message:', data);
          break;
      }
    }
  }, [lastJsonMessage]);

  // Update connection status based on WebSocket readyState
  useEffect(() => {
    switch (readyState) {
      case 0: // CONNECTING
        setConnectionStatus('connecting');
        break;
      case 1: // OPEN
        setConnectionStatus('connected');
        break;
      case 2: // CLOSING
        setConnectionStatus('disconnected');
        break;
      case 3: // CLOSED
        setConnectionStatus('disconnected');
        break;
    }
  }, [readyState]);

  // Handle reconnection attempts
  useEffect(() => {
    if (reconnectInfo) {
      const interval = setInterval(() => {
        const now = Date.now();
        const countdown = Math.ceil((reconnectInfo.nextAttempt - now) / 1000);
        if (countdown <= 0) {
          setReconnectInfo(null);
          clearInterval(interval);
        } else {
          setReconnectInfo(prev => ({ ...prev, countdown }));
        }
      }, 1000);
      return () => clearInterval(interval);
    }
  }, [reconnectInfo]);

  const handleReconnect = useCallback(() => {
    // Force a reconnection by closing and reopening the WebSocket
    if (readyState === 3) { // CLOSED
      window.location.reload();
    }
  }, [readyState]);

  // ... rest of the component code ...

  return (
    <div className="app">
      <ConnectionStatus 
        status={connectionStatus}
        reconnectInfo={reconnectInfo}
        onReconnect={handleReconnect}
      />
      {/* ... rest of the JSX ... */}
    </div>
  );
}; 