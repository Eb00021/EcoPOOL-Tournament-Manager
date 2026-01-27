// EcoPOOL Sync Manager
// Handles background synchronization of offline actions

class SyncManager {
    constructor() {
        this.isSyncing = false;
        this.syncInterval = null;
        this.listeners = [];
    }

    // Start the sync manager
    start() {
        // Listen for online events
        window.addEventListener('online', () => this.onOnline());

        // Periodic sync check (every 30 seconds when online)
        this.syncInterval = setInterval(() => {
            if (navigator.onLine) {
                this.sync();
            }
        }, 30000);

        // Initial sync if online
        if (navigator.onLine) {
            setTimeout(() => this.sync(), 2000);
        }

        console.log('[SyncManager] Started');
    }

    // Stop the sync manager
    stop() {
        if (this.syncInterval) {
            clearInterval(this.syncInterval);
            this.syncInterval = null;
        }
    }

    // Called when coming back online
    async onOnline() {
        console.log('[SyncManager] Back online, syncing...');
        await this.sync();
    }

    // Add a listener for sync events
    addListener(callback) {
        this.listeners.push(callback);
    }

    // Notify listeners of sync events
    notifyListeners(event, data) {
        this.listeners.forEach(cb => {
            try {
                cb(event, data);
            } catch (e) {
                console.error('[SyncManager] Listener error:', e);
            }
        });
    }

    // Main sync function - process the queue
    async sync() {
        if (this.isSyncing) {
            console.log('[SyncManager] Already syncing, skipping');
            return;
        }

        if (!navigator.onLine) {
            console.log('[SyncManager] Offline, skipping sync');
            return;
        }

        if (!window.offlineDB || !window.offlineDB.isAvailable()) {
            console.log('[SyncManager] OfflineDB not available');
            return;
        }

        this.isSyncing = true;
        this.notifyListeners('syncStart', {});

        try {
            const queue = await window.offlineDB.getSyncQueue();

            if (queue.length === 0) {
                console.log('[SyncManager] No items to sync');
                this.isSyncing = false;
                this.notifyListeners('syncComplete', { synced: 0 });
                return;
            }

            console.log(`[SyncManager] Syncing ${queue.length} items...`);

            let synced = 0;
            let failed = 0;

            for (const item of queue) {
                try {
                    const success = await this.executeAction(item);
                    if (success) {
                        await window.offlineDB.clearSyncQueueItem(item.id);
                        synced++;
                        this.notifyListeners('itemSynced', { item, synced, total: queue.length });
                    } else {
                        await window.offlineDB.markSyncItemFailed(item.id, 'Action failed');
                        failed++;
                    }
                } catch (error) {
                    console.error('[SyncManager] Error syncing item:', error);
                    await window.offlineDB.markSyncItemFailed(item.id, error.message);
                    failed++;
                }
            }

            console.log(`[SyncManager] Sync complete: ${synced} synced, ${failed} failed`);
            this.notifyListeners('syncComplete', { synced, failed });

        } catch (error) {
            console.error('[SyncManager] Sync error:', error);
            this.notifyListeners('syncError', { error: error.message });
        } finally {
            this.isSyncing = false;
        }
    }

    // Execute a single queued action
    async executeAction(item) {
        const { action, payload } = item;

        // Map actions to API endpoints
        const actionMap = {
            'pocket_ball': '/api/manager/pocket-ball',
            'win_game': '/api/manager/win-game',
            'set_group': '/api/manager/set-group',
            'set_breaking_team': '/api/manager/set-breaking-team',
            'set_golden_break': '/api/manager/set-golden-break',
            'set_early_8ball': '/api/manager/set-early-8ball',
            'reset_table': '/api/manager/reset-table',
            'start_match': '/api/manager/start-match',
            'complete_match': '/api/manager/complete-match'
        };

        const endpoint = actionMap[action];
        if (!endpoint) {
            console.warn('[SyncManager] Unknown action:', action);
            return false;
        }

        try {
            const response = await fetch(endpoint, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw new Error(errorData.error || `HTTP ${response.status}`);
            }

            const result = await response.json();
            if (result.success === false) {
                throw new Error(result.error || 'Action failed');
            }

            return true;

        } catch (error) {
            console.error(`[SyncManager] Action ${action} failed:`, error);
            // Check if it's a conflict we should handle
            await this.handleConflict(item, error);
            throw error;
        }
    }

    // Handle sync conflicts (server state wins)
    async handleConflict(item, error) {
        // For now, server state always wins
        // Notify user that their offline action was rejected
        this.notifyListeners('conflict', {
            action: item.action,
            error: error.message,
            timestamp: item.timestamp
        });
    }

    // Check if there are pending items
    async hasPendingItems() {
        if (!window.offlineDB || !window.offlineDB.isAvailable()) {
            return false;
        }
        const count = await window.offlineDB.getSyncQueueCount();
        return count > 0;
    }

    // Get pending item count
    async getPendingCount() {
        if (!window.offlineDB || !window.offlineDB.isAvailable()) {
            return 0;
        }
        return await window.offlineDB.getSyncQueueCount();
    }
}

// Global instance
window.syncManager = new SyncManager();
