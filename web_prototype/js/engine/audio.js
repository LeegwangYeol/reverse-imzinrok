/**
 * Web Audio API Sound Engine with 2D Stereo Spatial Panning and Voice Limiting
 *
 * Implements sound buffering, stereo spatial panning via StereoPannerNode,
 * distance attenuation, master volume/muting, and voice pooling (max 3 instances per sound ID).
 */

export class SoundEngine {
    constructor() {
        this.ctx = null;
        this.buffers = new Map(); // soundName -> AudioBuffer
        this.soundUrls = new Map(); // soundName -> string URL
        this.activeVoices = new Map(); // soundName -> count
        this.activeSources = new Set(); // set of actively playing source nodes
        this.maxVoicesPerSound = 3;
        this.masterVolume = 1.0;
        this.isMuted = false;
        this.isInitialized = false;
    }

    /**
     * Initializes or resumes the AudioContext upon user gesture.
     */
    init() {
        if (typeof window === 'undefined') return;

        if (!this.ctx) {
            const AudioContextClass = window.AudioContext || window.webkitAudioContext;
            if (AudioContextClass) {
                this.ctx = new AudioContextClass();
                this.isInitialized = true;
            }
        }

        if (this.ctx && this.ctx.state === 'suspended') {
            this.ctx.resume().catch(() => {});
        }
    }

    /**
     * Registers a sound name and asset URL for on-demand loading.
     *
     * @param {string} name - Identifier for the sound (e.g. 'sword_hit', 'arrow')
     * @param {string} url - Web-accessible URL to the audio file (.wav)
     */
    registerSound(name, url) {
        this.soundUrls.set(name, url);
    }

    /**
     * Loads and decodes an audio file into memory.
     *
     * @param {string} name - Sound identifier
     * @param {string} url - Audio asset URL
     * @returns {Promise<AudioBuffer|null>} Decoded audio buffer
     */
    async loadSound(name, url) {
        this.init();
        if (!this.ctx || typeof fetch === 'undefined') return null;

        try {
            const response = await fetch(url);
            if (!response.ok) {
                console.warn(`[SoundEngine] Failed to fetch sound "${name}" from ${url}: ${response.status}`);
                return null;
            }
            const arrayBuffer = await response.arrayBuffer();
            const audioBuffer = await this.ctx.decodeAudioData(arrayBuffer);
            this.buffers.set(name, audioBuffer);
            this.soundUrls.set(name, url);
            return audioBuffer;
        } catch (err) {
            console.warn(`[SoundEngine] Error loading sound "${name}":`, err);
            return null;
        }
    }

    /**
     * Preloads multiple sounds in parallel from a key-url map.
     *
     * @param {Object<string, string>} soundMap - Map of sound names to URLs
     */
    async preloadSounds(soundMap) {
        const promises = [];
        for (const [name, url] of Object.entries(soundMap)) {
            promises.push(this.loadSound(name, url));
        }
        await Promise.allSettled(promises);
    }

    /**
     * Plays a sound effect with optional 2D spatial stereo panning and distance attenuation.
     *
     * @param {string} name - Sound identifier
     * @param {number} [worldX] - World grid X position for spatial positioning
     * @param {number} [worldY] - World grid Y position for spatial positioning
     * @param {Object} [camera] - Camera object containing viewport and position
     * @returns {AudioBufferSourceNode|null} Playing source node, or null if voice limited or unplayable
     */
    play(name, worldX, worldY, camera) {
        if (this.isMuted) return null;
        if (!this.ctx) {
            this.init();
            if (!this.ctx) return null;
        }

        const buffer = this.buffers.get(name);
        if (!buffer) return null;

        // Voice limiting / sound pooling (max 3 instances per sound ID)
        const currentCount = this.activeVoices.get(name) || 0;
        if (currentCount >= this.maxVoicesPerSound) {
            return null;
        }
        this.activeVoices.set(name, currentCount + 1);

        try {
            const source = this.ctx.createBufferSource();
            source.buffer = buffer;

            const gainNode = this.ctx.createGain();

            // Spatial audio calculations
            if (worldX !== undefined && worldY !== undefined && camera) {
                // Screen X position of the audio source
                const sx = (worldX - worldY) * 32 + (camera.x || 0);
                const screenCenter = (camera.viewportWidth || 1024) / 2;

                // Stereo panning (-1.0 left to +1.0 right)
                const panRatio = (sx - screenCenter) / (screenCenter || 1);
                const pan = Math.max(-1.0, Math.min(1.0, panRatio));

                // Distance volume attenuation (drops off beyond screen edges)
                const distFromCenter = Math.abs(sx - screenCenter);
                const maxAudibleDist = (camera.viewportWidth || 1024) * 1.5;
                const distanceFactor = Math.max(0.08, 1.0 - (distFromCenter / maxAudibleDist));

                gainNode.gain.value = Math.max(0.0, Math.min(1.0, distanceFactor * this.masterVolume));

                if (typeof this.ctx.createStereoPanner === 'function') {
                    const panner = this.ctx.createStereoPanner();
                    panner.pan.value = pan;
                    source.connect(panner);
                    panner.connect(gainNode);
                } else {
                    source.connect(gainNode);
                }
            } else {
                gainNode.gain.value = Math.max(0.0, Math.min(1.0, this.masterVolume));
                source.connect(gainNode);
            }

            gainNode.connect(this.ctx.destination);
            this.activeSources.add(source);

            source.onended = () => {
                const count = this.activeVoices.get(name) || 1;
                this.activeVoices.set(name, Math.max(0, count - 1));
                this.activeSources.delete(source);
            };

            source.start(0);
            return source;
        } catch (err) {
            const count = this.activeVoices.get(name) || 1;
            this.activeVoices.set(name, Math.max(0, count - 1));
            return null;
        }
    }

    /**
     * Stops all currently playing sound sources.
     */
    stopAll() {
        for (const source of this.activeSources) {
            try {
                source.stop(0);
            } catch (_) {}
        }
        this.activeSources.clear();
        this.activeVoices.clear();
    }

    /**
     * Sets master volume level [0.0, 1.0].
     *
     * @param {number} volume - Volume multiplier
     */
    setVolume(volume) {
        this.masterVolume = Math.max(0.0, Math.min(1.0, volume));
    }

    /**
     * Toggles mute state.
     *
     * @param {boolean} muted - True to mute
     */
    setMuted(muted) {
        this.isMuted = !!muted;
        if (this.isMuted) {
            this.stopAll();
        }
    }
}

// Export AudioManager alias
export const AudioManager = SoundEngine;
