const config = {
    backendBaseUrl: (() => {
        // Default to localhost in development
        const defaultUrl = 'http://localhost:8000';
        
        // In production, use environment variable or default to localhost
        const envUrl = process.env.REACT_APP_BACKEND_BASE_URL || defaultUrl;
        
        // If we're in development, try localhost first
        if (process.env.NODE_ENV === 'development') {
            return fetch(`${defaultUrl}/api/status`)
                .then(response => response.ok ? defaultUrl : envUrl)
                .catch(() => envUrl);
        }
        
        // In production, use the environment variable
        return Promise.resolve(envUrl);
    })()
};

export default config; 