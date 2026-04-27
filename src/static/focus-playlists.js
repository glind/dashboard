/**
 * Focus Playlists UI Module
 * Handles mood-based playlist generation and playback
 */

class FocusPlaylistsUI {
    constructor() {
        this.currentPlaylist = null;
        this.currentTrackIndex = 0;
        this.isPlaying = false;
        this.youtubePlayer = null;
    }

    /**
     * Initialize the Focus Playlists section
     */
    async init() {
        console.log('Initializing Focus Playlists UI...');
        
        // Create UI if not exists
        const container = document.getElementById('focus-playlists-container');
        if (!container) {
            this.createUI();
        }

        // Load mood presets
        await this.loadMoodPresets();
        
        // Load existing playlists
        await this.loadPlaylists();

        console.log('Focus Playlists UI initialized');
    }

    /**
     * Create the Focus Playlists UI structure
     */
    createUI() {
        const html = `
            <section id="focus-playlists-section" class="dashboard-section">
                <div class="section-header">
                    <h2>🎵 Focus Playlists</h2>
                    <p>Generate mood-based playlists for focused work</p>
                </div>

                <!-- Mood Selector -->
                <div id="mood-selector" class="mood-selector-grid">
                    <p class="loading-spinner">Loading moods...</p>
                </div>

                <!-- Duration Selector -->
                <div class="playlist-generator-controls">
                    <label for="duration-select">Duration (minutes):</label>
                    <select id="duration-select">
                        <option value="30">30 min</option>
                        <option value="45">45 min</option>
                        <option value="60" selected>60 min</option>
                        <option value="90">90 min</option>
                        <option value="120">120 min</option>
                    </select>
                    <button id="generate-playlist-btn" class="btn btn-primary">
                        Generate Playlist
                    </button>
                </div>

                <!-- Playlist Playback Area -->
                <div id="playlist-playback" class="playlist-playback" style="display: none;">
                    <!-- YouTube Player -->
                    <div id="youtube-player-container" class="youtube-player-container">
                        <iframe id="youtube-player" 
                                width="100%" 
                                height="480" 
                                frameborder="0" 
                                allow="autoplay; encrypted-media" 
                                allowfullscreen>
                        </iframe>
                    </div>

                    <!-- Playlist Controls -->
                    <div class="playlist-controls">
                        <button id="prev-track-btn" class="btn btn-sm">⏮ Previous</button>
                        <button id="play-pause-btn" class="btn btn-sm">▶ Play</button>
                        <button id="next-track-btn" class="btn btn-sm">Next ⏭</button>
                        <span id="track-info" class="track-info"></span>
                    </div>

                    <!-- Sync Buttons -->
                    <div class="sync-buttons">
                        <button id="sync-spotify-btn" class="btn btn-secondary" title="Save to Spotify">
                            🎵 Save to Spotify
                        </button>
                        <button id="sync-apple-music-btn" class="btn btn-secondary" title="Save to Apple Music">
                            🎶 Save to Apple Music
                        </button>
                    </div>

                    <!-- Playlist Tracks List -->
                    <div id="playlist-tracks" class="playlist-tracks"></div>
                </div>

                <!-- Saved Playlists -->
                <div id="saved-playlists" class="saved-playlists">
                    <h3>Saved Playlists</h3>
                    <div id="playlists-list" class="playlists-list">
                        <p class="loading-spinner">Loading playlists...</p>
                    </div>
                </div>
            </section>
        `;

        const container = document.createElement('div');
        container.id = 'focus-playlists-container';
        container.innerHTML = html;
        
        // Insert into dashboard
        const dashboard = document.getElementById('main-content') || document.body;
        dashboard.appendChild(container);

        // Attach event listeners
        this.attachEventListeners();
    }

    /**
     * Attach event listeners
     */
    attachEventListeners() {
        document.getElementById('generate-playlist-btn')?.addEventListener('click', 
            () => this.generatePlaylist());
        
        document.getElementById('prev-track-btn')?.addEventListener('click',
            () => this.previousTrack());
        
        document.getElementById('play-pause-btn')?.addEventListener('click',
            () => this.playPause());
        
        document.getElementById('next-track-btn')?.addEventListener('click',
            () => this.nextTrack());

        document.getElementById('sync-spotify-btn')?.addEventListener('click',
            () => this.syncToProvider('spotify'));
        
        document.getElementById('sync-apple-music-btn')?.addEventListener('click',
            () => this.syncToProvider('apple_music'));
    }

