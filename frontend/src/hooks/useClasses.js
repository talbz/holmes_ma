import { useQuery } from 'react-query';
import axios from 'axios'; // Import axios
import qs from 'qs'; // Import qs

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
      
      // Clean the filters: remove empty arrays or null/undefined values
      const cleanedFilters = Object.entries(filters).reduce((acc, [key, value]) => {
          if (value !== null && value !== undefined) {
              if (Array.isArray(value) && value.length === 0) {
                  // Skip empty arrays
              } else if (typeof value === 'string' && value.trim() === '') {
                  // Skip empty strings
              } else {
                  // Map potentially incorrect keys (e.g., className -> class_name)
        const paramKey = key === 'className' ? 'class_name' : key;
                  acc[paramKey] = value;
              }
          }
          return acc;
      }, {});
      
      console.log("[useClasses Query Function] Cleaned filters for API:", cleanedFilters);

      // Use axios.get with the `params` option, which handles serialization correctly
      const url = `http://localhost:8080/classes`;
      try {
          const response = await axios.get(url, {
              params: cleanedFilters,
              // Use qs library for parameter serialization
              paramsSerializer: params => {
                  return qs.stringify(params, { arrayFormat: 'repeat' }); // Use 'repeat' for FastAPI compatibility
              }
          });
          console.log("[useClasses Query Function] Received data via axios:", response.data);
          return response.data;
      } catch (error) {
          console.error("[useClasses Query Function] Fetch failed via axios", error.response?.status, error.message);
          throw new Error(error.response?.data?.detail || 'Failed to fetch classes');
      }
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