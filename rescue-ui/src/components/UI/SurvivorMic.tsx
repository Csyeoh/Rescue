'use client';
import { useState, useEffect, useRef } from 'react';
import { Mic, Square, Loader2 } from 'lucide-react';

export default function SurvivorMic({ survivorId, onIntelReceived }: { survivorId: number, onIntelReceived: (intel: any) => void }) {
    const [isRecording, setIsRecording] = useState(false);
    const [isProcessing, setIsProcessing] = useState(false);
    const [transcript, setTranscript] = useState('');
    const recognitionRef = useRef<any>(null);

    // Initialize Web Speech API on mount
    useEffect(() => {
        if (typeof window !== 'undefined') {
            const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
            
            if (SpeechRecognition) {
                const rec = new SpeechRecognition();
                rec.continuous = false; // Stop listening when button released
                rec.interimResults = false; // We only want the final result
                rec.lang = 'en-US';

                rec.onstart = () => {
                    console.log("🎙️ Mic active and listening...");
                };

                rec.onresult = (event: any) => {
                    const text = event.results[0][0].transcript;
                    console.log("🎙️ Heard:", text);
                    setTranscript(text); // This triggers the API call below
                };

                rec.onend = () => {
                    console.log("🎙️ Mic stopped listening.");
                    setIsRecording(false);
                };

                // Inside SurvivorMic.tsx within the SpeechRecognition useEffect
                rec.onerror = (event: any) => {
                    // If no speech is detected, just reset the state quietly
                    if (event.error === 'no-speech') {
                        console.warn("🎙️ No speech detected. Try holding the button longer.");
                        setIsRecording(false);
                        setIsProcessing(false);
                        return; 
                    }

                    console.error("🎙️ Speech Recognition Error:", event.error);
                    setIsRecording(false);
                    setIsProcessing(false);
                };

                recognitionRef.current = rec;
            }
        }
    }, []);

    // Watch for new transcripts and send them to the backend safely
    useEffect(() => {
        if (!transcript) return;

        const sendData = async () => {
            setIsProcessing(true);
            try {
                const res = await fetch(`http://localhost:8000/api/survivors/${survivorId}/voice-intel`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ transcript }),
                });

                if (!res.ok) throw new Error('Failed to send intel');
                const data = await res.json();
                onIntelReceived(data); // Call this after getting data
            } catch (err) {
                console.error("❌ Intel transmission failed:", err);
            } finally {
                setIsProcessing(false);
                setTranscript(''); // Clear transcript to prevent re-triggering
            }
        };

        sendData();
        // REMOVE onIntelReceived and survivorId from this dependency array
    }, [transcript]);

    const startRecording = () => {
        if (recognitionRef.current) {
            try {
                recognitionRef.current.start();
                setIsRecording(true);
                setTranscript(''); // Clear previous
            } catch (e) {
                console.error("Microphone already active", e);
            }
        } else {
            console.warn("Speech API not initialized.");
        }
    };

    const stopRecording = () => {
        if (recognitionRef.current && isRecording) {
            recognitionRef.current.stop();
            setIsRecording(false);
        }
    };

    return (
        <div className="absolute bottom-4 right-4 flex flex-col items-center p-3 bg-slate-900/80 backdrop-blur border border-slate-700 rounded-xl shadow-2xl z-50">
            <div className="text-xs text-slate-300 mb-2 uppercase tracking-wider font-semibold">
                {isProcessing ? "Analyzing Intel..." : "Survivor Transmission"}
            </div>
            <button
                onMouseDown={startRecording}
                onMouseUp={stopRecording}
                onMouseLeave={stopRecording}
                disabled={isProcessing || !recognitionRef.current}
                className={`p-4 rounded-full transition-all ${isRecording
                        ? 'bg-red-500/90 shadow-[0_0_15px_rgba(239,68,68,0.6)] animate-pulse'
                        : 'bg-emerald-600/90 hover:bg-emerald-500'
                    } ${isProcessing || !recognitionRef.current ? 'opacity-50 cursor-not-allowed' : ''}`}
            >
                {isProcessing ? <Loader2 size={28} className="animate-spin text-white" /> :
                    isRecording ? <Square size={28} className="text-white" fill="currentColor" /> :
                        <Mic size={28} className="text-white" />}
            </button>
            {!recognitionRef.current && (
                <div className="text-[10px] text-red-400 mt-2 text-center max-w-[120px]">
                    Voice API unsupported
                </div>
            )}
        </div>
    );
}