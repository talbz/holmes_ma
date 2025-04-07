import { useState, useEffect, useCallback, useRef } from 'react';

export const useWebSocket = ({ url, onStatusChange }) => {
  const [wsStatus, setWsStatus] = useState('disconnected');
  const [crawlStatus, setCrawlStatus] = useState({
    inProgress: false,
    currentClub: null,
    currentDay: null,
    progress: 0,
    clubsList: [],
    message: null,
    totalClubs: 0,
    currentClubIndex: null,
  });
  const [clubStatuses, setClubStatuses] = useState({});
  const wsRef = useRef(null);
  const reconnectTimeoutRef = useRef(null);
  const RECONNECT_DELAY = 2000;
  const shouldReconnectRef = useRef(true);

  // Core WebSocket connection logic
  useEffect(() => {
    // Connect to WebSocket
    const connectWebSocket = () => {
      if (wsRef.current && wsRef.current.readyState !== WebSocket.CLOSED) {
        return; // Already connected or connecting
      }

      console.log(`Connecting to WebSocket at ${url}...`);
      
      try {
        const ws = new WebSocket(url);
        wsRef.current = ws;

        ws.onopen = () => {
          console.log('WebSocket connection established');
          setWsStatus('connected');
          if (onStatusChange) onStatusChange('connected');
        };

        ws.onclose = (event) => {
          console.log(`WebSocket closed with code: ${event.code}, reason: ${event.reason}`);
          setWsStatus('disconnected');
          wsRef.current = null;
          
          // Attempt to reconnect if appropriate
          if (shouldReconnectRef.current) {
            console.log(`Reconnecting in ${RECONNECT_DELAY}ms...`);
            reconnectTimeoutRef.current = setTimeout(connectWebSocket, RECONNECT_DELAY);
          }
        };

        ws.onerror = (error) => {
          console.error('WebSocket error:', error);
          setWsStatus('error');
        };

        ws.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data);
            const { type, message, data: eventData, ...rest } = data;
            let isErrorState = false;

            switch (type) {
              case 'connection_established':
                setClubStatuses({});
                setCrawlStatus(prev => ({ ...prev, message: 'מחובר לשרת' }));
                break;

              case 'crawl_started':
                setClubStatuses({});
                setCrawlStatus(prev => ({
                  ...prev,
                  inProgress: true,
                  message: 'איסוף נתונים התחיל! זה יכול לקחת מספר דקות',
                  progress: 0,
                  currentClub: null,
                  currentDay: null,
                  clubsList: [],
                  totalClubs: 0,
                  currentClubIndex: null,
                }));
                break;

              case 'progress':
                setCrawlStatus(prev => ({
                  ...prev,
                  progress: rest.progress || 0,
                  message: message || 'בתהליך איסוף נתונים',
                }));
                break;

              case 'clubs_found':
                const initialStatuses = {};
                (eventData?.clubs || []).forEach(clubName => {
                  initialStatuses[clubName] = 'pending';
                });
                setClubStatuses(initialStatuses);
                console.log('WebSocket Hook: Initialized club statuses', initialStatuses);
                setCrawlStatus(prev => ({
                  ...prev,
                  clubsList: eventData?.clubs || [],
                  totalClubs: (eventData?.clubs || []).length,
                  message: `נמצאו ${(eventData?.clubs || []).length} סניפים`,
                }));
                break;

              case 'club_processing':
                const processingClub = eventData?.club_name;
                if (processingClub) {
                    setClubStatuses(prev => {
                        const newStatuses = { ...prev, [processingClub]: 'processing' };
                        console.log('WebSocket Hook: Club processing started', {
                            club: processingClub,
                            previousStatus: prev[processingClub],
                            newStatus: 'processing',
                            allStatuses: newStatuses,
                            rawMessage: event.data
                        });
                        return newStatuses;
                    });
                }
                setCrawlStatus(prev => ({
                  ...prev,
                  currentClub: eventData?.club_name,
                  currentClubIndex: eventData?.current,
                  message: `מעבד סניף: ${eventData?.club_name || ''}`,
                  progress: eventData?.progress_percent || prev.progress,
                }));
                break;

              case 'club_success':
                const successClub = eventData?.club_name;
                if (successClub) {
                    setClubStatuses(prev => {
                        // Force update the status regardless of previous state
                        const newStatuses = { ...prev };
                        newStatuses[successClub] = 'success';
                        console.log('WebSocket Hook: Club processing succeeded', {
                            club: successClub,
                            previousStatus: prev[successClub],
                            newStatus: 'success',
                            allStatuses: newStatuses,
                            rawMessage: event.data
                        });
                        return newStatuses;
                    });
                }
                break;

              case 'club_failed':
                const failedClub = eventData?.club_name;
                if (failedClub) {
                    setClubStatuses(prev => {
                        // Force update the status regardless of previous state
                        const newStatuses = { ...prev };
                        newStatuses[failedClub] = 'failed';
                        console.log('WebSocket Hook: Club processing failed', {
                            club: failedClub,
                            previousStatus: prev[failedClub],
                            newStatus: 'failed',
                            allStatuses: newStatuses,
                            rawMessage: event.data
                        });
                        return newStatuses;
                    });
                }
                break;

              case 'day_processing':
                setCrawlStatus(prev => ({
                  ...prev,
                  currentDay: rest.data?.day,
                  message: `מעבד יום: ${rest.data?.day || ''} בסניף ${prev.currentClub || ''}`,
                }));
                break;

              case 'classes_found':
                // Minor status update, doesn't change core progress state
                break;

              case 'warning':
              case 'error_screenshot': // Treat screenshot message as a warning/info
                // Just update the message, don't stop progress
                setCrawlStatus(prev => ({
                  ...prev,
                  message: `אזהרה: ${message || ''}`,
                }));
                break;

              case 'error':
                isErrorState = true;
                setCrawlStatus(prev => ({
                  ...prev,
                  inProgress: false,
                  message: `שגיאה קריטית: ${message || 'לא ידועה'}`,
                }));
                break;

              case 'crawl_failed':
                isErrorState = true;
                setCrawlStatus(prev => ({
                  ...prev,
                  inProgress: false,
                  message: message || 'תהליך איסוף הנתונים נכשל.',
                  currentClub: null,
                  currentDay: null
                }));
                break;

              case 'crawl_complete':
                if (!isErrorState) {
                  // Update any remaining processing clubs to success
                  setClubStatuses(prev => {
                    const newStatuses = { ...prev };
                    let updatedCount = 0;
                    Object.keys(newStatuses).forEach(club => {
                      if (newStatuses[club] === 'processing' || newStatuses[club] === 'pending') {
                        newStatuses[club] = 'success';
                        updatedCount++;
                        console.log('WebSocket Hook: Auto-updating club status on completion', {
                            club,
                            previousStatus: prev[club],
                            newStatus: 'success'
                        });
                      }
                    });
                    console.log('WebSocket Hook: Finalizing club statuses on completion', {
                        updatedCount,
                        allStatuses: newStatuses,
                        previousStatuses: prev,
                        rawMessage: event.data
                    });
                    return newStatuses;
                  });
                  
                  setCrawlStatus(prev => ({
                    ...prev,
                    inProgress: false,
                    message: message || 'איסוף הנתונים הסתיים בהצלחה',
                    progress: 100,
                    currentClub: null,
                    currentDay: null
                  }));
                }
                break;

              default:
                console.log('Unknown WebSocket message type:', type, data);
            }
          } catch (error) {
            console.error('Error parsing WebSocket message:', error, event.data);
          }
        };
      } catch (error) {
        console.error('Error creating WebSocket:', error);
        setWsStatus('error');
        
        if (shouldReconnectRef.current) {
          console.log(`Reconnecting in ${RECONNECT_DELAY}ms after error...`);
          reconnectTimeoutRef.current = setTimeout(connectWebSocket, RECONNECT_DELAY);
        }
      }
    };

    // Connect immediately
    connectWebSocket();

    // Cleanup on unmount
    return () => {
      shouldReconnectRef.current = false;
      
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
      
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, [url, onStatusChange]);

  // Simple message sender
  const sendMessage = useCallback((message) => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      try {
        wsRef.current.send(JSON.stringify(message));
        return true;
      } catch (error) {
        console.error('Error sending message:', error);
        return false;
      }
    }
    return false;
  }, []);

  return {
    wsStatus,
    crawlStatus,
    clubStatuses,
    sendMessage,
  };
}; 