    /**
     * Load and display mood presets
     */
    async loadMoodPresets() {
        try {
            const response = await fetch('/api/focus-playlists/mood-presets');
            const data = await response.json();

            if (!data.success) {
                throw new Error(data.detail || 'Failed to load mood presets');
            }

            const container = document.getElementById('mood-selector');
            container.innerHTML = data.moods.map(mood => `
                <div class="mood-card" data-mood-id="${mood.id}">
                    <h4>${mood.name}</h4>
                    <p>${mood.description}</p>
                    <span class="energy-level">Energy: ${mood.energy_level}/10</span>
                </div>
            `).join('');

            // Add click listeners to mood cards
            document.querySelectorAll('.mood-card').forEach(card => {
                card.addEventListener('click', () => this.selectMood(card.dataset.moodId));
            });

        } catch (error) {
            console.error('Error loading mood presets:', error);
            document.getElementById('mood-selector').innerHTML = 
                `<p class="error">Error loading moods: ${error.message}</p>`;
        }
    }

    /**
     * Select a mood
     */
    selectMood(moodId) {
        // Update UI to show selected mood
        document.querySelectorAll('.mood-card').forEach(card => {
            card.classList.toggle('active', card.dataset.moodId === moodId);
        });

        // Store selected mood
        this.selectedMood = moodId;
    }

