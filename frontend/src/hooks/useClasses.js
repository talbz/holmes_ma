import { useQuery } from 'react-query';

/**
 * Hook to fetch classes from the API with filtering options
 * @param {Object} filters - Filter options for classes
 * @returns {Object} Query result with classes data and loading state
 */
export const useClasses = (filters = {}) => {
  // Log filters passed to the hook itself (might be stale)
  console.log("[useClasses Hook] Received filters prop:", filters);
  
  return useQuery(
    ['classes', filters], // Query key depends on filters
    async () => {
      // --- Log filters INSIDE the query function --- 
      console.log("[useClasses Query Function] Using filters:", filters); 
      // ---------------------------------------------
      
      const params = new URLSearchParams();
      
      Object.entries(filters).forEach(([key, value]) => {
        // Ensure only 'class_name' is used, not 'className'
        const paramKey = key === 'className' ? 'class_name' : key;

        if (value) {
          if (Array.isArray(value)) {
            // For arrays (like day_name_hebrew), append each value separately
            value.forEach(item => params.append(paramKey, item));
          } else {
            // For single values, append normally
            params.append(paramKey, value);
          }
        }
      });
      
      const url = `http://localhost:8080/classes?${params.toString()}`;
      console.log("[useClasses Query Function] Fetching URL:", url); // Log fetch URL
      const response = await fetch(url);
      
      if (!response.ok) {
        console.error("[useClasses Query Function] Fetch failed", response.status, response.statusText);
        throw new Error('Failed to fetch classes');
      }
      
      const data = await response.json();
      console.log("[useClasses Query Function] Received data", data); // Log received data
      return data;
    },
    {
      staleTime: 5 * 60 * 1000, // Consider data fresh for 5 minutes
      keepPreviousData: true, // Keep displaying old data while fetching new data
      refetchOnWindowFocus: false, // Don't refetch when window regains focus
      onError: (error) => {
        console.error('[useClasses Hook] Error fetching classes:', error);
      }
    }
  );
}; 