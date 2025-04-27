import React, { useState, useCallback, useMemo } from 'react';
import { QueryClient, QueryClientProvider } from 'react-query';
import './styles/App.scss';
import { useWebSocket } from './hooks/useWebSocket';
import { useLocalStorage } from './hooks/useLocalStorage';
import { Toast } from './components/Toast';
import { ClubList } from './components/ClubList';
import { ClassList } from './components/ClassList';
import { DataFreshness } from './components/DataFreshness';
import { Filters } from './components/Filters';
import { useClasses } from './hooks/useClasses';
import { useClubs } from './hooks/useClubs';
import { ErrorBoundary } from './components/ErrorBoundary';
import { ConnectionStatus } from './components/ConnectionStatus';
import { CrawlerControls } from './components/CrawlerControls';
import { AppProvider } from './contexts/AppContext';

// Create a new QueryClient instance
const queryClient = new QueryClient();

// Hebrew days of the week for display
const HEBREW_DAYS = {
  'Sunday': 'ראשון',
  'Monday': 'שני',
  'Tuesday': 'שלישי',
  'Wednesday': 'רביעי',
  'Thursday': 'חמישי',
  'Friday': 'שישי',
  'Saturday': 'שבת'
};

// Main application content component
function AppContent() {
  // State hooks
  const [selectedClub, setSelectedClub] = useLocalStorage('selected-club', []);
  const [toasts, setToasts] = useState([]);
  const [dataInfo, setDataInfo] = useState({
    has_data: false,
    latest_file: null,
    latest_crawl_date: null,
    days_since_crawl: null,
    is_stale: true,
    clubs: [] // Initialize clubs array in dataInfo
  });
  const [filters, setFilters] = useLocalStorage('class-filters', {});
  
  // Data fetching hooks for classes and clubs
  const { 
    data: classesData, 
    isLoading: classesLoading, 
    error: classesError, 
    refetch: refetchClasses
  } = useClasses(filters);
  
  // Use the useClubs hook to get clubs data from the API
  const {
    data: clubsData,
    isLoading: clubsLoading,
    error: clubsError,
    refetch: refetchClubs
  } = useClubs();
  
  // New state for headless mode
  const [headlessMode, setHeadlessMode] = useState(false);
  
  // Define toast handling functions first to avoid reference errors
  const removeToast = useCallback((id) => {
    setToasts(prev => prev.filter(toast => toast.id !== id));
  }, []);
  
  const addToast = useCallback((message, type = 'info') => {
    const newToast = {
      id: Date.now(),
      message,
      type
    };
    setToasts(prev => [...prev, newToast]);
    
    // Auto-remove toast after 5 seconds
    setTimeout(() => {
      removeToast(newToast.id);
    }, 5000);
  }, [removeToast]); // Now depends on removeToast which is defined above
  
  // Send message through WebSocket - define early to avoid reference errors
  const {
    wsStatus,
    crawlStatus,
    clubStatuses,
    reconnectInfo,
    reconnect,
    sendMessage
  } = useWebSocket({
    url: 'ws://localhost:8080/ws',
    autoConnect: true,
    onStatusChange: useCallback((status, data) => {
      console.log(`App: WebSocket status change: ${status}`, data);
      
      // Handle data_info events 
      if (status === 'data_info' && data) {
        console.log('App: Received data_info response', data);
        
        // We don't need to process clubs data from WebSocket anymore
        // as we're using the clubs API directly now
        // Just update the other dataInfo properties
        const { clubs, ...otherData } = data;
        setDataInfo(prev => ({ ...prev, ...otherData }));
      } 
      // Handle crawl completion events
      else if (status === 'crawl_complete') {
        console.log('App: Received crawl_complete event', data);
        addToast('איסוף נתונים הסתיים בהצלחה', 'success');
        
        // Refresh data info to get updated last crawl date using the new endpoint
        sendMessage({ action: 'get_crawl_status' });
        
        // Refresh clubs data from API after successful crawl
        refetchClubs();
      }
      // Handle crawl error events
      else if (status === 'crawl_error') {
        console.log('App: Received crawl_error event', data);
        addToast(`שגיאה באיסוף נתונים: ${data?.message || 'שגיאה לא ידועה'}`, 'error');
      }
    }, [addToast, refetchClubs])
  });
  
  // Handle starting the crawl process - Uses sendMessage
  const handleStartCrawl = useCallback(() => {
    if (wsStatus !== 'connected') {
      addToast('לא מחובר לשרת. אנא המתן לחיבור או נסה להתחבר מחדש.', 'error');
      return;
    }
    console.log("App: Requesting start_crawl with headless mode:", headlessMode);
    
    try {
      // Send the headless mode parameter with the start_crawl action
      sendMessage({ 
        action: 'start_crawl',
        headless: headlessMode 
      });
      
      // Add toast notification that crawl was requested
      addToast('בקשת איסוף נתונים נשלחה', 'info');
    } catch (error) {
      console.error("Error sending start_crawl message:", error);
      addToast(`שגיאה בשליחת בקשת איסוף: ${error.message}`, 'error');
    }
  }, [wsStatus, sendMessage, addToast, headlessMode]);
  
  // Handle data refreshing - Uses handleStartCrawl
  const handleRefreshData = useCallback(() => {
    if (wsStatus !== 'connected') {
      addToast('לא מחובר לשרת. אנא המתן לחיבור או נסה להתחבר מחדש.', 'error');
      return;
    }
    console.log("App: Requesting data refresh (via start_crawl)");
    handleStartCrawl();
  }, [wsStatus, addToast, handleStartCrawl]);

  // Handle filter changes
  const handleFilterChange = useCallback((newFilters) => {
      console.log("App: Filters changed", newFilters);
      setFilters(newFilters);
  }, [setFilters]);

  // Process clubs data for display - Use the data from the useClubs hook
  const availableClubs = useMemo(() => {
    // Use the clubsData from the API hook instead of dataInfo.clubs
    if (clubsData && Array.isArray(clubsData)) {
      console.log("App: Using clubs data from API:", clubsData.length, "clubs");
      return clubsData;
    }
    
    console.warn("App: No clubs data available from API");
    return [];
  }, [clubsData]);
  
  // Handle stopping the crawl process
  const handleStopCrawl = useCallback(() => {
    if (wsStatus !== 'connected') {
      addToast('לא מחובר לשרת. אנא המתן לחיבור או נסה להתחבר מחדש.', 'error');
      return;
    }
    console.log("App: Requesting stop_crawl");
    
    try {
      sendMessage({ action: 'stop_crawl' });
      addToast('בקשת עצירת איסוף נשלחה', 'info');
    } catch (error) {
      console.error("Error sending stop_crawl message:", error);
      addToast(`שגיאה בשליחת בקשת עצירה: ${error.message}`, 'error');
    }
  }, [wsStatus, sendMessage, addToast]);
  
  // Handle headless mode toggle
  const handleHeadlessToggle = useCallback((e) => {
    setHeadlessMode(e.target.checked);
  }, []);
  
  return (
    <div className={`App App-${wsStatus}`}>
      <header className="App-header">
        <h1>לוח הזמנים של הולמס פלייס</h1>
        <ConnectionStatus 
          status={wsStatus} 
          reconnectInfo={reconnectInfo}
          onReconnect={reconnect}
        />
      </header>
      
      <main>
        {/* Data freshness component */}
        <DataFreshness 
          dataInfo={dataInfo}
          onStartCrawl={handleStartCrawl}
        />
        
        {/* Crawler controls component */}
        <CrawlerControls
          crawlStatus={crawlStatus}
          onStartCrawl={handleStartCrawl}
          onStopCrawl={handleStopCrawl}
          headlessMode={headlessMode}
          onHeadlessToggle={handleHeadlessToggle}
        />
        
        {/* Club selection */}
        <section className="clubs-section">
          <h2>סניפים</h2>
          <ClubList 
            availableClubs={availableClubs} // Pass the processed list from API
            selectedClub={selectedClub} 
            onSelectClub={setSelectedClub}
            clubStatuses={clubStatuses || {}} // Statuses for individual item styling
            dataInfo={dataInfo} // Pass for freshness indicator
            onRefreshData={handleRefreshData}
            isLoading={clubsLoading} // Pass loading state
            error={clubsError} // Pass error state
          />
        </section>
        
        {/* Filters Component */}
        <section className="filters-section">
           <h2>סינון שיעורים</h2>
           <Filters 
              filters={filters} 
              onFilterChange={handleFilterChange} 
              loading={classesLoading || crawlStatus?.inProgress} // Disable filters while loading/crawling
           />
        </section>
        
        {/* Class display */}
        <section className="classes-section">
          <h2>שיעורים</h2>
          <ClassList 
            classes={classesData?.classes || []} // Pass classes from useClasses
            regions={classesData?.regions_found || []} // Pass regions from useClasses
            isLoading={classesLoading} // Pass loading state
            error={classesError} // Pass error state
            clubStatuses={clubStatuses || {}}
            openingHours={classesData?.opening_hours || {}}
          />
        </section>
      </main>
      
      {/* Toast notifications */}
      <Toast toasts={toasts} onRemove={removeToast} />
    </div>
  );
}

// Main application wrapper
export function App() {
  return (
    <ErrorBoundary>
      <QueryClientProvider client={queryClient}>
        <AppProvider>
          <AppContent />
        </AppProvider>
      </QueryClientProvider>
    </ErrorBoundary>
  );
}
