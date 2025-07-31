<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Wake Word SMS - Always Listening</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
            color: white;
        }

        .container {
            background: rgba(255, 255, 255, 0.1);
            border-radius: 20px;
            padding: 40px;
            box-shadow: 0 20px 40px rgba(0, 0, 0, 0.2);
            backdrop-filter: blur(15px);
            max-width: 700px;
            width: 100%;
            text-align: center;
        }

        .header h1 {
            font-size: 2.5em;
            margin-bottom: 10px;
            font-weight: 700;
        }

        .header p {
            font-size: 1.2em;
            opacity: 0.9;
            margin-bottom: 30px;
        }

        .wake-word-display {
            background: linear-gradient(45deg, #28a745, #20c997);
            padding: 15px 30px;
            border-radius: 50px;
            font-size: 1.3em;
            font-weight: bold;
            margin-bottom: 30px;
            display: inline-block;
        }

        .listening-status {
            height: 120px;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            margin-bottom: 30px;
        }

        .voice-indicator {
            width: 100px;
            height: 100px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 40px;
            margin-bottom: 15px;
            transition: all 0.3s ease;
        }

        .voice-indicator.listening {
            background: linear-gradient(45deg, #28a745, #20c997);
            animation: pulse 2s infinite;
            box-shadow: 0 0 30px rgba(40, 167, 69, 0.5);
        }

        .voice-indicator.wake-detected {
            background: linear-gradient(45deg, #ffc107, #e0a800);
            animation: glow 1s infinite alternate;
            box-shadow: 0 0 30px rgba(255, 193, 7, 0.7);
        }

        .voice-indicator.processing {
            background: linear-gradient(45deg, #dc3545, #c82333);
            animation: spin 1s linear infinite;
            box-shadow: 0 0 30px rgba(220, 53, 69, 0.5);
        }

        .voice-indicator.idle {
            background: rgba(255, 255, 255, 0.2);
            animation: none;
        }

        @keyframes pulse {
            0% { transform: scale(1); opacity: 1; }
            50% { transform: scale(1.1); opacity: 0.8; }
            100% { transform: scale(1); opacity: 1; }
        }

        @keyframes glow {
            0% { box-shadow: 0 0 30px rgba(255, 193, 7, 0.7); }
            100% { box-shadow: 0 0 50px rgba(255, 193, 7, 1); }
        }

        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }

        .status-text {
            font-size: 1.1em;
            font-weight: 500;
            min-height: 30px;
        }

        .status-text.listening {
            color: #20c997;
        }

        .status-text.wake-detected {
            color: #ffc107;
        }

        .status-text.processing {
            color: #dc3545;
        }

        .controls {
            margin-bottom: 30px;
        }

        .control-button {
            background: linear-gradient(45deg, #007bff, #0056b3);
            color: white;
            border: none;
            padding: 12px 30px;
            border-radius: 25px;
            font-size: 1em;
            font-weight: 600;
            cursor: pointer;
            margin: 0 10px;
            transition: all 0.3s ease;
        }

        .control-button:hover {
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(0, 123, 255, 0.4);
        }

        .control-button.stop {
            background: linear-gradient(45deg, #dc3545, #c82333);
        }

        .control-button:disabled {
            background: #6c757d;
            cursor: not-allowed;
            transform: none;
            box-shadow: none;
        }

        .transcription {
            background: rgba(255, 255, 255, 0.1);
            border-radius: 15px;
            padding: 20px;
            margin-bottom: 20px;
            min-height: 80px;
            border: 2px solid transparent;
            transition: all 0.3s ease;
        }

        .transcription.active {
            border-color: #28a745;
            background: rgba(40, 167, 69, 0.1);
        }

        .transcription h3 {
            font-size: 1.1em;
            margin-bottom: 10px;
            opacity: 0.8;
        }

        .transcription-text {
            font-size: 1.2em;
            font-weight: 500;
            font-family: 'Courier New', monospace;
        }

        .response {
            background: rgba(255, 255, 255, 0.1);
            border-radius: 15px;
            padding: 20px;
            margin-bottom: 20px;
            min-height: 80px;
            text-align: left;
            white-space: pre-wrap;
            display: none;
        }

        .response.success {
            background: rgba(40, 167, 69, 0.2);
            border: 2px solid #28a745;
        }

        .response.error {
            background: rgba(220, 53, 69, 0.2);
            border: 2px solid #dc3545;
        }

        .examples {
            background: rgba(255, 255, 255, 0.1);
            border-radius: 15px;
            padding: 20px;
            text-align: left;
            margin-bottom: 20px;
        }

        .examples h3 {
            margin-bottom: 15px;
            text-align: center;
        }

        .examples ul {
            list-style: none;
            padding: 0;
        }

        .examples li {
            background: rgba(255, 255, 255, 0.1);
            margin-bottom: 8px;
            padding: 12px 15px;
            border-radius: 8px;
            font-family: 'Courier New', monospace;
            font-size: 0.95em;
        }

        .browser-support {
            font-size: 0.9em;
            opacity: 0.8;
            margin-top: 20px;
        }

        .browser-support.unsupported {
            color: #dc3545;
            font-weight: bold;
            opacity: 1;
        }

        .privacy-note {
            background: rgba(255, 193, 7, 0.2);
            border: 1px solid #ffc107;
            border-radius: 10px;
            padding: 15px;
            margin-top: 20px;
            font-size: 0.9em;
        }

        @media (max-width: 600px) {
            .container {
                padding: 20px;
                margin: 10px;
            }

            .header h1 {
                font-size: 2em;
            }

            .voice-indicator {
                width: 80px;
                height: 80px;
                font-size: 32px;
            }

            .control-button {
                padding: 10px 20px;
                font-size: 0.9em;
                margin: 5px;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🎙️ Wake Word SMS</h1>
            <p>Always listening for voice commands</p>
        </div>

        <div class="wake-word-display">
            🎯 Say: "Hey Ringly"
        </div>

        <div class="listening-status">
            <div class="voice-indicator idle" id="voiceIndicator">🎤</div>
            <div class="status-text" id="statusText">Click "Start Listening" to begin</div>
        </div>

        <div class="controls">
            <button class="control-button" id="startButton" onclick="startListening()">
                Start Listening
            </button>
            <button class="control-button stop" id="stopButton" onclick="stopListening()" disabled>
                Stop Listening
            </button>
        </div>

        <div class="transcription" id="transcription">
            <h3>🎤 Voice Transcription</h3>
            <div class="transcription-text" id="transcriptionText">
                Waiting for "Hey Ringly" command...
            </div>
        </div>

        <div id="response" class="response"></div>

        <div class="examples">
            <h3>📝 Voice Commands</h3>
            <ul>
                <li>"Hey Ringly: text 5551234567 saying hello there!"</li>
                <li>"Hey Ringly: text Mom saying running late"</li>
                <li>"Hey Ringly: send message to John saying meeting at 3pm"</li>
                <li>"Hey Ringly: text 8136414177 saying voice test working"</li>
            </ul>
        </div>

        <div class="browser-support" id="browserSupport">
            Checking browser compatibility...
        </div>

        <div class="privacy-note">
            🔒 <strong>Privacy:</strong> Voice recognition runs locally in your browser. 
            Audio is only processed when "Hey Ringly" is detected.
        </div>
    </div>

    <script>
        // Global variables
        let recognition = null;
        let isListening = false;
        let isProcessingCommand = false;
        let continuousListening = true;

        // DOM elements
        const voiceIndicator = document.getElementById('voiceIndicator');
        const statusText = document.getElementById('statusText');
        const startButton = document.getElementById('startButton');
        const stopButton = document.getElementById('stopButton');
        const transcription = document.getElementById('transcription');
        const transcriptionText = document.getElementById('transcriptionText');
        const response = document.getElementById('response');
        const browserSupport = document.getElementById('browserSupport');

        // Initialize speech recognition
        function initSpeechRecognition() {
            if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {
                const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
                recognition = new SpeechRecognition();
                
                // Configuration for continuous listening
                recognition.continuous = true;  // Keep listening
                recognition.interimResults = true;  // Show interim results
                recognition.lang = 'en-US';
                recognition.maxAlternatives = 1;

                // Event handlers
                recognition.onstart = function() {
                    console.log('Speech recognition started');
                    isListening = true;
                    updateUI('listening', '🎤 Listening for "Hey Ringly"...', '👂');
                };

                recognition.onresult = function(event) {
                    let interimTranscript = '';
                    let finalTranscript = '';

                    // Process all results
                    for (let i = event.resultIndex; i < event.results.length; i++) {
                        const transcript = event.results[i][0].transcript;
                        if (event.results[i].isFinal) {
                            finalTranscript += transcript + ' ';
                        } else {
                            interimTranscript += transcript;
                        }
                    }

                    // Show current transcription
                    const currentText = (finalTranscript + interimTranscript).trim();
                    if (currentText) {
                        transcriptionText.textContent = currentText;
                        transcription.classList.add('active');
                    }

                    // Check for wake word in final transcript
                    if (finalTranscript && !isProcessingCommand) {
                        checkForWakeWord(finalTranscript.trim());
                    }
                };

                recognition.onerror = function(event) {
                    console.error('Speech recognition error:', event.error);
                    
                    let errorMessage = 'Recognition error: ';
                    switch(event.error) {
                        case 'no-speech':
                            // This is normal for continuous listening, don't show error
                            return;
                        case 'network':
                            errorMessage += 'Network error. Check connection.';
                            break;
                        case 'not-allowed':
                            errorMessage += 'Microphone access denied. Please allow microphone access.';
                            stopListening();
                            break;
                        case 'service-not-allowed':
                            errorMessage += 'Speech service not allowed.';
                            stopListening();
                            break;
                        default:
                            errorMessage += event.error;
                    }
                    
                    updateUI('idle', errorMessage, '❌');
                    setTimeout(() => {
                        if (continuousListening && !isListening) {
                            restartListening();
                        }
                    }, 2000);
                };

                recognition.onend = function() {
                    console.log('Speech recognition ended');
                    isListening = false;
                    
                    if (continuousListening && !isProcessingCommand) {
                        // Automatically restart listening
                        setTimeout(() => {
                            if (continuousListening) {
                                restartListening();
                            }
                        }, 100);
                    } else {
                        updateUI('idle', 'Stopped listening', '🎤');
                        startButton.disabled = false;
                        stopButton.disabled = true;
                    }
                };

                browserSupport.textContent = 'Voice recognition supported ✅';
                browserSupport.className = 'browser-support';
                return true;
            } else {
                browserSupport.textContent = '❌ Voice recognition not supported in this browser. Please use Chrome, Edge, or Safari.';
                browserSupport.className = 'browser-support unsupported';
                startButton.disabled = true;
                return false;
            }
        }

        // Check for wake word
        function checkForWakeWord(text) {
            const lowerText = text.toLowerCase().trim();
            
            // Look for "hey ringly" or similar wake words
            const wakeWords = ['hey ringly', 'hey ring', 'ringly'];
            let wakeWordFound = false;
            let detectedWakeWord = '';

            for (const wakeWord of wakeWords) {
                if (lowerText.includes(wakeWord)) {
                    wakeWordFound = true;
                    detectedWakeWord = wakeWord;
                    break;
                }
            }

            if (wakeWordFound) {
                console.log('Wake word detected:', detectedWakeWord);
                processWakeWordCommand(text);
            }
        }

        // Process wake word command
        async function processWakeWordCommand(fullText) {
            if (isProcessingCommand) return; // Prevent double processing
            
            isProcessingCommand = true;
            updateUI('wake-detected', '⚡ Wake word detected! Processing...', '⚡');
            
            // Show the full command
            transcriptionText.textContent = fullText;
            
            try {
                // Send to your backend
                updateUI('processing', '📤 Sending command...', '⚙️');
                
                const apiResponse = await fetch('/execute', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({ 
                        text: fullText  // Changed from 'command' to 'text' to match your backend
                    })
                });

                const data = await apiResponse.json();
                
                if (apiResponse.ok) {
                    showResponse(data.response || 'Command executed successfully!', 'success');
                    updateUI('listening', '✅ Command sent! Listening for next command...', '👂');
                } else {
                    showResponse(data.error || 'An error occurred while processing your command.', 'error');
                    updateUI('listening', '❌ Error occurred. Listening for next command...', '👂');
                }
            } catch (error) {
                console.error('Error sending command:', error);
                showResponse('Network error. Please check your connection and try again.', 'error');
                updateUI('listening', '❌ Network error. Listening for next command...', '👂');
            } finally {
                isProcessingCommand = false;
                
                // Clear transcription after a delay
                setTimeout(() => {
                    transcriptionText.textContent = 'Waiting for "Hey Ringly" command...';
                    transcription.classList.remove('active');
                }, 3000);
            }
        }

        // Update UI elements
        function updateUI(state, statusMessage, indicator) {
            // Update status text
            statusText.textContent = statusMessage;
            statusText.className = `status-text ${state}`;
            
            // Update voice indicator
            voiceIndicator.textContent = indicator;
            voiceIndicator.className = `voice-indicator ${state}`;
        }

        // Show response
        function showResponse(message, type) {
            response.textContent = message;
            response.className = `response ${type}`;
            response.style.display = 'block';
            
            // Auto-hide success messages after 10 seconds
            if (type === 'success') {
                setTimeout(() => {
                    response.style.display = 'none';
                }, 10000);
            }
        }

        // Start listening
        function startListening() {
            if (!recognition) {
                alert('Speech recognition not available in this browser.');
                return;
            }

            continuousListening = true;
            startButton.disabled = true;
            stopButton.disabled = false;
            response.style.display = 'none';
            
            try {
                recognition.start();
            } catch (error) {
                console.error('Error starting recognition:', error);
                updateUI('idle', 'Error starting recognition', '❌');
                startButton.disabled = false;
                stopButton.disabled = true;
            }
        }

        // Stop listening
        function stopListening() {
            continuousListening = false;
            if (recognition && isListening) {
                recognition.stop();
            }
            updateUI('idle', 'Stopped listening', '🎤');
            startButton.disabled = false;
            stopButton.disabled = true;
            transcriptionText.textContent = 'Waiting for "Hey Ringly" command...';
            transcription.classList.remove('active');
        }

        // Restart listening (for continuous mode)
        function restartListening() {
            if (continuousListening && recognition && !isListening) {
                try {
                    recognition.start();
                } catch (error) {
                    console.error('Error restarting recognition:', error);
                    setTimeout(() => {
                        if (continuousListening) {
                            restartListening();
                        }
                    }, 1000);
                }
            }
        }

        // Initialize on page load
        window.addEventListener('load', function() {
            const speechSupported = initSpeechRecognition();
            if (speechSupported) {
                console.log('Speech recognition initialized successfully');
            } else {
                console.log('Speech recognition not supported');
            }
        });

        // Handle visibility change (pause when tab not active)
        document.addEventListener('visibilitychange', function() {
            if (document.hidden && isListening) {
                console.log('Tab hidden, pausing recognition');
                recognition.stop();
            } else if (!document.hidden && continuousListening && !isListening) {
                console.log('Tab visible, resuming recognition');
                setTimeout(() => {
                    restartListening();
                }, 500);
            }
        });

        // Request microphone permission on first interaction
        document.addEventListener('click', function() {
            if (navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
                navigator.mediaDevices.getUserMedia({ audio: true })
                    .then(() => {
                        console.log('Microphone permission granted');
                    })
                    .catch((error) => {
                        console.warn('Microphone permission denied:', error);
                    });
            }
        }, { once: true });
    </script>
</body>
</html>
