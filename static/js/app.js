/**
 * ============================================================
 * Eco-Awaaz — Application Logic
 * Handles Twilio Voice SDK integration, call lifecycle,
 * timer, UI state management, and error handling.
 * ============================================================
 */

const EcoAwaaz = (() => {
    'use strict';

    // ---- State ----
    let device = null;       // Twilio.Device instance
    let connection = null;   // Active Twilio connection
    let timerInterval = null;
    let timerSeconds = 0;
    let isMuted = false;

    // ---- DOM References (cached on first use) ----
    const $ = (id) => document.getElementById(id);

    const dom = {
        get landingScreen()  { return $('landing-screen'); },
        get callScreen()     { return $('call-screen'); },
        get btnStartCall()   { return $('btn-start-call'); },
        get btnMute()        { return $('btn-mute'); },
        get btnEnd()         { return $('btn-end'); },
        get btnNewCall()     { return $('btn-new-call'); },
        get callStatus()     { return $('call-status'); },
        get callTimer()      { return $('call-timer'); },
        get callIconCircle() { return $('call-icon-circle'); },
        get callIcon()       { return $('call-icon'); },
        get callControls()   { return $('call-controls'); },
        get errorMessage()   { return $('error-message'); },
    };


    // ============================================================
    // Token
    // ============================================================

    /**
     * Fetch a Twilio access token from the existing /token endpoint.
     * @returns {Promise<string>} JWT token string
     */
    async function fetchToken() {
        const response = await fetch('/token');

        if (!response.ok) {
            const body = await response.json().catch(() => ({}));
            throw new Error(body.error || `Token request failed (${response.status})`);
        }

        const data = await response.json();

        if (!data.token) {
            throw new Error('No token received from server.');
        }

        return data.token;
    }


    // ============================================================
    // Twilio Device
    // ============================================================

    /**
     * Initialize the Twilio Device with the given token,
     * wire up event listeners, and connect the call.
     * @param {string} token - Twilio JWT token
     */
    function initDevice(token) {
        // Create new device
        device = new Twilio.Device(token, {
            codecPreferences: ['opus', 'pcmu'],
            debug: false,
        });

        // ---- Device Events ----

        device.on('ready', () => {
            console.log('[EcoAwaaz] Device ready — connecting call...');
            connectCall();
        });

        device.on('error', (err) => {
            console.error('[EcoAwaaz] Device error:', err);
            showError('Connection error. Please try again.');
            resetCallState();
        });

        device.on('disconnect', () => {
            console.log('[EcoAwaaz] Call disconnected');
            onCallEnded();
        });

        device.on('cancel', () => {
            console.log('[EcoAwaaz] Call cancelled');
            onCallEnded();
        });
    }


    /**
     * Tell the Twilio device to connect (outbound call).
     */
    function connectCall() {
        if (!device) return;

        connection = device.connect();

        connection.on('accept', () => {
            console.log('[EcoAwaaz] Call accepted / connected');
            onCallConnected();
        });

        connection.on('disconnect', () => {
            console.log('[EcoAwaaz] Connection disconnected');
            onCallEnded();
        });

        connection.on('error', (err) => {
            console.error('[EcoAwaaz] Connection error:', err);
            showError('Call failed. Please try again.');
            resetCallState();
        });
    }


    // ============================================================
    // Call Lifecycle
    // ============================================================

    /**
     * Entry point — called when user clicks "Start Call".
     */
    async function startCall() {
        hideError();

        // Show loading state on button
        const btn = dom.btnStartCall;
        btn.disabled = true;
        btn.classList.add('loading');
        const btnText = btn.querySelector('.btn-call-text');
        const originalText = btnText.textContent;
        btnText.textContent = 'Connecting';
        const btnIcon = btn.querySelector('.btn-call-icon i');
        btnIcon.className = 'fa-solid fa-spinner';

        try {
            const token = await fetchToken();
            switchToCallScreen();
            initDevice(token);
        } catch (err) {
            console.error('[EcoAwaaz] Start call error:', err);
            showError('Unable to connect. Please try again.');

            // Restore button
            btn.disabled = false;
            btn.classList.remove('loading');
            btnText.textContent = originalText;
            btnIcon.className = 'fa-solid fa-phone';
        }
    }


    /**
     * Called when the Twilio connection is accepted.
     */
    function onCallConnected() {
        dom.callStatus.textContent = 'Connected';
        dom.callStatus.className = 'call-status connected';

        // Start timer
        timerSeconds = 0;
        updateTimerDisplay();
        timerInterval = setInterval(() => {
            timerSeconds++;
            updateTimerDisplay();
        }, 1000);

        // Ensure pulse rings are animating
        document.querySelectorAll('.pulse-ring').forEach(r => r.classList.remove('paused'));
    }


    /**
     * Called when the call disconnects or ends.
     */
    function onCallEnded() {
        // Stop timer
        if (timerInterval) {
            clearInterval(timerInterval);
            timerInterval = null;
        }

        // Update status
        dom.callStatus.textContent = 'Call Ended';
        dom.callStatus.className = 'call-status ended';

        // Switch icon to success checkmark
        dom.callIconCircle.className = 'call-icon-circle success';
        dom.callIcon.className = 'fa-solid fa-check';

        // Pause pulse rings
        document.querySelectorAll('.pulse-ring').forEach(r => r.classList.add('paused'));

        // Hide call controls, show "Start New Call" button
        dom.callControls.classList.add('hidden');
        dom.btnNewCall.classList.remove('hidden');

        // Clean up
        connection = null;
    }


    /**
     * End the active call programmatically.
     */
    function endCall() {
        if (device) {
            device.disconnectAll();
        }
    }


    /**
     * Toggle mute on the active connection.
     */
    function toggleMute() {
        if (!connection) return;

        isMuted = !isMuted;
        connection.mute(isMuted);

        const btn = dom.btnMute;
        const icon = btn.querySelector('i');
        const label = btn.querySelector('span');

        if (isMuted) {
            btn.classList.add('active');
            icon.className = 'fa-solid fa-microphone-slash';
            label.textContent = 'Unmute';
            dom.callIconCircle.classList.add('muted');
        } else {
            btn.classList.remove('active');
            icon.className = 'fa-solid fa-microphone';
            label.textContent = 'Mute';
            dom.callIconCircle.classList.remove('muted');
        }
    }


    // ============================================================
    // UI Helpers
    // ============================================================

    /**
     * Switch from landing screen to call screen with smooth transition.
     */
    function switchToCallScreen() {
        dom.landingScreen.classList.remove('active');
        // Small delay for the fade-out before showing call screen
        setTimeout(() => {
            dom.callScreen.classList.add('active');
        }, 80);
    }


    /**
     * Reset everything and return to the landing page.
     */
    function resetToLanding() {
        resetCallState();

        dom.callScreen.classList.remove('active');
        setTimeout(() => {
            dom.landingScreen.classList.add('active');
        }, 80);
    }


    /**
     * Reset internal call state and UI to defaults.
     */
    function resetCallState() {
        // Kill timer
        if (timerInterval) {
            clearInterval(timerInterval);
            timerInterval = null;
        }
        timerSeconds = 0;

        // Destroy device
        if (device) {
            try { device.destroy(); } catch (_) { /* ignore */ }
            device = null;
        }
        connection = null;
        isMuted = false;

        // Reset call screen UI elements
        dom.callStatus.textContent = 'Connecting...';
        dom.callStatus.className = 'call-status';
        dom.callTimer.textContent = '00:00';
        dom.callIconCircle.className = 'call-icon-circle';
        dom.callIcon.className = 'fa-solid fa-microphone';
        dom.callControls.classList.remove('hidden');
        dom.btnNewCall.classList.add('hidden');
        document.querySelectorAll('.pulse-ring').forEach(r => r.classList.remove('paused'));

        // Reset mute button
        const muteBtn = dom.btnMute;
        muteBtn.classList.remove('active');
        muteBtn.querySelector('i').className = 'fa-solid fa-microphone';
        muteBtn.querySelector('span').textContent = 'Mute';

        // Reset start call button
        const startBtn = dom.btnStartCall;
        startBtn.disabled = false;
        startBtn.classList.remove('loading');
        startBtn.querySelector('.btn-call-text').textContent = 'Start Call';
        startBtn.querySelector('.btn-call-icon i').className = 'fa-solid fa-phone';
    }


    /**
     * Update the timer display from timerSeconds.
     */
    function updateTimerDisplay() {
        const mins = String(Math.floor(timerSeconds / 60)).padStart(2, '0');
        const secs = String(timerSeconds % 60).padStart(2, '0');
        dom.callTimer.textContent = `${mins}:${secs}`;
    }


    /**
     * Show an error message on the landing screen.
     * @param {string} message
     */
    function showError(message) {
        const el = dom.errorMessage;
        el.innerHTML = `<i class="fa-solid fa-circle-exclamation"></i> ${message}`;
        el.classList.remove('hidden');
    }


    /**
     * Hide the error message.
     */
    function hideError() {
        dom.errorMessage.classList.add('hidden');
    }


    // ============================================================
    // Public API
    // ============================================================
    return {
        startCall,
        endCall,
        toggleMute,
        resetToLanding,
    };

})();
