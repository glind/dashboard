// --- YouTube Music Player Logic ---
(function() {
    const ytPlayerState = {
        playlist: [], // [{title, artist, youtubeId}]
        current: 0,
        ytPlayer: null,
        isPlaying: false,
        playlistId: null, // ID of the currently playing playlist
        playlistName: 'Queue' // Name of the current playlist
    };

    // Expose state for persistence
    window.ytPlayerState = ytPlayerState;

    window.loadYouTubePlayer = function(playlist, playlistId, playlistName) {
        ytPlayerState.playlist = playlist || [];
        ytPlayerState.current = 0;
        ytPlayerState.playlistId = playlistId || null;
        ytPlayerState.playlistName = playlistName || 'Queue';
        renderYTPlayer();
        // Save playback state to database
        savePlaybackState();
    };

    // Save playback state to database
    async function savePlaybackState() {
        try {
            await fetch('/api/music/playback-state', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    playlist_id: ytPlayerState.playlistId || 'manual',
                    playlist_name: ytPlayerState.playlistName || 'Queue',
                    tracks: ytPlayerState.playlist,
                    current_index: ytPlayerState.current
                })
            });
        } catch (e) {
            console.warn('Failed to save playback state:', e);
        }
    }

    // Update just the current index
    async function updatePlaybackIndex() {
        try {
            await fetch('/api/music/playback-state/index', {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ index: ytPlayerState.current })
            });
        } catch (e) {
            console.warn('Failed to update playback index:', e);
        }
    }

    // Load playback state from database
    window.loadPlaybackState = async function() {
        try {
            const response = await fetch('/api/music/playback-state');
            if (response.ok) {
                const data = await response.json();
                // Handle response format from music module: {success: bool, state: {...}}
                const state = data.state;
                
                if (state && state.tracks && state.tracks.length > 0) {
                    ytPlayerState.playlist = state.tracks;
                    ytPlayerState.current = state.current_index || 0;
                    ytPlayerState.playlistId = state.playlist_id;
                    ytPlayerState.playlistName = state.playlist_name;
                    console.log(`Restored playback state: ${state.playlist_name} (${state.tracks.length} tracks, index ${state.current_index})`);
                    renderYTPlayer();
                    return true;
                }
            }
        } catch (e) {
            console.warn('Failed to load playback state:', e);
        }
        return false;
    };

    async function searchYouTubeVideo(artist, title) {
        const query = encodeURIComponent(`${artist} ${title}`);
        try {
            const response = await fetch(`/api/youtube/search?q=${query}`);
            if (response.ok) {
                const data = await response.json();
                return data.videoId;
            }
        } catch (e) {
            console.warn('YouTube search failed:', e);
        }
        return null;
    }

    async function renderYTPlayer() {
        const now = ytPlayerState.playlist[ytPlayerState.current];
        const titleEl = document.getElementById('yt-now-title');
        const artistEl = document.getElementById('yt-now-artist');
        if (titleEl) titleEl.textContent = now ? now.title : 'No Track Playing';
        if (artistEl) artistEl.textContent = now ? now.artist : '';
        
        // Update playlist name display
        const playlistNameEl = document.getElementById('yt-playlist-name');
        if (playlistNameEl) {
            playlistNameEl.textContent = ytPlayerState.playlistName || 'Queue';
        }
        
        // Embed YouTube
        const ytDiv = document.getElementById('yt-player-embed');
        if (ytDiv && now) {
            // Show loading
            ytDiv.innerHTML = '<div class="w-full h-full flex items-center justify-center text-gray-400">🔍 Loading...</div>';
            
            // If we have a youtubeId, try it first, otherwise search
            let videoId = now.youtubeId;
            
            // Always search to get a fresh, valid video ID
            const searchedId = await searchYouTubeVideo(now.artist, now.title);
            if (searchedId) {
                videoId = searchedId;
            }
            
            if (videoId) {
                ytDiv.innerHTML = `<iframe width="100%" height="315" src="https://www.youtube.com/embed/${videoId}?autoplay=1&enablejsapi=1" frameborder="0" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share" allowfullscreen></iframe>`;
                // Show audio control panel for music
                if (window.dataLoader && window.dataLoader.showAudioControlPanel) {
                    window.dataLoader.showAudioControlPanel('music', `${now.title} - ${now.artist}`);
                }
            } else {
                // Fallback: link to YouTube search
                const searchUrl = `https://www.youtube.com/results?search_query=${encodeURIComponent(now.artist + ' ' + now.title)}`;
                ytDiv.innerHTML = `<div class="w-full h-full flex flex-col items-center justify-center bg-gray-800 rounded p-4">
                    <p class="mb-4 text-center">${now.title} - ${now.artist}</p>
                    <a href="${searchUrl}" target="_blank" class="bg-red-600 hover:bg-red-700 text-white px-4 py-2 rounded">▶️ Play on YouTube</a>
                </div>`;
            }
        } else if (ytDiv) {
            ytDiv.innerHTML = '';
        }
        
        // Render upcoming
        const upList = document.getElementById('yt-upcoming-list');
        if (upList) {
            upList.innerHTML = ytPlayerState.playlist.slice(ytPlayerState.current+1).map((track, i) =>
                `<li class="flex items-center gap-2 p-2 rounded hover:bg-gray-700 cursor-pointer" data-yt-jump="${ytPlayerState.current+1+i}">
                    <span class="font-semibold text-sm">${i+1}. ${track.title}</span>
                    <span class="text-xs text-gray-400 ml-auto">${track.artist}</span>
                </li>`
            ).join('') || '<li class="text-gray-500 text-sm p-2">No more songs</li>';
            
            // Add click listeners for upcoming songs
            upList.querySelectorAll('[data-yt-jump]').forEach(li => {
                li.onclick = () => {
                    const idx = parseInt(li.getAttribute('data-yt-jump'));
                    window.ytJumpTo(idx);
                };
            });
        }
    }

    window.ytPlayPause = function() {
        renderYTPlayer();
    };
    
    window.ytNext = function() {
        if (ytPlayerState.current < ytPlayerState.playlist.length-1) {
            ytPlayerState.current++;
            renderYTPlayer();
            updatePlaybackIndex();
        }
    };
    
    window.ytPrev = function() {
        if (ytPlayerState.current > 0) {
            ytPlayerState.current--;
            renderYTPlayer();
            updatePlaybackIndex();
        }
    };
    
    window.ytJumpTo = function(idx) {
        ytPlayerState.current = idx;
        renderYTPlayer();
        updatePlaybackIndex();
    };

    document.addEventListener('DOMContentLoaded', async function() {
        if (document.getElementById('yt-player-embed')) {
            // Try to restore saved playback state first
            const restored = await window.loadPlaybackState();
            
            if (!restored) {
                // Only load default playlist if no saved state
                window.loadYouTubePlayer([
                    {title: 'Blinding Lights', artist: 'The Weeknd', youtubeId: 'fHI8X4OXluQ'},
                    {title: 'Levitating', artist: 'Dua Lipa', youtubeId: 'TUVcZfQe-Kw'},
                    {title: 'Save Your Tears', artist: 'The Weeknd', youtubeId: 'XXYlFuWEuKI'},
                    {title: 'Peaches', artist: 'Justin Bieber', youtubeId: 'tQ0yjYUFKAE'},
                    {title: 'Watermelon Sugar', artist: 'Harry Styles', youtubeId: 'E07s5ZYygMg'}
                ], 'default', 'Default Playlist');
            }
            
            const playBtn = document.getElementById('yt-play-btn');
            const nextBtn = document.getElementById('yt-next-btn');
            const prevBtn = document.getElementById('yt-prev-btn');
            
            if (playBtn) playBtn.onclick = window.ytPlayPause;
            if (nextBtn) nextBtn.onclick = window.ytNext;
            if (prevBtn) prevBtn.onclick = window.ytPrev;
            
            // Delegate click for upcoming list
            const upList = document.getElementById('yt-upcoming-list');
            if (upList) {
                upList.addEventListener('click', function(e) {
                    const li = e.target.closest('[data-yt-jump]');
                    if (li) {
                        window.ytJumpTo(Number(li.getAttribute('data-yt-jump')));
                    }
                });
            }
        }
    });
})();
/**
 * Modern Dashboard Data Loader
 * Handles loading data for all dashboard sections
 */

try {
    window.dataLoader = new (class DashboardDataLoader {
        constructor() {
            this.todos = [];
        this.calendar = [];
        this.emails = [];
        this.github = {};
        this.news = [];
        this.newsArticles = {}; // For article modal lookup
        this.weather = {};
        this.dashboards = {}; // Marketing dashboards (projects & websites)
        this.aiSuggestions = [];
        this.aiMessages = [];
        this.vanityAlerts = [];
        this.musicNews = [];
        this.upcomingEventTimer = null;
        this.voiceRecognition = null;
        this.speechSynthesis = window.speechSynthesis;
        this.alertedEvents = new Set();
        this.feedbackData = {}; // Store feedback for AI training
        this.dismissedSuggestions = new Set(); // Track dismissed AI suggestions
        // VIP/Client domains - emails from these will be prioritized and trigger alerts
        this.clientDomains = JSON.parse(localStorage.getItem('clientDomains') || '[]');
        this.clientEmailAddresses = JSON.parse(localStorage.getItem('clientEmailAddresses') || '[]');
        this.lastSeenClientEmails = JSON.parse(localStorage.getItem('lastSeenClientEmails') || '[]');
        this.aiVoiceEnabled = localStorage.getItem('aiVoiceEnabled') !== 'false'; // AI voice responses - persisted
        this.globalMuted = localStorage.getItem('globalMuted') === 'true'; // Global mute for ALL voice alerts
        this.editMode = false;
        this.autoRefreshInterval = 5; // minutes
        this.autoRefreshTimer = null;
        this.backgroundImages = []; // Available background images
        this.currentBackgroundIndex = 0;
        this.backgroundRotation = 'random'; // 'random', 'sequential', 'fixed'
        this.fullPageBackground = false; // Full-page background with transparent cards
        this.savedBackgrounds = []; // Liked backgrounds saved as base64
        this.taskSyncEnabled = false; // TickTick/Todoist sync
        this.taskSyncService = 'ticktick'; // 'ticktick' or 'todoist'
        this.selectedVoice = null; // Selected TTS voice
        this.availableVoices = []; // Available TTS voices
        this.voiceSignatureEnabled = localStorage.getItem('voiceSignatureEnabled') === 'true'; // "Roger Roger" signature
        this.conversationId = null; // Current AI conversation ID
        this.userProfile = null; // User profile for AI
        this.aiAssistants = []; // Configured assistant personas
        this.activeAssistantId = null; // Selected assistant persona
        this.aiMemory = { long_term: '', short_term: '' }; // Editable AI memory panes
        this.overviewSummary = null; // 5-minute overview summary for AI Assistant
        this.personalizedSuggestion = null; // Random personalized suggestion
        this.showReadArticles = false; // Show read articles in news section
        this.sectionLoadState = {
            todos: { lastLoadedAt: 0, inFlight: false, ttlMs: 60000 },
            calendar: { lastLoadedAt: 0, inFlight: false, ttlMs: 120000 },
            emails: { lastLoadedAt: 0, inFlight: false, ttlMs: 60000 },
            github: { lastLoadedAt: 0, inFlight: false, ttlMs: 120000 },
            news: { lastLoadedAt: 0, inFlight: false, ttlMs: 120000 },
            weather: { lastLoadedAt: 0, inFlight: false, ttlMs: 300000 }
        };
        this.dashboardConfig = {
            overview: true,
            leads: true,
            dashboards: true,
            todos: true,
            calendar: true,
            emails: true,
            github: true,
            news: true,
            weather: true,
            vanity: true,
            liked: true,
            music: true,
            ai: true
        };
        
        try {
            this.initVoiceRecognition();
            this.initAudioControlPanel();
            this.loadDashboardConfig();
            this.loadAutoRefreshSettings();
            this.loadBackgroundSettings();
            this.loadTaskSyncSettings();
            this.loadVoiceSettings();
            this.loadUserProfile();
            this.loadAIAssistants();
            this.loadAIMemory();
            this.updateGlobalMuteButton();
        } catch (error) {
            console.error('Error initializing dashboard components:', error);
        }
    }
    
    initVoiceRecognition() {
        // Initialize voice recognition if available
        try {
            const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
            if (SpeechRecognition) {
                this.voiceRecognition = new SpeechRecognition();
                this.voiceRecognition.continuous = false;
                this.voiceRecognition.interimResults = false;
            }
        } catch (error) {
            console.warn('Voice recognition not available:', error);
        }
    }
    
    updateGlobalMuteButton() {
        // Update the global mute button UI based on current state
        const iconEl = document.getElementById('mute-icon');
        const textEl = document.getElementById('mute-text');
        const btnEl = document.getElementById('global-mute-btn');
        
        if (iconEl && textEl && btnEl) {
            if (this.globalMuted) {
                iconEl.textContent = '🔇';
                textEl.textContent = 'Voice Alerts Off';
                btnEl.className = 'mt-2 w-full flex items-center justify-center gap-2 px-4 py-2 bg-gray-600 hover:bg-gray-700 text-white text-sm font-medium rounded-lg transition-colors shadow-lg';
            } else {
                iconEl.textContent = '🔊';
                textEl.textContent = 'Voice Alerts On';
                btnEl.className = 'mt-2 w-full flex items-center justify-center gap-2 px-4 py-2 bg-purple-600 hover:bg-purple-700 text-white text-sm font-medium rounded-lg transition-colors shadow-lg';
            }
        }
    }

    checkOAuthCallbackStatus() {
        // Check URL params for OAuth callback status
        const params = new URLSearchParams(window.location.search);
        if (params.has('spotify')) {
            const status = params.get('spotify');
            if (status === 'connected') {
                this.showNotification('Spotify connected successfully!', 'success');
                this.updateServiceStatus('spotify', true);
            } else if (status === 'error') {
                this.showNotification('Failed to connect Spotify', 'error');
            }
            // Clean up URL
            window.history.replaceState({}, document.title, window.location.pathname);
        }
        if (params.has('apple')) {
            const status = params.get('apple');
            if (status === 'connected') {
                this.showNotification('Apple Music connected successfully!', 'success');
                this.updateServiceStatus('apple', true);
            } else if (status === 'error') {
                this.showNotification('Failed to connect Apple Music', 'error');
            }
            // Clean up URL
            window.history.replaceState({}, document.title, window.location.pathname);
        }
    }
    
    async loadAllData() {
        // Load all data in parallel
        await Promise.all([
            this.loadTodos(),
            this.loadCalendar(),
            this.loadEmails(),
            this.loadGithub(),
            this.loadNews(),
            this.loadWeather(),
            this.loadDashboards(),
            this.loadPlaylists()  // Load saved playlists from database
        ]);
        
        this.updateAllCounts();
    }

    async fetchJsonWithTimeout(url, options = {}, timeoutMs = 12000) {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

        try {
            const response = await fetch(url, { ...options, signal: controller.signal });
            return response;
        } finally {
            clearTimeout(timeoutId);
        }
    }

    getLoadErrorMessage(defaultMessage, error) {
        if (error && error.name === 'AbortError') {
            return `${defaultMessage} (request timed out)`;
        }
        return defaultMessage;
    }

    isTimeoutAbort(error) {
        return !!(error && error.name === 'AbortError');
    }

    beginSectionFetch(sectionName) {
        const state = this.sectionLoadState[sectionName];
        if (!state) return true;
        if (state.inFlight) return false;
        state.inFlight = true;
        return true;
    }

    endSectionFetch(sectionName) {
        const state = this.sectionLoadState[sectionName];
        if (state) state.inFlight = false;
    }

    markSectionLoaded(sectionName) {
        const state = this.sectionLoadState[sectionName];
        if (state) state.lastLoadedAt = Date.now();
    }

    isSectionStale(sectionName) {
        const state = this.sectionLoadState[sectionName];
        if (!state) return true;
        if (!state.lastLoadedAt) return true;
        return (Date.now() - state.lastLoadedAt) > state.ttlMs;
    }

    hasSectionData(sectionName) {
        switch (sectionName) {
            case 'todos':
                return Array.isArray(this.todos) && this.todos.length > 0;
            case 'calendar':
                return Array.isArray(this.calendar) && this.calendar.length > 0;
            case 'emails':
                return Array.isArray(this.emails) && this.emails.length > 0;
            case 'news':
                return Array.isArray(this.news) && this.news.length > 0;
            case 'github':
                return !!(this.github && (Array.isArray(this.github.items) || Array.isArray(this.github.repos) || Array.isArray(this.github.prs) || Array.isArray(this.github.issues)));
            case 'weather':
                return !!(this.weather && this.weather.temperature);
            default:
                return false;
        }
    }

    refreshSectionData(sectionName, { force = false } = {}) {
        if (!this.sectionLoadState[sectionName]) return;

        const hasData = this.hasSectionData(sectionName);
        if (!force && hasData && !this.isSectionStale(sectionName)) {
            return;
        }

        const options = { background: hasData, reason: 'section-switch' };

        switch (sectionName) {
            case 'todos':
                this.loadTodos(0, options);
                break;
            case 'calendar':
                this.loadCalendar(0, options);
                break;
            case 'emails':
                this.loadEmails(false, 0, options);
                break;
            case 'github':
                this.loadGithub(0, options);
                break;
            case 'news':
                this.loadNews(0, options);
                break;
            case 'weather':
                this.loadWeather(0, options);
                break;
        }
    }

    setSectionLoading(containerId, message = 'Loading...') {
        const container = document.getElementById(containerId);
        if (!container) return;

        container.innerHTML = `
            <div class="col-span-full text-center py-12">
                <div class="inline-flex items-center gap-3 text-purple-400 mb-2">
                    <span class="w-5 h-5 border-2 border-purple-400 border-t-transparent rounded-full animate-spin"></span>
                    <span class="font-medium">${this.escapeHtml(message)}</span>
                </div>
                <p class="text-gray-500 text-sm animate-pulse">Please wait...</p>
            </div>
        `;
    }

    setSectionError(containerId, message = 'Failed to load data.') {
        const container = document.getElementById(containerId);
        if (!container) return;

        container.innerHTML = `
            <div class="col-span-full text-center py-12">
                <div class="text-3xl mb-2">⚠️</div>
                <h3 class="text-lg font-semibold text-white mb-1">Load Failed</h3>
                <p class="text-gray-400 text-sm">${this.escapeHtml(message)}</p>
            </div>
        `;
    }
    
    async loadNewJoke() {
        try {
            const response = await fetch('/api/joke');
            if (response.ok) {
                const data = await response.json();
                const jokeEl = document.getElementById('joke-content');
                if (jokeEl) {
                    jokeEl.textContent = data.joke || 'No joke available';
                    jokeEl.dataset.jokeId = data.id || 'unknown'; // Store joke ID for feedback
                }
            }
        } catch (error) {
            console.error('Error loading joke:', error);
            const jokeEl = document.getElementById('joke-content');
            if (jokeEl) {
                jokeEl.textContent = 'Failed to load joke 😅';
            }
        }
    }
    
    readJokeAloud() {
        const jokeEl = document.getElementById('joke-content');
        if (jokeEl && jokeEl.textContent) {
            this.speakText(jokeEl.textContent);
        }
    }
    
    async giveJokeFeedback(sentiment) {
        const jokeEl = document.getElementById('joke-content');
        if (!jokeEl) return;
        
        const jokeId = jokeEl.dataset.jokeId || 'unknown';
        const joke = jokeEl.textContent;
        
        // Store feedback for AI training
        if (!this.feedbackData.jokes) {
            this.feedbackData.jokes = {};
        }
        this.feedbackData.jokes[jokeId] = {
            joke: joke,
            sentiment: sentiment,
            timestamp: new Date().toISOString()
        };
        this.saveFeedbackToStorage();
        
        // Visual feedback
        const feedbackMsg = {
            'up': '👍 Great joke! Loading another...',
            'neutral': '👌 Okay! Loading another...',
            'down': '👎 Noted! Loading another...'
        }[sentiment] || 'Loading another...';
        
        jokeEl.textContent = feedbackMsg;
        
        // Load new joke after brief delay
        setTimeout(() => this.loadNewJoke(), 1000);
        
        console.log(`Joke feedback recorded: ${sentiment}`);
    }
    
    // TODOS
    async loadTodos(retryCount = 0, options = {}) {
        const hasExistingData = this.todos.length > 0;
        const backgroundRefresh = (options.background === true || (options.preserveExisting !== false && hasExistingData)) && hasExistingData;
        if (!backgroundRefresh) {
            this.setSectionLoading('todos-grid', 'Loading tasks...');
        }

        if (!this.beginSectionFetch('todos')) {
            return;
        }

        try {
            // By default, don't include completed tasks
            const response = await this.fetchJsonWithTimeout('/api/tasks?include_completed=false', {}, 20000);
            if (response.ok) {
                const data = await response.json();
                this.todos = data.tasks || [];
                this.renderTodos();
                this.renderOverviewTasks();
                this.updateAllCounts();
                this.markSectionLoaded('todos');
            } else {
                if (!backgroundRefresh) {
                    this.setSectionError('todos-grid', 'Unable to load tasks right now.');
                }
            }
        } catch (error) {
            if (this.isTimeoutAbort(error) && retryCount < 2) {
                console.warn(`Task load timed out, retrying (${retryCount + 1}/2)...`);
                setTimeout(() => this.loadTodos(retryCount + 1, options), 1200);
                return;
            }

            // Keep current tasks visible when a refresh request times out.
            if (this.isTimeoutAbort(error) && this.todos && this.todos.length > 0) {
                console.warn('Task refresh timed out, keeping existing task list visible.');
                this.renderTodos();
                this.renderOverviewTasks();
                return;
            }

            console.error('Error loading todos:', error);
            if (!backgroundRefresh) {
                this.setSectionError('todos-grid', this.getLoadErrorMessage('Unable to load tasks right now.', error));
            }
        } finally {
            this.endSectionFetch('todos');
        }
    }
    
    renderTodos() {
        const grid = document.getElementById('todos-grid');
        if (!grid) return;
        
        if (this.todos.length === 0) {
            grid.innerHTML = `
                <div class="col-span-full text-center py-12">
                    <div class="text-6xl mb-4">✅</div>
                    <h3 class="text-xl font-semibold mb-2">No tasks</h3>
                    <p class="text-gray-400">All caught up!</p>
                </div>
            `;
            return;
        }
        
        // Add filter buttons
        const priorities = [...new Set(this.todos.map(t => t.priority).filter(Boolean))];
        const sources = [...new Set(this.todos.map(t => t.source).filter(Boolean))];
        
        const filters = `
            <div class="mb-4 flex gap-2 flex-wrap col-span-full">
                <button onclick="dataLoader.filterTodos('all')" 
                        class="todo-filter-btn px-3 py-1 bg-blue-600 rounded text-sm">All</button>
                <button onclick="dataLoader.filterTodos('active')" 
                        class="todo-filter-btn px-3 py-1 bg-gray-700 rounded text-sm hover:bg-gray-600">Active</button>
                <button onclick="dataLoader.filterTodos('completed')" 
                        class="todo-filter-btn px-3 py-1 bg-gray-700 rounded text-sm hover:bg-gray-600">Completed</button>
                ${priorities.map(p => 
                    `<button onclick="dataLoader.filterTodos('priority-${p}')" 
                             class="todo-filter-btn px-3 py-1 bg-gray-700 rounded text-sm hover:bg-gray-600">${p}</button>`
                ).join('')}
                ${sources.map(s => 
                    `<button onclick="dataLoader.filterTodos('source-${s}')" 
                             class="todo-filter-btn px-3 py-1 bg-gray-700 rounded text-sm hover:bg-gray-600">${this.escapeHtml(s)}</button>`
                ).join('')}
            </div>
        `;
        
        const html = this.todos.map(todo => {
            const feedback = this.feedbackData[`todo-${todo.id}`] || null;
            const isCompleted = todo.status === 'completed';
            const isStarted = todo.status === 'in_progress';
            const isDeleted = todo.status === 'deleted';
            const sourceLabel = (todo.source_title || todo.source || 'Source').toString();
            const reasonShort = (todo.creation_reason || '').toString().slice(0, 80);
            
            return `
            <div class="dashboard-card bg-gray-800 rounded-xl p-6 border border-gray-700 cursor-pointer todo-item select-none" 
                 data-status="${todo.status || 'pending'}"
                 data-priority="${todo.priority || ''}"
                 data-source="${todo.source || ''}"
                 onclick="dataLoader.showTodoDetail('${this.escapeHtml(todo.id)}')">
                <div class="flex items-start gap-3">
                    <div class="flex flex-col gap-1" onclick="event.stopPropagation()">
                        <label class="flex items-center gap-1 text-xs text-gray-400" title="Mark as started">
                            <input type="checkbox" ${isStarted ? 'checked' : ''} 
                                   onclick="dataLoader.toggleTodoStarted('${this.escapeHtml(todo.id)}')"
                                   class="w-4 h-4 rounded">
                            <span>Started</span>
                        </label>
                        <label class="flex items-center gap-1 text-xs text-gray-400" title="Mark as done">
                            <input type="checkbox" ${isCompleted ? 'checked' : ''} 
                                   onclick="dataLoader.toggleTodo('${this.escapeHtml(todo.id)}')"
                                   class="w-4 h-4 rounded">
                            <span>Done</span>
                        </label>
                    </div>
                    <div class="flex-1">
                        <h3 class="font-semibold text-white mb-1 ${isCompleted ? 'line-through opacity-60' : ''}">
                            ${isStarted && !isCompleted ? '🚀 ' : ''}${this.escapeHtml(todo.title)}
                        </h3>
                        <div class="flex flex-wrap gap-1 mb-2 text-[10px]">
                            <span class="bg-indigo-700 px-2 py-1 rounded">Origin: ${this.escapeHtml(sourceLabel)}</span>
                            ${todo.source_url || todo.gmail_link ? `<span class="bg-purple-700 px-2 py-1 rounded">Linked</span>` : ''}
                            ${reasonShort ? `<span class="bg-gray-700 px-2 py-1 rounded" title="${this.escapeHtml(todo.creation_reason)}">Why: ${this.escapeHtml(reasonShort)}${todo.creation_reason && todo.creation_reason.length > 80 ? '…' : ''}</span>` : ''}
                        </div>
                        ${todo.creation_reason ? `<p class="text-xs text-purple-300 mb-2">Why: ${this.escapeHtml(todo.creation_reason)}</p>` : ''}
                        ${todo.description ? `<p class="text-sm text-gray-400 mb-2">${this.escapeHtml(todo.description)}</p>` : ''}
                        ${todo.source_preview ? `<p class="text-xs text-gray-500 mb-2 italic">Preview: ${this.escapeHtml(todo.source_preview)}</p>` : ''}
                        <div class="flex flex-wrap gap-2 text-xs mb-3">
                            ${todo.priority ? `<span class="bg-${this.getPriorityColor(todo.priority)}-600 px-2 py-1 rounded">${todo.priority}</span>` : ''}
                            ${todo.due_date ? `<span class="bg-gray-700 px-2 py-1 rounded">📅 ${this.formatDate(todo.due_date)}</span>` : ''}
                            ${todo.created_at ? `<span class="bg-gray-700 px-2 py-1 rounded text-gray-400">🕐 ${this.formatDate(todo.created_at)}</span>` : ''}
                            ${todo.source ? `<span class="bg-blue-700 px-2 py-1 rounded">${this.escapeHtml(todo.source)}</span>` : ''}
                            ${todo.source_url ? `<span class="bg-purple-700 px-2 py-1 rounded">🔗 Linked</span>` : ''}
                        </div>
                        <div class="flex gap-1 pt-2 border-t border-gray-700" onclick="event.stopPropagation()">
                            <button onclick="dataLoader.deleteTodo('${this.escapeHtml(todo.id)}')" 
                                    class="px-2 py-1 rounded text-xs bg-red-700 hover:bg-red-600" 
                                    title="Delete & never show again">🗑️ Delete</button>
                            <button onclick="dataLoader.giveFeedback('todo', '${this.escapeHtml(todo.id)}', 'up')" 
                                    class="feedback-btn px-2 py-1 rounded text-xs ${feedback === 'up' ? 'bg-green-600' : 'bg-gray-700 hover:bg-green-600'}" 
                                    title="I like this">👍</button>
                            <button onclick="dataLoader.giveFeedback('todo', '${this.escapeHtml(todo.id)}', 'neutral')" 
                                    class="feedback-btn px-2 py-1 rounded text-xs ${feedback === 'neutral' ? 'bg-blue-600' : 'bg-gray-700 hover:bg-blue-600'}" 
                                    title="Neutral">👌</button>
                            <button onclick="dataLoader.giveFeedback('todo', '${this.escapeHtml(todo.id)}', 'down')" 
                                    class="feedback-btn px-2 py-1 rounded text-xs ${feedback === 'down' ? 'bg-red-600' : 'bg-gray-700 hover:bg-red-600'}" 
                                    title="Not relevant">👎</button>
                        </div>
                    </div>
                </div>
            </div>
        `;
        }).join('');
        
        grid.innerHTML = filters + html;
    }
    
    async filterTodos(filter) {
        const items = document.querySelectorAll('.todo-item');
        const buttons = document.querySelectorAll('.todo-filter-btn');
        
        buttons.forEach(btn => {
            btn.classList.remove('bg-blue-600');
            btn.classList.add('bg-gray-700');
        });
        
        event.target.classList.remove('bg-gray-700');
        event.target.classList.add('bg-blue-600');
        
        // If filtering by completed, reload tasks with include_completed=true
        if (filter === 'completed') {
            try {
                const response = await fetch('/api/tasks?include_completed=true');
                if (response.ok) {
                    const data = await response.json();
                    this.todos = data.tasks || [];
                    this.renderTodos();
                    // After re-rendering, re-apply the filter visually
                    setTimeout(() => {
                        document.querySelectorAll('.todo-item').forEach(item => {
                            item.style.display = item.dataset.status === 'completed' ? 'block' : 'none';
                        });
                    }, 100);
                    return;
                }
            } catch (error) {
                console.error('Error loading completed tasks:', error);
            }
        } else if (filter === 'all' || filter === 'active') {
            // Reload without completed tasks for all/active filters
            try {
                const response = await fetch('/api/tasks?include_completed=false');
                if (response.ok) {
                    const data = await response.json();
                    this.todos = data.tasks || [];
                    this.renderTodos();
                    
                    if (filter === 'active') {
                        // After re-rendering, show only active tasks
                        setTimeout(() => {
                            document.querySelectorAll('.todo-item').forEach(item => {
                                const status = item.dataset.status;
                                item.style.display = (status === 'pending' || status === 'in_progress') ? 'block' : 'none';
                            });
                        }, 100);
                    }
                    return;
                }
            } catch (error) {
                console.error('Error loading tasks:', error);
            }
        }
        
        // For other filters (priority, source), just filter visible items
        items.forEach(item => {
            let show = false;
            const status = item.dataset.status;
            
            if (filter === 'all') {
                show = true;
            } else if (filter === 'active') {
                // Active = pending or in_progress (not completed or deleted)
                show = status === 'pending' || status === 'in_progress';
            } else if (filter === 'completed') {
                show = status === 'completed';
            } else if (filter.startsWith('priority-')) {
                const priority = filter.replace('priority-', '');
                show = item.dataset.priority === priority;
            } else if (filter.startsWith('source-')) {
                const source = filter.replace('source-', '');
                show = item.dataset.source === source;
            }
            
            item.style.display = show ? 'block' : 'none';
        });
    }
    
    async deleteTodo(id) {
        if (!confirm('Delete this task? It will never appear again.')) {
            return;
        }
        
        try {
            const response = await fetch(`/api/tasks/${id}`, {
                method: 'DELETE'
            });
            
            if (response.ok) {
                // Remove from local array
                this.todos = this.todos.filter(t => t.id !== id);
                this.renderTodos();
                this.updateAllCounts();
            }
        } catch (error) {
            console.error('Error deleting todo:', error);
            alert('Failed to delete task');
        }
    }
    
    renderOverviewTasks() {
        const container = document.getElementById('overview-tasks');
        if (!container) return;
        
        const topTasks = this.todos
            .filter(t => t.status !== 'completed' && t.status !== 'deleted')
            .slice(0, 5);
        
        if (topTasks.length === 0) {
            container.innerHTML = '<p class="text-gray-400">No pending tasks</p>';
            return;
        }
        
        container.innerHTML = topTasks.map(todo => `
            <div class="flex items-center gap-2 text-sm">
                <input type="checkbox" class="w-4 h-4 rounded">
                <span class="text-gray-300">${this.escapeHtml(todo.title)}</span>
            </div>
        `).join('');
    }
    
    // CALENDAR
    async loadCalendar(retryCount = 0, options = {}) {
        const hasExistingData = this.calendar.length > 0;
        const backgroundRefresh = (options.background === true || (options.preserveExisting !== false && hasExistingData)) && hasExistingData;
        if (!backgroundRefresh) {
            this.setSectionLoading('calendar-content', 'Loading calendar...');
        }

        if (!this.beginSectionFetch('calendar')) {
            return;
        }

        try {
            const response = await this.fetchJsonWithTimeout('/api/calendar', {}, 12000);
            if (response.ok) {
                const data = await response.json();
                this.calendar = data.events || [];
                this.renderCalendar();
                this.renderOverviewCalendar();
                this.startUpcomingEventMonitor();
                this.updateAllCounts();
                this.markSectionLoaded('calendar');
            } else {
                if (!backgroundRefresh) {
                    this.setSectionError('calendar-content', 'Unable to load calendar right now.');
                }
            }
        } catch (error) {
            if (this.isTimeoutAbort(error) && retryCount < 2) {
                console.warn(`Calendar load timed out, retrying (${retryCount + 1}/2)...`);
                setTimeout(() => this.loadCalendar(retryCount + 1, options), 1200);
                return;
            }
            console.error('Error loading calendar:', error);
            if (!backgroundRefresh) {
                this.setSectionError('calendar-content', this.getLoadErrorMessage('Unable to load calendar right now.', error));
            }
        } finally {
            this.endSectionFetch('calendar');
        }
    }
    
    renderCalendar() {
        const container = document.getElementById('calendar-content');
        if (!container) return;
        
        if (this.calendar.length === 0) {
            container.innerHTML = `
                <div class="text-center py-12">
                    <div class="text-6xl mb-4">📅</div>
                    <h3 class="text-xl font-semibold mb-2">No events</h3>
                    <p class="text-gray-400">Your calendar is clear</p>
                </div>
            `;
            return;
        }
        
        // Add current time indicator and upcoming event banner
        const now = new Date();
        const upcomingEvent = this.getUpcomingEvent();
        
        let header = `
            <div class="mb-6 bg-gradient-to-r from-blue-900 to-purple-900 rounded-xl p-6 border border-blue-700">
                <div class="flex justify-between items-center mb-4">
                    <div>
                        <div class="text-sm text-gray-300">Current Time</div>
                        <div class="text-3xl font-bold" id="current-time">${this.formatCurrentTime()}</div>
                    </div>
                    <div class="text-6xl">🕐</div>
                </div>
                ${upcomingEvent ? `
                    <div class="border-t border-blue-700 pt-4 mt-4">
                        <div class="text-sm text-blue-300 mb-2">🔔 UPCOMING EVENT</div>
                        <div class="flex justify-between items-start">
                            <div class="flex-1">
                                <h3 class="text-xl font-semibold text-white mb-1">${this.escapeHtml(upcomingEvent.summary || upcomingEvent.title)}</h3>
                                <div class="text-sm text-gray-300 mb-2">
                                    ⏰ ${this.formatEventTime(upcomingEvent)} 
                                    <span class="text-yellow-400 font-semibold">(${this.getTimeUntil(upcomingEvent)})</span>
                                </div>
                                ${upcomingEvent.location ? `<div class="text-sm text-gray-400 mb-2">📍 ${this.escapeHtml(upcomingEvent.location)}</div>` : ''}
                                ${this.extractMeetingLink(upcomingEvent) ? `
                                    <a href="${this.extractMeetingLink(upcomingEvent)}" target="_blank"
                                       class="inline-flex items-center gap-2 bg-green-600 hover:bg-green-700 px-4 py-2 rounded-lg text-sm font-semibold">
                                        🎥 Join Meeting
                                    </a>
                                ` : ''}
                            </div>
                            <button onclick="dataLoader.dismissEventAlert('${upcomingEvent.event_id}')" 
                                    class="ml-4 text-gray-400 hover:text-white">
                                ✕
                            </button>
                        </div>
                    </div>
                ` : '<div class="text-center text-gray-400 border-t border-blue-700 pt-4 mt-4">No upcoming events</div>'}
            </div>
        `;
        
        // Group events by day
        const grouped = this.groupEventsByDay(this.calendar);
        
        container.innerHTML = header + Object.entries(grouped).map(([day, events]) => `
            <div class="mb-6">
                <h3 class="text-xl font-bold mb-3 text-blue-400">${day}</h3>
                <div class="space-y-2">
                    ${events.map(event => {
                        const meetingLink = this.extractMeetingLink(event);
                        return `
                        <div class="bg-gray-800 rounded-lg p-4 border border-gray-700 cursor-pointer hover:border-gray-600"
                             onclick="dataLoader.showEventDetail('${this.escapeHtml(event.event_id)}')">
                            <div class="flex justify-between items-start">
                                <div class="flex-1">
                                    <h4 class="font-semibold text-white">${this.escapeHtml(event.summary || event.title)}</h4>
                                    ${event.location ? `<p class="text-sm text-gray-400">📍 ${this.escapeHtml(event.location)}</p>` : ''}
                                    ${event.summary_ai ? `
                                        <div class="mt-2 p-2 bg-gray-700 rounded text-sm">
                                            <div class="text-xs text-gray-400 mb-1">AI Summary:</div>
                                            <div class="text-white">${this.escapeHtml(event.summary_ai)}</div>
                                        </div>
                                    ` : ''}
                                    <div class="flex gap-2 mt-2" onclick="event.stopPropagation()">
                                        ${meetingLink ? `
                                            <a href="${meetingLink}" target="_blank"
                                               class="inline-flex items-center gap-1 text-xs bg-blue-600 hover:bg-blue-700 px-2 py-1 rounded">
                                                🎥 Join
                                            </a>
                                        ` : ''}
                                        <button data-item-type="calendar" 
                                                data-item-id="${this.escapeHtml(event.event_id)}" 
                                                data-item-data="${this.escapeHtml(JSON.stringify(event))}"
                                                onclick="dataLoader.summarizeItemFromButton(this)"
                                                class="inline-flex items-center gap-1 text-xs bg-purple-600 hover:bg-purple-700 px-2 py-1 rounded"
                                                title="Summarize and scan for tasks">
                                            🤖 AI
                                        </button>
                                    </div>
                                </div>
                                <span class="text-sm text-blue-400">${this.formatEventTime(event)}</span>
                            </div>
                        </div>
                    `;
                    }).join('')}
                </div>
            </div>
        `).join('');
        
        // Update current time every second
        this.startClockUpdate();
    }
    
    renderOverviewCalendar() {
        const container = document.getElementById('overview-calendar');
        if (!container) return;
        
        const today = new Date().toDateString();
        const todayEvents = this.calendar.filter(e => {
            const startDate = e.start && e.start.dateTime ? e.start.dateTime : e.start;
            const eventDate = new Date(startDate).toDateString();
            return eventDate === today;
        });
        
        if (todayEvents.length === 0) {
            container.innerHTML = '<p class="text-gray-400">No events today</p>';
            return;
        }
        
        container.innerHTML = todayEvents.map(event => `
            <div class="flex justify-between items-center text-sm">
                <span class="text-gray-300">${this.escapeHtml(event.summary || event.title)}</span>
                <span class="text-blue-400">${this.formatEventTime(event)}</span>
            </div>
        `).join('');
    }
    
    // EMAILS
    async loadEmails(forceRefresh = false, retryCount = 0, options = {}) {
        const hasExistingData = this.emails.length > 0;
        const backgroundRefresh = (options.background === true || (options.preserveExisting !== false && hasExistingData)) && hasExistingData;
        if (!backgroundRefresh) {
            this.setSectionLoading('emails-grid', 'Loading emails...');
        }

        if (!this.beginSectionFetch('emails')) {
            return;
        }

        try {
            // Add cache-busting parameter if force refresh
            const url = forceRefresh 
                ? `/api/email?refresh=${Date.now()}` 
                : '/api/email';
            const response = await this.fetchJsonWithTimeout(url, {}, 15000);
            if (response.ok) {
                const data = await response.json();
                // Filter out noreply and no-reply emails
                this.emails = (data.emails || []).filter(email => {
                    const sender = (email.sender || email.from || '').toLowerCase();
                    return !sender.includes('noreply') && !sender.includes('no-reply');
                });
                
                const unreadCount = this.emails.filter(e => !e.read).length;
                const readCount = this.emails.filter(e => e.read).length;
                console.log(`Loaded ${this.emails.length} emails (${unreadCount} unread, ${readCount} read)`);
                this.renderEmails();
                this.updateAllCounts();
                this.markSectionLoaded('emails');
            } else {
                if (!backgroundRefresh) {
                    this.setSectionError('emails-grid', 'Unable to load emails right now.');
                }
            }
        } catch (error) {
            if (this.isTimeoutAbort(error) && retryCount < 2) {
                console.warn(`Email load timed out, retrying (${retryCount + 1}/2)...`);
                setTimeout(() => this.loadEmails(forceRefresh, retryCount + 1, options), 1200);
                return;
            }
            console.error('Error loading emails:', error);
            if (!backgroundRefresh) {
                this.setSectionError('emails-grid', this.getLoadErrorMessage('Unable to load emails right now.', error));
            }
        } finally {
            this.endSectionFetch('emails');
        }
    }
    
    async refreshEmails() {
        this.showNotification('Refreshing emails...', 'info');
        try {
            await this.loadEmails(true); // Force refresh with cache busting
            this.updateAllCounts();
            this.renderEmails();
            this.showNotification('Emails refreshed!', 'success');
        } catch (error) {
            console.error('Error refreshing emails:', error);
            this.showNotification('Failed to refresh emails', 'error');
        }
    }
    
    showScanEmailsModal() {
        const today = new Date();
        const thirtyDaysAgo = new Date(today);
        thirtyDaysAgo.setDate(thirtyDaysAgo.getDate() - 30);
        
        const content = `
            <div class="space-y-4">
                <p class="text-gray-300">Scan your emails for tasks and action items. This will analyze emails from a specific date range and create todos for any emails that require action.</p>
                
                <div class="bg-yellow-900/30 border border-yellow-600 rounded-lg p-4">
                    <p class="text-yellow-200 text-sm">⚠️ <strong>Note:</strong> This uses AI to analyze emails and will only create tasks for emails with clear action items, not newsletters or spam.</p>
                </div>
                
                <div class="space-y-3">
                    <div>
                        <label class="block text-sm font-medium text-gray-300 mb-1">Start Date</label>
                        <input type="date" id="scan-start-date" 
                               value="${thirtyDaysAgo.toISOString().split('T')[0]}"
                               max="${today.toISOString().split('T')[0]}"
                               class="w-full bg-gray-700 border border-gray-600 rounded px-3 py-2 text-white">
                    </div>
                    
                    <div>
                        <label class="block text-sm font-medium text-gray-300 mb-1">End Date</label>
                        <input type="date" id="scan-end-date" 
                               value="${today.toISOString().split('T')[0]}"
                               max="${today.toISOString().split('T')[0]}"
                               class="w-full bg-gray-700 border border-gray-600 rounded px-3 py-2 text-white">
                    </div>
                    
                    <div>
                        <label class="block text-sm font-medium text-gray-300 mb-1">Max Emails to Scan</label>
                        <select id="scan-max-emails" class="w-full bg-gray-700 border border-gray-600 rounded px-3 py-2 text-white">
                            <option value="50">50 emails</option>
                            <option value="100" selected>100 emails</option>
                            <option value="200">200 emails</option>
                            <option value="500">500 emails</option>
                        </select>
                    </div>
                </div>
                
                <div class="flex gap-3 pt-4">
                    <button onclick="dataLoader.startEmailScan()" 
                            class="flex-1 bg-purple-600 hover:bg-purple-700 px-4 py-2 rounded-lg font-semibold">
                        🔍 Start Scan
                    </button>
                    <button onclick="closeModal()" 
                            class="flex-1 bg-gray-600 hover:bg-gray-700 px-4 py-2 rounded-lg font-semibold">
                        Cancel
                    </button>
                </div>
                
                <div id="scan-progress" class="hidden mt-4">
                    <div class="bg-gray-700 rounded-lg p-4">
                        <div class="flex items-center gap-3 mb-2">
                            <div class="animate-spin rounded-full h-5 w-5 border-b-2 border-purple-400"></div>
                            <span class="text-purple-400 font-semibold">Scanning emails...</span>
                        </div>
                        <p id="scan-status" class="text-sm text-gray-400">Initializing...</p>
                        <div id="scan-results" class="mt-3 text-sm"></div>
                    </div>
                </div>
            </div>
        `;
        
        showModal('Scan Emails for Tasks', content);
    }
    
    async startEmailScan() {
        const startDate = document.getElementById('scan-start-date').value;
        const endDate = document.getElementById('scan-end-date').value;
        const maxEmails = document.getElementById('scan-max-emails').value;
        
        if (!startDate || !endDate) {
            this.showNotification('Please select both start and end dates', 'error');
            return;
        }
        
        // Show progress section
        const progressDiv = document.getElementById('scan-progress');
        const statusDiv = document.getElementById('scan-status');
        const resultsDiv = document.getElementById('scan-results');
        progressDiv.classList.remove('hidden');
        
        statusDiv.textContent = `Scanning up to ${maxEmails} emails from ${startDate} to ${endDate}...`;
        
        try {
            const response = await fetch('/api/email/scan-for-tasks', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    start_date: startDate,
                    end_date: endDate,
                    max_emails: parseInt(maxEmails)
                })
            });
            
            if (response.ok) {
                const data = await response.json();
                statusDiv.textContent = `✅ Scan complete!`;
                resultsDiv.innerHTML = `
                    <div class="space-y-2">
                        <p class="text-green-400">✅ Scanned ${data.emails_scanned} emails</p>
                        <p class="text-blue-400">📋 Created ${data.tasks_created} new tasks</p>
                        <p class="text-gray-400">⏭️ Skipped ${data.emails_skipped} emails (spam/newsletters)</p>
                        <p class="text-yellow-400">⚠️ ${data.tasks_skipped} duplicate tasks avoided</p>
                    </div>
                    <button onclick="closeModal(); dataLoader.loadTodos();" 
                            class="mt-4 w-full bg-green-600 hover:bg-green-700 px-4 py-2 rounded-lg font-semibold">
                        View Tasks
                    </button>
                `;
                this.showNotification(`Created ${data.tasks_created} tasks from ${data.emails_scanned} emails`, 'success');
            } else {
                const error = await response.json();
                statusDiv.textContent = `❌ Error: ${error.detail || 'Failed to scan emails'}`;
                resultsDiv.innerHTML = '';
            }
        } catch (error) {
            statusDiv.textContent = `❌ Error: ${error.message}`;
            resultsDiv.innerHTML = '';
            this.showNotification('Failed to scan emails', 'error');
        }
    }
    
    renderEmails() {
        const grid = document.getElementById('emails-grid');
        if (!grid) {
            console.error('emails-grid element not found');
            return;
        }
        
        console.log(`Rendering ${this.emails.length} emails`);
        
        if (this.emails.length === 0) {
            grid.innerHTML = `
                <div class="text-center py-12">
                    <div class="text-6xl mb-4">📧</div>
                    <h3 class="text-xl font-semibold mb-2">Inbox Zero!</h3>
                    <p class="text-gray-400">No unread emails</p>
                </div>
            `;
            return;
        }
        
        // Add filter buttons
        const labels = [...new Set(this.emails.flatMap(e => e.labels || []))];
        
        const filters = `
            <div class="mb-4 flex gap-2 flex-wrap col-span-full">
                <input type="text" id="email-search" placeholder="Search emails..." 
                       oninput="dataLoader.filterEmails()" 
                       class="flex-1 max-w-md bg-gray-700 border border-gray-600 rounded px-3 py-1 text-sm text-white">
                <button onclick="dataLoader.filterEmails('all')" 
                        class="email-filter-btn px-3 py-1 bg-blue-600 rounded text-sm">All</button>
                <button onclick="dataLoader.filterEmails('unread')" 
                        class="email-filter-btn px-3 py-1 bg-gray-700 rounded text-sm hover:bg-gray-600">Unread</button>
                <button onclick="dataLoader.filterEmails('read')" 
                        class="email-filter-btn px-3 py-1 bg-gray-700 rounded text-sm hover:bg-gray-600">Read</button>
                <button onclick="dataLoader.filterEmails('has-todos')" 
                        class="email-filter-btn px-3 py-1 bg-gray-700 rounded text-sm hover:bg-gray-600">Has Tasks</button>
                <button onclick="dataLoader.filterEmails('high-priority')" 
                        class="email-filter-btn px-3 py-1 bg-gray-700 rounded text-sm hover:bg-gray-600">High Priority</button>
                <button onclick="dataLoader.filterEmails('high-risk')" 
                        class="email-filter-btn px-3 py-1 bg-red-700 rounded text-sm hover:bg-red-600">⚠️ High Risk</button>
                <button onclick="dataLoader.filterEmails('safe')" 
                        class="email-filter-btn px-3 py-1 bg-green-700 rounded text-sm hover:bg-green-600">✓ Safe</button>
                <button onclick="dataLoader.filterEmails('clients')" 
                        class="email-filter-btn px-3 py-1 bg-yellow-600 rounded text-sm hover:bg-yellow-500">⭐ Clients</button>
                ${labels.map(label => 
                    `<button onclick="dataLoader.filterEmails('label-${this.escapeHtml(label)}')" 
                             class="email-filter-btn px-3 py-1 bg-gray-700 rounded text-sm hover:bg-gray-600">${this.escapeHtml(label)}</button>`
                ).join('')}
            </div>
        `;
        
        // Update email stats
        this.updateEmailStats();
        
        // Sort emails: clients first, then by date
        const sortedEmails = [...this.emails].sort((a, b) => {
            const aIsClient = this.isClientEmail(a);
            const bIsClient = this.isClientEmail(b);
            if (aIsClient && !bIsClient) return -1;
            if (!aIsClient && bIsClient) return 1;
            // Within same priority, sort by date (newest first)
            const aDate = new Date(a.received_date || a.date || 0);
            const bDate = new Date(b.received_date || b.date || 0);
            return bDate - aDate;
        });
        
        // Check for new client emails and show alert
        this.checkClientEmailAlerts(sortedEmails);
        
        const html = sortedEmails.map(email => {
            const isClient = this.isClientEmail(email);
            const feedback = this.feedbackData[`email-${email.id}`] || null;
            const readClass = email.read ? 'opacity-70 bg-gray-800' : 'bg-gray-750 border-l-4 border-l-blue-500';
            const readIndicator = email.read ? 
                '<span class="text-gray-500 text-xs">✓</span>' : 
                '<span class="flex items-center gap-1 text-blue-400 text-xs font-semibold"><span class="w-2 h-2 bg-blue-500 rounded-full animate-pulse"></span></span>';
            const smartTag = this.getSmartTagForEmail(email);
            const starIcon = email.is_starred ? '⭐' : '☆';
            
            // Format the date/time nicely
            const emailDate = email.received_date || email.date;
            const timeAgo = this.getTimeAgo(emailDate);
            
            // Trust Layer Badge - on-demand scanning only
            let riskBadge = '';
            if (email.risk_score && email.risk_score >= 7) {
                riskBadge = '<span class="text-xs bg-red-600 px-2 py-1 rounded">⚠️ Risk</span>';
            }
            if (typeof trustUI !== 'undefined' && trustUI) {
                trustUI.getTrustReport(email).then(report => {
                    if (report && report.score !== undefined) {
                        const badge = trustUI.getTrustBadge(report.score, report.risk_level);
                        const container = document.querySelector(`[data-email-id="${this.escapeHtml(email.id)}"] .trust-badge-container`);
                        if (container) {
                            container.innerHTML = badge;
                        }
                    }
                }).catch(err => {
                    console.error('Trust report fetch failed for', email.id, err);
                });
            }
            
            // Smart tag with tooltip
            let smartTagHtml = '';
            if (smartTag) {
                const domain = email.sender.split('@')[1] || email.sender;
                smartTagHtml = `<span class="text-xs bg-purple-600 px-2 py-1 rounded whitespace-nowrap cursor-help" title="Auto-tagged based on your feedback patterns from ${domain}">${smartTag}</span>`;
            }
            
            // Client badge
            const clientBadge = isClient ? '<span class="text-xs bg-yellow-500 text-black font-bold px-2 py-1 rounded">⭐ CLIENT</span>' : '';
            // Client styling - add yellow border for client emails
            const clientClass = isClient ? 'ring-2 ring-yellow-500' : '';
            
            return `
            <div class="rounded-lg p-3 border border-gray-700 hover:border-gray-500 ${readClass} ${clientClass} flex items-start gap-3"
                 data-email-id="${this.escapeHtml(email.id)}">
                <div class="flex items-center gap-2 pt-1" onclick="event.stopPropagation()">
                    <input type="checkbox" class="email-checkbox w-4 h-4 rounded" 
                           data-email-checkbox="${this.escapeHtml(email.id)}"
                           onchange="window.emailClient && emailClient.toggleEmailSelection('${this.escapeHtml(email.id)}', this.checked)">
                    <button onclick="window.emailClient && emailClient.starEmail('${this.escapeHtml(email.id)}', ${!email.is_starred}); this.textContent = this.textContent === '☆' ? '⭐' : '☆';" 
                            class="text-lg hover:scale-110 transition-transform" title="Star">${starIcon}</button>
                </div>
                <div class="flex-1 min-w-0 cursor-pointer" onclick="window.emailClient && emailClient.showEmailDetail('${this.escapeHtml(email.id)}')">
                    <div class="flex items-center gap-2 mb-1">
                        ${readIndicator}
                        ${clientBadge}
                        <span class="font-semibold text-white truncate">${this.escapeHtml(email.sender)}</span>
                        <span class="text-xs text-gray-500 ml-auto whitespace-nowrap">${timeAgo}</span>
                    </div>
                    <div class="flex items-center gap-2 mb-1">
                        <h4 class="font-medium text-gray-200 truncate flex-1">${this.escapeHtml(email.subject)}</h4>
                        <div class="flex gap-1 items-center flex-shrink-0">
                            <div class="trust-badge-container">${riskBadge}</div>
                            ${smartTagHtml}
                            ${email.has_todos ? '<span class="text-xs bg-orange-600 px-1 py-0.5 rounded">📋</span>' : ''}
                        </div>
                    </div>
                    ${email.snippet ? `<p class="text-sm text-gray-400 truncate">${this.escapeHtml(email.snippet)}</p>` : ''}
                </div>
                <div class="flex flex-col gap-1" onclick="event.stopPropagation()">
                    <button onclick="window.emailClient && emailClient.showComposeModal('reply', {id:'${this.escapeHtml(email.id)}', from:'${this.escapeHtml(email.sender)}', subject:'${this.escapeHtml(email.subject)}', snippet:'${this.escapeHtml((email.snippet || '').replace(/'/g, ''))}'})"
                            class="px-2 py-1 rounded text-xs bg-blue-600 hover:bg-blue-700" title="Reply">↩️</button>
                    <button onclick="window.emailClient && emailClient.archiveEmail('${this.escapeHtml(email.id)}'); this.closest('[data-email-id]').remove();"
                            class="px-2 py-1 rounded text-xs bg-gray-700 hover:bg-gray-600" title="Archive">📥</button>
                    <button onclick="if(confirm('Delete?')){window.emailClient && emailClient.deleteEmail('${this.escapeHtml(email.id)}'); this.closest('[data-email-id]').remove();}"
                            class="px-2 py-1 rounded text-xs bg-gray-700 hover:bg-red-600" title="Delete">🗑️</button>
                    ${!isClient ? `<button onclick="dataLoader.addSenderAsClient('${this.escapeHtml(email.sender)}')"
                            class="px-2 py-1 rounded text-xs bg-gray-700 hover:bg-yellow-600" title="Add as Client">⭐</button>` : ''}
                </div>
            </div>
        `;
        }).join('');
        
        grid.innerHTML = filters + html;
    }
    
    updateEmailStats() {
        const totalEl = document.getElementById('email-total-count');
        const unreadEl = document.getElementById('email-unread-count');
        const starredEl = document.getElementById('email-starred-count');
        const riskEl = document.getElementById('email-highrisk-count');
        
        if (totalEl) totalEl.textContent = this.emails.length;
        if (unreadEl) unreadEl.textContent = this.emails.filter(e => !e.read).length;
        if (starredEl) starredEl.textContent = this.emails.filter(e => e.is_starred).length;
        if (riskEl) riskEl.textContent = this.emails.filter(e => e.risk_score >= 7).length;
    }
    
    filterEmails(filter = null) {
        const searchInput = document.getElementById('email-search');
        const searchTerm = searchInput ? searchInput.value.toLowerCase() : '';
        
        // Store current filter for use when rendering
        this.currentEmailFilter = filter;
        this.currentEmailSearch = searchTerm;
        
        // Update button states
        document.querySelectorAll('.email-filter-btn').forEach(btn => {
            btn.classList.remove('bg-blue-600', 'bg-red-700', 'bg-green-700');
            if (btn.textContent.includes('High Risk')) {
                btn.classList.add('bg-red-700');
            } else if (btn.textContent.includes('Safe')) {
                btn.classList.add('bg-green-700');
            } else if (btn.textContent.includes('Clients')) {
                btn.classList.add('bg-yellow-600');
            } else {
                btn.classList.add('bg-gray-700');
            }
        });
        
        if (filter && event && event.target) {
            event.target.classList.remove('bg-gray-700', 'bg-red-700', 'bg-green-700', 'bg-yellow-600');
            event.target.classList.add('bg-blue-600');
        }
        
        // Filter the full email list and re-render
        let filteredEmails = [...this.emails];
        
        // Apply filter
        if (filter && filter !== 'all') {
            filteredEmails = filteredEmails.filter(email => {
                if (filter === 'unread') return !email.read;
                if (filter === 'read') return email.read;
                if (filter === 'has-todos') return email.has_todos;
                if (filter === 'high-priority') return email.priority === 'high';
                if (filter === 'high-risk') return (email.risk_score || 0) >= 7;
                if (filter === 'safe') return (email.risk_score || 0) < 3;
                if (filter === 'clients') return this.isClientEmail(email);
                if (filter.startsWith('label-')) {
                    const label = filter.substring(6);
                    return email.labels && email.labels.includes(label);
                }
                return true;
            });
        }
        
        // Apply search across ALL emails (not just displayed)
        if (searchTerm) {
            filteredEmails = filteredEmails.filter(email => {
                const searchableText = `${email.sender} ${email.subject} ${email.snippet || ''} ${(email.labels || []).join(' ')}`.toLowerCase();
                return searchableText.includes(searchTerm);
            });
        }
        
        // Render the filtered emails
        this.renderFilteredEmails(filteredEmails);
    }
    
    renderFilteredEmails(emails) {
        const grid = document.getElementById('emails-grid');
        if (!grid) return;
        
        // Keep the filter bar at the top
        const filterBar = grid.querySelector('.col-span-full');
        
        // Sort emails: clients first, then by date
        const sortedEmails = [...emails].sort((a, b) => {
            const aIsClient = this.isClientEmail(a);
            const bIsClient = this.isClientEmail(b);
            if (aIsClient && !bIsClient) return -1;
            if (!aIsClient && bIsClient) return 1;
            const aDate = new Date(a.received_date || a.date || 0);
            const bDate = new Date(b.received_date || b.date || 0);
            return bDate - aDate;
        });
        
        if (sortedEmails.length === 0) {
            const filterHtml = filterBar ? filterBar.outerHTML : '';
            grid.innerHTML = filterHtml + `
                <div class="col-span-full text-center py-12">
                    <div class="text-6xl mb-4">🔍</div>
                    <h3 class="text-xl font-semibold mb-2">No emails found</h3>
                    <p class="text-gray-400">Try a different search or filter</p>
                </div>
            `;
            return;
        }
        
        const html = sortedEmails.map(email => {
            const isClient = this.isClientEmail(email);
            const feedback = this.feedbackData[`email-${email.id}`] || null;
            const readClass = email.read ? 'opacity-70 bg-gray-800' : 'bg-gray-750 border-l-4 border-l-blue-500';
            const readIndicator = email.read ? 
                '<span class="text-gray-500 text-xs">✓</span>' : 
                '<span class="flex items-center gap-1 text-blue-400 text-xs font-semibold"><span class="w-2 h-2 bg-blue-500 rounded-full animate-pulse"></span></span>';
            const smartTag = this.getSmartTagForEmail(email);
            const starIcon = email.is_starred ? '⭐' : '☆';
            const emailDate = email.received_date || email.date;
            const timeAgo = this.getTimeAgo(emailDate);
            
            let riskBadge = '';
            if (email.risk_score && email.risk_score >= 7) {
                riskBadge = '<span class="text-xs bg-red-600 px-2 py-1 rounded">⚠️ Risk</span>';
            }
            
            let smartTagHtml = '';
            if (smartTag) {
                const domain = email.sender.split('@')[1] || email.sender;
                smartTagHtml = `<span class="text-xs bg-purple-600 px-2 py-1 rounded whitespace-nowrap cursor-help" title="Auto-tagged based on your feedback patterns from ${domain}">${smartTag}</span>`;
            }
            
            const clientBadge = isClient ? '<span class="text-xs bg-yellow-500 text-black font-bold px-2 py-1 rounded">⭐ CLIENT</span>' : '';
            const clientClass = isClient ? 'ring-2 ring-yellow-500' : '';
            
            return `
            <div class="rounded-lg p-3 border border-gray-700 hover:border-gray-500 ${readClass} ${clientClass} flex items-start gap-3"
                 data-email-id="${this.escapeHtml(email.id)}">
                <div class="flex items-center gap-2 pt-1" onclick="event.stopPropagation()">
                    <input type="checkbox" class="email-checkbox w-4 h-4 rounded" 
                           data-email-checkbox="${this.escapeHtml(email.id)}"
                           onchange="window.emailClient && emailClient.toggleEmailSelection('${this.escapeHtml(email.id)}', this.checked)">
                    <button onclick="window.emailClient && emailClient.starEmail('${this.escapeHtml(email.id)}', ${!email.is_starred}); this.textContent = this.textContent === '☆' ? '⭐' : '☆';" 
                            class="text-lg hover:scale-110 transition-transform" title="Star">${starIcon}</button>
                </div>
                <div class="flex-1 min-w-0 cursor-pointer" onclick="window.emailClient && emailClient.showEmailDetail('${this.escapeHtml(email.id)}')">
                    <div class="flex items-center gap-2 mb-1">
                        ${readIndicator}
                        ${clientBadge}
                        <span class="font-semibold text-white truncate">${this.escapeHtml(email.sender)}</span>
                        <span class="text-xs text-gray-500 ml-auto whitespace-nowrap">${timeAgo}</span>
                    </div>
                    <div class="flex items-center gap-2 mb-1">
                        <h4 class="font-medium text-gray-200 truncate flex-1">${this.escapeHtml(email.subject)}</h4>
                        <div class="flex gap-1 items-center flex-shrink-0">
                            <div class="trust-badge-container">${riskBadge}</div>
                            ${smartTagHtml}
                            ${email.has_todos ? '<span class="text-xs bg-orange-600 px-1 py-0.5 rounded">📋</span>' : ''}
                        </div>
                    </div>
                    ${email.snippet ? `<p class="text-sm text-gray-400 truncate">${this.escapeHtml(email.snippet)}</p>` : ''}
                </div>
                <div class="flex flex-col gap-1" onclick="event.stopPropagation()">
                    <button onclick="window.emailClient && emailClient.showComposeModal('reply', {id:'${this.escapeHtml(email.id)}', from:'${this.escapeHtml(email.sender)}', subject:'${this.escapeHtml(email.subject)}', snippet:'${this.escapeHtml((email.snippet || '').replace(/'/g, ''))}'})"
                            class="px-2 py-1 rounded text-xs bg-blue-600 hover:bg-blue-700" title="Reply">↩️</button>
                    <button onclick="window.emailClient && emailClient.archiveEmail('${this.escapeHtml(email.id)}'); this.closest('[data-email-id]').remove();"
                            class="px-2 py-1 rounded text-xs bg-gray-700 hover:bg-gray-600" title="Archive">📥</button>
                    <button onclick="if(confirm('Delete?')){window.emailClient && emailClient.deleteEmail('${this.escapeHtml(email.id)}'); this.closest('[data-email-id]').remove();}"
                            class="px-2 py-1 rounded text-xs bg-gray-700 hover:bg-red-600" title="Delete">🗑️</button>
                    ${!isClient ? `<button onclick="dataLoader.addSenderAsClient('${this.escapeHtml(email.sender)}')"
                            class="px-2 py-1 rounded text-xs bg-gray-700 hover:bg-yellow-600" title="Add as Client">⭐</button>` : ''}
                </div>
            </div>
        `;
        }).join('');
        
        const filterHtml = filterBar ? filterBar.outerHTML : '';
        grid.innerHTML = filterHtml + html;
        
        // Update stats based on filtered view
        const totalEl = document.getElementById('email-total-count');
        if (totalEl) totalEl.textContent = sortedEmails.length;
    }
    
    // CLIENT EMAIL MANAGEMENT
    isClientEmail(email) {
        if (!email || !email.sender) return false;
        const senderLower = email.sender.toLowerCase();
        const senderDomain = senderLower.split('@')[1] || '';
        
        // Check against client domains
        for (const domain of this.clientDomains) {
            if (senderDomain === domain.toLowerCase() || senderDomain.endsWith('.' + domain.toLowerCase())) {
                return true;
            }
        }
        
        // Check against specific client email addresses
        for (const addr of this.clientEmailAddresses) {
            if (senderLower.includes(addr.toLowerCase())) {
                return true;
            }
        }
        
        return false;
    }
    
    checkClientEmailAlerts(emails) {
        const clientEmails = emails.filter(e => this.isClientEmail(e) && !e.read);
        const newClientEmails = clientEmails.filter(e => !this.lastSeenClientEmails.includes(e.id));
        
        if (newClientEmails.length > 0) {
            // Show notification
            const count = newClientEmails.length;
            const firstSender = newClientEmails[0].sender;
            const message = count === 1 
                ? `New email from client: ${firstSender}` 
                : `${count} new emails from clients`;
            
            this.showNotification(`⭐ ${message}`, 'warning', 10000);
            
            // Play sound alert if not muted
            if (!this.globalMuted) {
                this.playAlertSound();
            }
            
            // Update last seen
            this.lastSeenClientEmails = [...this.lastSeenClientEmails, ...newClientEmails.map(e => e.id)];
            localStorage.setItem('lastSeenClientEmails', JSON.stringify(this.lastSeenClientEmails));
        }
    }
    
    playAlertSound() {
        try {
            // Create a simple alert tone
            const audioContext = new (window.AudioContext || window.webkitAudioContext)();
            const oscillator = audioContext.createOscillator();
            const gainNode = audioContext.createGain();
            
            oscillator.connect(gainNode);
            gainNode.connect(audioContext.destination);
            
            oscillator.frequency.value = 880; // A5 note
            oscillator.type = 'sine';
            gainNode.gain.setValueAtTime(0.3, audioContext.currentTime);
            gainNode.gain.exponentialRampToValueAtTime(0.01, audioContext.currentTime + 0.5);
            
            oscillator.start(audioContext.currentTime);
            oscillator.stop(audioContext.currentTime + 0.5);
        } catch (e) {
            console.warn('Could not play alert sound:', e);
        }
    }
    
    showManageClientsModal() {
        const currentDomains = this.clientDomains.join('\\n');
        const currentAddresses = this.clientEmailAddresses.join('\\n');
        
        const content = `
            <div class="space-y-4">
                <p class="text-gray-300">Emails from these domains and addresses will be highlighted and appear at the top of your inbox with alerts.</p>
                
                <div>
                    <label class="block text-sm font-medium text-gray-300 mb-1">Client Domains (one per line)</label>
                    <textarea id="client-domains-input" rows="4" 
                              class="w-full bg-gray-700 border border-gray-600 rounded px-3 py-2 text-white placeholder-gray-400"
                              placeholder="example.com&#10;client-company.com">${currentDomains}</textarea>
                    <p class="text-xs text-gray-500 mt-1">e.g., acme.com, bigclient.io</p>
                </div>
                
                <div>
                    <label class="block text-sm font-medium text-gray-300 mb-1">Client Email Addresses (one per line)</label>
                    <textarea id="client-addresses-input" rows="4" 
                              class="w-full bg-gray-700 border border-gray-600 rounded px-3 py-2 text-white placeholder-gray-400"
                              placeholder="john@example.com&#10;ceo@bigclient.com">${currentAddresses}</textarea>
                    <p class="text-xs text-gray-500 mt-1">For specific people not from a client domain</p>
                </div>
                
                <div class="flex gap-3 pt-4">
                    <button onclick="dataLoader.saveClientSettings()" 
                            class="flex-1 bg-yellow-600 hover:bg-yellow-700 px-4 py-2 rounded-lg font-semibold">
                        💾 Save Settings
                    </button>
                    <button onclick="closeModal()" 
                            class="flex-1 bg-gray-600 hover:bg-gray-700 px-4 py-2 rounded-lg font-semibold">
                        Cancel
                    </button>
                </div>
            </div>
        `;
        
        showModal('⭐ Manage Client Emails', content);
    }
    
    saveClientSettings() {
        const domainsInput = document.getElementById('client-domains-input');
        const addressesInput = document.getElementById('client-addresses-input');
        
        if (domainsInput) {
            this.clientDomains = domainsInput.value.split('\\n').map(s => s.trim()).filter(s => s);
            localStorage.setItem('clientDomains', JSON.stringify(this.clientDomains));
        }
        
        if (addressesInput) {
            this.clientEmailAddresses = addressesInput.value.split('\\n').map(s => s.trim()).filter(s => s);
            localStorage.setItem('clientEmailAddresses', JSON.stringify(this.clientEmailAddresses));
        }
        
        // Clear last seen to re-trigger alerts for any current client emails
        this.lastSeenClientEmails = [];
        localStorage.setItem('lastSeenClientEmails', '[]');
        
        closeModal();
        this.showNotification('Client settings saved! Refreshing emails...', 'success');
        this.renderEmails();
    }
    
    // Quick add current sender as client
    addSenderAsClient(sender) {
        const email = sender.toLowerCase();
        const domain = email.split('@')[1];
        
        if (domain && !this.clientDomains.includes(domain)) {
            // Ask if they want to add domain or just this address
            const content = `
                <div class="space-y-4">
                    <p class="text-gray-300">Add <strong>${sender}</strong> as a client?</p>
                    <div class="flex flex-col gap-2">
                        <button onclick="dataLoader.addClientDomain('${domain}'); closeModal();"
                                class="w-full bg-yellow-600 hover:bg-yellow-700 px-4 py-2 rounded-lg font-semibold">
                            Add entire domain: @${domain}
                        </button>
                        <button onclick="dataLoader.addClientAddress('${email}'); closeModal();"
                                class="w-full bg-gray-600 hover:bg-gray-700 px-4 py-2 rounded-lg font-semibold">
                            Add just this address
                        </button>
                        <button onclick="closeModal()"
                                class="w-full bg-gray-700 hover:bg-gray-800 px-4 py-2 rounded-lg">
                            Cancel
                        </button>
                    </div>
                </div>
            `;
            showModal('⭐ Add Client', content);
        } else if (!this.clientEmailAddresses.includes(email)) {
            this.addClientAddress(email);
        }
    }
    
    addClientDomain(domain) {
        if (!this.clientDomains.includes(domain)) {
            this.clientDomains.push(domain);
            localStorage.setItem('clientDomains', JSON.stringify(this.clientDomains));
            this.lastSeenClientEmails = [];
            localStorage.setItem('lastSeenClientEmails', '[]');
            this.showNotification(`Added @${domain} as client domain`, 'success');
            this.renderEmails();
        }
    }
    
    addClientAddress(address) {
        if (!this.clientEmailAddresses.includes(address)) {
            this.clientEmailAddresses.push(address);
            localStorage.setItem('clientEmailAddresses', JSON.stringify(this.clientEmailAddresses));
            this.lastSeenClientEmails = [];
            localStorage.setItem('lastSeenClientEmails', '[]');
            this.showNotification(`Added ${address} as client`, 'success');
            this.renderEmails();
        }
    }
    
    // DASHBOARDS
    async loadDashboards() {
        try {
            const response = await fetch('/api/dashboards');
            if (response.ok) {
                const data = await response.json();
                this.dashboards = data.data || {};
                this.renderDashboards();
            }
        } catch (error) {
            console.error('Error loading dashboards:', error);
        }
    }
    
    renderDashboards() {
        const grid = document.getElementById('dashboards-grid');
        if (!grid) return;
        
        const dashboards = this.dashboards;
        if (!dashboards.projects && !dashboards.websites) {
            grid.innerHTML = `
                <div class="col-span-full text-center py-12">
                    <div class="text-6xl mb-4">📊</div>
                    <h3 class="text-xl font-semibold mb-2">No dashboards</h3>
                    <p class="text-gray-400">No projects or websites found</p>
                </div>
            `;
            return;
        }
        
        let html = '';
        
        // Projects section
        if (dashboards.projects && dashboards.projects.details) {
            html += `
                <div class="col-span-full mb-6">
                    <h3 class="text-xl font-bold mb-4">Projects (${dashboards.projects.total})</h3>
                    <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                        ${dashboards.projects.details.map(project => {
                            const statusColors = {
                                'running': 'bg-green-500',
                                'stopped': 'bg-gray-500',
                                'error': 'bg-red-500'
                            };
                            const statusColor = statusColors[project.status] || 'bg-gray-500';
                            
                            return `
                                <div class="bg-gray-800 rounded-lg border border-gray-700 p-4 hover:border-gray-600 transition-colors">
                                    <div class="flex justify-between items-start mb-3">
                                        <div class="flex-1">
                                            <div class="flex items-center gap-2 mb-1">
                                                <span class="w-2 h-2 ${statusColor} rounded-full"></span>
                                                <h4 class="font-semibold text-white">${this.escapeHtml(project.name)}</h4>
                                            </div>
                                            ${project.brand ? `<div class="text-xs text-gray-400">${this.escapeHtml(project.brand)}</div>` : ''}
                                        </div>
                                    </div>
                                    
                                    ${project.description ? `<p class="text-sm text-gray-400 mb-3">${this.escapeHtml(project.description)}</p>` : ''}
                                    
                                    <div class="flex flex-wrap gap-2 text-xs">
                                        <span class="px-2 py-1 bg-gray-700 rounded">${project.type || 'Unknown'}</span>
                                        ${project.port ? `<span class="px-2 py-1 bg-blue-900 rounded">Port ${project.port}</span>` : ''}
                                    </div>
                                    
                                    ${project.url ? `
                                        <div class="mt-3 pt-3 border-t border-gray-700">
                                            <a href="${project.url}" target="_blank" 
                                               class="text-sm text-blue-400 hover:text-blue-300 flex items-center gap-1">
                                                🔗 Open Project
                                            </a>
                                        </div>
                                    ` : ''}
                                </div>
                            `;
                        }).join('')}
                    </div>
                </div>
            `;
        }
        
        // Websites section
        if (dashboards.websites && dashboards.websites.details) {
            html += `
                <div class="col-span-full">
                    <h3 class="text-xl font-bold mb-4">Websites (${dashboards.websites.total})</h3>
                    <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                        ${dashboards.websites.details.map(website => {
                            const statusColors = {
                                'online': 'bg-green-500',
                                'offline': 'bg-red-500'
                            };
                            const statusColor = statusColors[website.status] || 'bg-gray-500';
                            
                            return `
                                <div class="bg-gray-800 rounded-lg border border-gray-700 p-4 hover:border-gray-600 transition-colors">
                                    <div class="flex justify-between items-start mb-3">
                                        <div class="flex-1">
                                            <div class="flex items-center gap-2 mb-1">
                                                <span class="w-2 h-2 ${statusColor} rounded-full"></span>
                                                <h4 class="font-semibold text-white">${this.escapeHtml(website.name)}</h4>
                                            </div>
                                            ${website.brand ? `<div class="text-xs text-gray-400">${this.escapeHtml(website.brand)}</div>` : ''}
                                        </div>
                                    </div>
                                    
                                    <div class="flex flex-wrap gap-2 text-xs mb-3">
                                        <span class="px-2 py-1 bg-gray-700 rounded">${website.deployment_type || 'Unknown'}</span>
                                        ${website.build_status ? `<span class="px-2 py-1 bg-purple-900 rounded">${website.build_status}</span>` : ''}
                                    </div>
                                    
                                    ${website.live_url ? `
                                        <div class="pt-3 border-t border-gray-700">
                                            <a href="${website.live_url}" target="_blank" 
                                               class="text-sm text-blue-400 hover:text-blue-300 flex items-center gap-1">
                                                🌐 Visit Website
                                            </a>
                                        </div>
                                    ` : ''}
                                </div>
                            `;
                        }).join('')}
                    </div>
                </div>
            `;
        }
        
        grid.innerHTML = html;
    }
    
    // GITHUB
    async loadGithub(retryCount = 0, options = {}) {
        const hasGithubData = this.hasSectionData('github');
        const backgroundRefresh = (options.background === true || (options.preserveExisting !== false && hasGithubData)) && hasGithubData;
        if (!backgroundRefresh) {
            this.setSectionLoading('github-content', 'Loading GitHub activity...');
        }

        if (!this.beginSectionFetch('github')) {
            return;
        }

        try {
            const response = await this.fetchJsonWithTimeout('/api/github', {}, 12000);
            if (!response.ok) {
                if (!backgroundRefresh) {
                    this.github = {};
                    this.renderGithub();
                }
                return;
            }

            const data = await response.json();
            if (Array.isArray(data.items) && !data.repos && !data.issues && !data.prs) {
                const items = data.items;
                this.github = {
                    repos: items
                        .filter(item => item.type === 'Recent Repository')
                        .map(item => ({
                            name: item.repo || item.title || 'Repository',
                            description: item.description || '',
                            url: item.html_url || item.github_url || ''
                        })),
                    prs: items.filter(item => item.type === 'Pull Request' || item.type === 'Review Requested'),
                    issues: items.filter(item => item.type && item.type.includes('Issue')),
                    items
                };
            } else {
                this.github = data || {};
            }
            this.renderGithub();
            this.updateAllCounts();
            this.markSectionLoaded('github');
        } catch (error) {
            if (this.isTimeoutAbort(error) && retryCount < 2) {
                console.warn(`GitHub load timed out, retrying (${retryCount + 1}/2)...`);
                setTimeout(() => this.loadGithub(retryCount + 1, options), 1200);
                return;
            }
            console.error('Error loading GitHub:', error);
            if (!backgroundRefresh) {
                this.github = {};
                this.setSectionError('github-content', this.getLoadErrorMessage('Unable to load GitHub activity right now.', error));
            }
        } finally {
            this.endSectionFetch('github');
        }
    }
    
    renderGithub() {
        const container = document.getElementById('github-content');
        if (!container) return;

        const items = this.github?.items || [];
        const repos = (this.github?.repos && this.github.repos.length)
            ? this.github.repos
            : items.filter(i => i.type === 'Recent Repository');
        const prs = (this.github?.prs && this.github.prs.length)
            ? this.github.prs
            : items.filter(i => i.type === 'Pull Request' || i.type === 'Review Requested');
        const issues = (this.github?.issues && this.github.issues.length)
            ? this.github.issues
            : items.filter(i => i.type && i.type.includes('Issue'));

        if (repos.length === 0 && issues.length === 0 && prs.length === 0) {
            container.innerHTML = `
                <div class="bg-gray-800 rounded-xl p-8 border border-gray-700 text-center">
                    <div class="text-5xl mb-4">🐙</div>
                    <h3 class="text-xl font-semibold mb-2">No GitHub activity found</h3>
                    <p class="text-gray-400 mb-4">Check your GitHub connection in Providers or refresh this tab.</p>
                    <a href="#" onclick="showSection('settings'); return false;" 
                       class="inline-block px-6 py-3 bg-purple-600 hover:bg-purple-700 rounded-lg font-semibold">
                        Configure GitHub
                    </a>
                </div>
            `;
            return;
        }
        
        container.innerHTML = `
            <div class="grid grid-cols-1 md:grid-cols-3 gap-6 mb-6">
                <div class="bg-gray-800 rounded-xl p-6 border border-gray-700 text-center">
                    <div class="text-3xl font-bold text-blue-400">${repos.length}</div>
                    <div class="text-sm text-gray-400">Recent Repos</div>
                </div>
                <div class="bg-gray-800 rounded-xl p-6 border border-gray-700 text-center">
                    <div class="text-3xl font-bold text-green-400">${prs.length}</div>
                    <div class="text-sm text-gray-400">Pull Requests</div>
                </div>
                <div class="bg-gray-800 rounded-xl p-6 border border-gray-700 text-center">
                    <div class="text-3xl font-bold text-yellow-400">${issues.length}</div>
                    <div class="text-sm text-gray-400">Issues</div>
                </div>
            </div>
            
            <div class="space-y-6">
                ${prs.length > 0 ? `
                    <div>
                        <h3 class="text-xl font-bold mb-3 flex items-center gap-2">
                            <span class="text-green-400">🔀</span> Pull Requests
                        </h3>
                        <div class="space-y-2">
                            ${prs.map(pr => `
                                <div class="bg-gray-800 rounded-lg p-4 border border-gray-700 hover:border-green-500 transition-colors">
                                    <div class="flex items-start justify-between">
                                        <div class="flex-1">
                                            <a href="${pr.html_url || pr.github_url}" target="_blank" class="font-semibold text-blue-400 hover:underline">
                                                ${this.escapeHtml(pr.title)}
                                            </a>
                                            <div class="text-sm text-gray-500 mt-1">
                                                ${this.escapeHtml(pr.repository || pr.repo)} #${pr.number}
                                                ${pr.user ? ` • by ${this.escapeHtml(pr.user)}` : ''}
                                            </div>
                                        </div>
                                        <span class="px-2 py-1 text-xs rounded ${pr.state === 'open' ? 'bg-green-600' : 'bg-purple-600'}">
                                            ${pr.type === 'Review Requested' ? '👀 Review' : pr.state}
                                        </span>
                                    </div>
                                    ${pr.labels && pr.labels.length > 0 ? `
                                        <div class="flex gap-1 mt-2 flex-wrap">
                                            ${pr.labels.map(label => `<span class="px-2 py-0.5 text-xs bg-gray-700 rounded">${this.escapeHtml(label)}</span>`).join('')}
                                        </div>
                                    ` : ''}
                                </div>
                            `).join('')}
                        </div>
                    </div>
                ` : ''}
                
                ${issues.length > 0 ? `
                    <div>
                        <h3 class="text-xl font-bold mb-3 flex items-center gap-2">
                            <span class="text-yellow-400">🐛</span> Assigned Issues
                        </h3>
                        <div class="space-y-2">
                            ${issues.map(issue => `
                                <div class="bg-gray-800 rounded-lg p-4 border border-gray-700 hover:border-yellow-500 transition-colors">
                                    <div class="flex items-start justify-between">
                                        <div class="flex-1">
                                            <a href="${issue.html_url || issue.github_url}" target="_blank" class="font-semibold text-blue-400 hover:underline">
                                                ${this.escapeHtml(issue.title)}
                                            </a>
                                            <div class="text-sm text-gray-500 mt-1">
                                                ${this.escapeHtml(issue.repository || issue.repo)} #${issue.number}
                                            </div>
                                        </div>
                                        <span class="px-2 py-1 text-xs rounded ${issue.state === 'open' ? 'bg-yellow-600' : 'bg-gray-600'}">
                                            ${issue.state}
                                        </span>
                                    </div>
                                    ${issue.labels && issue.labels.length > 0 ? `
                                        <div class="flex gap-1 mt-2 flex-wrap">
                                            ${issue.labels.map(label => `<span class="px-2 py-0.5 text-xs bg-gray-700 rounded">${this.escapeHtml(label)}</span>`).join('')}
                                        </div>
                                    ` : ''}
                                </div>
                            `).join('')}
                        </div>
                    </div>
                ` : ''}
                
                ${repos.length > 0 ? `
                    <div>
                        <h3 class="text-xl font-bold mb-3 flex items-center gap-2">
                            <span class="text-blue-400">📁</span> Recent Repositories
                        </h3>
                        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                            ${repos.slice(0, 6).map(repo => `
                                <div class="bg-gray-800 rounded-lg p-4 border border-gray-700 hover:border-blue-500 transition-colors">
                                    <div class="flex items-start justify-between mb-2">
                                        <a href="${repo.html_url || repo.github_url || repo.url || '#'}" target="_blank" class="font-semibold text-blue-400 hover:underline">
                                            ${this.escapeHtml(repo.title || repo.repo || repo.name || 'Repository')}
                                        </a>
                                        ${repo.private ? '<span class="px-2 py-0.5 text-xs bg-gray-700 rounded">🔒 Private</span>' : ''}
                                    </div>
                                    ${repo.description ? `<p class="text-sm text-gray-400 mb-2">${this.escapeHtml(repo.description)}</p>` : ''}
                                    <div class="flex items-center gap-4 text-sm text-gray-500">
                                        ${repo.language ? `<span>💻 ${this.escapeHtml(repo.language)}</span>` : ''}
                                        ${repo.stars ? `<span>⭐ ${repo.stars}</span>` : ''}
                                        ${repo.forks ? `<span>🔀 ${repo.forks}</span>` : ''}
                                    </div>
                                </div>
                            `).join('')}
                        </div>
                    </div>
                ` : ''}
            </div>
        `;
    }
    
    // NEWS
    async loadNews(retryCount = 0, options = {}) {
        const hasExistingData = this.news.length > 0;
        const backgroundRefresh = (options.background === true || (options.preserveExisting !== false && hasExistingData)) && hasExistingData;
        if (!backgroundRefresh) {
            this.setSectionLoading('news-grid', 'Loading news...');
        }

        if (!this.beginSectionFetch('news')) {
            return;
        }

        try {
            const includeRead = this.showReadArticles ? 'true' : 'false';
            const response = await this.fetchJsonWithTimeout(`/api/news?include_read=${includeRead}`, {}, 12000);
            if (response.ok) {
                const data = await response.json();
                this.news = data.articles || [];
                this.renderNews();
                this.markSectionLoaded('news');
            } else {
                if (!backgroundRefresh) {
                    this.setSectionError('news-grid', 'Unable to load news right now.');
                }
            }
        } catch (error) {
            if (this.isTimeoutAbort(error) && retryCount < 2) {
                console.warn(`News load timed out, retrying (${retryCount + 1}/2)...`);
                setTimeout(() => this.loadNews(retryCount + 1, options), 1200);
                return;
            }
            console.error('Error loading news:', error);
            if (!backgroundRefresh) {
                this.setSectionError('news-grid', this.getLoadErrorMessage('Unable to load news right now.', error));
            }
        } finally {
            this.endSectionFetch('news');
        }
    }
    
    renderNews() {
        const grid = document.getElementById('news-grid');
        if (!grid) return;
        
        if (this.news.length === 0) {
            grid.innerHTML = `
                <div class="col-span-full text-center py-12">
                    <div class="text-6xl mb-4">📰</div>
                    <h3 class="text-xl font-semibold mb-2">No news</h3>
                    <p class="text-gray-400">Check back later</p>
                </div>
            `;
            return;
        }
        
        // Store articles for modal access
        this.newsArticles = {};
        this.news.forEach(article => {
            this.newsArticles[article.id] = article;
        });
        
        // Get unique categories for filtering
        const categories = [...new Set(this.news.map(item => item.category).filter(Boolean))];
        
        const categoryFilters = categories.length > 0 ? `
            <div class="mb-6 flex gap-2 flex-wrap">
                <button onclick="dataLoader.filterNews('all')" 
                        class="news-filter-btn px-4 py-2 bg-blue-600 rounded-full text-sm font-medium">All</button>
                ${categories.slice(0, 6).map(cat => 
                    `<button onclick="dataLoader.filterNews('${this.escapeHtml(cat)}')" 
                             class="news-filter-btn px-4 py-2 bg-gray-700 rounded-full text-sm hover:bg-gray-600">${this.escapeHtml(cat)}</button>`
                ).join('')}
                <button onclick="dataLoader.toggleShowReadArticles()" 
                        class="ml-auto px-4 py-2 bg-gray-700 rounded-full text-sm hover:bg-gray-600">
                    ${this.showReadArticles ? '📖 Hide Read' : '📚 Show All'}
                </button>
            </div>
        ` : `
            <div class="mb-6 flex justify-end">
                <button onclick="dataLoader.toggleShowReadArticles()" 
                        class="px-4 py-2 bg-gray-700 rounded-full text-sm hover:bg-gray-600">
                    ${this.showReadArticles ? '📖 Hide Read' : '📚 Show All'}
                </button>
            </div>
        `;
        
        // Generate Google News-style cards
        const html = this.news.map((article, index) => {
            // Process description to extract and render images
            let cleanDesc = article.description || article.snippet || '';
            
            // Skip if no content at all
            if (!cleanDesc && !article.title) {
                return '';
            }
            
            // First decode HTML entities
            const textarea = document.createElement('textarea');
            textarea.innerHTML = cleanDesc;
            cleanDesc = textarea.value;
            
            // Extract image URLs before removing tags
            const imgMatches = cleanDesc.match(/<img[^>]+src="([^">]+)"/g);
            let imgUrl = null;
            if (imgMatches) {
                const srcMatch = imgMatches[0].match(/src="([^"]+)"/);
                imgUrl = srcMatch ? srcMatch[1] : null;
            }
            
            // Remove img tags
            cleanDesc = cleanDesc.replace(/<img[^>]*>/gi, '');
            
            // Remove all other HTML tags
            cleanDesc = cleanDesc.replace(/<[^>]*>/gi, '');
            
            // Clean up extra whitespace
            cleanDesc = cleanDesc.trim().replace(/\s+/g, ' ');
            
            // Truncate description for preview
            const previewText = cleanDesc.length > 150 ? cleanDesc.substring(0, 150) + '...' : cleanDesc;
            
            const feedback = this.feedbackData[`news-${article.id}`] || null;
            const isRead = article.is_read || false;
            const displayImg = this.getNewsImageUrl(article, imgUrl);
            const fallbackImg = this.getNewsFallbackImage(article);
            
            return `
            <div class="news-card bg-gray-800 border border-gray-700 rounded-xl overflow-hidden hover:border-purple-500 transition-all cursor-pointer ${isRead ? 'opacity-70' : ''}"
                 data-category="${this.escapeHtml(article.category || '')}"
                 data-article-id="${article.id}"
                 onclick="dataLoader.openNewsArticle('${article.id}')">
                <div class="flex h-32">
                    <!-- Image Preview -->
                    <div class="w-40 flex-shrink-0 bg-gray-700 relative overflow-hidden">
                        <img src="${displayImg}" 
                             alt="" 
                             class="w-full h-full object-cover"
                                onerror="this.onerror=null;this.src='${fallbackImg}'">
                        ${isRead ? '<div class="absolute top-2 left-2 px-2 py-0.5 bg-gray-900 bg-opacity-80 rounded text-xs text-gray-400">✓ Read</div>' : ''}
                    </div>
                    
                    <!-- Content -->
                    <div class="flex-1 p-4 flex flex-col justify-between min-w-0">
                        <div>
                            <h3 class="font-semibold text-white text-sm line-clamp-2 mb-1">${this.escapeHtml(article.title)}</h3>
                            <p class="text-gray-400 text-xs line-clamp-2">${this.escapeHtml(previewText)}</p>
                        </div>
                        <div class="flex items-center gap-2 text-xs text-gray-500 mt-2">
                            <span class="text-purple-400 font-medium">${this.escapeHtml(article.source || 'News')}</span>
                            <span>•</span>
                            <span>${this.formatRelativeDate(article.published_at)}</span>
                            ${article.category ? `<span class="ml-auto px-2 py-0.5 bg-gray-700 rounded text-gray-400">${this.escapeHtml(article.category.split(',')[0])}</span>` : ''}
                        </div>
                    </div>
                </div>
            </div>
        `;
        }).join('');
        
        grid.innerHTML = categoryFilters + `
            <style>
                .line-clamp-2 {
                    display: -webkit-box;
                    -webkit-line-clamp: 2;
                    -webkit-box-orient: vertical;
                    overflow: hidden;
                }
            </style>
            <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">${html}</div>
        `;
    }

    getNewsImageUrl(article, extractedImageUrl = null) {
        const preferred = article?.image_url || extractedImageUrl;
        if (preferred && /^https?:\/\//i.test(preferred)) {
            return preferred;
        }
        return this.getNewsFallbackImage(article);
    }

    getNewsFallbackImage(article) {
        const categoryText = String(article?.category || '').toLowerCase();
        const titleText = String(article?.title || '').toLowerCase();
        const sourceUrl = String(article?.url || '').toLowerCase();
        const haystack = `${categoryText} ${titleText} ${sourceUrl}`;

        // Prefer source logo when available for a "relevant" visual instead of random art.
        try {
            const hostname = article?.url ? new URL(article.url).hostname.replace(/^www\./i, '') : '';
            if (hostname) {
                return `https://logo.clearbit.com/${hostname}`;
            }
        } catch (e) {
            // Ignore URL parse errors and use topical fallback below.
        }

        const topicalImages = {
            star_wars: 'https://images.unsplash.com/photo-1446776653964-20c1d3a81b06?w=800&h=450&fit=crop&auto=format',
            star_trek: 'https://images.unsplash.com/photo-1419242902214-272b3f66ee7a?w=800&h=450&fit=crop&auto=format',
            soccer: 'https://images.unsplash.com/photo-1431324155629-1a6deb1dec8d?w=800&h=450&fit=crop&auto=format',
            oregon_state: 'https://images.unsplash.com/photo-1541339907198-e08756dedf3f?w=800&h=450&fit=crop&auto=format',
            tech: 'https://images.unsplash.com/photo-1518770660439-4636190af475?w=800&h=450&fit=crop&auto=format',
            business: 'https://images.unsplash.com/photo-1460925895917-afdab827c52f?w=800&h=450&fit=crop&auto=format',
            general: 'https://images.unsplash.com/photo-1504711434969-e33886168f5c?w=800&h=450&fit=crop&auto=format'
        };

        if (haystack.includes('star wars') || haystack.includes('lucasfilm') || haystack.includes('jedi')) {
            return topicalImages.star_wars;
        }
        if (haystack.includes('star trek') || haystack.includes('enterprise') || haystack.includes('federation')) {
            return topicalImages.star_trek;
        }
        if (haystack.includes('timbers') || haystack.includes('soccer') || haystack.includes('mls')) {
            return topicalImages.soccer;
        }
        if (haystack.includes('oregon state') || haystack.includes('beavers') || haystack.includes('corvallis')) {
            return topicalImages.oregon_state;
        }
        if (haystack.includes('tech') || haystack.includes('ai') || haystack.includes('software') || haystack.includes('hacker')) {
            return topicalImages.tech;
        }
        if (haystack.includes('market') || haystack.includes('finance') || haystack.includes('business')) {
            return topicalImages.business;
        }
        return topicalImages.general;
    }
    
    formatRelativeDate(dateStr) {
        if (!dateStr) return '';
        try {
            const date = new Date(dateStr);
            const now = new Date();
            const diffMs = now - date;
            const diffMins = Math.floor(diffMs / 60000);
            const diffHours = Math.floor(diffMs / 3600000);
            const diffDays = Math.floor(diffMs / 86400000);
            
            if (diffMins < 60) return `${diffMins}m ago`;
            if (diffHours < 24) return `${diffHours}h ago`;
            if (diffDays < 7) return `${diffDays}d ago`;
            return date.toLocaleDateString();
        } catch {
            return dateStr;
        }
    }
    
    openNewsArticle(articleId) {
        const article = this.newsArticles[articleId];
        if (!article) return;
        
        // Process description
        let cleanDesc = article.description || article.snippet || '';
        const textarea = document.createElement('textarea');
        textarea.innerHTML = cleanDesc;
        cleanDesc = textarea.value;
        
        // Extract image URL
        const imgMatches = cleanDesc.match(/<img[^>]+src="([^">]+)"/g);
        let imgUrl = null;
        if (imgMatches) {
            const srcMatch = imgMatches[0].match(/src="([^"]+)"/);
            imgUrl = srcMatch ? srcMatch[1] : null;
        }

        const displayImg = this.getNewsImageUrl(article, imgUrl);
        const fallbackImg = this.getNewsFallbackImage(article);
        
        // Clean description
        cleanDesc = cleanDesc.replace(/<img[^>]*>/gi, '');
        cleanDesc = cleanDesc.replace(/<a\s+(?:[^>]*?\s+)?href="([^"]*)"[^>]*>(.*?)<\/a>/gi, '<a href="$1" target="_blank" class="text-blue-400 hover:underline">$2</a>');
        cleanDesc = cleanDesc.replace(/<(?!a\s|\/a>)[^>]*>/gi, '');
        cleanDesc = cleanDesc.trim();
        
        // Populate modal
        document.getElementById('news-modal-title').textContent = article.title;
        document.getElementById('news-modal-source').textContent = article.source || 'News';
        document.getElementById('news-modal-category').textContent = article.category || 'General';
        document.getElementById('news-modal-date').textContent = this.formatDate(article.published_at);
        document.getElementById('news-modal-content').innerHTML = cleanDesc || 'No content available. Click "Read Full Article" to view the complete story.';
        document.getElementById('news-modal-link').href = article.url;
        document.getElementById('news-modal-link').onclick = () => this.markArticleRead(articleId);
        
        // Show/hide image
        const imgContainer = document.getElementById('news-modal-image-container');
        const imgEl = document.getElementById('news-modal-image');
        imgEl.src = displayImg;
        imgEl.alt = article.title;
        imgEl.onerror = () => {
            imgEl.onerror = null;
            imgEl.src = fallbackImg;
        };
        imgContainer.classList.remove('hidden');
        
        // Add feedback buttons
        const feedback = this.feedbackData[`news-${articleId}`] || null;
        document.getElementById('news-modal-feedback').innerHTML = `
            <button onclick="dataLoader.giveFeedback('news', '${articleId}', 'up'); event.stopPropagation();" 
                    class="feedback-btn px-3 py-2 rounded-lg text-sm ${feedback === 'up' ? 'bg-green-600' : 'bg-gray-700 hover:bg-green-600'}" 
                    title="Interesting">👍</button>
            <button onclick="dataLoader.giveFeedback('news', '${articleId}', 'neutral'); event.stopPropagation();" 
                    class="feedback-btn px-3 py-2 rounded-lg text-sm ${feedback === 'neutral' ? 'bg-blue-600' : 'bg-gray-700 hover:bg-blue-600'}" 
                    title="Neutral">👌</button>
            <button onclick="dataLoader.giveFeedback('news', '${articleId}', 'down'); event.stopPropagation();" 
                    class="feedback-btn px-3 py-2 rounded-lg text-sm ${feedback === 'down' ? 'bg-red-600' : 'bg-gray-700 hover:bg-red-600'}" 
                    title="Not interested">👎</button>
        `;
        
        // Show modal
        document.getElementById('news-article-modal').classList.remove('hidden');
        document.body.style.overflow = 'hidden';
    }

    toggleNewsAccordion(articleId) {
        // Legacy function - now opens modal instead
        this.openNewsArticle(articleId);
    }
    
    async markArticleRead(articleId) {
        try {
            const response = await fetch(`/api/news/${articleId}/read`, {
                method: 'POST'
            });
            
            if (response.ok) {
                // Update UI to show as read
                const item = document.querySelector(`[data-article-id="${articleId}"]`);
                if (item) {
                    item.classList.remove('news-unread');
                    item.classList.add('news-read');
                    
                    // Update the status badge
                    const header = item.querySelector('.news-accordion-header');
                    const statusBadge = header.querySelector('.text-green-400');
                    if (statusBadge) {
                        statusBadge.className = 'text-xs text-gray-500';
                        statusBadge.textContent = '✓ Read';
                    }
                }
                
                // Update the article in our data
                const article = this.news.find(a => a.id === articleId);
                if (article) {
                    article.is_read = true;
                }
                
                // Don't auto-hide - let the user continue reading and close manually
                // Articles will be filtered on next news load/refresh
                this.updateAllCounts();
            }
        } catch (error) {
            console.error('Error marking article as read:', error);
        }
    }
    
    toggleShowReadArticles() {
        this.showReadArticles = !this.showReadArticles;
        
        // Reload news with updated filter
        this.loadNews();
    }
    
    filterNews(category) {
        const items = document.querySelectorAll('.news-item');
        const buttons = document.querySelectorAll('.news-filter-btn');
        
        buttons.forEach(btn => {
            btn.classList.remove('bg-blue-600');
            btn.classList.add('bg-gray-700');
        });
        
        event.target.classList.remove('bg-gray-700');
        event.target.classList.add('bg-blue-600');
        
        items.forEach(item => {
            if (category === 'all' || item.dataset.category === category) {
                item.style.display = 'block';
            } else {
                item.style.display = 'none';
            }
        });
    }
    
    async showNewsSourcesModal() {
        try {
            // Fetch current news sources
            const response = await fetch('/api/news-sources');
            const data = await response.json();
            const sources = data.sources || [];
            
            const modal = document.createElement('div');
            modal.id = 'news-sources-modal';
            modal.className = 'fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4 overflow-y-auto';
            modal.onclick = (e) => {
                if (e.target === modal) modal.remove();
            };
            
            modal.innerHTML = `
                <div class="bg-gray-800 rounded-xl p-6 max-w-4xl w-full my-8">
                    <div class="flex items-center justify-between mb-4">
                        <h3 class="text-2xl font-bold">Manage News Sources</h3>
                        <button onclick="document.getElementById('news-sources-modal').remove()" 
                                class="text-gray-400 hover:text-white text-2xl leading-none">
                            ×
                        </button>
                    </div>
                    
                    <div class="max-h-[calc(90vh-12rem)] overflow-y-auto pr-2 space-y-6">
                        <div>
                            <h4 class="text-lg font-semibold mb-3">Add Custom Source</h4>
                            <form id="add-source-form" class="grid grid-cols-3 gap-3">
                                <input type="text" id="source-name" placeholder="Source Name" 
                                       class="bg-gray-700 border border-gray-600 rounded px-3 py-2" required>
                                <input type="url" id="source-url" placeholder="RSS Feed URL" 
                                       class="bg-gray-700 border border-gray-600 rounded px-3 py-2" required>
                                <button type="submit" 
                                        class="bg-green-600 hover:bg-green-700 px-4 py-2 rounded">
                                    ➕ Add Source
                                </button>
                            </form>
                        </div>
                        
                        <div>
                            <h4 class="text-lg font-semibold mb-3">Active Sources (${sources.filter(s => s.is_active).length})</h4>
                            <div class="space-y-2">
                                ${sources.map(source => `
                                    <div class="bg-gray-700 rounded-lg p-3 flex items-center justify-between">
                                        <div class="flex-1">
                                            <div class="font-semibold">${this.escapeHtml(source.name)}</div>
                                            <div class="text-xs text-gray-400">${source.category || 'general'} ${source.is_custom ? '(Custom)' : ''}</div>
                                        </div>
                                        <div class="flex items-center gap-2">
                                            <label class="flex items-center gap-1">
                                                <input type="checkbox" 
                                                       ${source.is_active ? 'checked' : ''}
                                                       onchange="dataLoader.toggleNewsSource(${source.id}, this.checked)"
                                                       class="w-4 h-4 rounded">
                                                <span class="text-xs">Active</span>
                                            </label>
                                            ${source.is_custom ? `
                                                <button onclick="dataLoader.deleteNewsSource(${source.id})" 
                                                        class="bg-red-600 hover:bg-red-700 px-2 py-1 rounded text-xs">
                                                    🗑️
                                                </button>
                                            ` : ''}
                                        </div>
                                    </div>
                                `).join('')}
                            </div>
                        </div>
                    </div>
                    
                    <div class="mt-6 pt-4 border-t border-gray-700">
                        <button onclick="document.getElementById('news-sources-modal').remove(); dataLoader.loadNews();" 
                                class="w-full bg-blue-600 hover:bg-blue-700 px-4 py-2 rounded">
                            Save & Reload News
                        </button>
                    </div>
                </div>
            `;
            
            document.body.appendChild(modal);
            
            // Handle add source form
            document.getElementById('add-source-form').onsubmit = async (e) => {
                e.preventDefault();
                const name = document.getElementById('source-name').value;
                const url = document.getElementById('source-url').value;
                
                await this.addNewsSource(name, url);
                modal.remove();
                this.showNewsSourcesModal();
            };
        } catch (error) {
            console.error('Error showing news sources modal:', error);
            this.showNotification('⚠️ Error loading news sources');
        }
    }
    
    async addNewsSource(name, url) {
        try {
            const response = await fetch('/api/news-sources', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name, url, category: 'custom' })
            });
            
            if (response.ok) {
                this.showNotification(`✅ Added news source: ${name}`);
            } else {
                this.showNotification('⚠️ Error adding news source');
            }
        } catch (error) {
            console.error('Error adding news source:', error);
            this.showNotification('⚠️ Error adding news source');
        }
    }
    
    async toggleNewsSource(sourceId, isActive) {
        try {
            const response = await fetch(`/api/news-sources/${sourceId}/toggle`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ is_active: isActive })
            });
            
            if (response.ok) {
                this.showNotification(isActive ? '✅ Source activated' : '⏸️ Source deactivated');
            }
        } catch (error) {
            console.error('Error toggling news source:', error);
        }
    }
    
    async deleteNewsSource(sourceId) {
        if (!confirm('Delete this news source?')) return;
        
        try {
            const response = await fetch(`/api/news-sources/${sourceId}`, {
                method: 'DELETE'
            });
            
            if (response.ok) {
                this.showNotification('🗑️ News source deleted');
                document.getElementById('news-sources-modal').remove();
                this.showNewsSourcesModal();
            }
        } catch (error) {
            console.error('Error deleting news source:', error);
            this.showNotification('⚠️ Error deleting news source');
        }
    }
    
    // WEATHER
    async loadWeather(retryCount = 0, options = {}) {
        const hasExistingData = this.hasSectionData('weather');
        const backgroundRefresh = (options.background === true || (options.preserveExisting !== false && hasExistingData)) && hasExistingData;
        if (!backgroundRefresh) {
            this.setSectionLoading('weather-content', 'Loading weather...');
        }

        if (!this.beginSectionFetch('weather')) {
            return;
        }

        try {
            const response = await this.fetchJsonWithTimeout('/api/weather', {}, 12000);
            if (response.ok) {
                const data = await response.json();
                this.weather = data;
                this.renderWeather();
                this.markSectionLoaded('weather');
            } else {
                if (!backgroundRefresh) {
                    this.setSectionError('weather-content', 'Unable to load weather right now.');
                }
            }
        } catch (error) {
            if (this.isTimeoutAbort(error) && retryCount < 2) {
                console.warn(`Weather load timed out, retrying (${retryCount + 1}/2)...`);
                setTimeout(() => this.loadWeather(retryCount + 1, options), 1200);
                return;
            }
            console.error('Error loading weather:', error);
            if (!backgroundRefresh) {
                this.setSectionError('weather-content', this.getLoadErrorMessage('Unable to load weather right now.', error));
            }
        } finally {
            this.endSectionFetch('weather');
        }
    }
    
    renderWeather() {
        const container = document.getElementById('weather-content');
        if (!container) return;
        
        // Weather API returns flat structure: temperature, description, icon, location, forecast[]
        if (!this.weather || !this.weather.temperature) {
            container.innerHTML = '<p class="text-gray-400 text-center py-12">Weather data unavailable</p>';
            return;
        }
        
        const iconMap = {
            '01d': '☀️', '01n': '🌙',
            '02d': '⛅', '02n': '☁️',
            '03d': '☁️', '03n': '☁️',
            '04d': '☁️', '04n': '☁️',
            '09d': '🌧️', '09n': '🌧️',
            '10d': '🌦️', '10n': '🌧️',
            '11d': '⛈️', '11n': '⛈️',
            '13d': '🌨️', '13n': '🌨️',
            '50d': '🌫️', '50n': '🌫️'
        };
        
        const currentIcon = iconMap[this.weather.icon] || '🌤️';
        
        container.innerHTML = `
            <div class="bg-gray-800 rounded-xl p-8 border border-gray-700 text-center mb-6">
                <div class="text-6xl mb-4">${currentIcon}</div>
                <div class="text-5xl font-bold mb-2">${this.weather.temperature}</div>
                <div class="text-xl text-gray-400 mb-2">${this.weather.description || 'Clear'}</div>
                ${this.weather.location ? `<div class="text-sm text-gray-500">📍 ${this.weather.location}</div>` : ''}
                <div class="grid grid-cols-2 gap-4 mt-6 text-sm">
                    ${this.weather.feels_like ? `<div><span class="text-gray-400">Feels Like:</span> ${this.weather.feels_like}</div>` : ''}
                    ${this.weather.humidity ? `<div><span class="text-gray-400">Humidity:</span> ${this.weather.humidity}%</div>` : ''}
                    ${this.weather.wind_speed ? `<div><span class="text-gray-400">Wind:</span> ${this.weather.wind_speed}</div>` : ''}
                    ${this.weather.pressure ? `<div><span class="text-gray-400">Pressure:</span> ${this.weather.pressure}</div>` : ''}
                </div>
            </div>
            
            ${this.weather.forecast && this.weather.forecast.length > 0 ? `
                <div class="grid grid-cols-2 md:grid-cols-5 gap-4">
                    ${this.weather.forecast.map(day => {
                        const dayIcon = iconMap[day.icon] || '☀️';
                        return `
                        <div class="bg-gray-800 rounded-lg p-4 border border-gray-700 text-center">
                            <div class="text-sm text-gray-400 mb-2">${day.day || day.date}</div>
                            <div class="text-3xl mb-2">${dayIcon}</div>
                            <div class="font-semibold text-white mb-1">${day.high}° / ${day.low}°</div>
                            <div class="text-xs text-gray-400">${day.condition}</div>
                            ${day.precipitation_chance ? `<div class="text-xs text-blue-400 mt-1">💧 ${day.precipitation_chance}%</div>` : ''}
                        </div>
                    `;
                    }).join('')}
                </div>
            ` : ''}
        `;
    }
    
    async loadNotes() {
        this.setSectionLoading('notes-grid', 'Loading notes...');
        const statsContainer = document.getElementById('notes-stats');
        if (statsContainer) {
            statsContainer.innerHTML = `
                <div class="col-span-4 text-center py-4 text-gray-400 animate-pulse">Loading note stats...</div>
            `;
        }
        try {
            const response = await this.fetchJsonWithTimeout('/api/notes', {}, 22000);
            if (response.ok) {
                const data = await response.json();
                this.notes = data.notes || [];
                this.notesStats = {
                    obsidian_count: data.obsidian_count || 0,
                    gdrive_count: data.gdrive_count || 0,
                    total_todos_found: data.total_todos_found || 0,
                    tasks_created: data.tasks_created || 0
                };
                this.renderNotes();
            } else {
                this.setSectionError('notes-grid', 'Unable to load notes right now.');
            }
        } catch (error) {
            console.error('Error loading notes:', error);
            this.setSectionError('notes-grid', this.getLoadErrorMessage('Unable to load notes right now.', error));
        }
    }
    
    refreshNotes() {
        this.loadNotes();
    }
    
    // Helper function to call summarizeItem from button with data attributes
    async summarizeItemFromButton(button) {
        try {
            const itemType = button.getAttribute('data-item-type');
            const itemId = button.getAttribute('data-item-id');
            const itemDataStr = button.getAttribute('data-item-data');
            const itemData = JSON.parse(itemDataStr);
            
            await this.summarizeItem(itemType, itemId, itemData);
        } catch (error) {
            console.error('Error parsing item data:', error);
            this.showNotification('❌ Error: Invalid item data', 'error');
        }
    }
    
    async summarizeItem(itemType, itemId, itemData) {
        try {
            // Show loading indicator - add spinning wheel next to button
            const button = event.target.closest('button');
            const originalText = button.innerHTML;
            button.disabled = true;
            
            // Create and add spinner
            const spinner = document.createElement('span');
            spinner.className = 'ai-loading-spinner';
            spinner.innerHTML = '&nbsp;<svg class="inline-block animate-spin h-4 w-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg>';
            button.appendChild(spinner);
            
            // Prepare content based on item type
            let content = '';
            let title = '';
            let metadata = {};
            
            if (itemType === 'note') {
                content = itemData.preview || '';
                title = itemData.title || 'Untitled Note';
                metadata = {
                    url: itemData.url || itemData.path,
                    source: itemData.source
                };
            } else if (itemType === 'email') {
                content = itemData.body || itemData.snippet || '';
                title = itemData.subject || 'No Subject';
                metadata = {
                    id: itemData.id,
                    from: itemData.from
                };
            } else if (itemType === 'calendar') {
                content = itemData.description || '';
                title = itemData.summary || itemData.title || 'Untitled Event';
                metadata = {
                    id: itemData.id,
                    start: itemData.start,
                    end: itemData.end
                };
            }
            
            // Call API
            const response = await fetch('/api/ai/summarize/item', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    item_type: itemType,
                    item_id: itemId,
                    content: content,
                    title: title,
                    metadata: metadata
                })
            });
            
            if (response.ok) {
                const data = await response.json();
                
                // Update the item with the summary
                if (itemType === 'note') {
                    const note = this.notes.find(n => (n.doc_id === itemId || n.relative_path === itemId));
                    if (note) {
                        note.summary = data.summary;
                    }
                    this.renderNotes();
                } else if (itemType === 'email') {
                    const email = this.emails.find(e => e.id === itemId);
                    if (email) {
                        email.summary = data.summary;
                    }
                    this.renderEmails();
                } else if (itemType === 'calendar') {
                    const event = this.calendar.find(e => e.id === itemId);
                    if (event) {
                        event.summary_ai = data.summary;
                    }
                    this.renderCalendar();
                }
                
                // Show success message
                const message = `✅ Summary complete! ${data.tasks_created > 0 ? `Created ${data.tasks_created} task${data.tasks_created > 1 ? 's' : ''}.` : 'No tasks found.'}`;
                this.showNotification(message, 'success');
                
                // Reload tasks if any were created
                if (data.tasks_created > 0) {
                    this.loadTodos();
                }
            } else {
                const error = await response.json();
                this.showNotification(`❌ Error: ${error.detail || 'Failed to summarize'}`, 'error');
            }
            
            // Remove spinner and restore button
            const loadingSpinner = button.querySelector('.ai-loading-spinner');
            if (loadingSpinner) loadingSpinner.remove();
            button.disabled = false;
            
        } catch (error) {
            console.error('Error summarizing item:', error);
            this.showNotification('❌ Error summarizing item', 'error');
            
            // Remove spinner and restore button
            const errorButton = event.target.closest('button');
            const errorSpinner = errorButton.querySelector('.ai-loading-spinner');
            if (errorSpinner) errorSpinner.remove();
            errorButton.disabled = false;
        }
    }
    
    renderNotes() {
        const container = document.getElementById('notes-grid');
        const statsContainer = document.getElementById('notes-stats');
        
        if (!container) return;
        
        // Render stats
        if (statsContainer && this.notesStats) {
            statsContainer.innerHTML = `
                <div class="bg-gray-800 rounded-lg p-4">
                    <div class="text-gray-400 text-sm">Obsidian Notes</div>
                    <div class="text-2xl font-bold text-white">${this.notesStats.obsidian_count}</div>
                </div>
                <div class="bg-gray-800 rounded-lg p-4">
                    <div class="text-gray-400 text-sm">Google Drive Notes</div>
                    <div class="text-2xl font-bold text-white">${this.notesStats.gdrive_count}</div>
                </div>
                <div class="bg-gray-800 rounded-lg p-4">
                    <div class="text-gray-400 text-sm">TODOs Found</div>
                    <div class="text-2xl font-bold text-purple-400">${this.notesStats.total_todos_found}</div>
                </div>
                <div class="bg-gray-800 rounded-lg p-4">
                    <div class="text-gray-400 text-sm">Tasks Created</div>
                    <div class="text-2xl font-bold text-green-400">${this.notesStats.tasks_created}</div>
                </div>
            `;
        }
        
        // Render notes grid
        if (!this.notes || this.notes.length === 0) {
            container.innerHTML = '<p class="text-gray-400 text-center py-12 col-span-3">No recent notes found</p>';
            return;
        }
        
        container.innerHTML = this.notes.map(note => {
            const isObsidian = note.source === 'obsidian';
            const isGoogleDrive = note.source === 'google_drive' || note.source === 'gdrive';
            const sourceIcon = isObsidian ? '📓' : '📄';
            const sourceLabel = isObsidian ? 'Obsidian' : 'Google Drive';
            const sourceColor = isObsidian ? 'purple' : 'blue';
            
            // Resolve note link for all connected sources
            let noteLink = '';
            if (isGoogleDrive && note.url) {
                noteLink = note.url;
            } else if (isObsidian) {
                if (note.relative_path) {
                    noteLink = `obsidian://open?file=${encodeURIComponent(note.relative_path)}`;
                } else if (note.path) {
                    noteLink = `obsidian://open?path=${encodeURIComponent(note.path)}`;
                }
            }

            const hasLink = Boolean(noteLink);
            
            return `
                <div class="bg-gray-800 rounded-lg p-5 hover:bg-gray-750 transition-all duration-200">
                    <div class="flex items-start justify-between mb-3">
                        <div class="flex items-center gap-2">
                            <span class="text-2xl">${sourceIcon}</span>
                            <span class="px-2 py-1 rounded text-xs font-medium bg-${sourceColor}-500/20 text-${sourceColor}-400">
                                ${sourceLabel}
                            </span>
                            ${note.todo_count ? `<span class="px-2 py-1 rounded text-xs font-medium bg-yellow-500/20 text-yellow-400">${note.todo_count} TODOs</span>` : ''}
                        </div>
                        <span class="text-xs text-gray-500">${note.modified || 'Recently updated'}</span>
                    </div>
                    
                    <h3 class="text-lg font-semibold text-white mb-2 line-clamp-2">
                        ${note.title || 'Untitled Note'}
                    </h3>
                    
                    ${note.tags && note.tags.length > 0 ? `
                        <div class="flex flex-wrap gap-1 mb-2">
                            ${note.tags.slice(0, 3).map(tag => `
                                <span class="px-2 py-0.5 rounded text-xs bg-gray-700 text-gray-300">#${tag}</span>
                            `).join('')}
                            ${note.tags.length > 3 ? `<span class="text-xs text-gray-500">+${note.tags.length - 3} more</span>` : ''}
                        </div>
                    ` : ''}
                    
                    <p class="text-gray-400 text-sm mb-3 line-clamp-3">
                        ${note.preview || 'No preview available'}
                    </p>
                    
                    ${note.word_count ? `<div class="text-xs text-gray-500 mb-3">${note.word_count} words</div>` : ''}
                    
                    ${note.summary ? `
                        <div class="mb-3 p-3 bg-gray-700 rounded text-sm">
                            <div class="text-xs text-gray-400 mb-1">AI Summary:</div>
                            <div class="text-white">${this.escapeHtml(note.summary)}</div>
                        </div>
                    ` : ''}
                    
                    <div class="flex gap-2">
                        ${hasLink ? `
                            <a href="${this.escapeHtml(noteLink)}" target="_blank" rel="noopener noreferrer"
                               class="flex-1 px-3 py-2 bg-${sourceColor}-600 hover:bg-${sourceColor}-700 rounded text-sm font-medium text-center transition-all duration-200">
                                Open Note
                            </a>
                        ` : `
                            <button disabled
                               class="flex-1 px-3 py-2 bg-gray-700 text-gray-400 rounded text-sm font-medium text-center cursor-not-allowed">
                                Link Unavailable
                            </button>
                        `}
                        <button data-item-type="note" 
                                data-item-id="${note.doc_id || note.relative_path}" 
                                data-item-data="${this.escapeHtml(JSON.stringify(note))}"
                                onclick="dataLoader.summarizeItemFromButton(this)"
                                class="px-3 py-2 bg-purple-600 hover:bg-purple-700 rounded text-sm font-medium transition-all duration-200 flex items-center gap-1"
                                title="Summarize and scan for tasks">
                            🤖 AI
                        </button>
                        ${note.todo_count ? `
                            <button onclick="dataLoader.loadTodos(); showSection('todos');" 
                                    class="px-3 py-2 bg-yellow-600 hover:bg-yellow-700 rounded text-sm font-medium transition-all duration-200">
                                View Tasks
                            </button>
                        ` : ''}
                    </div>
                </div>
            `;
        }).join('');
    }
    
    // UPDATE COUNTS
    updateAllCounts() {
        // Todos - count active (pending or in_progress)
        const todosCount = this.todos.filter(t => t.status !== 'completed' && t.status !== 'deleted').length;
        this.updateBadge('todos-count', todosCount);
        this.updateStat('stat-tasks', todosCount);
        this.updateStat('tasks-count', todosCount);

        // Calendar - upcoming events only
        const now = new Date();
        const upcomingCalendarCount = this.calendar.filter(event => {
            const startDate = event.start && event.start.dateTime ? event.start.dateTime : event.start;
            if (!startDate) return false;
            const eventTime = new Date(startDate);
            return !isNaN(eventTime.getTime()) && eventTime >= now;
        }).length;
        this.updateStat('calendar-count', upcomingCalendarCount);
        
        // Emails - only count unread
        const unreadEmailsCount = this.emails.filter(e => {
            if (typeof e.unread === 'boolean') return e.unread;
            if (typeof e.read === 'boolean') return !e.read;
            if (typeof e.is_read === 'boolean') return !e.is_read;
            return true;
        }).length;
        this.updateBadge('emails-count', unreadEmailsCount);
        this.updateStat('stat-emails', unreadEmailsCount);
        this.updateStat('email-count', unreadEmailsCount);

        // GitHub - open issues count for top overview tile
        const githubIssuesCount = Array.isArray(this.github?.issues)
            ? this.github.issues.length
            : (Array.isArray(this.github?.items)
                ? this.github.items.filter(item => item.type && item.type.includes('Issue')).length
                : 0);
        this.updateStat('github-count', githubIssuesCount);
        
        // News - only count unread
        const unreadNewsCount = this.news.filter(n => !n.is_read).length;
        this.updateBadge('news-count', unreadNewsCount);
        this.updateStat('stat-news', unreadNewsCount);
    }
    
    updateBadge(id, count) {
        const badge = document.getElementById(id);
        if (badge) {
            badge.textContent = count;
            badge.style.display = count > 0 ? 'block' : 'none';
        }
    }
    
    updateStat(id, count) {
        const stat = document.getElementById(id);
        if (stat) {
            stat.textContent = count;
        }
    }
    
    // HELPER METHODS
    getPriorityColor(priority) {
        const colors = { high: 'red', medium: 'yellow', low: 'green' };
        return colors[priority?.toLowerCase()] || 'gray';
    }
    
    formatDate(dateString) {
        if (!dateString) return '';
        const date = new Date(dateString);
        const today = new Date();
        const tomorrow = new Date(today);
        tomorrow.setDate(tomorrow.getDate() + 1);
        
        if (date.toDateString() === today.toDateString()) return 'Today';
        if (date.toDateString() === tomorrow.toDateString()) return 'Tomorrow';
        
        return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
    }
    
    getTimeAgo(dateString) {
        if (!dateString) return '';
        const date = new Date(dateString);
        const now = new Date();
        const diffMs = now - date;
        const diffMins = Math.floor(diffMs / 60000);
        const diffHours = Math.floor(diffMs / 3600000);
        const diffDays = Math.floor(diffMs / 86400000);
        
        if (diffMins < 1) return 'Just now';
        if (diffMins < 60) return `${diffMins}m ago`;
        if (diffHours < 24) return `${diffHours}h ago`;
        if (diffDays === 1) return 'Yesterday';
        if (diffDays < 7) return `${diffDays}d ago`;
        
        return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
    }
    
    formatTime(dateString) {
        if (!dateString) return '';
        return new Date(dateString).toLocaleTimeString('en-US', { 
            hour: 'numeric', 
            minute: '2-digit',
            hour12: true 
        });
    }
    
    formatEventTime(event) {
        if (event.is_all_day) return 'All day';
        if (event.time) return event.time;
        const start = event.start && event.start.dateTime ? event.start.dateTime : event.start;
        return this.formatTime(start);
    }
    
    groupEventsByDay(events) {
        const grouped = {};
        events.forEach(event => {
            const start = event.start && event.start.dateTime ? event.start.dateTime : event.start;
            const day = this.formatDate(start);
            if (!grouped[day]) grouped[day] = [];
            grouped[day].push(event);
        });
        return grouped;
    }
    
    escapeHtml(text) {
        if (!text) return '';
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
    
    // CALENDAR HELPERS
    formatCurrentTime() {
        const now = new Date();
        return now.toLocaleTimeString('en-US', { 
            hour: 'numeric', 
            minute: '2-digit',
            hour12: true 
        });
    }
    
    startClockUpdate() {
        setInterval(() => {
            const clockEl = document.getElementById('current-time');
            if (clockEl) {
                clockEl.textContent = this.formatCurrentTime();
            }
        }, 1000);
    }
    
    getUpcomingEvent() {
        const now = new Date();
        const upcomingEvents = this.calendar
            .filter(event => {
                const startDate = event.start && event.start.dateTime ? new Date(event.start.dateTime) : new Date(event.start);
                return startDate > now;
            })
            .sort((a, b) => {
                const aStart = a.start && a.start.dateTime ? new Date(a.start.dateTime) : new Date(a.start);
                const bStart = b.start && b.start.dateTime ? new Date(b.start.dateTime) : new Date(b.start);
                return aStart - bStart;
            });
        
        return upcomingEvents[0] || null;
    }
    
    getTimeUntil(event) {
        const now = new Date();
        const startDate = event.start && event.start.dateTime ? new Date(event.start.dateTime) : new Date(event.start);
        const diff = startDate - now;
        
        const minutes = Math.floor(diff / 60000);
        const hours = Math.floor(minutes / 60);
        const days = Math.floor(hours / 24);
        
        if (days > 0) return `in ${days} day${days > 1 ? 's' : ''}`;
        if (hours > 0) return `in ${hours} hour${hours > 1 ? 's' : ''}`;
        if (minutes > 0) return `in ${minutes} minute${minutes > 1 ? 's' : ''}`;
        return 'starting now';
    }
    
    extractMeetingLink(event) {
        // Check description for Zoom/Google Meet/Teams links
        const text = (event.description || '') + ' ' + (event.location || '');
        
        // Zoom
        const zoomMatch = text.match(/https?:\/\/[\w-]*\.?zoom\.us\/[^\s]*/i);
        if (zoomMatch) return zoomMatch[0];
        
        // Google Meet
        const meetMatch = text.match(/https?:\/\/meet\.google\.com\/[^\s]*/i);
        if (meetMatch) return meetMatch[0];
        
        // Microsoft Teams
        const teamsMatch = text.match(/https?:\/\/teams\.microsoft\.com\/[^\s]*/i);
        if (teamsMatch) return teamsMatch[0];
        
        // Check if location is a URL
        if (event.location && event.location.startsWith('http')) {
            return event.location;
        }
        
        return null;
    }
    
    startUpcomingEventMonitor() {
        // Clear existing timer
        if (this.upcomingEventTimer) {
            clearInterval(this.upcomingEventTimer);
        }
        
        // Check every minute for upcoming events
        this.upcomingEventTimer = setInterval(() => {
            this.checkUpcomingEvents();
        }, 60000); // Check every minute
        
        // Check immediately
        this.checkUpcomingEvents();
    }
    
    checkUpcomingEvents() {
        const now = new Date();
        const alertThresholds = [15, 10, 5, 2]; // Alert at 15, 10, 5, and 2 minutes before
        
        this.calendar.forEach(event => {
            const startDate = event.start && event.start.dateTime ? new Date(event.start.dateTime) : new Date(event.start);
            const minutesUntil = Math.floor((startDate - now) / 60000);
            
            // Check if we should alert for this event
            if (alertThresholds.includes(minutesUntil) && !this.alertedEvents.has(`${event.event_id}-${minutesUntil}`)) {
                this.alertedEvents.add(`${event.event_id}-${minutesUntil}`);
                this.showEventAlert(event, minutesUntil);
            }
        });
    }
    
    showEventAlert(event, minutesUntil) {
        const meetingLink = this.extractMeetingLink(event);
        const eventTitle = event.summary || event.title;
        const location = event.location || '';
        
        // Create visual alert
        const alertDiv = document.createElement('div');
        alertDiv.id = `alert-${event.event_id}`;
        alertDiv.className = 'fixed top-4 right-4 bg-gradient-to-r from-blue-600 to-purple-600 text-white rounded-xl shadow-2xl p-6 max-w-md z-50 bounce-thrice';
        alertDiv.innerHTML = `
            <div class="flex justify-between items-start mb-3">
                <h3 class="text-xl font-bold">🔔 Event Starting Soon!</h3>
                <button onclick="dataLoader.dismissAlert('${event.event_id}')" class="text-white hover:text-gray-200">✕</button>
            </div>
            <p class="font-semibold text-lg mb-2">${this.escapeHtml(eventTitle)}</p>
            <p class="text-sm mb-2">⏰ Starting in ${minutesUntil} minute${minutesUntil > 1 ? 's' : ''}</p>
            ${location ? `<p class="text-sm mb-3">📍 ${this.escapeHtml(location)}</p>` : ''}
            <div class="flex gap-2 mb-3">
                ${meetingLink ? `
                    <a href="${meetingLink}" target="_blank" 
                       class="flex-1 bg-green-500 hover:bg-green-600 px-4 py-2 rounded-lg text-center font-semibold">
                        🎥 Join Now
                    </a>
                ` : ''}
                <button onclick="dataLoader.dismissAlert('${event.event_id}')" 
                        class="flex-1 bg-white bg-opacity-20 hover:bg-opacity-30 px-4 py-2 rounded-lg font-semibold">
                    Dismiss
                </button>
            </div>
            <div class="border-t border-white border-opacity-20 pt-3 mt-3">
                <button onclick="dataLoader.startVoiceResponse('${event.event_id}')" 
                        class="w-full bg-white bg-opacity-20 hover:bg-opacity-30 px-4 py-2 rounded-lg flex items-center justify-center gap-2">
                    🎤 Voice Response
                </button>
            </div>
        `;
        
        document.body.appendChild(alertDiv);
        
        // Speak the alert using AI voice
        this.speakEventAlert(eventTitle, minutesUntil, location);
        
        // Auto-dismiss after 30 seconds
        setTimeout(() => {
            this.dismissAlert(event.event_id);
        }, 30000);
    }
    
    speakEventAlert(eventTitle, minutesUntil, location) {
        if (!this.speechSynthesis) return;
        if (this.globalMuted) return;
        
        const message = `Hello! You have an event starting in ${minutesUntil} minute${minutesUntil > 1 ? 's' : ''}. ${eventTitle}. ${location ? `The location is ${location}.` : ''} Would you like to join?`;
        
        // Sanitize text (though this message is clean, good practice)
        const cleanedMessage = this.sanitizeTextForSpeech(message);
        
        const utterance = new SpeechSynthesisUtterance(cleanedMessage);
        utterance.rate = 0.9; // Slightly slower for clarity
        utterance.pitch = 1.0;
        utterance.volume = this.audioState?.volume ?? 0.8;
        
        // Try to use a more natural voice
        const voices = this.speechSynthesis.getVoices();
        const preferredVoice = voices.find(v => v.name.includes('Samantha') || v.name.includes('Karen') || v.name.includes('Daniel'));
        if (preferredVoice) {
            utterance.voice = preferredVoice;
        }
        
        // Show audio control panel
        this.showAudioControlPanel('alert', 'Event Alert');
        
        utterance.onend = () => this.hideAudioControlPanel();
        utterance.onerror = () => this.hideAudioControlPanel();
        
        this.speechSynthesis.speak(utterance);
    }
    
    startVoiceResponse(eventId) {
        if (!this.voiceRecognition) {
            alert('Voice recognition is not supported in your browser.');
            return;
        }
        
        const alertDiv = document.getElementById(`alert-${eventId}`);
        if (alertDiv) {
            const btn = alertDiv.querySelector('button[onclick*="startVoiceResponse"]');
            if (btn) {
                btn.innerHTML = '🎤 Listening...';
                btn.classList.add('animate-pulse');
            }
        }
        
        this.voiceRecognition.onresult = (event) => {
            const transcript = event.results[0][0].transcript.toLowerCase();
            console.log('Voice input:', transcript);
            
            if (transcript.includes('know') || transcript.includes('got it') || transcript.includes('on it')) {
                this.handleVoiceResponse(eventId, 'acknowledged');
            } else if (transcript.includes('not') || transcript.includes('skip') || transcript.includes('cancel')) {
                this.handleVoiceResponse(eventId, 'declined');
            } else {
                this.handleVoiceResponse(eventId, 'unclear');
            }
        };
        
        this.voiceRecognition.onerror = (event) => {
            console.error('Voice recognition error:', event.error);
            alert('Could not understand. Please try again.');
        };
        
        this.voiceRecognition.start();
    }
    
    handleVoiceResponse(eventId, response) {
        const event = this.calendar.find(e => e.event_id === eventId);
        const eventTitle = event ? (event.summary || event.title) : 'the event';
        
        let message = '';
        if (response === 'acknowledged') {
            message = `Great! I've noted that you're aware of ${eventTitle}. See you there!`;
        } else if (response === 'declined') {
            message = `Understood. I've noted that you won't be attending ${eventTitle}.`;
        } else {
            message = `I didn't quite catch that. Please try again or dismiss this alert.`;
        }
        
        const utterance = new SpeechSynthesisUtterance(message);
        utterance.rate = 0.9;
        utterance.volume = this.audioState?.volume ?? 0.8;
        
        // Show audio control panel
        this.showAudioControlPanel('speech', 'Responding...');
        utterance.onend = () => this.hideAudioControlPanel();
        utterance.onerror = () => this.hideAudioControlPanel();
        
        this.speechSynthesis.speak(utterance);
        
        if (response !== 'unclear') {
            setTimeout(() => {
                this.dismissAlert(eventId);
            }, 2000);
        }
    }
    
    dismissAlert(eventId) {
        const alertDiv = document.getElementById(`alert-${eventId}`);
        if (alertDiv) {
            alertDiv.remove();
        }
    }
    
    dismissEventAlert(eventId) {
        this.dismissAlert(eventId);
    }
    
    // DETAIL MODALS
    async showTodoDetail(id) {
        const localTodo = this.todos.find(t => t.id === id);
        if (!localTodo) return;

        let todo = localTodo;
        try {
            const response = await fetch(`/api/tasks/${encodeURIComponent(id)}`);
            if (response.ok) {
                const detail = await response.json();
                if (detail && detail.task) {
                    todo = { ...localTodo, ...detail.task };
                }
            }
        } catch (error) {
            console.warn('Could not load full task detail, using local task data:', error);
        }
        
        // Determine source icon
        const sourceIcon = {
            'email': '📧',
            'calendar': '📅',
            'note': '📝',
            'notes_obsidian': '📝',
            'notes_google_drive': '📄',
            'ticktick': '✓',
            'default': '📌'
        }[todo.source?.toLowerCase()] || '📌';

        const sourceLink = todo.source_url || todo.gmail_link || (todo.source_info && todo.source_info.link);
        const sourceButtonLabel = todo.source_info?.display_text || `View Original ${todo.source_title || todo.source || 'Source'}`;
        
        const sourceButton = sourceLink ? `
            <button onclick="window.open('${this.escapeHtml(sourceLink)}', '_blank')" 
                    class="w-full px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors font-semibold">
                🔗 ${this.escapeHtml(sourceButtonLabel)}
            </button>
        ` : '';

        const createdLabel = todo.created_at ? this.formatDate(todo.created_at) : 'Unknown';
        const completedLabel = todo.completed_at ? this.formatDate(todo.completed_at) : '—';
        const statusLabel = (todo.status || 'pending').replace('_', ' ');
        const requiresResponse = todo.requires_response ? 'Yes' : 'No';
        const previewText = (todo.source_preview || '').toString();
        const fullReason = (todo.creation_reason || '').toString();
        
        const content = `
            <div class="space-y-4">
                <div class="flex items-center gap-3 mb-4">
                    <span class="text-3xl">${sourceIcon}</span>
                    <div>
                        <p class="text-xs font-semibold text-gray-400 uppercase">${this.escapeHtml(todo.source || 'Task')}</p>
                        <h1 class="text-2xl font-bold">${this.escapeHtml(todo.title)}</h1>
                        ${todo.source_title ? `<p class="text-sm text-gray-400 mt-1">From: ${this.escapeHtml(todo.source_title)}</p>` : ''}
                    </div>
                </div>
                
                ${todo.description ? `<p class="text-gray-300 bg-gray-700 rounded-lg p-4">${this.escapeHtml(todo.description)}</p>` : ''}

                ${todo.creation_reason ? `
                    <div class="bg-purple-900/30 border border-purple-700 rounded-lg p-4">
                        <p class="text-xs text-purple-300 uppercase mb-1">Why This Task Was Created</p>
                        <p class="text-sm text-purple-100">${this.escapeHtml(todo.creation_reason)}</p>
                    </div>
                ` : ''}

                <div class="grid grid-cols-2 gap-3">
                    <div class="bg-gray-700 rounded-lg p-3">
                        <p class="text-xs text-gray-400">Status</p>
                        <p class="text-lg font-semibold">${this.escapeHtml(statusLabel)}</p>
                    </div>
                    <div class="bg-gray-700 rounded-lg p-3">
                        <p class="text-xs text-gray-400">Needs Response</p>
                        <p class="text-lg font-semibold">${requiresResponse}</p>
                    </div>
                    <div class="bg-gray-700 rounded-lg p-3">
                        <p class="text-xs text-gray-400">Created</p>
                        <p class="text-lg font-semibold">${this.escapeHtml(createdLabel)}</p>
                    </div>
                    <div class="bg-gray-700 rounded-lg p-3">
                        <p class="text-xs text-gray-400">Completed</p>
                        <p class="text-lg font-semibold">${this.escapeHtml(completedLabel)}</p>
                    </div>
                </div>

                ${todo.source_preview ? `
                    <div class="bg-gray-750 border border-gray-700 rounded-lg p-4">
                        <p class="text-xs text-gray-400 uppercase mb-1">Source Preview</p>
                        <p class="text-sm text-gray-300">${this.escapeHtml(todo.source_preview)}</p>
                    </div>
                ` : ''}
                
                <div class="grid grid-cols-2 gap-3">
                    ${todo.priority ? `
                        <div class="bg-gray-700 rounded-lg p-3">
                            <p class="text-xs text-gray-400">Priority</p>
                            <p class="text-lg font-semibold">⚡ ${this.escapeHtml(todo.priority)}</p>
                        </div>
                    ` : ''}
                    ${todo.due_date ? `
                        <div class="bg-gray-700 rounded-lg p-3">
                            <p class="text-xs text-gray-400">Due Date</p>
                            <p class="text-lg font-semibold">📅 ${this.formatDate(todo.due_date)}</p>
                        </div>
                    ` : ''}
                </div>

                ${(todo.source_id || todo.email_id || sourceLink) ? `
                    <div class="bg-gray-800 border border-gray-700 rounded-lg p-4">
                        <p class="text-xs text-gray-400 uppercase mb-2">Origin Metadata</p>
                        ${todo.source_id ? `<p class="text-sm text-gray-300 break-all"><span class="text-gray-500">source_id:</span> ${this.escapeHtml(todo.source_id)}</p>` : ''}
                        ${todo.email_id ? `<p class="text-sm text-gray-300 break-all"><span class="text-gray-500">email_id:</span> ${this.escapeHtml(todo.email_id)}</p>` : ''}
                        ${sourceLink ? `<p class="text-sm text-gray-300 break-all"><span class="text-gray-500">link:</span> ${this.escapeHtml(sourceLink)}</p>` : ''}
                    </div>
                ` : ''}
                
                ${sourceButton}
                
                ${todo.source ? `
                    <div class="text-sm text-gray-400 border-t border-gray-700 pt-4">
                        <p>📌 Source: <span class="text-gray-300">${this.escapeHtml(todo.source_title || todo.source)}</span></p>
                    </div>
                ` : ''}
            </div>
        `;
        
        showModal('Task Details', content);
    }
    
    showEventDetail(id) {
        const event = this.calendar.find(e => e.event_id === id);
        if (!event) return;
        
        const start = event.start && event.start.dateTime ? event.start.dateTime : event.start;
        
        const content = `
            <div class="space-y-4">
                <h1 class="text-2xl font-bold">${this.escapeHtml(event.summary || event.title)}</h1>
                <p class="text-blue-400">${this.formatDate(start)} ${event.is_all_day ? '(All day)' : 'at ' + this.formatEventTime(event)}</p>
                ${event.location ? `<p class="text-gray-300">📍 ${this.escapeHtml(event.location)}</p>` : ''}
                ${event.description ? `<p class="text-gray-300">${this.escapeHtml(event.description)}</p>` : ''}
                ${event.organizer ? `<p class="text-gray-400 text-sm">Organizer: ${this.escapeHtml(event.organizer)}</p>` : ''}
                ${event.attendees && event.attendees.length > 0 ? `<p class="text-gray-400 text-sm">Attendees: ${event.attendees.length}</p>` : ''}
                ${event.calendar_url ? `<a href="${event.calendar_url}" target="_blank" class="text-blue-400 hover:underline text-sm">View in Google Calendar →</a>` : ''}
            </div>
        `;
        
        showModal('Event Details', content);
    }
    
    showEmailDetail(id) {
        const email = this.emails.find(e => e.id === id);
        if (!email) return;
        
        // Process email body to render HTML properly and extract text for reading
        let emailContent = email.body || email.snippet || 'No content available';
        let emailTextForReading = '';
        
        // Check if content contains HTML
        if (/<[^>]+>/.test(emailContent)) {
            // Create a temporary div to parse HTML
            const tempDiv = document.createElement('div');
            tempDiv.innerHTML = emailContent;
            
            // Extract text for voice reading (without HTML)
            emailTextForReading = tempDiv.textContent || tempDiv.innerText || '';
            
            // Style the HTML content for display
            tempDiv.querySelectorAll('*').forEach(el => {
                el.style.maxWidth = '100%';
                el.style.wordWrap = 'break-word';
            });
            
            tempDiv.querySelectorAll('img').forEach(img => {
                img.style.maxWidth = '100%';
                img.style.height = 'auto';
                img.style.borderRadius = '8px';
                img.style.marginTop = '8px';
                img.style.marginBottom = '8px';
            });
            
            tempDiv.querySelectorAll('a').forEach(link => {
                link.className = 'text-blue-400 hover:text-blue-300 underline';
                link.target = '_blank';
            });
            
            emailContent = tempDiv.innerHTML;
        } else {
            emailTextForReading = emailContent;
            emailContent = this.escapeHtml(emailContent).replace(/\n/g, '<br>');
        }
        
        const content = `
            <div class="space-y-4">
                <div class="border-b border-gray-700 pb-4">
                    <h1 class="text-2xl font-bold mb-2">${this.escapeHtml(email.subject)}</h1>
                    <p class="text-gray-400">From: ${this.escapeHtml(email.sender)}</p>
                    <p class="text-gray-400 text-sm">${this.formatDate(email.received_date || email.date || email.timestamp)}</p>
                    ${email.labels && email.labels.length > 0 ? `
                        <div class="flex gap-2 mt-2">
                            ${email.labels.map(label => 
                                `<span class="text-xs bg-blue-600 px-2 py-1 rounded">${this.escapeHtml(label)}</span>`
                            ).join('')}
                        </div>
                    ` : ''}
                </div>
                
                <div class="bg-gray-700 rounded-lg p-6 max-h-96 overflow-y-auto prose prose-invert max-w-none">
                    ${emailContent}
                </div>
                
                <div id="ai-analysis-section" class="bg-gray-800 rounded-lg p-4 border border-purple-600">
                    <div class="flex items-center justify-center gap-2 text-purple-400">
                        <div class="animate-spin rounded-full h-5 w-5 border-b-2 border-purple-400"></div>
                        <span>AI is analyzing this email...</span>
                    </div>
                </div>
                
                <div class="flex gap-2 pt-4 border-t border-gray-700">
                    ${email.gmail_url ? `
                        <button onclick="window.open('${email.gmail_url}', '_blank')" 
                                class="bg-blue-600 hover:bg-blue-700 px-4 py-2 rounded-lg font-semibold">
                            Open in Gmail
                        </button>
                    ` : ''}
                    <button onclick="closeModal()" 
                            class="bg-gray-700 hover:bg-gray-600 px-4 py-2 rounded-lg font-semibold">
                        Close
                    </button>
                </div>
            </div>
        `;
        
        showModal('Email', content);
        
        // Read email aloud and get AI analysis
        this.readAndAnalyzeEmail(email, emailTextForReading);
    }
    
    async readAndAnalyzeEmail(email, emailText) {
        // Prepare text for reading - subject + from + body
        const textToRead = `Email from ${email.sender}. Subject: ${email.subject}. ${emailText.substring(0, 500)}`;
        
        // Read email aloud
        this.speakText(textToRead);
        
        // Get AI analysis
        try {
            const response = await fetch('/api/ai/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    message: `Analyze this email and suggest what I should do:

Subject: ${email.subject}
From: ${email.sender}
Date: ${email.date || email.timestamp || email.received_date}

${emailText.substring(0, 1500)}

Please provide:
1. Brief summary (2-3 sentences)
2. Key action items or requests
3. Suggested response or next steps
4. Priority level (High/Medium/Low)

Then ask me: "What would you like to do with this email?"`,
                    context: {
                        email_context: {
                            subject: email.subject,
                            sender: email.sender,
                            priority: email.priority,
                            has_todos: email.has_todos,
                            labels: email.labels
                        }
                    }
                })
            });
            
            if (response.ok) {
                const data = await response.json();
                const aiAnalysis = data.response || data.message;
                
                // Update the analysis section
                const analysisSection = document.getElementById('ai-analysis-section');
                if (analysisSection) {
                    analysisSection.innerHTML = `
                        <div>
                            <h3 class="font-bold text-purple-400 mb-2 flex items-center gap-2">
                                <span>🤖</span>
                                <span>AI Analysis</span>
                            </h3>
                            <div class="text-gray-300 whitespace-pre-line mb-4">${this.escapeHtml(aiAnalysis)}</div>
                            <div class="flex gap-2 flex-wrap">
                                <button onclick="dataLoader.handleEmailAction('${email.id}', 'reply')" 
                                        class="bg-blue-600 hover:bg-blue-700 px-3 py-2 rounded text-sm">
                                    📝 Reply
                                </button>
                                <button onclick="dataLoader.handleEmailAction('${email.id}', 'create-task')" 
                                        class="bg-green-600 hover:bg-green-700 px-3 py-2 rounded text-sm">
                                    ✅ Create Task
                                </button>
                                <button onclick="dataLoader.handleEmailAction('${email.id}', 'schedule')" 
                                        class="bg-purple-600 hover:bg-purple-700 px-3 py-2 rounded text-sm">
                                    📅 Schedule Follow-up
                                </button>
                                <button onclick="dataLoader.handleEmailAction('${email.id}', 'archive')" 
                                        class="bg-gray-600 hover:bg-gray-700 px-3 py-2 rounded text-sm">
                                    📦 Archive
                                </button>
                                <button onclick="dataLoader.handleEmailAction('${email.id}', 'delete')" 
                                        class="bg-red-600 hover:bg-red-700 px-3 py-2 rounded text-sm">
                                    🗑️ Delete
                                </button>
                            </div>
                        </div>
                    `;
                    
                    // Read the AI analysis aloud
                    this.speakText(aiAnalysis);
                }
            }
        } catch (error) {
            console.error('Error analyzing email:', error);
            const analysisSection = document.getElementById('ai-analysis-section');
            if (analysisSection) {
                analysisSection.innerHTML = `
                    <div class="text-red-400">
                        <p>❌ Failed to analyze email. Please try again.</p>
                    </div>
                `;
            }
        }
    }
    
    async handleEmailAction(emailId, action) {
        const email = this.emails.find(e => e.id === emailId);
        if (!email) return;
        
        switch(action) {
            case 'reply':
                if (email.gmail_url) {
                    window.open(email.gmail_url, '_blank');
                }
                this.showNotification('Opening Gmail to reply...', 'info');
                break;
                
            case 'create-task':
                // Create a task from the email
                const newTask = {
                    title: `Follow up: ${email.subject}`,
                    description: `Email from ${email.sender}`,
                    priority: email.priority || 'medium',
                    source: 'email'
                };
                this.todos.push(newTask);
                this.renderTodos();
                this.showNotification('Task created!', 'success');
                closeModal();
                break;
                
            case 'schedule':
                this.showNotification('Schedule follow-up (coming soon)', 'info');
                break;
                
            case 'archive':
                this.showNotification('Archiving email...', 'info');
                // TODO: Call API to archive
                closeModal();
                break;
                
            case 'delete':
                if (confirm('Are you sure you want to delete this email?')) {
                    this.showNotification('Deleting email...', 'info');
                    // TODO: Call API to delete
                    closeModal();
                }
                break;
        }
    }
    
    async toggleTodo(id) {
        const todo = this.todos.find(t => t.id === id);
        if (!todo) return;
        
        // Toggle between completed and pending
        const newStatus = todo.status === 'completed' ? 'pending' : 'completed';
        
        try {
            const response = await fetch(`/api/tasks/${encodeURIComponent(id)}/status`, {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ status: newStatus })
            });
            
            if (response.ok) {
                // Update local state
                todo.status = newStatus;
                this.renderTodos();
                this.updateAllCounts();
            } else {
                console.error('Failed to update task status');
                alert('Failed to update task. Please try again.');
            }
        } catch (error) {
            console.error('Error updating task status:', error);
            alert('Failed to update task. Please try again.');
        }
    }
    
    async toggleTodoStarted(id) {
        const todo = this.todos.find(t => t.id === id);
        if (!todo) return;
        
        // Toggle between in_progress and pending (unless completed)
        if (todo.status === 'completed') return; // Don't toggle if already completed
        
        const newStatus = todo.status === 'in_progress' ? 'pending' : 'in_progress';
        
        try {
            const response = await fetch(`/api/tasks/${encodeURIComponent(id)}/status`, {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ status: newStatus })
            });
            
            if (response.ok) {
                // Update local state
                todo.status = newStatus;
                this.renderTodos();
            } else {
                console.error('Failed to update task status');
                alert('Failed to update task. Please try again.');
            }
        } catch (error) {
            console.error('Error updating task status:', error);
            alert('Failed to update task. Please try again.');
        }
    }
    
    // AI ASSISTANT
    async loadAISuggestions() {
        try {
            // Generate suggestions from emails with has_todos flag
            const todoEmails = this.emails.filter(e => e.has_todos);
            
            this.aiSuggestions = todoEmails.map((email, idx) => ({
                id: `suggestion-${idx}`,
                title: `Follow up: ${email.subject}`,
                description: email.snippet || 'Review and create tasks from this email',
                priority: email.priority,
                source: 'email',
                email_id: email.id,
                action: 'create_task'
            }));
            
            // Add high priority emails
            const highPriority = this.emails.filter(e => e.priority === 'high' && !e.has_todos);
            highPriority.slice(0, 3).forEach((email, idx) => {
                this.aiSuggestions.push({
                    id: `priority-${idx}`,
                    title: `High Priority: ${email.subject}`,
                    description: email.snippet || 'This email needs your attention',
                    priority: 'high',
                    source: 'email',
                    email_id: email.id,
                    action: 'review'
                });
            });
            
            // Filter out tasks that already exist in todos
            this.aiSuggestions = this.aiSuggestions.filter(suggestion => {
                // Check if a similar task already exists
                const exists = this.todos.some(todo => {
                    // Check for exact title match
                    if (todo.title && suggestion.title && 
                        todo.title.toLowerCase() === suggestion.title.toLowerCase()) {
                        return true;
                    }
                    // Check if the email subject is in the todo title or description
                    if (suggestion.email_id && this.emails) {
                        const email = this.emails.find(e => e.id === suggestion.email_id);
                        if (email && email.subject) {
                            const subject = email.subject.toLowerCase();
                            const todoTitle = (todo.title || '').toLowerCase();
                            const todoDesc = (todo.description || '').toLowerCase();
                            // Check if email subject is substantially present in todo
                            if (todoTitle.includes(subject) || subject.includes(todoTitle) ||
                                todoDesc.includes(subject)) {
                                return true;
                            }
                        }
                    }
                    return false;
                });
                return !exists;
            });
            
            // Generate personalized random suggestion
            this.generatePersonalizedSuggestion();
            
            // Generate overview summary
            await this.generateOverviewSummary();
            
            this.renderAISuggestions();
        } catch (error) {
            console.error('Error loading AI suggestions:', error);
        }
    }
    
    renderAISuggestions() {
        const container = document.getElementById('ai-suggestions');
        if (!container) return;
        
        let html = '';
        
        // Add 5-minute overview summary at the top
        if (this.overviewSummary) {
            html += `
                <div class="col-span-full bg-gradient-to-r from-purple-900/50 to-blue-900/50 rounded-lg p-6 border border-purple-500/30 mb-6">
                    <div class="flex items-center gap-3 mb-3">
                        <span class="text-3xl">🧠</span>
                        <h3 class="text-xl font-semibold">5-Minute Overview</h3>
                    </div>
                    <div class="text-gray-200 space-y-2 text-sm">
                        ${this.overviewSummary}
                    </div>
                </div>
            `;
        }
        
        // Add personalized suggestion
        if (this.personalizedSuggestion) {
            html += `
                <div class="col-span-full bg-gradient-to-r from-green-900/50 to-teal-900/50 rounded-lg p-6 border border-green-500/30 mb-6">
                    <div class="flex items-center gap-3 mb-3">
                        <span class="text-3xl">✨</span>
                        <h3 class="text-xl font-semibold">Personalized for You</h3>
                    </div>
                    <div class="text-gray-200 space-y-2">
                        <p class="font-medium">${this.escapeHtml(this.personalizedSuggestion.title)}</p>
                        <p class="text-sm text-gray-300">${this.escapeHtml(this.personalizedSuggestion.description)}</p>
                        ${this.personalizedSuggestion.action ? `
                            <button onclick="dataLoader.handlePersonalizedAction('${this.personalizedSuggestion.action}')" 
                                    class="mt-2 bg-green-600 hover:bg-green-700 px-4 py-2 rounded text-sm">
                                ${this.personalizedSuggestion.actionLabel || 'Take Action'}
                            </button>
                        ` : ''}
                    </div>
                </div>
            `;
        }
        
        // Filter out dismissed suggestions
        const visibleSuggestions = this.aiSuggestions.filter(s => !this.dismissedSuggestions.has(s.id));
        
        if (visibleSuggestions.length === 0 && !this.overviewSummary && !this.personalizedSuggestion) {
            container.innerHTML = `
                <div class="col-span-full text-center py-12">
                    <div class="text-6xl mb-4">✅</div>
                    <h3 class="text-xl font-semibold mb-2">All Caught Up!</h3>
                    <p class="text-gray-400">No pending suggestions</p>
                </div>
            `;
            return;
        }
        
        html += visibleSuggestions.map(suggestion => {
            const feedback = this.feedbackData[`suggestion-${suggestion.id}`] || null;
            return `
            <div class="bg-gray-800 rounded-lg p-4 border border-gray-700">
                <div class="flex justify-between items-start mb-2">
                    <h4 class="font-semibold text-white">${this.escapeHtml(suggestion.title)}</h4>
                    ${suggestion.priority === 'high' ? '<span class="text-xs bg-red-600 px-2 py-1 rounded">High Priority</span>' : ''}
                </div>
                <p class="text-sm text-gray-400 mb-3 line-clamp-2">${this.escapeHtml(suggestion.description)}</p>
                <div class="flex gap-2 mb-2">
                    <button onclick="dataLoader.applySuggestion('${suggestion.id}')" 
                            class="flex-1 bg-blue-600 hover:bg-blue-700 px-3 py-1 rounded text-sm">
                        ${suggestion.action === 'create_task' ? 'Create Task' : 'Review'}
                    </button>
                    <button onclick="dataLoader.dismissSuggestion('${suggestion.id}')" 
                            class="bg-gray-700 hover:bg-gray-600 px-3 py-1 rounded text-sm">
                        Dismiss
                    </button>
                </div>
                <div class="flex gap-1 pt-2 border-t border-gray-700">
                    <button onclick="dataLoader.giveFeedback('suggestion', '${suggestion.id}', 'up')" 
                            class="feedback-btn px-2 py-1 rounded text-xs ${feedback === 'up' ? 'bg-green-600' : 'bg-gray-700 hover:bg-green-600'}" 
                            title="Good suggestion">👍</button>
                    <button onclick="dataLoader.giveFeedback('suggestion', '${suggestion.id}', 'neutral')" 
                            class="feedback-btn px-2 py-1 rounded text-xs ${feedback === 'neutral' ? 'bg-blue-600' : 'bg-gray-700 hover:bg-blue-600'}" 
                            title="Neutral">👌</button>
                    <button onclick="dataLoader.giveFeedback('suggestion', '${suggestion.id}', 'down')" 
                            class="feedback-btn px-2 py-1 rounded text-xs ${feedback === 'down' ? 'bg-red-600' : 'bg-gray-700 hover:bg-red-600'}" 
                            title="Not helpful">👎</button>
                </div>
            </div>
        `;
        }).join('');
        
        container.innerHTML = html;
    }
    
    applySuggestion(id) {
        const suggestion = this.aiSuggestions.find(s => s.id === id);
        if (!suggestion) return;
        
        if (suggestion.action === 'create_task') {
            // Navigate to email or create task
            showSection('emails');
            if (suggestion.email_id) {
                this.showEmailDetail(suggestion.email_id);
            }
        } else {
            // Navigate to the relevant section
            showSection('emails');
            if (suggestion.email_id) {
                this.showEmailDetail(suggestion.email_id);
            }
        }
    }
    
    dismissSuggestion(id) {
        this.dismissedSuggestions.add(id);
        this.saveDismissedSuggestions();
        this.aiSuggestions = this.aiSuggestions.filter(s => s.id !== id);
        this.renderAISuggestions();
    }
    
    saveDismissedSuggestions() {
        localStorage.setItem('dismissedSuggestions', JSON.stringify([...this.dismissedSuggestions]));
    }
    
    loadDismissedSuggestions() {
        const stored = localStorage.getItem('dismissedSuggestions');
        if (stored) {
            this.dismissedSuggestions = new Set(JSON.parse(stored));
        }
    }
    
    async sendAIMessage() {
        const input = document.getElementById('ai-chat-input');
        const message = input.value.trim();
        
        if (!message) return;
        
        // Add user message
        this.aiMessages.push({ role: 'user', content: message });
        this.renderAIChat();
        input.value = '';
        
        // IMMEDIATELY show "working" status
        const statusMessageId = `status_${Date.now()}`;
        this.aiMessages.push({
            role: 'status',
            content: '🤖 I\'m on it...',
            id: statusMessageId
        });
        this.renderAIChat();
        
        // Speak immediate acknowledgment if voice enabled
        if (this.aiVoiceEnabled && this.speechSynthesis) {
            this.speakText("I'm on it");
        }
        
        try {
            // Build comprehensive context with actual data
            const context = {
                current_time: new Date().toLocaleString(),
                todos: {
                    count: this.todos.length,
                    active_count: this.todos.filter(t => t.status !== 'completed' && t.status !== 'deleted').length,
                    items: this.todos.slice(0, 10).map(t => ({
                        title: t.title,
                        priority: t.priority,
                        due_date: t.due_date,
                        source: t.source,
                        status: t.status,
                        description: t.description ? t.description.substring(0, 100) : null
                    }))
                },
                calendar: {
                    count: this.calendar.length,
                    upcoming: this.calendar
                        .filter(e => new Date(e.start) > new Date())
                        .slice(0, 5)
                        .map(e => ({
                            summary: e.summary,
                            start: e.start,
                            location: e.location,
                            description: e.description ? e.description.substring(0, 100) : null
                        }))
                },
                emails: {
                    count: this.emails.length,
                    high_priority_count: this.emails.filter(e => e.priority === 'high').length,
                    recent: this.emails.slice(0, 5).map(e => ({
                        subject: e.subject,
                        sender: e.sender,
                        priority: e.priority,
                        has_todos: e.has_todos,
                        snippet: e.snippet ? e.snippet.substring(0, 100) : null
                    }))
                },
                user_preferences: {
                    liked_items_count: Object.keys(this.feedbackData).filter(
                        k => this.feedbackData[k] === 'like'
                    ).length,
                    recent_feedback: Object.entries(this.feedbackData)
                        .slice(-5)
                        .map(([key, value]) => ({ item: key, sentiment: value }))
                }
            };
            
            // Use EventSource for streaming responses with real-time progress updates
            const messageId = `msg_${Date.now()}`;
            // Reuse the statusMessageId we already created above
            let accumulatedResponse = '';
            let hasSeenResponse = false;
            
            // Build URL with query parameters for GET-compatible EventSource
            // Note: EventSource only supports GET, so we can't send large context in body
            // The backend will build context server-side
            const params = new URLSearchParams({
                message: message,
                conversation_id: this.conversationId || ''
            });

            if (this.activeAssistantId) {
                params.set('assistant_id', this.activeAssistantId);
            }
            
            const streamUrl = `/api/ai/chat/stream?${params.toString()}`;
            console.log('🚀 Opening AI stream:', streamUrl);
            
            const eventSource = new EventSource(streamUrl);
            
            eventSource.onopen = () => {
                console.log('✅ EventSource connection opened');
            };
            
            eventSource.onmessage = (event) => {
                console.log('📨 Received event:', event.data);
                try {
                    const data = JSON.parse(event.data);
                    
                    if (data.type === 'status') {
                        console.log('📊 Status update:', data.message);
                        // Show/update status message
                        const existingStatusIndex = this.aiMessages.findIndex(m => m.id === statusMessageId);
                        if (existingStatusIndex >= 0) {
                            this.aiMessages[existingStatusIndex].content = data.message;
                        } else {
                            this.aiMessages.push({
                                role: 'status',
                                content: data.message,
                                id: statusMessageId
                            });
                        }
                        this.renderAIChat();
                        
                    } else if (data.type === 'response') {
                        // Accumulate response chunks
                        accumulatedResponse += data.content;
                        
                        // Remove status message if present
                        if (!hasSeenResponse) {
                            const statusIndex = this.aiMessages.findIndex(m => m.id === statusMessageId);
                            if (statusIndex >= 0) {
                                this.aiMessages.splice(statusIndex, 1);
                            }
                            hasSeenResponse = true;
                        }
                        
                        // Update or create response message
                        const existingIndex = this.aiMessages.findIndex(m => m.id === messageId);
                        if (existingIndex >= 0) {
                            this.aiMessages[existingIndex].content = accumulatedResponse;
                        } else {
                            this.aiMessages.push({
                                role: 'assistant',
                                content: accumulatedResponse,
                                id: messageId,
                                conversation_id: this.conversationId
                            });
                        }
                        this.renderAIChat();
                        
                    } else if (data.type === 'done') {
                        // Save conversation ID
                        if (data.conversation_id) {
                            this.conversationId = data.conversation_id;
                            
                            // Update conversation_id on the message
                            const msgIndex = this.aiMessages.findIndex(m => m.id === messageId);
                            if (msgIndex >= 0) {
                                this.aiMessages[msgIndex].conversation_id = data.conversation_id;
                            }
                        }
                        
                        // Speak the complete response if voice is enabled
                        if (this.aiVoiceEnabled && this.speechSynthesis && accumulatedResponse) {
                            this.speakText(accumulatedResponse);
                        }

                        this.loadAIMemory();
                        
                        eventSource.close();
                        
                    } else if (data.type === 'error') {
                        // Remove status message if present
                        const statusIndex = this.aiMessages.findIndex(m => m.id === statusMessageId);
                        if (statusIndex >= 0) {
                            this.aiMessages.splice(statusIndex, 1);
                        }

                        if (!hasSeenResponse) {
                            this.sendAIMessageFallback(message, messageId, statusMessageId);
                        } else {
                            const errorMsg = data.message || 'Sorry, I encountered an error. Please try again.';
                            this.aiMessages.push({
                                role: 'assistant',
                                content: errorMsg,
                                id: messageId
                            });
                            this.renderAIChat();

                            if (this.aiVoiceEnabled && this.speechSynthesis) {
                                this.speakText(errorMsg);
                            }
                        }
                        
                        eventSource.close();
                    }
                } catch (parseError) {
                    console.error('Error parsing event data:', parseError, event.data);
                }
            };
            
            eventSource.onerror = (error) => {
                console.error('❌ EventSource error:', error);
                console.error('EventSource readyState:', eventSource.readyState);
                eventSource.close();
                
                // Remove status message if present
                const statusIndex = this.aiMessages.findIndex(m => m.id === statusMessageId);
                if (statusIndex >= 0) {
                    this.aiMessages.splice(statusIndex, 1);
                }
                
                // Only show error if no response was received
                if (!hasSeenResponse) {
                    this.sendAIMessageFallback(message, messageId, statusMessageId);
                }
            };
        } catch (error) {
            console.error('Error sending AI message:', error);
            const errorMsg = 'Sorry, I encountered an error. Please try again.';
            this.aiMessages.push({ 
                role: 'assistant', 
                content: errorMsg
            });
            this.renderAIChat();
            
            if (this.aiVoiceEnabled && this.speechSynthesis) {
                this.speakText(errorMsg);
            }
        }
    }

    async sendAIMessageFallback(message, messageId, statusMessageId) {
        try {
            const existingStatusIndex = this.aiMessages.findIndex(m => m.id === statusMessageId);
            if (existingStatusIndex >= 0) {
                this.aiMessages[existingStatusIndex].content = '⚠️ Stream interrupted, retrying...';
                this.renderAIChat();
            }

            const response = await fetch('/api/ai/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    message,
                    conversation_id: this.conversationId || null,
                    stream: false,
                    assistant_id: this.activeAssistantId || undefined
                })
            });

            const data = await response.json();

            const statusIndex = this.aiMessages.findIndex(m => m.id === statusMessageId);
            if (statusIndex >= 0) {
                this.aiMessages.splice(statusIndex, 1);
            }

            if (response.ok && data.success && data.response) {
                this.aiMessages.push({
                    role: 'assistant',
                    content: data.response,
                    id: messageId,
                    conversation_id: data.conversation_id || this.conversationId
                });

                if (data.conversation_id) {
                    this.conversationId = data.conversation_id;
                }

                this.renderAIChat();

                if (this.aiVoiceEnabled && this.speechSynthesis) {
                    this.speakText(data.response);
                }

                this.loadAIMemory();
                return;
            }

            throw new Error(data.error || 'Fallback request failed');
        } catch (fallbackError) {
            console.error('Fallback chat request failed:', fallbackError);
            const errorMsg = 'Sorry, I encountered an error. Please try again.';
            this.aiMessages.push({
                role: 'assistant',
                content: errorMsg,
                id: messageId
            });
            this.renderAIChat();

            if (this.aiVoiceEnabled && this.speechSynthesis) {
                this.speakText(errorMsg);
            }
        }
    }
    
    /**
     * Convert Markdown to HTML for display in chat messages.
     * Supports: bold, italic, code, code blocks, links, lists, headers, blockquotes
     */
    renderMarkdown(text) {
        if (!text) return text;
        
        let html = this.escapeHtml(text);
        
        // Code blocks (```code```) - must be first to prevent inner processing
        html = html.replace(/```(\w*)\n?([\s\S]*?)```/g, (match, lang, code) => {
            return `<pre class="bg-gray-900 rounded p-2 my-2 overflow-x-auto text-xs"><code class="language-${lang || 'text'}">${code.trim()}</code></pre>`;
        });
        
        // Inline code (`code`)
        html = html.replace(/`([^`]+)`/g, '<code class="bg-gray-900 px-1 rounded text-xs">$1</code>');
        
        // Headers (### Header)
        html = html.replace(/^### (.+)$/gm, '<h3 class="font-bold text-base mt-2 mb-1">$1</h3>');
        html = html.replace(/^## (.+)$/gm, '<h2 class="font-bold text-lg mt-2 mb-1">$1</h2>');
        html = html.replace(/^# (.+)$/gm, '<h1 class="font-bold text-xl mt-2 mb-1">$1</h1>');
        
        // Bold (**text** or __text__)
        html = html.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
        html = html.replace(/__([^_]+)__/g, '<strong>$1</strong>');
        
        // Italic (*text* or _text_)
        html = html.replace(/\*([^*]+)\*/g, '<em>$1</em>');
        html = html.replace(/(?<![a-zA-Z])_([^_]+)_(?![a-zA-Z])/g, '<em>$1</em>');
        
        // Strikethrough (~~text~~)
        html = html.replace(/~~([^~]+)~~/g, '<del>$1</del>');
        
        // Links [text](url)
        html = html.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" class="text-blue-400 hover:underline">$1</a>');
        
        // Blockquotes (> text)
        html = html.replace(/^&gt; (.+)$/gm, '<blockquote class="border-l-2 border-gray-500 pl-2 italic text-gray-400">$1</blockquote>');
        
        // Unordered lists (- item or * item)
        html = html.replace(/^[\-\*] (.+)$/gm, '<li class="ml-4">• $1</li>');
        
        // Ordered lists (1. item)
        html = html.replace(/^\d+\. (.+)$/gm, '<li class="ml-4 list-decimal">$1</li>');
        
        // Horizontal rule (---)
        html = html.replace(/^---$/gm, '<hr class="border-gray-600 my-2">');
        
        // Line breaks (preserve paragraph structure)
        html = html.replace(/\n\n/g, '</p><p class="mt-2">');
        html = html.replace(/\n/g, '<br>');
        
        // Wrap in paragraph if not already structured
        if (!html.startsWith('<')) {
            html = `<p>${html}</p>`;
        }
        
        return html;
    }
    
    /**
     * Strip Markdown syntax from text for speech.
     * Removes formatting markers while keeping the content readable.
     */
    stripMarkdownForSpeech(text) {
        if (!text) return text;
        
        let cleaned = text;
        
        // Remove code blocks entirely (they don't speak well)
        cleaned = cleaned.replace(/```[\s\S]*?```/g, ' code block ');
        
        // Remove inline code backticks
        cleaned = cleaned.replace(/`([^`]+)`/g, '$1');
        
        // Remove headers markers
        cleaned = cleaned.replace(/^#{1,6}\s+/gm, '');
        
        // Remove bold markers
        cleaned = cleaned.replace(/\*\*([^*]+)\*\*/g, '$1');
        cleaned = cleaned.replace(/__([^_]+)__/g, '$1');
        
        // Remove italic markers
        cleaned = cleaned.replace(/\*([^*]+)\*/g, '$1');
        cleaned = cleaned.replace(/(?<![a-zA-Z])_([^_]+)_(?![a-zA-Z])/g, '$1');
        
        // Remove strikethrough
        cleaned = cleaned.replace(/~~([^~]+)~~/g, '$1');
        
        // Convert links to just the text
        cleaned = cleaned.replace(/\[([^\]]+)\]\([^)]+\)/g, '$1');
        
        // Remove blockquote markers
        cleaned = cleaned.replace(/^>\s*/gm, '');
        
        // Remove list markers
        cleaned = cleaned.replace(/^[\-\*]\s+/gm, '');
        cleaned = cleaned.replace(/^\d+\.\s+/gm, '');
        
        // Remove horizontal rules
        cleaned = cleaned.replace(/^---$/gm, '');
        
        // Remove excess whitespace
        cleaned = cleaned.replace(/\n{3,}/g, '\n\n');
        
        return cleaned;
    }
    
    /**
     * Sanitize text for natural speech by removing elements that sound bad when spoken.
     * Removes URLs, hashes, long numbers, file paths, markdown syntax, etc.
     */
    sanitizeTextForSpeech(text) {
        if (!text) return text;
        
        // First strip markdown syntax
        let cleaned = this.stripMarkdownForSpeech(text);
        
        // URLs
        cleaned = cleaned.replace(/https?:\/\/[^\s<>"{}|\\^`\[\]]+/gi, 'link');
        cleaned = cleaned.replace(/www\.[^\s<>"{}|\\^`\[\]]+/gi, 'link');
        
        // Email addresses
        cleaned = cleaned.replace(/[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}/g, 'email address');
        
        // UUIDs
        cleaned = cleaned.replace(/[a-fA-F0-9]{8}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{12}/g, 'ID');
        
        // SHA/MD5 hashes (32+ hex chars)
        cleaned = cleaned.replace(/\b[a-fA-F0-9]{32,}\b/g, 'hash');
        
        // Long hex values
        cleaned = cleaned.replace(/\b0x[a-fA-F0-9]{8,}\b/g, 'hex value');
        
        // Long numeric sequences (7+ digits)
        cleaned = cleaned.replace(/\b\d{7,}\b/g, 'number');
        
        // File paths
        cleaned = cleaned.replace(/[\/\\][\w.\/\\-]{10,}/g, ' file path ');
        
        // Base64-like strings
        cleaned = cleaned.replace(/[A-Za-z0-9+\/=]{40,}/g, 'encoded data');
        
        // JSON-like content
        cleaned = cleaned.replace(/\{[^{}]{100,}\}/g, 'data object');
        
        // Code syntax
        cleaned = cleaned.replace(/[\[\]{}();]{3,}/g, '');
        
        // Multiple special chars
        cleaned = cleaned.replace(/[_\-=]{4,}/g, ' ');
        
        // Clean up whitespace
        cleaned = cleaned.replace(/\s+/g, ' ').trim();
        
        return cleaned;
    }
    
    speakText(text, forceSignature = false) {
        // Check if globally muted
        if (this.globalMuted) {
            console.log('🔇 Voice muted globally');
            return;
        }

        const activeAssistant = this.getActiveAssistant();
        const effectiveBrowserVoice = activeAssistant?.browser_voice || this.selectedVoice;
        
        // Sanitize text for natural speech
        const cleanedText = this.sanitizeTextForSpeech(text);
        if (!cleanedText || cleanedText.length < 2) {
            console.log('🔇 Text too short after sanitization, skipping');
            return;
        }
        
        // Check if Rogr is selected (default)
        if (!effectiveBrowserVoice || effectiveBrowserVoice === 'rogr') {
            // Use Rogr battle-droid voice system
            // If forceSignature is true (from test button), use it; otherwise use setting
            const assistantStyle = activeAssistant?.voice_style || 'droid';
            this.speakWithRogr(cleanedText, assistantStyle, forceSignature ? true : null);
        } else {
            // Use browser TTS for other voices
            this.speakWithBrowserTTS(cleanedText, activeAssistant);
        }
    }
    
    speakWithBrowserTTS(text, assistant = null) {
        // Fallback to browser Text-to-Speech
        if ('speechSynthesis' in window) {
            // Cancel any ongoing speech
            window.speechSynthesis.cancel();

            const cleanedText = this.sanitizeTextForSpeech(text);
            if (!cleanedText || cleanedText.length < 2) return;

            const utterance = new SpeechSynthesisUtterance(cleanedText);
            const selectedVoiceName = assistant?.browser_voice || this.selectedVoice;
            
            // Find and set the selected voice
            if (selectedVoiceName) {
                const voice = this.availableVoices.find(v => v.name === selectedVoiceName);
                if (voice) {
                    utterance.voice = voice;
                }
            }

            // Set voice properties (per-assistant if provided)
            const assistantRate = Number(assistant?.voice_speed ?? 0.95);
            const assistantPitch = Number(assistant?.voice_pitch ?? 1.0);
            utterance.rate = Math.max(0.5, Math.min(1.8, assistantRate));
            utterance.pitch = Math.max(0.5, Math.min(1.8, assistantPitch));
            utterance.volume = this.audioState?.volume ?? 1.0;

            this.showAudioControlPanel('speech', 'Speaking...');
            utterance.onend = () => this.hideAudioControlPanel();
            utterance.onerror = () => this.hideAudioControlPanel();
            
            window.speechSynthesis.speak(utterance);
        } else {
            console.warn('Browser TTS not supported');
        }
    }
    
    async speakWithRogr(text, style = 'droid', addSignature = null) {
        const activeAssistant = this.getActiveAssistant();
        // Use setting if not explicitly specified
        if (addSignature === null) {
            addSignature = activeAssistant ? !!activeAssistant.signature_enabled : this.voiceSignatureEnabled;
        }
        
        // Show audio control panel
        this.showAudioControlPanel('ai-voice', 'Rogr speaking...');
        
        try {
            const response = await fetch('/api/voice/test', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    message: text,
                    style: style,
                    signature: addSignature,
                    assistant_id: this.activeAssistantId
                })
            });
            
            const result = await response.json();
            if (!result.success) {
                console.error('Voice system error:', result.error);
                this.hideAudioControlPanel();
            } else {
                // Voice was sent to PersonaPlex - hide after estimated time
                // Rough estimate: 100ms per character
                const estimatedDuration = Math.max(2000, text.length * 100);
                setTimeout(() => this.hideAudioControlPanel(), estimatedDuration);
            }
        } catch (error) {
            console.error('Failed to speak with Rogr:', error);
            this.hideAudioControlPanel();
        }
    }
    
    // Legacy browser TTS (fallback if needed)
    speakTextBrowser(text) {
        if (!this.speechSynthesis) return;
        
        // Sanitize text
        const cleanedText = this.sanitizeTextForSpeech(text);
        if (!cleanedText || cleanedText.length < 2) return;
        
        // Cancel any ongoing speech
        this.speechSynthesis.cancel();
        
        const utterance = new SpeechSynthesisUtterance(cleanedText);
        utterance.rate = 0.9;
        utterance.pitch = 1.0;
        utterance.volume = this.audioState?.volume ?? 0.8;
        
        // Get available voices (they may have loaded since init)
        const voices = this.speechSynthesis.getVoices();
        
        // If voices just loaded, update our list
        if (voices.length > this.availableVoices.length) {
            this.availableVoices = voices;
            console.log('🔄 Voices updated, now have', voices.length, 'voices');
        }
        
        // If we have a selected voice, use it
        if (this.selectedVoice) {
            const voice = voices.find(v => v.name === this.selectedVoice);
            if (voice) {
                utterance.voice = voice;
                console.log('🎤 Using voice:', voice.name);
            } else {
                console.warn('⚠️ Selected voice not found:', this.selectedVoice);
                // Try to set a new default
                this.setDefaultVoice();
            }
        } else if (voices.length > 0) {
            // No voice selected yet, set default
            this.setDefaultVoice();
            if (this.selectedVoice) {
                const voice = voices.find(v => v.name === this.selectedVoice);
                if (voice) {
                    utterance.voice = voice;
                    console.log('🎤 Using default voice:', voice.name);
                }
            }
        }
        
        // Show stop button and start listening for stop commands
        this.showStopSpeechButton();
        this.startStopCommandListener();
        
        // Hide stop button and stop listener when speech ends
        utterance.onend = () => {
            this.hideStopSpeechButton();
            this.stopStopCommandListener();
        };
        
        utterance.onerror = (error) => {
            console.error('Speech error:', error);
            this.hideStopSpeechButton();
            this.stopStopCommandListener();
        };
        
        this.speechSynthesis.speak(utterance);
    }
    
    stopSpeech() {
        if (this.speechSynthesis) {
            this.speechSynthesis.cancel();
        }
        this.hideAudioControlPanel();
        this.stopStopCommandListener();
    }
    
    // =========================================================================
    // FLOATING AUDIO CONTROL PANEL
    // Unified control for all audio: speech, music, AI voice
    // =========================================================================
    
    initAudioControlPanel() {
        // Track audio state
        this.audioState = {
            isSpeaking: false,
            isMusicPlaying: false,
            currentSource: null, // 'speech', 'music', 'ai-voice'
            volume: 0.8,
            isMuted: false
        };
        
        // Create the floating panel (hidden by default)
        this.createAudioControlPanel();
    }
    
    createAudioControlPanel() {
        // Remove existing panel if any
        const existing = document.getElementById('audio-control-panel');
        if (existing) existing.remove();
        
        const panel = document.createElement('div');
        panel.id = 'audio-control-panel';
        panel.className = 'fixed bottom-6 right-6 z-[9999] bg-gray-900/95 backdrop-blur-sm border border-gray-700 rounded-2xl shadow-2xl p-3 transition-all duration-300 transform translate-y-full opacity-0 pointer-events-none';
        panel.innerHTML = `
            <div class="flex items-center gap-3">
                <!-- Audio source indicator -->
                <div id="audio-source-indicator" class="flex items-center gap-2 px-3 py-1.5 bg-gray-800 rounded-lg min-w-[120px]">
                    <span id="audio-icon" class="text-lg">🔊</span>
                    <span id="audio-label" class="text-sm text-gray-300 truncate">Audio</span>
                </div>
                
                <!-- Volume slider -->
                <div class="flex items-center gap-2">
                    <button id="audio-mute-btn" class="p-2 rounded-lg hover:bg-gray-700 transition-colors" title="Mute">
                        <svg id="volume-icon" class="w-5 h-5 text-gray-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15.536 8.464a5 5 0 010 7.072M18.364 5.636a9 9 0 010 12.728M12 6.253v11.494c0 .935-1.03 1.535-1.856 1.082l-4.39-2.561A2 2 0 014.9 16H3a2 2 0 01-2-2v-4a2 2 0 012-2h1.9a2 2 0 00.854-.189l4.39-2.561C10.97 4.719 12 5.319 12 6.253z"/>
                        </svg>
                    </button>
                    <input type="range" id="audio-volume-slider" min="0" max="100" value="80" 
                           class="w-20 h-1.5 bg-gray-700 rounded-lg appearance-none cursor-pointer accent-blue-500">
                </div>
                
                <!-- Skip/Next button -->
                <button id="audio-skip-btn" class="p-2 rounded-lg hover:bg-gray-700 transition-colors" title="Skip">
                    <svg class="w-5 h-5 text-gray-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"/>
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 5v14"/>
                    </svg>
                </button>
                
                <!-- Stop button -->
                <button id="audio-stop-btn" class="p-2 bg-red-600 hover:bg-red-700 rounded-lg transition-colors" title="Stop">
                    <svg class="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <rect x="6" y="6" width="12" height="12" rx="1" stroke-width="2"/>
                    </svg>
                </button>
                
                <!-- Close/minimize button -->
                <button id="audio-close-btn" class="p-1.5 rounded-lg hover:bg-gray-700 transition-colors text-gray-500 hover:text-gray-300" title="Hide controls">
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/>
                    </svg>
                </button>
            </div>
        `;
        
        document.body.appendChild(panel);
        
        // Bind event handlers
        this.bindAudioControlEvents();
    }
    
    bindAudioControlEvents() {
        const muteBtn = document.getElementById('audio-mute-btn');
        const volumeSlider = document.getElementById('audio-volume-slider');
        const skipBtn = document.getElementById('audio-skip-btn');
        const stopBtn = document.getElementById('audio-stop-btn');
        const closeBtn = document.getElementById('audio-close-btn');
        
        if (muteBtn) {
            muteBtn.onclick = () => this.toggleAudioMute();
        }
        
        if (volumeSlider) {
            volumeSlider.oninput = (e) => this.setAudioVolume(e.target.value / 100);
        }
        
        if (skipBtn) {
            skipBtn.onclick = () => this.skipCurrentAudio();
        }
        
        if (stopBtn) {
            stopBtn.onclick = () => this.stopAllAudio();
        }
        
        if (closeBtn) {
            closeBtn.onclick = () => this.hideAudioControlPanel();
        }
        
        // Keyboard shortcut: Escape to stop audio
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && this.audioState?.isSpeaking) {
                this.stopAllAudio();
            }
        });
    }
    
    showAudioControlPanel(source = 'speech', label = 'Speaking...') {
        if (!this.audioState) this.initAudioControlPanel();
        
        this.audioState.currentSource = source;
        this.audioState.isSpeaking = true;
        
        const panel = document.getElementById('audio-control-panel');
        const icon = document.getElementById('audio-icon');
        const labelEl = document.getElementById('audio-label');
        
        if (!panel) {
            this.createAudioControlPanel();
            return this.showAudioControlPanel(source, label);
        }
        
        // Update source indicator
        const icons = {
            'speech': '🗣️',
            'music': '🎵',
            'ai-voice': '🤖',
            'alert': '🔔'
        };
        
        if (icon) icon.textContent = icons[source] || '🔊';
        if (labelEl) labelEl.textContent = label;
        
        // Show panel with animation
        panel.classList.remove('translate-y-full', 'opacity-0', 'pointer-events-none');
        panel.classList.add('translate-y-0', 'opacity-100', 'pointer-events-auto');
    }
    
    hideAudioControlPanel() {
        if (this.audioState) {
            this.audioState.isSpeaking = false;
            this.audioState.currentSource = null;
        }
        
        const panel = document.getElementById('audio-control-panel');
        if (panel) {
            panel.classList.add('translate-y-full', 'opacity-0', 'pointer-events-none');
            panel.classList.remove('translate-y-0', 'opacity-100', 'pointer-events-auto');
        }
    }
    
    toggleAudioMute() {
        if (!this.audioState) return;
        
        this.audioState.isMuted = !this.audioState.isMuted;
        this.globalMuted = this.audioState.isMuted;
        
        const volumeIcon = document.getElementById('volume-icon');
        const volumeSlider = document.getElementById('audio-volume-slider');
        
        if (this.audioState.isMuted) {
            // Muted
            if (volumeIcon) {
                volumeIcon.innerHTML = '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5.586 15H4a1 1 0 01-1-1v-4a1 1 0 011-1h1.586l4.707-4.707C10.923 3.663 12 4.109 12 5v14c0 .891-1.077 1.337-1.707.707L5.586 15z"/><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2"/>';
            }
            if (volumeSlider) volumeSlider.disabled = true;
            
            // Actually mute
            if (this.speechSynthesis) this.speechSynthesis.cancel();
        } else {
            // Unmuted
            if (volumeIcon) {
                volumeIcon.innerHTML = '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15.536 8.464a5 5 0 010 7.072M18.364 5.636a9 9 0 010 12.728M12 6.253v11.494c0 .935-1.03 1.535-1.856 1.082l-4.39-2.561A2 2 0 014.9 16H3a2 2 0 01-2-2v-4a2 2 0 012-2h1.9a2 2 0 00.854-.189l4.39-2.561C10.97 4.719 12 5.319 12 6.253z"/>';
            }
            if (volumeSlider) volumeSlider.disabled = false;
        }
    }
    
    setAudioVolume(volume) {
        if (!this.audioState) return;
        this.audioState.volume = volume;
        
        // Apply to any active audio elements
        const iframes = document.querySelectorAll('iframe[src*="youtube"]');
        iframes.forEach(iframe => {
            try {
                iframe.contentWindow.postMessage(JSON.stringify({
                    event: 'command',
                    func: 'setVolume',
                    args: [volume * 100]
                }), '*');
            } catch (e) {}
        });
        
        // Note: Browser TTS volume is set per utterance
    }
    
    skipCurrentAudio() {
        const source = this.audioState?.currentSource;
        
        if (source === 'speech' || source === 'ai-voice') {
            // Stop current speech
            if (this.speechSynthesis) {
                this.speechSynthesis.cancel();
            }
            this.hideAudioControlPanel();
        } else if (source === 'music') {
            // Skip to next track
            if (window.ytNext) {
                window.ytNext();
            }
        }
    }
    
    stopAllAudio() {
        // Stop speech synthesis
        if (this.speechSynthesis) {
            this.speechSynthesis.cancel();
        }
        
        // Stop music (pause YouTube)
        const ytPlayer = document.querySelector('iframe[src*="youtube"]');
        if (ytPlayer) {
            try {
                ytPlayer.contentWindow.postMessage(JSON.stringify({
                    event: 'command',
                    func: 'pauseVideo',
                    args: []
                }), '*');
            } catch (e) {}
        }
        
        // Set global mute flag
        this.globalMuted = true;
        
        // Hide control panel
        this.hideAudioControlPanel();
        
        console.log('🔇 All audio stopped');
    }
    
    // Legacy method compatibility
    showStopSpeechButton() {
        this.showAudioControlPanel('speech', 'Speaking...');
    }
    
    hideStopSpeechButton() {
        this.hideAudioControlPanel();
    }
    
    renderAIChat() {
        const container = document.getElementById('ai-chat-messages');
        if (!container) return;
        
        if (this.aiMessages.length === 0) {
            container.innerHTML = `
                <div class="text-center py-8 text-gray-400">
                    <p>Start a conversation with your AI assistant</p>
                    <p class="text-xs mt-2">Powered by ${this.userProfile?.preferred_name ? this.userProfile.preferred_name + "'s" : 'your'} personalized profile</p>
                </div>
            `;
            return;
        }
        
        const html = this.aiMessages.map((msg, index) => {
            if (msg.role === 'user') {
                return `
                    <div class="text-right">
                        <div class="inline-block max-w-[80%] bg-blue-600 rounded-lg px-4 py-2">
                            <p class="text-sm">${this.escapeHtml(msg.content)}</p>
                        </div>
                    </div>
                `;
            } else if (msg.role === 'status') {
                // Status messages: small, gray, italic with emoji
                return `
                    <div class="text-left">
                        <div class="inline-block max-w-[80%] bg-gray-800/50 rounded-lg px-3 py-1.5 border border-gray-700/50">
                            <p class="text-xs text-gray-400 italic">${this.escapeHtml(msg.content)}</p>
                        </div>
                    </div>
                `;
            } else {
                // Assistant messages: render markdown for proper formatting
                return `
                    <div class="text-left">
                        <div class="inline-block max-w-[80%] bg-gray-700 rounded-lg px-4 py-2 ai-message-content">
                            <div class="text-sm prose prose-invert prose-sm max-w-none">${this.renderMarkdown(msg.content)}</div>
                            ${msg.id ? `
                                <div class="flex gap-2 mt-2 pt-2 border-t border-gray-600">
                                    <button onclick="dataLoader.rateAIMessage('${msg.id}', '${msg.conversation_id}', 'thumbs_up')" 
                                            class="text-xs px-2 py-1 bg-gray-600 hover:bg-green-600 rounded">
                                        👍 Helpful
                                    </button>
                                    <button onclick="dataLoader.rateAIMessage('${msg.id}', '${msg.conversation_id}', 'thumbs_down')" 
                                            class="text-xs px-2 py-1 bg-gray-600 hover:bg-red-600 rounded">
                                        👎 Not Helpful
                                    </button>
                                </div>
                            ` : ''}
                        </div>
                    </div>
                `;
            }
        }).join('');
        
        container.innerHTML = html;
        container.scrollTop = container.scrollHeight;
    }
    
    async rateAIMessage(messageId, conversationId, feedbackType) {
        try {
            const response = await fetch('/api/ai/message/feedback', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    message_id: messageId,
                    conversation_id: conversationId,
                    feedback_type: feedbackType
                })
            });
            
            if (response.ok) {
                this.showNotification(`Feedback recorded: ${feedbackType === 'thumbs_up' ? '👍 Helpful' : '👎 Not Helpful'}`, 'success');
            }
        } catch (error) {
            console.error('Error rating message:', error);
        }
    }
    
    async loadUserProfile() {
        try {
            const response = await fetch('/api/user/profile');
            if (response.ok) {
                this.userProfile = await response.json();
                console.log('User profile loaded:', this.userProfile);
            }
        } catch (error) {
            console.error('Error loading user profile:', error);
        }
    }
    
    async saveUserProfile(profile) {
        try {
            const response = await fetch('/api/user/profile', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(profile)
            });
            
            if (response.ok) {
                this.userProfile = profile;
                this.showNotification('Profile saved successfully!', 'success');
            }
        } catch (error) {
            console.error('Error saving user profile:', error);
            this.showNotification('Failed to save profile', 'error');
        }
    }

    getActiveAssistant() {
        if (!this.aiAssistants || this.aiAssistants.length === 0) return null;
        return this.aiAssistants.find(a => a.id === this.activeAssistantId) || this.aiAssistants[0];
    }

    async loadAIAssistants() {
        try {
            const response = await fetch('/api/ai/assistants');
            const data = await response.json();
            if (!data.success) return;

            this.aiAssistants = data.assistants || [];
            this.activeAssistantId = data.active_assistant_id || (this.aiAssistants[0] && this.aiAssistants[0].id);
            this.renderAIAssistantEditor();
        } catch (error) {
            console.error('Error loading AI assistants:', error);
        }
    }

    async loadAIMemory() {
        const status = document.getElementById('ai-memory-status');

        try {
            if (status) status.textContent = 'Loading memory...';

            const response = await fetch('/api/ai/memory');
            const data = await response.json();
            if (!data.success) {
                if (status) status.textContent = data.error || 'Failed to load memory';
                return;
            }

            this.aiMemory = data.memory || { long_term: '', short_term: '' };

            const longTermInput = document.getElementById('ai-long-term-memory');
            const shortTermInput = document.getElementById('ai-short-term-memory');

            if (longTermInput) longTermInput.value = this.aiMemory.long_term || '';
            if (shortTermInput) shortTermInput.value = this.aiMemory.short_term || '';
            if (status) status.textContent = 'Memory loaded.';
        } catch (error) {
            console.error('Error loading AI memory:', error);
            if (status) status.textContent = 'Failed to load memory';
        }
    }

    async saveAIMemory(memoryType) {
        const inputId = memoryType === 'long_term' ? 'ai-long-term-memory' : 'ai-short-term-memory';
        const input = document.getElementById(inputId);
        const status = document.getElementById('ai-memory-status');
        const content = input?.value?.trim();

        if (!content) {
            this.showNotification('Memory content cannot be empty', 'error');
            return;
        }

        try {
            if (status) status.textContent = `Saving ${memoryType.replace('_', ' ')}...`;

            const response = await fetch('/api/ai/memory', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ memory_type: memoryType, content })
            });
            const data = await response.json();

            if (!data.success) {
                throw new Error(data.error || 'Failed to save memory');
            }

            this.aiMemory = data.memory || this.aiMemory;
            const longTermInput = document.getElementById('ai-long-term-memory');
            const shortTermInput = document.getElementById('ai-short-term-memory');
            if (longTermInput) longTermInput.value = this.aiMemory.long_term || '';
            if (shortTermInput) shortTermInput.value = this.aiMemory.short_term || '';

            if (status) status.textContent = data.message || 'Memory saved.';
            this.showNotification(data.message || 'Memory saved', 'success');
        } catch (error) {
            console.error('Error saving AI memory:', error);
            if (status) status.textContent = error.message || 'Failed to save memory';
            this.showNotification(error.message || 'Failed to save memory', 'error');
        }
    }

    async clearAIMemory(memoryType) {
        if (!confirm(`Reset ${memoryType.replace('_', ' ')} memory?`)) {
            return;
        }

        const status = document.getElementById('ai-memory-status');

        try {
            if (status) status.textContent = `Resetting ${memoryType.replace('_', ' ')}...`;

            const response = await fetch('/api/ai/memory/clear', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ memory_type: memoryType })
            });
            const data = await response.json();

            if (!data.success) {
                throw new Error(data.error || 'Failed to reset memory');
            }

            this.aiMemory = data.memory || this.aiMemory;
            const longTermInput = document.getElementById('ai-long-term-memory');
            const shortTermInput = document.getElementById('ai-short-term-memory');
            if (longTermInput) longTermInput.value = this.aiMemory.long_term || '';
            if (shortTermInput) shortTermInput.value = this.aiMemory.short_term || '';

            if (status) status.textContent = data.message || 'Memory reset.';
            this.showNotification(data.message || 'Memory reset', 'success');
        } catch (error) {
            console.error('Error resetting AI memory:', error);
            if (status) status.textContent = error.message || 'Failed to reset memory';
            this.showNotification(error.message || 'Failed to reset memory', 'error');
        }
    }

    renderAIAssistantEditor() {
        const selector = document.getElementById('ai-assistant-selector');
        if (!selector) return;

        selector.innerHTML = this.aiAssistants.map(a => {
            const selected = a.id === this.activeAssistantId ? 'selected' : '';
            return `<option value="${a.id}" ${selected}>${this.escapeHtml(a.name || 'Assistant')}</option>`;
        }).join('');

        const active = this.getActiveAssistant();
        if (!active) return;

        const nameInput = document.getElementById('ai-assistant-name');
        const personalityInput = document.getElementById('ai-assistant-personality');
        const taglineInput = document.getElementById('ai-assistant-tagline');
        const keyPhrasesInput = document.getElementById('ai-assistant-key-phrases');
        const signatureInput = document.getElementById('ai-assistant-signature');
        const voiceStyleInput = document.getElementById('ai-assistant-voice-style');
        const voiceModelInput = document.getElementById('ai-assistant-voice-model');
        const voiceSpeedInput = document.getElementById('ai-assistant-voice-speed');
        const voicePitchInput = document.getElementById('ai-assistant-voice-pitch');
        const signatureCheckbox = document.querySelector('input[onchange*="setVoiceSignature"]');
        const status = document.getElementById('ai-assistant-status');

        if (nameInput) nameInput.value = active.name || '';
        if (personalityInput) personalityInput.value = active.personality || '';
        if (taglineInput) taglineInput.value = active.tagline || '';
        if (keyPhrasesInput) keyPhrasesInput.value = (active.key_phrases || []).join(', ');
        if (signatureInput) signatureInput.value = active.signature_phrase || 'roger, roger';
        if (voiceStyleInput) voiceStyleInput.value = active.voice_style || 'droid';
        if (voiceModelInput) voiceModelInput.value = active.voice_model || 'auto';
        if (voiceSpeedInput) voiceSpeedInput.value = Number(active.voice_speed ?? 0.75).toFixed(2);
        if (voicePitchInput) voicePitchInput.value = Number(active.voice_pitch ?? 0.85).toFixed(2);
        if (signatureCheckbox) signatureCheckbox.checked = active.signature_enabled ?? true;
        if (status) status.textContent = `Active: ${active.name}`;

        // Update global state from loaded assistant
        if (active.signature_enabled !== undefined) {
            this.voiceSignatureEnabled = active.signature_enabled;
            localStorage.setItem('voiceSignatureEnabled', active.signature_enabled);
        }
        if (active.browser_voice) {
            this.selectedVoice = active.browser_voice;
            localStorage.setItem('selectedVoice', this.selectedVoice);
        }
    }

    async selectAIAssistant(assistantId) {
        try {
            const response = await fetch('/api/ai/assistants/select', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ assistant_id: assistantId })
            });
            const data = await response.json();
            if (!data.success) {
                this.showNotification(data.error || 'Failed to select assistant', 'error');
                return;
            }

            this.activeAssistantId = assistantId;
            this.renderAIAssistantEditor();
            this.showNotification('Assistant switched', 'success');
        } catch (error) {
            console.error('Error selecting assistant:', error);
        }
    }

    createAIAssistant() {
        const nameInput = document.getElementById('ai-assistant-name');
        const personalityInput = document.getElementById('ai-assistant-personality');
        const taglineInput = document.getElementById('ai-assistant-tagline');
        const keyPhrasesInput = document.getElementById('ai-assistant-key-phrases');
        const signatureInput = document.getElementById('ai-assistant-signature');
        const voiceStyleInput = document.getElementById('ai-assistant-voice-style');
        const voiceModelInput = document.getElementById('ai-assistant-voice-model');
        const voiceSpeedInput = document.getElementById('ai-assistant-voice-speed');
        const voicePitchInput = document.getElementById('ai-assistant-voice-pitch');

        if (nameInput) nameInput.value = 'New Assistant';
        if (personalityInput) personalityInput.value = 'Helpful, concise, personalized';
        if (taglineInput) taglineInput.value = '';
        if (keyPhrasesInput) keyPhrasesInput.value = '';
        if (signatureInput) signatureInput.value = 'roger, roger';
        if (voiceStyleInput) voiceStyleInput.value = 'droid';
        if (voiceModelInput) voiceModelInput.value = 'auto';
        if (voiceSpeedInput) voiceSpeedInput.value = '0.75';
        if (voicePitchInput) voicePitchInput.value = '0.85';

        const status = document.getElementById('ai-assistant-status');
        if (status) status.textContent = 'Creating a new assistant profile... click Save';
    }

    async saveAIAssistant() {
        const active = this.getActiveAssistant();
        const signatureCheckbox = document.querySelector('input[onchange*=\"setVoiceSignature\"]');
        
        const payload = {
            id: active ? active.id : undefined,
            name: (document.getElementById('ai-assistant-name')?.value || '').trim(),
            personality: (document.getElementById('ai-assistant-personality')?.value || '').trim(),
            tagline: (document.getElementById('ai-assistant-tagline')?.value || '').trim(),
            key_phrases: (document.getElementById('ai-assistant-key-phrases')?.value || '').trim(),
            signature_phrase: (document.getElementById('ai-assistant-signature')?.value || '').trim(),
            voice_style: document.getElementById('ai-assistant-voice-style')?.value || 'droid',
            voice_model: document.getElementById('ai-assistant-voice-model')?.value || 'auto',
            voice_speed: parseFloat(document.getElementById('ai-assistant-voice-speed')?.value || '0.75'),
            voice_pitch: parseFloat(document.getElementById('ai-assistant-voice-pitch')?.value || '0.85'),
            signature_enabled: signatureCheckbox?.checked ?? this.voiceSignatureEnabled ?? true,
            browser_voice: this.selectedVoice || 'rogr'
        };

        if (!payload.name) {
            this.showNotification('Assistant name is required', 'error');
            return;
        }

        try {
            const response = await fetch('/api/ai/assistants/save', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ assistant: payload })
            });
            const data = await response.json();
            if (!data.success) {
                this.showNotification(data.error || 'Failed to save assistant', 'error');
                return;
            }

            // Update global state
            this.voiceSignatureEnabled = payload.signature_enabled;
            localStorage.setItem('voiceSignatureEnabled', payload.signature_enabled);
            if (payload.browser_voice) {
                this.selectedVoice = payload.browser_voice;
                localStorage.setItem('selectedVoice', this.selectedVoice);
            }

            await this.loadAIAssistants();
            if (data.assistant && data.assistant.id) {
                await this.selectAIAssistant(data.assistant.id);
            }
            this.showNotification('✓ Assistant saved successfully', 'success');
        } catch (error) {
            console.error('Error saving assistant:', error);
            this.showNotification('Failed to save assistant', 'error');
        }
    }

    async deleteAIAssistant() {
        const active = this.getActiveAssistant();
        if (!active) return;

        if (!confirm(`Delete assistant "${active.name}"?`)) {
            return;
        }

        try {
            const response = await fetch(`/api/ai/assistants/${encodeURIComponent(active.id)}`, {
                method: 'DELETE'
            });
            const data = await response.json();
            if (!data.success) {
                this.showNotification(data.error || 'Failed to delete assistant', 'error');
                return;
            }

            await this.loadAIAssistants();
            this.showNotification('Assistant deleted', 'success');
        } catch (error) {
            console.error('Error deleting assistant:', error);
            this.showNotification('Failed to delete assistant', 'error');
        }
    }

    testAIAssistantVoice() {
        const assistant = this.getActiveAssistant();
        const phrase = assistant?.tagline || 'Voice check complete.';
        this.speakText(phrase, !!assistant?.signature_enabled);
    }
    
    showUserProfileModal() {
        const profile = this.userProfile || {};
        
        const modal = document.createElement('div');
        modal.id = 'user-profile-modal';
        modal.className = 'fixed inset-0 bg-black bg-opacity-75 flex items-center justify-center z-50 modal-backdrop';
        modal.innerHTML = `
            <div class="bg-gray-800 rounded-xl p-8 max-w-2xl w-full mx-4 max-h-[90vh] overflow-y-auto modal-content">
                <div class="flex justify-between items-center mb-6">
                    <h2 class="text-2xl font-bold">Your AI Profile</h2>
                    <button onclick="document.getElementById('user-profile-modal').remove()" 
                            class="text-gray-400 hover:text-white text-2xl">&times;</button>
                </div>
                
                <p class="text-sm text-gray-400 mb-6">
                    Help the AI assistant understand you better by providing context about yourself, 
                    your work, and preferences. This information will be used to personalize responses.
                </p>
                
                <form id="profile-form" class="space-y-4">
                    <div>
                        <label class="block text-sm font-medium mb-2">Full Name</label>
                        <input type="text" name="full_name" value="${profile.full_name || ''}" 
                               class="w-full bg-gray-700 border border-gray-600 rounded px-3 py-2">
                    </div>
                    
                    <div>
                        <label class="block text-sm font-medium mb-2">Preferred Name</label>
                        <input type="text" name="preferred_name" value="${profile.preferred_name || ''}" 
                               class="w-full bg-gray-700 border border-gray-600 rounded px-3 py-2">
                    </div>
                    
                    <div class="grid grid-cols-2 gap-4">
                        <div>
                            <label class="block text-sm font-medium mb-2">Role/Title</label>
                            <input type="text" name="role" value="${profile.role || ''}" 
                                   class="w-full bg-gray-700 border border-gray-600 rounded px-3 py-2">
                        </div>
                        <div>
                            <label class="block text-sm font-medium mb-2">Company</label>
                            <input type="text" name="company" value="${profile.company || ''}" 
                                   class="w-full bg-gray-700 border border-gray-600 rounded px-3 py-2">
                        </div>
                    </div>
                    
                    <div>
                        <label class="block text-sm font-medium mb-2">Work Focus</label>
                        <input type="text" name="work_focus" value="${profile.work_focus || ''}" 
                               placeholder="e.g., Software Development, Marketing, Product Management"
                               class="w-full bg-gray-700 border border-gray-600 rounded px-3 py-2">
                    </div>
                    
                    <div>
                        <label class="block text-sm font-medium mb-2">Interests</label>
                        <input type="text" name="interests" value="${profile.interests || ''}" 
                               placeholder="e.g., AI, Music, Technology, Sports"
                               class="w-full bg-gray-700 border border-gray-600 rounded px-3 py-2">
                    </div>
                    
                    <div>
                        <label class="block text-sm font-medium mb-2">Communication Style</label>
                        <select name="communication_style" 
                                class="w-full bg-gray-700 border border-gray-600 rounded px-3 py-2">
                            <option value="Professional and formal" ${profile.communication_style === 'Professional and formal' ? 'selected' : ''}>Professional and formal</option>
                            <option value="Professional and friendly" ${!profile.communication_style || profile.communication_style === 'Professional and friendly' ? 'selected' : ''}>Professional and friendly</option>
                            <option value="Casual and conversational" ${profile.communication_style === 'Casual and conversational' ? 'selected' : ''}>Casual and conversational</option>
                            <option value="Direct and concise" ${profile.communication_style === 'Direct and concise' ? 'selected' : ''}>Direct and concise</option>
                        </select>
                    </div>
                    
                    <div>
                        <label class="block text-sm font-medium mb-2">Work Hours</label>
                        <input type="text" name="work_hours" value="${profile.work_hours || ''}" 
                               placeholder="e.g., 9am-5pm EST, Flexible"
                               class="w-full bg-gray-700 border border-gray-600 rounded px-3 py-2">
                    </div>
                    
                    <div>
                        <label class="block text-sm font-medium mb-2">Current Priorities</label>
                        <textarea name="priorities" rows="3" 
                                  placeholder="What are you focusing on right now?"
                                  class="w-full bg-gray-700 border border-gray-600 rounded px-3 py-2">${profile.priorities || ''}</textarea>
                    </div>
                    
                    <div>
                        <label class="block text-sm font-medium mb-2">Bio / Context</label>
                        <textarea name="bio" rows="4" 
                                  placeholder="Anything else the AI should know about you?"
                                  class="w-full bg-gray-700 border border-gray-600 rounded px-3 py-2">${profile.bio || ''}</textarea>
                    </div>
                    
                    <div class="flex gap-3 pt-4">
                        <button type="submit" 
                                class="flex-1 bg-purple-600 hover:bg-purple-700 px-6 py-3 rounded-lg font-semibold">
                            Save Profile
                        </button>
                        <button type="button" 
                                onclick="document.getElementById('user-profile-modal').remove()"
                                class="bg-gray-600 hover:bg-gray-700 px-6 py-3 rounded-lg">
                            Cancel
                        </button>
                    </div>
                </form>
            </div>
        `;
        
        document.body.appendChild(modal);
        
        // Handle form submission
        document.getElementById('profile-form').onsubmit = async (e) => {
            e.preventDefault();
            const formData = new FormData(e.target);
            const profile = Object.fromEntries(formData.entries());
            await this.saveUserProfile(profile);
            modal.remove();
        };
    }
    
    toggleAIVoice() {
        this.aiVoiceEnabled = !this.aiVoiceEnabled;
        
        // Persist the setting
        localStorage.setItem('aiVoiceEnabled', this.aiVoiceEnabled);
        
        // Stop any currently speaking text
        if (!this.aiVoiceEnabled && this.speechSynthesis && this.speechSynthesis.speaking) {
            this.speechSynthesis.cancel();
        }
        
        const btn = document.getElementById('ai-voice-toggle');
        if (btn) {
            btn.textContent = this.aiVoiceEnabled ? '🔊 Voice On' : '🔇 Voice Off';
            btn.className = this.aiVoiceEnabled ? 
                'bg-purple-600 hover:bg-purple-700 px-4 py-2 rounded-lg text-sm' : 
                'bg-gray-600 hover:bg-gray-700 px-4 py-2 rounded-lg text-sm';
        }
        
        // Show notification
        this.showNotification(
            this.aiVoiceEnabled ? 'Voice responses enabled' : 'Voice responses muted',
            'info'
        );
    }
    
    toggleGlobalMute() {
        this.globalMuted = !this.globalMuted;
        
        // Persist the setting
        localStorage.setItem('globalMuted', this.globalMuted);
        
        // Stop any currently speaking text
        if (this.globalMuted && this.speechSynthesis && this.speechSynthesis.speaking) {
            this.speechSynthesis.cancel();
            this.hideStopSpeechButton();
        }
        
        // Update button UI
        const iconEl = document.getElementById('mute-icon');
        const textEl = document.getElementById('mute-text');
        const btnEl = document.getElementById('global-mute-btn');
        
        if (iconEl && textEl && btnEl) {
            if (this.globalMuted) {
                iconEl.textContent = '🔇';
                textEl.textContent = 'Voice Alerts Off';
                btnEl.className = 'mt-2 w-full flex items-center justify-center gap-2 px-4 py-2 bg-gray-600 hover:bg-gray-700 text-white text-sm font-medium rounded-lg transition-colors shadow-lg';
            } else {
                iconEl.textContent = '🔊';
                textEl.textContent = 'Voice Alerts On';
                btnEl.className = 'mt-2 w-full flex items-center justify-center gap-2 px-4 py-2 bg-purple-600 hover:bg-purple-700 text-white text-sm font-medium rounded-lg transition-colors shadow-lg';
            }
        }
        
        // Show notification
        this.showNotification(
            this.globalMuted ? '🔇 All voice alerts muted' : '🔊 Voice alerts enabled',
            'info'
        );
    }
    
    startVoicePrompt() {
        if (!this.voiceRecognition) {
            alert('Voice recognition is not supported in your browser.');
            return;
        }
        
        const btn = document.getElementById('ai-voice-prompt');
        if (btn) {
            btn.textContent = '🎤 Listening...';
            btn.classList.add('animate-pulse');
        }
        
        this.voiceRecognition.onresult = (event) => {
            const transcript = event.results[0][0].transcript;
            const input = document.getElementById('ai-chat-input');
            if (input) {
                input.value = transcript;
                this.sendAIMessage();
            }
            
            if (btn) {
                btn.textContent = '🎤 Voice Prompt';
                btn.classList.remove('animate-pulse');
            }
        };
        
        this.voiceRecognition.onerror = (event) => {
            console.error('Voice recognition error:', event.error);
            if (btn) {
                btn.textContent = '🎤 Voice Prompt';
                btn.classList.remove('animate-pulse');
            }
        };
        
        this.voiceRecognition.start();
    }
    
    // VANITY ALERTS
    async loadVanityAlerts() {
        this.setSectionLoading('vanity-grid', 'Loading vanity alerts...');
        try {
            const response = await this.fetchJsonWithTimeout('/api/vanity-alerts', {}, 12000);
            if (!response.ok) {
                this.vanityAlerts = [];
                this.renderVanityAlerts();
                return;
            }

            const data = await response.json();
            this.vanityAlerts = data.alerts || [];

            if (!this.vanityAlerts.length) {
                try {
                    const fallbackResponse = await fetch('/api/vanity');
                    if (fallbackResponse.ok) {
                        const fallbackData = await fallbackResponse.json();
                        this.vanityAlerts = fallbackData.alerts || [];
                    }
                } catch (fallbackError) {
                    console.warn('Vanity fallback fetch failed:', fallbackError);
                }
            }

            this.renderVanityAlerts();
        } catch (error) {
            console.error('Error loading vanity alerts:', error);
            this.vanityAlerts = [];
            this.setSectionError('vanity-grid', this.getLoadErrorMessage('Unable to load vanity alerts right now.', error));
        }
    }
    
    renderVanityAlerts() {
        const grid = document.getElementById('vanity-grid');
        if (!grid) return;
        
        if (this.vanityAlerts.length === 0) {
            grid.innerHTML = `
                <div class="col-span-full text-center py-12">
                    <div class="text-6xl mb-4">🔔</div>
                    <h3 class="text-xl font-semibold mb-2">No Alerts</h3>
                    <p class="text-gray-400">No brand mentions or alerts found</p>
                </div>
            `;
            return;
        }
        
        const html = this.vanityAlerts.map(alert => {
            const feedback = this.feedbackData[`vanity-${alert.id}`] || null;
            return `
            <div class="bg-gray-800 rounded-xl p-6 border border-gray-700 relative">
                <button onclick="dataLoader.dismissAlert('${alert.id}')" 
                        class="absolute top-2 right-2 text-gray-400 hover:text-white px-2 py-1 rounded hover:bg-gray-700" 
                        title="Dismiss">✕</button>
                <div class="flex items-start gap-3 mb-3">
                    <span class="text-3xl">${this.getAlertIcon(alert.type)}</span>
                    <div class="flex-1">
                        <h3 class="font-semibold text-white mb-1">${this.escapeHtml(alert.title)}</h3>
                        <p class="text-sm text-gray-400 mb-2">${this.escapeHtml(alert.description || '')}</p>
                        <div class="flex gap-2 text-xs">
                            ${alert.source ? `<span class="bg-purple-600 px-2 py-1 rounded">${this.escapeHtml(alert.source)}</span>` : ''}
                            ${alert.url ? `<a href="${alert.url}" target="_blank" class="text-blue-400 hover:underline">View →</a>` : ''}
                        </div>
                    </div>
                </div>
                <div class="flex gap-1 pt-3 border-t border-gray-700">
                    <button onclick="dataLoader.giveFeedback('vanity', '${alert.id}', 'up')" 
                            class="feedback-btn px-2 py-1 rounded text-xs ${feedback === 'up' ? 'bg-green-600' : 'bg-gray-700 hover:bg-green-600'}" 
                            title="Important">👍</button>
                    <button onclick="dataLoader.giveFeedback('vanity', '${alert.id}', 'neutral')" 
                            class="feedback-btn px-2 py-1 rounded text-xs ${feedback === 'neutral' ? 'bg-blue-600' : 'bg-gray-700 hover:bg-blue-600'}" 
                            title="Neutral">👌</button>
                    <button onclick="dataLoader.giveFeedback('vanity', '${alert.id}', 'down')" 
                            class="feedback-btn px-2 py-1 rounded text-xs ${feedback === 'down' ? 'bg-red-600' : 'bg-gray-700 hover:bg-red-600'}" 
                            title="Not relevant">👎</button>
                </div>
            </div>
        `;
        }).join('');
        
        grid.innerHTML = html;
    }
    
    getAlertIcon(type) {
        const icons = {
            'mention': '💬',
            'social': '📱',
            'web': '🌐',
            'press': '📰',
            'review': '⭐',
            'default': '🔔'
        };
        return icons[type] || icons.default;
    }
    
    getItemTypeIcon(type) {
        const icons = {
            'todo': '✅',
            'Task': '✅',
            'event': '📅',
            'Event': '📅',
            'email': '📧',
            'Email': '📧',
            'news': '📰',
            'News': '📰',
            'suggestion': '💡',
            'vanity': '🔔',
            'music': '🎵',
            'default': '⭐'
        };
        return icons[type] || icons.default;
    }
    
    // LIKED ITEMS
    async loadLikedItems() {
        try {
            const response = await fetch('/api/liked-items');
            if (response.ok) {
                const data = await response.json();
                this.renderLikedItemsFromDB(data.liked_items || []);
                return;
            }
        } catch (error) {
            console.error('Error loading liked items from database:', error);
        }
        
        // Fallback to localStorage if API fails
        this.renderLikedItemsFromStorage();
    }
    
    renderLikedItemsFromDB(likedItems) {
        const grid = document.getElementById('liked-grid');
        if (!grid) return;
        
        if (likedItems.length === 0) {
            grid.innerHTML = `
                <div class="col-span-full text-center py-12">
                    <div class="text-6xl mb-4">❤️</div>
                    <h3 class="text-xl font-semibold mb-2">No Liked Items</h3>
                    <p class="text-gray-400">Start giving thumbs up to items you like!</p>
                </div>
            `;
            return;
        }
        
        const html = likedItems.map(item => `
            <div class="bg-gray-800 rounded-xl p-6 border border-gray-700">
                <div class="flex items-start gap-3">
                    <span class="text-3xl">${this.getItemTypeIcon(item.item_type)}</span>
                    <div class="flex-1">
                        <span class="text-xs text-purple-400 mb-1 block">${item.item_type}</span>
                        <h3 class="font-semibold text-white mb-1">${this.escapeHtml(item.title || item.item_details?.title || 'Liked Item')}</h3>
                        ${item.description || item.item_details?.description ? `<p class="text-sm text-gray-400">${this.escapeHtml(item.description || item.item_details?.description)}</p>` : ''}
                        <p class="text-xs text-gray-500 mt-2">${this.formatDate(item.created_at)}</p>
                    </div>
                </div>
            </div>
        `).join('');
        
        grid.innerHTML = html;
    }
    
    renderLikedItemsFromStorage() {
        const grid = document.getElementById('liked-grid');
        if (!grid) return;
        
        const likedItems = [];
        
        // Collect all items marked with thumbs up
        Object.entries(this.feedbackData).forEach(([key, sentiment]) => {
            if (sentiment === 'up') {
                const [type, id] = key.split('-');
                let item = null;
                
                switch(type) {
                    case 'todo':
                        item = this.todos.find(t => t.id === id);
                        if (item) likedItems.push({ type: 'Task', icon: '✅', title: item.title, description: item.description, id: key });
                        break;
                    case 'event':
                        item = this.calendar.find(e => e.event_id === id);
                        if (item) likedItems.push({ type: 'Event', icon: '📅', title: item.summary || item.title, description: item.location, id: key });
                        break;
                    case 'email':
                        item = this.emails.find(e => e.id === id);
                        if (item) likedItems.push({ type: 'Email', icon: '📧', title: item.subject, description: item.sender, id: key });
                        break;
                    case 'news':
                        item = this.news.find(n => n.id === id);
                        if (item) likedItems.push({ type: 'News', icon: '📰', title: item.title, description: item.source, id: key });
                        break;
                }
            }
        });
        
        if (likedItems.length === 0) {
            grid.innerHTML = `
                <div class="col-span-full text-center py-12">
                    <div class="text-6xl mb-4">❤️</div>
                    <h3 class="text-xl font-semibold mb-2">No Liked Items</h3>
                    <p class="text-gray-400">Start giving thumbs up to items you like!</p>
                </div>
            `;
            return;
        }
        
        const html = likedItems.map(item => `
            <div class="bg-gray-800 rounded-xl p-6 border border-gray-700">
                <div class="flex items-start gap-3">
                    <span class="text-3xl">${item.icon}</span>
                    <div class="flex-1">
                        <span class="text-xs text-purple-400 mb-1 block">${item.type}</span>
                        <h3 class="font-semibold text-white mb-1">${this.escapeHtml(item.title)}</h3>
                        ${item.description ? `<p class="text-sm text-gray-400">${this.escapeHtml(item.description)}</p>` : ''}
                    </div>
                </div>
            </div>
        `).join('');
        
        grid.innerHTML = html;
    }
    
    // MUSIC NEWS
    async loadMusicNews() {
        this.setSectionLoading('music-grid', 'Loading music updates...');
        try {
            const response = await this.fetchJsonWithTimeout('/api/music', {}, 12000);
            if (response.ok) {
                const data = await response.json();
                // Combine all music-related data into one array
                const allMusic = [];
                
                // Add streaming stats/tracks
                if (data.tracks && data.tracks.length > 0) {
                    allMusic.push(...data.tracks.map(track => ({
                        id: `track-${track.platform}-${Date.now()}`,
                        title: track.title,
                        artist: track.artist,
                        description: track.trending_tracks ? `Trending: ${track.trending_tracks.slice(0, 3).join(', ')}` : '',
                        type: 'streaming',
                        platform: track.platform,
                        plays: track.plays,
                        followers: track.followers
                    })));
                }
                
                // Add music news articles
                if (data.music_news && data.music_news.length > 0) {
                    allMusic.push(...data.music_news.map(article => ({
                        id: `news-${article.url}`,
                        title: article.title,
                        artist: article.source,
                        description: article.snippet,
                        type: 'news',
                        url: article.url,
                        release_date: article.published_date
                    })));
                }
                
                // Add label mentions
                if (data.label_mentions && data.label_mentions.length > 0) {
                    allMusic.push(...data.label_mentions.slice(0, 5).map(mention => ({
                        id: `label-${mention.url}`,
                        title: `Null Records mentioned on ${mention.platform}`,
                        artist: mention.source || mention.platform,
                        description: mention.text,
                        type: 'mention',
                        url: mention.url,
                        engagement: mention.engagement,
                        release_date: mention.date
                    })));
                }
                
                // Add band mentions
                if (data.band_mentions && data.band_mentions.length > 0) {
                    allMusic.push(...data.band_mentions.slice(0, 5).map(mention => ({
                        id: `band-${mention.url}`,
                        title: `Artist mentioned on ${mention.platform}`,
                        artist: mention.source || mention.platform,
                        description: mention.text,
                        type: 'mention',
                        url: mention.url,
                        engagement: mention.engagement,
                        release_date: mention.date
                    })));
                }
                
                this.musicNews = allMusic;
                this.renderMusicNews();
                
                // Load music player data
                this.loadUnifiedLibrary();
                this.loadPlaylists();
            } else {
                this.setSectionError('music-grid', 'Unable to load music updates right now.');
            }
        } catch (error) {
            console.error('Error loading music news:', error);
            this.setSectionError('music-grid', this.getLoadErrorMessage('Unable to load music updates right now.', error));
        }
    }
    
    renderMusicNews() {
        const grid = document.getElementById('music-grid');
        if (!grid) return;
        
        if (this.musicNews.length === 0) {
            grid.innerHTML = `
                <div class="col-span-full text-center py-12">
                    <div class="text-6xl mb-4">🎵</div>
                    <h3 class="text-xl font-semibold mb-2">No Music News</h3>
                    <p class="text-gray-400">No music updates available</p>
                </div>
            `;
            return;
        }
        
        const html = this.musicNews.map(music => {
            const feedback = this.feedbackData[`music-${music.id}`] || null;
            const typeEmoji = {
                'streaming': '📊',
                'news': '📰',
                'mention': '💬',
                'release': '🎵'
            };
            
            return `
            <div class="bg-gray-750 rounded-lg p-4 border border-gray-600 ${music.url ? 'cursor-pointer hover:border-purple-500 transition-colors' : ''}"
                 ${music.url ? `onclick="window.open('${music.url}', '_blank')"` : ''}>
                <div class="flex items-start gap-3">
                    <span class="text-2xl">${typeEmoji[music.type] || '🎵'}</span>
                    <div class="flex-1 min-w-0">
                        <h4 class="font-semibold text-white text-sm mb-1 truncate">${this.escapeHtml(music.title)}</h4>
                        <p class="text-xs text-purple-400 mb-1">${this.escapeHtml(music.artist || '')}</p>
                        ${music.description ? `<p class="text-xs text-gray-400 line-clamp-2">${this.escapeHtml(music.description)}</p>` : ''}
                        <div class="flex gap-1 text-xs mt-2 flex-wrap">
                            ${music.type ? `<span class="bg-purple-600 px-2 py-0.5 rounded text-xs">${this.escapeHtml(music.type)}</span>` : ''}
                            ${music.platform ? `<span class="bg-blue-600 px-2 py-0.5 rounded text-xs">${this.escapeHtml(music.platform)}</span>` : ''}
                        </div>
                    </div>
                </div>
            </div>
        `;
        }).join('');
        
        grid.innerHTML = html;
    }
    
    // UNIVERSAL MUSIC PLAYER FUNCTIONS
    async connectService(service) {
        this.showNotification(`Connecting to ${service}...`, 'info');
        try {
            if (service === 'spotify') {
                // Redirect to Spotify OAuth
                window.location.href = '/api/music/oauth/spotify/login';
            } else if (service === 'apple') {
                // Initialize MusicKit JS for Apple Music
                await this.connectAppleMusic();
            } else if (service === 'amazon') {
                this.showNotification('Amazon Music integration coming soon!', 'info');
            }
        } catch (error) {
            console.error(`Error connecting to ${service}:`, error);
            this.showNotification(`Failed to connect to ${service}`, 'error');
        }
    }
    
    async connectAppleMusic() {
        try {
            // Get Apple Music configuration
            const response = await fetch('/api/music/oauth/apple/login');
            if (!response.ok) {
                throw new Error('Failed to get Apple Music configuration');
            }
            
            const config = await response.json();
            
            // Load MusicKit JS if not already loaded
            if (!window.MusicKit) {
                await this.loadMusicKitJS();
            }
            
            // Configure MusicKit
            await MusicKit.configure(config.music_kit_config);
            
            // Get the MusicKit instance
            const music = MusicKit.getInstance();
            
            // Authorize the user
            const userToken = await music.authorize();
            
            // Save the user token to backend
            const saveResponse = await fetch('/api/music/oauth/apple/callback', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ user_token: userToken })
            });
            
            if (saveResponse.ok) {
                this.showNotification('Apple Music connected successfully!', 'success');
                this.updateServiceStatus('apple', true);
            } else {
                throw new Error('Failed to save Apple Music token');
            }
        } catch (error) {
            console.error('Error connecting Apple Music:', error);
            this.showNotification('Failed to connect Apple Music', 'error');
        }
    }
    
    loadMusicKitJS() {
        return new Promise((resolve, reject) => {
            if (document.getElementById('musickit-js')) {
                resolve();
                return;
            }
            
            const script = document.createElement('script');
            script.id = 'musickit-js';
            script.src = 'https://js-cdn.music.apple.com/musickit/v3/musickit.js';
            script.onload = resolve;
            script.onerror = reject;
            document.head.appendChild(script);
        });
    }
    
    updateServiceStatus(service, connected) {
        const statusSpan = document.querySelector(`.${service}-status`);
        if (statusSpan) {
            statusSpan.textContent = connected ? 'Connected' : 'Not Connected';
            statusSpan.parentElement.style.color = connected ? '#10b981' : '#ef4444';
        }
    }
    
    async loadUnifiedLibrary() {
        this.setSectionLoading('unified-library', 'Loading library...');
        try {
            const response = await this.fetchJsonWithTimeout('/api/music/unified-library', {}, 12000);
            if (response.ok) {
                const data = await response.json();
                this.renderUnifiedLibrary(data.tracks || []);
            } else {
                this.setSectionError('unified-library', 'Unable to load music library right now.');
            }
        } catch (error) {
            console.error('Error loading unified library:', error);
            this.setSectionError('unified-library', this.getLoadErrorMessage('Unable to load music library right now.', error));
        }
    }
    
    renderUnifiedLibrary(tracks) {
        const container = document.getElementById('unified-library');
        if (!container) return;
        
        if (tracks.length === 0) {
            container.innerHTML = '<p class="text-gray-400 text-sm">No tracks found. Connect your music services first.</p>';
            return;
        }
        
        const html = tracks.slice(0, 20).map(track => `
            <div class="flex items-center gap-3 p-2 bg-gray-750 rounded hover:bg-gray-700 cursor-pointer transition"
                 onclick="dataLoader.playTrack('${track.id}', '${track.service}')">
                <span class="text-xl">🎵</span>
                <div class="flex-1 min-w-0">
                    <div class="text-sm font-medium truncate">${this.escapeHtml(track.title)}</div>
                    <div class="text-xs text-gray-400 truncate">${this.escapeHtml(track.artist)}</div>
                </div>
                <span class="service-badge text-xs px-2 py-1 bg-gray-600 rounded">${track.service}</span>
            </div>
        `).join('');
        
        container.innerHTML = html;
    }
    
    async createMoodPlaylist() {
        const mood = document.getElementById('mood-selector')?.value;
        const maxTracks = document.getElementById('mood-max-tracks')?.value || 30;
        const useAI = document.getElementById('use-ai-mood')?.checked || false;
        const artists = document.getElementById('mood-artists')?.value.split(',').map(a => a.trim()).filter(Boolean);
        const songs = document.getElementById('mood-songs')?.value.split(',').map(s => s.trim()).filter(Boolean);

        if (!mood) {
            this.showNotification('Please select a mood', 'error');
            return;
        }

        this.showNotification(`Creating ${mood} playlist...`, 'info');

        try {
            const payload = {
                mood,
                max_tracks: parseInt(maxTracks),
                use_ai: useAI
            };
            if (artists.length) payload.artists = artists;
            if (songs.length) payload.songs = songs;

            const response = await fetch('/api/music/playlist', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            if (response.ok) {
                const data = await response.json();
                this.showNotification(`Created ${mood} playlist with ${data.tracks.length} tracks!`, 'success');
                this.loadPlaylists();
            } else {
                this.showNotification('Failed to create playlist', 'error');
            }
        } catch (error) {
            console.error('Error creating mood playlist:', error);
            this.showNotification('Failed to create playlist', 'error');
        }
    }
    
    async createCustomPlaylist() {
        const genres = document.getElementById('custom-genres')?.value.split(',').map(g => g.trim()).filter(g => g);
        const artists = document.getElementById('custom-artists')?.value.split(',').map(a => a.trim()).filter(a => a);
        const minPop = parseInt(document.getElementById('custom-min-pop')?.value || 0);
        const maxPop = parseInt(document.getElementById('custom-max-pop')?.value || 100);
        
        if (!genres.length && !artists.length) {
            this.showNotification('Please specify at least one genre or artist', 'error');
            return;
        }
        
        this.showNotification('Creating custom playlist...', 'info');
        
        try {
            const response = await fetch('/api/music/create-custom-playlist', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    criteria: {
                        genres: genres,
                        artists: artists,
                        min_popularity: minPop,
                        max_popularity: maxPop
                    }
                })
            });
            
            if (response.ok) {
                const data = await response.json();
                this.showNotification(`Created custom playlist with ${data.tracks.length} tracks!`, 'success');
                this.loadPlaylists();
            }
        } catch (error) {
            console.error('Error creating custom playlist:', error);
            this.showNotification('Failed to create playlist', 'error');
        }
    }
    
    async loadPlaylists() {
        this.setSectionLoading('playlists-grid', 'Loading playlists...');
        try {
            const response = await this.fetchJsonWithTimeout('/api/music/playlists', {}, 12000);
            if (response.ok) {
                const data = await response.json();
                this.renderPlaylists(data.playlists || []);
            } else {
                this.setSectionError('playlists-grid', 'Unable to load playlists right now.');
            }
        } catch (error) {
            console.error('Error loading playlists:', error);
            this.setSectionError('playlists-grid', this.getLoadErrorMessage('Unable to load playlists right now.', error));
        }
    }
    
    renderPlaylists(playlists) {
        const grid = document.getElementById('playlists-grid');
        if (!grid) return;
        
        if (playlists.length === 0) {
            grid.innerHTML = '<p class="text-gray-400 col-span-full text-center">No playlists yet. Create one above!</p>';
            return;
        }
        
        const html = playlists.map(playlist => `
            <div class="bg-gray-750 rounded-lg p-4 border border-gray-600 hover:border-purple-500 transition cursor-pointer"
                 onclick="dataLoader.playPlaylist('${playlist.id}')">
                <div class="flex items-center gap-3 mb-3">
                    <span class="text-3xl">🎵</span>
                    <div class="flex-1 min-w-0">
                        <h4 class="font-semibold truncate">${this.escapeHtml(playlist.name)}</h4>
                        <p class="text-xs text-gray-400">${playlist.tracks.length} tracks</p>
                    </div>
                </div>
                <div class="flex gap-2 text-xs">
                    ${playlist.mood ? `<span class="bg-purple-600 px-2 py-1 rounded">${playlist.mood}</span>` : ''}
                    ${playlist.created_at ? `<span class="bg-gray-700 px-2 py-1 rounded">${this.formatDate(playlist.created_at)}</span>` : ''}
                </div>
            </div>
        `).join('');
        
        grid.innerHTML = html;
    }
    
    // Playback Controls (stubs for now - need actual player integration)
    playTrack(trackId, service) {
        const title = document.getElementById('now-playing-title');
        const artist = document.getElementById('now-playing-artist');
        const serviceBadge = document.getElementById('playing-service');
        
        if (title) title.textContent = `Playing track ${trackId}`;
        if (artist) artist.textContent = `from ${service}`;
        if (serviceBadge) {
            serviceBadge.textContent = service.toUpperCase();
            serviceBadge.className = 'service-badge bg-blue-600 px-2 py-1 rounded text-xs';
            serviceBadge.classList.remove('hidden');
        }
        
        const btn = document.getElementById('play-pause-btn');
        if (btn) btn.textContent = '⏸️';
        
        this.showNotification(`Playing track from ${service}`, 'info');
    }
    
    playPlaylist(playlistId) {
        // Find the playlist by ID
        fetch('/api/music/playlists')
            .then(res => res.json())
            .then(data => {
                const playlist = (data.playlists || []).find(pl => pl.id === playlistId);
                if (!playlist) {
                    this.showNotification('Playlist not found', 'error');
                    return;
                }
                
                // Use the YouTube player to load the playlist
                if (window.loadYouTubePlayer && playlist.tracks && playlist.tracks.length > 0) {
                    // Convert tracks to YouTube format
                    const ytTracks = playlist.tracks.map(t => ({
                        title: t.title,
                        artist: t.artist,
                        youtubeId: t.youtubeId || null
                    }));
                    window.loadYouTubePlayer(ytTracks, playlistId, playlist.name);
                    this.showNotification(`Playing playlist: ${playlist.name} (${playlist.tracks.length} tracks)`, 'info');
                } else {
                    this.showNotification('No tracks in playlist', 'warning');
                }
            })
            .catch(err => {
                console.error('Error playing playlist:', err);
                this.showNotification('Error loading playlist', 'error');
            });
    }
    
    togglePlay() {
        const btn = document.getElementById('play-pause-btn');
        if (!btn) return;
        
        const isPlaying = btn.textContent === '⏸️';
        btn.textContent = isPlaying ? '▶️' : '⏸️';
        this.showNotification(isPlaying ? 'Paused' : 'Playing', 'info');
    }
    
    previousTrack() {
        this.showNotification('Previous track', 'info');
    }
    
    nextTrack() {
        this.showNotification('Next track', 'info');
    }
    
    setVolume(value) {
        const display = document.getElementById('volume-display');
        if (display) display.textContent = `${value}%`;
    }
    
    // DASHBOARD EDIT MODE
    toggleEditMode() {
        this.editMode = !this.editMode;
        const btn = document.getElementById('edit-mode-btn');
        
        if (this.editMode) {
            if (btn) {
                btn.innerHTML = '<span>✅</span><span>Save Settings</span>';
                btn.className = 'w-full bg-green-600 hover:bg-green-700 px-4 py-2 rounded-lg text-sm flex items-center justify-center gap-2 mb-2';
            }
            this.showEditPanel();
        } else {
            if (btn) {
                btn.innerHTML = '<span>⚙️</span><span>Edit Dashboard</span>';
                btn.className = 'w-full bg-purple-600 hover:bg-purple-700 px-4 py-2 rounded-lg text-sm flex items-center justify-center gap-2 mb-2';
            }
            this.hideEditPanel();
            this.saveDashboardConfig();
            this.updateNavVisibility();
        }
    }
    
    showEditPanel() {
        const panel = document.createElement('div');
        panel.id = 'edit-panel';
        panel.className = 'fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4 overflow-y-auto';
        panel.onclick = (e) => {
            if (e.target === panel) this.hideEditPanel();
        };
        
        panel.innerHTML = `
            <div class="bg-gray-800 border border-gray-700 rounded-xl p-6 shadow-2xl max-w-2xl w-full my-8 max-h-[90vh] overflow-y-auto">
                <div class="flex items-center justify-between mb-4">
                    <h3 class="text-xl font-bold">Configure Dashboard</h3>
                    <button onclick="dataLoader.hideEditPanel()" 
                            class="text-gray-400 hover:text-white text-2xl leading-none">
                        ×
                    </button>
                </div>
                
                <p class="text-sm text-gray-400 mb-4">Customize your dashboard sections and settings</p>
                
                <div class="space-y-6">
                    <div>
                        <h4 class="text-lg font-semibold mb-3">Dashboard Sections</h4>
                        <div class="grid grid-cols-2 gap-2">
                            ${Object.entries(this.dashboardConfig).map(([key, enabled]) => `
                                <label class="flex items-center gap-2 p-2 rounded hover:bg-gray-700 cursor-pointer">
                                    <input type="checkbox" 
                                           ${enabled ? 'checked' : ''} 
                                           onchange="dataLoader.toggleSection('${key}')"
                                           class="w-4 h-4 rounded">
                                    <span class="text-sm capitalize">${key}</span>
                                </label>
                            `).join('')}
                        </div>
                    </div>
            
            <div class="border-t border-gray-700 pt-4 mb-4">
                <h4 class="text-lg font-semibold mb-3">Auto-Refresh Interval</h4>
                <p class="text-xs text-gray-400 mb-3">Automatically refresh data and generate overview prompts</p>
                <select onchange="dataLoader.setAutoRefreshInterval(this.value)" 
                        class="w-full bg-gray-700 border border-gray-600 rounded px-3 py-2 text-white">
                    <option value="0" ${this.autoRefreshInterval === 0 ? 'selected' : ''}>Disabled</option>
                    <option value="5" ${this.autoRefreshInterval === 5 ? 'selected' : ''}>Every 5 minutes</option>
                    <option value="15" ${this.autoRefreshInterval === 15 ? 'selected' : ''}>Every 15 minutes</option>
                    <option value="30" ${this.autoRefreshInterval === 30 ? 'selected' : ''}>Every 30 minutes</option>
                    <option value="60" ${this.autoRefreshInterval === 60 ? 'selected' : ''}>Every hour</option>
                </select>
            </div>
                    
                    <div class="border-t border-gray-700 pt-4">
                        <h4 class="text-lg font-semibold mb-3">Auto-Refresh Interval</h4>
                        <p class="text-xs text-gray-400 mb-3">Automatically refresh data and generate overview prompts</p>
                        <select onchange="dataLoader.setAutoRefreshInterval(this.value)" 
                                class="w-full bg-gray-700 border border-gray-600 rounded px-3 py-2 text-white">
                            <option value="0" ${this.autoRefreshInterval === 0 ? 'selected' : ''}>Disabled</option>
                            <option value="5" ${this.autoRefreshInterval === 5 ? 'selected' : ''}>Every 5 minutes</option>
                            <option value="15" ${this.autoRefreshInterval === 15 ? 'selected' : ''}>Every 15 minutes</option>
                            <option value="30" ${this.autoRefreshInterval === 30 ? 'selected' : ''}>Every 30 minutes</option>
                            <option value="60" ${this.autoRefreshInterval === 60 ? 'selected' : ''}>Every hour</option>
                        </select>
                    </div>
                    
                    <div class="border-t border-gray-700 pt-4">
                        <h4 class="text-lg font-semibold mb-3">Task Sync</h4>
                        <p class="text-xs text-gray-400 mb-3">Sync tasks with external services</p>
                        <label class="flex items-center gap-2 mb-3">
                            <input type="checkbox" 
                                   ${this.taskSyncEnabled ? 'checked' : ''}
                                   onchange="dataLoader.setTaskSync(this.checked)"
                                   class="w-4 h-4 rounded">
                            <span>Enable Task Sync</span>
                        </label>
                        <select onchange="dataLoader.setTaskSyncService(this.value)" 
                                class="w-full bg-gray-700 border border-gray-600 rounded px-3 py-2"
                                ${!this.taskSyncEnabled ? 'disabled' : ''}>
                            <option value="ticktick" ${this.taskSyncService === 'ticktick' ? 'selected' : ''}>TickTick</option>
                            <option value="todoist" ${this.taskSyncService === 'todoist' ? 'selected' : ''}>Todoist</option>
                        </select>
                    </div>
                    
                    <div class="border-t border-gray-700 pt-4">
                        <h4 class="text-lg font-semibold mb-3">AI Voice</h4>
                        <p class="text-xs text-gray-400 mb-3">Customize the AI assistant voice</p>
                        <select onchange="dataLoader.setAIVoice(this.value)" 
                                id="voice-selector"
                                class="w-full bg-gray-700 border border-gray-600 rounded px-3 py-2">
                            <option value="">Loading voices...</option>
                        </select>
                        <label class="flex items-center gap-2 mt-3">
                            <input type="checkbox" 
                                   ${this.voiceSignatureEnabled ? 'checked' : ''}
                                   onchange="dataLoader.setVoiceSignature(this.checked)"
                                   class="w-4 h-4 rounded">
                            <span class="text-sm">Enable "Roger Roger" signature</span>
                        </label>
                        <button onclick="dataLoader.testAIVoice()" 
                                class="w-full mt-2 bg-blue-600 hover:bg-blue-700 px-3 py-2 rounded text-sm">
                            🔊 Test Voice
                        </button>
                    </div>
                    
                    <div class="border-t border-gray-700 pt-4">
                        <h4 class="text-lg font-semibold mb-3">AI Personalization</h4>
                        <p class="text-xs text-gray-400 mb-3">Tell the AI about yourself for better responses</p>
                        <button onclick="dataLoader.showUserProfileModal()" 
                                class="w-full bg-purple-600 hover:bg-purple-700 px-4 py-2 rounded">
                            ${this.userProfile?.preferred_name ? '✏️ Edit' : '➕ Create'} Your AI Profile
                        </button>
                    </div>
                </div>
                
                <button onclick="dataLoader.hideEditPanel()" 
                        class="w-full mt-6 bg-green-600 hover:bg-green-700 px-4 py-2 rounded-lg">
                    Save & Close
                </button>
            </div>
        `;
        document.body.appendChild(panel);
        
        // Populate voice options
        this.populateVoiceOptions();
    }
    
    hideEditPanel() {
        const panel = document.getElementById('edit-panel');
        if (panel) {
            panel.remove();
        }
        this.editMode = false;
        const btn = document.getElementById('edit-mode-btn');
        if (btn) {
            btn.innerHTML = '<span>⚙️</span><span>Edit Dashboard</span>';
            btn.className = 'w-full bg-gray-700 hover:bg-gray-600 px-4 py-2 rounded-lg text-sm flex items-center justify-center gap-2 mb-2';
        }
    }
    
    toggleSection(sectionName) {
        this.dashboardConfig[sectionName] = !this.dashboardConfig[sectionName];
        this.saveDashboardConfig();
        this.updateNavVisibility();
    }
    
    setAutoRefreshInterval(minutes) {
        this.autoRefreshInterval = parseInt(minutes);
        this.saveAutoRefreshSettings();
        this.startAutoRefresh();
        
        if (this.autoRefreshInterval === 0) {
            console.log('Auto-refresh disabled');
        } else {
            console.log(`Auto-refresh set to ${this.autoRefreshInterval} minutes`);
        }
    }
    
    setTaskSync(enabled) {
        this.taskSyncEnabled = enabled;
        this.saveTaskSyncSettings();
        console.log(`Task sync ${enabled ? 'enabled' : 'disabled'} for ${this.taskSyncService}`);
    }
    
    setTaskSyncService(service) {
        this.taskSyncService = service;
        this.saveTaskSyncSettings();
        console.log(`Task sync service set to ${service}`);
    }
    
    saveTaskSyncSettings() {
        localStorage.setItem('taskSyncSettings', JSON.stringify({
            enabled: this.taskSyncEnabled,
            service: this.taskSyncService
        }));
    }
    
    loadTaskSyncSettings() {
        const stored = localStorage.getItem('taskSyncSettings');
        if (stored) {
            const settings = JSON.parse(stored);
            this.taskSyncEnabled = settings.enabled || false;
            this.taskSyncService = settings.service || 'ticktick';
        }
    }
    
    // Voice Settings
    loadVoiceSettings() {
        const stored = localStorage.getItem('selectedVoice');
        if (stored) {
            this.selectedVoice = stored;
        }
        
        // Load available voices
        this.loadAvailableVoices();
        
        // Voices may not be loaded immediately, reload on voiceschanged event
        if (this.speechSynthesis) {
            this.speechSynthesis.onvoiceschanged = () => {
                this.loadAvailableVoices();
                // Set default voice if not already set
                if (!this.selectedVoice) {
                    this.setDefaultVoice();
                }
            };
        }
    }
    
    setDefaultVoice() {
        if (!this.availableVoices || this.availableVoices.length === 0) {
            return;
        }
        
        console.log('Available voices:', this.availableVoices.map(v => `${v.name} (${v.lang})`));
        
        // Priority order for voice selection
        const voicePriorities = [
            // Google voices (work best in Safari)
            v => v.name.includes('Google') && v.name.includes('US') && v.name.includes('Male'),
            v => v.name.includes('Google') && v.name.includes('UK') && v.name.includes('Male'),
            v => v.name.includes('Google') && v.name.includes('Male'),
            v => v.name.includes('Google') && v.lang.startsWith('en'),
            // Other quality English male voices
            v => v.name.toLowerCase().includes('alex'),  // macOS Alex voice
            v => v.lang === 'en-US' && v.name.toLowerCase().includes('male'),
            v => v.lang === 'en-GB' && v.name.toLowerCase().includes('male'),
            // Any English male voice
            v => v.lang.startsWith('en') && v.name.toLowerCase().includes('male'),
            // Any English voice
            v => v.lang.startsWith('en')
        ];
        
        // Try each priority until we find a voice
        for (const priorityFn of voicePriorities) {
            const voice = this.availableVoices.find(priorityFn);
            if (voice) {
                this.selectedVoice = voice.name;
                localStorage.setItem('selectedVoice', this.selectedVoice);
                console.log('✅ Default voice set to:', this.selectedVoice, `(${voice.lang})`);
                return;
            }
        }
        
        // Last resort: just use the first available voice
        if (this.availableVoices.length > 0) {
            this.selectedVoice = this.availableVoices[0].name;
            localStorage.setItem('selectedVoice', this.selectedVoice);
            console.log('⚠️ Fallback to first available voice:', this.selectedVoice);
        }
    }
    
    loadAvailableVoices() {
        if (this.speechSynthesis) {
            this.availableVoices = this.speechSynthesis.getVoices();
            
            // Filter to show only high-quality voices (prioritize Google voices)
            const googleVoices = this.availableVoices.filter(v => v.name.includes('Google'));
            const otherQualityVoices = this.availableVoices.filter(v => 
                !v.name.includes('Google') && 
                (v.name.toLowerCase().includes('alex') || 
                 v.lang.startsWith('en'))
            );
            
            console.log(`Loaded ${this.availableVoices.length} total voices (${googleVoices.length} Google voices)`);
            if (googleVoices.length > 0) {
                console.log('🎤 Google voices available:', googleVoices.map(v => v.name));
            }
            
            // Set default voice on first load if none selected
            if (!this.selectedVoice && this.availableVoices.length > 0) {
                this.setDefaultVoice();
            }
        }
    }
    
    populateVoiceOptions() {
        const selector = document.getElementById('voice-selector');
        if (!selector) return;
        
        // Build options array with Rogr first
        let options = [];
        
        // Add Rogr as the primary option
        const rogrSelected = (!this.selectedVoice || this.selectedVoice === 'rogr') ? 'selected' : '';
        options.push(`<option value="rogr" ${rogrSelected}>🤖 Rogr (Battle Droid) - Recommended</option>`);
        
        // Add browser TTS voices
        if (this.availableVoices.length === 0) {
            // Try loading voices again
            this.loadAvailableVoices();
        }
        
        if (this.availableVoices.length > 0) {
            // Add separator
            options.push('<option disabled>──────────────</option>');
            options.push('<option disabled>Browser Voices (Fallback):</option>');
            
            // Add browser voices
            this.availableVoices.forEach((voice, index) => {
                const selected = this.selectedVoice === voice.name ? 'selected' : '';
                options.push(`<option value="${voice.name}" ${selected}>${voice.name} (${voice.lang})</option>`);
            });
        }
        
        selector.innerHTML = options.join('');
        
        // Set default to Rogr if nothing selected
        if (!this.selectedVoice) {
            this.setAIVoice('rogr');
        }
    }
    
    setAIVoice(voiceName) {
        this.selectedVoice = voiceName;
        localStorage.setItem('selectedVoice', voiceName);
        console.log(`AI voice set to: ${voiceName}`);
    }
    
    setVoiceSignature(enabled) {
        this.voiceSignatureEnabled = enabled;
        localStorage.setItem('voiceSignatureEnabled', enabled);
        console.log(`Voice signature ${enabled ? 'enabled' : 'disabled'}`);
    }
    
    testAIVoice() {
        const assistant = this.getActiveAssistant();
        const testLine = assistant?.tagline || 'Voice system operational. All systems ready.';
        if (this.selectedVoice === 'rogr' || !this.selectedVoice) {
            this.speakText(testLine, !!assistant?.signature_enabled);
        } else {
            this.speakText(`Hello, this is ${assistant?.name || 'your AI assistant'}. ${testLine}`);
        }
    }
    
    updateNavVisibility() {
        Object.entries(this.dashboardConfig).forEach(([key, enabled]) => {
            const navLinks = document.querySelectorAll('.nav-link');
            navLinks.forEach(link => {
                const linkText = link.textContent.trim().toLowerCase();
                if (linkText.includes(key)) {
                    link.style.display = enabled ? 'flex' : 'none';
                }
            });
        });
    }
    
    saveDashboardConfig() {
        localStorage.setItem('dashboardConfig', JSON.stringify(this.dashboardConfig));
    }
    
    loadDashboardConfig() {
        const stored = localStorage.getItem('dashboardConfig');
        if (stored) {
            try {
                this.dashboardConfig = { ...this.dashboardConfig, ...JSON.parse(stored) };
                this.updateNavVisibility();
            } catch (error) {
                console.error('Error loading dashboard config:', error);
            }
        }
    }
    
    loadAutoRefreshSettings() {
        const stored = localStorage.getItem('autoRefreshInterval');
        if (stored) {
            this.autoRefreshInterval = parseInt(stored);
        }
        this.startAutoRefresh();
    }
    
    saveAutoRefreshSettings() {
        localStorage.setItem('autoRefreshInterval', this.autoRefreshInterval.toString());
    }
    
    startAutoRefresh() {
        // Clear existing timer
        if (this.autoRefreshTimer) {
            clearInterval(this.autoRefreshTimer);
        }
        
        // Update status display
        this.updateRefreshStatus();
        
        // Don't start if interval is 0 (disabled)
        if (this.autoRefreshInterval === 0) {
            return;
        }
        
        // Start new timer
        const intervalMs = this.autoRefreshInterval * 60 * 1000;
        this.autoRefreshTimer = setInterval(async () => {
            console.log('Auto-refreshing dashboard data...');
            await this.loadAllData();
            await this.generateOverviewPrompt();
            this.updateRefreshStatus();
        }, intervalMs);
        
        console.log(`Auto-refresh enabled: every ${this.autoRefreshInterval} minutes`);
    }
    
    updateRefreshStatus() {
        const statusEl = document.getElementById('refresh-status-text');
        if (!statusEl) return;
        
        if (this.autoRefreshInterval === 0) {
            statusEl.textContent = 'Auto-refresh: Disabled';
        } else {
            const lastUpdate = new Date().toLocaleTimeString();
            const nextUpdate = new Date(Date.now() + this.autoRefreshInterval * 60 * 1000).toLocaleTimeString();
            statusEl.textContent = `Auto-refresh: Every ${this.autoRefreshInterval}min | Last: ${lastUpdate} | Next: ${nextUpdate}`;
        }
    }
    
    async generateOverviewPrompt() {
        // Generate an AI prompt for the overview based on current data
        const activeTodos = this.todos.filter(t => t.status !== 'completed' && t.status !== 'deleted');
        const upcomingEvents = this.calendar.filter(e => new Date(e.start) > new Date()).slice(0, 3);
        const highPriorityEmails = this.emails.filter(e => e.priority === 'high');
        
        const prompt = `Dashboard Update:\n\n` +
            `Tasks: ${activeTodos.length} active (${activeTodos.filter(t => t.priority === 'high').length} high priority)\n` +
            `Calendar: ${upcomingEvents.length} upcoming events\n` +
            `Emails: ${highPriorityEmails.length} high priority\n\n` +
            `Top Priorities:\n` +
            activeTodos.slice(0, 3).map(t => `- ${t.title}`).join('\n');
        
        console.log('Overview Prompt:', prompt);
        
        // Could optionally send to AI for suggestions
        // For now just log it
        return prompt;
    }
    
    async generateOverviewSummary() {
        // Generate a 5-minute overview summary for the AI Assistant page
        const activeTodos = this.todos.filter(t => t.status !== 'completed' && t.status !== 'deleted');
        const highPriorityTodos = activeTodos.filter(t => t.priority === 'high');
        const startedTodos = activeTodos.filter(t => t.status === 'in_progress');
        const upcomingEvents = this.calendar.filter(e => new Date(e.start) > new Date());
        const todayEvents = upcomingEvents.filter(e => {
            const start = new Date(e.start);
            const today = new Date();
            return start.toDateString() === today.toDateString();
        });
        const highPriorityEmails = this.emails.filter(e => e.priority === 'high');
        const unreadEmails = this.emails.filter(e => !e.read);
        
        let summary = '<div class="space-y-2">';
        
        // Quick stats
        summary += `<div class="flex flex-wrap gap-4 mb-3">`;
        if (activeTodos.length > 0) {
            summary += `<span class="text-yellow-400">📋 ${activeTodos.length} active task${activeTodos.length !== 1 ? 's' : ''}</span>`;
        }
        if (highPriorityTodos.length > 0) {
            summary += `<span class="text-red-400">🔥 ${highPriorityTodos.length} high priority</span>`;
        }
        if (todayEvents.length > 0) {
            summary += `<span class="text-blue-400">📅 ${todayEvents.length} event${todayEvents.length !== 1 ? 's' : ''} today</span>`;
        }
        if (highPriorityEmails.length > 0) {
            summary += `<span class="text-purple-400">📧 ${highPriorityEmails.length} important email${highPriorityEmails.length !== 1 ? 's' : ''}</span>`;
        }
        summary += `</div>`;
        
        // Top priorities
        if (highPriorityTodos.length > 0) {
            summary += `<div class="mt-3"><strong class="text-red-400">🎯 Top Priorities:</strong><ul class="list-disc list-inside ml-4 mt-1">`;
            highPriorityTodos.slice(0, 3).forEach(todo => {
                summary += `<li class="text-gray-300">${this.escapeHtml(todo.title)}</li>`;
            });
            summary += `</ul></div>`;
        }
        
        // In progress
        if (startedTodos.length > 0) {
            summary += `<div class="mt-3"><strong class="text-green-400">🚀 In Progress:</strong><ul class="list-disc list-inside ml-4 mt-1">`;
            startedTodos.slice(0, 3).forEach(todo => {
                summary += `<li class="text-gray-300">${this.escapeHtml(todo.title)}</li>`;
            });
            summary += `</ul></div>`;
        }
        
        // Today's events
        if (todayEvents.length > 0) {
            summary += `<div class="mt-3"><strong class="text-blue-400">📅 Today's Events:</strong><ul class="list-disc list-inside ml-4 mt-1">`;
            todayEvents.slice(0, 3).forEach(event => {
                const time = new Date(event.start).toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' });
                summary += `<li class="text-gray-300">${time} - ${this.escapeHtml(event.title)}</li>`;
            });
            summary += `</ul></div>`;
        }
        
        // Summary message
        if (activeTodos.length === 0 && todayEvents.length === 0) {
            summary += `<p class="text-green-400 mt-3">✨ You're all caught up! Great work!</p>`;
        } else if (highPriorityTodos.length === 0 && startedTodos.length > 0) {
            summary += `<p class="text-green-400 mt-3">💪 Making progress! Keep up the momentum.</p>`;
        } else if (highPriorityTodos.length > 0) {
            summary += `<p class="text-yellow-400 mt-3">⚡ Focus on high priority items to stay ahead.</p>`;
        }
        
        summary += '</div>';
        
        this.overviewSummary = summary;
    }
    
    generatePersonalizedSuggestion() {
        // Generate a random personalized suggestion based on user profile and activity
        const suggestions = [];
        
        // Check user profile for interests
        if (this.userProfile && this.userProfile.interests) {
            const interests = this.userProfile.interests.split(',').map(i => i.trim()).filter(Boolean);
            if (interests.length > 0) {
                const randomInterest = interests[Math.floor(Math.random() * interests.length)];
                suggestions.push({
                    title: `Explore ${randomInterest}`,
                    description: `Based on your interest in ${randomInterest}, consider setting aside time to dive deeper into this topic today.`,
                    action: null
                });
            }
        }
        
        // Check for sections not visited recently
        const now = new Date();
        const sections = ['emails', 'calendar', 'news', 'music', 'github'];
        const unvisitedSections = sections.filter(section => {
            if (this.dashboardConfig && this.dashboardConfig.sections && 
                this.dashboardConfig.sections[section] === false) {
                return false; // Don't suggest disabled sections
            }
            return true;
        });
        
        if (unvisitedSections.length > 0) {
            const randomSection = unvisitedSections[Math.floor(Math.random() * unvisitedSections.length)];
            const sectionNames = {
                emails: '📧 Emails',
                calendar: '📅 Calendar', 
                news: '📰 News',
                music: '🎵 Music',
                github: '💻 GitHub'
            };
            suggestions.push({
                title: `Check ${sectionNames[randomSection]}`,
                description: `You might have updates in your ${randomSection} section. Take a quick look!`,
                action: randomSection,
                actionLabel: `View ${sectionNames[randomSection]}`
            });
        }
        
        // Time-based suggestions
        const hour = now.getHours();
        if (hour >= 6 && hour < 9) {
            suggestions.push({
                title: 'Morning Planning',
                description: 'Start your day strong! Review your top 3 priorities and schedule time for focused work.',
                action: 'todos',
                actionLabel: 'Review Tasks'
            });
        } else if (hour >= 12 && hour < 14) {
            suggestions.push({
                title: 'Midday Check-in',
                description: 'Take a break and review your progress. Are you on track with your priorities?',
                action: null
            });
        } else if (hour >= 17 && hour < 19) {
            suggestions.push({
                title: 'End-of-Day Wrap-up',
                description: 'Review what you accomplished today and set up tomorrow for success.',
                action: 'todos',
                actionLabel: 'Review Progress'
            });
        }
        
        // Activity-based suggestions
        const completedToday = this.todos.filter(t => {
            if (t.status !== 'completed' || !t.completed_at) return false;
            const completed = new Date(t.completed_at);
            return completed.toDateString() === now.toDateString();
        });
        
        if (completedToday.length >= 5) {
            suggestions.push({
                title: '🎉 Productivity Streak!',
                description: `You've completed ${completedToday.length} tasks today! You're on fire! Keep the momentum going.`,
                action: null
            });
        }
        
        const highPriorityTodos = this.todos.filter(t => t.status !== 'completed' && t.status !== 'deleted' && t.priority === 'high');
        if (highPriorityTodos.length > 5) {
            suggestions.push({
                title: '🎯 Focus Strategy',
                description: `You have ${highPriorityTodos.length} high priority tasks. Consider breaking them down or delegating some to stay focused.`,
                action: 'todos',
                actionLabel: 'Review Priorities'
            });
        }
        
        // Feedback-based suggestions
        const likedItems = Object.entries(this.feedbackData).filter(([key, value]) => value === 'up');
        if (likedItems.length > 10) {
            suggestions.push({
                title: '💡 Pattern Recognition',
                description: 'You\'ve given lots of positive feedback! The AI is learning your preferences to provide better suggestions.',
                action: null
            });
        }
        
        // Select random suggestion
        if (suggestions.length > 0) {
            this.personalizedSuggestion = suggestions[Math.floor(Math.random() * suggestions.length)];
        }
    }
    
    handlePersonalizedAction(action) {
        // Handle action from personalized suggestion
        if (action && typeof showSection === 'function') {
            showSection(action);
        }
    }
    
    // BACKGROUND IMAGE SYSTEM
    loadBackgroundSettings() {
        const stored = localStorage.getItem('backgroundSettings');
        if (stored) {
            const settings = JSON.parse(stored);
            this.backgroundImages = settings.images || [];
            this.currentBackgroundIndex = settings.currentIndex || 0;
            this.backgroundRotation = settings.rotation || 'random';
            this.fullPageBackground = settings.fullPageBackground || false;
        }
        
        // Load saved backgrounds
        this.loadSavedBackgrounds();
        
        // Initialize with default sci-fi images if none saved
        if (this.backgroundImages.length === 0) {
            this.backgroundImages = [
                { url: 'https://images.unsplash.com/photo-1419242902214-272b3f66ee7a', name: 'Space Nebula', theme: 'dark' },
                { url: 'https://images.unsplash.com/photo-1462331940025-496dfbfc7564', name: 'Night Sky', theme: 'dark' },
                { url: 'https://images.unsplash.com/photo-1446776653964-20c1d3a81b06', name: 'Cosmos', theme: 'dark' },
                { url: 'https://images.unsplash.com/photo-1451187580459-43490279c0fa', name: 'Earth Space', theme: 'blue' },
                { url: 'https://images.unsplash.com/photo-1502134249126-9f3755a50d78', name: 'Galaxy', theme: 'purple' }
            ];
        }
        
        this.applyBackground();
    }
    
    saveBackgroundSettings() {
        const settings = {
            images: this.backgroundImages,
            currentIndex: this.currentBackgroundIndex,
            rotation: this.backgroundRotation,
            fullPageBackground: this.fullPageBackground
        };
        localStorage.setItem('backgroundSettings', JSON.stringify(settings));
    }
    
    applyBackground() {
        if (this.backgroundImages.length === 0) return;
        
        const image = this.backgroundImages[this.currentBackgroundIndex];
        
        // Apply to ALL visible sections if full-page background is enabled
        if (this.fullPageBackground) {
            const allSections = document.querySelectorAll('.section-content:not(.hidden)');
            allSections.forEach(section => {
                section.style.backgroundImage = `linear-gradient(rgba(0,0,0,0.7), rgba(0,0,0,0.85)), url(${image.url}?w=1920&q=85)`;
                section.style.backgroundSize = 'cover';
                section.style.backgroundPosition = 'center';
                section.style.backgroundAttachment = 'fixed';
                
                // Make all cards semi-transparent
                const cards = section.querySelectorAll('.bg-gray-800, .bg-gray-700');
                cards.forEach(card => {
                    card.style.backgroundColor = 'rgba(31, 41, 55, 0.85)';
                    card.style.webkitBackdropFilter = 'blur(10px)';
                    card.style.backdropFilter = 'blur(10px)';
                });
            });
        }
        
        // Apply header image to overview section specifically
        const section = document.getElementById('section-overview');
        if (!section) return;
        
        const header = section.querySelector('.max-w-7xl');
        if (header) {
            // Create header image container if it doesn't exist
            let headerImage = document.getElementById('overview-header-image');
            if (!headerImage) {
                headerImage = document.createElement('div');
                headerImage.id = 'overview-header-image';
                headerImage.className = 'relative rounded-xl overflow-hidden mb-8 h-64';
                header.insertBefore(headerImage, header.firstChild);
            }
            
            // Apply background image with gradient overlay to header
            headerImage.style.backgroundImage = `linear-gradient(rgba(0,0,0,0.5), rgba(0,0,0,0.7)), url(${image.url}?w=1200&q=80)`;
            headerImage.style.backgroundSize = 'cover';
            headerImage.style.backgroundPosition = 'center';
            
            // Add title overlay
            headerImage.innerHTML = `
                <div class="absolute inset-0 flex flex-col justify-end p-6">
                    <h2 class="text-4xl font-bold text-white mb-2">Dashboard Overview</h2>
                    <div class="flex gap-2 items-center flex-wrap">
                        <span class="text-sm text-gray-300">${image.name}</span>
                        <div class="ml-auto flex gap-2">
                            <button onclick="dataLoader.giveBackgroundFeedback('up')" 
                                    class="bg-white/20 hover:bg-green-500/80 backdrop-blur-sm px-3 py-1 rounded text-lg">
                                👍
                            </button>
                            <button onclick="dataLoader.giveBackgroundFeedback('neutral')" 
                                    class="bg-white/20 hover:bg-yellow-500/80 backdrop-blur-sm px-3 py-1 rounded text-lg">
                                👌
                            </button>
                            <button onclick="dataLoader.giveBackgroundFeedback('down')" 
                                    class="bg-white/20 hover:bg-red-500/80 backdrop-blur-sm px-3 py-1 rounded text-lg">
                                👎
                            </button>
                            <button onclick="dataLoader.nextBackground()" 
                                    class="bg-white/20 hover:bg-white/30 backdrop-blur-sm px-3 py-1 rounded text-sm text-white">
                                🔄 Change
                            </button>
                            <button onclick="dataLoader.openBackgroundSettings()" 
                                    class="bg-white/20 hover:bg-white/30 backdrop-blur-sm px-3 py-1 rounded text-sm text-white">
                                ⚙️ Settings
                            </button>
                        </div>
                    </div>
                </div>
            `;
        }
        
        // Apply full-page background to overview if enabled
        if (this.fullPageBackground) {
            // Apply full-page background
            section.style.backgroundImage = `linear-gradient(rgba(0,0,0,0.7), rgba(0,0,0,0.85)), url(${image.url}?w=1920&q=85)`;
            section.style.backgroundSize = 'cover';
            section.style.backgroundPosition = 'center';
            section.style.backgroundAttachment = 'fixed';
            
            // Make all cards semi-transparent
            const cards = section.querySelectorAll('.bg-gray-800, .bg-gray-700');
            cards.forEach(card => {
                card.style.backgroundColor = 'rgba(31, 41, 55, 0.85)';
                card.style.webkitBackdropFilter = 'blur(10px)'; // Safari support
                card.style.backdropFilter = 'blur(10px)';
            });
            
            // Create floating controls
            let controls = document.getElementById('background-controls');
            if (!controls) {
                controls = document.createElement('div');
                controls.id = 'background-controls';
                controls.className = 'fixed top-20 right-4 bg-gray-800/90 backdrop-blur-sm rounded-lg p-3 z-40 shadow-lg';
                controls.innerHTML = `
                    <div class="flex flex-col gap-2">
                        <span class="text-xs text-gray-400">${image.name}</span>
                        <div class="flex gap-2">
                            <button onclick="dataLoader.giveBackgroundFeedback('up')" 
                                    class="bg-gray-700 hover:bg-green-600 px-2 py-1 rounded text-sm">👍</button>
                            <button onclick="dataLoader.giveBackgroundFeedback('neutral')" 
                                    class="bg-gray-700 hover:bg-yellow-600 px-2 py-1 rounded text-sm">👌</button>
                            <button onclick="dataLoader.giveBackgroundFeedback('down')" 
                                    class="bg-gray-700 hover:bg-red-600 px-2 py-1 rounded text-sm">👎</button>
                        </div>
                        <div class="flex gap-2">
                            <button onclick="dataLoader.nextBackground()" 
                                    class="bg-gray-700 hover:bg-gray-600 px-2 py-1 rounded text-xs">� Change</button>
                            <button onclick="dataLoader.openBackgroundSettings()" 
                                    class="bg-gray-700 hover:bg-gray-600 px-2 py-1 rounded text-xs">⚙️ Settings</button>
                        </div>
                    </div>
                `;
                document.body.appendChild(controls);
            } else {
                // Update controls text
                const nameSpan = controls.querySelector('.text-gray-400');
                if (nameSpan) nameSpan.textContent = image.name;
            }
        } else {
            // No full-page background - clear section background
            section.style.backgroundImage = '';
            section.style.backgroundColor = '';
            
            // Reset card transparency
            const cards = section.querySelectorAll('.bg-gray-800, .bg-gray-700');
            cards.forEach(card => {
                card.style.backgroundColor = '';
                card.style.webkitBackdropFilter = ''; // Safari support
                card.style.backdropFilter = '';
            });
            
            // Remove floating controls
            const controls = document.getElementById('background-controls');
            if (controls) controls.remove();
        }
        
        // Apply theme adjustment based on image
        this.adjustTheme(image.theme);
    }
    
    adjustTheme(theme) {
        const root = document.documentElement;
        
        switch(theme) {
            case 'blue':
                root.style.setProperty('--accent-color', '#3b82f6');
                break;
            case 'purple':
                root.style.setProperty('--accent-color', '#a855f7');
                break;
            case 'dark':
            default:
                root.style.setProperty('--accent-color', '#6366f1');
                break;
        }
    }
    
    nextBackground() {
        if (this.backgroundImages.length === 0) return;
        
        if (this.backgroundRotation === 'random') {
            this.currentBackgroundIndex = Math.floor(Math.random() * this.backgroundImages.length);
        } else {
            this.currentBackgroundIndex = (this.currentBackgroundIndex + 1) % this.backgroundImages.length;
        }
        
        this.saveBackgroundSettings();
        this.applyBackground();
    }
    
    openBackgroundSettings() {
        const modal = `
            <div class="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4 overflow-y-auto" onclick="if(event.target===this) this.remove()">
                <div class="bg-gray-800 rounded-xl p-6 max-w-3xl w-full my-8">
                    <div class="flex items-center justify-between mb-4">
                        <h3 class="text-2xl font-bold">Background Settings</h3>
                        <button onclick="this.closest('.fixed').remove()" 
                                class="text-gray-400 hover:text-white text-2xl leading-none">
                            ×
                        </button>
                    </div>
                    
                    <div class="max-h-[calc(90vh-8rem)] overflow-y-auto pr-2 space-y-6">
                    
                    <div class="mb-6">
                        <label class="flex items-center gap-3 cursor-pointer">
                            <input type="checkbox" 
                                   ${this.fullPageBackground ? 'checked' : ''}
                                   onchange="dataLoader.toggleFullPageBackground(this.checked)"
                                   class="w-5 h-5 rounded">
                            <div>
                                <div class="font-semibold">Full-Page Background</div>
                                <div class="text-xs text-gray-400">Apply background to entire overview page with transparent cards</div>
                            </div>
                        </label>
                    </div>
                    
                    <div class="mb-6">
                        <label class="block text-sm font-medium mb-2">Rotation Mode</label>
                        <select onchange="dataLoader.setBackgroundRotation(this.value)" 
                                class="w-full bg-gray-700 border border-gray-600 rounded px-3 py-2">
                            <option value="random" ${this.backgroundRotation === 'random' ? 'selected' : ''}>Random</option>
                            <option value="sequential" ${this.backgroundRotation === 'sequential' ? 'selected' : ''}>Sequential</option>
                            <option value="fixed" ${this.backgroundRotation === 'fixed' ? 'selected' : ''}>Fixed (Current Only)</option>
                        </select>
                    </div>
                    
                    <div class="mb-6">
                        <h4 class="text-lg font-semibold mb-3">Add New Backgrounds</h4>
                        <div class="grid grid-cols-2 gap-3">
                            <button onclick="dataLoader.fetchNewBackgroundFromUnsplash()" 
                                    class="bg-purple-600 hover:bg-purple-700 px-4 py-3 rounded-lg flex items-center justify-center gap-2">
                                <span>🌌</span>
                                <span>Fetch from Unsplash</span>
                            </button>
                            <label class="bg-blue-600 hover:bg-blue-700 px-4 py-3 rounded-lg flex items-center justify-center gap-2 cursor-pointer">
                                <span>📤</span>
                                <span>Upload Custom</span>
                                <input type="file" 
                                       accept="image/*" 
                                       onchange="dataLoader.uploadCustomBackground(event)" 
                                       class="hidden">
                            </label>
                        </div>
                    </div>
                    
                    ${this.savedBackgrounds.length > 0 ? `
                        <div class="mb-6">
                            <div class="flex items-center justify-between mb-3">
                                <h4 class="text-lg font-semibold">💾 Saved Backgrounds (${this.savedBackgrounds.length})</h4>
                                <button onclick="dataLoader.clearSavedBackgrounds()" 
                                        class="text-xs text-red-400 hover:text-red-300">
                                    Clear All
                                </button>
                            </div>
                            <p class="text-xs text-gray-400 mb-3">These images are saved offline and ready to use</p>
                            <div class="grid grid-cols-3 gap-3 max-h-64 overflow-y-auto">
                                ${this.savedBackgrounds.map((img, idx) => `
                                    <div class="relative group">
                                        <img src="${img.url}" 
                                             onclick="dataLoader.useSavedBackground(${idx})"
                                             class="w-full h-24 object-cover rounded cursor-pointer" 
                                             alt="${img.name}">
                                        <div class="absolute inset-0 bg-black/50 opacity-0 group-hover:opacity-100 flex items-center justify-center rounded transition-opacity">
                                            <span class="text-white text-xs">${img.name}</span>
                                        </div>
                                        <button onclick="event.stopPropagation(); dataLoader.removeSavedBackground(${idx})" 
                                                class="absolute top-1 right-1 bg-red-600 hover:bg-red-700 text-white text-xs w-5 h-5 rounded-full opacity-0 group-hover:opacity-100 transition-opacity">
                                            ×
                                        </button>
                                        <span class="absolute top-1 left-1 bg-green-600 text-xs px-1 rounded">✓</span>
                                    </div>
                                `).join('')}
                            </div>
                        </div>
                    ` : ''}
                    
                    <div class="mb-6">
                        <h4 class="text-lg font-semibold mb-3">Available Backgrounds</h4>
                        <div class="grid grid-cols-3 gap-3">
                            ${this.backgroundImages.map((img, idx) => `
                                <div class="relative group cursor-pointer ${idx === this.currentBackgroundIndex ? 'ring-2 ring-blue-500' : ''}" 
                                     onclick="dataLoader.selectBackground(${idx})">
                                    <img src="${img.url}?w=300&h=200&fit=crop" 
                                         class="w-full h-24 object-cover rounded" 
                                         alt="${img.name}">
                                    <div class="absolute inset-0 bg-black/50 opacity-0 group-hover:opacity-100 flex items-center justify-center rounded transition-opacity">
                                        <span class="text-white text-xs">${img.name}</span>
                                    </div>
                                    ${idx === this.currentBackgroundIndex ? '<span class="absolute top-1 right-1 bg-blue-600 text-xs px-1 rounded">▶</span>' : ''}
                                    <button onclick="event.stopPropagation(); dataLoader.removeBackground(${idx})" 
                                            class="absolute top-1 left-1 bg-red-600 hover:bg-red-700 text-white text-xs w-5 h-5 rounded-full opacity-0 group-hover:opacity-100 transition-opacity">
                                        ×
                                    </button>
                                </div>
                            `).join('')}
                        </div>
                    </div>
                    </div>
                    
                    <div class="mt-6 pt-4 border-t border-gray-700">
                        <button onclick="this.closest('.fixed').remove()" 
                                class="w-full bg-blue-600 hover:bg-blue-700 px-4 py-2 rounded">
                            Close
                        </button>
                    </div>
                </div>
            </div>
        `;
        document.body.insertAdjacentHTML('beforeend', modal);
    }
    
    toggleFullPageBackground(enabled) {
        this.fullPageBackground = enabled;
        this.saveBackgroundSettings();
        this.applyBackground();
        this.showNotification(enabled ? '🌌 Full-page background enabled!' : '📸 Header-only background enabled');
    }
    
    useSavedBackground(index) {
        if (index < 0 || index >= this.savedBackgrounds.length) return;
        
        const savedBg = this.savedBackgrounds[index];
        
        // Check if already in current backgrounds
        const exists = this.backgroundImages.find(img => img.name === savedBg.name);
        if (!exists) {
            this.backgroundImages.push(savedBg);
        }
        
        // Set as current
        this.currentBackgroundIndex = this.backgroundImages.findIndex(img => img.name === savedBg.name);
        this.saveBackgroundSettings();
        this.applyBackground();
        
        // Close modal
        const modal = document.querySelector('.fixed.inset-0');
        if (modal) modal.remove();
        
        this.showNotification(`Using saved background: ${savedBg.name}`);
    }
    
    async fetchNewBackgroundFromUnsplash() {
        try {
            this.showNotification('🌌 Fetching new background from Unsplash...');
            
            // Fetch random space/sci-fi image from Unsplash
            const topics = ['space', 'galaxy', 'nebula', 'cosmos', 'stars', 'universe', 'astronomy', 'planet'];
            const randomTopic = topics[Math.floor(Math.random() * topics.length)];
            
            // Using Unsplash Source API with timestamp to ensure unique fetch
            const timestamp = Date.now();
            const url = `https://source.unsplash.com/1600x900/?${randomTopic}&sig=${timestamp}`;
            
            // Create a new image object
            const newImage = {
                url: url,
                name: `${randomTopic.charAt(0).toUpperCase() + randomTopic.slice(1)} ${new Date().toLocaleTimeString()}`,
                theme: 'dark'
            };
            
            this.backgroundImages.push(newImage);
            this.currentBackgroundIndex = this.backgroundImages.length - 1;
            this.saveBackgroundSettings();
            this.applyBackground();
            
            // Close and reopen modal to show new image
            const modal = document.querySelector('.fixed.inset-0');
            if (modal) {
                modal.remove();
                this.openBackgroundSettings();
            }
            
            this.showNotification(`✅ Added new ${randomTopic} background!`);
        } catch (error) {
            console.error('Error fetching new background:', error);
            this.showNotification('⚠️ Could not fetch new background from Unsplash');
        }
    }
    
    async uploadCustomBackground(event) {
        const file = event.target.files[0];
        if (!file) return;
        
        // Validate file type
        if (!file.type.startsWith('image/')) {
            this.showNotification('⚠️ Please select an image file');
            return;
        }
        
        // Validate file size (max 5MB)
        if (file.size > 5 * 1024 * 1024) {
            this.showNotification('⚠️ Image too large. Please select an image under 5MB');
            return;
        }
        
        try {
            this.showNotification('📤 Uploading custom background...');
            
            // Convert to base64
            const reader = new FileReader();
            reader.onload = (e) => {
                const base64url = e.target.result;
                
                // Create new image object
                const newImage = {
                    url: base64url,
                    name: `Custom: ${file.name.split('.')[0]}`,
                    theme: 'custom',
                    custom: true
                };
                
                // Add to backgrounds
                this.backgroundImages.push(newImage);
                this.currentBackgroundIndex = this.backgroundImages.length - 1;
                this.saveBackgroundSettings();
                this.applyBackground();
                
                // Close and reopen modal to show new image
                const modal = document.querySelector('.fixed.inset-0');
                if (modal) {
                    modal.remove();
                    this.openBackgroundSettings();
                }
                
                this.showNotification(`✅ Custom background "${file.name}" uploaded!`);
            };
            
            reader.onerror = () => {
                this.showNotification('⚠️ Error reading image file');
            };
            
            reader.readAsDataURL(file);
        } catch (error) {
            console.error('Error uploading custom background:', error);
            this.showNotification('⚠️ Could not upload custom background');
        }
    }
    
    removeBackground(index) {
        if (index < 0 || index >= this.backgroundImages.length) return;
        
        const image = this.backgroundImages[index];
        if (confirm(`Remove "${image.name}" from backgrounds?`)) {
            this.backgroundImages.splice(index, 1);
            
            // Adjust current index if needed
            if (this.currentBackgroundIndex >= this.backgroundImages.length) {
                this.currentBackgroundIndex = Math.max(0, this.backgroundImages.length - 1);
            }
            
            this.saveBackgroundSettings();
            this.applyBackground();
            
            // Reopen modal to update view
            const modal = document.querySelector('.fixed.inset-0');
            if (modal) {
                modal.remove();
                this.openBackgroundSettings();
            }
            
            this.showNotification(`🗑️ Removed "${image.name}"`);
        }
    }
    
    removeSavedBackground(index) {
        if (index < 0 || index >= this.savedBackgrounds.length) return;
        
        const image = this.savedBackgrounds[index];
        if (confirm(`Remove "${image.name}" from saved backgrounds?`)) {
            this.savedBackgrounds.splice(index, 1);
            localStorage.setItem('savedBackgrounds', JSON.stringify(this.savedBackgrounds));
            
            // Reopen modal to update view
            const modal = document.querySelector('.fixed.inset-0');
            if (modal) {
                modal.remove();
                this.openBackgroundSettings();
            }
            
            this.showNotification(`🗑️ Removed "${image.name}" from saved`);
        }
    }
    
    clearSavedBackgrounds() {
        if (confirm(`Clear all ${this.savedBackgrounds.length} saved backgrounds? This cannot be undone.`)) {
            this.savedBackgrounds = [];
            localStorage.setItem('savedBackgrounds', JSON.stringify(this.savedBackgrounds));
            
            // Reopen modal to update view
            const modal = document.querySelector('.fixed.inset-0');
            if (modal) {
                modal.remove();
                this.openBackgroundSettings();
            }
            
            this.showNotification('🗑️ All saved backgrounds cleared');
        }
    }
    
    setBackgroundRotation(mode) {
        this.backgroundRotation = mode;
        this.saveBackgroundSettings();
    }
    
    selectBackground(index) {
        this.currentBackgroundIndex = index;
        this.saveBackgroundSettings();
        this.applyBackground();
        document.querySelector('.fixed.inset-0')?.remove();
    }
    
    async giveBackgroundFeedback(sentiment) {
        const currentImage = this.backgroundImages[this.currentBackgroundIndex];
        const key = `background-${currentImage.url}`;
        
        // Store feedback
        this.feedbackData[key] = sentiment;
        localStorage.setItem('dashboardFeedback', JSON.stringify(this.feedbackData));
        
        // Send to backend for AI training
        try {
            await fetch('/api/feedback', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    item_type: 'background',
                    item_id: currentImage.url,
                    sentiment: sentiment,
                    context: {
                        name: currentImage.name,
                        theme: currentImage.theme,
                        url: currentImage.url
                    }
                })
            });
        } catch (error) {
            console.error('Error sending background feedback:', error);
        }
        
        // Handle feedback actions
        if (sentiment === 'up') {
            // Save the image as base64 for offline use
            await this.saveBackgroundOffline(currentImage);
            this.showNotification('👍 Background saved for offline use!');
        } else if (sentiment === 'down') {
            // Remove from collection and load new one
            this.backgroundImages.splice(this.currentBackgroundIndex, 1);
            
            // Load a new background from Unsplash
            await this.fetchNewBackground();
            
            // Adjust index if needed
            if (this.currentBackgroundIndex >= this.backgroundImages.length) {
                this.currentBackgroundIndex = 0;
            }
            
            this.saveBackgroundSettings();
            this.applyBackground();
            this.showNotification('👎 Background removed. Loading a new one...');
        } else {
            // Neutral - just move to next
            this.nextBackground();
            this.showNotification('👌 Noted! Moving to next background.');
        }
    }
    
    async saveBackgroundOffline(image) {
        try {
            // Convert image URL to base64
            const response = await fetch(image.url);
            const blob = await response.blob();
            
            return new Promise((resolve, reject) => {
                const reader = new FileReader();
                reader.onloadend = () => {
                    const base64data = reader.result;
                    
                    // Save to savedBackgrounds array
                    const savedImage = {
                        url: base64data,
                        name: image.name,
                        theme: image.theme,
                        saved_at: new Date().toISOString()
                    };
                    
                    this.savedBackgrounds.push(savedImage);
                    
                    // Save to localStorage
                    localStorage.setItem('savedBackgrounds', JSON.stringify(this.savedBackgrounds));
                    
                    console.log('Background saved offline:', image.name);
                    resolve();
                };
                reader.onerror = reject;
                reader.readAsDataURL(blob);
            });
        } catch (error) {
            console.error('Error saving background offline:', error);
            this.showNotification('⚠️ Could not save background offline');
        }
    }
    
    loadSavedBackgrounds() {
        const stored = localStorage.getItem('savedBackgrounds');
        if (stored) {
            this.savedBackgrounds = JSON.parse(stored);
            console.log(`Loaded ${this.savedBackgrounds.length} saved backgrounds`);
        }
    }
    
    async fetchNewBackground() {
        try {
            // Fetch random space/sci-fi image from Unsplash
            const topics = ['space', 'galaxy', 'nebula', 'cosmos', 'stars', 'universe'];
            const randomTopic = topics[Math.floor(Math.random() * topics.length)];
            
            // Using Unsplash Source API for random images
            const url = `https://source.unsplash.com/1600x900/?${randomTopic}`;
            
            // Create a new image object
            const newImage = {
                url: url,
                name: `${randomTopic.charAt(0).toUpperCase() + randomTopic.slice(1)} View`,
                theme: 'dark'
            };
            
            this.backgroundImages.push(newImage);
            this.currentBackgroundIndex = this.backgroundImages.length - 1;
            
            console.log('Fetched new background:', newImage.name);
        } catch (error) {
            console.error('Error fetching new background:', error);
            this.showNotification('⚠️ Could not load new background. Using existing ones.');
        }
    }
    
    downloadBackgroundImage(image) {
        // Create a download link
        const link = document.createElement('a');
        link.href = `${image.url}?w=1920&q=90&dl=${encodeURIComponent(image.name)}.jpg`;
        link.download = `${image.name.replace(/\s+/g, '_')}.jpg`;
        link.target = '_blank';
        
        // Trigger download
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        
        console.log('Downloaded background:', image.name);
    }
    
    showNotification(message) {
        // Create notification element
        const notification = document.createElement('div');
        notification.className = 'fixed top-4 right-4 bg-gray-800 border border-gray-700 rounded-lg px-6 py-3 shadow-lg z-50 animate-slide-in';
        notification.textContent = message;
        
        document.body.appendChild(notification);
        
        // Remove after 3 seconds
        setTimeout(() => {
            notification.classList.add('opacity-0', 'transition-opacity', 'duration-500');
            setTimeout(() => notification.remove(), 500);
        }, 3000);
    }
    
    // FEEDBACK SYSTEM
    async giveFeedback(itemType, itemId, sentiment) {
        const key = `${itemType}-${itemId}`;
        this.feedbackData[key] = sentiment;
        
        // Store feedback locally
        localStorage.setItem('dashboardFeedback', JSON.stringify(this.feedbackData));
        
        // Get item details for context
        let itemDetails = {};
        switch(itemType) {
            case 'todo':
                const todo = this.todos.find(t => t.id === itemId);
                if (todo) itemDetails = { title: todo.title, priority: todo.priority, source: todo.source };
                break;
            case 'event':
                const event = this.calendar.find(e => e.event_id === itemId);
                if (event) itemDetails = { title: event.summary || event.title, location: event.location, organizer: event.organizer };
                break;
            case 'email':
                const email = this.emails.find(e => e.id === itemId);
                if (email) itemDetails = { sender: email.sender, subject: email.subject, priority: email.priority, has_todos: email.has_todos };
                break;
            case 'news':
                const article = this.news.find(n => n.id === itemId);
                if (article) itemDetails = { title: article.title, source: article.source, category: article.category };
                break;
            case 'suggestion':
                const suggestion = this.aiSuggestions.find(s => s.id === itemId);
                if (suggestion) itemDetails = { title: suggestion.title, action: suggestion.action, source: suggestion.source };
                break;
            case 'vanity':
                const alert = this.vanityAlerts.find(v => v.id === itemId);
                if (alert) itemDetails = { title: alert.title, type: alert.type, source: alert.source };
                break;
            case 'music':
                const music = this.musicNews.find(m => m.id === itemId);
                if (music) itemDetails = { title: music.title, artist: music.artist, type: music.type };
                break;
        }
        
        // Send to backend for AI training
        try {
            await fetch('/api/ai/training/feedback', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    item_type: itemType,
                    item_id: itemId,
                    sentiment: sentiment,
                    item_details: itemDetails,
                    timestamp: new Date().toISOString()
                })
            });
            
            console.log(`Feedback recorded: ${itemType} ${itemId} - ${sentiment}`);
        } catch (error) {
            console.error('Error sending feedback:', error);
        }
        
        // Re-render the appropriate section to update button states
        switch(itemType) {
            case 'todo':
                this.renderTodos();
                break;
            case 'event':
                this.renderCalendar();
                break;
            case 'email':
                this.renderEmails();
                break;
            case 'news':
                this.renderNews();
                break;
            case 'suggestion':
                this.renderAISuggestions();
                break;
            case 'vanity':
                this.renderVanityAlerts();
                break;
            case 'music':
                this.renderMusicNews();
                break;
        }
    }
    
    async markEmailAsSafe(senderEmail) {
        try {
            const response = await fetch('/api/email/mark-safe', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    sender_email: senderEmail,
                    reason: 'User marked as safe from dashboard'
                })
            });
            
            if (response.ok) {
                console.log(`Marked ${senderEmail} as safe`);
                // Reload emails to update UI
                await this.loadEmails(true);
                
                // Show success message
                alert(`✓ ${senderEmail} has been added to your safe senders list. Future emails from this sender will be trusted.`);
            } else {
                throw new Error('Failed to mark sender as safe');
            }
        } catch (error) {
            console.error('Error marking email as safe:', error);
            alert('Failed to mark sender as safe. Please try again.');
        }
    }
    
    // Smart Email Tagging based on feedback patterns
    analyzeEmailTags() {
        const emailFeedback = {};
        
        // Group feedback by sender domain
        Object.entries(this.feedbackData).forEach(([key, sentiment]) => {
            if (key.startsWith('email-')) {
                const emailId = key.substring(6);
                const email = this.emails.find(e => e.id === emailId);
                if (email) {
                    const domain = email.sender.split('@')[1] || email.sender;
                    if (!emailFeedback[domain]) {
                        emailFeedback[domain] = { likes: 0, dislikes: 0, neutral: 0 };
                    }
                    
                    if (sentiment === 'like') emailFeedback[domain].likes++;
                    else if (sentiment === 'down') emailFeedback[domain].dislikes++;
                    else emailFeedback[domain].neutral++;
                }
            }
        });
        
        // Generate smart tags based on patterns
        const smartTags = {};
        Object.entries(emailFeedback).forEach(([domain, counts]) => {
            const total = counts.likes + counts.dislikes + counts.neutral;
            if (total >= 3) { // Need at least 3 feedbacks to establish pattern
                if (counts.likes / total > 0.7) {
                    smartTags[domain] = '⭐ Important';
                } else if (counts.dislikes / total > 0.7) {
                    smartTags[domain] = '🚫 Spam';
                } else if (counts.neutral / total > 0.7) {
                    smartTags[domain] = '📰 Newsletter';
                }
            }
        });
        
        return smartTags;
    }
    
    getSmartTagForEmail(email) {
        const smartTags = this.analyzeEmailTags();
        const domain = email.sender.split('@')[1] || email.sender;
        return smartTags[domain] || null;
    }
    
    loadFeedbackFromStorage() {
        const stored = localStorage.getItem('dashboardFeedback');
        if (stored) {
            try {
                this.feedbackData = JSON.parse(stored);
            } catch (error) {
                console.error('Error loading feedback:', error);
            }
        }
    }
    
    // ── Servers ──────────────────────────────────────────────────────────────

    async loadServers(retryCount = 0, options = {}) {
        const container = document.getElementById('servers-content');
        if (!container) return;

        const includeRemote = document.getElementById('include-remote-servers')?.checked || false;
        const params = new URLSearchParams();
        if (includeRemote) params.set('include_remote', 'true');

        if (!options.silent) {
            container.innerHTML = `
                <div class="flex items-center gap-3 py-8 text-gray-400">
                    <svg class="animate-spin h-5 w-5" fill="none" viewBox="0 0 24 24">
                        <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                        <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z"></path>
                    </svg>
                    <span>Scanning ports…</span>
                </div>`;
        }

        try {
            const r    = await fetch(`/api/servers?${params}`);
            const data = await r.json();

            if (!data.success) throw new Error(data.error || 'Server discovery failed');

            const servers = data.servers || [];
            if (!servers.length) {
                container.innerHTML = `
                    <div class="flex flex-col items-center py-12 text-gray-500">
                        <span class="text-4xl mb-3">🔇</span>
                        <p class="text-sm">No web servers detected on ports 8000–9000.</p>
                    </div>`;
                return;
            }

            container.innerHTML = servers.map(s => this._renderServerCard(s)).join('');
        } catch (e) {
            console.error('loadServers error:', e);
            if (retryCount < 1) {
                setTimeout(() => this.loadServers(retryCount + 1, { silent: true }), 2000);
            } else {
                container.innerHTML = `<p class="text-red-400 text-sm">Failed to load servers: ${this._escHtml(e.message)}</p>`;
            }
        }
    }

    _renderServerCard(s) {
        const statusColor = s.status === 'running' ? 'green' : s.status === 'stopped' ? 'red' : 'yellow';
        const memMb = s.memory_mb != null ? `${Math.round(s.memory_mb)} MB` : '—';
        const cpu   = s.cpu_percent != null ? `${s.cpu_percent.toFixed(1)}%` : '—';
        const pid   = s.pid ? `PID ${s.pid}` : '—';
        const remote = s.host && s.host !== 'localhost' && s.host !== '127.0.0.1';
        const hostLabel = remote ? `${s.host}:${s.port}` : `localhost:${s.port}`;

        const openHref = `http://${s.host || 'localhost'}:${s.port}`;

        return `
        <div class="bg-gray-800 border border-gray-700 rounded-xl p-5 mb-4 flex flex-wrap items-start gap-4">
            <!-- Status dot + name -->
            <div class="flex items-center gap-3 min-w-48">
                <span class="h-3 w-3 rounded-full bg-${statusColor}-400 mt-1 shrink-0"></span>
                <div>
                    <p class="font-semibold text-white">${this._escHtml(s.name || s.command || hostLabel)}</p>
                    <p class="text-xs text-gray-400 font-mono">${this._escHtml(hostLabel)}</p>
                </div>
            </div>

            <!-- Stats -->
            <div class="flex flex-wrap gap-4 text-xs text-gray-400 flex-1">
                <span title="Process ID">🆔 ${this._escHtml(pid)}</span>
                <span title="CPU">⚡ ${this._escHtml(cpu)}</span>
                <span title="Memory">🧠 ${this._escHtml(memMb)}</span>
                ${s.command ? `<span class="font-mono truncate max-w-xs" title="${this._escHtml(s.command)}">$ ${this._escHtml(s.command.slice(0, 60))}</span>` : ''}
                <span class="px-2 py-0.5 bg-${statusColor}-900 text-${statusColor}-300 rounded">${this._escHtml(s.status || 'unknown')}</span>
            </div>

            <!-- Actions -->
            <div class="flex gap-2 shrink-0">
                <a href="${this._escHtml(openHref)}" target="_blank"
                   class="px-3 py-1.5 bg-blue-700 hover:bg-blue-600 text-white text-xs rounded font-semibold">
                    🌐 Open
                </a>
                ${s.can_control && s.status === 'running' ? `
                <button onclick="window.dataLoader && dataLoader.stopServer(${s.port})"
                        class="px-3 py-1.5 bg-red-800 hover:bg-red-700 text-white text-xs rounded font-semibold">
                    ⏹ Stop
                </button>
                <button onclick="window.dataLoader && dataLoader.restartServer(${s.port})"
                        class="px-3 py-1.5 bg-yellow-700 hover:bg-yellow-600 text-white text-xs rounded font-semibold">
                    🔄 Restart
                </button>` : ''}
            </div>
        </div>`;
    }

    async stopServer(port) {
        if (!confirm(`Stop server on port ${port}?`)) return;
        try {
            const r    = await fetch(`/api/servers/${port}/stop`, { method: 'POST' });
            const data = await r.json();
            if (data.success) {
                this.showNotification(`✅ Server on port ${port} stopped`, 'success');
                setTimeout(() => this.loadServers(0, { silent: true }), 800);
            } else {
                this.showNotification(data.error || 'Failed to stop server', 'error');
            }
        } catch (e) {
            this.showNotification('Failed to stop server', 'error');
        }
    }

    async restartServer(port) {
        if (!confirm(`Restart server on port ${port}?`)) return;
        try {
            const r    = await fetch(`/api/servers/${port}/restart`, { method: 'POST' });
            const data = await r.json();
            if (data.success) {
                this.showNotification(`✅ Server on port ${port} restarting…`, 'success');
                setTimeout(() => this.loadServers(0, { silent: true }), 2000);
            } else {
                this.showNotification(data.error || 'Failed to restart server', 'error');
            }
        } catch (e) {
            this.showNotification('Failed to restart server', 'error');
        }
    }

    toggleRemoteServers(checked) {
        this.loadServers(0, { force: true });
    }

    // ── Diagnostics ──────────────────────────────────────────────────────────

    switchDiagTab(tab) {
        const tabs = ['events', 'review', 'suggest', 'logs', 'ask'];
        tabs.forEach(t => {
            const btn   = document.getElementById(`diag-tab-${t}`);
            const panel = document.getElementById(`diag-panel-${t}`);
            if (!btn || !panel) return;
            const active = t === tab;
            panel.classList.toggle('hidden', !active);
            if (active) {
                btn.classList.add('bg-gray-700', 'text-white');
                btn.classList.remove('text-gray-400');
            } else {
                btn.classList.remove('bg-gray-700', 'text-white');
                btn.classList.add('text-gray-400');
            }
        });
        if (tab === 'events') this.loadDiagnostics();
        if (tab === 'logs')   this.loadDiagLogs();
    }

    // ── Report a JS / runtime error to the backend ──────────────────────────
    async reportErrorToDiag(message, stack = '', module = 'frontend', autoAnalyze = true) {
        try {
            const r = await fetch('/api/diagnostics/report', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    title: message.slice(0, 120),
                    module,
                    source: 'js_runtime',
                    message,
                    stack,
                    auto_analyze: autoAnalyze
                })
            });
            const data = await r.json();
            return data;
        } catch (e) {
            console.warn('[diag] Failed to report error to backend:', e);
            return null;
        }
    }

    // ── Events tab (rich rendering) ──────────────────────────────────────────
    async loadDiagnostics() {
        const container = document.getElementById('diagnostics-content');
        if (!container) return;
        container.innerHTML = '<p class="text-gray-500 text-sm animate-pulse">Loading events…</p>';
        try {
            const r    = await fetch('/api/diagnostics/events?limit=50');
            const data = await r.json();
            const events = data.events || [];
            if (!events.length) {
                container.innerHTML = `
                    <div class="flex flex-col items-center justify-center py-12 text-gray-500">
                        <span class="text-4xl mb-3">✅</span>
                        <p class="text-sm">No diagnostic events recorded yet.</p>
                        <p class="text-xs mt-1 text-gray-600">Errors detected at runtime will appear here with AI analysis.</p>
                    </div>`;
                return;
            }
            container.innerHTML = events.map(ev => this._renderDiagEventCard(ev)).join('');
        } catch (e) {
            console.error('loadDiagnostics error:', e);
            container.innerHTML = '<p class="text-red-400 text-sm">Failed to load events.</p>';
        }
    }

    _renderDiagEventCard(ev) {
        const d = ev.diagnosis || {};
        const confidence = d.confidence || '';
        const confColor = { high: 'green', medium: 'yellow', low: 'red' }[confidence] || 'gray';
        const status = ev.status || 'reported';
        const statusColor = { diagnosed: 'blue', pr_created: 'green', fix_planned: 'purple', reported: 'yellow' }[status] || 'gray';
        const canFix = d.can_auto_fix && (d.code_fixes || []).length > 0;
        const ts = ev.created_at ? new Date(ev.created_at).toLocaleString() : '';

        const causesHtml = (d.likely_causes || []).map(c =>
            `<li class="text-xs text-gray-300 ml-3 list-disc">${this._escHtml(c)}</li>`
        ).join('');

        const stepsHtml = (d.manual_steps || []).map(s =>
            `<li class="text-xs text-gray-300 ml-3 list-disc">${this._escHtml(s)}</li>`
        ).join('');

        const actionsHtml = (d.repair_actions || []).map(a => {
            if (a.key === 'apply_code_fix') return ''; // handled separately
            return `<button onclick="window.dataLoader && dataLoader.approveDiagRepair('${this._escHtml(ev.id)}','${a.key}','${this._escHtml(a.module||'')}')"
                            class="px-3 py-1.5 bg-blue-700 hover:bg-blue-600 text-white text-xs rounded font-semibold"
                            title="${this._escHtml(a.description)}">
                        ${this._escHtml(a.label)}
                    </button>`;
        }).join('');

        const fixesHtml = (d.code_fixes || []).map((f, i) => `
            <div class="mt-2 border border-gray-600 rounded-lg overflow-hidden text-xs">
                <div class="flex items-center gap-2 px-3 py-1.5 bg-gray-700">
                    <span class="font-mono text-purple-300">${this._escHtml(f.file)}</span>
                    <span class="text-gray-400 flex-1">${this._escHtml(f.description)}</span>
                </div>
                <div class="grid grid-cols-2 divide-x divide-gray-600">
                    <div class="p-2 bg-red-950 font-mono whitespace-pre-wrap text-red-200 max-h-48 overflow-y-auto">${this._escHtml(f.old_snippet)}</div>
                    <div class="p-2 bg-green-950 font-mono whitespace-pre-wrap text-green-200 max-h-48 overflow-y-auto">${this._escHtml(f.new_snippet)}</div>
                </div>
            </div>`).join('');

        const prBadge = ev.pr ? `<a href="${this._escHtml(ev.pr.url)}" target="_blank"
            class="px-2 py-0.5 bg-green-800 text-green-200 text-xs rounded hover:bg-green-700">
            PR #${ev.pr.number} ↗</a>` : '';

        return `
        <div id="diag-ev-${this._escHtml(ev.id)}" class="mb-4 rounded-xl border border-gray-700 bg-gray-800 overflow-hidden">
            <!-- Header -->
            <div class="flex flex-wrap items-center gap-2 px-4 py-3 bg-gray-700 cursor-pointer"
                 onclick="document.getElementById('diag-body-${this._escHtml(ev.id)}').classList.toggle('hidden')">
                <span class="text-xs font-mono text-gray-400">${ts}</span>
                <span class="px-2 py-0.5 bg-${statusColor}-800 text-${statusColor}-200 text-xs rounded">${status}</span>
                ${confidence ? `<span class="px-2 py-0.5 bg-${confColor}-900 text-${confColor}-300 text-xs rounded">${confidence} confidence</span>` : ''}
                <span class="flex-1 text-sm font-semibold text-white truncate">${this._escHtml(ev.title || ev.message || 'Event')}</span>
                <span class="text-xs text-gray-400">${this._escHtml(ev.module || '')}</span>
                ${prBadge}
                <span class="text-gray-500 text-xs ml-1">▼</span>
            </div>

            <!-- Body -->
            <div id="diag-body-${this._escHtml(ev.id)}" class="">
                <div class="px-4 pt-3 pb-1">
                    <!-- Error message + stack -->
                    <p class="text-sm text-red-300 font-mono break-words mb-1">${this._escHtml(ev.message || '')}</p>
                    ${ev.stack ? `<pre class="text-xs text-gray-500 bg-gray-900 rounded p-2 overflow-x-auto max-h-28 mb-2">${this._escHtml(ev.stack)}</pre>` : ''}
                </div>

                ${d.summary ? `
                <div class="px-4 py-2 border-t border-gray-700">
                    <p class="text-xs uppercase text-gray-500 font-semibold mb-1">AI Analysis</p>
                    <p class="text-sm text-gray-200">${this._escHtml(d.summary)}</p>
                    ${causesHtml ? `<ul class="mt-2">${causesHtml}</ul>` : ''}
                </div>` : ''}

                ${fixesHtml ? `
                <div class="px-4 py-2 border-t border-gray-700">
                    <p class="text-xs uppercase text-gray-500 font-semibold mb-1">Proposed Code Changes</p>
                    <p class="text-xs text-gray-500 mb-1">Left = current code &nbsp;|&nbsp; Right = replacement</p>
                    ${fixesHtml}
                </div>` : ''}

                ${stepsHtml ? `
                <div class="px-4 py-2 border-t border-gray-700">
                    <p class="text-xs uppercase text-gray-500 font-semibold mb-1">Manual Steps</p>
                    <ul>${stepsHtml}</ul>
                </div>` : ''}

                <!-- Actions -->
                <div class="px-4 py-3 border-t border-gray-700 flex flex-wrap gap-2 items-center">
                    ${actionsHtml}
                    ${canFix && !ev.pr ? `
                    <button onclick="window.dataLoader && dataLoader.applyDiagFix('${this._escHtml(ev.id)}')"
                            class="px-3 py-1.5 bg-purple-700 hover:bg-purple-600 text-white text-xs rounded font-semibold">
                        ✅ Approve &amp; Apply Code Fix → PR
                    </button>` : ''}
                    ${!d.summary ? `
                    <button onclick="window.dataLoader && dataLoader.reDiagnoseEvent('${this._escHtml(ev.id)}')"
                            class="px-3 py-1.5 bg-gray-600 hover:bg-gray-500 text-white text-xs rounded font-semibold">
                        🔍 Analyze with AI
                    </button>` : ''}
                    <span class="text-xs text-gray-600 font-mono ml-auto">${this._escHtml(ev.id)}</span>
                </div>
            </div>
        </div>`;
    }

    async approveDiagRepair(eventId, actionKey, module) {
        if (!confirm(`Run repair action "${actionKey}" for event ${eventId}?`)) return;
        try {
            const r = await fetch('/api/diagnostics/repair', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ event_id: eventId, action_key: actionKey, module, approved: true })
            });
            const data = await r.json();
            if (data.success) {
                this.showNotification(data.message || '✅ Repair action completed', 'success');
                setTimeout(() => this.loadDiagnostics(), 500);
            } else {
                this.showNotification(data.error || 'Repair failed', 'error');
            }
        } catch (e) {
            this.showNotification('Repair request failed', 'error');
        }
    }

    async applyDiagFix(eventId) {
        if (!confirm(`Apply AI-generated code fix for event ${eventId} and create a GitHub PR?\n\nThis will modify source files. Review the diff above before continuing.`)) return;
        const card = document.getElementById(`diag-ev-${eventId}`);
        const btn  = card?.querySelector('button[onclick*="applyDiagFix"]');
        if (btn) { btn.disabled = true; btn.textContent = '⏳ Applying…'; }
        try {
            const r = await fetch('/api/diagnostics/apply-fix', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ event_id: eventId, approved: true })
            });
            const data = await r.json();
            if (data.success) {
                this.showNotification(`✅ PR created: ${data.pr_url || ''}`, 'success');
                setTimeout(() => this.loadDiagnostics(), 800);
            } else {
                this.showNotification(data.error || 'Apply fix failed', 'error');
                if (btn) { btn.disabled = false; btn.textContent = '✅ Approve & Apply Code Fix → PR'; }
            }
        } catch (e) {
            this.showNotification('Apply fix request failed', 'error');
            if (btn) { btn.disabled = false; btn.textContent = '✅ Approve & Apply Code Fix → PR'; }
        }
    }

    async reDiagnoseEvent(eventId) {
        const card = document.getElementById(`diag-ev-${eventId}`);
        const btn  = card?.querySelector('button[onclick*="reDiagnoseEvent"]');
        if (btn) { btn.disabled = true; btn.textContent = '⏳ Analyzing…'; }
        try {
            // Re-report the event to trigger AI analysis
            const evData = await fetch('/api/diagnostics/events?limit=200').then(r => r.json());
            const ev = (evData.events || []).find(e => e.id === eventId);
            if (!ev) { this.showNotification('Event not found', 'error'); return; }
            await this.reportErrorToDiag(ev.message || ev.title || 'Unknown', ev.stack || '', ev.module || 'general');
            this.showNotification('Re-analysis complete', 'success');
            setTimeout(() => this.loadDiagnostics(), 600);
        } catch (e) {
            this.showNotification('Re-diagnosis failed', 'error');
        } finally {
            if (btn) { btn.disabled = false; btn.textContent = '🔍 Analyze with AI'; }
        }
    }

    // ── Review tab ───────────────────────────────────────────────────────────
    async runManualDiagnosticReview() {
        const btn    = document.getElementById('diag-review-btn');
        const module = document.getElementById('diagnostics-module')?.value || 'general';
        const notes  = document.getElementById('diagnostics-notes')?.value || '';
        if (btn) { btn.disabled = true; btn.textContent = '⏳ Running…'; }
        try {
            const r    = await fetch('/api/diagnostics/review', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ module, notes })
            });
            const data = await r.json();
            if (data.success) {
                this.showNotification('✅ Review complete – see Events tab', 'success');
                this.switchDiagTab('events');
            } else {
                this.showNotification(data.error || 'Review failed', 'error');
            }
        } catch (e) {
            this.showNotification('Review request failed', 'error');
        } finally {
            if (btn) { btn.disabled = false; btn.textContent = 'Run AI Diagnostic Review'; }
        }
    }

    // ── Suggest-fix tab ──────────────────────────────────────────────────────
    async runSuggestFix() {
        const btn     = document.getElementById('suggest-fix-btn');
        const module  = document.getElementById('suggest-module')?.value || 'general';
        const eventId = document.getElementById('suggest-event-id')?.value || '';
        const text    = document.getElementById('suggest-text')?.value || '';
        const resultEl = document.getElementById('suggest-fix-result');
        if (!text.trim()) { this.showNotification('Please describe the fix', 'warning'); return; }
        if (btn) { btn.disabled = true; btn.textContent = '⏳ Generating…'; }
        if (resultEl) resultEl.innerHTML = '<p class="text-gray-400 text-sm">⏳ Asking AI to generate a fix plan…</p>';
        try {
            const r    = await fetch('/api/diagnostics/suggest-fix', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ module, event_id: eventId, suggestion: text })
            });
            const data = await r.json();
            if (!resultEl) return;
            if (data.success && data.fix_plan) {
                const fp = data.fix_plan;
                const confColor = { high: 'green', medium: 'yellow', low: 'red' }[fp.confidence] || 'gray';
                const fixesHtml = (fp.code_fixes || []).map(f => `
                    <div class="border border-gray-600 rounded overflow-hidden mt-2 text-xs">
                        <div class="flex items-center gap-2 px-3 py-1 bg-gray-700">
                            <span class="font-mono text-purple-300">${this._escHtml(f.file)}</span>
                            <span class="text-gray-400">${this._escHtml(f.description)}</span>
                        </div>
                        <div class="grid grid-cols-2 divide-x divide-gray-600">
                            <div class="p-2 bg-red-950 font-mono whitespace-pre-wrap text-red-200 max-h-40 overflow-y-auto">${this._escHtml(f.old_snippet)}</div>
                            <div class="p-2 bg-green-950 font-mono whitespace-pre-wrap text-green-200 max-h-40 overflow-y-auto">${this._escHtml(f.new_snippet)}</div>
                        </div>
                    </div>`).join('');
                const risksHtml = (fp.risks || []).map(r => `<li class="text-xs text-yellow-300 ml-3 list-disc">${this._escHtml(r)}</li>`).join('');
                const stepsHtml = (fp.manual_steps || []).map(s => `<li class="text-xs text-gray-300 ml-3 list-disc">${this._escHtml(s)}</li>`).join('');
                resultEl.innerHTML = `
                    <div class="bg-gray-900 border border-gray-700 rounded-xl p-4">
                        <div class="flex items-center gap-3 mb-3">
                            <span class="text-sm font-semibold text-white">${this._escHtml(fp.summary)}</span>
                            <span class="px-2 py-0.5 bg-${confColor}-900 text-${confColor}-300 text-xs rounded">${fp.confidence} confidence</span>
                        </div>
                        ${fixesHtml ? `<div class="mb-2"><p class="text-xs uppercase text-gray-500 font-semibold mb-1">Code Changes</p><p class="text-xs text-gray-500 mb-1">Left = current &nbsp;|&nbsp; Right = replacement</p>${fixesHtml}</div>` : '<p class="text-xs text-yellow-400 mb-2">⚠ AI could not produce concrete code changes. Check summary for manual steps.</p>'}
                        ${risksHtml ? `<div class="mt-3"><p class="text-xs uppercase text-gray-500 font-semibold mb-1">Risks</p><ul>${risksHtml}</ul></div>` : ''}
                        ${stepsHtml ? `<div class="mt-2"><p class="text-xs uppercase text-gray-500 font-semibold mb-1">Manual Steps</p><ul>${stepsHtml}</ul></div>` : ''}
                        ${(fp.code_fixes || []).length > 0 ? `
                        <div class="mt-4 flex gap-2">
                            <button onclick="window.dataLoader && dataLoader.applyDiagFix('${this._escHtml(data.event_id || eventId)}')"
                                    class="px-4 py-2 bg-purple-700 hover:bg-purple-600 text-white text-xs rounded font-semibold">
                                ✅ Approve &amp; Apply Fix → PR
                            </button>
                            <button onclick="document.getElementById('suggest-fix-result').innerHTML=''"
                                    class="px-3 py-2 bg-gray-700 hover:bg-gray-600 text-xs rounded">Dismiss</button>
                        </div>` : ''}
                    </div>`;
            } else {
                resultEl.innerHTML = `<p class="text-red-400 text-sm">${this._escHtml(data.error || 'Failed to generate fix plan')}</p>`;
            }
        } catch (e) {
            if (resultEl) resultEl.innerHTML = '<p class="text-red-400 text-sm">Failed to generate fix plan.</p>';
        } finally {
            if (btn) { btn.disabled = false; btn.textContent = '🤖 Generate Fix Plan'; }
        }
    }

    // ── Logs tab ─────────────────────────────────────────────────────────────
    async loadDiagLogs() {
        const viewer = document.getElementById('log-viewer');
        const info   = document.getElementById('log-files-info');
        const level  = document.getElementById('log-level-filter')?.value  || '';
        const mod    = document.getElementById('log-module-filter')?.value || '';
        const lines  = document.getElementById('log-lines-count')?.value   || '200';
        if (viewer) viewer.innerHTML = '<span class="text-gray-500">Loading…</span>';
        try {
            const params = new URLSearchParams({ lines });
            if (level) params.set('level', level);
            if (mod)   params.set('module', mod);
            const r    = await fetch(`/api/diagnostics/logs?${params}`);
            const data = await r.json();
            const logFiles = data.log_files || [];
            if (info) info.textContent = logFiles.length
                ? `Files: ${logFiles.map(f => `${f.path} (${f.size_kb} KB)`).join(', ')}`
                : '';
            if (viewer) {
                const rawLines = data.lines || [];
                if (!rawLines.length) {
                    viewer.innerHTML = '<span class="text-gray-500">No log entries found.</span>';
                } else {
                    viewer.innerHTML = rawLines.map(line => {
                        const escaped = this._escHtml(typeof line === 'string' ? line : JSON.stringify(line));
                        const color = escaped.includes('ERROR')   ? 'text-red-300' :
                                      escaped.includes('WARNING') ? 'text-yellow-300' :
                                      escaped.includes('INFO')    ? 'text-blue-300' : 'text-gray-300';
                        return `<span class="${color}">${escaped}</span>`;
                    }).join('\n');
                    viewer.scrollTop = viewer.scrollHeight;
                }
            }
        } catch (e) {
            if (viewer) viewer.innerHTML = '<span class="text-red-400">Failed to load logs.</span>';
        }
    }

    async clearDiagLogs() {
        if (!confirm('Clear the dashboard log file? This cannot be undone.')) return;
        try {
            await fetch('/api/diagnostics/logs/clear', {
                method:'POST',
                headers:{'Content-Type':'application/json'},
                body: JSON.stringify({ confirmed: true })
            });
            this.showNotification('Log cleared', 'success');
            await this.loadDiagLogs();
        } catch (e) {
            this.showNotification('Failed to clear logs', 'error');
        }
    }

    async runDiagnosticRollback() {
        if (!confirm('Roll back the last applied diagnostic patch?')) return;
        try {
            const r    = await fetch('/api/diagnostics/rollback', {
                method:'POST',
                headers:{'Content-Type':'application/json'},
                body: JSON.stringify({ confirmed: true })
            });
            const data = await r.json();
            if (data.success) {
                this.showNotification(data.message || '↩ Rollback complete', 'success');
            } else {
                this.showNotification(data.error || 'Rollback failed', 'error');
            }
        } catch (e) {
            this.showNotification('Rollback failed', 'error');
        }
    }

    // ── Ask AI tab ───────────────────────────────────────────────────────────
    async askDiagAI() {
        const input    = document.getElementById('diag-ask-input');
        const output   = document.getElementById('diag-ask-output');
        const btn      = document.getElementById('diag-ask-btn');
        const question = input?.value?.trim();
        if (!question) { this.showNotification('Please enter a question', 'warning'); return; }
        if (btn)    { btn.disabled = true; btn.textContent = '⏳ Asking…'; }
        if (output) output.innerHTML = '<p class="text-gray-400 text-sm animate-pulse">⏳ Waiting for AI response…</p>';
        try {
            const r    = await fetch('/api/ai/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ message: question, context: 'diagnostics' })
            });
            const data = await r.json();
            const reply = data.response || data.message || data.content || JSON.stringify(data);
            if (output) {
                output.innerHTML = `<div class="bg-gray-900 border border-gray-700 rounded-lg p-4 text-sm text-gray-200 whitespace-pre-wrap">${this._escHtml(reply)}</div>
                    <div class="flex gap-2 mt-2">
                        <button onclick="window.dataLoader && dataLoader._sendDiagQuestionToReport('${this._escHtml(question)}')"
                                class="px-3 py-1 bg-yellow-700 hover:bg-yellow-600 text-xs rounded font-semibold">
                            🔍 Send to Self-Diagnostics for Code Fix
                        </button>
                    </div>`;
            }
        } catch (e) {
            if (output) output.innerHTML = '<p class="text-red-400 text-sm">Failed to get AI response. Make sure Ollama is running.</p>';
        } finally {
            if (btn) { btn.disabled = false; btn.textContent = '🤖 Ask AI'; }
        }
    }

    async _sendDiagQuestionToReport(question) {
        const data = await this.reportErrorToDiag(question, '', 'user_reported', true);
        if (data?.success) {
            this.showNotification('Sent to Self-Diagnostics – check Events tab', 'success');
            this.switchDiagTab('events');
        } else {
            this.showNotification(data?.error || 'Failed to send', 'error');
        }
    }

    _escHtml(str) {
        if (!str) return '';
        return String(str).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
    }

    // Initialize dashboard on page load
    async init() {
        try {
            console.log('Initializing dashboard data loader...');
            
            // Load initial user profile
            await this.loadUserProfile();
            
            // Load all data in parallel
            await Promise.all([
                this.loadTodos().catch(e => console.warn('Error loading todos:', e)),
                this.loadCalendar().catch(e => console.warn('Error loading calendar:', e)),
                this.loadEmails().catch(e => console.warn('Error loading emails:', e)),
                this.loadGithub().catch(e => console.warn('Error loading github:', e)),
                this.loadNews().catch(e => console.warn('Error loading news:', e)),
                this.loadWeather().catch(e => console.warn('Error loading weather:', e))
            ]);

            this.updateAllCounts();
            
            console.log('Dashboard initialization complete');
        } catch (error) {
            console.error('Error during dashboard initialization:', error);
        }
    }
})();

// Global instance
console.log('✅ DashboardDataLoader class instantiated, window.dataLoader:', typeof window.dataLoader);

// Dashboard Management Functions
function showAddDashboardModal(dashboardData = null) {
    const modal = document.getElementById('add-dashboard-modal');
    const titleText = document.getElementById('modal-title-text');
    const saveBtnText = document.getElementById('save-btn-text');
    const form = document.getElementById('add-dashboard-form');
    
    if (dashboardData) {
        // Edit mode
        titleText.textContent = 'Edit Dashboard Configuration';
        saveBtnText.textContent = 'Save Changes';
        
        // Populate form with existing data
        document.getElementById('dashboard-id').value = dashboardData.id || '';
        document.getElementById('dashboard-name').value = dashboardData.name || '';
        document.getElementById('dashboard-path').value = dashboardData.path || '';
        document.getElementById('dashboard-type').value = dashboardData.type || 'forgeweb';
        document.getElementById('dashboard-port').value = dashboardData.port || '';
        document.getElementById('dashboard-command').value = dashboardData.start_command || '';
        document.getElementById('dashboard-production-url').value = dashboardData.production_url || '';
        document.getElementById('dashboard-api-url').value = dashboardData.api_url || '';
        document.getElementById('dashboard-active').checked = dashboardData.active !== false;
    } else {
        // Add mode
        titleText.textContent = 'Add Marketing Dashboard / Website';
        saveBtnText.textContent = 'Add Dashboard';
        form.reset();
        document.getElementById('dashboard-active').checked = true;
        
        // Set default type to forgeweb
        document.getElementById('dashboard-type').value = 'forgeweb';
        updateProjectTypeDefaults();
    }
    
    modal.classList.remove('hidden');
    modal.classList.add('flex');
}

function closeAddDashboardModal() {
    const modal = document.getElementById('add-dashboard-modal');
    modal.classList.add('hidden');
    modal.classList.remove('flex');
    // Reset form
    document.getElementById('add-dashboard-form').reset();
    document.getElementById('dashboard-id').value = '';
}

function updateProjectTypeDefaults() {
    const type = document.getElementById('dashboard-type').value;
    const portInput = document.getElementById('dashboard-port');
    const commandInput = document.getElementById('dashboard-command');
    const pathInput = document.getElementById('dashboard-path').value || '';
    
    // Default ports and commands for each type
    const defaults = {
        'forgeweb': {
            port: 8000,
            command: `python3 -m http.server 8000`
        },
        'forgemarket': {
            port: 8001,
            command: `python3 -m http.server 8001`
        },
        'flask': {
            port: 5000,
            command: `python app.py`
        },
        'fastapi': {
            port: 8000,
            command: `uvicorn main:app --reload --port 8000`
        },
        'react': {
            port: 3000,
            command: `npm start`
        },
        'vue': {
            port: 8080,
            command: `npm run serve`
        },
        'static': {
            port: 8000,
            command: `python3 -m http.server 8000`
        },
        'streamlit': {
            port: 8501,
            command: `streamlit run streamlit_app.py --server.port 8501`
        }
    };
    
    const config = defaults[type] || { port: 8000, command: '' };
    
    // Only update if fields are empty
    if (!portInput.value) {
        portInput.value = config.port;
    }
    if (!commandInput.value) {
        // Add path to command if available
        if (pathInput && config.command) {
            commandInput.value = `cd ${pathInput} && ${config.command}`;
        } else {
            commandInput.value = config.command;
        }
    }
}

function browseDirectory() {
    // Provide helpful path suggestions
    const pathInput = document.getElementById('dashboard-path');
    const homeDir = process.env.HOME || '~';
    const suggestions = [
        `${homeDir}/Projects/marketing/websites/`,
        `${homeDir}/Projects/marketing/`,
        `${homeDir}/Projects/`,
        `${homeDir}/`
    ];
    
    const suggestion = prompt(
        'Enter the full path to your project directory:\n\n' +
        'Common locations:\n' +
        suggestions.join('\n') +
        '\n\nOr paste your custom path below:',
        pathInput.value || suggestions[0]
    );
    
    if (suggestion) {
        pathInput.value = suggestion.trim();
        updateProjectTypeDefaults();
    }
}

async function saveDashboard() {
    const dashboardId = document.getElementById('dashboard-id').value;
    const path = document.getElementById('dashboard-path').value.trim();
    const name = document.getElementById('dashboard-name').value.trim();
    
    if (!path) {
        alert('Please enter a project directory path');
        return;
    }
    
    if (!name) {
        alert('Please enter a project name');
        return;
    }
    
    const data = {
        id: dashboardId || null,
        name: name,
        path: path,
        type: document.getElementById('dashboard-type').value,
        port: document.getElementById('dashboard-port').value ? parseInt(document.getElementById('dashboard-port').value) : null,
        start_command: document.getElementById('dashboard-command').value.trim() || null,
        production_url: document.getElementById('dashboard-production-url').value.trim() || null,
        api_url: document.getElementById('dashboard-api-url').value.trim() || null,
        active: document.getElementById('dashboard-active').checked
    };
    
    try {
        const endpoint = dashboardId ? '/api/dashboards/save' : '/api/dashboards/add';
        const response = await fetch(endpoint, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(data)
        });
        
        const result = await response.json();
        
        if (result.success || response.ok) {
            showNotification(
                dashboardId ? 'Dashboard updated successfully!' : 'Dashboard added successfully!',
                'success'
            );
            closeAddDashboardModal();
            
            // Reload dashboards section
            if (window.dataLoader) {
                await dataLoader.loadDashboards();
            }
        } else {
            showNotification(result.message || result.detail || 'Failed to save dashboard', 'error');
        }
    } catch (error) {
        console.error('Error saving dashboard:', error);
        showNotification('Error saving dashboard: ' + error.message, 'error');
    }
}

function showNotification(message, type = 'info') {
    // Create notification element
    const notification = document.createElement('div');
    notification.className = `fixed top-4 right-4 z-50 px-6 py-4 rounded-lg shadow-lg transform transition-all duration-300 ${
        type === 'success' ? 'bg-green-600' :
        type === 'error' ? 'bg-red-600' :
        'bg-blue-600'
    } text-white`;
    notification.textContent = message;
    
    document.body.appendChild(notification);
    
    // Animate in
    setTimeout(() => {
        notification.style.transform = 'translateX(0)';
    }, 10);
    
    // Remove after 3 seconds
    setTimeout(() => {
        notification.style.transform = 'translateX(400px)';
        setTimeout(() => notification.remove(), 300);
    }, 3000);
}

// Google Authentication
window.handleGoogleAuth = async function() {
    try {
        const statusResponse = await fetch('/api/auth/google/status');
        const status = await statusResponse.json();
        
        if (status.authenticated && !status.expired && !status.needs_reconnect) {
            showNotification('✅ Already connected to Google', 'success');
            return;
        }
        
        // Open OAuth flow in popup
        const width = 500;
        const height = 600;
        const left = (screen.width - width) / 2;
        const top = (screen.height - height) / 2;
        
        const popup = window.open(
            '/auth/google',
            'GoogleAuth',
            `width=${width},height=${height},left=${left},top=${top}`
        );
        
        // Poll for popup close and check auth status
        const pollTimer = setInterval(async () => {
            if (popup.closed) {
                clearInterval(pollTimer);
                await updateGoogleAuthButton();
                showNotification('Google authentication completed!', 'success');
            }
        }, 1000);
    } catch (error) {
        console.error('Error with Google auth:', error);
        showNotification('Error connecting to Google', 'error');
    }
}

async function updateGoogleAuthButton() {
    try {
        const response = await fetch('/api/auth/google/status');
        const status = await response.json();
        
        const btn = document.getElementById('google-auth-btn');
        const text = document.getElementById('google-auth-text');
        
        if (!btn || !text) return;
        
        if (status.authenticated && !status.expired && !status.needs_reconnect) {
            btn.className = btn.className.replace('bg-blue-600 hover:bg-blue-700', 'bg-green-600 hover:bg-green-700');
            text.textContent = '✓ Google Connected';
        } else if (status.expired || status.needs_reconnect) {
            btn.className = btn.className.replace('bg-blue-600 hover:bg-blue-700', 'bg-yellow-600 hover:bg-yellow-700');
            text.textContent = status.can_modify_gmail === false ? '⚠️ Reconnect Google (Mail Access)' : '⚠️ Reconnect Google';
        } else {
            btn.className = btn.className.replace('bg-green-600 hover:bg-green-700', 'bg-blue-600 hover:bg-blue-700');
            btn.className = btn.className.replace('bg-yellow-600 hover:bg-yellow-700', 'bg-blue-600 hover:bg-blue-700');
            text.textContent = 'Connect Google';
        }
    } catch (error) {
        console.error('Error updating Google auth button:', error);
    }
}

// Dismiss Vanity Alert
async function dismissAlert(alertId) {
    try {
        const response = await fetch(`/api/vanity-alerts/${alertId}/dismiss`, {
            method: 'POST'
        });
        
        const result = await response.json();
        
        if (result.success) {
            showNotification('Alert dismissed', 'success');
            // Reload vanity alerts
            if (window.dataLoader) {
                await dataLoader.loadVanityAlerts();
            }
        } else {
            showNotification('Failed to dismiss alert', 'error');
        }
    } catch (error) {
        console.error('Error dismissing alert:', error);
        showNotification('Error dismissing alert', 'error');
    }
}

// Suggested Todos Management
async function loadSuggestedTodos() {
    try {
        const response = await fetch('/api/suggested-todos');
        const data = await response.json();
        
        if (data.success && data.suggestions && data.suggestions.length > 0) {
            renderSuggestedTodos(data.suggestions);
        } else {
            document.getElementById('suggested-todos-section').style.display = 'none';
        }
    } catch (error) {
        console.error('Error loading suggested todos:', error);
    }
}

function renderSuggestedTodos(suggestions) {
    const section = document.getElementById('suggested-todos-section');
    const list = document.getElementById('suggested-todos-list');
    
    if (!section || !list) return;
    
    const header = `
        <div class="flex flex-wrap items-center justify-between gap-2 mb-3">
            <div class="text-xs text-yellow-200">${suggestions.length} pending suggestion${suggestions.length === 1 ? '' : 's'}</div>
            <div class="flex gap-2">
                <button onclick="approveAllSuggestedTodos()"
                        class="px-3 py-1 bg-green-700 hover:bg-green-600 text-white text-xs rounded transition-colors">
                    ✓ Accept All
                </button>
                <button onclick="rejectAllSuggestedTodos()"
                        class="px-3 py-1 bg-gray-700 hover:bg-gray-600 text-white text-xs rounded transition-colors">
                    ✕ Dismiss All
                </button>
            </div>
        </div>
    `;

    const cards = suggestions.map(suggestion => {
        const sourceIcon = {
            'email': '📧',
            'calendar': '📅',
            'note': '📝',
            'default': '📌'
        }[suggestion.source] || '📌';
        
        return `
            <div class="bg-gradient-to-r from-yellow-900 to-yellow-800 rounded-lg p-4 mb-3 border border-yellow-700">
                <!-- Header with source info -->
                <div class="flex items-start justify-between gap-3 mb-3">
                    <div class="flex-1">
                        <div class="flex items-center gap-2 mb-2">
                            <span class="text-lg">${sourceIcon}</span>
                            <span class="text-xs font-semibold text-yellow-200 uppercase">${escapeHtml(suggestion.source)}</span>
                            ${suggestion.priority ? `<span class="text-xs px-2 py-1 bg-yellow-700 rounded text-yellow-100">⚡ ${suggestion.priority}</span>` : ''}
                        </div>
                        <h4 class="font-bold text-white text-lg">${escapeHtml(suggestion.title)}</h4>
                        ${suggestion.description ? `<p class="text-sm text-yellow-100 mt-2">${escapeHtml(suggestion.description)}</p>` : ''}
                    </div>
                </div>
                
                <!-- Source link button -->
                ${suggestion.source_url ? `
                    <div class="mb-3">
                        <button onclick="openSourceContent('${suggestion.id}', '${suggestion.source_url}')" 
                                class="w-full px-3 py-2 bg-yellow-700 hover:bg-yellow-600 text-white text-sm rounded transition-colors"
                                title="View original source">
                            🔗 View Original ${escapeHtml(suggestion.source_title || suggestion.source)}
                        </button>
                    </div>
                ` : ''}
                
                <!-- Action buttons -->
                <div class="flex gap-2">
                    <button onclick="approveSuggestedTodo('${suggestion.id}')" 
                            class="flex-1 px-4 py-2 bg-green-600 hover:bg-green-700 text-white font-semibold rounded transition-colors"
                            title="Add to your tasks">
                        ✓ Accept Task
                    </button>
                    <button onclick="rejectSuggestedTodo('${suggestion.id}')" 
                            class="flex-1 px-4 py-2 bg-gray-600 hover:bg-gray-700 text-white font-semibold rounded transition-colors"
                            title="Dismiss this suggestion">
                        ✕ Dismiss
                    </button>
                </div>
            </div>
        `;
    }).join('');
    
    list.innerHTML = header + cards;
    section.style.display = 'block';
}

async function bulkProcessSuggestedTodos(action) {
    try {
        const response = await fetch('/api/suggested-todos/bulk', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ action })
        });

        const result = await response.json();
        if (!response.ok || !result.success) {
            throw new Error(result.detail || result.error || 'Bulk action failed');
        }

        showNotification(`✅ ${result.message}`, 'success');
        await loadSuggestedTodos();

        if (window.dataLoader) {
            await dataLoader.loadTodos();
        }
    } catch (error) {
        console.error(`Error processing ${action} for suggestions:`, error);
        showNotification(`Error running bulk ${action}`, 'error');
    }
}

async function approveAllSuggestedTodos() {
    await bulkProcessSuggestedTodos('approve');
}

async function rejectAllSuggestedTodos() {
    await bulkProcessSuggestedTodos('reject');
}

window.approveSuggestedTodo = async function approveSuggestedTodo(suggestionId) {
    try {
        const response = await fetch(`/api/suggested-todos/${suggestionId}/approve`, {
            method: 'POST'
        });
        
        const result = await response.json();
        
        if (result.success) {
            showNotification('✅ Task approved and added!', 'success');
            await loadSuggestedTodos();
            // Reload tasks if on that section
            if (window.dataLoader) {
                await dataLoader.loadTodos();
            }
        } else {
            showNotification('Failed to approve task', 'error');
        }
    } catch (error) {
        console.error('Error approving suggestion:', error);
        showNotification('Error approving task', 'error');
    }
};

window.rejectSuggestedTodo = async function rejectSuggestedTodo(suggestionId) {
    try {
        const response = await fetch(`/api/suggested-todos/${suggestionId}/reject`, {
            method: 'POST'
        });
        
        const result = await response.json();
        
        if (result.success) {
            showNotification('✅ Suggestion dismissed', 'success');
            await loadSuggestedTodos();
        } else {
            showNotification('Failed to dismiss suggestion', 'error');
        }
    } catch (error) {
        console.error('Error rejecting suggestion:', error);
        showNotification('Error dismissing suggestion', 'error');
    }
};

window.openSourceContent = async function openSourceContent(suggestionId, sourceUrl) {
    try {
        // Create a modal to show the source content
        const modal = document.createElement('div');
        modal.className = 'fixed inset-0 bg-black bg-opacity-50 z-50 flex items-center justify-center modal-backdrop';
        modal.id = 'source-modal-' + suggestionId;
        
        modal.innerHTML = `
            <div class="bg-gray-900 rounded-lg w-11/12 h-5/6 flex flex-col modal-content shadow-2xl">
                <!-- Header -->
                <div class="flex items-center justify-between p-4 border-b border-gray-700">
                    <h3 class="text-xl font-bold text-white">Original Source</h3>
                    <button onclick="document.getElementById('source-modal-${suggestionId}').remove()" 
                            class="text-gray-400 hover:text-white text-2xl">✕</button>
                </div>
                <!-- Content -->
                <div class="flex-1 overflow-auto p-4 bg-gray-800">
                    <iframe src="${sourceUrl}" class="w-full h-full border-0" frameborder="0" sandbox="allow-same-origin"></iframe>
                </div>
            </div>
        `;
        
        document.body.appendChild(modal);
        modal.onclick = (e) => {
            if (e.target === modal) modal.remove();
        };
    } catch (error) {
        console.error('Error opening source:', error);
        showNotification('Could not open source content', 'error');
    }
};

function escapeHtml(unsafe) {
    if (!unsafe) return '';
    return unsafe
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', async () => {
    await updateGoogleAuthButton();
    await loadSuggestedTodos();
});
} catch (error) {
    console.error('❌ CRITICAL: Failed to initialize DashboardDataLoader:', error);
    console.error('Stack:', error.stack);
    // Create a minimal fallback dataLoader
    window.dataLoader = {
        loadEmails: () => console.warn('dataLoader not functional'),
        loadCalendar: () => console.warn('dataLoader not functional'),
        loadTodos: () => console.warn('dataLoader not functional'),
        loadGithub: () => console.warn('dataLoader not functional'),
        loadNews: () => console.warn('dataLoader not functional'),
        loadServers: () => console.warn('dataLoader not functional'),
        showNotification: (msg) => alert(msg),
        switchDiagTab: () => console.warn('dataLoader not functional'),
        loadDiagnostics: () => console.warn('dataLoader not functional'),
        loadDiagLogs: () => console.warn('dataLoader not functional'),
        askDiagAI: () => console.warn('dataLoader not functional')
    };
}

