import React, { useState, useCallback, useEffect } from 'react';
import PropTypes from 'prop-types';
import Select, { components } from 'react-select'; // Import components
import { useClassNames } from '../hooks/useClassNames';
import { useInstructors } from '../hooks/useInstructors';
import { useClubs } from '../hooks/useClubs'; // Assuming useClubs fetches simple list for now
import '../styles/Filters.scss';

// --- Custom Styles for react-select (RTL Option & Alignment) --- 
const compactSelectStyles = {
  option: (provided, state) => ({
    ...provided,
    display: 'flex', // Flex for layout
    alignItems: 'center', // Vertically center items
    direction: 'rtl', // Ensure RTL ordering
    padding: '4px 8px', // Compact padding
    minHeight: '32px', // Consistent height
    cursor: 'pointer',
  }),
  control: (provided) => ({ 
     ...provided,
     minHeight: '38px', 
     height: '38px', 
     direction: 'rtl', // Keep control RTL
  }),
  // Keep other overrides minimal
  valueContainer: (provided) => ({ ...provided, height: '38px', padding: '0 6px' }),
  input: (provided) => ({ ...provided, textAlign: 'right' }),
  placeholder: (provided) => ({ ...provided, textAlign: 'right' }),
  menu: (provided) => ({ ...provided, direction: 'rtl', textAlign: 'right' }),
  singleValue: (provided) => ({ ...provided, textAlign: 'right' }),
  indicatorsContainer: (provided) => ({ ...provided, height: '38px' }),
};
// ----------------------------------------------------------------

// --- Custom Option Component (RTL) --- 
const OptionWithCheckbox = ({ children, isSelected, innerRef, innerProps, getStyles, isDisabled, isFocused, ...rest }) => {
  // Apply react-select's option styles (calculated by compactSelectStyles.option)
  const style = getStyles('option', { ...rest, isSelected, isDisabled, isFocused });

  return (
    <div
      ref={innerRef}
      {...innerProps}
      style={style}
    >
      {/* Checkbox first in DOM so it renders on the right (due to RTL) */}
      <input
        type="checkbox"
        checked={isSelected}
        readOnly
        style={{ cursor: 'pointer', marginLeft: '6px' }}
      />
      {/* Text label */}
      <span style={{ whiteSpace: 'nowrap' }}>{children}</span>
    </div>
  );
};
// -----------------------------

const HEBREW_DAYS = ["ראשון", "שני", "שלישי", "רביעי", "חמישי", "שישי", "שבת"];
const ALL_DAYS_SELECTED = HEBREW_DAYS.reduce((acc, day) => { acc[day] = true; return acc; }, {});
const NO_DAYS_SELECTED = HEBREW_DAYS.reduce((acc, day) => { acc[day] = false; return acc; }, {});

