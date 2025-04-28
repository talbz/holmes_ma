import React, { useState, useMemo, useCallback, memo } from 'react';
import PropTypes from 'prop-types';
import { MdCheckBoxOutlineBlank, MdCheckBox } from 'react-icons/md';
import { TbAlertTriangle } from 'react-icons/tb';
import { RiTimeFill } from 'react-icons/ri';
import classNames from 'classnames';
import { formatDistanceToNow } from 'date-fns';
import { he } from 'date-fns/locale';
import '../styles/ClubList.scss';

// REMOVE the frontend helper function
/*
const getClubRegion = (clubName) => { ... };
*/

export const ClubList = memo(({ 
  availableClubs, // Now expects format: [{ name, short_name, status, url, region, opening_hours }, ...]
  selectedClub, 
  onSelectClub, 
  clubStatuses, 
  dataInfo, 
  onRefreshData 
}) => {
  console.log('Received clubs data:', availableClubs); // Debug log
  
  // Calculate the number of selected clubs
  const selectedCount = Array.isArray(selectedClub) 
    ? selectedClub.length 
    : (selectedClub ? 1 : 0);
  
  // Data freshness information
  const dataAge = dataInfo?.days_since_crawl ?? null;
  const isDataStale = dataAge === null || dataAge > 2 || !dataInfo?.latest_crawl_date; // Stale if unknown, > 48 hours, or missing date
  const isPartialData = dataInfo?.is_complete_crawl === false;
  
  // Get crawl metadata if available
  const crawlWasStopped = dataInfo?.crawl_metadata?.was_stopped_early;
  const criticalErrorOccurred = dataInfo?.crawl_metadata?.critical_error_occurred;
  
  // Get reason for partial data
  const getPartialReason = () => {
    if (crawlWasStopped) {
      return "הנתונים לא מושלמים כי תהליך האיסוף הופסק באמצע";
    } else if (criticalErrorOccurred) {
      return "הנתונים לא מושלמים בגלל שגיאה קריטית בתהליך האיסוף";
    } else {
      return "הנתונים חלקיים בלבד";
    }
  };
  
  // Memoize the list of clubs to be used for selection logic (just names)
  const allClubNamesForSelection = useMemo(() => {
    // Use names from availableClubs prop
    const clubNames = new Set(availableClubs.map(club => club.name));
    // Add any clubs from clubStatuses that aren't in the availableClubs list
    if (clubStatuses) {
      Object.keys(clubStatuses).forEach(clubName => clubNames.add(clubName));
    }
    return Array.from(clubNames);
  }, [availableClubs, clubStatuses]);
  
  // Group clubs by area for display - USE REGION FROM PROP
  const clubsByArea = useMemo(() => {
    console.log("ClubList: Grouping clubs by area using provided region. availableClubs:", availableClubs);
    if (!Array.isArray(availableClubs) || availableClubs.length === 0) {
        return {}; // Return empty if no clubs
    }
    
    // Normalize region names to avoid "unknown" category
    const normalizeRegion = (region) => {
      if (!region || region === "unknown" || region.toLowerCase() === "unknown") {
        return "אחר"; // Default all missing/unknown regions to "אחר" (Other)
      }
      return region;
    };
    
    const grouped = {};
    availableClubs.forEach(club => { 
      // Skip clubs without a name or with null value
      if (!club || !club.name) {
        console.warn("ClubList: Skipping club with missing name:", club);
        return;
      }
      
      // Normalize the region
      const region = normalizeRegion(club.region);
      
      if (!grouped[region]) {
        grouped[region] = [];
      }
      grouped[region].push(club); // Store the whole club object
    });
    
    // Sort clubs within each region alphabetically by name
    Object.keys(grouped).forEach(region => {
      grouped[region].sort((a, b) => {
        // Defensive check for name properties
        const nameA = a?.name || '';
        const nameB = b?.name || '';
        return nameA.localeCompare(nameB);
      });
    });
    
    console.log("ClubList: Grouped clubs result:", grouped);
    return grouped;
  }, [availableClubs]); // Depend only on availableClubs

  // --- Action Handlers --- 
  const handleSelectArea = useCallback((areaClubs) => {
    const clubNamesToAdd = areaClubs
      .map(club => club.name)
      .filter(name => clubStatuses[name] !== 'failed' && 
             availableClubs.find(c => c.name === name)?.status !== 'failed');
    
    onSelectClub(prevSelected => {
      const currentSelected = Array.isArray(prevSelected) ? prevSelected : (prevSelected ? [prevSelected] : []);
      const newSelected = new Set([...currentSelected, ...clubNamesToAdd]);
      return Array.from(newSelected);
    });
  }, [onSelectClub, clubStatuses, availableClubs]);

  const handleClearArea = useCallback((areaClubs) => {
    const clubNamesToClear = areaClubs.map(club => club.name);
    onSelectClub(prevSelected => {
        const currentSelected = Array.isArray(prevSelected) ? prevSelected : (prevSelected ? [prevSelected] : []);
        return currentSelected.filter(name => !clubNamesToClear.includes(name));
    });
  }, [onSelectClub]);

  const handleSelectAll = useCallback(() => {
      const allSelectableNames = availableClubs
          .filter(club => club.status !== 'failed' && clubStatuses[club.name] !== 'failed')
          .map(club => club.name);
      onSelectClub(allSelectableNames);
  }, [availableClubs, clubStatuses, onSelectClub]);

  const handleClearAll = useCallback(() => {
      onSelectClub([]);
  }, [onSelectClub]);

  const handleClubClick = useCallback((clubName, isFailed) => {
      if (isFailed) return; // Don't select failed clubs
      
      onSelectClub(prevSelected => {
          const currentSelected = Array.isArray(prevSelected) ? prevSelected : (prevSelected ? [prevSelected] : []);
          const isCurrentlySelected = currentSelected.includes(clubName);
          
          if (isCurrentlySelected) {
              // Deselect
              return currentSelected.filter(name => name !== clubName);
          } else {
              // Select
              return [...currentSelected, clubName];
          }
      });
  }, [onSelectClub]);
  // -----------------------

  // Format last crawl date function
  const formatLastCrawlDate = useCallback(() => {
    if (!dataInfo?.latest_crawl_date) return 'לא ידוע';
    
    try {
      const date = new Date(dataInfo.latest_crawl_date);
      // Check if date is valid before formatting
      if (isNaN(date.getTime())) {
        return 'תאריך לא תקין';
      }
      return date.toLocaleDateString('he-IL', { 
        year: 'numeric', 
        month: 'numeric', 
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
      });
    } catch (e) {
      console.error('Error formatting date:', e);
      return 'שגיאה בפורמט';
    }
  }, [dataInfo?.latest_crawl_date]);
  
  // Loading/Empty State
  const isLoading = !dataInfo; // Basic loading state
  const hasClubs = Object.keys(clubsByArea).length > 0;

  if (isLoading) {
      return <div className="clubs-list-loading">טוען רשימת סניפים...</div>;
  }
  
  if (!hasClubs && !dataInfo?.has_data) {
      return <div className="no-clubs-message">לא נמצא מידע. אנא בצע איסוף נתונים ראשוני.</div>;
  }
  
  if (!hasClubs && dataInfo?.has_data) {
      return (
        <div className="no-clubs-message">
          <p>לא נמצאו סניפים זמינים במידע הקיים.</p>
          <p className="debug-info">
            קובץ נתונים: {dataInfo.latest_file}<br/>
            נאסף בתאריך: {new Date(dataInfo.latest_crawl_date).toLocaleString()}<br/>
            {dataInfo.is_complete_crawl === false && <span>נתונים חלקיים בלבד</span>}
          </p>
          <button 
            className="refresh-button" 
            onClick={onRefreshData} 
            disabled={!onRefreshData}
          >
            רענן נתונים עכשיו
          </button>
        </div>
      );
  }

  // Render club item with opening hours
  const renderClubItem = (club) => {
    const isSelected = Array.isArray(selectedClub) 
      ? selectedClub.includes(club.name)
      : selectedClub === club.name;
    const isFailed = club.status === 'failed' || clubStatuses[club.name] === 'failed';
    
    // Use short_name if available, otherwise use name
    const displayName = club.short_name || club.name;
    
    return (
      <div 
        key={club.name} 
        className={classNames('club-item', { 
          'selected': isSelected,
          'failed': isFailed
        })}
        onClick={() => handleClubClick(club.name, isFailed)}
      >
        <div className="club-checkbox">
          {isFailed ? (
            <TbAlertTriangle className="failed-icon" />
          ) : isSelected ? (
            <MdCheckBox className="selected-icon" />
          ) : (
            <MdCheckBoxOutlineBlank className="unselected-icon" />
          )}
        </div>
        <div className="club-info">
          <div className="club-name">{displayName}</div>
          {club.opening_hours && Object.keys(club.opening_hours).length > 0 && (
            <div className="club-opening-hours">
              {Object.entries(club.opening_hours).map(([days, hours]) => (
                <span key={days} className="hours-entry">
                  <RiTimeFill /> {days} {hours}
                </span>
              ))}
            </div>
          )}
        </div>
      </div>
    );
  };

  return (
    <div className="clubs-list compact">
      {/* Data freshness indicator */}
      <div className={classNames('data-freshness-indicator', { 
        'data-stale': isDataStale,
        'data-partial': isPartialData && !isDataStale 
      })}>
        <div className="freshness-content">
          <span className="freshness-icon">
            {isDataStale ? "⚠️" : isPartialData ? "ℹ️" : "✓"}
          </span>
          <div className="freshness-text">
            <p>
              {!dataInfo?.latest_crawl_date 
                ? "מועד העדכון האחרון אינו ידוע" 
                : dataAge === 0 
                  ? `המידע מעודכן להיום${isPartialData ? ` (${getPartialReason()})` : ''}` 
                  : `מועד עדכון אחרון: ${formatLastCrawlDate()}${dataAge !== null ? ` (לפני ${dataAge} ימים)` : ''}${isPartialData ? ` - ${getPartialReason()}` : ''}`
              }
            </p>
            {(isDataStale || !dataInfo?.has_data || isPartialData) && (
              <button className="refresh-button" onClick={onRefreshData} disabled={!onRefreshData}>
                {!dataInfo?.has_data ? 'בצע איסוף נתונים' : isPartialData ? 'השלם את הנתונים' : 'רענן נתונים'}
              </button>
            )}
          </div>
        </div>
      </div>
      
      <div className="clubs-header">
        <div className="clubs-title">
          <h3>סניפים זמינים</h3>
          {selectedCount > 0 && <span className="clubs-selected-count">({selectedCount} נבחרו)</span>}
        </div>
        <div className="clubs-actions">
          <button
            onClick={handleSelectAll}
            className="club-action-button select-all"
            disabled={!hasClubs}
          >
            בחר הכל
          </button>
          <button
            onClick={handleClearAll}
            className="club-action-button clear-all"
            disabled={selectedCount === 0}
          >
            נקה הכל
          </button>
        </div>
      </div>
      
      {/* Define region order */}
      {(() => {
        const regionOrder = ['מרכז', 'שרון', 'שפלה', 'ירושלים והסביבה', 'דרום', 'צפון', 'אחר'];
        const sortedEntries = Object.entries(clubsByArea).sort(([regionA], [regionB]) => {
          const indexA = regionOrder.indexOf(regionA);
          const indexB = regionOrder.indexOf(regionB);
          if (indexA === -1 && indexB === -1) return regionA.localeCompare(regionB); 
          if (indexA === -1) return 1; 
          if (indexB === -1) return -1;
          return indexA - indexB;
        });
        
        return sortedEntries.map(([area, areaClubs]) => (
          <div key={area} className="area-section">
            <div className="area-header">
              <h3 className="area-title">{area}</h3>
              <div className="area-actions">
                <button 
                  className="select-all-btn"
                  onClick={() => handleSelectArea(areaClubs)}
                  disabled={areaClubs.every(club => club.status === 'failed' || clubStatuses[club.name] === 'failed')}
                >
                  בחר הכל
                </button>
                <button 
                  className="clear-all-btn"
                  onClick={() => handleClearArea(areaClubs)}
                >
                  נקה הכל
                </button>
              </div>
            </div>
            <div className="clubs-container">
              {areaClubs.map(renderClubItem)}
            </div>
          </div>
        ));
      })()}
    </div>
  );
});

ClubList.displayName = 'ClubList';

// Update propTypes to include region and short_name
ClubList.propTypes = {
  availableClubs: PropTypes.arrayOf(PropTypes.shape({
    name: PropTypes.string.isRequired,
    short_name: PropTypes.string,
    status: PropTypes.string,
    url: PropTypes.string,
    region: PropTypes.string,
    opening_hours: PropTypes.object
  })),
  selectedClub: PropTypes.oneOfType([
    PropTypes.string,
    PropTypes.arrayOf(PropTypes.string)
  ]),
  onSelectClub: PropTypes.func.isRequired,
  clubStatuses: PropTypes.object, // Live statuses from WebSocket
  dataInfo: PropTypes.shape({      // For freshness indicator
    has_data: PropTypes.bool,
    latest_file: PropTypes.string,
    latest_crawl_date: PropTypes.string,
    days_since_crawl: PropTypes.number,
    is_stale: PropTypes.bool,
    is_complete_crawl: PropTypes.bool,
    crawl_metadata: PropTypes.shape({
      was_stopped_early: PropTypes.bool,
      critical_error_occurred: PropTypes.bool,
      timestamp: PropTypes.string
    })
  }),
  onRefreshData: PropTypes.func
}; 