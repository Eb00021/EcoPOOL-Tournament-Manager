// EcoPOOL Offline Database (IndexedDB)
// Provides offline storage for app state, sync queue, and cached data

class OfflineDB {
    constructor() {
        this.dbName = 'ecopool-offline';
        this.dbVersion = 1;
        this.db = null;
        this.isReady = false;
    }

    // Initialize the database
    async init() {
        if (this.db) return true;

        return new Promise((resolve, reject) => {
            if (!window.indexedDB) {
                console.warn('[OfflineDB] IndexedDB not supported');
                resolve(false);
                return;
            }

            const request = indexedDB.open(this.dbName, this.dbVersion);

            request.onerror = (event) => {
                console.error('[OfflineDB] Error opening database:', event.target.error);
                resolve(false);
            };

            request.onsuccess = (event) => {
                this.db = event.target.result;
                this.isReady = true;
                console.log('[OfflineDB] Database ready');
                resolve(true);
            };

            request.onupgradeneeded = (event) => {
                const db = event.target.result;

                // Store for app state (SSE data cache)
                if (!db.objectStoreNames.contains('appState')) {
                    db.createObjectStore('appState', { keyPath: 'key' });
                }

                // Store for sync queue (offline actions)
                if (!db.objectStoreNames.contains('syncQueue')) {
                    const syncStore = db.createObjectStore('syncQueue', {
                        keyPath: 'id',
                        autoIncrement: true
                    });
                    syncStore.createIndex('timestamp', 'timestamp', { unique: false });
                    syncStore.createIndex('action', 'action', { unique: false });
                }

                // Store for cached matches
                if (!db.objectStoreNames.contains('matches')) {
                    const matchStore = db.createObjectStore('matches', { keyPath: 'id' });
                    matchStore.createIndex('status', 'status', { unique: false });
                }

                // Store for cached games
                if (!db.objectStoreNames.contains('games')) {
                    const gameStore = db.createObjectStore('games', { keyPath: 'id' });
                    gameStore.createIndex('match_id', 'match_id', { unique: false });
                }

                console.log('[OfflineDB] Database schema created');
            };
        });
    }

    // Save app state (SSE data)
    async saveAppState(data) {
        if (!this.db) return false;

        return new Promise((resolve, reject) => {
            try {
                const transaction = this.db.transaction(['appState'], 'readwrite');
                const store = transaction.objectStore('appState');

                // Save with timestamp
                const record = {
                    key: 'currentState',
                    data: data,
                    timestamp: Date.now()
                };

                const request = store.put(record);
                request.onsuccess = () => resolve(true);
                request.onerror = () => resolve(false);
            } catch (e) {
                console.error('[OfflineDB] Error saving app state:', e);
                resolve(false);
            }
        });
    }

    // Get cached app state
    async getAppState() {
        if (!this.db) return null;

        return new Promise((resolve) => {
            try {
                const transaction = this.db.transaction(['appState'], 'readonly');
                const store = transaction.objectStore('appState');
                const request = store.get('currentState');

                request.onsuccess = () => {
                    const result = request.result;
                    if (result && result.data) {
                        // Include cache age info
                        result.data._cacheAge = Date.now() - result.timestamp;
                        result.data._cached = true;
                        resolve(result.data);
                    } else {
                        resolve(null);
                    }
                };
                request.onerror = () => resolve(null);
            } catch (e) {
                console.error('[OfflineDB] Error getting app state:', e);
                resolve(null);
            }
        });
    }

    // Add action to sync queue (for offline manager actions)
    async addToSyncQueue(action, payload) {
        if (!this.db) return null;

        return new Promise((resolve, reject) => {
            try {
                const transaction = this.db.transaction(['syncQueue'], 'readwrite');
                const store = transaction.objectStore('syncQueue');

                const record = {
                    action: action,
                    payload: payload,
                    timestamp: Date.now(),
                    retries: 0,
                    status: 'pending'
                };

                const request = store.add(record);
                request.onsuccess = () => {
                    console.log('[OfflineDB] Added to sync queue:', action);
                    resolve(request.result); // Returns the auto-generated ID
                };
                request.onerror = () => {
                    console.error('[OfflineDB] Error adding to sync queue');
                    resolve(null);
                };
            } catch (e) {
                console.error('[OfflineDB] Error adding to sync queue:', e);
                resolve(null);
            }
        });
    }