export const Filters = ({ filters: currentFilters, onFilterChange, loading }) => {
  // Initialize with all days selected
  const [selectedDays, setSelectedDays] = useState(ALL_DAYS_SELECTED);
  const [allDaysSelected, setAllDaysSelected] = useState(true);

  // Fetch data for dropdowns/autocomplete
  const { data: classNamesData = [], isLoading: classNamesLoading } = useClassNames();
  const { data: instructorsData = [], isLoading: instructorsLoading } = useInstructors();
  const { data: clubsData = [], isLoading: clubsLoading } = useClubs(); // Keep using existing clubs hook

  // Transform data for react-select
  const classNameOptions = classNamesData.map(name => ({ value: name, label: name }));
  const instructorOptions = instructorsData.map(name => ({ value: name, label: name }));
  const clubOptions = clubsData.map(name => ({ value: name, label: name }));

  // --- Define Helper Function FIRST --- 
  const getSelectedOptions = (options, values) => {
    console.log("getSelectedOptions called with:", { options, values }); // Log inside helper
    if (!Array.isArray(values)) return []; 
    const result = options.filter(opt => values.includes(opt.value));
    console.log("getSelectedOptions result:", result);
    return result;
  };
  // ----------------------------------
  
  // --- Add Logging (Now Uses Defined Function) --- 
  console.log("Filters Component Received Props:", { currentFilters });
  console.log("Filters Component classNameOptions:", classNameOptions);
  const selectedClassNameOptions = getSelectedOptions(classNameOptions, currentFilters.class_name || []);
  console.log("Filters Component calculated selectedClassNameOptions:", selectedClassNameOptions);
  // -----------------

  // Log initial filters received
  useEffect(() => {
      console.log("Filters component mounted/received filters:", currentFilters);
  }, [currentFilters]);

  // Sync local day state from filters prop
   useEffect(() => {
    const daysFromFilters = currentFilters.day_name_hebrew || [];
        const newSelectedDays = {};
        let allChecked = daysFromFilters.length === HEBREW_DAYS.length;
        HEBREW_DAYS.forEach(day => {
            newSelectedDays[day] = daysFromFilters.includes(day);
            if (!newSelectedDays[day]) allChecked = false;
        });
    if (daysFromFilters.length === 0 && !currentFilters.class_name && !currentFilters.instructor && !currentFilters.club) {
             // If NO filters are set (including days), default to all days checked
             setSelectedDays(ALL_DAYS_SELECTED);
             setAllDaysSelected(true);
        } else if (daysFromFilters.length === 0) {
             setSelectedDays(NO_DAYS_SELECTED);
             setAllDaysSelected(false);
        } else {
            setSelectedDays(newSelectedDays);
            setAllDaysSelected(allChecked);
        }
   // Depend also on other filters to reset days correctly when they are cleared
  }, [currentFilters.day_name_hebrew, currentFilters.class_name, currentFilters.instructor, currentFilters.club]);

  // Handler for react-select components - Modified to pass full filters object
  const handleSelectChange = useCallback((selectedOptions, actionMeta) => {
    const { name } = actionMeta;
    let values = [];
    if (Array.isArray(selectedOptions)) {
      values = selectedOptions.map(option => option.value);
    } else if (selectedOptions) { 
      values = [selectedOptions.value]; 
    }
    
    console.log(`Filters: handleSelectChange for '${name}', new values:`, values);
    // Construct the new filters object by updating the specific key
    const newFilters = {
        ...currentFilters,
        [name]: values
    };
    console.log(`Filters: Calling onFilterChange with new object:`, newFilters);
    onFilterChange(newFilters); // Pass the single updated filters object
  }, [onFilterChange, currentFilters]); // Depend on currentFilters

  // Handle individual day checkbox changes - Modified to pass full filters object
  const handleDayChange = useCallback((e) => {
    const { name, checked } = e.target;
    setSelectedDays(prev => {
      const newSelectedDaysState = { ...prev, [name]: checked };
      const selectedDayNames = Object.entries(newSelectedDaysState)
        .filter(([, isSelected]) => isSelected)
        .map(([dayName]) => dayName);
        
      setAllDaysSelected(selectedDayNames.length === HEBREW_DAYS.length);
      
      // Construct the new filters object
      const newFilters = {
          ...currentFilters,
          day_name_hebrew: selectedDayNames
      };
      console.log(`Filters: Calling onFilterChange for days:`, newFilters);
      onFilterChange(newFilters); // Pass the single updated filters object
      return newSelectedDaysState;
    });
  }, [onFilterChange, currentFilters]); // Depend on currentFilters

  // Handle "All Days" checkbox change - Modified to pass full filters object
  const handleAllDaysChange = useCallback((e) => {
    const isChecked = e.target.checked;
    setAllDaysSelected(isChecked);
    const newSelectedDaysState = isChecked ? ALL_DAYS_SELECTED : NO_DAYS_SELECTED;
    setSelectedDays(newSelectedDaysState);
    
    const selectedDayNames = isChecked ? HEBREW_DAYS : [];
    // Construct the new filters object
    const newFilters = {
        ...currentFilters,
        day_name_hebrew: selectedDayNames
    };
    console.log(`Filters: Calling onFilterChange for all days toggle:`, newFilters);
    onFilterChange(newFilters); // Pass the single updated filters object
  }, [onFilterChange, currentFilters]); // Depend on currentFilters

  // Reset handler - Modified to pass full filters object
  const handleReset = useCallback(() => {
     const defaultFilters = {
          class_name: [], 
          instructor: [], 
          club: [],       
          day_name_hebrew: HEBREW_DAYS // Reset days to all selected
     };
     setSelectedDays(ALL_DAYS_SELECTED);
     setAllDaysSelected(true);
     console.log(`Filters: Calling onFilterChange for reset:`, defaultFilters);
     onFilterChange(defaultFilters); // Pass the single default filters object
  }, [onFilterChange]);

  // Calculate values for Select components using currentFilters
  const selectedClassNameValue = getSelectedOptions(classNameOptions, currentFilters.class_name || []);
  const selectedInstructorValue = getSelectedOptions(instructorOptions, currentFilters.instructor || []);
  const selectedClubValue = getSelectedOptions(clubOptions, currentFilters.club || []);

  return (
    <form className="filters">
      <div className="filter-row">
         {/* Class Name Multi-Select with Checkboxes */}
         <div className="filter-group">
           <label htmlFor="class_name_select">שם שיעור</label>
           <Select
             inputId="class_name_select"
             name="class_name"
             options={classNameOptions}
             isMulti 
             closeMenuOnSelect={false} 
             hideSelectedOptions={false} // Keep selected options visible
             components={{ Option: OptionWithCheckbox }} // Use custom Option component
             styles={compactSelectStyles} // Apply custom styles
             value={selectedClassNameValue} // Use value derived from currentFilters
             onChange={handleSelectChange}
             isLoading={classNamesLoading}
             isDisabled={loading}
             isClearable={true}
             placeholder="הכל (בחר אחד או יותר)"
             noOptionsMessage={() => classNamesLoading ? 'טוען...' : 'לא נמצאו שיעורים'}
             // Add styles if needed, e.g., to adjust control height
             // styles={{ control: (base) => ({ ...base, minHeight: '38px' }) }}
           />
         </div>
 
         {/* Instructor Multi-Select with Checkboxes */}
         <div className="filter-group">
           <label htmlFor="instructor_select">מדריך</label>
            <Select
             inputId="instructor_select"
             name="instructor"
             options={instructorOptions}
             isMulti
             closeMenuOnSelect={false}
             hideSelectedOptions={false}
             components={{ Option: OptionWithCheckbox }}
             styles={compactSelectStyles} // Apply custom styles
             value={selectedInstructorValue} // Use value derived from currentFilters
             onChange={handleSelectChange}
             isLoading={instructorsLoading}
             isDisabled={loading}
             isClearable={true}
             placeholder="הכל (בחר אחד או יותר)"
             noOptionsMessage={() => instructorsLoading ? 'טוען...' : 'לא נמצאו מדריכים'}
           />
         </div>
 
         {/* Club Multi-Select with Checkboxes */}
          <div className="filter-group">
           <label htmlFor="club_select">סניף</label>
            <Select
             inputId="club_select"
             name="club"
             options={clubOptions}
             isMulti
             closeMenuOnSelect={false}
             hideSelectedOptions={false}
             components={{ Option: OptionWithCheckbox }}
             styles={compactSelectStyles} // Apply custom styles
             value={selectedClubValue} // Use value derived from currentFilters
             onChange={handleSelectChange}
             isLoading={clubsLoading}
             isDisabled={loading}
             isClearable={true}
             placeholder="הכל (בחר אחד או יותר)"
             noOptionsMessage={() => clubsLoading ? 'טוען...' : 'לא נמצאו סניפים'}
           />
         </div>
      </div>

      {/* Day Checkboxes (logic remains same) */}
      <div className="filter-group days-filter">
        <label>ימים</label>
        <div className="checkbox-group">
          {/* "All Days" Checkbox */}
          <div className="checkbox-item all-days-checkbox">
             <input
                type="checkbox"
                id="day-all"
                name="all-days"
                checked={allDaysSelected}
                onChange={handleAllDaysChange}
                disabled={loading}
             />
             <label htmlFor="day-all">הכל</label>
          </div>
          {/* Individual Day Checkboxes */}
          {HEBREW_DAYS.map(day => (
            <div key={day} className="checkbox-item">
              <input
                type="checkbox"
                id={`day-${day}`}
                name={day}
                checked={selectedDays[day] || false}
                onChange={handleDayChange}
                disabled={loading}
              />
              <label htmlFor={`day-${day}`}>{day}</label>
            </div>
          ))}
        </div>
      </div>

      <div className="filter-actions">
        <button type="button" className="reset-filters" onClick={handleReset} disabled={loading}>
          איפוס
        </button>
      </div>
    </form>
  );
};

Filters.propTypes = {
  filters: PropTypes.object.isRequired, // Renamed prop for clarity
  onFilterChange: PropTypes.func.isRequired,
  loading: PropTypes.bool,
}; 