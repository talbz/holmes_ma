import { useMutation, useQueryClient } from 'react-query';

/**
 * Hook for starting the crawler
 * @returns {Object} Mutation result with start function and loading state
 */
export const useCrawler = () => {
  const queryClient = useQueryClient();
  
  return useMutation(
    async ( { headless = true } ) => {
      const response = await fetch('http://localhost:8080/start-crawl', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ headless: headless }),
      });
      
      if (!response.ok) {
        let errorDetails = 'Failed to start crawler';
        try {
           const errorData = await response.json();
           errorDetails = errorData.detail || errorDetails;
        } catch (parseError) {
           // Ignore if response body isn't JSON
        }
        throw new Error(errorDetails);
      }
      
      return response.json();
    },
    {
      onSuccess: (data) => {
        window.dispatchEvent(new CustomEvent('toast', { 
          detail: { message: data.status || 'איסוף נתונים התחיל!', type: 'success' } 
        }));
      },
      onError: (error) => {
        console.error('Error starting crawler:', error);
        window.dispatchEvent(new CustomEvent('toast', { 
          detail: { message: `שגיאה בהפעלת האיסוף: ${error.message}`, type: 'error' } 
        }));
      }
    }
  );
};

/**
 * Hook for stopping the crawler
 * @returns {Object} Mutation result with stop function and loading state
 */
export const useStopCrawler = () => {
  return useMutation(
    async () => {
      const response = await fetch('http://localhost:8080/stop-crawl', {
        method: 'POST',
      });
      
      if (!response.ok) {
        let errorDetails = 'Failed to send stop signal';
        try {
           const errorData = await response.json();
           errorDetails = errorData.detail || errorData.status || errorDetails;
        } catch (parseError) { /* Ignore */ }
        throw new Error(errorDetails);
      }
      
      return response.json();
    },
    {
      onSuccess: (data) => {
        window.dispatchEvent(new CustomEvent('toast', { 
          detail: { message: data.status || 'Stop signal sent!', type: 'info' } 
        }));
      },
      onError: (error) => {
        console.error('Error stopping crawler:', error);
        window.dispatchEvent(new CustomEvent('toast', { 
          detail: { message: `Error sending stop signal: ${error.message}`, type: 'error' } 
        }));
      }
    }
  );
}; 