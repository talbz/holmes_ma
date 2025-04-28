import React, { createContext, useContext, useState, useCallback, useMemo } from 'react';
import PropTypes from 'prop-types';

// Create the context
const AppContext = createContext();

// Custom hook to use the AppContext
export const useAppContext = () => {
  const context = useContext(AppContext);
  if (!context) {
    throw new Error('useAppContext must be used within an AppProvider');
  }
  return context;
};

// Hebrew day names for i18n
export const HEBREW_DAYS = {
  'Sunday': 'ראשון',
  'Monday': 'שני',
  'Tuesday': 'שלישי',
  'Wednesday': 'רביעי',
  'Thursday': 'חמישי',
  'Friday': 'שישי',
  'Saturday': 'שבת'
};

/**
 * AppProvider component that manages global application state
 */
export const AppProvider = ({ children }) => {
  // Debug mode for development
  const [debugMode, setDebugMode] = useState(false);
  
  // Global app settings
  const [settings, setSettings] = useState({
    autoRefreshEnabled: false,
    autoRefreshInterval: 30, // minutes
    darkMode: false
  });

  // Update settings handler
  const updateSettings = useCallback((newSettings) => {
    setSettings(prevSettings => ({
      ...prevSettings,
      ...newSettings
    }));
  }, []);

  // Toggle debug mode
  const toggleDebugMode = useCallback(() => {
    setDebugMode(prev => !prev);
  }, []);

  // Memoize context value to prevent unnecessary re-renders
  const contextValue = useMemo(() => ({
    debugMode,
    toggleDebugMode,
    settings,
    updateSettings,
    HEBREW_DAYS
  }), [debugMode, toggleDebugMode, settings, updateSettings]);

  return (
    <AppContext.Provider value={contextValue}>
      {children}
    </AppContext.Provider>
  );
};

AppProvider.propTypes = {
  children: PropTypes.node.isRequired
}; 