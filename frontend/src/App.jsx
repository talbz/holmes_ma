import { useState, useEffect, useCallback, useMemo } from 'react';
import { QueryClient, QueryClientProvider, useQuery } from 'react-query';
import classNames from 'classnames';

// Components
import { Toast } from './components/Toast';
import { CrawlerStatus } from './components/CrawlerStatus';
import { ClassList } from './components/ClassList';
import { ClubList } from './components/ClubList';
import { Filters } from './components/Filters';

// Hooks
import { useWebSocket } from './hooks/useWebSocket';
import { useLocalStorage } from './hooks/useLocalStorage';
import { useClasses } from './hooks/useClasses';
import { useClubs } from './hooks/useClubs';
import { useCrawler, useStopCrawler } from './hooks/useCrawler';
import { useRetryCrawl } from './hooks/useRetryCrawl';
import { useToast } from './hooks/useToast';

// Styles
import './styles/main.scss';

// Create a client
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
      staleTime: 300000, // 5 minutes
    },
  },
});

// Define HEBREW_DAYS if needed here or import from Filters if possible
const HEBREW_DAYS = ["ראשון", "שני", "שלישי", "רביעי", "חמישי", "שישי", "שבת"];

const AppContent = () => {
  // Local state
  const [filters, setFilters] = useLocalStorage('holmesFilters', {
    class_name: [],
    instructor: [],
    day_name_hebrew: HEBREW_DAYS,
    club: [],
  });

  console.log("AppContent: filters state:", filters);
  
  const [showHeadless, setShowHeadless] = useState(false); // Default to NOT headless (show window)
  
  // Hooks
  const { toasts, addToast, removeToast } = useToast();
  
  // Memoize the onStatusChange callback
  const handleWsStatusChange = useCallback((status) => {
    console.log(`WebSocket status changed to: ${status}`);
    // Only show toast for initial connection
    if (status === 'connected') {
      addToast('WebSocket connection established', 'success');
    }
  }, [addToast]); // Dependency: addToast

  // WebSocket connection and status handling
  const { 
    wsStatus, 
    crawlStatus, 
    clubStatuses,
    sendMessage 
  } = useWebSocket({
    url: 'ws://localhost:8080/ws',
    onStatusChange: handleWsStatusChange, // Use the memoized callback
  });

  // Data fetching with React Query
  const { 
    data: classesData,
    isLoading: classesLoading, 
    isError: classesError,
    refetch: refetchClasses
  } = useClasses(filters);
  const classes = classesData?.classes || [];
  const regions = classesData?.regions_found || [];

  // Club data
  const {
    data: availableClubs = [],
    isLoading: clubsLoading
  } = useClubs();

  // Start crawl mutation
  const { mutate: startCrawl, isLoading: startCrawlLoading } = useCrawler();
  // Stop crawl mutation
  const { mutate: stopCrawl, isLoading: stopCrawlLoading } = useStopCrawler();
  const { mutate: retryCrawl, isLoading: retryCrawlLoading } = useRetryCrawl();

  // Filter handling
  const handleFilterChange = useCallback((name, value) => {
    console.log(`AppContent: handleFilterChange received - Name: ${name}, Value:`, value);
    setFilters(prev => {
      const newState = { ...prev, [name]: value };
      console.log(`AppContent: setFilters updating to:`, newState);
      // React Query will trigger fetch automatically because the 'filters' object reference changes
      return newState;
    });
  }, [setFilters]);

  // Crawl handling
  const handleStartCrawl = useCallback(() => {
    startCrawl({ headless: showHeadless });
  }, [startCrawl, showHeadless]);

  // Stop handler
  const handleStopCrawl = useCallback(() => {
    stopCrawl();
  }, [stopCrawl]);

  // Retry handler
  const handleRetryFailed = useCallback(() => {
     retryCrawl({ headless: showHeadless });
  }, [retryCrawl, showHeadless]);

  // Club selection handling
  const handleClubSelect = useCallback((clubName) => {
    handleFilterChange('club', clubName);
    refetchClasses();
  }, [handleFilterChange, refetchClasses]);

  // Effect to refresh classes when crawl completes
  useEffect(() => {
    if (crawlStatus.message && crawlStatus.message.includes('הסתיים')) {
      refetchClasses();
    }
  }, [crawlStatus.message, refetchClasses]);

  // App class based on WebSocket status
  const appClass = useMemo(() => {
    return classNames('App', {
      'App-crawling': crawlStatus.inProgress,
      'App-disconnected': wsStatus !== 'connected'
    });
  }, [wsStatus, crawlStatus.inProgress]);

  // Which clubs to display - either from WebSocket or from API
  const displayClubs = useMemo(() => {
    if (crawlStatus.clubsList && crawlStatus.clubsList.length > 0) {
      return crawlStatus.clubsList;
    }
    return availableClubs;
  }, [crawlStatus.clubsList, availableClubs]);

  // --- Add log before return --- 
  console.log("AppContent rendering with:", { 
      filters, 
      classesLoading, 
      classesError, 
      classesCount: classes.length, 
      regionCount: regions.length 
  });
  // -----------------------------

  return (
    <div className={appClass}>
      <header className="App-header">
        <h1>מערכת שעות הולמס פלייס</h1>
        
        {/* Connection status indicator */}
        <div className="connection-status">
          {wsStatus === 'connected' && <span className="status-connected">מחובר</span>}
          {wsStatus === 'connecting' && <span>מתחבר...</span>}
          {wsStatus === 'disconnected' && <span className="status-disconnected">מנותק</span>}
          {wsStatus === 'error' && <span className="status-error">שגיאת חיבור</span>}
        </div>
      </header>

      <div className="controls">
        <div className="crawl-controls">
          {/* Start Button */}
          <button 
            className="crawl-button start-button"
            onClick={handleStartCrawl}
            disabled={crawlStatus.inProgress || startCrawlLoading || stopCrawlLoading || retryCrawlLoading || wsStatus !== 'connected'}
          >
            {startCrawlLoading ? 'מתחיל...' : (crawlStatus.inProgress ? 'איסוף בתהליך...' : 'התחל איסוף נתונים')}
          </button>

          {/* Retry Button - Show only when NOT crawling */}
          {!crawlStatus.inProgress && (
              <button 
                className="crawl-button retry-button"
                onClick={handleRetryFailed}
                disabled={startCrawlLoading || stopCrawlLoading || retryCrawlLoading || wsStatus !== 'connected'}
                title="נסה לאסוף נתונים רק מסניפים שנכשלו בפעם הקודמת"
              >
                {retryCrawlLoading ? 'מנסה שוב...' : 'נסה שוב כשלונות'}
              </button>
          )}
          
          {/* Stop Button - Show only when crawl IS in progress */}
          {crawlStatus.inProgress && (
            <button 
              className="crawl-button stop-button"
              onClick={handleStopCrawl}
              disabled={stopCrawlLoading}
            >
              {stopCrawlLoading ? 'עוצר...' : 'עצור איסוף'}
            </button>
          )}

          {/* Headless Toggle - Disable if already crawling */}
          <div className="headless-toggle">
            {/* Use label as the switch container */}
            <label className="toggle-switch">
              <input 
                type="checkbox" 
                checked={!showHeadless} // Input checked means headless=TRUE
                onChange={(e) => setShowHeadless(!e.target.checked)} // Invert logic: checked = headless
                disabled={crawlStatus.inProgress || startCrawlLoading || stopCrawlLoading}
              />
              <span className="slider round"></span> {/* The visual slider */}
            </label>
            <span>Show Browser Window</span> {/* Simple text label beside switch */}
          </div>
        </div>

        {/* Show crawler status when crawling is in progress OR if there's a final status message */}
        {(crawlStatus.inProgress || crawlStatus.message) && (
          <CrawlerStatus 
            status={crawlStatus} 
            isError={crawlStatus.message?.includes('נכשל') || crawlStatus.message?.includes('שגיאה')}
          />
        )}

        {/* Show clubs list when clubs are available */}
        {displayClubs && displayClubs.length > 0 && (
          (() => { // Immediately invoked function expression for logging
            console.log("AppContent rendering ClubList with statuses:", clubStatuses);
            return (
              <ClubList 
                clubs={displayClubs} 
                selectedClub={filters.club}
                onSelectClub={handleClubSelect}
                clubStatuses={clubStatuses} 
              />
            );
          })()
        )}

        {/* Filters */}
        <Filters 
          filters={filters}
          onFilterChange={handleFilterChange}
          loading={classesLoading}
        />
      </div>

      {/* Classes list */}
      <div className="classes-container">
        <h2>שיעורים</h2>
        
        {classesLoading ? (
          <div className="loading-message">טוען שיעורים...</div>
        ) : classesError ? (
          <div className="error-message">שגיאה בטעינת השיעורים</div>
        ) : classes && classes.length > 0 ? (
          <ClassList classes={classes} regions={regions} />
        ) : (
          // Check if filters are applied before showing "no results"
          Object.values(filters).some(val => Array.isArray(val) ? val.length > 0 : !!val) ? 
             <div className="empty-message">לא נמצאו שיעורים מתאימים לסינון</div>
           : <div className="empty-message">התחל סינון או איסוף נתונים...</div>
        )}
      </div>

      {/* Toast notifications */}
      <div className="toast-container">
        {toasts.map(toast => (
          <Toast
            key={toast.id}
            type={toast.type}
            message={toast.message}
            onClose={() => removeToast(toast.id)}
          />
        ))}
      </div>
    </div>
  );
};

const App = () => {
  return (
    <QueryClientProvider client={queryClient}>
      <AppContent />
    </QueryClientProvider>
  );
};

export default App; 