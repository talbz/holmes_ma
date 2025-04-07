import { useState, useEffect, useCallback } from 'react';

/**
 * Hook for managing toast notifications
 * @returns {Object} Toast state and functions to control it
 */
export const useToast = () => {
  const [toasts, setToasts] = useState([]);
  
  const addToast = useCallback((message, type = 'info') => {
    const id = Date.now();
    setToasts(prev => [...prev, { id, message, type }]);
    
    // Auto-remove after 5 seconds
    setTimeout(() => {
      setToasts(prev => prev.filter(toast => toast.id !== id));
    }, 5000);
  }, []);

  const removeToast = useCallback((id) => {
    setToasts(prev => prev.filter(toast => toast.id !== id));
  }, []);
  
  // Listen for toast events from other components
  useEffect(() => {
    const handleToastEvent = (event) => {
      const { message, type } = event.detail;
      addToast(message, type);
    };
    
    window.addEventListener('toast', handleToastEvent);
    
    return () => {
      window.removeEventListener('toast', handleToastEvent);
    };
  }, [addToast]);

  return {
    toasts,
    addToast,
    removeToast
  };
}; 