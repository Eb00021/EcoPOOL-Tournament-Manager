        // Mobile compatibility helpers
        const isMobile = /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent);
        const isIOS = /iPad|iPhone|iPod/.test(navigator.userAgent);
        
        // ========================================
        // HAPTIC FEEDBACK SYSTEM
        // ========================================
        // Different vibration patterns for various interactions
        const HapticPatterns = {
            // Light tap - for small buttons, toggles
            light: 10,
            // Medium tap - for important buttons, selections
            medium: 25,
            // Strong tap - for confirmations, wins
            strong: 50,
            // Double tap pattern - for special actions
            double: [15, 50, 15],
            // Success pattern - celebration feel
            success: [30, 50, 30, 50, 50],
            // Error pattern - warning feel
            error: [100, 30, 100],
            // Ball pocket pattern - satisfying click
            ballPocket: [5, 30, 10],
            // Score update - quick pulse
            score: [20, 20, 20],
            // Swipe pattern - smooth drag feel
            swipe: 15,
            // Modal open - attention grab
            modalOpen: [10, 30, 20],
            // Modal close - dismissive
            modalClose: 20,
            // Reaction sent - fun burst
            reaction: [10, 20, 10, 20, 30],
            // Table tap - pool ball feel
            tableTap: [8, 40, 15],
            // Win game - celebration
            winGame: [50, 50, 50, 100, 50, 50, 50],
            // Golden break - ultimate celebration
            goldenBreak: [30, 30, 30, 30, 50, 50, 100, 100],
            // Button press - subtle feedback
            button: 12,
            // Long press - building tension
            longPress: [10, 10, 10, 10, 10, 30],
        };
        
        // Main haptic feedback function
        function haptic(pattern = 'light') {
            if (!navigator.vibrate) return false;
            
            try {
                const vibration = HapticPatterns[pattern] || pattern;
                navigator.vibrate(vibration);
                return true;
            } catch (e) {
                // Vibration not supported or blocked
                return false;
            }
        }
        
        // Quick haptic helpers
        const hapticLight = () => haptic('light');
        const hapticMedium = () => haptic('medium');
        const hapticStrong = () => haptic('strong');
        const hapticSuccess = () => haptic('success');
        const hapticError = () => haptic('error');
        
        // Auto-add haptic feedback to interactive buttons on touch
        // Only fires haptic on tap (not scroll) by tracking touch movement
        let hapticTouchStart = null;
        const SCROLL_THRESHOLD = 10; // pixels of movement before considered a scroll
        
        document.addEventListener('touchstart', function(e) {
            const target = e.target.closest('button, .reaction-btn, .table-card.live, .manager-ball-btn, .manager-btn, .manager-breaking-btn, .manager-group-btn, .manager-special-btn, .manager-win-btn, .start-match-btn, .complete-match-btn');
            if (target) {
                // Store touch info to check on touchend
                hapticTouchStart = {
                    target: target,
                    x: e.touches[0].clientX,
                    y: e.touches[0].clientY,
                    time: Date.now()
                };
            } else {
                hapticTouchStart = null;
            }
        }, { passive: true });
        
        document.addEventListener('touchmove', function(e) {
            // If touch moved too much, cancel the haptic
            if (hapticTouchStart && e.touches.length > 0) {
                const dx = Math.abs(e.touches[0].clientX - hapticTouchStart.x);
                const dy = Math.abs(e.touches[0].clientY - hapticTouchStart.y);
                if (dx > SCROLL_THRESHOLD || dy > SCROLL_THRESHOLD) {
                    hapticTouchStart = null; // Cancel - user is scrolling
                }
            }
        }, { passive: true });
        
        document.addEventListener('touchend', function(e) {
            // Only fire haptic if touch didn't move much (was a tap, not scroll)
            if (hapticTouchStart) {
                const target = hapticTouchStart.target;
                const elapsed = Date.now() - hapticTouchStart.time;
                
                // Only fire if it was a quick tap (under 500ms)
                if (elapsed < 500) {
                    // Different haptics for different element types
                    if (target.classList.contains('table-card')) {
                        haptic('tableTap');
                    } else if (target.classList.contains('reaction-btn')) {
                        // Handled separately in sendReaction
                    } else if (target.classList.contains('manager-ball-btn') || target.classList.contains('manager-ball')) {
                        haptic('ballPocket');
                    } else if (target.classList.contains('manager-win-btn') || target.classList.contains('manager-special-btn')) {
                        haptic('medium');
                    } else {
                        haptic('button');
                    }
                }
                
                hapticTouchStart = null;
            }
        }, { passive: true });
        
        // Prevent double-tap zoom on buttons
        let lastTouchEnd = 0;
        document.addEventListener('touchend', function(event) {
            const now = Date.now();
            if (now - lastTouchEnd <= 300) {
                event.preventDefault();
            }
            lastTouchEnd = now;
        }, false);
        
        // Prevent pull-to-refresh on mobile
        let touchStartY = 0;
        document.addEventListener('touchstart', function(event) {
            touchStartY = event.touches[0].clientY;
        }, { passive: true });
        
        document.addEventListener('touchmove', function(event) {
            if (window.scrollY === 0 && event.touches[0].clientY > touchStartY) {
                event.preventDefault();
            }
        }, { passive: false });
        
        let eventSource = null;
        let reconnectAttempts = 0;
        const maxReconnectAttempts = 10;
        let isReconnecting = false;
        let lastConnectTime = 0;
        let managerMode = false;
        let managerAuthenticated = false;
        let currentManagerMatch = null;
        let currentManagerGame = null;
        let openScorecardMatchId = null;  // Track which match is open in scorecard modal
        let openScorecardIsManager = false;
        let lastQueuePanelHash = null;  // Track queue panel state to avoid unnecessary redraws (null = first load)
        let lastMainUIHash = null;  // Track main UI state to avoid flickering
        let isOffline = !navigator.onLine;  // Track offline state
        let offlineDBReady = false;  // Track if IndexedDB is ready

        const BALL_COLORS = {
            1: 'solid-1', 2: 'solid-2', 3: 'solid-3', 4: 'solid-4',
            5: 'solid-5', 6: 'solid-6', 7: 'solid-7', 8: 'solid-8',
            9: 'stripe-9', 10: 'stripe-10', 11: 'stripe-11', 12: 'stripe-12',
            13: 'stripe-13', 14: 'stripe-14', 15: 'stripe-15'
        };
        
        // Avatar colors matching the desktop app
        const AVATAR_COLORS = [
            ["#FF6B6B", "#C62828"], ["#4ECDC4", "#00897B"], ["#45B7D1", "#0277BD"],
            ["#96CEB4", "#388E3C"], ["#FFEAA7", "#F9A825"], ["#DDA0DD", "#7B1FA2"],
            ["#F8B500", "#E65100"], ["#85C1E9", "#1565C0"], ["#BB8FCE", "#6A1B9A"],
            ["#98D8C8", "#00695C"], ["#F7DC6F", "#FBC02D"], ["#FF69B4", "#C2185B"]
        ];
        
        function getAvatarColorForName(name) {
            // Simple hash to get consistent color for a name
            let hash = 0;
            for (let i = 0; i < name.length; i++) {
                hash = name.charCodeAt(i) + ((hash << 5) - hash);
            }
            return AVATAR_COLORS[Math.abs(hash) % AVATAR_COLORS.length];
        }
        
        function getInitials(name) {
            if (!name) return '?';
            const parts = name.trim().split(' ');
            if (parts.length >= 2) {
                return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
            } else if (parts[0].length >= 2) {
                return parts[0].substring(0, 2).toUpperCase();
            }
            return parts[0][0].toUpperCase();
        }
        
        function getProfilePictureUrl(profilePicture) {
            // Extract filename from a file path and return the API URL
            if (!profilePicture) return null;
            // Handle Windows and Unix paths
            const parts = profilePicture.replace(/\\\\/g, '/').split('/');
            const filename = parts[parts.length - 1];
            return `/api/pfp/${encodeURIComponent(filename)}`;
        }
        
        function isFilePath(profilePicture) {
            // Check if this is an actual file path (not emoji: or color: prefix)
            if (!profilePicture) return false;
            if (profilePicture.startsWith('emoji:')) return false;
            if (profilePicture.startsWith('color:')) return false;
            // If it contains path separators or file extensions, it's likely a file
            return profilePicture.includes('/') || profilePicture.includes('\\\\') || 
                   profilePicture.match(/\\.(jpg|jpeg|png|gif)$/i);
        }
        
        function createAvatar(name, profilePicture) {
            // Check if it's an actual image file
            if (isFilePath(profilePicture)) {
                const url = getProfilePictureUrl(profilePicture);
                return `<img class="player-avatar" src="${url}" alt="${escapeHtml(name)}" onerror="this.outerHTML=createAvatarFallback('${escapeHtml(name)}', false)">`;
            }
            
            // Check if it's an emoji avatar
            if (profilePicture && profilePicture.startsWith('emoji:')) {
                const emoji = profilePicture.substring(6);
                return `<div class="player-avatar emoji">${emoji}</div>`;
            }
            
            // Generate initials-based avatar
            return createAvatarFallback(name, false);
        }
        
        function createAvatarFallback(name, isMini) {
            const colors = getAvatarColorForName(name);
            const initials = getInitials(name);
            const className = isMini ? 'mini-avatar' : 'player-avatar';
            return `<div class="${className}" style="background: linear-gradient(135deg, ${colors[0]}, ${colors[1]})">${initials}</div>`;
        }
        
        function createMiniAvatar(name, profilePicture) {
            // Check if it's an actual image file
            if (isFilePath(profilePicture)) {
                const url = getProfilePictureUrl(profilePicture);
                return `<img class="mini-avatar" src="${url}" alt="${escapeHtml(name)}" onerror="this.outerHTML=createAvatarFallback('${escapeHtml(name)}', true)">`;
            }
            
            // Smaller version for stat cards
            if (profilePicture && profilePicture.startsWith('emoji:')) {
                const emoji = profilePicture.substring(6);
                return `<div class="mini-avatar emoji">${emoji}</div>`;
            }
            
            return createAvatarFallback(name, true);
        }
        
        function connectSSE() {
            // Prevent rapid reconnection attempts
            const now = Date.now();
            if (now - lastConnectTime < 2000) {
                console.log('Throttling SSE reconnection');
                return;
            }
            lastConnectTime = now;
            
            if (isReconnecting) {
                return;
            }
            
            if (eventSource) {
                eventSource.close();
                eventSource = null;
            }
            
            try {
                eventSource = new EventSource('/api/stream');
                
                eventSource.onopen = function() {
                    console.log('Connected to live updates');
                    reconnectAttempts = 0;
                    isReconnecting = false;
                    updateConnectionStatus(true);
                };
                
                eventSource.onmessage = function(event) {
                    try {
                        const data = JSON.parse(event.data);
                        updateUI(data);
                        
                        // Refresh scorecard modal if it's open (but not too frequently)
                        if (openScorecardMatchId) {
                            refreshOpenScorecard();
                        }
                        
                        // Check for new reactions
                        if (data.reactions && data.reactions.length > 0) {
                            const latest = data.reactions[data.reactions.length - 1];
                            if (latest) {
                                showLocalReaction(latest.emoji);
                            }
                        }
                    } catch (parseError) {
                        console.error('Error parsing SSE data:', parseError);
                    }
                };
                
                eventSource.onerror = function() {
                    console.log('SSE connection error');
                    updateConnectionStatus(false);
                    
                    if (eventSource) {
                        eventSource.close();
                        eventSource = null;
                    }
                    
                    if (reconnectAttempts < maxReconnectAttempts && !isReconnecting) {
                        reconnectAttempts++;
                        isReconnecting = true;
                        setTimeout(function() {
                            isReconnecting = false;
                            connectSSE();
                        }, 3000);
                    }
                };
            } catch (e) {
                console.error('Error creating EventSource:', e);
                isReconnecting = false;
            }
        }
        
        function updateConnectionStatus(connected) {
            const dot = document.getElementById('status-dot');
            const text = document.getElementById('status-text');
            
            if (connected) {
                dot.classList.remove('disconnected');
                text.textContent = 'Connected';
                // Light haptic on reconnection (only if we were disconnected)
                if (text.dataset.wasDisconnected) {
                    haptic('light');
                    text.dataset.wasDisconnected = '';
                }
            } else {
                dot.classList.add('disconnected');
                text.textContent = 'Reconnecting...';
                text.dataset.wasDisconnected = 'true';
            }
        }
        
        function updateUI(data) {
            document.getElementById('update-time').textContent = data.timestamp;

            // Cache data to IndexedDB for offline use (only if not cached data)
            if (!data._cached && offlineDBReady) {
                saveToOfflineCache(data);
            }

            // Show cache indicator if using cached data
            const updateTimeEl = document.getElementById('update-time');
            if (data._cached) {
                updateTimeEl.textContent = data.timestamp + ' (cached)';
                updateTimeEl.style.color = '#ff9800';
            } else {
                updateTimeEl.style.color = '';
            }

            // Create a hash of the data (excluding timestamp) to detect actual changes
            const dataHash = JSON.stringify({
                tables: data.tables?.map(t => ({id: t.match_id, s: t.status, t1g: t.team1_games, t2g: t.team2_games, t1p: t.team1_points, t2p: t.team2_points})),
                queue: data.queue?.map(q => q.id),
                completed: data.completed_matches?.map(m => m.id),
                live: data.live_matches?.map(m => m.id),
                round: data.round_progress,
                leaderboard: data.leaderboard?.slice(0, 5).map(l => l.points),  // Just check top 5 for changes
                managerMode: managerMode
            });

            // Skip full redraw if nothing changed
            if (dataHash === lastMainUIHash) {
                return;
            }
            lastMainUIHash = dataHash;
            
            let html = '';
            
            // Round Progress Section (if rounds exist)
            if (data.round_progress && data.round_progress.total_rounds > 0) {
                const rp = data.round_progress;
                const progressPercent = rp.total > 0 ? Math.round((rp.completed / rp.total) * 100) : 0;
                html += `
                    <div class="section">
                        <div class="round-progress-card">
                            <div class="round-info">
                                <span class="round-number">Round ${rp.current_round}</span>
                                <span class="round-of">of ${rp.total_rounds}</span>
                            </div>
                            <div class="round-stats">
                                <span class="round-live">${rp.live} live</span>
                                <span class="round-sep">•</span>
                                <span class="round-done">${rp.completed}/${rp.total} done</span>
                            </div>
                            <div class="round-progress-bar">
                                <div class="round-progress-fill" style="width: ${progressPercent}%"></div>
                            </div>
                        </div>
                    </div>
                `;
            }
            
            // Tables Section (Visual Overview) - Main focus
            if (data.tables && data.tables.length > 0) {
                const liveTables = data.tables.filter(t => t.status === 'live').length;
                const availableTables = data.tables.length - liveTables;
                html += `
                    <div class="section">
                        <div class="section-title">🎱 Pool Hall <span style="font-weight:normal;font-size:0.85em;color:var(--text-secondary)">(${liveTables} active, ${availableTables} open)</span></div>
                        <div class="tables-grid">
                            ${data.tables.map(t => createTableCard(t)).join('')}
                        </div>
                    </div>
                `;
            }
            
            // Manager Mode Panel (only show if manager mode is active)
            if (managerMode) {
                html += `
                    <div class="section">
                        <div id="manager-panel" class="manager-panel active">
                            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px;">
                                <h2 style="margin: 0;">🔧 Manager Mode - Score Entry</h2>
                                <div style="display: flex; gap: 8px;">
                                    <button onclick="openPaymentPortal()" style="background: #238636; color: white; border: none; padding: 8px 16px; border-radius: 6px; cursor: pointer; font-size: 14px; font-weight: 600;">
                                        💳 Payment Portal
                                    </button>
                                    <button id="google-sheet-btn" onclick="updateGoogleSheet()" style="background: #1a73e8; color: white; border: none; padding: 8px 16px; border-radius: 6px; cursor: pointer; font-size: 14px; font-weight: 600;">
                                        📊 Update Google Sheet
                                    </button>
                                </div>
                            </div>
                            
                            <div class="manager-match-selector">
                                <label style="display: block; margin-bottom: 8px; font-weight: bold;">Select Match:</label>
                                <select id="manager-match-select" onchange="loadManagerMatch()">
                                    <option value="">-- Select a match --</option>
                                </select>
                            </div>
                            
                            <div id="manager-match-content" style="display: none;">
                                <div class="manager-controls">
                                    <div class="manager-team-controls">
                                        <h3 id="manager-team1-name">Team 1</h3>
                                        <div class="manager-balls-grid" id="manager-team1-balls"></div>
                                    </div>
                                    <div class="manager-team-controls">
                                        <h3 id="manager-team2-name">Team 2</h3>
                                        <div class="manager-balls-grid" id="manager-team2-balls"></div>
                                    </div>
                                </div>
                                
                                <div style="text-align: center; margin: 20px 0;">
                                    <div style="font-size: 1.5em; font-weight: bold; margin-bottom: 10px;">
                                        <span id="manager-team1-score" style="color: var(--green);">0</span>
                                        <span style="margin: 0 15px;">-</span>
                                        <span id="manager-team2-score" style="color: var(--blue);">0</span>
                                    </div>
                                </div>
                                
                                <div class="manager-actions">
                                    <button class="manager-btn team1" onclick="managerWinGame(1)">
                                        Team 1 Wins Game
                                    </button>
                                    <button class="manager-btn team2" onclick="managerWinGame(2)">
                                        Team 2 Wins Game
                                    </button>
                                </div>
                            </div>
                        </div>
                    </div>
                    
                    <div class="section">
                        <div id="manager-queue-panel" class="manager-panel active">
                            <h2 style="margin-bottom: 15px;">📋 Start Match from Queue</h2>
                            <p style="color: var(--text-secondary); font-size: 0.9em; margin-bottom: 15px;">
                                Select a match from the queue and assign it to an available table.
                            </p>
                            <div id="manager-queue-content">
                                <div style="text-align: center; color: var(--text-secondary);">Loading...</div>
                            </div>
                        </div>
                    </div>
                `;
            }
            
            // Queue Section - Up Next
            if (data.queue && data.queue.length > 0) {
                html += `
                    <div class="section">
                        <div class="section-title">⏳ Up Next</div>
                        <div class="queue-list">
                            <div class="queue-header">
                                <span>Queue</span>
                                <span>${data.queue.length} waiting</span>
                            </div>
                            ${data.queue.slice(0, 5).map(q => createQueueItem(q)).join('')}
                            ${data.queue.length > 5 ? `<div class="queue-item" style="justify-content:center;color:var(--text-secondary);">+ ${data.queue.length - 5} more</div>` : ''}
                        </div>
                    </div>
                `;
            }
            
            // Completed matches section
            if (data.completed_matches && data.completed_matches.length > 0) {
                html += `
                    <div class="section">
                        <div class="section-title">✅ Recent Results</div>
                        ${data.completed_matches.map(m => createMatchCard(m, true)).join('')}
                    </div>
                `;
            }
            
            // League Stats section
            if (data.league_stats && data.league_stats.total_games > 0) {
                const ls = data.league_stats;
                html += `
                    <div class="section">
                        <div class="section-title">📈 League Stats</div>
                        <div class="league-stats">
                            <div class="stat-card highlight">
                                <div class="stat-icon">🎱</div>
                                <div class="stat-number">${ls.total_games}</div>
                                <div class="stat-desc">Games Played</div>
                            </div>
                            <div class="stat-card">
                                <div class="stat-icon">⭐</div>
                                <div class="stat-number">${ls.total_golden}</div>
                                <div class="stat-desc">Golden Breaks</div>
                            </div>
                            ${ls.top_scorer ? `
                            <div class="stat-card">
                                <div class="stat-icon">👑</div>
                                <div class="stat-number">${ls.top_scorer_pts}</div>
                                <div class="stat-desc">Top Scorer</div>
                                <div class="stat-player">${createMiniAvatar(ls.top_scorer, ls.top_scorer_pfp)} ${escapeHtml(ls.top_scorer)}</div>
                            </div>
                            ` : ''}
                            ${ls.best_win_rate ? `
                            <div class="stat-card">
                                <div class="stat-icon">🎯</div>
                                <div class="stat-number">${ls.best_win_rate_pct}%</div>
                                <div class="stat-desc">Best Win Rate</div>
                                <div class="stat-player">${createMiniAvatar(ls.best_win_rate, ls.best_win_rate_pfp)} ${escapeHtml(ls.best_win_rate)}</div>
                            </div>
                            ` : ''}
                        </div>
                    </div>
                `;
            }
            
            // Leaderboard section (show all players)
            if (data.leaderboard && data.leaderboard.length > 0) {
                html += `
                    <div class="section">
                        <div class="section-title">🏆 Leaderboard <span style="font-weight:normal;font-size:0.85em;color:var(--text-secondary)">(${data.leaderboard.length} players)</span></div>
                        <div class="leaderboard">
                            ${data.leaderboard.map((p, i) => createLeaderboardRow(p, i)).join('')}
                        </div>
                    </div>
                `;
            }
            
            // Empty state
            if (!data.tables?.some(t => t.status === 'live') && !data.queue?.length && !data.completed_matches?.length) {
                html = `
                    <div class="empty-state">
                        <div class="emoji">🎱</div>
                        <div>No matches yet tonight</div>
                        <div style="margin-top: 10px; font-size: 0.9em;">
                            Matches will appear here when they start
                        </div>
                    </div>
                `;
            }
            
            document.getElementById('content').innerHTML = html;
            
            // Reload manager matches dropdown and queue panel if manager mode is active
            if (managerMode) {
                loadManagerMatches();
                loadManagerQueuePanel();
            }
        }
        
        function createTableCard(table) {
            const statusClass = table.status === 'live' ? 'live' : 'available';
            const statusText = table.status === 'live' ? 'LIVE' : 'Open';
            // In manager mode, always allow clicking on live matches to open scorecard
            const clickHandler = (table.match_id && (table.status === 'live' || managerMode)) ? `onclick="openScorecard(${table.match_id}, ${managerMode ? 'true' : 'false'})"` : '';
            
            let visualContent = '';
            let teamsContent = '';
            
            if (table.status === 'live') {
                // Show large score on the table visual
                visualContent = `
                    <div class="match-score">${table.team1_games} - ${table.team2_games}</div>
                    <div class="match-points">${table.team1_points} - ${table.team2_points} pts</div>
                `;
                
                // Team names are already first names from server
                const team1Display = escapeHtml(table.team1);
                const team2Display = escapeHtml(table.team2);
                
                // Determine group labels (solids/stripes)
                let team1GroupLabel = '';
                let team2GroupLabel = '';
                if (table.team1_group === 'solids') {
                    team1GroupLabel = '<span class="group-badge solids">⚫ Solids</span>';
                    team2GroupLabel = '<span class="group-badge stripes">⬜ Stripes</span>';
                } else if (table.team1_group === 'stripes') {
                    team1GroupLabel = '<span class="group-badge stripes">⬜ Stripes</span>';
                    team2GroupLabel = '<span class="group-badge solids">⚫ Solids</span>';
                }
                
                teamsContent = `
                    <div class="table-teams">
                        <div class="table-team team1"><span class="team-number-small team1-small">T1</span> ${team1Display} ${team1GroupLabel}</div>
                        <div class="table-vs">vs</div>
                        <div class="table-team team2"><span class="team-number-small team2-small">T2</span> ${team2Display} ${team2GroupLabel}</div>
                    </div>
                `;
            } else {
                visualContent = `<div class="empty">Ready</div>`;
                teamsContent = `<div class="table-waiting">Waiting for game</div>`;
            }
            
            return `
                <div class="table-card ${statusClass}" ${clickHandler}>
                    <div class="table-header">
                        <span class="table-number">Table ${table.table_number}</span>
                        <span class="table-status">${statusText}</span>
                    </div>
                    <div class="table-visual ${table.status === 'available' ? 'empty' : ''}">
                        ${visualContent}
                    </div>
                    ${teamsContent}
                    ${table.status === 'live' ? `<div class="table-tap-hint">Tap for scorecard</div>` : ''}
                </div>
            `;
        }
        
        function createQueueItem(item) {
            const team1Badge = item.team1_ai_name
                ? `<span class="ai-team-badge">${escapeHtml(item.team1_ai_name)}</span> `
                : '';
            const team2Badge = item.team2_ai_name
                ? `<span class="ai-team-badge">${escapeHtml(item.team2_ai_name)}</span> `
                : '';
            return `
                <div class="queue-item">
                    <span class="queue-position">#${item.position}</span>
                    <span class="queue-teams">${team1Badge}${escapeHtml(item.team1)} vs ${team2Badge}${escapeHtml(item.team2)}</span>
                    ${item.round > 1 ? `<span class="queue-round">R${item.round}</span>` : ''}
                </div>
            `;
        }

        function createMatchCard(match, completed) {
            const finals = match.is_finals ? 'finals' : '';
            const completedClass = completed ? 'completed' : '';
            // In manager mode, always allow clicking to open scorecard
            const clickHandler = `onclick="openScorecard(${match.id}, ${managerMode ? 'true' : 'false'})"`;
            const team1Badge = match.team1_ai_name
                ? `<div class="ai-team-badge">${escapeHtml(match.team1_ai_name)}</div>`
                : '';
            const team2Badge = match.team2_ai_name
                ? `<div class="ai-team-badge">${escapeHtml(match.team2_ai_name)}</div>`
                : '';

            return `
                <div class="match-card ${finals} ${completedClass}" ${clickHandler} style="cursor:pointer">
                    <div class="match-header">
                        <span>${match.is_finals ? '🏆 Finals' : 'Best of ' + match.best_of}</span>
                        <span class="table-badge">Table ${match.table}</span>
                    </div>
                    <div class="teams-container">
                        <div class="team">
                            ${team1Badge}
                            <div class="team-name"><span class="team-number-small team1-small">T1</span> ${escapeHtml(match.team1)}</div>
                            <div class="score-box">
                                <div class="game-score">${match.team1_games}</div>
                                <div class="points-score">${match.team1_points} pts</div>
                            </div>
                        </div>
                        <div class="vs-divider">VS</div>
                        <div class="team">
                            ${team2Badge}
                            <div class="team-name"><span class="team-number-small team2-small">T2</span> ${escapeHtml(match.team2)}</div>
                            <div class="score-box">
                                <div class="game-score">${match.team2_games}</div>
                                <div class="points-score">${match.team2_points} pts</div>
                            </div>
                        </div>
                    </div>
                </div>
            `;
        }
        
        function createLeaderboardRow(player, index) {
            const isTop3 = index < 3 ? 'top-3' : '';
            const rankDisplay = index === 0 ? '🥇' : index === 1 ? '🥈' : index === 2 ? '🥉' : (index + 1);
            const winRateColor = player.win_rate >= 50 ? 'var(--green)' : 'var(--red)';
            const goldenBreaks = player.golden_breaks || 0;
            const avatar = createAvatar(player.name, player.profile_picture);
            
            return `
                <div class="leaderboard-row ${isTop3}">
                    <div class="player-main">
                        <div class="rank">${rankDisplay}</div>
                        ${avatar}
                        <div class="player-name">${escapeHtml(player.name)}</div>
                        <div class="points-badge">${player.points} pts</div>
                    </div>
                    <div class="player-stats">
                        <div class="stat">
                            <span class="stat-value wins">${player.wins}W</span>
                            <span class="stat-label">-</span>
                            <span class="stat-value losses">${player.losses || 0}L</span>
                        </div>
                        <div class="stat">
                            <span class="stat-label">Games:</span>
                            <span class="stat-value">${player.games}</span>
                        </div>
                        <div class="stat">
                            <span class="stat-label">Win%:</span>
                            <span class="stat-value" style="color: ${winRateColor}">${player.win_rate}%</span>
                            <div class="win-rate-bar">
                                <div class="win-rate-fill" style="width: ${player.win_rate}%; background: ${winRateColor}"></div>
                            </div>
                        </div>
                        <div class="stat">
                            <span class="stat-label">Avg:</span>
                            <span class="stat-value" style="color: var(--blue)">${player.avg_points || 0}</span>
                        </div>
                        ${goldenBreaks > 0 ? `
                        <div class="stat">
                            <span class="stat-value golden">⭐ ${goldenBreaks}</span>
                            <span class="stat-label">golden</span>
                        </div>
                        ` : ''}
                    </div>
                </div>
            `;
        }
        
        function openScorecard(matchId, isManagerMode = false) {
            const modal = document.getElementById('scorecard-modal');
            const content = document.getElementById('scorecard-content');
            const reactionBar = document.querySelector('.reaction-bar');
            
            // Haptic feedback - modal opening
            haptic('modalOpen');
            
            // Track which match is open
            openScorecardMatchId = matchId;
            openScorecardIsManager = isManagerMode;
            
            // Hide reaction bar when modal is open
            if (reactionBar) {
                reactionBar.style.display = 'none';
            }
            
            content.innerHTML = '<div class="empty-state">Loading...</div>';
            modal.classList.add('active');
            
            loadScorecardData(matchId, isManagerMode);
        }
        
        function loadScorecardData(matchId, isManagerMode) {
            const content = document.getElementById('scorecard-content');
            const endpoint = isManagerMode ? `/api/manager/match/${matchId}` : `/api/match/${matchId}`;
            
            fetch(endpoint)
                .then(r => r.json())
                .then(data => {
                    if (data.error) {
                        content.innerHTML = `<div class="empty-state">${data.error}</div>`;
                        return;
                    }
                    // If manager mode, use manager match data structure
                    const matchData = isManagerMode ? data.match : data;
                    const gamesData = isManagerMode ? data.games : (data.games || []);
                    content.innerHTML = renderScorecard(matchData, gamesData, isManagerMode);
                })
                .catch(err => {
                    content.innerHTML = `<div class="empty-state">Failed to load</div>`;
                });
        }
        
        function refreshOpenScorecard() {
            if (openScorecardMatchId) {
                loadScorecardData(openScorecardMatchId, openScorecardIsManager);
            }
        }
        
        // Timeline event icons and formatting
        const TIMELINE_ICONS = {
            'ball_pocketed': '🎱',
            'game_win': '🏆',
            'golden_break': '⭐',
            'early_8ball': '❌',
            'group_assigned': '🎯'
        };

        function renderTimeline(events, matchData) {
            if (!events || events.length === 0) {
                return '<div class="timeline-empty">No events recorded yet</div>';
            }

            // Group events by game number
            const eventsByGame = {};
            events.forEach(e => {
                const gameNum = e.game_number;
                if (!eventsByGame[gameNum]) {
                    eventsByGame[gameNum] = [];
                }
                eventsByGame[gameNum].push(e);
            });

            let html = '<div class="timeline-container">';
            html += '<div class="timeline-header">📋 Match Timeline</div>';

            Object.keys(eventsByGame).sort((a, b) => a - b).forEach(gameNum => {
                const gameEvents = eventsByGame[gameNum];
                html += `<div class="timeline-game-section">`;
                html += `<div class="timeline-game-header">Game ${gameNum}</div>`;

                gameEvents.forEach(event => {
                    const icon = TIMELINE_ICONS[event.event_type] || '📌';
                    const teamClass = event.team === 1 ? 'team1' : event.team === 2 ? 'team2' : '';
                    const time = formatTimelineTime(event.timestamp);
                    const description = formatTimelineEvent(event, matchData);

                    html += `
                        <div class="timeline-event ${teamClass}">
                            <span class="timeline-icon">${icon}</span>
                            <div class="timeline-content">
                                <span class="timeline-desc">${description}</span>
                                <span class="timeline-time">${time}</span>
                            </div>
                        </div>
                    `;
                });

                html += '</div>';
            });

            html += '</div>';
            return html;
        }

        function formatTimelineTime(timestamp) {
            if (!timestamp) return '';
            try {
                const date = new Date(timestamp.replace(' ', 'T'));
                return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
            } catch (e) {
                return timestamp.split(' ')[1] || timestamp;
            }
        }

        function formatTimelineEvent(event, matchData) {
            const team1Name = matchData?.team1 || 'Team 1';
            const team2Name = matchData?.team2 || 'Team 2';
            const teamName = event.team === 1 ? team1Name : event.team === 2 ? team2Name : '';
            const data = event.event_data || {};

            switch (event.event_type) {
                case 'ball_pocketed':
                    return `${teamName} pocketed ball ${data.ball || '?'}`;
                case 'game_win':
                    return `${teamName} wins game! (${data.team1_wins || 0}-${data.team2_wins || 0})`;
                case 'golden_break':
                    return `${teamName} gets a GOLDEN BREAK!`;
                case 'early_8ball':
                    const loser = data.losing_team === 1 ? team1Name : team2Name;
                    return `${loser} early 8-ball - ${teamName} wins`;
                case 'group_assigned':
                    const group = data.team1_group === 'solids' ? 'Solids' : 'Stripes';
                    return `Groups assigned - ${team1Name}: ${group}`;
                default:
                    return event.event_type.replace(/_/g, ' ');
            }
        }

        function renderScorecard(match, gamesData = null, isManagerMode = false) {
            const statusText = match.is_complete ? 'Complete' : 'In Progress';
            
            // Determine group labels for team headers
            let team1GroupBadge = '';
            let team2GroupBadge = '';
            if (match.team1_group === 'solids') {
                team1GroupBadge = '<span class="group-badge solids">⚫ Solids</span>';
                team2GroupBadge = '<span class="group-badge stripes">⬜ Stripes</span>';
            } else if (match.team1_group === 'stripes') {
                team1GroupBadge = '<span class="group-badge stripes">⬜ Stripes</span>';
                team2GroupBadge = '<span class="group-badge solids">⚫ Solids</span>';
            }
            
            // Use provided gamesData or match.games
            const games = gamesData || match.games || [];
            
            // Find current/active game (for showing pool table)
            let currentGame = null;
            if (games.length > 0) {
                currentGame = games.find(g => g.winner_team === 0 || !g.winner_team) || games[games.length - 1];
            }
            
            let gamesHtml = '';
            if (games.length > 0) {
                gamesHtml = games.map(g => {
                    const winnerIcon = g.winner_team === 1 ? '<span class="winner-badge">🏆</span>' : '';
                    const winnerIcon2 = g.winner_team === 2 ? '<span class="winner-badge">🏆</span>' : '';
                    const goldenBadge = g.golden_break ? '<span class="golden-badge">⭐ Golden Break</span>' : '';
                    const isCurrentGame = currentGame && g.game_number === currentGame.game_number;
                    const isActiveGame = !g.winner_team; // Game still in progress
                    
                    // Handle both string JSON and object formats
                    let ballsPocketed = g.balls_pocketed;
                    if (typeof ballsPocketed === 'string') {
                        try {
                            ballsPocketed = JSON.parse(ballsPocketed);
                        } catch (e) {
                            ballsPocketed = {};
                        }
                    }
                    if (!ballsPocketed) ballsPocketed = {};
                    
                    // Always render pool table for active games (interactive in manager mode)
                    let poolTableHtml = '';
                    if (isActiveGame) {
                        poolTableHtml = renderPoolTable(g, match, ballsPocketed, isManagerMode);
                    }
                    
                    // Progress indicators (always show for games with group assignment)
                    let progressHtml = '';
                    if (g.team1_group) {
                        progressHtml = renderProgressIndicators(g, ballsPocketed);
                    }
                    
                    return `
                        <div class="scorecard-game ${isCurrentGame && isActiveGame ? 'current-game' : ''} ${!isActiveGame ? 'completed-game' : ''}">
                            <div class="scorecard-game-header">
                                <span>Game ${g.game_number} ${isCurrentGame && isActiveGame ? '<span style="color:var(--green);font-size:0.8em;">(Live)</span>' : ''}</span>
                                <span>${g.team1_group ? (g.team1_group === 'solids' ? 'T1: Solids' : 'T1: Stripes') : ''}</span>
                                ${goldenBadge}
                            </div>
                            <div class="scorecard-game-scores">
                                <span class="scorecard-game-score" style="color:var(--green)">${g.team1_score} ${winnerIcon}</span>
                                <span style="color:var(--text-secondary)">-</span>
                                <span class="scorecard-game-score" style="color:var(--blue)">${winnerIcon2} ${g.team2_score}</span>
                            </div>
                            ${poolTableHtml}
                            ${progressHtml}
                        </div>
                    `;
                }).join('');
            } else {
                gamesHtml = '<div class="empty-state" style="padding:15px">No games recorded yet</div>';
            }
            
            // Render timeline if available (for live matches)
            const timelineHtml = !match.is_complete && match.timeline && match.timeline.length > 0
                ? renderTimeline(match.timeline, match)
                : '';

            return `
                <div class="modal-header">
                    <h2>${match.is_finals ? '🏆 Finals' : 'Match'}</h2>
                    <div class="table-info">Table ${match.table} • ${statusText}</div>
                </div>

                <div class="scorecard-teams">
                    <div class="scorecard-team">
                        <div class="scorecard-team-name">
                            <span class="team-number-badge team1-badge">Team 1</span>
                            ${escapeHtml(match.team1)} ${team1GroupBadge}
                        </div>
                        <div class="scorecard-team-score">${match.team1_games}</div>
                    </div>
                    <div style="color:var(--text-secondary);padding:20px">vs</div>
                    <div class="scorecard-team">
                        <div class="scorecard-team-name">
                            <span class="team-number-badge team2-badge">Team 2</span>
                            ${escapeHtml(match.team2)} ${team2GroupBadge}
                        </div>
                        <div class="scorecard-team-score">${match.team2_games}</div>
                    </div>
                </div>

                <div style="margin-bottom:10px;color:var(--text-secondary);font-size:0.85em;text-align:center">
                    Best of ${match.best_of}
                </div>

                ${gamesHtml}

                ${timelineHtml}
            `;
        }
        
        function renderPoolTable(game, match, ballsPocketed, isManagerMode) {
            // For manager mode, use the enhanced scorecard
            if (isManagerMode) {
                return renderManagerPoolTable(game, match, ballsPocketed);
            }
            
            // Regular spectator view
            const solidsRow = [1, 2, 3, 4, 5, 6, 7, 8];
            const stripesRow = [9, 10, 11, 12, 13, 14, 15];
            
            function createBallElement(ballNum) {
                const isStripe = ballNum >= 9 && ballNum <= 15;
                const pocketedBy = ballsPocketed ? ballsPocketed[ballNum] : null;
                
                let stateClass = 'on-table';
                let stateLabel = '';
                if (pocketedBy === 1) {
                    stateClass = 'pocketed-team1';
                    stateLabel = 'T1';
                } else if (pocketedBy === 2) {
                    stateClass = 'pocketed-team2';
                    stateLabel = 'T2';
                }
                
                return `
                    <div class="pool-ball-btn ${stateClass} ${isStripe ? 'stripe' : 'solid'}" 
                         title="Ball ${ballNum}${pocketedBy ? ' - Team ' + pocketedBy : ' - On Table'}">
                        <div class="ball-inner ${BALL_COLORS[ballNum]}">
                            <span class="ball-num">${ballNum}</span>
                        </div>
                        ${stateLabel ? `<span class="ball-state-label">${stateLabel}</span>` : ''}
                    </div>
                `;
            }
            
            const solidsHtml = solidsRow.map(createBallElement).join('');
            const stripesHtml = stripesRow.map(createBallElement).join('');
            
            let groupInfo = '';
            if (game.team1_group) {
                const t1Group = game.team1_group === 'solids' ? '⚫ Solids' : '⬜ Stripes';
                const t2Group = game.team1_group === 'solids' ? '⬜ Stripes' : '⚫ Solids';
                groupInfo = `
                    <div class="group-assignment">
                        <span class="team1-group">Team 1: ${t1Group}</span>
                        <span class="team2-group">Team 2: ${t2Group}</span>
                    </div>
                `;
            }
            
            return `
                <div class="pool-table-scorecard">
                    ${groupInfo}
                    <div class="balls-section">
                        <div class="balls-label">Solids (1-7) + 8</div>
                        <div class="balls-row-grid">${solidsHtml}</div>
                    </div>
                    <div class="balls-section">
                        <div class="balls-label">Stripes (9-15)</div>
                        <div class="balls-row-grid">${stripesHtml}</div>
                    </div>
                </div>
            `;
        }
        
        function renderManagerPoolTable(game, match, ballsPocketed) {
            // Enhanced manager mode pool table with larger, more touch-friendly balls
            const allBalls = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15];
            
            // Get current breaking team and group assignment (needed for ball assignment)
            const breakingTeam = game.breaking_team || 1;
            
            function createManagerBall(ballNum) {
                const isStripe = ballNum >= 9 && ballNum <= 15;
                // Check both string and number keys since JSON may use strings
                // Ensure we get a clean numeric value (1, 2, or null/undefined for 0)
                let pocketedBy = null;
                if (ballsPocketed) {
                    // Try both numeric and string keys explicitly
                    const ballKeyNum = ballNum;
                    const ballKeyStr = String(ballNum);
                    pocketedBy = ballsPocketed[ballKeyNum] !== undefined ? ballsPocketed[ballKeyNum] : 
                                 (ballsPocketed[ballKeyStr] !== undefined ? ballsPocketed[ballKeyStr] : null);
                    
                    // Normalize to number if it's a string, or ensure it's null/undefined if not 1 or 2
                    if (pocketedBy === '1' || pocketedBy === 1) {
                        pocketedBy = 1;
                    } else if (pocketedBy === '2' || pocketedBy === 2) {
                        pocketedBy = 2;
                    } else {
                        pocketedBy = null; // Ensure null for on-table state
                    }
                }
                
                // Use 0 for on-table state to ensure proper cycling
                const currentState = pocketedBy || 0;
                
                let stateClass = 'on-table';
                let stateBadge = '';
                if (pocketedBy === 1) {
                    stateClass = 'pocketed-team1';
                    stateBadge = '<span class="state-badge">T1</span>';
                } else if (pocketedBy === 2) {
                    stateClass = 'pocketed-team2';
                    stateBadge = '<span class="state-badge">T2</span>';
                }
                
                // Get proper ball color class
                const ballColorClass = BALL_COLORS[ballNum] || '';
                
                return `
                    <div class="manager-ball-btn ${stateClass} ${ballColorClass}" 
                         onclick="cycleBallState(${match.id}, ${game.game_number}, ${ballNum}, ${currentState}, '${game.team1_group || ''}', ${breakingTeam})"
                         title="Ball ${ballNum}">
                        <div class="ball-inner ${ballColorClass}">
                            <span class="ball-num">${ballNum}</span>
                        </div>
                        ${stateBadge}
                    </div>
                `;
            }
            
            const ballsHtml = allBalls.map(createManagerBall).join('');
            const team1Group = game.team1_group || '';
            const team2Group = team1Group === 'solids' ? 'stripes' : (team1Group === 'stripes' ? 'solids' : '');
            
            // Breaking team selection
            const breakingTeamHtml = `
                <div class="manager-breaking-section">
                    <div class="section-label">🎯 Who's Breaking?</div>
                    <div class="manager-breaking-buttons">
                        <button class="manager-breaking-btn ${breakingTeam === 1 ? 'active' : ''}" 
                                onclick="setBreakingTeam(${match.id}, ${game.game_number}, 1)">
                            <span>${escapeHtml(match.team1)}</span>
                        </button>
                        <button class="manager-breaking-btn ${breakingTeam === 2 ? 'active' : ''}" 
                                onclick="setBreakingTeam(${match.id}, ${game.game_number}, 2)">
                            <span>${escapeHtml(match.team2)}</span>
                        </button>
                    </div>
                </div>
            `;
            
            // Group assignment buttons
            const groupAssignmentHtml = `
                <div class="manager-group-section">
                    <div class="section-label">Ball Assignment (who has solids?) - Auto-assigned on first pocket</div>
                    <div class="manager-group-buttons">
                        <button class="manager-group-btn ${team1Group === 'solids' ? 'active' : ''}" 
                                onclick="setGroupAssignment(${match.id}, ${game.game_number}, 'solids')">
                            <span>⚫ ${escapeHtml(match.team1)}</span>
                            <span class="group-sub">Solids (1-7)</span>
                        </button>
                        <button class="manager-group-btn ${team1Group === 'stripes' ? 'active' : ''}" 
                                onclick="setGroupAssignment(${match.id}, ${game.game_number}, 'stripes')">
                            <span>⬜ ${escapeHtml(match.team1)}</span>
                            <span class="group-sub">Stripes (9-15)</span>
                        </button>
                    </div>
                </div>
            `;
            
            // Special actions section
            const specialActionsHtml = `
                <div class="manager-special-section">
                    <div class="section-label">Special Actions</div>
                    <div class="manager-special-buttons">
                        <button class="manager-special-btn golden" onclick="setGoldenBreak(${match.id}, ${game.game_number}, 1)">
                            <span>⭐ Golden Break</span>
                            <span class="special-sub">${escapeHtml(match.team1)}</span>
                        </button>
                        <button class="manager-special-btn golden" onclick="setGoldenBreak(${match.id}, ${game.game_number}, 2)">
                            <span>⭐ Golden Break</span>
                            <span class="special-sub">${escapeHtml(match.team2)}</span>
                        </button>
                    </div>
                    <div class="manager-special-buttons" style="margin-top: 8px;">
                        <button class="manager-special-btn scratch" onclick="setEarly8Ball(${match.id}, ${game.game_number}, 1)">
                            <span>❌ Scratch on 8</span>
                            <span class="special-sub">${escapeHtml(match.team1)} loses</span>
                        </button>
                        <button class="manager-special-btn scratch" onclick="setEarly8Ball(${match.id}, ${game.game_number}, 2)">
                            <span>❌ Scratch on 8</span>
                            <span class="special-sub">${escapeHtml(match.team2)} loses</span>
                        </button>
                    </div>
                </div>
            `;
            
            return `
                <div class="manager-scorecard">
                    <div class="manager-scorecard-header">
                        <h3>🎱 Game ${game.game_number}</h3>
                        <div class="game-info">Manage the game below</div>
                    </div>
                    
                    <div class="manager-score-display">
                        <div class="manager-team-score team1">
                            <div class="team-number-label team1-label">Team 1</div>
                            <div class="team-label">${escapeHtml(match.team1)}${breakingTeam === 1 ? ' 🎯' : ''}</div>
                            <div class="score" id="score-display-team1-${match.id}-${game.game_number}">${game.team1_score || 0}</div>
                            ${team1Group ? `<div class="group-label">${team1Group === 'solids' ? '⚫ Solids' : '⬜ Stripes'}</div>` : ''}
                        </div>
                        <div class="manager-score-divider">-</div>
                        <div class="manager-team-score team2">
                            <div class="team-number-label team2-label">Team 2</div>
                            <div class="team-label">${escapeHtml(match.team2)}${breakingTeam === 2 ? ' 🎯' : ''}</div>
                            <div class="score" id="score-display-team2-${match.id}-${game.game_number}">${game.team2_score || 0}</div>
                            ${team2Group ? `<div class="group-label">${team2Group === 'solids' ? '⚫ Solids' : '⬜ Stripes'}</div>` : ''}
                        </div>
                    </div>
                    
                    <div class="manager-edit-scores-section" style="margin: 15px 0; padding: 12px; background: rgba(255,255,255,0.05); border-radius: 8px;">
                        <div class="section-label" style="margin-bottom: 10px;">Edit Scores (if ball tracking wasn't used)</div>
                        <div style="display: flex; gap: 10px; align-items: center; justify-content: center;">
                            <div style="flex: 1; display: flex; flex-direction: column; gap: 5px;">
                                <label style="font-size: 12px; color: #aaa;">${escapeHtml(match.team1)}</label>
                                <input type="number" min="0" max="10" value="${game.team1_score || 0}" 
                                       id="edit-score-team1-${match.id}-${game.game_number}"
                                       style="width: 100%; padding: 8px; border: 1px solid #444; border-radius: 4px; background: #222; color: #fff; text-align: center; font-size: 16px; font-weight: bold;">
                            </div>
                            <div style="font-size: 20px; color: #666; margin-top: 20px;">-</div>
                            <div style="flex: 1; display: flex; flex-direction: column; gap: 5px;">
                                <label style="font-size: 12px; color: #aaa;">${escapeHtml(match.team2)}</label>
                                <input type="number" min="0" max="10" value="${game.team2_score || 0}" 
                                       id="edit-score-team2-${match.id}-${game.game_number}"
                                       style="width: 100%; padding: 8px; border: 1px solid #444; border-radius: 4px; background: #222; color: #fff; text-align: center; font-size: 16px; font-weight: bold;">
                            </div>
                        </div>
                        <button class="manager-edit-scores-btn" 
                                onclick="editGameScores(${match.id}, ${game.game_number})"
                                style="margin-top: 10px; width: 100%; padding: 10px; background: #4CAF50; color: white; border: none; border-radius: 6px; font-weight: bold; cursor: pointer;">
                            💾 Save Scores
                        </button>
                    </div>
                    
                    ${breakingTeamHtml}
                    
                    ${groupAssignmentHtml}
                    
                    <div class="manager-balls-section">
                        <div class="section-label">Tap ball to cycle: On Table → Team 1 → Team 2 → On Table</div>
                        <div class="manager-balls-row">
                            ${ballsHtml}
                        </div>
                    </div>
                    
                    ${specialActionsHtml}
                    
                    <div class="manager-win-buttons">
                        <button class="manager-win-btn team1" onclick="managerWinGameFromScorecard(${match.id}, ${game.game_number}, 1)">
                            <span class="btn-icon">🏆</span>
                            <span>Team 1 Wins</span>
                        </button>
                        <button class="manager-win-btn team2" onclick="managerWinGameFromScorecard(${match.id}, ${game.game_number}, 2)">
                            <span class="btn-icon">🏆</span>
                            <span>Team 2 Wins</span>
                        </button>
                    </div>
                    
                    <div class="manager-reset-section" style="margin-top: 15px; text-align: center;">
                        <button class="manager-reset-btn" onclick="resetTable(${match.id}, ${game.game_number})">
                            <span>🔄 Reset Table</span>
                        </button>
                    </div>
                </div>
            `;
        }
        
        function getBallStyle(ballNum, isStripe) {
            const colors = {
                1: '#FFD700', 2: '#0066CC', 3: '#CC0000', 4: '#6B2D8B',
                5: '#FF6600', 6: '#006633', 7: '#8B0000', 8: '#000000',
                9: '#FFD700', 10: '#0066CC', 11: '#CC0000', 12: '#6B2D8B',
                13: '#FF6600', 14: '#006633', 15: '#8B0000'
            };
            
            const color = colors[ballNum] || '#888888';
            
            if (isStripe) {
                return `background: white; border: 3px solid ${color}; background-image: linear-gradient(90deg, ${color} 30%, white 30%, white 70%, ${color} 70%);`;
            } else if (ballNum === 8) {
                return `background: ${color}; border: 2px solid #333;`;
            } else {
                return `background: ${color}; border: 2px solid #333;`;
            }
        }
        
        function renderProgressIndicators(game, ballsPocketed) {
            const SOLIDS = [1, 2, 3, 4, 5, 6, 7];
            const STRIPES = [9, 10, 11, 12, 13, 14, 15];
            
            const group = game.team1_group;
            if (!group) return '';
            
            const team1Balls = group === 'solids' ? SOLIDS : STRIPES;
            const team2Balls = group === 'solids' ? STRIPES : SOLIDS;
            
            // Count pocketed balls
            let team1Pocketed = 0;
            let team2Pocketed = 0;
            let eightBallPocketed = false;
            let eightBallTeam = null;
            
            for (const [ballStr, team] of Object.entries(ballsPocketed)) {
                const ballNum = parseInt(ballStr);
                if (ballNum === 8) {
                    eightBallPocketed = true;
                    eightBallTeam = team;
                } else if (team1Balls.includes(ballNum)) {
                    team1Pocketed++;
                } else if (team2Balls.includes(ballNum)) {
                    team2Pocketed++;
                }
            }
            
            // Create progress indicators
            const team1Indicators = Array(7).fill(0).map((_, i) => {
                if (i < team1Pocketed) {
                    return '<span style="color:#4CAF50;">✓</span>';
                } else {
                    return '<span style="color:#FFD700;">●</span>';
                }
            }).join('');
            
            const team2Indicators = Array(7).fill(0).map((_, i) => {
                if (i < team2Pocketed) {
                    return '<span style="color:#2196F3;">✓</span>';
                } else {
                    return '<span style="color:#87CEEB;">●</span>';
                }
            }).join('');
            
            const team1Eight = team1Pocketed === 7 ? (eightBallPocketed && eightBallTeam === 1 ? '<span style="color:#ffd700;">✓</span>' : '<span style="color:#4CAF50;">⑧</span>') : '<span style="color:#333;">⑧</span>';
            const team2Eight = team2Pocketed === 7 ? (eightBallPocketed && eightBallTeam === 2 ? '<span style="color:#ffd700;">✓</span>' : '<span style="color:#2196F3;">⑧</span>') : '<span style="color:#333;">⑧</span>';
            
            return `
                <div class="progress-indicators">
                    <div class="team-progress">
                        <span style="color:var(--green);font-weight:bold;">Team 1:</span>
                        <span style="margin:0 10px;">${team1Indicators}</span>
                        ${team1Eight}
                        <span style="margin-left:10px;color:var(--text-secondary);font-size:0.9em;">${team1Pocketed}/7</span>
                    </div>
                    <div class="team-progress">
                        <span style="color:var(--blue);font-weight:bold;">Team 2:</span>
                        <span style="margin:0 10px;">${team2Indicators}</span>
                        ${team2Eight}
                        <span style="margin-left:10px;color:var(--text-secondary);font-size:0.9em;">${team2Pocketed}/7</span>
                    </div>
                </div>
            `;
        }
        
        function cycleBallState(matchId, gameNumber, ballNum, currentState, team1Group, breakingTeam = 1) {
            // Check if user is authenticated as manager (either via full manager mode or scorecard manager mode)
            if (!managerAuthenticated && !openScorecardIsManager) {
                console.log('Not authenticated for manager mode');
                return;
            }
            
            // Normalize currentState to ensure it's always 0, 1, or 2
            // Handle null, undefined, or string values - be very explicit
            let normalizedState = 0;
            const stateNum = typeof currentState === 'number' ? currentState : parseInt(currentState);
            if (stateNum === 1) {
                normalizedState = 1;
            } else if (stateNum === 2) {
                normalizedState = 2;
            } else {
                normalizedState = 0; // Default to on table (0) for any other value
            }
            
            // Check if this is the 8-ball and it's on the table
            if (ballNum === 8 && normalizedState === 0) {
                if (!confirm('⚠️ Warning: Pocketing the 8-ball will end the game!\n\nAre you sure you want to continue?')) {
                    return; // User cancelled
                }
            }
            
            // Haptic feedback on mobile - satisfying ball pocket feel
            haptic('ballPocket');
            
            const sessionToken = sessionStorage.getItem('manager_session_token');
            if (!sessionToken) {
                handleSessionExpired();
                return;
            }
            
            // Determine ball type
            const isSolid = ballNum >= 1 && ballNum <= 7;
            const isStripe = ballNum >= 9 && ballNum <= 15;
            const is8Ball = ballNum === 8;
            
            // Cycle: 0 (on table) -> correct team -> other team -> 0 (on table)
            // If group is assigned, first click goes to the team that owns that ball type
            let newTeam = 0;
            if (normalizedState === 0) {
                // First click - assign to correct team based on ball type and group
                if (team1Group && !is8Ball) {
                    if (team1Group === 'solids') {
                        // Team 1 has solids, Team 2 has stripes
                        newTeam = isSolid ? 1 : 2;
                    } else if (team1Group === 'stripes') {
                        // Team 1 has stripes, Team 2 has solids
                        newTeam = isStripe ? 1 : 2;
                    }
                } else {
                    // No group assigned yet, default to breaking team (matches backend auto-assignment logic)
                    newTeam = breakingTeam || 1;
                }
            } else if (normalizedState === 1) {
                // Currently on Team 1, cycle to Team 2
                newTeam = 2;
            } else if (normalizedState === 2) {
                // Currently on Team 2, cycle back to on table (0)
                newTeam = 0;
            }
            
            fetch('/api/manager/pocket-ball', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    match_id: matchId,
                    game_number: gameNumber,
                    ball_number: ballNum,
                    team: newTeam,
                    session_token: sessionToken
                })
            })
            .then(r => r.json())
            .then(data => {
                if (data.success) {
                    // Show notification if group was auto-assigned
                    if (data.group_changed) {
                        haptic('success');
                        const groupText = data.team1_group === 'solids' ? 'Team 1: Solids, Team 2: Stripes' : 'Team 1: Stripes, Team 2: Solids';
                        showToast(`🎱 Groups assigned! ${groupText}`);
                    }
                    // Check for illegal 8-ball
                    if (data.illegal_8ball) {
                        haptic('error');
                        if (data.early_8ball_on_break) {
                            showToast(`❌ 8-ball on the break! Team ${data.losing_team} loses. Team ${data.winning_team} wins!`);
                        } else {
                            showToast(`❌ Illegal 8-ball! Team ${data.losing_team} pocketed the 8-ball early. Team ${data.winning_team} wins!`);
                        }
                    }
                    // Refresh scorecard immediately for responsive UX
                    setTimeout(() => refreshOpenScorecard(), 50);
                } else {
                    handleApiError(data, 'Failed to update ball');
                }
            })
            .catch(err => {
                console.error('Error:', err);
                alert('Failed to update ball');
            });
        }
        
        function showToast(message) {
            // Create a temporary toast notification
            const toast = document.createElement('div');
            toast.className = 'toast-notification';
            toast.textContent = message;
            toast.style.cssText = `
                position: fixed;
                top: 20px;
                left: 50%;
                transform: translateX(-50%);
                background: linear-gradient(135deg, #4CAF50, #2d7a3e);
                color: white;
                padding: 12px 24px;
                border-radius: 25px;
                font-weight: bold;
                font-size: 0.9em;
                z-index: 10000;
                box-shadow: 0 4px 12px rgba(0,0,0,0.3);
                animation: slideDown 0.3s ease-out;
            `;
            document.body.appendChild(toast);
            
            // Remove after 3 seconds
            setTimeout(() => {
                toast.style.animation = 'slideUp 0.3s ease-out forwards';
                setTimeout(() => toast.remove(), 300);
            }, 3000);
        }
        
        // Legacy function - redirect to new cycle function
        function clickBallInScorecard(matchId, gameNumber, ballNum) {
            cycleBallState(matchId, gameNumber, ballNum, 0, '');
        }
        
        function toggleBallInScorecard(matchId, gameNumber, ballNum, currentTeam) {
            if (!managerAuthenticated) return;

            const sessionToken = sessionStorage.getItem('manager_session_token');

            // Toggle: currentTeam -> other team -> remove (0)
            let newTeam = currentTeam === 1 ? 2 : (currentTeam === 2 ? 0 : 1);

            fetch('/api/manager/pocket-ball', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    match_id: matchId,
                    game_number: gameNumber,
                    ball_number: ballNum,
                    team: newTeam,
                    session_token: sessionToken
                })
            })
            .then(r => r.json())
            .then(data => {
                if (data.success) {
                    // Reload scorecard - it will auto-refresh via SSE, but refresh immediately for better UX
                    setTimeout(() => refreshOpenScorecard(), 100);
                } else {
                    handleApiError(data, 'Failed to update ball');
                }
            })
            .catch(err => {
                console.error('Error:', err);
                alert('Failed to update ball');
            });
        }
        
        function closeModal() {
            // Haptic feedback - modal closing
            haptic('modalClose');
            
            document.getElementById('scorecard-modal').classList.remove('active');
            openScorecardMatchId = null;  // Clear tracking when modal closes
            openScorecardIsManager = false;
            
            // Show reaction bar again when modal closes
            const reactionBar = document.querySelector('.reaction-bar');
            if (reactionBar) {
                reactionBar.style.display = '';
            }
        }
        
        // ========================================
        // RULES MODAL
        // ========================================
        function openRulesModal() {
            haptic('modalOpen');
            document.getElementById('rules-modal').classList.add('active');
        }

        function closeRulesModal() {
            haptic('modalClose');
            document.getElementById('rules-modal').classList.remove('active');
        }

        // Close rules modal on background click
        document.getElementById('rules-modal').addEventListener('click', function(e) {
            if (e.target === this) {
                closeRulesModal();
            }
        });

        // Close modal on background click or swipe down (mobile)
        const modal = document.getElementById('scorecard-modal');
        let modalTouchStartY = 0;
        let modalTouchStartTime = 0;
        
        modal.addEventListener('click', function(e) {
            if (e.target === this) {
                closeModal();
            }
        });
        
        // Swipe down to close modal on mobile
        modal.addEventListener('touchstart', function(e) {
            if (e.target === this) {
                modalTouchStartY = e.touches[0].clientY;
                modalTouchStartTime = Date.now();
            }
        }, { passive: true });
        
        modal.addEventListener('touchend', function(e) {
            if (e.target === this && modalTouchStartY > 0) {
                const touchEndY = e.changedTouches[0].clientY;
                const touchDuration = Date.now() - modalTouchStartTime;
                const swipeDistance = touchEndY - modalTouchStartY;
                
                // Close if swiped down more than 100px in less than 300ms
                if (swipeDistance > 100 && touchDuration < 300) {
                    haptic('swipe');
                    closeModal();
                }
                modalTouchStartY = 0;
            }
        }, { passive: true });
        
        function escapeHtml(text) {
            if (!text) return '';
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }
        
        // ========================================
        // OFFLINE MODE SUPPORT
        // ========================================

        // Initialize offline database
        async function initOfflineSupport() {
            if (window.offlineDB) {
                offlineDBReady = await window.offlineDB.init();
                if (offlineDBReady) {
                    console.log('[Offline] IndexedDB initialized');
                }
            }

            // Start sync manager
            if (window.syncManager) {
                window.syncManager.start();
                window.syncManager.addListener(handleSyncEvent);
            }
        }

        // Handle sync events
        function handleSyncEvent(event, data) {
            switch (event) {
                case 'syncStart':
                    console.log('[Offline] Sync started');
                    break;
                case 'syncComplete':
                    console.log(`[Offline] Sync complete: ${data.synced} synced`);
                    updateSyncPendingUI();
                    if (data.synced > 0) {
                        showToast(`Synced ${data.synced} action(s)`);
                    }
                    break;
                case 'conflict':
                    console.warn('[Offline] Sync conflict:', data);
                    showToast(`Action rejected: ${data.error}`, true);
                    break;
                case 'itemSynced':
                    updateSyncPendingUI();
                    break;
            }
        }

        // Update offline indicator UI
        function updateOfflineIndicator() {
            const indicator = document.getElementById('offline-indicator');
            if (!indicator) return;

            if (isOffline) {
                indicator.style.display = 'flex';
            } else {
                indicator.style.display = 'none';
            }

            updateSyncPendingUI();
        }

        // Update sync pending count UI
        async function updateSyncPendingUI() {
            const badge = document.getElementById('sync-pending-count');
            if (!badge) return;

            if (window.syncManager) {
                const count = await window.syncManager.getPendingCount();
                if (count > 0) {
                    badge.textContent = count;
                    badge.style.display = 'inline';
                } else {
                    badge.style.display = 'none';
                }
            }
        }

        // Handle going offline
        function handleOffline() {
            isOffline = true;
            console.log('[Offline] App is now offline');
            updateOfflineIndicator();
            loadFromOfflineCache();
        }

        // Handle coming online
        function handleOnline() {
            isOffline = false;
            console.log('[Offline] App is now online');
            updateOfflineIndicator();
            // SSE will reconnect automatically
        }

        // Load data from offline cache
        async function loadFromOfflineCache() {
            if (!offlineDBReady || !window.offlineDB) return;

            const cachedData = await window.offlineDB.getAppState();
            if (cachedData) {
                console.log('[Offline] Loading from cache');
                // Mark data as cached
                cachedData._cached = true;
                updateUI(cachedData);
            }
        }

        // Save data to offline cache
        async function saveToOfflineCache(data) {
            if (!offlineDBReady || !window.offlineDB) return;
            await window.offlineDB.saveAppState(data);
        }

        // Execute manager action with offline support
        async function executeManagerAction(action, payload) {
            // Add session token to payload
            payload.session_token = sessionStorage.getItem('manager_session_token');

            if (isOffline) {
                // Queue for later sync
                if (window.offlineDB && offlineDBReady) {
                    await window.offlineDB.addToSyncQueue(action, payload);
                    updateSyncPendingUI();
                    showToast('Action queued for sync', false, 'queued');
                    return { success: true, queued: true };
                } else {
                    showToast('Cannot perform action offline', true);
                    return { success: false, error: 'Offline' };
                }
            }

            // Online - execute immediately
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
                return { success: false, error: 'Unknown action' };
            }

            try {
                const response = await fetch(endpoint, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });
                return await response.json();
            } catch (error) {
                console.error('[Offline] Action failed:', error);
                // Queue for retry if network error
                if (window.offlineDB && offlineDBReady) {
                    await window.offlineDB.addToSyncQueue(action, payload);
                    updateSyncPendingUI();
                    showToast('Action queued for sync', false, 'queued');
                    return { success: true, queued: true };
                }
                return { success: false, error: error.message };
            }
        }

        // Show toast notification
        function showToast(message, isError = false, type = '') {
            // Remove existing toast
            const existing = document.querySelector('.toast-notification');
            if (existing) existing.remove();

            const toast = document.createElement('div');
            toast.className = `toast-notification ${isError ? 'error-toast' : ''} ${type === 'queued' ? 'queued-toast' : ''}`;
            toast.textContent = message;
            toast.style.cssText = `
                position: fixed;
                top: 60px;
                left: 50%;
                transform: translateX(-50%);
                background: ${isError ? '#f44336' : '#4CAF50'};
                color: white;
                padding: 10px 20px;
                border-radius: 8px;
                font-size: 0.9em;
                font-weight: 500;
                z-index: 10001;
                animation: slideDown 0.3s ease-out;
                box-shadow: 0 4px 12px rgba(0,0,0,0.3);
            `;

            document.body.appendChild(toast);

            // Remove after 3 seconds
            setTimeout(() => {
                toast.style.animation = 'slideUp 0.3s ease-out forwards';
                setTimeout(() => toast.remove(), 300);
            }, 3000);
        }

        // Listen for online/offline events
        window.addEventListener('online', handleOnline);
        window.addEventListener('offline', handleOffline);

        // Initialize offline support
        initOfflineSupport();

        // Start connection when page loads
        connectSSE();

        // Check for existing manager session (auto-login if session is still valid)
        checkExistingManagerSession();

        // Reconnect on visibility change (when user returns to tab)
        document.addEventListener('visibilitychange', function() {
            if (document.visibilityState === 'visible') {
                connectSSE();
            }
        });
        
        // Fallback: fetch data periodically if SSE fails
        setInterval(function() {
            if (!eventSource || eventSource.readyState === EventSource.CLOSED) {
                fetch('/api/scores')
                    .then(r => r.json())
                    .then(updateUI)
                    .catch(console.error);
            }
        }, 5000);
        
        // Manager Mode Functions
        function toggleManagerMode() {
            // Haptic feedback for mode toggle
            haptic('medium');

            if (managerMode) {
                managerMode = false;
                managerAuthenticated = false;
                lastQueuePanelHash = null;  // Reset so next time manager mode is enabled, it loads fresh
                lastMainUIHash = null;  // Reset to force UI redraw
                sessionStorage.removeItem('manager_session_token');
                const btn = document.getElementById('manager-toggle');
                btn.classList.remove('active');
                btn.textContent = '🔧 Manager Mode';
                // Hide stream link
                const streamLink = document.getElementById('stream-link');
                if (streamLink) streamLink.style.display = 'none';
                // Refresh UI to remove manager panel
                fetch('/api/scores')
                    .then(r => r.json())
                    .then(updateUI)
                    .catch(console.error);
            } else {
                promptManagerPassword();
            }
        }

        function promptManagerPassword() {
            const password = prompt('Enter Manager Password:');
            if (password === null) return;

            fetch('/api/manager/verify-password', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({password: password})
            })
            .then(r => r.json())
            .then(data => {
                if (data.success) {
                    // Success haptic - authenticated!
                    haptic('success');

                    managerAuthenticated = true;
                    managerMode = true;
                    lastMainUIHash = null;  // Reset to force UI redraw with manager panel
                    lastQueuePanelHash = null;  // Reset queue panel
                    // Store session token instead of password
                    sessionStorage.setItem('manager_session_token', data.session_token);
                    const btn = document.getElementById('manager-toggle');
                    btn.classList.add('active');
                    btn.textContent = '🔧 Manager Mode (ON)';
                    // Show stream link
                    const streamLink = document.getElementById('stream-link');
                    if (streamLink) streamLink.style.display = 'inline-flex';
                    // Refresh UI to show manager panel
                    fetch('/api/scores')
                        .then(r => r.json())
                        .then(updateUI)
                        .catch(console.error);
                } else {
                    // Error haptic - wrong password
                    haptic('error');
                    alert('Incorrect password. Manager Mode access denied.');
                }
            })
            .catch(err => {
                console.error('Password verification error:', err);
                alert('Error verifying password. Please try again.');
            });
        }

        // Check for existing manager session on page load
        function checkExistingManagerSession() {
            const sessionToken = sessionStorage.getItem('manager_session_token');
            if (!sessionToken) return;

            fetch('/api/manager/check-session', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({session_token: sessionToken})
            })
            .then(r => r.json())
            .then(data => {
                if (data.valid) {
                    // Session is still valid - auto-enable manager mode
                    managerAuthenticated = true;
                    managerMode = true;
                    lastMainUIHash = null;
                    lastQueuePanelHash = null;
                    const btn = document.getElementById('manager-toggle');
                    if (btn) {
                        btn.classList.add('active');
                        btn.textContent = '🔧 Manager Mode (ON)';
                    }
                    // Refresh UI to show manager panel
                    fetch('/api/scores')
                        .then(r => r.json())
                        .then(updateUI)
                        .catch(console.error);
                } else {
                    // Session expired - clear it
                    sessionStorage.removeItem('manager_session_token');
                }
            })
            .catch(err => {
                console.error('Session check error:', err);
                sessionStorage.removeItem('manager_session_token');
            });
        }

        // Check if an API error indicates session expiration
        function isUnauthorizedError(data) {
            return data.error && (
                data.error === 'Unauthorized' ||
                data.error.toLowerCase().includes('unauthorized') ||
                data.error.toLowerCase().includes('session')
            );
        }

        // Handle API errors, checking for session expiration
        function handleApiError(data, defaultMessage) {
            if (isUnauthorizedError(data)) {
                handleSessionExpired();
                return true; // Indicates session expired
            }
            haptic('error');
            alert('Error: ' + (data.error || defaultMessage));
            return false;
        }

        // Handle session expiration - disable manager mode and notify user
        function handleSessionExpired() {
            managerMode = false;
            managerAuthenticated = false;
            sessionStorage.removeItem('manager_session_token');

            const btn = document.getElementById('manager-toggle');
            if (btn) {
                btn.classList.remove('active');
                btn.textContent = '🔧 Manager Mode';
            }

            // Reset UI state
            lastMainUIHash = null;
            lastQueuePanelHash = null;

            // Haptic feedback
            haptic('error');

            alert('Your manager session has expired. Please log in again.');

            // Refresh UI to remove manager panel
            fetch('/api/scores')
                .then(r => r.json())
                .then(updateUI)
                .catch(console.error);
        }

        function openPaymentPortal() {
            // Open payment portal in new tab/window
            window.open('/admin/payments/login', '_blank');
        }

        async function updateGoogleSheet() {
            const btn = document.getElementById('google-sheet-btn');
            if (!btn) return;

            const originalText = btn.innerHTML;
            btn.disabled = true;
            btn.innerHTML = '⏳ Updating...';

            try {
                const response = await fetch('/api/manager/update-google-sheet', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({session_token: managerSessionToken})
                });
                const data = await response.json();
                if (data.success) {
                    btn.innerHTML = '✅ Updated!';
                    setTimeout(() => { btn.innerHTML = originalText; btn.disabled = false; }, 2000);
                } else {
                    alert('Google Sheet update failed: ' + (data.error || 'Unknown error'));
                    btn.innerHTML = originalText;
                    btn.disabled = false;
                }
            } catch (err) {
                alert('Google Sheet update failed: ' + err.message);
                btn.innerHTML = originalText;
                btn.disabled = false;
            }
        }

        function loadManagerMatches() {
            fetch('/api/scores')
                .then(r => r.json())
                .then(data => {
                    const select = document.getElementById('manager-match-select');
                    if (!select) return; // Panel might not be rendered yet
                    select.innerHTML = '<option value="">-- Select a match --</option>';

                    if (data.live_matches && data.live_matches.length > 0) {
                        const liveGroup = document.createElement('optgroup');
                        liveGroup.label = 'Live Matches';
                        data.live_matches.forEach(match => {
                            const option = document.createElement('option');
                            option.value = match.id;
                            option.textContent = `${match.team1} vs ${match.team2} (Table ${match.table})`;
                            liveGroup.appendChild(option);
                        });
                        select.appendChild(liveGroup);
                    }

                    if (data.completed_matches && data.completed_matches.length > 0) {
                        const completedGroup = document.createElement('optgroup');
                        completedGroup.label = 'Completed Matches';
                        data.completed_matches.forEach(match => {
                            const option = document.createElement('option');
                            option.value = match.id;
                            option.textContent = `${match.team1} vs ${match.team2} (Completed)`;
                            completedGroup.appendChild(option);
                        });
                        select.appendChild(completedGroup);
                    }
                })
                .catch(console.error);
        }
        
        function loadManagerQueuePanel() {
            const container = document.getElementById('manager-queue-content');
            if (!container) {
                console.log('Manager queue content container not found');
                return;
            }
            
            fetch('/api/manager/available-tables')
                .then(r => {
                    if (!r.ok) {
                        throw new Error(`HTTP error! status: ${r.status}`);
                    }
                    return r.json();
                })
                .then(data => {
                    if (data.error) {
                        container.innerHTML = `<div style="color: var(--red);">Error: ${data.error}</div>`;
                        return;
                    }
                    
                    const availableTables = data.available_tables || [];
                    const queue = data.queue || [];
                    const liveMatches = data.live_matches || [];
                    
                    // Create a hash of the current data to avoid unnecessary redraws
                    const currentHash = JSON.stringify({
                        tables: availableTables, 
                        queue: queue.map(q => q.id), 
                        live: liveMatches.map(l => l.id + '-' + l.is_complete)
                    });
                    
                    // Skip update if nothing changed (but always update on first load or if showing "Loading...")
                    if (lastQueuePanelHash !== null && currentHash === lastQueuePanelHash && !container.innerHTML.includes('Loading')) {
                        return;
                    }
                    lastQueuePanelHash = currentHash;
                    
                    let html = '';
                    
                    // Show live matches with Complete button
                    if (liveMatches.length > 0) {
                        html += `
                            <div class="manager-live-section">
                                <div class="section-label">🔴 Live Matches - Mark as Complete</div>
                                <div class="manager-live-list">
                        `;
                        
                        liveMatches.forEach(match => {
                            html += `
                                <div class="manager-live-item">
                                    <div class="live-match-info">
                                        <div class="live-match-table">Table ${match.table}</div>
                                        <div class="live-match-teams">${escapeHtml(match.team1)} vs ${escapeHtml(match.team2)}</div>
                                        <div class="live-match-score">${match.team1_games} - ${match.team2_games}</div>
                                    </div>
                                    <button class="complete-match-btn" onclick="completeMatch(${match.id}, ${match.table})">
                                        ✓ Complete & Free Table
                                    </button>
                                </div>
                            `;
                        });
                        
                        html += `
                                </div>
                            </div>
                        `;
                    }
                    
                    // Show available tables
                    html += `
                        <div class="manager-tables-section">
                            <div class="section-label">Available Tables</div>
                            <div class="manager-tables-grid">
                    `;
                    
                    if (availableTables.length === 0) {
                        html += `<div style="color: var(--text-secondary); padding: 10px;">All tables are in use</div>`;
                    } else {
                        availableTables.forEach(tableNum => {
                            html += `
                                <div class="manager-table-btn available" id="manager-table-${tableNum}">
                                    <span class="table-icon">🎱</span>
                                    <span>Table ${tableNum}</span>
                                    <span class="table-status-text">Open</span>
                                </div>
                            `;
                        });
                    }
                    
                    html += `
                            </div>
                        </div>
                    `;
                    
                    // Show queue
                    html += `
                        <div class="manager-queue-section">
                            <div class="section-label">Matches in Queue (${queue.length})</div>
                    `;
                    
                    if (queue.length === 0) {
                        html += `<div style="color: var(--text-secondary); padding: 10px;">No matches waiting in queue</div>`;
                    } else {
                        html += `<div class="manager-queue-list">`;
                        queue.forEach(match => {
                            const finalsTag = match.is_finals ? '<span class="finals-badge">🏆 Finals</span>' : '';
                            html += `
                                <div class="manager-queue-item" data-match-id="${match.id}">
                                    <div class="queue-match-info">
                                        <div class="queue-match-teams">${escapeHtml(match.team1)} vs ${escapeHtml(match.team2)}</div>
                                        <div class="queue-match-meta">Round ${match.round} • Best of ${match.best_of} ${finalsTag}</div>
                                    </div>
                                    <div class="queue-match-actions">
                                        ${availableTables.map(t => `
                                            <button class="start-match-btn" onclick="startMatchOnTable(${match.id}, ${t})">
                                                Table ${t}
                                            </button>
                                        `).join('')}
                                    </div>
                                </div>
                            `;
                        });
                        html += `</div>`;
                    }
                    
                    html += `</div>`;
                    
                    container.innerHTML = html;
                })
                .catch(err => {
                    console.error('Error loading queue:', err);
                    container.innerHTML = `<div style="color: var(--red);">Failed to load queue data</div>`;
                });
        }
        
        function completeMatch(matchId, tableNumber) {
            if (!managerAuthenticated) {
                alert('Manager mode not authenticated');
                return;
            }
            
            const sessionToken = sessionStorage.getItem('manager_session_token');
            if (!sessionToken) {
                handleSessionExpired();
                return;
            }
            
            if (!confirm(`Mark this match as complete and free Table ${tableNumber}?`)) return;
            
            haptic('medium');
            
            fetch('/api/manager/complete-match', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    match_id: matchId,
                    session_token: sessionToken
                })
            })
            .then(r => r.json())
            .then(data => {
                if (data.success) {
                    haptic('success');
                    showToast(`✅ Match completed! Table ${tableNumber} is now available.`);
                    // Reset the queue panel hash to force refresh
                    lastQueuePanelHash = '';
                    // Refresh the UI
                    fetch('/api/scores')
                        .then(r => r.json())
                        .then(updateUI)
                        .catch(console.error);
                } else {
                    handleApiError(data, 'Failed to complete match');
                }
            })
            .catch(err => {
                console.error('Error:', err);
                haptic('error');
                alert('Failed to complete match');
            });
        }
        
        function startMatchOnTable(matchId, tableNumber) {
            if (!managerAuthenticated) {
                alert('Manager mode not authenticated');
                return;
            }
            
            const sessionToken = sessionStorage.getItem('manager_session_token');
            if (!sessionToken) {
                handleSessionExpired();
                return;
            }
            
            if (!confirm(`Start this match on Table ${tableNumber}?`)) return;
            
            haptic('medium');
            
            fetch('/api/manager/start-match', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    match_id: matchId,
                    table_number: tableNumber,
                    session_token: sessionToken
                })
            })
            .then(r => r.json())
            .then(data => {
                if (data.success) {
                    haptic('success');
                    showToast(`✅ Match started on Table ${tableNumber}!`);
                    // Refresh both the main UI and queue panel
                    fetch('/api/scores')
                        .then(r => r.json())
                        .then(updateUI)
                        .catch(console.error);
                } else {
                    handleApiError(data, 'Failed to start match');
                }
            })
            .catch(err => {
                console.error('Error:', err);
                haptic('error');
                alert('Failed to start match');
            });
        }
        
        function loadManagerMatch() {
            const matchId = parseInt(document.getElementById('manager-match-select').value);
            if (!matchId) {
                document.getElementById('manager-match-content').style.display = 'none';
                return;
            }
            
            fetch(`/api/manager/match/${matchId}`)
                .then(r => r.json())
                .then(data => {
                    if (data.error) {
                        alert(data.error);
                        return;
                    }
                    
                    currentManagerMatch = data.match;
                    
                    // Find active game (winner_team is 0, null, undefined, or empty string)
                    currentManagerGame = data.games.find(g => 
                        g.winner_team === 0 || 
                        g.winner_team === null || 
                        g.winner_team === undefined || 
                        g.winner_team === ''
                    );
                    
                    // If no active game found, check if match is complete
                    if (!currentManagerGame) {
                        if (data.match.is_complete || data.games.every(g => g.winner_team > 0)) {
                            showCompletedMatchEditor(data);
                            return;
                        } else if (data.games.length === 0) {
                            alert('No games found for this match. Please try refreshing.');
                            document.getElementById('manager-match-content').style.display = 'none';
                            return;
                        }
                    }

                    document.getElementById('manager-team1-name').textContent = (data.match.team1_p1_name || 'Team 1') + (data.match.team1_p2_name ? ' & ' + data.match.team1_p2_name : '');
                    document.getElementById('manager-team2-name').textContent = (data.match.team2_p1_name || 'Team 2') + (data.match.team2_p2_name ? ' & ' + data.match.team2_p2_name : '');

                    // Hide completed match editor, restore normal UI
                    const editorEl = document.getElementById('completed-match-editor');
                    if (editorEl) editorEl.style.display = 'none';
                    const ballGrids = document.querySelectorAll('.manager-balls-grid');
                    ballGrids.forEach(g => g.style.display = '');
                    const actionsEl = document.querySelector('.manager-actions');
                    if (actionsEl) actionsEl.style.display = '';

                    renderManagerBalls();
                    updateManagerScores();
                    document.getElementById('manager-match-content').style.display = 'block';
                })
                .catch(err => {
                    console.error('Error loading manager match:', err);
                    alert('Failed to load match data. Please try again.');
                });
        }
        
        function showCompletedMatchEditor(data) {
            const match = data.match;
            const games = data.games;
            const team1Name = (match.team1_p1_name || 'Team 1') + (match.team1_p2_name ? ' & ' + match.team1_p2_name : '');
            const team2Name = (match.team2_p1_name || 'Team 2') + (match.team2_p2_name ? ' & ' + match.team2_p2_name : '');

            document.getElementById('manager-team1-name').textContent = team1Name;
            document.getElementById('manager-team2-name').textContent = team2Name;

            // Hide normal ball interface, show completed editor
            document.getElementById('manager-match-content').style.display = 'block';

            // Build or reuse the completed match editor div
            let editor = document.getElementById('completed-match-editor');
            if (!editor) {
                editor = document.createElement('div');
                editor.id = 'completed-match-editor';
                document.getElementById('manager-match-content').appendChild(editor);
            }
            editor.style.display = 'block';

            // Hide normal ball grids and actions while showing editor
            const ballGrids = document.querySelectorAll('.manager-balls-grid');
            ballGrids.forEach(g => g.style.display = 'none');
            const actions = document.querySelector('.manager-actions');
            if (actions) actions.style.display = 'none';

            const sessionToken = sessionStorage.getItem('manager_session_token');

            let html = `<div style="margin-top: 15px;">
                <h3 style="color: var(--yellow); margin-bottom: 10px;">Match Complete — Edit Games</h3>
                <div style="margin-bottom: 15px;">
                    <label style="font-weight: bold; display: block; margin-bottom: 5px;">Select Game:</label>
                    <select id="completed-game-select" style="width: 100%; padding: 8px; border-radius: 6px; background: var(--card-bg); color: var(--text-primary); border: 1px solid var(--border);">
                        ${games.map(g => {
                            const winner = g.winner_team === 1 ? team1Name : g.winner_team === 2 ? team2Name : 'No winner';
                            const earlyTag = g.early_8ball_team ? ' (Early 8)' : '';
                            const goldenTag = g.golden_break ? ' (Golden Break)' : '';
                            return `<option value="${g.game_number}">Game ${g.game_number} — ${g.team1_score}-${g.team2_score} | ${winner} wins${earlyTag}${goldenTag}</option>`;
                        }).join('')}
                    </select>
                </div>
                <div style="display: flex; gap: 10px; flex-wrap: wrap;">
                    <button onclick="revertSelectedGame()" style="flex: 1; padding: 10px; background: var(--orange, #d29922); color: white; border: none; border-radius: 6px; cursor: pointer; font-weight: 600;">
                        Revert Game (Replay)
                    </button>
                    ${match.is_complete ? `<button onclick="reopenMatch()" style="flex: 1; padding: 10px; background: var(--red, #f85149); color: white; border: none; border-radius: 6px; cursor: pointer; font-weight: 600;">
                        Reopen Match
                    </button>` : ''}
                </div>
            </div>`;

            editor.innerHTML = html;
        }

        function revertSelectedGame() {
            const gameNumber = parseInt(document.getElementById('completed-game-select').value);
            if (!currentManagerMatch || !gameNumber) return;
            if (!confirm(`Revert Game ${gameNumber}? This will clear its result and let you replay it.`)) return;

            const sessionToken = sessionStorage.getItem('manager_session_token');
            fetch('/api/manager/revert-game', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    match_id: currentManagerMatch.id,
                    game_number: gameNumber,
                    session_token: sessionToken
                })
            })
            .then(r => r.json())
            .then(data => {
                if (data.success) {
                    loadManagerMatch();
                } else {
                    alert('Failed to revert game: ' + (data.error || 'Unknown error'));
                }
            })
            .catch(err => {
                console.error('Error reverting game:', err);
                alert('Failed to revert game');
            });
        }

        function reopenMatch() {
            if (!currentManagerMatch) return;
            if (!confirm('Reopen this match? It will return to live status.')) return;

            const sessionToken = sessionStorage.getItem('manager_session_token');
            fetch('/api/manager/revert-match-completion', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    match_id: currentManagerMatch.id,
                    session_token: sessionToken
                })
            })
            .then(r => r.json())
            .then(data => {
                if (data.success) {
                    loadManagerMatches();
                    loadManagerMatch();
                } else {
                    alert('Failed to reopen match: ' + (data.error || 'Unknown error'));
                }
            })
            .catch(err => {
                console.error('Error reopening match:', err);
                alert('Failed to reopen match');
            });
        }

        function renderManagerBalls() {
            if (!currentManagerGame) return;

            const balls = JSON.parse(currentManagerGame.balls_pocketed || '{}');
            const team1Container = document.getElementById('manager-team1-balls');
            const team2Container = document.getElementById('manager-team2-balls');
            team1Container.innerHTML = '';
            team2Container.innerHTML = '';
            
            for (let i = 1; i <= 15; i++) {
                const ball = document.createElement('div');
                ball.className = `manager-ball ${BALL_COLORS[i]}`;
                ball.textContent = i;
                ball.onclick = () => toggleManagerBall(i);
                
                if (balls[i]) {
                    if (balls[i] === 1) {
                        ball.classList.add('pocketed-team1');
                    } else if (balls[i] === 2) {
                        ball.classList.add('pocketed-team2');
                    }
                }
                
                if (i <= 8) {
                    team1Container.appendChild(ball);
                } else {
                    team2Container.appendChild(ball);
                }
            }
        }
        
        function toggleManagerBall(ballNum) {
            if (!managerAuthenticated || !currentManagerMatch || !currentManagerGame) return;
            
            // Haptic feedback on mobile - ball pocket feel
            haptic('ballPocket');
            
            const sessionToken = sessionStorage.getItem('manager_session_token');
            const balls = JSON.parse(currentManagerGame.balls_pocketed || '{}');
            const currentTeam = balls[ballNum];
            
            let newTeam = 1;
            if (currentTeam === 1) {
                newTeam = 2;
            } else if (currentTeam === 2) {
                newTeam = 0;
            }
            
            if (newTeam === 0) {
                delete balls[ballNum];
            } else {
                balls[ballNum] = newTeam;
            }
            
            fetch('/api/manager/pocket-ball', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    match_id: currentManagerMatch.id,
                    game_number: currentManagerGame.game_number,
                    ball_number: ballNum,
                    team: newTeam,
                    session_token: sessionToken
                })
            })
            .then(r => r.json())
            .then(data => {
                if (data.success) {
                    loadManagerMatch();
                } else {
                    handleApiError(data, 'Failed to update ball');
                }
            })
            .catch(err => {
                console.error('Error:', err);
                alert('Failed to update ball');
            });
        }
        
        function managerWinGame(winningTeam) {
            if (!managerAuthenticated || !currentManagerMatch || !currentManagerGame) return;
            
            if (!confirm(`Confirm: Team ${winningTeam} wins this game?`)) return;
            
            haptic('strong');
            
            const sessionToken = sessionStorage.getItem('manager_session_token');
            
            fetch('/api/manager/win-game', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    match_id: currentManagerMatch.id,
                    game_number: currentManagerGame.game_number,
                    winning_team: winningTeam,
                    session_token: sessionToken
                })
            })
            .then(r => r.json())
            .then(data => {
                if (data.success) {
                    haptic('winGame');
                    alert('Game marked as won!');
                    loadManagerMatch();
                    // Refresh scorecard if open
                    if (openScorecardMatchId === currentManagerMatch.id) {
                        setTimeout(() => refreshOpenScorecard(), 100);
                    }
                } else {
                    handleApiError(data, 'Failed to mark game as won');
                }
            })
            .catch(err => {
                console.error('Error:', err);
                haptic('error');
                alert('Failed to mark game as won');
            });
        }
        
        function managerWinGameFromScorecard(matchId, gameNumber, winningTeam) {
            // Win game directly from the scorecard modal
            if (!managerAuthenticated && !openScorecardIsManager) {
                alert('Manager mode not authenticated');
                return;
            }
            
            const sessionToken = sessionStorage.getItem('manager_session_token');
            if (!sessionToken) {
                handleSessionExpired();
                return;
            }
            
            if (!confirm(`Confirm: Team ${winningTeam} wins this game?`)) return;
            
            haptic('strong');
            
            fetch('/api/manager/win-game', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    match_id: matchId,
                    game_number: gameNumber,
                    winning_team: winningTeam,
                    session_token: sessionToken
                })
            })
            .then(r => r.json())
            .then(data => {
                if (data.success) {
                    haptic('winGame');
                    alert('Game marked as won!');
                    // Refresh the scorecard
                    setTimeout(() => refreshOpenScorecard(), 100);
                } else {
                    handleApiError(data, 'Failed to mark game as won');
                }
            })
            .catch(err => {
                console.error('Error:', err);
                haptic('error');
                alert('Failed to mark game as won');
            });
        }
        
        function setBreakingTeam(matchId, gameNumber, breakingTeam) {
            // Haptic feedback for selection
            haptic('medium');
            
            // Set which team is breaking/shooting first
            if (!managerAuthenticated && !openScorecardIsManager) {
                alert('Manager mode not authenticated');
                return;
            }
            
            const sessionToken = sessionStorage.getItem('manager_session_token');
            if (!sessionToken) {
                handleSessionExpired();
                return;
            }
            
            fetch('/api/manager/set-breaking-team', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    match_id: matchId,
                    game_number: gameNumber,
                    breaking_team: breakingTeam,
                    session_token: sessionToken
                })
            })
            .then(r => r.json())
            .then(data => {
                if (data.success) {
                    // Refresh the scorecard
                    setTimeout(() => refreshOpenScorecard(), 50);
                } else {
                    handleApiError(data, 'Failed to set breaking team');
                }
            })
            .catch(err => {
                console.error('Error:', err);
                alert('Failed to set breaking team');
            });
        }
        
        function setGroupAssignment(matchId, gameNumber, team1Group) {
            // Haptic feedback for selection
            haptic('medium');
            
            // Set which team has solids vs stripes
            if (!managerAuthenticated && !openScorecardIsManager) {
                alert('Manager mode not authenticated');
                return;
            }
            
            const sessionToken = sessionStorage.getItem('manager_session_token');
            if (!sessionToken) {
                handleSessionExpired();
                return;
            }
            
            fetch('/api/manager/set-group', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    match_id: matchId,
                    game_number: gameNumber,
                    team1_group: team1Group,
                    session_token: sessionToken
                })
            })
            .then(r => r.json())
            .then(data => {
                if (data.success) {
                    // Refresh the scorecard to show updated group and scores
                    setTimeout(() => refreshOpenScorecard(), 50);
                } else {
                    handleApiError(data, 'Failed to set group');
                }
            })
            .catch(err => {
                console.error('Error:', err);
                alert('Failed to set group assignment');
            });
        }
        
        function setGoldenBreak(matchId, gameNumber, winningTeam) {
            // Set golden break - team wins instantly with 10 points
            if (!managerAuthenticated && !openScorecardIsManager) {
                alert('Manager mode not authenticated');
                return;
            }
            
            const sessionToken = sessionStorage.getItem('manager_session_token');
            if (!sessionToken) {
                handleSessionExpired();
                return;
            }
            
            if (!confirm(`Confirm: Team ${winningTeam} got a GOLDEN BREAK! They win this game instantly.`)) return;
            
            haptic('strong');
            
            fetch('/api/manager/set-golden-break', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    match_id: matchId,
                    game_number: gameNumber,
                    golden_break: true,
                    winning_team: winningTeam,
                    session_token: sessionToken
                })
            })
            .then(r => r.json())
            .then(data => {
                if (data.success) {
                    // Ultimate celebration haptic for golden break!
                    haptic('goldenBreak');
                    alert('⭐ Golden Break! Game won!');
                    setTimeout(() => refreshOpenScorecard(), 100);
                } else {
                    handleApiError(data, 'Failed to set golden break');
                }
            })
            .catch(err => {
                console.error('Error:', err);
                haptic('error');
                alert('Failed to set golden break');
            });
        }
        
        function setEarly8Ball(matchId, gameNumber, losingTeam) {
            // Early 8-ball scratch - team loses the game
            if (!managerAuthenticated && !openScorecardIsManager) {
                alert('Manager mode not authenticated');
                return;
            }
            
            const sessionToken = sessionStorage.getItem('manager_session_token');
            if (!sessionToken) {
                handleSessionExpired();
                return;
            }
            
            const winningTeam = losingTeam === 1 ? 2 : 1;
            if (!confirm(`Confirm: Team ${losingTeam} scratched on the 8-ball. Team ${winningTeam} wins!`)) return;
            
            haptic('strong');
            
            fetch('/api/manager/set-early-8ball', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    match_id: matchId,
                    game_number: gameNumber,
                    losing_team: losingTeam,
                    session_token: sessionToken
                })
            })
            .then(r => r.json())
            .then(data => {
                if (data.success) {
                    // Error/scratch haptic pattern
                    haptic('error');
                    alert('❌ Early 8-ball! Game over.');
                    setTimeout(() => refreshOpenScorecard(), 100);
                } else {
                    handleApiError(data, 'Failed to set early 8-ball');
                }
            })
            .catch(err => {
                console.error('Error:', err);
                haptic('error');
                alert('Failed to set early 8-ball');
            });
        }
        
        function resetTable(matchId, gameNumber) {
            // Reset the table - clear all balls and scores
            if (!managerAuthenticated && !openScorecardIsManager) {
                alert('Manager mode not authenticated');
                return;
            }
            
            const sessionToken = sessionStorage.getItem('manager_session_token');
            if (!sessionToken) {
                handleSessionExpired();
                return;
            }
            
            if (!confirm('Reset the table? This will clear all balls and scores for this game.')) return;
            
            haptic('medium');
            
            fetch('/api/manager/reset-table', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    match_id: matchId,
                    game_number: gameNumber,
                    session_token: sessionToken
                })
            })
            .then(r => r.json())
            .then(data => {
                if (data.success) {
                    haptic('double');
                    showToast('🔄 Table reset! All balls back on table.');
                    setTimeout(() => refreshOpenScorecard(), 50);
                } else {
                    handleApiError(data, 'Failed to reset table');
                }
            })
            .catch(err => {
                console.error('Error:', err);
                haptic('error');
                alert('Failed to reset table');
            });
        }
        
        function editGameScores(matchId, gameNumber) {
            // Edit game scores manually
            if (!managerAuthenticated && !openScorecardIsManager) {
                alert('Manager mode not authenticated');
                return;
            }
            
            const sessionToken = sessionStorage.getItem('manager_session_token');
            if (!sessionToken) {
                handleSessionExpired();
                return;
            }
            
            // Get scores from input fields
            const team1ScoreInput = document.getElementById(`edit-score-team1-${matchId}-${gameNumber}`);
            const team2ScoreInput = document.getElementById(`edit-score-team2-${matchId}-${gameNumber}`);
            
            if (!team1ScoreInput || !team2ScoreInput) {
                alert('Score input fields not found');
                return;
            }
            
            const team1Score = parseInt(team1ScoreInput.value) || 0;
            const team2Score = parseInt(team2ScoreInput.value) || 0;
            
            // Validate scores
            if (team1Score < 0 || team1Score > 10 || team2Score < 0 || team2Score > 10) {
                alert('Scores must be between 0 and 10');
                return;
            }
            
            haptic('medium');
            
            fetch('/api/manager/edit-game-scores', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    match_id: matchId,
                    game_number: gameNumber,
                    team1_score: team1Score,
                    team2_score: team2Score,
                    session_token: sessionToken
                })
            })
            .then(r => r.json())
            .then(data => {
                if (data.success) {
                    haptic('double');
                    showToast('💾 Scores updated!');
                    // Update the displayed scores
                    const scoreDisplay1 = document.getElementById(`score-display-team1-${matchId}-${gameNumber}`);
                    const scoreDisplay2 = document.getElementById(`score-display-team2-${matchId}-${gameNumber}`);
                    if (scoreDisplay1) scoreDisplay1.textContent = data.team1_score;
                    if (scoreDisplay2) scoreDisplay2.textContent = data.team2_score;
                    // Refresh the scorecard to ensure everything is in sync
                    setTimeout(() => refreshOpenScorecard(), 100);
                } else {
                    handleApiError(data, 'Failed to update scores');
                }
            })
            .catch(err => {
                console.error('Error:', err);
                haptic('error');
                alert('Failed to update scores');
            });
        }
        
        function updateManagerScores() {
            if (!currentManagerGame) return;
            
            const balls = JSON.parse(currentManagerGame.balls_pocketed || '{}');
            let team1Score = 0;
            let team2Score = 0;
            
            for (const [ball, team] of Object.entries(balls)) {
                const ballNum = parseInt(ball);
                if (team === 1) {
                    team1Score++;
                    if (ballNum === 8) team1Score += 2;
                } else if (team === 2) {
                    team2Score++;
                    if (ballNum === 8) team2Score += 2;
                }
            }
            
            team1Score = Math.min(team1Score, 10);
            team2Score = Math.min(team2Score, 10);
            
            document.getElementById('manager-team1-score').textContent = team1Score;
            document.getElementById('manager-team2-score').textContent = team2Score;
        }
        
        // Spectator Reactions Functions
        let reactionCooldown = false;
        let pendingReactionType = null;  // Track type before SSE arrives
        let lastLocalReactionId = null;  // Track to avoid showing duplicates from SSE

        function sendReaction(type, event) {
            if (reactionCooldown) return;
            
            // Haptic feedback on mobile - fun reaction pattern
            haptic('reaction');
            
            reactionCooldown = true;
            setTimeout(() => reactionCooldown = false, 2000);
            
            // Remove focus/active state immediately on mobile to prevent sticky state
            const btn = event?.target || document.querySelector(`.reaction-btn[onclick*="${type}"]`);
            if (btn) {
                // Use requestAnimationFrame to ensure the blur happens after the click
                requestAnimationFrame(() => {
                    btn.blur();
                    // Force remove any active state styling
                    setTimeout(() => {
                        btn.style.transform = '';
                        btn.style.background = '';
                    }, 150);
                });
            }
            
            // Track pending type so SSE can use it if it arrives first
            pendingReactionType = type;

            fetch('/api/reaction', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({type: type})
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    // Track this reaction ID so SSE doesn't show it again
                    lastLocalReactionId = data.reaction.id;
                    // Only show if SSE hasn't already shown it
                    if (pendingReactionType) {
                        showLocalReaction(data.reaction.emoji);
                        pendingReactionType = null;
                    }
                } else {
                    console.log('Reaction failed:', data.error);
                    pendingReactionType = null;
                }
            })
            .catch(err => {
                console.log('Reaction error:', err);
                pendingReactionType = null;
            });
        }
        
        function showLocalReaction(emoji) {
            // Light haptic when reactions appear on screen
            haptic('light');
            
            const overlay = document.getElementById('reactionOverlay');
            const reaction = document.createElement('div');
            reaction.className = 'floating-reaction';

            // Always use actual car image for car emoji (check multiple ways for unicode reliability)
            const isCarEmoji = emoji === '🚗' || emoji.includes('🚗') || emoji.codePointAt(0) === 0x1F697;
            if (isCarEmoji) {
                const img = document.createElement('img');
                img.src = '/static/images/ecoREACTION.png';
                img.alt = 'EcoCAR';
                img.style.width = '48px';
                img.style.height = 'auto';
                reaction.appendChild(img);
            } else {
                reaction.textContent = emoji;
            }

            reaction.style.left = (Math.random() * 80 + 10) + '%';
            reaction.style.bottom = '100px';
            overlay.appendChild(reaction);

            setTimeout(() => reaction.remove(), 3000);
        }
        
        // Listen for reactions from SSE
        function handleReactionEvent(event) {
            try {
                const data = JSON.parse(event.data);
                if (data.reactions && Array.isArray(data.reactions)) {
                    // Show the latest reaction
                    const latest = data.reactions[data.reactions.length - 1];
                    if (latest) {
                        // Skip if we already showed this reaction locally
                        if (latest.id === lastLocalReactionId) {
                            lastLocalReactionId = null;
                            return;
                        }

                        // Clear pending flag so POST response doesn't double-show
                        if (pendingReactionType) {
                            pendingReactionType = null;
                        }
                        showLocalReaction(latest.emoji);
                    }
                }
            } catch (e) {
                console.error('Error handling reaction event:', e);
            }
        }
    