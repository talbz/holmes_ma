import { useQuery } from 'react-query';

/**
 * Hook to fetch unique class names from the API
 */
export const useClassNames = () => {
  return useQuery(
    'classNames', 
    async () => {
      const url = `http://localhost:8000/api/class-names`;
      const response = await fetch(url);
      if (!response.ok) {
        throw new Error('Failed to fetch class names');
      }
      const data = await response.json();
      return data.class_names || []; // Ensure returning an array
    },
    {
      staleTime: Infinity, // Names don't change unless crawled
      refetchOnWindowFocus: false,
    }
  );
}; 