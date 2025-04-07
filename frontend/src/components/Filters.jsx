import React, { useState, useCallback, useEffect } from 'react';
import PropTypes from 'prop-types';
import Select, { components } from 'react-select'; // Import components
import { useClassNames } from '../hooks/useClassNames';
import { useInstructors } from '../hooks/useInstructors';
import { useClubs } from '../hooks/useClubs'; // Assuming useClubs fetches simple list for now

// --- Custom Option Component (RTL) --- 
const OptionWithCheckbox = (props) => {
  return (
    // Style is applied via styles prop, but ensure base component is used
    <components.Option {...props}> 
      {/* Label first for RTL flow */} 
      <label style={{ marginRight: '8px' }}>{props.label}</label> 
      <input 
        type="checkbox" 
        checked={props.isSelected} 
        onChange={() => null} 
        // No specific style needed here if parent is flex-reversed
      /> 
    </components.Option>
  );
};
// -----------------------------

// --- Custom Styles for react-select (RTL Option & Alignment) --- 
const compactSelectStyles = {
  option: (provided, state) => ({
    ...provided,
    paddingTop: '4px',
    paddingBottom: '4px',
    display: 'flex',
    alignItems: 'center',
    flexDirection: 'row-reverse', 
    justifyContent: 'space-between',
    textAlign: 'right', // Align text within option to the right
  }),
  control: (provided) => ({ 
     ...provided,
     minHeight: '34px',
     direction: 'rtl', // Set control direction to RTL
  }),
  valueContainer: (provided) => ({ 
     ...provided,
     padding: '0 6px', // Keep padding, but alignment is handled by control
  }),
  input: (provided) => ({
    ...provided,
    textAlign: 'right', // Align typing input to the right
  }),
  placeholder: (provided) => ({
    ...provided,
    textAlign: 'right', // Align placeholder text to the right
  }),
  menu: (provided) => ({
    ...provided,
    textAlign: 'right', // Align menu text (like "No options") to right
  }),
  // Ensure singleValue is also right-aligned if it ever shows (though less likely in multi-select)
  singleValue: (provided) => ({
    ...provided,
    textAlign: 'right',
  }),
};
// ----------------------------------------------------------------

const HEBREW_DAYS = ["ראשון", "שני", "שלישי", "רביעי", "חמישי", "שישי", "שבת"];
const ALL_DAYS_SELECTED = HEBREW_DAYS.reduce((acc, day) => { acc[day] = true; return acc; }, {});
const NO_DAYS_SELECTED = HEBREW_DAYS.reduce((acc, day) => { acc[day] = false; return acc; }, {});

export const Filters = ({ filters: initialFilters, onFilterChange, loading }) => {
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
  console.log("Filters Component Received Props:", { initialFilters });
  console.log("Filters Component classNameOptions:", classNameOptions);
  const selectedClassNameOptions = getSelectedOptions(classNameOptions, initialFilters.class_name || []);
  console.log("Filters Component calculated selectedClassNameOptions:", selectedClassNameOptions);
  // -----------------

   // Sync local day state if initialFilters change externally (e.g., reset)
   useEffect(() => {
        const daysFromFilters = initialFilters.day_name_hebrew || [];
        const newSelectedDays = {};
        let allChecked = daysFromFilters.length === HEBREW_DAYS.length;
        HEBREW_DAYS.forEach(day => {
            newSelectedDays[day] = daysFromFilters.includes(day);
            if (!newSelectedDays[day]) allChecked = false;
        });
        if (daysFromFilters.length === 0 && !initialFilters.class_name && !initialFilters.instructor && !initialFilters.club) {
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
   }, [initialFilters.day_name_hebrew, initialFilters.class_name, initialFilters.instructor, initialFilters.club]);

  // Handler for react-select components
  const handleSelectChange = useCallback((selectedOptions, actionMeta) => {
    const { name } = actionMeta;
    let values = [];
    if (Array.isArray(selectedOptions)) {
      values = selectedOptions.map(option => option.value);
    } else if (selectedOptions) { 
      values = [selectedOptions.value]; 
    } // If selectedOptions is null (cleared), values remains []
    
    console.log(`Filters: handleSelectChange - Name: ${name}, Values Sent:`, values); // Log values being sent
    onFilterChange(name, values);
  }, [onFilterChange]);

  // Handle individual day checkbox changes
  const handleDayChange = useCallback((e) => {
    const { name, checked } = e.target;
    setSelectedDays(prev => {
      const newSelectedDays = { ...prev, [name]: checked };
      const selectedDayNames = Object.entries(newSelectedDays)
        .filter(([, isSelected]) => isSelected)
        .map(([dayName]) => dayName);
      setAllDaysSelected(selectedDayNames.length === HEBREW_DAYS.length);
      onFilterChange('day_name_hebrew', selectedDayNames);
      return newSelectedDays;
    });
  }, [onFilterChange]);

  // Handle "All Days" checkbox change
  const handleAllDaysChange = useCallback((e) => {
    const isChecked = e.target.checked;
    setAllDaysSelected(isChecked);
    const newSelectedDays = isChecked ? ALL_DAYS_SELECTED : NO_DAYS_SELECTED;
    setSelectedDays(newSelectedDays);
    const selectedDayNames = isChecked ? HEBREW_DAYS : [];
    onFilterChange('day_name_hebrew', selectedDayNames);
  }, [onFilterChange]);

  // Reset handler: Ensure filter values are empty arrays for multi-select fields
  const handleReset = useCallback(() => {
     const defaultFilters = {
          class_name: [], // Reset to empty array
          instructor: [], // Reset to empty array
          club: [],       // Reset to empty array
          day_name_hebrew: HEBREW_DAYS 
     };
     setSelectedDays(ALL_DAYS_SELECTED);
     setAllDaysSelected(true);
     Object.entries(defaultFilters).forEach(([key, value]) => {
         onFilterChange(key, value);
     });
  }, [onFilterChange]);

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
             value={selectedClassNameOptions} // Use the logged variable
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
             value={getSelectedOptions(instructorOptions, initialFilters.instructor || [])} // Ensure value is array
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
             value={getSelectedOptions(clubOptions, initialFilters.club || [])} // Ensure value is array
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
  filters: PropTypes.object.isRequired,
  onFilterChange: PropTypes.func.isRequired,
  loading: PropTypes.bool,
}; 