import { useQuery } from 'react-query';

/**
 * Hook to fetch crawl status information and available clubs
 * @returns {Object} Query result with crawl status info and clubs
 */
export const useCrawlStatus = () => {
  return useQuery(
    ['crawl-status'],
    async () => {
      const response = await fetch('http://localhost:8080/crawl-status');
      if (!response.ok) {
        throw new Error('Failed to fetch crawl status information');
      }
      return await response.json();
    },
    {
      staleTime: 60 * 1000, // 1 minute - keep relatively fresh
      refetchOnWindowFocus: true, // Refresh when window gains focus
      onError: (error) => {
        console.error('Error fetching crawl status:', error);
      }
    }
  );
};

/**
 * @deprecated Use useCrawlStatus instead
 * Legacy hook to maintain backward compatibility
 */
export const useDataInfo = () => {
  console.warn("useDataInfo is deprecated. Please use useCrawlStatus instead.");
  return useCrawlStatus();
}; 