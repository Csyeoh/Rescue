'use client';
import { useState, useEffect, useRef } from 'react';
import { Mic, Square, Loader2 } from 'lucide-react';

// BCP 47 Language Tags for multilingual support
const LANGUAGES = [
    { label: 'English', code: 'en-US' },
    { label: 'Malay', code: 'ms-MY' },
    { label: 'Chinese', code: 'zh-CN' },
    { label: 'Tamil', code: 'ta-IN' },
    { label: 'Thai', code: 'th-TH' }
];

export default function SurvivorMic({ 
    droneId,
    survivorId, 
    onIntelReceived,
    onResolve 
}: { 
    droneId: string,
    survivorId: string | number, 
    onIntelReceived: (intel: any) => void,
    onResolve: () => void
}) {
    const [isRecording, setIsRecording] = useState(false);
    const [isProcessing, setIsProcessing] = useState(false);
    const [transcript, setTranscript] = useState('');
    const [selectedLang, setSelectedLang] = useState('en-US'); // Default to English
    const recognitionRef = useRef<any>(null);

    // Initialize Web Speech API on mount or when language changes
    useEffect(() => {
        if (typeof window !== 'undefined') {
            const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
            
            if (SpeechRecognition) {
                const rec = new SpeechRecognition();
                rec.continuous = false; 
                rec.interimResults = false; 
                rec.lang = selectedLang; // Set the browser to listen for the selected language

                rec.onstart = () => console.log(`🎙️ Mic active (${selectedLang})...`);

                rec.onresult = (event: any) => {
                    const text = event.results[0][0].transcript;
                    console.log("🎙️ Heard:", text);
                    setTranscript(text); 
                };

                rec.onend = () => setIsRecording(false);

                rec.onerror = (event: any) => {
                    if (event.error === 'no-speech') {
                        console.warn("🎙️ No speech detected.");
                    } else {
                        console.error("🎙️ Error:", event.error);
                    }
                    setIsRecording(false);
                    setIsProcessing(false);
                };

                recognitionRef.current = rec;
            }
        }
    }, [selectedLang]); // Re-run effect when language selection changes

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
                onIntelReceived(data); 
            } catch (err) {
                console.error("❌ Intel transmission failed:", err);
            } finally {
                setIsProcessing(false);
                setTranscript(''); 
            }
        };

        sendData();
    }, [transcript, survivorId]);

    const resolveTriage = async (resolution: string) => {
        try {
            await fetch(`http://localhost:8000/api/triage/resolve`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ drone_id: droneId, survivor_id: String(survivorId), resolution }),
            });
        } catch (err) {
            console.error("❌ Failed to release drone (Backend might be offline):", err);
        } finally {
            // ALWAYS close the panel in the UI, whether the backend succeeds or fails
            onResolve(); 
        }
    };

    const startRecording = () => {
        if (recognitionRef.current) {
            try {
                recognitionRef.current.start();
                setIsRecording(true);
                setTranscript(''); 
            } catch (e) {
                console.error("Microphone already active", e);
            }
        }
    };

    const stopRecording = () => {
        if (recognitionRef.current && isRecording) {
            recognitionRef.current.stop();
            setIsRecording(false);
        }
    };

    return (
        <div className="absolute bottom-4 right-4 flex flex-col items-center p-3 bg-slate-900/80 backdrop-blur border border-slate-700 rounded-xl shadow-2xl z-50 pointer-events-auto">
            {/* Language Selector Dropdown */}
            <select 
                value={selectedLang}
                onChange={(e) => setSelectedLang(e.target.value)}
                className="bg-slate-800 text-white text-[10px] mb-2 p-1 rounded border border-slate-600 outline-none cursor-pointer"
            >
                {LANGUAGES.map(lang => (
                    <option key={lang.code} value={lang.code}>{lang.label}</option>
                ))}
            </select>

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

            {/* Resolution Controls */}
            <div className="flex gap-2 mt-4 w-full justify-center">
                <button 
                    onClick={() => resolveTriage('Medivac Required')} 
                    className="px-3 py-1.5 text-[10px] bg-red-600/80 hover:bg-red-500 rounded text-white font-bold tracking-wider uppercase transition-colors"
                >
                    Medivac
                </button>
                <button 
                    onClick={() => resolveTriage('Safe')} 
                    className="px-3 py-1.5 text-[10px] bg-emerald-600/80 hover:bg-emerald-500 rounded text-white font-bold tracking-wider uppercase transition-colors"
                >
                    Safe / Clear
                </button>
            </div>
        </div>
    );
}