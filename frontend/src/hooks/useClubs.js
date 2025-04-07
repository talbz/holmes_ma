import { useQuery } from 'react-query';

/**
 * Hook to fetch available clubs from the API
 * @returns {Object} Query result with clubs data and loading state
 */
export const useClubs = () => {
  return useQuery(
    ['clubs'], // Query key
    async () => {
      const response = await fetch('http://localhost:8080/clubs');
      
      if (!response.ok) {
        throw new Error('Failed to fetch clubs');
      }
      
      const data = await response.json();
      return data.clubs || [];
    },
    {
      staleTime: 10 * 60 * 1000, // Consider data fresh for 10 minutes
      refetchOnWindowFocus: false,
      onError: (error) => {
        console.error('Error fetching clubs:', error);
      }
    }
  );
}; 