import { useMutation } from 'react-query';
import { useToast } from './useToast'; // Assuming you have a toast hook

/**
 * Hook to trigger the retry failed crawl endpoint.
 */
export const useRetryCrawl = () => {
  const { addToast } = useToast();

  return useMutation(
    async (variables) => {
      // variables will contain { headless }
      const response = await fetch('http://localhost:8080/retry-failed-crawl', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(variables), // Send headless preference
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ status: 'Failed to parse error response' }));
        throw new Error(errorData?.status || 'Failed to start retry crawl');
      }
      
      return response.json(); // Return success status message
    },
    {
      onSuccess: (data) => {
        addToast(data?.status || 'Retry crawl started', 'info');
      },
      onError: (error) => {
        addToast(`Error starting retry crawl: ${error.message}`, 'error');
        console.error("Retry Crawl Error:", error);
      },
    }
  );
}; 