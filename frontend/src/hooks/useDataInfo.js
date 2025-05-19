import { useQuery } from 'react-query';

/**
 * Hook to fetch crawl status information and available clubs
 * @returns {Object} Query result with crawl status info and clubs
 */
export const useCrawlStatus = () => {
  return useQuery(
    ['crawl-status'],
    async () => {
      const response = await fetch('http://localhost:8000/api/crawl-status');
      if (!response.ok) {
        throw new Error('Failed to fetch crawl status information');
      }
      const data = await response.json();
      
      // Calculate days since last crawl if we have a date
      let days_since_crawl = null;
      if (data.latest_crawl_date) {
        const lastCrawlDate = new Date(data.latest_crawl_date);
        const now = new Date();
        days_since_crawl = Math.floor((now - lastCrawlDate) / (1000 * 60 * 60 * 24));
      }
      
      // Return the data with additional calculated fields
      return {
        ...data,
        days_since_crawl,
        is_stale: days_since_crawl !== null && days_since_crawl > 7, // Consider data stale after 7 days
        has_data: data.latest_crawl_date !== null
      };
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