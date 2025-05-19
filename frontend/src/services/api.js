import config from '../config';

class ApiService {
    constructor() {
        this.baseUrl = null;
        this.initializeBaseUrl();
    }

    async initializeBaseUrl() {
        this.baseUrl = await config.backendBaseUrl;
    }

    async get(endpoint) {
        if (!this.baseUrl) {
            await this.initializeBaseUrl();
        }
        const response = await fetch(`${this.baseUrl}/api${endpoint}`);
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        return response.json();
    }

    async post(endpoint, data) {
        if (!this.baseUrl) {
            await this.initializeBaseUrl();
        }
        const response = await fetch(`${this.baseUrl}/api${endpoint}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(data),
        });
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        return response.json();
    }

    // WebSocket connection
    connectWebSocket(onMessage) {
        if (!this.baseUrl) {
            this.initializeBaseUrl().then(() => {
                this._connectWebSocket(onMessage);
            });
        } else {
            this._connectWebSocket(onMessage);
        }
    }

    _connectWebSocket(onMessage) {
        const wsUrl = this.baseUrl.replace('http', 'ws') + '/api/ws';
        const ws = new WebSocket(wsUrl);

        ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            onMessage(data);
        };

        ws.onerror = (error) => {
            console.error('WebSocket error:', error);
        };

        ws.onclose = () => {
            console.log('WebSocket connection closed');
            // Attempt to reconnect after a delay
            setTimeout(() => this._connectWebSocket(onMessage), 5000);
        };

        return ws;
    }
}

export const apiService = new ApiService(); 