    /**
     * Generate a playlist
     */
    async generatePlaylist() {
        if (!this.selectedMood) {
            alert('Please select a mood first');
            return;
        }

        const duration = parseInt(document.getElementById('duration-select').value);
        const btn = document.getElementById('generate-playlist-btn');
        
        try {
            btn.disabled = true;
            btn.textContent = 'Generating...';

            const response = await fetch('/api/focus-playlists/generate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    mood: this.selectedMood,
                    duration_minutes: duration
                })
            });

            const data = await response.json();

            if (!data.success) {
                throw new Error(data.detail || 'Failed to generate playlist');
            }

            this.currentPlaylist = data.playlist;
            this.currentTrackIndex = 0;
            this.displayPlaylist();
            this.showNotification('✅ Playlist generated successfully!', 'success');

            // Reload playlists
            await this.loadPlaylists();

        } catch (error) {
            console.error('Error generating playlist:', error);
            this.showNotification(`❌ Error: ${error.message}`, 'error');
        } finally {
            btn.disabled = false;
            btn.textContent = 'Generate Playlist';
        }
    }

    /**
     * Display the current playlist
     */
    displayPlaylist() {
        if (!this.currentPlaylist) return;

        // Show playback area
        document.getElementById('playlist-playback').style.display = 'block';

        // Load first track
        this.loadTrack();

        // Display tracks list
        const tracksList = document.getElementById('playlist-tracks');
        tracksList.innerHTML = this.currentPlaylist.tracks.map((track, index) => `
            <div class="playlist-track" data-index="${index}">
                <span class="track-number">${index + 1}</span>
                <div class="track-details">
                    <div class="track-title">${track.title}</div>
                    <div class="track-artist">${track.artist}</div>
                </div>
                ${track.youtube_video_id ? 
                    `<span class="match-badge">✓ YouTube</span>` : 
                    `<span class="match-badge warning">⚠ Searching...</span>`
                }
                <button class="btn btn-sm" onclick="focusPlaylistsUI.playTrack(${index})">
                    ▶
                </button>
            </div>
        `).join('');

        // Update track info
        this.updateTrackInfo();
    }

    /**
     * Load current track in YouTube player
     */
    loadTrack() {
        if (!this.currentPlaylist || this.currentTrackIndex >= this.currentPlaylist.tracks.length) {
            return;
        }

        const track = this.currentPlaylist.tracks[this.currentTrackIndex];
        
        if (track.youtube_video_id) {
            const embedUrl = `https://www.youtube.com/embed/${track.youtube_video_id}?autoplay=0`;
            document.getElementById('youtube-player').src = embedUrl;
        } else {
            document.getElementById('youtube-player').src = '';
        }

        this.updateTrackInfo();
    }

    /**
     * Update track information display
     */
    updateTrackInfo() {
        if (!this.currentPlaylist) return;

        const track = this.currentPlaylist.tracks[this.currentTrackIndex];
        const info = document.getElementById('track-info');
        info.textContent = `${this.currentTrackIndex + 1} / ${this.currentPlaylist.tracks.length}: ${track.title} - ${track.artist}`;
    }

    /**
     * Play specific track
     */
    playTrack(index) {
        this.currentTrackIndex = index;
        this.loadTrack();
        this.isPlaying = true;
        this.updatePlayButton();
    }

    /**
     * Play next track
     */
    nextTrack() {
        if (this.currentPlaylist && this.currentTrackIndex < this.currentPlaylist.tracks.length - 1) {
            this.currentTrackIndex++;
            this.loadTrack();
        }
    }

    /**
     * Play previous track
     */
    previousTrack() {
        if (this.currentTrackIndex > 0) {
            this.currentTrackIndex--;
            this.loadTrack();
        }
    }

    /**
     * Toggle play/pause
     */
    playPause() {
        this.isPlaying = !this.isPlaying;
        this.updatePlayButton();
        // Note: YouTube iframe doesn't provide simple play/pause API without OAuth
    }

    /**
     * Update play button state
     */
    updatePlayButton() {
        const btn = document.getElementById('play-pause-btn');
        if (btn) {
            btn.textContent = this.isPlaying ? '⏸ Pause' : '▶ Play';
        }
    }

    /**
     * Sync playlist to external provider
     */
    async syncToProvider(provider) {
        if (!this.currentPlaylist) {
            alert('No playlist to sync');
            return;
        }

        const providerName = provider === 'spotify' ? 'Spotify' : 'Apple Music';
        const btn = document.getElementById(`sync-${provider}-btn`);

        try {
            btn.disabled = true;
            btn.textContent = `Syncing to ${providerName}...`;

            const response = await fetch(
                `/api/focus-playlists/${this.currentPlaylist.id}/sync/${provider}`,
                { method: 'POST' }
            );

            const data = await response.json();

            if (data.success) {
                this.showNotification(
                    `✅ Syncing to ${providerName} started`,
                    'success'
                );
            } else {
                throw new Error(data.detail || 'Sync failed');
            }

        } catch (error) {
            console.error(`Error syncing to ${providerName}:`, error);
            this.showNotification(`❌ Error: ${error.message}`, 'error');
        } finally {
            btn.disabled = false;
            btn.textContent = `🎵 Save to ${providerName}`;
        }
    }

    /**
     * Load saved playlists
     */
    async loadPlaylists() {
        try {
            const response = await fetch('/api/focus-playlists/');
            const data = await response.json();

            if (!data.success) {
                throw new Error('Failed to load playlists');
            }

            const listContainer = document.getElementById('playlists-list');
            
            if (!data.playlists || data.playlists.length === 0) {
                listContainer.innerHTML = '<p class="empty-state">No playlists yet. Generate one above!</p>';
                return;
            }

            listContainer.innerHTML = data.playlists.map(playlist => `
                <div class="playlist-item">
                    <div class="playlist-info">
                        <h4>${playlist.title}</h4>
                        <p>${playlist.track_count} tracks • ${playlist.duration_minutes} min</p>
                        <span class="mood-badge">${playlist.mood || 'Custom'}</span>
                    </div>
                    <div class="playlist-actions">
                        <button class="btn btn-sm btn-primary" 
                                onclick="focusPlaylistsUI.loadPlaylistDetail('${playlist.id}')">
                            Play
                        </button>
                        <button class="btn btn-sm btn-danger"
                                onclick="focusPlaylistsUI.deletePlaylist('${playlist.id}')">
                            Delete
                        </button>
                    </div>
                </div>
            `).join('');

        } catch (error) {
            console.error('Error loading playlists:', error);
            document.getElementById('playlists-list').innerHTML =
                `<p class="error">Error loading playlists: ${error.message}</p>`;
        }
    }

    /**
     * Load playlist details and display for playback
     */
    async loadPlaylistDetail(playlistId) {
        try {
            const response = await fetch(`/api/focus-playlists/${playlistId}`);
            const data = await response.json();

            if (!data.success) {
                throw new Error('Failed to load playlist');
            }

            this.currentPlaylist = data.playlist;
            this.currentTrackIndex = 0;
            this.displayPlaylist();
            this.showNotification('✅ Playlist loaded', 'success');

        } catch (error) {
            console.error('Error loading playlist:', error);
            this.showNotification(`❌ Error: ${error.message}`, 'error');
        }
    }

    /**
     * Delete a playlist
     */
    async deletePlaylist(playlistId) {
        if (!confirm('Are you sure you want to delete this playlist?')) {
            return;
        }

        try {
            const response = await fetch(`/api/focus-playlists/${playlistId}`, {
                method: 'DELETE'
            });

            const data = await response.json();

            if (data.success) {
                this.showNotification('✅ Playlist deleted', 'success');
                await this.loadPlaylists();
            } else {
                throw new Error(data.detail || 'Delete failed');
            }

        } catch (error) {
            console.error('Error deleting playlist:', error);
            this.showNotification(`❌ Error: ${error.message}`, 'error');
        }
    }

    /**
     * Show notification
     */
    showNotification(message, type = 'info') {
        console.log(`[${type.toUpperCase()}] ${message}`);
        // Integrate with existing notification system if available
        if (window.dataLoader?.showNotification) {
            window.dataLoader.showNotification(message, type);
        }
    }
}

// Initialize when DOM is ready
let focusPlaylistsUI;
document.addEventListener('DOMContentLoaded', () => {
    focusPlaylistsUI = new FocusPlaylistsUI();
    focusPlaylistsUI.init().catch(err => console.error('Failed to initialize Focus Playlists:', err));
});
