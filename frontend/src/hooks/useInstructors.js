import { useQuery } from 'react-query';

/**
 * Hook to fetch unique instructor names from the API
 */
export const useInstructors = () => {
  return useQuery(
    'instructors', 
    async () => {
      const url = `http://localhost:8000/api/instructors`;
      const response = await fetch(url);
      if (!response.ok) {
        throw new Error('Failed to fetch instructors');
      }
      const data = await response.json();
      return data.instructors || []; // Ensure returning an array
    },
    {
      staleTime: Infinity, // Names don't change unless crawled
      refetchOnWindowFocus: false,
    }
  );
}; 