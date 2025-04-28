import { useState, useEffect, useCallback, useRef } from 'react';

export const useWebSocket = ({ url, onStatusChange, autoConnect = false }) => {
  // Keep a ref to the onStatusChange callback so we don't re-run effects on each render
  const onStatusChangeRef = useRef(onStatusChange);
  useEffect(() => {
    onStatusChangeRef.current = onStatusChange;
  }, [onStatusChange]);

  // Initialize state with default values first
  const [wsStatus, setWsStatus] = useState('disconnected');
  const [reconnectInfo, setReconnectInfo] = useState({
    attemptCount: 0,
    nextAttempt: null,
    countdown: null,
  });
  const [crawlStatus, setCrawlStatus] = useState(() => {
    // Try to restore crawl status from sessionStorage
    try {
      const savedStatus = sessionStorage.getItem('crawlStatus');
      if (savedStatus) {
        const parsed = JSON.parse(savedStatus);
        // Only restore if not in progress (to avoid stuck UIs)
        if (!parsed.inProgress) {
          return parsed;
        }
      }
    } catch (e) {
      console.error("Error restoring crawl status:", e);
    }
    
    // Default status if nothing in storage
    return {
      inProgress: false,
      currentClub: null,
      currentDay: null,
      progress: 0,
      clubsList: [],
      message: null,
      totalClubs: 0,
      currentClubIndex: null,
      lastCompleted: null,
      processedClubs: 0
    };
  });
  
  const [clubStatuses, setClubStatuses] = useState({});
  
  // Save significant crawl status changes to sessionStorage
  useEffect(() => {
    // Only save non-trivial status updates
    if (crawlStatus && (crawlStatus.inProgress || crawlStatus.lastCompleted)) {
      try {
        sessionStorage.setItem('crawlStatus', JSON.stringify(crawlStatus));
      } catch (e) {
        console.error("Error saving crawl status:", e);
      }
    }
  }, [crawlStatus]);
  
  // Create refs before any conditional logic
  const wsRef = useRef(null);
  const reconnectTimeoutRef = useRef(null);
  const countdownIntervalRef = useRef(null);
  const shouldReconnectRef = useRef(true);
  const disconnectedSinceRef = useRef(null);
  
  // Clear crawl status after successful completion
  const clearCompletedStatus = useCallback(() => {
    setCrawlStatus(prev => {
      // If the crawl is complete (not in progress and has lastCompleted),
      // clear it after a delay
      if (!prev.inProgress && prev.lastCompleted) {
        return {
          ...prev,
          lastCompleted: null,
          message: null,
          currentClub: null,
          currentDay: null
        };
      }
      return prev;
    });
  }, []);
  
  // Use a timer to clear the completion status after a delay
  useEffect(() => {
    if (crawlStatus?.lastCompleted && !crawlStatus.inProgress) {
      const timer = setTimeout(clearCompletedStatus, 10000); // 10 seconds
      return () => clearTimeout(timer);
    }
  }, [crawlStatus?.lastCompleted, crawlStatus?.inProgress, clearCompletedStatus]);
  
  // Reconnection strategy constants
  const INITIAL_RECONNECT_DELAY = 5000; // 5 seconds
  const MEDIUM_RECONNECT_DELAY = 60000; // 1 minute
  const LONG_RECONNECT_DELAY = 300000; // 5 minutes
  const MEDIUM_THRESHOLD = 5 * 60 * 1000; // 5 minutes in ms
  const LONG_THRESHOLD = 10 * 60 * 1000; // 10 minutes in ms

  // Determine reconnect delay based on total disconnected time
  const getReconnectDelay = useCallback((attemptCount, disconnectedSince) => {
    if (!disconnectedSince) return INITIAL_RECONNECT_DELAY;
    
    const disconnectedTime = Date.now() - disconnectedSince;
    
    if (disconnectedTime > LONG_THRESHOLD) {
      return LONG_RECONNECT_DELAY;
    } else if (disconnectedTime > MEDIUM_THRESHOLD) {
      return MEDIUM_RECONNECT_DELAY;
    } else {
      return INITIAL_RECONNECT_DELAY;
    }
  }, []);

  // Setup countdown timer for reconnection
  const setupCountdown = useCallback((timeToNextAttempt) => {
    // Clear any existing interval
    if (countdownIntervalRef.current) {
      clearInterval(countdownIntervalRef.current);
    }
    
    // Calculate end time
    const endTime = Date.now() + timeToNextAttempt;
    
    // Update countdown immediately
    setReconnectInfo(prev => ({
      ...prev,
      countdown: Math.ceil(timeToNextAttempt / 1000)
    }));
    
    // Setup interval to update countdown
    countdownIntervalRef.current = setInterval(() => {
      const remaining = Math.max(0, endTime - Date.now());
      const seconds = Math.ceil(remaining / 1000);
      
      setReconnectInfo(prev => ({
        ...prev,
        countdown: seconds
      }));
      
      // Clear interval when countdown reaches 0
      if (seconds <= 0 && countdownIntervalRef.current) {
        clearInterval(countdownIntervalRef.current);
        countdownIntervalRef.current = null;
      }
    }, 1000);
  }, []);
  
  // Handle websocket messages
  const handleMessage = useCallback((event) => {
    try {
      const data = JSON.parse(event.data);
      console.log('WebSocket received:', data);
      
      // Handle different message types
      if (data.type === 'connection_established') {
        setWsStatus('connected');
        
        // Reset reconnect info when successfully connected
        setReconnectInfo({
          attemptCount: 0,
          nextAttempt: null,
          countdown: null,
        });
        
        // Trigger callback if provided
        if (onStatusChangeRef.current) {
          onStatusChangeRef.current('connected', data);
        }
        
        // Auto-request crawl_status when connected
        if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
          wsRef.current.send(JSON.stringify({ action: 'get_crawl_status' }));
        }
      } 
      else if (data.type === 'crawler_status') {
        // Update crawl status from websocket updates
        setCrawlStatus(prevStatus => {
          const newStatus = {
            ...prevStatus,
            inProgress: data.data.in_progress,
            currentClub: data.data.current_club || prevStatus.currentClub,
            currentDay: data.data.current_day || prevStatus.currentDay,
            message: data.data.message || prevStatus.message,
            progress: data.data.progress !== undefined ? data.data.progress : prevStatus.progress,
            totalClubs: data.data.total_clubs || prevStatus.totalClubs,
            currentClubIndex: data.data.current_club_index !== undefined ? 
                             data.data.current_club_index : prevStatus.currentClubIndex
          };

          // If status changed from in-progress to completed
          if (prevStatus.inProgress && !newStatus.inProgress) {
            newStatus.lastCompleted = new Date().toISOString();
            newStatus.processedClubs = newStatus.totalClubs || prevStatus.processedClubs;
            
            // Notify about completion
            if (onStatusChangeRef.current) {
              onStatusChangeRef.current('crawl_complete', newStatus);
            }
          }
          
          return newStatus;
        });
      }
      else if (data.type === 'club_status') {
        // Update individual club status
        setClubStatuses(prev => ({
          ...prev,
          [data.data.name]: {
            status: data.data.status,
            message: data.data.message,
            timestamp: data.timestamp
          }
        }));
      }
      else if (data.type === 'data_info' || data.type === 'crawl_status') {
        // Handle both data_info (legacy) and crawl_status (new) message types
        // Forward to callback
        if (onStatusChangeRef.current) {
          onStatusChangeRef.current('data_info', data.data);
        }
      }
      else if (data.type === 'crawl_started') {
        // Update UI to show crawl is starting
        setCrawlStatus(prev => ({
          ...prev,
          inProgress: true,
          message: 'מתחיל איסוף נתונים...',
          progress: 0,
          lastCompleted: null
        }));
      }
      else if (data.type === 'crawl_stopped' || data.type === 'crawl_complete') {
        // Update UI to show crawl is stopped
        setCrawlStatus(prev => ({
          ...prev,
          inProgress: false,
          message: data.type === 'crawl_stopped' ? 'איסוף נתונים הופסק.' : 'איסוף נתונים הסתיים בהצלחה!',
          lastCompleted: new Date().toISOString()
        }));
        
        // Notify via callback
        if (onStatusChangeRef.current) {
          onStatusChangeRef.current(data.type === 'crawl_stopped' ? 'crawl_stopped' : 'crawl_complete', data);
        }
      }
      else if (data.type === 'crawl_error') {
        // Handle crawl errors
        setCrawlStatus(prev => ({
          ...prev,
          inProgress: false,
          message: `שגיאה: ${data.message || 'אירעה שגיאה באיסוף נתונים'}`,
          lastCompleted: new Date().toISOString()
        }));
        
        // Notify via callback
        if (onStatusChangeRef.current) {
          onStatusChangeRef.current('crawl_error', data);
        }
      }
      else if (data.type === 'error') {
        console.error('WebSocket error message:', data);
        
        // Notify via callback
        if (onStatusChangeRef.current) {
          onStatusChangeRef.current('error', data);
        }
      }
    } catch (e) {
      console.error('Error parsing WebSocket message:', e);
    }
  }, []);
  
  // Connect to websocket
  const connect = useCallback(() => {
    // Don't try to connect if we already have a connection
    if (wsRef.current && (wsRef.current.readyState === WebSocket.OPEN || 
                           wsRef.current.readyState === WebSocket.CONNECTING)) {
      console.log('WebSocket already connected or connecting');
      return;
    }
    
    try {
      console.log(`Connecting to WebSocket: ${url}`);
      setWsStatus('connecting');
      
      // Create new WebSocket connection
      const ws = new WebSocket(url);
      wsRef.current = ws;
      
      // Setup event listeners
      ws.onopen = () => {
        console.log('WebSocket connection opened');
        disconnectedSinceRef.current = null;
        setWsStatus('connected');
      };
      
      ws.onmessage = handleMessage;
      
      ws.onerror = (error) => {
        console.error('WebSocket error:', error);
        setWsStatus('error');
        
        // Notify via callback
        if (onStatusChangeRef.current) {
          onStatusChangeRef.current('error', { error });
        }
      };
      
      ws.onclose = (event) => {
        console.log(`WebSocket closed: ${event.code} ${event.reason}`);
        wsRef.current = null;
        setWsStatus('disconnected');
        
        // Set disconnected timestamp if not already set
        if (!disconnectedSinceRef.current) {
          disconnectedSinceRef.current = Date.now();
        }
        
        // Notify via callback
        if (onStatusChangeRef.current) {
          onStatusChangeRef.current('disconnected', { code: event.code, reason: event.reason });
        }
        
        // Auto-reconnect if enabled
        if (shouldReconnectRef.current) {
          const attemptCount = (reconnectInfo.attemptCount || 0) + 1;
          const delay = getReconnectDelay(attemptCount, disconnectedSinceRef.current);
          
          console.log(`Scheduling reconnect (attempt ${attemptCount}) in ${delay}ms`);
          
          // Update reconnect info
          setReconnectInfo({
            attemptCount,
            nextAttempt: Date.now() + delay,
            countdown: Math.ceil(delay / 1000)
          });
          
          // Setup countdown
          setupCountdown(delay);
          
          // Schedule reconnect
          reconnectTimeoutRef.current = setTimeout(() => {
            connect();
          }, delay);
        }
      };
    } catch (error) {
      console.error('Error creating WebSocket:', error);
      setWsStatus('error');
    }
  }, [url, reconnectInfo.attemptCount, getReconnectDelay, setupCountdown, handleMessage]);
  
  // Send message through WebSocket
  const sendMessage = useCallback((message) => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      const messageString = typeof message === 'string' ? message : JSON.stringify(message);
      wsRef.current.send(messageString);
      return true;
    } else {
      console.error('Cannot send message, WebSocket is not connected');
      return false;
    }
  }, []);
  
  // Manually reconnect (user-initiated)
  const reconnect = useCallback(() => {
    // Clear any pending reconnect
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }
    
    // Clear countdown interval
    if (countdownIntervalRef.current) {
      clearInterval(countdownIntervalRef.current);
      countdownIntervalRef.current = null;
    }
    
    // Reset reconnect info
    setReconnectInfo({
      attemptCount: 0,
      nextAttempt: null,
      countdown: null
    });
    
    // Close existing connection if any
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
    
    // Connect again
    connect();
  }, [connect]);
  
  // Clean up on unmount
  useEffect(() => {
    // Setup auto-connect if enabled
    if (autoConnect) {
      connect();
    }
    
    // Cleanup function
    return () => {
      // Mark that we should not auto-reconnect
      shouldReconnectRef.current = false;
      
      // Clear timeouts and intervals
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
      
      if (countdownIntervalRef.current) {
        clearInterval(countdownIntervalRef.current);
      }
      
      // Close WebSocket connection
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, [connect, autoConnect]);
  
  return {
    wsStatus,
    crawlStatus,
    clubStatuses,
    reconnectInfo,
    reconnect,
    sendMessage
  };
}; 