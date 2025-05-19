import React, { useEffect, useState } from "react";
import PropTypes from 'prop-types';
import { memo } from 'react';
import classNames from 'classnames';
import '../styles/ClassList.scss'; // Import component-specific styles
import { MdLocationOn, MdAccessTime, MdPerson } from 'react-icons/md';
import { format, parseISO } from 'date-fns';
import { he } from 'date-fns/locale';

// Club name mapping to short names
const clubShortNames = {
  'הולמס פלייס אשדוד': 'אשדוד',
  'הולמס פלייס באר שבע': 'באר שבע',
  'הולמס פלייס גבעתיים': 'גבעתיים',
  'הולמס פלייס הרצליה': 'הרצליה',
  'הולמס פלייס חולון': 'חולון',
  'הולמס פלייס חיפה': 'חיפה',
  'הולמס פלייס ירושלים': 'ירושלים',
  'הולמס פלייס כפר סבא': 'כפר סבא',
  'הולמס פלייס מודיעין': 'מודיעין',
  'הולמס פלייס נהריה': 'נהריה',
  'הולמס פלייס נתניה': 'נתניה',
  'הולמס פלייס עפולה': 'עפולה',
  'הולמס פלייס פתח תקווה': 'פתח תקווה',
  'הולמס פלייס ראשון לציון': 'ראשון לציון',
  'הולמס פלייס רחובות': 'רחובות',
  'הולמס פלייס רמת גן': 'רמת גן',
  'הולמס פלייס רעננה': 'רעננה',
  'הולמס פלייס תל אביב': 'תל אביב',
  "הולמס פלייס": "הולמס",
  "גו אקטיב": "גו אקטיב",
  "קאנטרי קלאב": "קאנטרי",
};

// Function to check if a class has passed (within 5 minute grace period)
const isClassPassed = (day, time) => {
  // Get current date and time
  const now = new Date();
  const currentDay = now.getDay();
  
  // Map Hebrew day names to numbers (0 = Sunday, 1 = Monday, etc.)
  const hebrewDayMap = {
    'ראשון': 0,
    'שני': 1,
    'שלישי': 2,
    'רביעי': 3,
    'חמישי': 4,
    'שישי': 5,
    'שבת': 6
  };
  
  // Get the day number from Hebrew day name
  const classDay = hebrewDayMap[day];
  
  // If it's not the same day, class is in the past or future
  if (classDay !== currentDay) {
    // If class day is before current day in the same week, it has passed
    return classDay < currentDay;
  }
  
  // Parse class time (format: HH:MM)
  const [hours, minutes] = time.split(':').map(Number);
  const classTime = new Date();
  classTime.setHours(hours, minutes, 0, 0);
  
  // Add 5 minutes grace period
  const graceTime = new Date(classTime);
  graceTime.setMinutes(graceTime.getMinutes() + 5);
  
  // Check if current time is after the grace period
  return now > graceTime;
};

// Assuming classes is an array like [{ name: ..., time: ..., club: ..., region: ... }, ...]
// And regions is a sorted array like ["צפון", "מרכז", "דרום", ...]
// Added clubStatuses to the props
export const ClassList = memo(({ classes = [], regions = [], clubStatuses = {}, openingHours = {}, availableClubs = [] }) => {
  // Create a mapping of club names to their regions from availableClubs
  const clubToRegion = availableClubs.reduce((acc, club) => {
    if (club.name && club.region) {
      acc[club.name] = club.region;
    }
    return acc;
  }, {});

  // Group classes by region and day
  const groupedClasses = classes.reduce((acc, cls) => {
    // Use the club's region from availableClubs if no region is provided
    const region = cls.region || clubToRegion[cls.club] || 'מרכז';
    const day = cls.day_name_hebrew || 'לא ידוע';
    
    if (!acc[region]) {
      acc[region] = {};
    }
    if (!acc[region][day]) {
      acc[region][day] = [];
    }
    
    acc[region][day].push(cls);
    return acc;
  }, {});

  // Sort classes by time within each day
  Object.keys(groupedClasses).forEach(region => {
    Object.keys(groupedClasses[region]).forEach(day => {
      groupedClasses[region][day].sort((a, b) => {
        const timeA = a.time ? a.time.split(':').map(Number) : [0, 0];
        const timeB = b.time ? b.time.split(':').map(Number) : [0, 0];
        return timeA[0] * 60 + timeA[1] - (timeB[0] * 60 + timeB[1]);
      });
    });
  });

  // Define the region order to match ClubList
  const regionOrder = ['מרכז', 'שרון', 'שפלה', 'ירושלים והסביבה', 'דרום', 'צפון', 'אחר'];

  // Sort regions according to the specified order
  const sortedRegions = Object.keys(groupedClasses).sort((a, b) => {
    const indexA = regionOrder.indexOf(a);
    const indexB = regionOrder.indexOf(b);
    // If a region is not found in the regionOrder array, put it at the end
    if (indexA === -1 && indexB === -1) return 0;
    if (indexA === -1) return 1;
    if (indexB === -1) return -1;
    return indexA - indexB;
  });

  // Log the regions for debugging
  console.log('Available regions:', regions);
  console.log('Found regions:', Object.keys(groupedClasses));
  console.log('Sorted regions:', sortedRegions);

  // Extract all clubs from the classes
  const clubsWithData = new Set(classes.map(cls => cls.club));

  // Check for selected clubs with no data due to failed crawls
  const failedSelectedClubs = Object.entries(clubStatuses)
    .filter(([clubName, status]) => 
      status === 'failed' && !clubsWithData.has(clubName)
    )
    .map(([clubName]) => clubName);

  // If there are no classes and no failed clubs, show the empty message
  if ((!classes || classes.length === 0) && failedSelectedClubs.length === 0) {
    return <div className="empty-message">לא נמצאו שיעורים מתאימים</div>;
  }
  
  return (
    <div className="class-list">
      {sortedRegions.map(region => (
        <div key={region} className="region-section">
          <h2 className="region-title">{region}</h2>
          {Object.entries(groupedClasses[region]).map(([day, dayClasses]) => (
            <div key={day} className="day-section">
              <h3 className="day-title">{day}</h3>
              <div className="classes-container">
                {dayClasses.map((cls) => (
                  <div key={`${cls.club}-${cls.time}-${cls.name}`} className="class-card">
                    <div className="class-time">
                      {isClassPassed(day, cls.time) && <span className="class-passed">חלף</span>}
                      {cls.time}
                    </div>
                    <div className="class-name">{cls.name}</div>
                    <div className="class-instructor">{cls.instructor}</div>
                    <div className="class-club">{clubShortNames[cls.club] || cls.club}</div>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      ))}
    </div>
  );
});

ClassList.displayName = 'ClassList';

ClassList.propTypes = {
  classes: PropTypes.arrayOf(PropTypes.shape({
      club: PropTypes.string,
      day: PropTypes.string, 
      day_name_hebrew: PropTypes.string,
      time: PropTypes.string,
      name: PropTypes.string,
      instructor: PropTypes.string,
      location: PropTypes.string,
      region: PropTypes.string,
      timestamp: PropTypes.string
  })),
  regions: PropTypes.arrayOf(PropTypes.string),
  clubStatuses: PropTypes.object,
  openingHours: PropTypes.object,
  availableClubs: PropTypes.arrayOf(PropTypes.shape({
    name: PropTypes.string,
    region: PropTypes.string
  }))
}; 