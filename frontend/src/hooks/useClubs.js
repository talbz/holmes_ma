import { useQuery } from 'react-query';

/**
 * Hook to fetch available clubs from the API
 * @returns {Object} Query result with clubs data and loading state
 */
export const useClubs = () => {
  return useQuery(
    ['clubs'], // Query key
    async () => {
      try {
        const response = await fetch('http://localhost:8000/api/clubs');
        
        if (!response.ok) {
          throw new Error('Failed to fetch clubs');
        }
        
        const data = await response.json();
        console.log("useClubs: Raw API response:", data);

        // Handle the updated API format with clubs_by_region
        if (data && typeof data === 'object') {
          // Handle new format with clubs_by_region array
          if (data.clubs_by_region && Array.isArray(data.clubs_by_region)) {
            const flattenedClubs = [];
            
            // Process each region
            data.clubs_by_region.forEach(regionData => {
              const region = regionData.region || "אחר";
              
              // Process clubs in this region
              if (regionData.clubs && Array.isArray(regionData.clubs)) {
                regionData.clubs.forEach(club => {
                  // Ensure each club has a valid structure
                  if (club) {
                    // If club is just a string (old format), create proper object
                    if (typeof club === 'string') {
                      flattenedClubs.push({
                        name: club,
                        region: region,
                        status: 'unknown',
                        url: '',
                        opening_hours: {}
                      });
                    } 
                    // If club is an object with name property (new format)
                    else if (typeof club === 'object' && club.name) {
                      flattenedClubs.push({
                        name: club.name,
                        short_name: club.short_name || club.name,
                        region: region,
                        status: club.status || 'unknown',
                        url: club.url || '',
                        opening_hours: club.opening_hours || {}
                      });
                    }
                    // Skip invalid club formats
                    else {
                      console.warn("useClubs: Skipping invalid club format:", club);
                    }
                  }
                });
              }
            });
            
            console.log("useClubs: Processed clubs data:", flattenedClubs);
            return flattenedClubs;
          } 
          // Fall back to old format handling if clubs_by_region is not present
          else if (data.clubs) {
            console.log("useClubs: Using legacy clubs format");
            return Array.isArray(data.clubs) ? data.clubs.map(club => {
              if (typeof club === 'string') {
                return { name: club, region: 'unknown', status: 'unknown', url: '', opening_hours: {} };
              } else {
                return { 
                  ...club, 
                  short_name: club.short_name || club.name,
                  opening_hours: club.opening_hours || {} 
                };
              }
            }) : [];
          }
        }
        
        console.warn("useClubs: Unexpected API response format:", data);
        return [];
      } catch (error) {
        console.error("useClubs: Error fetching clubs:", error);
        throw error;
      }
    },
    {
      staleTime: 5 * 60 * 1000, // 5 minutes
      refetchOnWindowFocus: false,
      onError: (error) => {
        console.error('Error fetching clubs:', error);
      }
    }
  );
};

/**
 * Hook to fetch clubs with their status from the last crawl
 * @returns {Object} Query result with clubs data including status and loading state
 */
export const useClubsWithStatus = () => {
  return useQuery(
    ['clubs-with-status'],
    async () => {
      const response = await fetch('http://localhost:8000/api/clubs-with-status');
      if (!response.ok) {
        throw new Error('Failed to fetch clubs with status');
      }
      const data = await response.json();
      return data.clubs || [];
    },
    {
      staleTime: 5 * 60 * 1000, // 5 minutes
      refetchOnWindowFocus: false,
    }
  );
}; 