    // Get all pending items from sync queue
    async getSyncQueue() {
        if (!this.db) return [];

        return new Promise((resolve) => {
            try {
                const transaction = this.db.transaction(['syncQueue'], 'readonly');
                const store = transaction.objectStore('syncQueue');
                const request = store.getAll();

                request.onsuccess = () => {
                    const items = request.result || [];
                    // Sort by timestamp (oldest first)
                    items.sort((a, b) => a.timestamp - b.timestamp);
                    resolve(items.filter(item => item.status === 'pending'));
                };
                request.onerror = () => resolve([]);
            } catch (e) {
                console.error('[OfflineDB] Error getting sync queue:', e);
                resolve([]);
            }
        });
    }

    // Clear a specific item from sync queue (after successful sync)
    async clearSyncQueueItem(id) {
        if (!this.db) return false;

        return new Promise((resolve) => {
            try {
                const transaction = this.db.transaction(['syncQueue'], 'readwrite');
                const store = transaction.objectStore('syncQueue');
                const request = store.delete(id);

                request.onsuccess = () => resolve(true);
                request.onerror = () => resolve(false);
            } catch (e) {
                console.error('[OfflineDB] Error clearing sync queue item:', e);
                resolve(false);
            }
        });
    }

    // Mark a sync queue item as failed (for retry logic)
    async markSyncItemFailed(id, error) {
        if (!this.db) return false;

        return new Promise((resolve) => {
            try {
                const transaction = this.db.transaction(['syncQueue'], 'readwrite');
                const store = transaction.objectStore('syncQueue');
                const getRequest = store.get(id);

                getRequest.onsuccess = () => {
                    const item = getRequest.result;
                    if (item) {
                        item.retries = (item.retries || 0) + 1;
                        item.lastError = error;
                        item.lastAttempt = Date.now();

                        // Mark as failed after 3 retries
                        if (item.retries >= 3) {
                            item.status = 'failed';
                        }

                        const putRequest = store.put(item);
                        putRequest.onsuccess = () => resolve(true);
                        putRequest.onerror = () => resolve(false);
                    } else {
                        resolve(false);
                    }
                };
                getRequest.onerror = () => resolve(false);
            } catch (e) {
                console.error('[OfflineDB] Error marking sync item failed:', e);
                resolve(false);
            }
        });
    }

    // Get count of pending sync items
    async getSyncQueueCount() {
        const queue = await this.getSyncQueue();
        return queue.length;
    }

    // Clear all sync queue items
    async clearSyncQueue() {
        if (!this.db) return false;

        return new Promise((resolve) => {
            try {
                const transaction = this.db.transaction(['syncQueue'], 'readwrite');
                const store = transaction.objectStore('syncQueue');
                const request = store.clear();

                request.onsuccess = () => resolve(true);
                request.onerror = () => resolve(false);
            } catch (e) {
                console.error('[OfflineDB] Error clearing sync queue:', e);
                resolve(false);
            }
        });
    }

    // Cache a match for offline viewing
    async cacheMatch(match) {
        if (!this.db) return false;

        return new Promise((resolve) => {
            try {
                const transaction = this.db.transaction(['matches'], 'readwrite');
                const store = transaction.objectStore('matches');

                match._cachedAt = Date.now();
                const request = store.put(match);

                request.onsuccess = () => resolve(true);
                request.onerror = () => resolve(false);
            } catch (e) {
                console.error('[OfflineDB] Error caching match:', e);
                resolve(false);
            }
        });
    }

    // Get a cached match
    async getCachedMatch(matchId) {
        if (!this.db) return null;

        return new Promise((resolve) => {
            try {
                const transaction = this.db.transaction(['matches'], 'readonly');
                const store = transaction.objectStore('matches');
                const request = store.get(matchId);

                request.onsuccess = () => resolve(request.result || null);
                request.onerror = () => resolve(null);
            } catch (e) {
                console.error('[OfflineDB] Error getting cached match:', e);
                resolve(null);
            }
        });
    }

    // Check if database is available
    isAvailable() {
        return this.isReady && this.db !== null;
    }
}

// Global instance
window.offlineDB = new OfflineDB();
